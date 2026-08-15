# ============================================================
# PLACEPRO - PHASE 10 - ML FEATURE MAPPING LAYER
# ============================================================
#
# verified_student_profile
#         |
#         v
#   ml_feature_mapping  (this module)
#         |
#         v
#   src.pipeline.py     (Phase 8 model - untouched)
#         |
#         v
#   prediction           (Phase 11 - NOT wired yet)
#
# RULES
#   - The feature contract is IMPORTED from src.pipeline.RAW_FEATURE_COLUMNS
#     (single source of truth - no duplicate list, nothing guessed).
#   - A feature is mapped ONLY when there is a defensible relationship
#     between the verified profile and the model input:
#         * cgpa            <- education.cgpa
#         * branch          <- education.branch (documented synonyms only)
#         * internships     <- count of profile.internships
#         * projects_count  <- count of profile.projects
#         * certifications  <- count of profile.certifications
#         * hackathons      <- count of achievements.hackathons
#         * the other 10    <- user-provided via ml_inputs (never derived)
#   - Anything else is None -> "requires manual input". A skill like
#     "Python" is NEVER converted into coding_skill_score = 90; no such
#     deterministic mapping exists in this project.
#
# ============================================================

import os
import sys

# Project root on sys.path so `src.pipeline` imports from anywhere
_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.pipeline import RAW_FEATURE_COLUMNS  # noqa: E402  (exact feature contract)

# Features with a defensible resume-derived source
RESUME_DERIVED_FEATURES = (
    "cgpa",
    "branch",
    "internships",
    "projects_count",
    "certifications",
    "hackathons",
)

# Features with NO defensible resume source -> student provides via ml_inputs
MANUAL_INPUT_FEATURES = (
    "college_tier",
    "backlogs",
    "coding_skills",
    "dsa_score",
    "aptitude_score",
    "communication_skills",
    "ml_knowledge",
    "system_design",
    "open_source_contributions",
    "extracurriculars",
)

# Documented, defensible branch synonyms -> the dataset's branch values
# (data/placement_phase6.csv: CE, CSE, Chemical, ECE, EE, IT, ME).
# A branch with no defensible mapping stays None (requires manual input).
BRANCH_SYNONYMS = {
    "cse": "CSE",
    "computer science": "CSE",
    "computer science and engineering": "CSE",
    "it": "IT",
    "information technology": "IT",
    "ece": "ECE",
    "electronics": "ECE",
    "electronics and communication": "ECE",
    "electronics and communication engineering": "ECE",
    "ee": "EE",
    "electrical": "EE",
    "electrical and electronics": "EE",
    "electrical and electronics engineering": "EE",
    "eee": "EE",
    "me": "ME",
    "mechanical": "ME",
    "mechanical engineering": "ME",
    "ce": "CE",
    "civil": "CE",
    "civil engineering": "CE",
    "chemical": "Chemical",
    "chemical engineering": "Chemical",
}


def _map_branch(branch_text):
    """Map an education.branch string to a dataset branch, or None."""
    if not branch_text:
        return None
    key = str(branch_text).strip().lower()
    return BRANCH_SYNONYMS.get(key)


def map_profile_to_ml_features(profile: dict) -> dict:
    """Map a verified/canonical profile dict to the 16 Phase 8 model inputs.

    Returns {feature_name: value-or-None} for EXACTLY the 16 features in
    src.pipeline.RAW_FEATURE_COLUMNS. None = missing / requires manual input.
    """
    mapping = {col: None for col in RAW_FEATURE_COLUMNS}

    education = profile.get("education") or {}
    mapping["cgpa"] = education.get("cgpa")
    mapping["branch"] = _map_branch(education.get("branch"))

    # Counts derive deterministically from the profile's confirmed lists
    mapping["internships"] = len(profile.get("internships") or [])
    mapping["projects_count"] = len(profile.get("projects") or [])
    mapping["certifications"] = len(profile.get("certifications") or [])
    achievements = profile.get("achievements") or {}
    mapping["hackathons"] = len(achievements.get("hackathons") or [])

    # The remaining features come ONLY from explicit user input
    ml_inputs = profile.get("ml_inputs") or {}
    for feature in MANUAL_INPUT_FEATURES:
        mapping[feature] = ml_inputs.get(feature)

    return mapping


def check_profile_completion(profile: dict) -> dict:
    """Return {profile_complete, missing_fields, ml_feature_mapping}.

    Informational only in Phase 10 - the model is NOT called here.
    """
    mapping = map_profile_to_ml_features(profile)
    missing_fields = [f for f, v in mapping.items() if v is None]
    return {
        "profile_complete": len(missing_fields) == 0,
        "missing_fields": missing_fields,
        "ml_feature_mapping": mapping,
    }
