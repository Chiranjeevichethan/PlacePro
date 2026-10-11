# ============================================================
# PLACEPRO - PHASE 14 - COMPANY RECOMMENDATION ROUTE
# ============================================================
#
#   GET /api/profile/{profile_id}/recommendations[?limit=N]
#       -> transparent, ranked company recommendations for a
#          VERIFIED profile
#
# All scores / statuses / probabilities are computed server-side.
# `limit` is validated (1..50) and caps the total number of items.
#
# ============================================================

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..schemas_recommendation import RecommendationsResponse
from ..services.profile_service import ProfileServiceError
from ..services.recommendation_service import (
    RecommendationServiceError,
    get_recommendations,
)

router = APIRouter(tags=["recommendation"])


@router.get(
    "/api/profile/{profile_id}/recommendations",
    response_model=RecommendationsResponse,
    summary="Ranked company recommendations for a verified profile",
)
def profile_recommendations(
    profile_id: str,
    limit: Optional[int] = Query(
        None, ge=1, le=50,
        description="Max total recommendations (1-50). Groups are "
                    "filled in priority order: recommended, eligible, "
                    "incomplete, not_recommended.",
    ),
):
    """Rank every active company for a verified profile.

    Uses five transparent signals (eligibility, skill match,
    readiness, model-estimated placement probability, profile
    completeness). Mandatory eligibility failures override the
    numerical score. Nothing is ever fabricated - missing ML
    features simply mean the probability component is absent.
    """
    try:
        return get_recommendations(profile_id, limit)
    except (ProfileServiceError, RecommendationServiceError) as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(
            status_code=500, detail=f"Recommendations failed: {exc}"
        ) from exc
