# ============================================================
# PLACEPRO - SALARY PREDICTION SERVICE
# ============================================================

import os
import sys

import joblib
import pandas as pd


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


def _load_model():
    """Load the salary model lazily."""

    global _MODEL

    if _MODEL is None:
        _MODEL = joblib.load(MODEL_PATH)

    return _MODEL


def predict_salary(profile: dict) -> dict:
    """Predict estimated salary conditional on placement.

    The frontend sends the existing 16-field PlacePro profile.
    Only the 12 features used by the trained salary model are
    passed to the saved pipeline.
    """

    model_input = {
        "cgpa": profile["cgpa"],
        "branch": profile["branch"],
        "college_tier": profile["college_tier"],
        "internships_count": profile["internships"],
        "projects_count": profile["projects_count"],
        "certifications_count": profile["certifications"],
        "coding_skill_score": profile["coding_skills"],
        "aptitude_score": profile["aptitude_score"],
        "communication_skill_score": profile["communication_skills"],
        "hackathons_participated": profile["hackathons"],
        "backlogs": profile["backlogs"],
        "extracurricular_score": profile["extracurriculars"],
    }

    frame = pd.DataFrame([model_input])

    prediction = float(_load_model().predict(frame)[0])

    return {
        "predicted_salary_lpa": prediction,
        "model_version": MODEL_VERSION,
    }