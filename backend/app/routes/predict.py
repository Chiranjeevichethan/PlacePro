# ============================================================
# PLACEPRO - PHASE 8 - PREDICTION ROUTE
# ============================================================

from fastapi import APIRouter, HTTPException

from ..schemas import PredictionResponse, StudentProfile
from ..services.prediction_service import predict

router = APIRouter(prefix="/api", tags=["prediction"])


@router.post(
    "/predict",
    response_model=PredictionResponse,
    summary="Predict placement probability for a student profile",
)
def predict_endpoint(profile: StudentProfile):
    """Predict placement for a raw student profile.

    Request body must contain the exact 16 feature columns the final
    model was trained on (see schemas.StudentProfile).
    """
    try:
        return predict(profile.model_dump())
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Model not available: {exc}",
        ) from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(
            status_code=500,
            detail=f"Prediction failed: {exc}",
        ) from exc
