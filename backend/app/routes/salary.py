from fastapi import APIRouter, HTTPException

from ..schemas_salary import SalaryPredictionRequest, SalaryPredictionResponse
from ..services.salary_prediction_service import predict_salary


router = APIRouter(prefix="/api", tags=["salary prediction"])


@router.post(
    "/salary-predict",
    response_model=SalaryPredictionResponse,
    summary="Estimate salary conditional on placement",
)
def salary_predict_endpoint(profile: SalaryPredictionRequest):
    """Estimate salary using the dedicated Ridge salary model."""

    try:
        return predict_salary(profile.model_dump())

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Salary model not available: {exc}",
        ) from exc

    except Exception as exc:  # pragma: no cover
        raise HTTPException(
            status_code=500,
            detail=f"Salary prediction failed: {exc}",
        ) from exc
