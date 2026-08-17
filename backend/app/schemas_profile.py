# ============================================================
# PLACEPRO - PHASE 10 - CANONICAL STUDENT PROFILE SCHEMAS
# ============================================================
#
# ONE canonical internal student profile. It clearly separates:
#
#   A. resume_extracted  -> provenance.resume  (from the resume)
#   B. user_provided     -> provenance.user   (student edited / typed)
#   C. ml_derived        -> provenance.ml     (RESERVED for Phase 11+
#                                             model outputs; empty now)
#
# Rules:
#   - Missing information stays null / [] - never invented.
#   - `verified` is only True after the student explicitly confirms
#     the profile (POST /api/profile/verify).
#   - Editing a verified profile resets `verified` to False.
#
# ============================================================

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

# Reuse the Phase 9 structures (no duplicate schema definitions)
from .schemas_resume import (
    Achievements,
    CertificationEntry,
    ExperienceEntry,
    InternshipEntry,
    ProjectEntry,
    SkillSet,
)


class PersonalInfo(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    portfolio: Optional[str] = None


class EducationInfo(BaseModel):
    degree: Optional[str] = None
    branch: Optional[str] = None
    college: Optional[str] = None
    cgpa: Optional[float] = None
    graduation_year: Optional[int] = None


class MlInputs(BaseModel):
    """User-provided ML feature values that a resume cannot supply.

    These are the Phase 8 model features with no defensible resume
    source (scores, tier, backlogs, etc.). The student provides them
    manually; the mapping layer never invents them.
    """

    college_tier: Optional[str] = None  # Tier-1 / Tier-2 / Tier-3
    backlogs: Optional[int] = None
    coding_skills: Optional[float] = None
    dsa_score: Optional[float] = None
    aptitude_score: Optional[float] = None
    communication_skills: Optional[float] = None
    ml_knowledge: Optional[float] = None
    system_design: Optional[float] = None
    open_source_contributions: Optional[int] = None
    extracurriculars: Optional[int] = None


class Provenance(BaseModel):
    """Where each non-empty profile value came from (dotted field paths)."""

    resume: List[str] = Field(default_factory=list)
    user: List[str] = Field(default_factory=list)
    ml: List[str] = Field(default_factory=list)


class PredictionHistoryEntry(BaseModel):
    """One recorded prediction for a profile (resume itself is never stored)."""

    timestamp: str
    model_version: str
    placement_probability: float
    prediction: str


class StudentProfile(BaseModel):
    """The canonical unified student profile."""

    profile_id: Optional[str] = None
    personal: PersonalInfo = Field(default_factory=PersonalInfo)
    education: EducationInfo = Field(default_factory=EducationInfo)
    skills: SkillSet = Field(default_factory=SkillSet)
    experience: List[ExperienceEntry] = Field(default_factory=list)
    internships: List[InternshipEntry] = Field(default_factory=list)
    projects: List[ProjectEntry] = Field(default_factory=list)
    certifications: List[CertificationEntry] = Field(default_factory=list)
    achievements: Achievements = Field(default_factory=Achievements)
    ml_inputs: MlInputs = Field(default_factory=MlInputs)
    provenance: Provenance = Field(default_factory=Provenance)
    original_resume_values: Dict[str, Optional[Union[float, int, str, List]]] = Field(
        default_factory=dict,
        description=(
            "Phase 16: original resume-extracted values (dotted field path "
            "-> value). When the student edits an extracted field, the new "
            "value is stored normally with source 'user' and the original "
            "resume value is kept here for reference."
        ),
    )
    assessment_evidence: List[Dict[str, Optional[Union[float, int, str, bool]]]] = Field(
        default_factory=list,
        description=(
            "Phase 17: verified assessment evidence (server-produced only). "
            "Each entry: {skill, score, level, source: 'assessment', "
            "verified: true, assessment_id, attempt, timestamp}. Clients "
            "can never write this - scores come from the assessment engine."
        ),
    )
    verified: bool = False
    prediction_history: List[PredictionHistoryEntry] = Field(default_factory=list)


class ProfileCompletion(BaseModel):
    """Readiness of the profile for the Phase 8 model (informational only
    in Phase 10 - no prediction is made yet)."""

    profile_complete: bool
    missing_fields: List[str] = Field(default_factory=list)
    ml_feature_mapping: Dict[str, Optional[Union[float, int, str]]] = Field(
        default_factory=dict
    )


class ProfileResponse(BaseModel):
    profile: StudentProfile
    completion: ProfileCompletion
    message: str


class ProfileFromResumeResponse(ProfileResponse):
    """Phase 16: from-resume response with the additive Resume
    Intelligence fields. The Phase 10 contract (profile / completion /
    message) is fully preserved - the new fields are extra."""

    provenance: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: Dict[str, str] = Field(default_factory=dict)
    diagnostics: Dict[str, Any] = Field(default_factory=dict)
    extraction_summary: Dict[str, Any] = Field(default_factory=dict)
    feature_availability: List[Dict[str, str]] = Field(default_factory=list)


class ProfilePredictionResponse(BaseModel):
    """Response of POST /api/profile/{profile_id}/predict.

    ready_for_prediction=False (with `reason` and/or `missing_fields`)
    means the model was NOT called - nothing is invented.
    """

    ready_for_prediction: bool
    prediction: Optional[str] = None
    placement_probability: Optional[float] = None
    confidence: Optional[float] = None
    model_version: Optional[str] = None
    missing_fields: List[str] = Field(default_factory=list)
    reason: Optional[str] = None
    prediction_history: List[PredictionHistoryEntry] = Field(default_factory=list)
