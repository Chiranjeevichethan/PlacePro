import os
from functools import lru_cache

import joblib
import pandas as pd
from experimental.v1.feature_schema import MODEL_FEATURES, MODEL_VERSION, UNSEEN_BRANCHES
from ..schemas_experimental_v1 import ExperimentalV1Request

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

MODEL_PATH = os.path.join(
    PROJECT_ROOT,
    "experimental",
    "v1",
    "placepro_v1_production_fields.pkl",
)

FEATURE_COLUMNS = MODEL_FEATURES

SYNTHETIC_DATA_NOTICE = (
    "This experimental prediction uses a model trained entirely on "
    "synthetic data. It is not a validated estimate of real-world "
    "placement outcomes. DSA score, ML knowledge, system design, open-source "
    "contributions and extracurricular activity count are validated but not "
    "used because this dataset has no matching features. Synthetic coding and "
    "communication scores were divided by 10 during training; this is not "
    "real-world score calibration."
)


@lru_cache(maxsize=1)
def _load_model():
    if not os.path.isfile(MODEL_PATH):
        raise FileNotFoundError(
            f"Experimental V1 model not found: {MODEL_PATH}"
        )
    model = joblib.load(MODEL_PATH)
    if list(model.feature_names_in_) != FEATURE_COLUMNS:
        raise ValueError("Experimental V1 model feature schema mismatch.")
    return model


def predict_experimental_v1(student_data: dict) -> dict:
    """Predict placement using the separate synthetic-data V1 model."""

    validated = ExperimentalV1Request.model_validate(student_data).model_dump()
    # Only 11 supported features enter the classifier. The other 5 API values
    # are required/validated but ignored, with no substitute or fabricated input.
    # Salary, placement labels and identifiers are never model inputs.
    row = {
        column: validated[column]
        for column in FEATURE_COLUMNS
    }
    features = pd.DataFrame([row], columns=FEATURE_COLUMNS)

    model = _load_model()
    probability = float(model.predict_proba(features)[0][1])

    prediction = (
        "Placed" if probability >= 0.50 else "Not Placed"
    )
    confidence = max(probability, 1.0 - probability)

    notice = SYNTHETIC_DATA_NOTICE
    if validated["branch"] in UNSEEN_BRANCHES:
        notice += (
            f" {validated['branch']} has no synthetic training rows. Its branch "
            "indicators are all zero; it is not mapped to another department."
        )
    return {
        "placement_probability": probability,
        "prediction": prediction,
        "confidence": confidence,
        "model_version": MODEL_VERSION,
        "experimental": True,
        "synthetic_data_notice": notice,
    }
