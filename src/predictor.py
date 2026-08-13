# ============================================================
# PLACEPRO - REUSABLE PREDICTION FUNCTION
# Phase 4 - predict_placement(student_data)
# ============================================================
#
# The saved Phase 4 model is a single scikit-learn Pipeline:
#
#     feature_engineering -> preprocessing -> tuned classifier
#
# Because the feature engineering lives INSIDE the pipeline, this
# function uses EXACTLY the same preprocessing and feature
# engineering that was applied during training — no extra code,
# no risk of drift between training and prediction.
#
# Usage:
#     from src.predictor import predict_placement
#
#     result = predict_placement({
#         "age": 21,
#         "gender": "Male",
#         "cgpa": 8.2,
#         "branch": "CSE",
#         "college_tier": "Tier 1",
#         # ... all raw training columns ...
#     })
#     print(result["status"], result["probability"])

import os
import sys

import joblib
import pandas as pd

# Make `src` importable regardless of where this module is imported from
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DEFAULT_MODEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "models",
    "placepro_tuned_best_model.pkl",
)

# Columns the model must NEVER see (target / leakage / identifier)
FORBIDDEN_COLUMNS = ("placement_status", "salary_package_lpa", "student_id")


def predict_placement(student_data, model_path=None):
    """
    Predict whether a student will be placed.

    Parameters
    ----------
    student_data : dict or pandas.DataFrame
        Student attributes. Must contain the same raw columns that
        were used during training (target / salary / student_id are
        ignored if present).
    model_path : str, optional
        Path to the saved Phase 4 pipeline. Defaults to
        models/placepro_tuned_best_model.pkl.

    Returns
    -------
    dict
        {
            "status":      "PLACED" | "NOT PLACED",
            "probability": float between 0 and 100 (probability of PLACED)
        }
    """
    if model_path is None:
        model_path = DEFAULT_MODEL_PATH

    if not os.path.exists(model_path):
        raise FileNotFoundError(
            f"Saved model not found at: {model_path}\n"
            "Run `python phase4_model_tuning.py` first to train and "
            "save the Phase 4 model."
        )

    # Load the full pipeline (feature engineering + preprocessing + model)
    pipeline = joblib.load(model_path)

    # Normalise input into a single-row DataFrame
    if isinstance(student_data, dict):
        student_data = pd.DataFrame([student_data])
    elif isinstance(student_data, pd.DataFrame):
        student_data = student_data.copy()
    else:
        raise TypeError(
            "student_data must be a dict or a pandas DataFrame, "
            f"got {type(student_data).__name__}"
        )

    # Defensively drop anything the model must not see
    student_data = student_data.drop(
        columns=[c for c in FORBIDDEN_COLUMNS if c in student_data.columns],
        errors="ignore",
    )

    # The pipeline applies the exact same feature engineering +
    # preprocessing used during training.
    predicted_class = pipeline.predict(student_data)[0]

    probability = pipeline.predict_proba(student_data)[0][1] * 100.0

    return {
        "status": "PLACED" if predicted_class == 1 else "NOT PLACED",
        "probability": float(probability),
    }


# ------------------------------------------------------------
# Quick self-test when run directly:  python src/predictor.py
# ------------------------------------------------------------
if __name__ == "__main__":
    sample = {
        "age": 21,
        "gender": "Male",
        "cgpa": 8.4,
        "branch": "CSE",
        "college_tier": "Tier 1",
        "internships_count": 3,
        "projects_count": 4,
        "certifications_count": 2,
        "coding_skill_score": 88.0,
        "aptitude_score": 82.0,
        "communication_skill_score": 75.0,
        "logical_reasoning_score": 80.0,
        "hackathons_participated": 2,
        "github_repos": 5,
        "linkedin_connections": 300,
        "mock_interview_score": 70.0,
        "attendance_percentage": 85.0,
        "backlogs": 0,
        "extracurricular_score": 65.0,
        "leadership_score": 60.0,
        "volunteer_experience": "Yes",
        "sleep_hours": 7.0,
        "study_hours_per_day": 4.0,
    }

    result = predict_placement(sample)
    print(
        f"Prediction: {result['status']} "
        f"(probability {result['probability']:.2f}%)"
    )
