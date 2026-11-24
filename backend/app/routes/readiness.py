# ============================================================
# PLACEPRO - PHASE 12 - READINESS / SKILL-GAP ROUTES
# ============================================================
#
#   GET /api/profile/{profile_id}/readiness
#       -> transparent readiness score + strengths + skill gaps
#          + improvement plan (verified profiles only)
#
#   GET /api/profile/{profile_id}/placement-summary
#       -> Phase 11 ML prediction + Phase 12 readiness, side by
#          side (never merged)
#
# ============================================================

from fastapi import APIRouter, HTTPException

from ..schemas_readiness import PlacementSummaryResponse, ReadinessResponse
from ..services.profile_service import ProfileServiceError
from ..services.readiness_service import (
    ReadinessServiceError,
    get_placement_summary,
    get_readiness,
)

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get(
    "/{profile_id}/readiness",
    response_model=ReadinessResponse,
    summary="Transparent placement readiness + skill-gap analysis",
)
def profile_readiness(profile_id: str):
    """Readiness analysis from VERIFIED profile information only.

    - Unverified profile -> 422 (must be explicitly confirmed first).
    - Readiness score is a transparent rule-based 0-100 value, NOT
      the ML placement probability.
    - Missing skills are reported as "not found in verified profile",
      never as "student does not know X".
    """
    try:
        return get_readiness(profile_id)
    except (ProfileServiceError, ReadinessServiceError) as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(
            status_code=500, detail=f"Readiness analysis failed: {exc}"
        ) from exc


@router.get(
    "/{profile_id}/placement-summary",
    response_model=PlacementSummaryResponse,
    summary="Combined ML prediction + readiness summary",
)
def profile_placement_summary(profile_id: str):
    """Combined view: Phase 11 ML prediction + Phase 12 readiness.

    The two scores measure different things and are NEVER merged.
    The prediction runs the exact Phase 11 flow (verified ->
    complete -> src.pipeline.predict_placement).
    """
    try:
        return get_placement_summary(profile_id)
    except (ProfileServiceError, ReadinessServiceError) as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(
            status_code=500, detail=f"Placement summary failed: {exc}"
        ) from exc
