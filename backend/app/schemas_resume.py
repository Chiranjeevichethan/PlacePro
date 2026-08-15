# ============================================================
# PLACEPRO - PHASE 9 - RESUME EXTRACTION SCHEMAS
# ============================================================
#
# NOTE: Phase 8's schemas.py is a protected file (do-not-modify),
# so the resume schemas live in their own module. All fields are
# optional / empty-by-default: the parser NEVER invents data.
#
# ============================================================

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class Education(BaseModel):
    degree: Optional[str] = None
    branch: Optional[str] = None
    college: Optional[str] = None
    cgpa: Optional[float] = None
    graduation_year: Optional[int] = None


class SkillSet(BaseModel):
    programming_languages: List[str] = Field(default_factory=list)
    frameworks: List[str] = Field(default_factory=list)
    databases: List[str] = Field(default_factory=list)
    cloud: List[str] = Field(default_factory=list)
    ai_ml: List[str] = Field(default_factory=list)
    web_technologies: List[str] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)
    other_skills: List[str] = Field(default_factory=list)


class ExperienceEntry(BaseModel):
    company: Optional[str] = None
    role: Optional[str] = None
    duration: Optional[str] = None
    technologies: List[str] = Field(default_factory=list)


class InternshipEntry(BaseModel):
    company: Optional[str] = None
    role: Optional[str] = None
    duration: Optional[str] = None
    technologies: List[str] = Field(default_factory=list)


class ProjectEntry(BaseModel):
    project_name: Optional[str] = None
    description: Optional[str] = None
    technologies: List[str] = Field(default_factory=list)


class CertificationEntry(BaseModel):
    name: Optional[str] = None
    issuer: Optional[str] = None
    year: Optional[int] = None


class Achievements(BaseModel):
    hackathons: List[str] = Field(default_factory=list)
    awards: List[str] = Field(default_factory=list)
    coding_achievements: List[str] = Field(default_factory=list)


class ExtractedProfile(BaseModel):
    """Structured student profile extracted from a resume.

    Only fields actually present in the resume are populated;
    everything else stays None / [] (never invented).
    """

    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    portfolio: Optional[str] = None

    education: Education = Field(default_factory=Education)
    skills: SkillSet = Field(default_factory=SkillSet)
    experience: List[ExperienceEntry] = Field(default_factory=list)
    internships: List[InternshipEntry] = Field(default_factory=list)
    projects: List[ProjectEntry] = Field(default_factory=list)
    certifications: List[CertificationEntry] = Field(default_factory=list)
    achievements: Achievements = Field(default_factory=Achievements)


class ExtractionInfo(BaseModel):
    raw_text_preview: Optional[str] = Field(
        default=None, description="First ~500 chars of extracted text"
    )
    page_count: Optional[int] = Field(
        default=None, description="Page count (PDF only; None for DOCX)"
    )
    extraction_success: bool
    ocr_required: Optional[bool] = Field(
        default=False,
        description=(
            "True when a PDF contains no extractable text (scanned "
            "document) - OCR is required; DOCX is never flagged."
        ),
    )


class Verification(BaseModel):
    """Heuristic extraction confidence - NOT mathematically calibrated.

    confidence maps a field path to a 0..1 heuristic score.
    needs_verification lists fields that are missing or uncertain.
    """

    confidence: Dict[str, float] = Field(default_factory=dict)
    needs_verification: List[str] = Field(default_factory=list)


class ResumeUploadResponse(BaseModel):
    success: bool
    filename: str
    file_type: str
    extraction: ExtractionInfo
    extracted_profile: ExtractedProfile
    verification: Verification


# ------------------------------------------------------------
# PHASE 16 - RESUME INTELLIGENCE 2.0 (additive)
# ------------------------------------------------------------


class FieldEvidence(BaseModel):
    """Provenance for one extracted field.

    source is "resume" for extraction, "user" after the student
    edits a field, "calculated" for derived counts, "system" for
    diagnostics. evidence is a short resume snippet (raw text is
    never exposed in full).
    """

    field: str
    value: Optional[Union[float, int, str]] = None
    source: str
    evidence: Optional[str] = None


class ResumeDiagnostics(BaseModel):
    """Resume quality diagnostics (not a claim of accuracy)."""

    page_count: Optional[int] = None
    word_count: int = 0
    detected_sections: List[str] = Field(default_factory=list)
    extraction_completeness: int = 0
    ocr_required: bool = False
    scanned_document_warning: bool = False


class ExtractionSummary(BaseModel):
    """What was found: counts + presence flags."""

    fields_extracted: int = 0
    counts: Dict[str, int] = Field(default_factory=dict)
    has_education: bool = False
    has_cgpa: bool = False
    has_github: bool = False
    has_linkedin: bool = False


class FeatureAvailabilityEntry(BaseModel):
    """Availability status of one Phase 8 ML feature for this profile.

    AVAILABLE_FROM_RESUME / AVAILABLE_FROM_USER / CALCULATED /
    REQUIRES_MANUAL_INPUT / UNKNOWN - never invented.
    """

    field: str
    status: str
    reason: str


class ResumeAnalysisResponse(BaseModel):
    """POST /api/resume/analyze - analysis WITHOUT creating a profile."""

    success: bool
    filename: str
    file_type: str
    extraction: ExtractionInfo
    extracted_profile: ExtractedProfile
    verification: Verification
    provenance: List[FieldEvidence] = Field(default_factory=list)
    confidence: Dict[str, str] = Field(default_factory=dict)
    diagnostics: ResumeDiagnostics = Field(default_factory=ResumeDiagnostics)
    extraction_summary: ExtractionSummary = Field(default_factory=ExtractionSummary)
    completeness: Dict[str, Any] = Field(default_factory=dict)
