# ============================================================
# PLACEPRO - PHASE 27 - PERFORMANCE ANALYTICS ROUTE
# ============================================================
#
#   GET /api/profile/{profile_id}/performance
#       -> consolidated view of prediction history, assessment
#          history, Phase 12 readiness and the combined skill view
#          (verified profiles only)
#
# Conventions follow routes/readiness.py: same prefix, same
# exception-to-HTTPException mapping, same 404/422 behavior.
#
# ============================================================

from fastapi import APIRouter, HTTPException

from ..schemas_performance import PerformanceResponse
from ..services.performance_service import (
    PerformanceServiceError,
    get_performance,
)
from ..services.profile_service import ProfileServiceError
from ..services.readiness_service import ReadinessServiceError

router = APIRouter(prefix="/api/profile", tags=["performance"])


@router.get(
    "/{profile_id}/performance",
    response_model=PerformanceResponse,
    summary="Consolidated performance analytics for a verified profile",
)
def profile_performance(profile_id: str):
    """Prediction history + assessment history + readiness + skills.

    - Unverified profile -> 422 (same convention as readiness /
      eligibility / recommendations / placement-summary).
    - All sections are derived from data already stored on the
      profile - nothing is fabricated.
    """
    try:
        return get_performance(profile_id)
    except (ProfileServiceError, ReadinessServiceError,
            PerformanceServiceError) as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(
            status_code=500, detail=f"Performance analysis failed: {exc}"
        ) from exc
