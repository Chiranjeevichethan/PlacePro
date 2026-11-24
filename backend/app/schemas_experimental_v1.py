from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ExperimentalV1Request(BaseModel):
    """Production-form domains, isolated from the production API schema.

    All 16 values are required and validated. Five unsupported synthetic
    features are explicitly excluded by the V1 service, never imputed.
    """

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    branch: Literal["CSE", "ISE", "IT", "ECE", "EE", "ME", "CE", "Chemical"]
    college_tier: Literal["Tier-1", "Tier-2", "Tier-3"]
    cgpa: float = Field(ge=4, le=10)
    backlogs: int = Field(ge=0)
    coding_skills: float = Field(ge=1, le=10)
    dsa_score: float = Field(ge=1, le=10)
    ml_knowledge: float = Field(ge=0, le=10)
    system_design: float = Field(ge=0, le=10)
    projects_count: int = Field(ge=0)
    certifications: int = Field(ge=0)
    aptitude_score: float = Field(ge=20, le=100)
    communication_skills: float = Field(ge=1, le=10)
    internships: int = Field(ge=0)
    hackathons: int = Field(ge=0)
    open_source_contributions: int = Field(ge=0)
    extracurriculars: int = Field(ge=0)


class ExperimentalV1Response(BaseModel):
    """Response schema for experimental V1 predictions."""

    placement_probability: float = Field(ge=0, le=1)
    prediction: Literal["Placed", "Not Placed"]
    confidence: float = Field(ge=0, le=1)
    model_version: str
    experimental: bool = True
    synthetic_data_notice: str
