# ============================================================
# PLACEPRO - PHASE 10 - PROFILE SERVICE
# ============================================================
#
# Orchestrates the canonical student profile lifecycle:
#
#   resume -> draft profile (provenance.resume) -> student edits
#   -> verify (provenance.user) -> verified profile
#
# Storage: lightweight JSON files under data/profiles/ (dev-grade;
# a real database is a later phase). Uploaded RESUMES are never
# stored - only the resulting profiles.
#
# ============================================================

import json
import os
import re
import sys
import threading
import uuid
from datetime import datetime, timezone

from .ml_feature_mapping import check_profile_completion
from .prediction_service import predict as predict_with_model
from .resume_service import _process_resume_upload_full

# Project root on sys.path (same pattern as prediction_service)
PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Overridable for tests (PLACEPRO_PROFILES_DIR)
DEFAULT_PROFILES_DIR = os.path.join(PROJECT_ROOT, "data", "profiles")
PROFILES_DIR = os.environ.get("PLACEPRO_PROFILES_DIR") or DEFAULT_PROFILES_DIR

# The editable sections used for provenance diffing
EDITABLE_SECTIONS = (
    "personal",
    "education",
    "skills",
    "experience",
    "internships",
    "projects",
    "certifications",
    "achievements",
    "ml_inputs",
)

_ID_PATTERN = re.compile(r"^[A-Za-z0-9\-_]+$")

_lock = threading.Lock()


# ------------------------------------------------------------
# ERRORS
# ------------------------------------------------------------


class ProfileServiceError(Exception):
    status_code = 400


class ProfileNotFoundError(ProfileServiceError):
    status_code = 404


class InvalidProfileError(ProfileServiceError):
    status_code = 422


# ------------------------------------------------------------
# STORAGE
# ------------------------------------------------------------


def _profile_path(profile_id: str) -> str:
    return os.path.join(PROFILES_DIR, f"{profile_id}.json")


def _validate_id(profile_id: str) -> str:
    if not profile_id or not _ID_PATTERN.match(profile_id):
        raise InvalidProfileError(
            "Invalid profile_id - only letters, digits, '-' and '_' are allowed."
        )
    return profile_id


def _save(profile: dict) -> None:
    os.makedirs(PROFILES_DIR, exist_ok=True)
    profile_id = _validate_id(profile["profile_id"])
    path = _profile_path(profile_id)
    # Atomic-ish write: temp file then rename
    tmp_path = f"{path}.tmp"
    with _lock:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2)
        os.replace(tmp_path, path)


def _load(profile_id: str) -> dict:
    profile_id = _validate_id(profile_id)
    path = _profile_path(profile_id)
    if not os.path.exists(path):
        raise ProfileNotFoundError(f"Profile '{profile_id}' not found.")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ------------------------------------------------------------
# PROVENANCE HELPERS
# ------------------------------------------------------------


def collect_nonempty_paths(obj, prefix=""):
    """Dotted paths of non-empty leaves in a nested dict/list."""
    paths = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            child = f"{prefix}.{key}" if prefix else key
            paths.extend(collect_nonempty_paths(value, child))
    elif isinstance(obj, list):
        if obj:
            paths.append(prefix)
    else:
        if obj is not None:
            paths.append(prefix)
    return paths


def diff_paths(before: dict, after: dict, prefix=""):
    """Dotted paths whose leaf values differ between before and after."""
    changed = []
    if isinstance(before, dict) and isinstance(after, dict):
        for key in set(before) | set(after):
            child = f"{prefix}.{key}" if prefix else key
            changed.extend(diff_paths(before.get(key), after.get(key), child))
    elif isinstance(before, list) and isinstance(after, list):
        if before != after:
            changed.append(prefix)
    elif before != after:
        changed.append(prefix)
    return changed


def _editable_view(profile: dict) -> dict:
    return {section: profile.get(section) for section in EDITABLE_SECTIONS}


# ------------------------------------------------------------
# ORCHESTRATION
# ------------------------------------------------------------


def _extracted_path_values(extracted: dict) -> dict:
    """{dotted path: original value} for every non-empty extracted leaf."""
    values = {}
    for path in collect_nonempty_paths(extracted):
        value = _resolve_value(extracted, path)
        if value is not None:
            values[path] = value
    return values


def _resolve_value(obj, dotted_path):
    current = obj
    for part in dotted_path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return current


def build_draft_from_resume(filename: str, content: bytes, content_type=None):
    """Run Phase 9 extraction, then build a draft canonical profile.

    Returns (profile_dict, completion_dict).
    """
    extraction_result, _ = _process_resume_upload_full(
        filename, content, content_type
    )
    extracted = extraction_result["extracted_profile"]

    profile = {
        "profile_id": str(uuid.uuid4()),
        "personal": {
            key: extracted.get(key)
            for key in (
                "name", "email", "phone", "location",
                "linkedin", "github", "portfolio",
            )
        },
        "education": extracted.get("education") or {},
        "skills": extracted.get("skills") or {},
        "experience": extracted.get("experience") or [],
        "internships": extracted.get("internships") or [],
        "projects": extracted.get("projects") or [],
        "certifications": extracted.get("certifications") or [],
        "achievements": extracted.get("achievements") or {},
        "ml_inputs": {},
        "provenance": {
            "resume": collect_nonempty_paths(extracted),
            "user": [],
            "ml": [],
        },
        "original_resume_values": _extracted_path_values(extracted),
        "verified": False,
        "prediction_history": [],
    }

    _save(profile)
    completion = check_profile_completion(profile)
    return profile, completion


def verify_profile(submitted: dict):
    """Explicitly confirm a profile. Returns (profile_dict, completion_dict).

    - name and email are required to verify (the student must be
      identifiable).
    - provenance.user is computed by diffing against the stored draft
      (or all provided values for a brand-new profile).
    - The student's confirmation is REQUIRED - nothing is assumed
      correct from the resume.
    """
    personal = submitted.get("personal") or {}
    if not (personal.get("name") and personal.get("email")):
        raise InvalidProfileError(
            "name and email are required to verify a profile."
        )

    profile_id = submitted.get("profile_id")
    existing = None
    if profile_id:
        try:
            existing = _load(profile_id)
        except ProfileNotFoundError:
            existing = None  # brand-new profile with a client-chosen id

    if existing is not None:
        edited = diff_paths(
            _editable_view(existing), _editable_view(submitted)
        )
        resume_paths = [
            p for p in existing.get("provenance", {}).get("resume", [])
            if p not in edited
        ]
        user_paths = list(
            dict.fromkeys(
                existing.get("provenance", {}).get("user", []) + edited
            )
        )
    else:
        # No baseline: treat every provided value as user-provided
        user_paths = collect_nonempty_paths(_editable_view(submitted))
        resume_paths = []

    # prediction_history is server-controlled: never accept it from the
    # client (it would let a student forge history).
    history = (existing or {}).get("prediction_history", []) if existing else []

    # Phase 17: assessment evidence is server-controlled too (scores are
    # produced by the assessment engine, never by the client).
    assessment_evidence = (
        (existing or {}).get("assessment_evidence", [])
        if existing else []
    )

    # Phase 16: preserve original resume values when present (the
    # student's edits stay in the editable sections; the resume originals
    # are kept server-side for reference, never overwritten silently).
    originals = (existing or {}).get("original_resume_values", {})
    if not originals:
        originals = _extracted_path_values(
            _editable_view(submitted)
        ) if not existing else {}

    profile = {
        **submitted,
        "profile_id": profile_id or str(uuid.uuid4()),
        "provenance": {
            "resume": resume_paths,
            "user": user_paths,
            "ml": [],
        },
        "original_resume_values": originals,
        "assessment_evidence": assessment_evidence,
        "verified": True,
        "prediction_history": history,
    }

    _save(profile)
    completion = check_profile_completion(profile)
    return profile, completion


def get_profile(profile_id: str):
    """Return (profile_dict, completion_dict) for a stored profile."""
    profile = _load(profile_id)
    completion = check_profile_completion(profile)
    return profile, completion


def update_profile(profile_id: str, submitted: dict):
    """Apply student edits to a stored profile.

    Editing resets `verified` to False - the student must explicitly
    confirm again before the profile is considered verified.
    """
    existing = _load(profile_id)

    edited = diff_paths(_editable_view(existing), _editable_view(submitted))
    user_paths = list(
        dict.fromkeys(
            existing.get("provenance", {}).get("user", []) + edited
        )
    )
    resume_paths = [
        p for p in existing.get("provenance", {}).get("resume", [])
        if p not in user_paths
    ]

    # prediction_history and assessment_evidence are server-controlled
    # (never from the client)
    profile = {
        **submitted,
        "profile_id": profile_id,
        "provenance": {
            "resume": resume_paths,
            "user": user_paths,
            "ml": [],
        },
        "original_resume_values": existing.get("original_resume_values", {}),
        "assessment_evidence": existing.get("assessment_evidence", []),
        "verified": False,
        "prediction_history": existing.get("prediction_history", []),
    }

    _save(profile)
    completion = check_profile_completion(profile)
    return profile, completion


def create_draft_with_analysis(filename: str, content: bytes, content_type=None):
    """Phase 16: build a draft profile AND the full intelligence analysis.

    Returns (profile_dict, completion_dict, analysis_dict). The draft
    is saved (so the student can review/edit/verify it); the analysis
    is returned to the caller for the enhanced from-resume response.
    """
    from .resume_intelligence import build_analysis

    base, full_raw_text = _process_resume_upload_full(
        filename, content, content_type
    )
    extracted = base["extracted_profile"]

    profile = {
        "profile_id": str(uuid.uuid4()),
        "personal": {
            key: extracted.get(key)
            for key in (
                "name", "email", "phone", "location",
                "linkedin", "github", "portfolio",
            )
        },
        "education": extracted.get("education") or {},
        "skills": extracted.get("skills") or {},
        "experience": extracted.get("experience") or [],
        "internships": extracted.get("internships") or [],
        "projects": extracted.get("projects") or [],
        "certifications": extracted.get("certifications") or [],
        "achievements": extracted.get("achievements") or {},
        "ml_inputs": {},
        "provenance": {
            "resume": collect_nonempty_paths(extracted),
            "user": [],
            "ml": [],
        },
        "original_resume_values": _extracted_path_values(extracted),
        "verified": False,
        "prediction_history": [],
    }

    _save(profile)
    completion = check_profile_completion(profile)
    analysis = build_analysis(base, full_raw_text)
    return profile, completion, analysis


# ------------------------------------------------------------
# PREDICTION (Phase 11)
# ------------------------------------------------------------


def predict_for_profile(profile_id: str) -> dict:
    """Predict placement for a profile using the existing Phase 8 model.

    Flow: load -> verified check -> ML feature mapping -> completeness
    check -> src.pipeline.predict_placement() -> record history.

    The model is NEVER called for unverified or incomplete profiles,
    and missing features are NEVER invented.
    """
    profile = _load(profile_id)  # raises ProfileNotFoundError
    history = profile.get("prediction_history", [])

    if not profile.get("verified"):
        return {
            "ready_for_prediction": False,
            "prediction": None,
            "placement_probability": None,
            "confidence": None,
            "model_version": None,
            "reason": "Student profile must be verified first.",
            "prediction_history": history,
        }

    completion = check_profile_completion(profile)
    if not completion["profile_complete"]:
        return {
            "ready_for_prediction": False,
            "prediction": None,
            "placement_probability": None,
            "confidence": None,
            "model_version": None,
            "missing_fields": completion["missing_fields"],
            "prediction_history": history,
        }

    # All 16 Phase 8 features are available (verified + complete)
    ml_inputs = completion["ml_feature_mapping"]
    result = predict_with_model(ml_inputs)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model_version": result["model_version"],
        "placement_probability": result["placement_probability"],
        "prediction": result["prediction"],
    }
    history = history + [entry]
    profile["prediction_history"] = history
    _save(profile)

    return {
        "ready_for_prediction": True,
        "prediction": result["prediction"],
        "placement_probability": result["placement_probability"],
        "confidence": result["confidence"],
        "model_version": result["model_version"],
        "prediction_history": history,
    }
