# ============================================================
# PLACEPRO - PHASE 17 - ASSESSMENT SCHEMAS
# ============================================================
#
# Response models for the skill assessment API. Correct answers and
# explanations NEVER appear in any response model - they stay
# server-side in the question bank and session store.
#
# ============================================================

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class StartAssessmentRequest(BaseModel):
    profile_id: str = Field(
        ..., description="The verified profile taking the assessment"
    )
    skill: str = Field(..., description="Canonical skill name (Phase 12 taxonomy)")
    num_questions: Optional[int] = Field(
        default=None, ge=1, le=10,
        description="Optional question count (max 10)",
    )


class AssessmentQuestion(BaseModel):
    """A question as served to the client - no answers, no explanation."""

    question_id: str
    skill: str
    topic: str
    difficulty: str
    question_type: str
    question: str
    options: List[str] = Field(default_factory=list)


class StartAssessmentResponse(BaseModel):
    assessment_id: str
    skill: str
    attempt: int
    total_questions: int
    questions: List[AssessmentQuestion] = Field(default_factory=list)
    time_limit_minutes: Optional[int] = None


class SubmitAssessmentRequest(BaseModel):
    """question_id -> submitted answer. Scoring is always server-side."""

    profile_id: str = Field(
        ..., description="Profile that owns the assessment (ownership check)"
    )
    answers: Dict[str, str] = Field(
        default_factory=dict,
        description="question_id -> answer text (evaluated server-side)",
    )


class SubmitAssessmentResponse(BaseModel):
    assessment_id: str
    skill: str
    attempt: int
    skill_score: float
    level: str
    correct: int
    total: int
    difficulty_breakdown: Dict[str, float] = Field(default_factory=dict)
    topic_breakdown: Dict[str, float] = Field(default_factory=dict)
    message: str


class AssessmentHistoryEntry(BaseModel):
    skill: str
    score: float
    level: str
    source: str
    verified: bool
    assessment_id: str
    attempt: int
    timestamp: str


class AssessmentHistoryResponse(BaseModel):
    profile_id: str
    assessments: List[AssessmentHistoryEntry] = Field(default_factory=list)


class SkillViewEntry(BaseModel):
    skill: str
    resume_detected: bool = False
    user_entered: bool = False
    assessment_score: Optional[float] = None
    assessment_verified: bool = False
    level: Optional[str] = None


class SkillsViewResponse(BaseModel):
    profile_id: str
    skills: List[SkillViewEntry] = Field(default_factory=list)
