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
import uuid
from copy import deepcopy
import math
from contextlib import contextmanager
from datetime import datetime, timezone
from pydantic import ValidationError
from ..schemas_profile import StudentProfile

from .ml_feature_mapping import check_profile_completion
from .prediction_service import predict as predict_with_model
from .resume_service import _process_resume_upload_full
from .storage_lock import StorageLockTimeout, record_transaction

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
    # Student-provided context that is NOT a model feature. Listed here so
    # edits get provenance.user like any other student input; the ML
    # feature mapping never reads it (see schemas_profile.AdditionalInfo).
    "additional_info",
)

_ID_PATTERN = re.compile(r"^[A-Za-z0-9\-_]+$")

# ------------------------------------------------------------
# ERRORS
# ------------------------------------------------------------


class ProfileServiceError(Exception):
    status_code = 400


class ProfileNotFoundError(ProfileServiceError):
    status_code = 404


class InvalidProfileError(ProfileServiceError):
    status_code = 422


class ProfileStorageBusyError(ProfileServiceError):
    status_code = 503


class ProfileConflictError(ProfileServiceError):
    status_code = 409


class ProfilePersistenceError(ProfileServiceError):
    status_code = 503


# ------------------------------------------------------------
# STORAGE
# ------------------------------------------------------------


def _profile_path(profile_id: str) -> str:
    return os.path.join(PROFILES_DIR, f"{profile_id}.json")


def _validate_id(profile_id: str) -> str:
    if not isinstance(profile_id, str) or not _ID_PATTERN.fullmatch(profile_id):
        raise InvalidProfileError(
            "Invalid profile_id - only letters, digits, '-' and '_' are allowed."
        )
    return profile_id


@contextmanager
def profile_transaction(profile_id: str):
    """Share one update lock across profile and assessment operations."""
    profile_id = _validate_id(profile_id)
    try:
        with record_transaction(PROFILES_DIR, profile_id):
            yield
    except StorageLockTimeout as exc:
        raise ProfileStorageBusyError(
            "Profile storage is busy. Please retry the request."
        ) from exc


def _save(profile: dict) -> None:
    profile_id = _validate_id(profile["profile_id"])
    path = _profile_path(profile_id)
    # Unique temporary files also avoid collisions with another process.
    tmp_path = f"{path}.{uuid.uuid4().hex}.tmp"
    with profile_transaction(profile_id):
        existing = _load(profile_id) if os.path.exists(path) else None
        candidate = deepcopy(profile)
        candidate['revision'] = (existing['revision'] + int(
            _revision_view(existing) != _revision_view(candidate)
        )) if existing is not None else 1
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(candidate, f, indent=2, allow_nan=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, path)
        except (OSError, ValueError) as exc:
            raise ProfilePersistenceError(
                'Profile could not be saved. Please retry; the previous profile is preserved.'
            ) from exc
        # Do not expose an advanced revision to the caller on failed replacement.
        profile['revision'] = candidate['revision']


def _load(profile_id: str) -> dict:
    profile_id = _validate_id(profile_id)
    path = _profile_path(profile_id)
    if not os.path.exists(path):
        raise ProfileNotFoundError(f"Profile '{profile_id}' not found.")
    # Windows cannot replace a file while a cooperating reader holds it open.
    # Reuse the writer lock so reads are snapshots and never break atomic saves.
    with profile_transaction(profile_id):
        with open(path, "r", encoding="utf-8") as f:
            profile = json.load(f)
    revision = profile.get('revision')
    profile['revision'] = revision if type(revision) is int and revision >= 0 else 0
    return profile


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
    # Normalize absent/null defaults for comparison, without rewriting legacy files.
    normalized = StudentProfile.model_validate({
        section: profile.get(section) for section in EDITABLE_SECTIONS if profile.get(section) is not None
    }).model_dump()
    return {section: normalized[section] for section in EDITABLE_SECTIONS}


def _revision_view(profile):
    return {**_editable_view(profile), 'verified': bool(profile.get('verified')),
            'provenance': profile.get('provenance') or {},
            'assessment_evidence': profile.get('assessment_evidence') or []}


def _validate_submission(submitted, existing=None):
    try:
        StudentProfile.model_validate(submitted)
    except ValidationError as exc:
        raise InvalidProfileError('Invalid profile fields. Please review your changes.') from exc
    # Validate new/changed numeric inputs only: legacy out-of-range values remain
    # readable, and unrelated corrections do not silently rewrite them.
    bounds = {'education.cgpa': (0, 10), 'ml_inputs.aptitude_score': (0, 100),
              **{f'ml_inputs.{key}': (0, 10) for key in (
                  'coding_skills', 'dsa_score', 'communication_skills', 'ml_knowledge', 'system_design')},
              **{f'ml_inputs.{key}': (0, None) for key in (
                  'backlogs', 'open_source_contributions', 'extracurriculars')}}
    for path, (minimum, maximum) in bounds.items():
        value = _resolve_value(submitted, path)
        if value is None or (existing is not None and value == _resolve_value(existing, path)):
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or \
                value < minimum or (maximum is not None and value > maximum) or \
                (path.endswith(('backlogs', 'open_source_contributions', 'extracurriculars')) and int(value) != value):
            raise InvalidProfileError(f'Invalid value for {path}. Please review your changes.')


def _check_revision(submitted, existing, *, confirming=False):
    expected = submitted.get('revision')
    if expected is None or expected == existing['revision']:
        return
    # Exact retries are harmless; a stale confirmation must not confirm a newer edit.
    if _editable_view(submitted) == _editable_view(existing) and (not confirming or existing.get('verified')):
        return
    raise ProfileConflictError('Profile changed since it was loaded. Reload it and review your edits before saving.')


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
    profile = _draft_from_extraction(extraction_result)
    completion = check_profile_completion(profile)
    _save(profile)
    return profile, completion


def _draft_from_extraction(extraction_result, *, profile_id=None):
    """Build an independent draft; neither email nor confirmation proves ownership."""
    if not extraction_result.get('success') or extraction_result.get('extraction', {}).get('ocr_required'):
        raise InvalidProfileError(
            'OCR_REQUIRED: no extractable text; no profile can be created from this file.'
            if extraction_result.get('extraction', {}).get('ocr_required')
            else 'No readable text could be extracted. Upload a readable PDF or DOCX.'
        )
    extracted = extraction_result["extracted_profile"]

    profile = {
        "profile_id": profile_id or str(uuid.uuid4()),
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
        "additional_info": {},
        "provenance": {
            "resume": collect_nonempty_paths(extracted),
            "user": [],
            "ml": [],
        },
        "original_resume_values": _extracted_path_values(extracted),
        "verified": False,
        "prediction_history": [],
    }

    # Personal extraction uses flat keys, while canonical edits use personal.*.
    profile['provenance']['resume'] = collect_nonempty_paths(_editable_view(profile))
    return profile


def verify_profile(submitted: dict):
    """Confirm a profile while preserving concurrently recorded evidence/history."""
    profile_id = submitted.get("profile_id") or str(uuid.uuid4())
    with profile_transaction(profile_id):
        return _verify_profile({**submitted, "profile_id": profile_id})


def _verify_profile(submitted: dict):
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
        _validate_submission(submitted, existing)
        _check_revision(submitted, existing, confirming=True)
        edited = diff_paths(
            _editable_view(existing), _editable_view(submitted)
        )
        if not edited and existing.get('verified'):
            return existing, check_profile_completion(existing)
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
        _validate_submission(submitted)
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

    profile = {
        **submitted,
        "profile_id": profile_id or str(uuid.uuid4()),
        "provenance": {
            "resume": resume_paths,
            "user": user_paths,
            "ml": (existing or {}).get('provenance', {}).get('ml', []),
        },
        "original_resume_values": originals,
        "assessment_evidence": assessment_evidence,
        "verified": True,
        "prediction_history": history,
        **{key:existing[key] for key in ('_creation_receipt','_request_receipts') if existing and key in existing},
    }

    completion = check_profile_completion(profile)
    _save(profile)
    return profile, completion


def get_profile(profile_id: str):
    """Return (profile_dict, completion_dict) for a stored profile."""
    profile = _load(profile_id)
    completion = check_profile_completion(profile)
    return profile, completion


def update_profile(profile_id: str, submitted: dict):
    """Apply edits under the same transaction used by assessment completion."""
    with profile_transaction(profile_id):
        return _update_profile(profile_id, submitted)


def _update_profile(profile_id: str, submitted: dict):
    """Apply student edits to a stored profile.

    Editing resets `verified` to False - the student must explicitly
    confirm again before the profile is considered verified.
    """
    existing = _load(profile_id)
    if submitted.get('profile_id') not in (None, profile_id):
        raise InvalidProfileError('Submitted profile_id does not match the selected profile.')
    _validate_submission(submitted, existing)
    _check_revision(submitted, existing)

    edited = diff_paths(_editable_view(existing), _editable_view(submitted))
    if not edited:
        return existing, check_profile_completion(existing)
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
            "ml": existing.get('provenance', {}).get('ml', []),
        },
        "original_resume_values": existing.get("original_resume_values", {}),
        "assessment_evidence": existing.get("assessment_evidence", []),
        "verified": False,
        "prediction_history": existing.get("prediction_history", []),
        **{key:existing[key] for key in ('_creation_receipt','_request_receipts') if key in existing},
    }

    completion = check_profile_completion(profile)
    _save(profile)
    return profile, completion


def create_draft_with_analysis(filename: str, content: bytes, content_type=None):
    """Phase 16: build a draft profile AND the full intelligence analysis.

    Returns (profile_dict, completion_dict, analysis_dict). The draft
    is saved (so the student can review/edit/verify it); the analysis
    is returned to the caller for the enhanced from-resume response.
    """
    profile,completion,analysis=prepare_draft_with_analysis(filename,content,content_type)
    _save(profile)
    return profile,completion,analysis


def prepare_draft_with_analysis(filename,content,content_type=None, *, profile_id=None):
    """Prepare without publication, for the account-bound creation workflow."""
    from .resume_intelligence import build_analysis

    base, full_raw_text = _process_resume_upload_full(
        filename, content, content_type
    )
    profile = _draft_from_extraction(base,profile_id=profile_id)
    completion = check_profile_completion(profile)
    analysis = build_analysis(base, full_raw_text)
    # Complete all extraction/analysis work before creating a persistent draft.
    return profile, completion, analysis


def prepare_confirmed_profile(submitted,profile_id):
    """Build a new confirmed profile without reading/claiming an existing record."""
    _validate_submission(submitted)
    personal=submitted.get('personal') or {}
    if not personal.get('name') or not personal.get('email'):
        raise InvalidProfileError('name and email are required to verify a profile.')
    profile={**submitted,'profile_id':profile_id,'revision':1,'verified':True,
             'provenance':{'resume':[],'user':collect_nonempty_paths(_editable_view(submitted)),'ml':[]},
             'original_resume_values':{},'assessment_evidence':[],'prediction_history':[]}
    return profile,check_profile_completion(profile)


def persist_new_profile(profile,encoded):
    """Exclusive creation; never replace a path, including a non-cooperating collision."""
    path=_profile_path(_validate_id(profile['profile_id']))
    try:
        with open(path,'xb') as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError:
        raise ProfileConflictError('New profile identity could not be created.') from None
    except OSError:
        raise ProfilePersistenceError('Profile creation is incomplete and unavailable. Please retry as a new creation.') from None


# ------------------------------------------------------------
# PREDICTION (Phase 11)
# ------------------------------------------------------------


def predict_for_profile(profile_id: str, *, request_id=None) -> dict:
    """Record prediction history without overwriting concurrent assessment evidence."""
    with profile_transaction(profile_id):
        return _predict_for_profile(profile_id, request_id=request_id)


def _predict_for_profile(profile_id: str, *, request_id=None) -> dict:
    profile = _load(profile_id)
    history = profile.get('prediction_history') or []
    if request_id:
        previous = next((entry for entry in history if entry.get('request_id') == request_id), None)
        if previous:
            if previous.get('source_revision') != profile['revision']:
                raise ProfileConflictError('This prediction request belongs to an earlier profile revision. Start a new prediction.')
            return {**previous, 'profile_id': profile_id, 'ready_for_prediction': True,
                    'prediction_history': history}
    result = prediction_for_snapshot(profile)
    if not result['ready_for_prediction']:
        return result
    inputs = check_profile_completion(profile)['ml_feature_mapping']
    entry = {key: result[key] for key in ('model_version', 'placement_probability', 'prediction', 'confidence')}
    entry.update(timestamp=datetime.now(timezone.utc).isoformat(), request_id=request_id,
                 source_revision=profile['revision'], source_inputs=inputs)
    profile['prediction_history'] = [*history, entry]
    _save(profile)
    result['prediction_history'] = profile.get('prediction_history') or []
    return result


def prediction_for_snapshot(profile: dict) -> dict:
    """Predict placement for a profile using the existing Phase 8 model.

    Flow: verified check -> ML feature mapping -> completeness check
    -> existing prediction model, without a history write.

    The model is NEVER called for unverified or incomplete profiles,
    and missing features are NEVER invented.
    """
    history = profile.get("prediction_history", [])
    metadata = {'profile_id': profile['profile_id'], 'source_revision': profile.get('revision', 0)}

    if not profile.get("verified"):
        return {
            **metadata,
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
            **metadata,
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

    return {
        **metadata,
        "ready_for_prediction": True,
        "prediction": result["prediction"],
        "placement_probability": result["placement_probability"],
        "confidence": result["confidence"],
        "model_version": result["model_version"],
        "prediction_history": history,
    }
