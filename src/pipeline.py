# ============================================================
# PLACEPRO - FINAL REUSABLE PREDICTION PIPELINE
# Phase 8 - Single source of truth for the production model
# ============================================================
#
# This module IS the final prediction pipeline. It is the ONLY
# place that knows:
#   - the exact raw input schema (the 16 feature columns)
#   - the exact feature engineering rules (Phase 7, verbatim)
#   - the exact preprocessing + model (saved as one joblib file)
#
# The saved artifact (models/placepro_final_model.pkl) is a single
# scikit-learn Pipeline:
#
#     feature_engineering (FunctionTransformer -> create_features)
#       -> preprocessing (impute + scale / one-hot encode)
#       -> Logistic Regression (Phase 7 tuned grid)
#
# Because feature engineering lives INSIDE the pipeline, prediction
# uses EXACTLY the same transforms that were applied during training
# — no drift between training and prediction, no leakage.
#
# Output schema (dict):
#     {
#         "placement_probability": float 0..1  (P(PLACED)),
#         "prediction":            "PLACED" | "NOT PLACED"  (threshold 0.50),
#         "confidence":            float 0..1  (max(p, 1-p)),
#         "model_version":         str
#     }
#
# Usage:
#     from src.pipeline import predict_placement
#     result = predict_placement({...16 raw columns...})
#
# ============================================================

import os
import sys

import joblib
import numpy as np
import pandas as pd

# Make the project root importable regardless of where this module is
# imported from (needed so the saved pipeline can be unpickled - the
# FunctionTransformer references src.pipeline.create_features).
# Same pattern as src/predictor.py (Phase 4).
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler

# Module-level cache: load the saved pipeline once per process
# (the backend server calls predict_placement per request).
_pipeline_cache = {}

# ------------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------------

# Project root = parent of the `src` directory
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_MODEL_PATH = os.path.join(PROJECT_ROOT, "models", "placepro_final_model.pkl")

MODEL_VERSION = "placepro-final-v1"

# The exact raw feature columns the model was trained on.
# (placement_status = target; salary_package_lpa / student_id = leakage,
#  both handled below and never seen by the model.)
RAW_FEATURE_COLUMNS = [
    "branch",
    "college_tier",
    "cgpa",
    "backlogs",
    "coding_skills",
    "dsa_score",
    "aptitude_score",
    "communication_skills",
    "ml_knowledge",
    "system_design",
    "internships",
    "projects_count",
    "certifications",
    "hackathons",
    "open_source_contributions",
    "extracurriculars",
]

TARGET_COLUMN = "placement_status"

# Columns the model must NEVER see (target / post-placement leakage / ID)
LEAKAGE_COLUMNS = ("salary_package_lpa", "student_id")

# Decision threshold (Phase 7 production decision: 0.50)
DECISION_THRESHOLD = 0.50

# ------------------------------------------------------------------
# FEATURE ENGINEERING (verbatim rules from Phase 7, cleaned of debug
# prints). All transforms are deterministic, fixed-domain rules:
# no statistic is fitted on the data, so there is no leakage risk
# and engineering can safely run before any split.
# ------------------------------------------------------------------


def create_features(df):
    """Apply the Phase 7 feature-engineering rules to a raw DataFrame.

    Accepts the 16 raw feature columns (extra columns such as the
    target or leakage columns are ignored/dropped).
    """
    df = df.copy()

    # ---- Drop post-placement / ID leakage columns -----------------
    for col in LEAKAGE_COLUMNS:
        if col in df.columns:
            df = df.drop(columns=[col])

    # ---- Normalized skill components (fixed scales) ---------------
    def norm01(s, hi):
        return (df[s] / hi).clip(0, 1) if s in df.columns else None

    coding = norm01("coding_skills", 10)
    dsa = norm01("dsa_score", 10)
    aptitude = norm01("aptitude_score", 100)
    comm = norm01("communication_skills", 10)
    ml = norm01("ml_knowledge", 10)
    sysd = norm01("system_design", 10)

    def mean_of(cols):
        present = [c for c in cols if c is not None]
        if not present:
            return None
        return pd.concat(present, axis=1).mean(axis=1)

    # 1. Overall skill score (all six skills, aptitude on 0-100 scale)
    overall = mean_of([coding, dsa, aptitude, comm, ml, sysd])
    if overall is not None:
        df["overall_skill_score"] = overall

    # 2. Academic skill index (academics + aptitude + DSA + coding)
    academic = mean_of([norm01("cgpa", 10), aptitude, dsa, coding])
    if academic is not None:
        df["academic_skill_index"] = academic

    # 3. Experience score (log-scaled count features)
    exp_cols = [
        "internships",
        "projects_count",
        "certifications",
        "hackathons",
        "open_source_contributions",
    ]
    present_exp = [c for c in exp_cols if c in df.columns]
    if present_exp:
        df["experience_score"] = np.log1p(df[present_exp]).mean(axis=1)

    # 4. High CGPA indicator
    if "cgpa" in df.columns:
        df["high_cgpa"] = (df["cgpa"] >= 7.5).astype(int)

    # 5. Has internship indicator
    if "internships" in df.columns:
        df["has_internship"] = (df["internships"] >= 1).astype(int)

    # 6. Project level (0 / 1-2 / 3-4 / 5+ projects)
    if "projects_count" in df.columns:
        df["project_level"] = np.digitize(df["projects_count"], bins=[1, 3, 5])

    # 7. Coding x experience interaction
    if coding is not None and "internships" in df.columns:
        df["coding_experience_interaction"] = (
            df["coding_skills"] * (df["internships"] + 1)
        )

    # 8. CGPA x projects interaction
    if "cgpa" in df.columns and "projects_count" in df.columns:
        df["cgpa_projects_interaction"] = (
            df["cgpa"] * (df["projects_count"] + 1)
        )

    # 9. Backlog risk indicator
    if "backlogs" in df.columns:
        df["backlog_risk"] = (df["backlogs"] >= 1).astype(int)

    # 10. Strong candidate indicator
    if all(c in df.columns for c in ["cgpa", "coding_skills", "internships"]):
        df["strong_candidate_indicator"] = (
            (df["cgpa"] >= 7.5)
            & (df["coding_skills"] >= 6)
            & (df["internships"] >= 1)
        ).astype(int)

    return df


# ------------------------------------------------------------------
# PIPELINE BUILDERS
# ------------------------------------------------------------------


def build_preprocessor(numerical_features, categorical_features):
    """Numeric: median imputation -> StandardScaler.
    Categorical: most-frequent imputation -> OneHotEncoder(ignore).
    Column lists are explicit (captured at fit time), so the pipeline
    is robust to column ordering and dtype changes at prediction time.
    """
    numeric_transformer = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])

    categorical_transformer = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ])

    return ColumnTransformer(
        transformers=[
            ("num", numeric_transformer, numerical_features),
            ("cat", categorical_transformer, categorical_features),
        ],
        remainder="drop",
    )


def build_final_pipeline(model, numerical_features, categorical_features):
    """Full leak-free pipeline:
        feature_engineering -> preprocessing -> model
    Saved as ONE joblib file; prediction needs zero extra code."""
    return Pipeline(steps=[
        ("feature_engineering",
         FunctionTransformer(create_features, validate=False)),
        ("preprocessor",
         build_preprocessor(numerical_features, categorical_features)),
        ("model", model),
    ])


# ------------------------------------------------------------------
# PREDICTION
# ------------------------------------------------------------------


def predict_placement(student_data, model_path=None):
    """Predict placement for a raw student profile.

    Parameters
    ----------
    student_data : dict or pandas.DataFrame
        Must contain the 16 raw feature columns (see RAW_FEATURE_COLUMNS).
        Extra columns (e.g. placement_status, salary_package_lpa,
        student_id) are ignored / dropped before prediction.
    model_path : str, optional
        Path to the saved final pipeline. Defaults to
        models/placepro_final_model.pkl.

    Returns
    -------
    dict
        {
            "placement_probability": float 0..1 (P(PLACED)),
            "prediction":            "PLACED" | "NOT PLACED",
            "confidence":            float 0..1 (max(p, 1-p)),
            "model_version":         str
        }
    """
    if model_path is None:
        model_path = DEFAULT_MODEL_PATH

    if not os.path.exists(model_path):
        raise FileNotFoundError(
            f"Saved model not found at: {model_path}\n"
            "Run `python phase8_final_pipeline.py` first to train and "
            "save the final pipeline."
        )

    if model_path not in _pipeline_cache:
        _pipeline_cache[model_path] = joblib.load(model_path)
    pipeline = _pipeline_cache[model_path]

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
        columns=[c for c in LEAKAGE_COLUMNS if c in student_data.columns],
        errors="ignore",
    )

    probability = float(pipeline.predict_proba(student_data)[0][1])
    predicted_class = int(pipeline.predict(student_data)[0])

    # Confidence = model certainty in the predicted class
    confidence = max(probability, 1.0 - probability)

    return {
        "placement_probability": round(probability, 6),
        "prediction": "PLACED" if predicted_class == 1 else "NOT PLACED",
        "confidence": round(confidence, 6),
        "model_version": MODEL_VERSION,
    }


# ------------------------------------------------------------
# Quick self-test when run directly:  python src/pipeline.py
# ------------------------------------------------------------
if __name__ == "__main__":
    sample = {
        "branch": "CSE",
        "college_tier": "Tier-1",
        "cgpa": 8.5,
        "backlogs": 0,
        "coding_skills": 8.2,
        "dsa_score": 8.0,
        "aptitude_score": 85.0,
        "communication_skills": 7.5,
        "ml_knowledge": 6.5,
        "system_design": 5.0,
        "internships": 2,
        "projects_count": 4,
        "certifications": 2,
        "hackathons": 1,
        "open_source_contributions": 1,
        "extracurriculars": 1,
    }

    result = predict_placement(sample)
    print("Sample student prediction:")
    for key, value in result.items():
        print(f"  {key}: {value}")
