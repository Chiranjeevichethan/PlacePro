# ============================================================
# PLACEPRO - PHASE 27 - PERFORMANCE ANALYTICS SCHEMAS
# ============================================================
#
# Response models for:
#   GET /api/profile/{profile_id}/performance
#
# CONSOLIDATION RULES (mirrors the Phase 12 honesty rules):
#   - Everything here is derived from data that ALREADY exists on
#     the stored profile: prediction_history, assessment_evidence,
#     the Phase 12 readiness analysis and the combined skill view.
#   - No history is fabricated, no scores are invented, and skill
#     "progress" over time is NOT reported (per-attempt assessment
#     evidence exists, but no historical skill snapshots do).
#   - Empty history is reported explicitly: count 0 and None for
#     latest/highest/lowest/average - never a made-up default.
#
# Existing schemas are REUSED where possible (no duplicates):
#   - PredictionHistoryEntry  (schemas_profile, Phase 11)
#   - AssessmentHistoryEntry  (schemas_assessment, Phase 17)
#   - ReadinessResponse       (schemas_readiness, Phase 12)
#   - SkillViewEntry          (schemas_assessment, Phase 17)
#
# ============================================================

from typing import List, Optional

from pydantic import BaseModel, Field

from .schemas_assessment import AssessmentHistoryEntry, SkillViewEntry
from .schemas_profile import PredictionHistoryEntry
from .schemas_readiness import ReadinessResponse


class PredictionSummary(BaseModel):
    """Summary of the stored Phase 11 prediction history.

    latest_* reflect the most recent attempt (history is appended
    chronologically by the server). All Optional fields are None
    when no prediction has been made yet.
    """

    predictions_count: int = 0
    latest_prediction: Optional[str] = None
    latest_probability: Optional[float] = None
    latest_timestamp: Optional[str] = None
    highest_probability: Optional[float] = None
    lowest_probability: Optional[float] = None


class AssessmentSummary(BaseModel):
    """Summary of the stored Phase 17 assessment evidence.

    Scores are 0-100 assessment-bank percentages (never resume
    mentions). latest_* reflect the most recent attempt. All
    Optional fields are None when no assessment was taken yet.
    """

    assessments_count: int = 0
    skills_assessed: int = 0
    average_score: Optional[float] = None
    latest_skill: Optional[str] = None
    latest_score: Optional[float] = None
    latest_level: Optional[str] = None
    latest_timestamp: Optional[str] = None


class PerformanceSummary(BaseModel):
    """Top-level rollup. Every number is computed from real data."""

    predictions: PredictionSummary = Field(default_factory=PredictionSummary)
    assessments: AssessmentSummary = Field(default_factory=AssessmentSummary)
    readiness_score: int
    readiness_level: str
    skills_tracked: int


class PerformanceResponse(BaseModel):
    """Consolidated performance view for a VERIFIED profile.

    Sections:
      summary            - rollup of the four sections below
      prediction_history - Phase 11 prediction attempts (verbatim)
      assessment_history - Phase 17 assessment attempts (verbatim)
      readiness          - Phase 12 readiness analysis (recomputed)
      skills             - Phase 17 combined skill view (recomputed)
    """

    profile_id: str
    verified: bool
    summary: PerformanceSummary
    prediction_history: List[PredictionHistoryEntry] = Field(default_factory=list)
    assessment_history: List[AssessmentHistoryEntry] = Field(default_factory=list)
    readiness: ReadinessResponse
    skills: List[SkillViewEntry] = Field(default_factory=list)
