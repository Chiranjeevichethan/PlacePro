from pydantic import BaseModel, Field


class SalaryPredictionRequest(BaseModel):
    """16-field frontend-compatible request for salary prediction.

    The salary model itself uses only 12 of these fields. The remaining
    four fields are accepted for compatibility with the existing frontend
    payload but are intentionally not used by the salary model.
    """

    branch: str = Field(description="Canonical engineering branch")
    college_tier: str = Field(description="Canonical college tier")
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
