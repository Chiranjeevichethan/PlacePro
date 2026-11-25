# ============================================================
# PLACEPRO - PHASE 8 - PREDICTION SERVICE
# ============================================================
#
# Thin wrapper around src.pipeline.predict_placement - the ONE
# reusable prediction pipeline. The service adds no preprocessing
# of its own: the saved model pipeline (feature engineering +
# preprocessing + model) does everything, so the API can never
# drift from the trained model.
#
# ============================================================

import os
import sys

# Make the project root importable regardless of the working
# directory the server is started from (same trick as
# src/predictor.py).
PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.pipeline import predict_placement as _predict  # noqa: E402


def predict(profile: dict) -> dict:
    """Predict placement for a raw student profile dict.

    Returns the Phase 8 output schema:
        {
            "placement_probability": float 0..1,
            "prediction":            "PLACED" | "NOT PLACED",
            "confidence":            float 0..1,
            "model_version":         str,
        }
    """
    return _predict(profile)
