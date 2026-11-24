# ============================================================
# PLACEPRO - SALARY PREDICTION SERVICE
# ============================================================

import os
import sys

import joblib
import pandas as pd


# ============================================================
# PROJECT CONFIGURATION
# ============================================================

# Project root:
# salary_prediction_service.py
# -> services
# -> app
# -> backend
# -> project root

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(
        os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        )
    )
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


MODEL_PATH = os.path.join(
    PROJECT_ROOT,
    "models",
    "placepro_salary_model_v2.pkl",
)

MODEL_VERSION = "placepro-salary-v2"

_MODEL = None


# ============================================================
# COLLEGE TIER DEFAULT
# ============================================================

# The salary page no longer sends a college tier. When the request omits
# it (or sends null / ""), the service resolves it to this value.
#
# "Tier 2" is not an arbitrary pick: it is evidence-based from the served
# model itself. The salary pipeline's categorical SimpleImputer
# (strategy="most_frequent") learned "Tier 2" as the most frequent college
# tier of the placed students it was trained on, and the OneHotEncoder's
# observed categories are exactly ["Tier 1", "Tier 2", "Tier 3"]. So a
# missing tier is resolved to the same category the model would impute.
#
# Overridable with PLACEPRO_SALARY_DEFAULT_COLLEGE_TIER (same env-var
# convention as the other services); any accepted spelling is normalized.
DEFAULT_COLLEGE_TIER = (
    os.environ.get("PLACEPRO_SALARY_DEFAULT_COLLEGE_TIER") or "Tier 2"
)


# ============================================================
# TRAINING FEATURE SUPPORT (ANTI-EXTRAPOLATION GUARD)
# ============================================================

# Every numeric model input is clipped to the range that input actually takes
# in the placed-student training data (placement.csv) - the only range the
# served model has ever seen.
#
# Why this is needed: the salary model is a linear Ridge regression with a
# positive intercept, so an input outside its training range extrapolates
# along a straight line. The documented all-zero profile (cgpa 0,
# aptitude 0, ...) used to return 4.11 LPA, which is BELOW the 7.11 LPA
# minimum salary present anywhere in the training target - a salary the model
# could never have learned from data containing only salaries >= 7.11 LPA.
#
# Inputs inside this range are passed through UNCHANGED: a genuine score of 0
# stays 0 wherever 0 is supported (backlogs, internships, projects, ...). The
# guard only prevents extrapolation; it never substitutes a default for a
# real value.
#
# These bounds are not hand-picked. They are the observed min/max of each
# column over the placed students in the training data, and
# tests/test_salary_prediction.py recomputes them from that data so they
# cannot silently drift from the model's actual domain. Count-feature bounds
# are ints so count inputs stay ints.
FEATURE_SUPPORT = {
    "cgpa": (4.5, 10.0),
    "internships_count": (0, 8),
    "projects_count": (0, 13),
    "certifications_count": (0, 11),
    "coding_skill_score": (20.0, 100.0),
    "aptitude_score": (20.0, 100.0),
    "communication_skill_score": (20.0, 100.0),
    "hackathons_participated": (0, 7),
    "backlogs": (0, 5),
    "extracurricular_score": (0.0, 100.0),
}


# ============================================================
# BRANCH NORMALIZATION
# ============================================================

BRANCH_MAPPING = {
    "Computer Science & Engineering": "CSE",
    "Computer Science and Engineering": "CSE",
    "Information Science & Engineering": "IT",
    "Information Science and Engineering": "IT",
    "Electronics and Communication Engineering": "ECE",
    "Electrical and Electronics Engineering": "EEE",
    "Mechanical Engineering": "Mechanical",
    "Civil Engineering": "Civil",
    # Canonical short codes used by the frontend profile form
    # (profileConfig.js BRANCH_OPTIONS) mapped to the salary
    # dataset's categories. Without these, "EE" / "ME" / "CE"
    # reach the encoder as unknown values and are silently
    # one-hot-ignored (handle_unknown="ignore").
    "EE": "EEE",
    "ME": "Mechanical",
    "CE": "Civil",
}


# The salary dataset (salary_model/placement.csv) uses these exact
# tier spellings. The placement form uses "Tier-1" / "1" spellings,
# so both the frontend and this service normalize them.
COLLEGE_TIER_MAPPING = {
    "Tier 1": "Tier 1",
    "Tier 2": "Tier 2",
    "Tier 3": "Tier 3",
    "Tier-1": "Tier 1",
    "Tier-2": "Tier 2",
    "Tier-3": "Tier 3",
    "1": "Tier 1",
    "2": "Tier 2",
    "3": "Tier 3",
}


def normalize_college_tier(tier: str) -> str:
    """Convert any accepted tier spelling to the dataset categories."""

    normalized = str(tier).strip()

    return COLLEGE_TIER_MAPPING.get(normalized, normalized)


def resolve_college_tier(tier) -> str:
    """Resolve an optional college tier to a supported model category.

    Missing (None), empty, and whitespace-only values fall back to
    DEFAULT_COLLEGE_TIER. Every other accepted spelling is normalized
    exactly as before, so existing requests that still send a tier keep
    their current behavior. Unknown-but-non-empty values are passed
    through to the pipeline, which one-hot-ignores them
    (handle_unknown="ignore").
    """

    if tier is None:
        return normalize_college_tier(DEFAULT_COLLEGE_TIER)

    if isinstance(tier, str) and tier.strip() == "":
        return normalize_college_tier(DEFAULT_COLLEGE_TIER)

    return normalize_college_tier(tier)


def normalize_branch(branch: str) -> str:
    """Convert frontend branch labels to dataset categories."""

    normalized = str(branch).strip()

    return BRANCH_MAPPING.get(normalized, normalized)


# ============================================================
# MODEL LOADING
# ============================================================

def _load_model():
    """Load the salary prediction model lazily."""

    global _MODEL

    if _MODEL is None:
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(
                f"Salary model not found at: {MODEL_PATH}"
            )

        _MODEL = joblib.load(MODEL_PATH)

    return _MODEL


# ============================================================
# INPUT CONVERSION
# ============================================================

def _convert_skill_score(value: float) -> float:
    """
    Convert a frontend skill score from 0???10 to 0???100.

    The training dataset uses scores between 20 and 100.
    Values are bounded to that observed range.

    Validate this conversion against the dataset-generation
    logic before treating it as the final production mapping.
    """

    score = float(value) * 10.0

    return max(20.0, min(100.0, score))


def _convert_extracurricular_score(value: int) -> float:
    """
    Convert extracurricular activity count (0???3) to a
    provisional 0???100 score.

    This is a provisional mapping, not a verified equivalence
    with the original dataset's extracurricular_score feature.
    """

    count = max(0.0, min(3.0, float(value)))

    return (count / 3.0) * 100.0


# ============================================================
# SALARY PREDICTION
# ============================================================

def predict_salary(profile: dict) -> dict:
    """
    Predict estimated salary conditional on placement.

    college_tier is optional (missing / null / empty resolves to
    DEFAULT_COLLEGE_TIER, and the frontend no longer sends it).
    The trained salary model uses only these 12 features:

        1. cgpa
        2. branch
        3. college_tier
        4. internships_count
        5. projects_count
        6. certifications_count
        7. coding_skill_score
        8. aptitude_score
        9. communication_skill_score
       10. hackathons_participated
       11. backlogs
       12. extracurricular_score

    Numeric inputs are clipped to FEATURE_SUPPORT - the range each
    feature takes in the training data - so the linear model cannot
    extrapolate a salary outside the range it was trained on. In-range
    values (including genuine zeros) are passed through unchanged.

    Salary is an estimate, not a guaranteed job offer.
    """

    # Normalize branch names.
    branch = normalize_branch(profile["branch"])

    # Normalize accepted tier spellings to the dataset categories
    # ("Tier 1" / "Tier 2" / "Tier 3"); missing, null, and empty
    # values fall back to DEFAULT_COLLEGE_TIER.
    college_tier = resolve_college_tier(profile.get("college_tier"))

    # Convert skill scores.
    coding_score = _convert_skill_score(
        profile["coding_skills"]
    )

    communication_score = _convert_skill_score(
        profile["communication_skills"]
    )

    # Convert extracurricular count provisionally.
    extracurricular_score = _convert_extracurricular_score(
        profile["extracurriculars"]
    )

    # Build model input using the exact feature names
    # expected by the saved training pipeline.
    model_input = {
        "cgpa": float(profile["cgpa"]),
        "branch": branch,
        "college_tier": college_tier,
        "internships_count": int(
            profile["internships"]
        ),
        "projects_count": int(
            profile["projects_count"]
        ),
        "certifications_count": int(
            profile["certifications"]
        ),
        "coding_skill_score": coding_score,
        "aptitude_score": float(
            profile["aptitude_score"]
        ),
        "communication_skill_score": communication_score,
        "hackathons_participated": int(
            profile["hackathons"]
        ),
        "backlogs": int(
            profile["backlogs"]
        ),
        "extracurricular_score": extracurricular_score,
    }

    # Guard against extrapolation: clip every numeric input to the range
    # the model was trained on. Without this, a linear model extrapolates
    # for out-of-range inputs (see FEATURE_SUPPORT).
    for feature, (low, high) in FEATURE_SUPPORT.items():
        model_input[feature] = min(max(model_input[feature], low), high)

    # Create the DataFrame expected by the saved pipeline.
    frame = pd.DataFrame([model_input])

    # Generate prediction.
    prediction = float(
        _load_model().predict(frame)[0]
    )

    # Return the existing API response format.
    return {
        "predicted_salary_lpa": prediction,
        "model_version": MODEL_VERSION,
    }