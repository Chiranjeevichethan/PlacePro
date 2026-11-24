from typing import Optional

from pydantic import BaseModel, Field


class SalaryPredictionRequest(BaseModel):
    """16-field frontend-compatible request for salary prediction.

    The salary model itself uses only 12 of these fields. The remaining
    four fields are accepted for compatibility with the existing frontend
    payload but are intentionally not used by the salary model.

    ``college_tier`` is OPTIONAL: the salary page no longer collects it.
    Missing / null / empty values are resolved by the service to its
    configurable default (see DEFAULT_COLLEGE_TIER) before the features
    reach the model, so the model input structure is unchanged.
    """

    branch: str = Field(description="Canonical engineering branch")
    college_tier: Optional[str] = Field(
        default=None,
        description=(
            "Canonical college tier (Tier-1 / Tier-2 / Tier-3). Optional: "
            "omitted, null, or empty values resolve to the service default."
        ),
    )
    cgpa: float = Field(ge=0.0, le=10.0)
    backlogs: int = Field(ge=0)
    coding_skills: float = Field(ge=0.0, le=10.0)
    dsa_score: float = Field(ge=0.0, le=10.0)
    aptitude_score: float = Field(ge=0.0, le=100.0)
    communication_skills: float = Field(ge=0.0, le=10.0)
    ml_knowledge: float = Field(ge=0.0, le=10.0)
    system_design: float = Field(ge=0.0, le=10.0)
    internships: int = Field(ge=0)
    projects_count: int = Field(ge=0)
    certifications: int = Field(ge=0)
    hackathons: int = Field(ge=0)
    open_source_contributions: int = Field(ge=0)
    extracurriculars: int = Field(ge=0)


class SalaryPredictionResponse(BaseModel):
    """Response contract for POST /api/salary-predict."""

    predicted_salary_lpa: float = Field(
        description="Estimated salary in LPA, conditional on placement"
    )
    model_version: str = Field(
        description="Version tag of the served salary model"
    )
