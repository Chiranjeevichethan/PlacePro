# ============================================================
# PLACEPRO - PHASE 12 - READINESS / SKILL-GAP RESPONSE SCHEMAS
# ============================================================
#
# Response models for:
#   GET /api/profile/{profile_id}/readiness
#   GET /api/profile/{profile_id}/placement-summary
#
# Conceptual separation (never merged):
#   - placement_probability / prediction  -> Phase 8 ML model ONLY
#   - readiness_score                     -> transparent rule-based
#                                            score (Phase 12)
#
# ============================================================

from typing import List, Optional

from pydantic import BaseModel, Field


class StrengthEntry(BaseModel):
    skill: str
    category: Optional[str] = None
    evidence: List[str] = Field(default_factory=list)


class SkillGapEntry(BaseModel):
    skill: str
    category: str
    priority: str  # HIGH / MEDIUM / LOW
    reason: str


class ImprovementItem(BaseModel):
    priority: int  # 1 = do this first
    skill: str
    reason: str
    action: str


class ReadinessBreakdown(BaseModel):
    """Documented, transparent components of the 0-100 score."""

    technical_skills: int = 0
    projects: int = 0
    internships: int = 0
    certifications: int = 0
    communication: int = 0
    profile_completeness: int = 0


class ProfileCompletenessView(BaseModel):
    percentage: int
    missing_fields: List[str] = Field(default_factory=list)


class ReadinessResponse(BaseModel):
    profile_id: str
    readiness_score: int
    readiness_level: str
    readiness_breakdown: ReadinessBreakdown
    strengths: List[StrengthEntry] = Field(default_factory=list)
    skill_gaps: List[SkillGapEntry] = Field(default_factory=list)
    improvement_plan: List[ImprovementItem] = Field(default_factory=list)
    profile_completeness: ProfileCompletenessView


class PlacementSummaryResponse(BaseModel):
    """Phase 11 prediction + Phase 12 readiness, side by side.

    The two scores are reported separately - they are never merged
    or mathematically combined.
    """

    ready_for_prediction: bool
    prediction: Optional[str] = None
    placement_probability: Optional[float] = None
    confidence: Optional[float] = None
    model_version: Optional[str] = None
    missing_fields: List[str] = Field(default_factory=list)
    reason: Optional[str] = None

    readiness_score: int
    readiness_level: str
    readiness_breakdown: ReadinessBreakdown
    strengths: List[StrengthEntry] = Field(default_factory=list)
    skill_gaps: List[SkillGapEntry] = Field(default_factory=list)
    improvement_plan: List[ImprovementItem] = Field(default_factory=list)
