# ============================================================
# PLACEPRO - PHASE 14 - RECOMMENDATION SCHEMAS
# ============================================================
#
# Response model for:
#   GET /api/profile/{profile_id}/recommendations[?limit=N]
#
# Everything is calculated SERVER-SIDE - clients never submit
# scores, statuses, probabilities or readiness values.
#
# ============================================================

from typing import List, Optional

from pydantic import BaseModel, Field


class SkillMatch(BaseModel):
    """Required/preferred skill match against one company."""

    score: float = 0.0
    required_matched: List[str] = Field(default_factory=list)
    required_missing: List[str] = Field(default_factory=list)
    preferred_matched: List[str] = Field(default_factory=list)
    preferred_missing: List[str] = Field(default_factory=list)


class RecommendationItem(BaseModel):
    company_id: str
    company_name: str
    status: str  # RECOMMENDED / ELIGIBLE / INCOMPLETE / NOT_RECOMMENDED
    recommendation_score: float
    eligibility_status: str  # ELIGIBLE / NOT_ELIGIBLE / INCOMPLETE
    skill_match: SkillMatch = Field(default_factory=SkillMatch)
    readiness_score: int = 0
    readiness_level: str = ""
    placement_probability: Optional[float] = None
    reasons: List[str] = Field(default_factory=list)
    improvement_actions: List[str] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)


class RecommendationGroups(BaseModel):
    recommended: List[RecommendationItem] = Field(default_factory=list)
    eligible: List[RecommendationItem] = Field(default_factory=list)
    incomplete: List[RecommendationItem] = Field(default_factory=list)
    not_recommended: List[RecommendationItem] = Field(default_factory=list)


class RecommendationsResponse(BaseModel):
    profile_id: str
    recommendations: RecommendationGroups
