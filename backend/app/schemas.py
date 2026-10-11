# ============================================================
# PLACEPRO - PHASE 8 - API SCHEMAS
# ============================================================
#
# The request schema is the EXACT raw input schema of the final
# model (16 feature columns from data/placement_phase6.csv).
# The response schema is the Phase 8 output contract.
#
# ============================================================

from pydantic import BaseModel, Field


class StudentProfile(BaseModel):
    """Raw student profile accepted by POST /api/predict.

    Exactly the 16 feature columns the final model was trained on
    (see src/pipeline.py RAW_FEATURE_COLUMNS). Values use the same
    domains as the training dataset.
    """

    branch: str = Field(description="Engineering branch, e.g. CSE, ECE, ME, IT, CE, EE, Chemical")
    college_tier: str = Field(description="College tier, one of Tier-1, Tier-2, Tier-3")
    cgpa: float = Field(ge=0.0, le=10.0, description="Cumulative GPA (0-10)")
    backlogs: int = Field(ge=0, description="Number of active backlogs")
    coding_skills: float = Field(ge=0.0, le=10.0, description="Coding skill score (0-10)")
    dsa_score: float = Field(ge=0.0, le=10.0, description="Data structures & algorithms score (0-10)")
    aptitude_score: float = Field(ge=0.0, le=100.0, description="Aptitude score (0-100)")
    communication_skills: float = Field(ge=0.0, le=10.0, description="Communication skill score (0-10)")
    ml_knowledge: float = Field(ge=0.0, le=10.0, description="Machine learning knowledge score (0-10)")
    system_design: float = Field(ge=0.0, le=10.0, description="System design score (0-10)")
    internships: int = Field(ge=0, description="Number of internships completed")
    projects_count: int = Field(ge=0, description="Number of projects completed")
    certifications: int = Field(ge=0, description="Number of certifications")
    hackathons: int = Field(ge=0, description="Number of hackathons participated in")
    open_source_contributions: int = Field(ge=0, description="Number of open-source contributions")
    extracurriculars: int = Field(ge=0, description="Extracurricular activities count")


class PredictionResponse(BaseModel):
    """Response contract of POST /api/predict."""

    placement_probability: float = Field(
        description="Estimated probability of being placed, 0..1"
    )
    prediction: str = Field(
        description="PLACED if placement_probability >= 0.50, else NOT PLACED"
    )
    confidence: float = Field(
        description="Model certainty in the prediction = max(p, 1-p), 0..1"
    )
    model_version: str = Field(description="Version tag of the served model")
