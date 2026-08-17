# ============================================================
# PLACEPRO - PHASE 17 - ASSESSMENT ROUTES
# ============================================================
#
#   POST /api/assessment/start              -> new assessment session
#   POST /api/assessment/{id}/submit        -> server-side scoring
#   GET  /api/assessment/{id}               -> session (no answers)
#   GET  /api/profile/{id}/assessments      -> attempt history
#   GET  /api/profile/{id}/skills           -> combined skill view
#
# SECURITY
#   - Answer keys never leave the server.
#   - Scoring is server-side; client-submitted scores are ignored.
#   - Sessions are validated by ID + profile ownership.
#
# ============================================================

from fastapi import APIRouter, HTTPException

from ..schemas_assessment import (
    AssessmentHistoryResponse,
    SkillsViewResponse,
    StartAssessmentRequest,
    StartAssessmentResponse,
    SubmitAssessmentRequest,
    SubmitAssessmentResponse,
)
from ..services.assessment_service import (
    AssessmentCooldownError,
    AssessmentCompletedError,
    AssessmentError,
    AssessmentLimitError,
    AssessmentNotFoundError,
    AssessmentOwnershipError,
    InvalidSubmissionError,
    UnknownSkillError,
    combined_skill_view,
    get_assessment,
    get_assessment_history,
    start_assessment,
    submit_assessment,
)
from ..services.profile_service import ProfileServiceError

router = APIRouter(prefix="/api", tags=["assessment"])


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ProfileServiceError):
        return HTTPException(status_code=exc.status_code, detail=str(exc))
    if isinstance(exc, AssessmentError):
        return HTTPException(status_code=exc.status_code, detail=str(exc))
    return HTTPException(status_code=500, detail=f"Assessment failed: {exc}")


@router.post(
    "/assessment/start",
    response_model=StartAssessmentResponse,
    summary="Start a skill assessment (questions only - never answers)",
)
def assessment_start(body: StartAssessmentRequest):
    """Start an assessment for a canonical skill.

    The profile must be verified and within the attempt limit for the
    skill. Returns questions WITHOUT correct answers or explanations.
    """
    try:
        return start_assessment(
            body.profile_id,
            body.skill,
            body.num_questions,
        )
    except Exception as exc:  # noqa: BLE001 - mapped below
        raise _http_error(exc) from exc


@router.post(
    "/assessment/{assessment_id}/submit",
    response_model=SubmitAssessmentResponse,
    summary="Submit answers (scored server-side) and record verified evidence",
)
def assessment_submit(assessment_id: str, body: SubmitAssessmentRequest):
    """Evaluate answers server-side and record verified skill evidence.

    Rejects: unknown assessment, ownership mismatch, already-completed
    sessions, empty submissions and answers for unknown question ids.
    The answers are evaluated against the server-side question bank.
    """
    try:
        return submit_assessment(assessment_id, body.profile_id, body.answers)
    except Exception as exc:  # noqa: BLE001 - mapped below
        raise _http_error(exc) from exc


@router.get(
    "/assessment/{assessment_id}",
    summary="Get an assessment session (no answers, no answer keys)",
)
def assessment_get(assessment_id: str):
    """Optional: view a session. Returns questions only - answers and
    answer keys are never exposed. (Ownership is enforced on submit,
    which is the only mutating operation.)"""
    try:
        return get_assessment(assessment_id, profile_id=None)
    except Exception as exc:  # noqa: BLE001 - mapped below
        raise _http_error(exc) from exc


@router.get(
    "/profile/{profile_id}/assessments",
    response_model=AssessmentHistoryResponse,
    summary="Assessment history for a profile",
)
def profile_assessments(profile_id: str):
    try:
        history = get_assessment_history(profile_id)
    except Exception as exc:  # noqa: BLE001 - mapped below
        raise _http_error(exc) from exc
    return {"profile_id": profile_id, "assessments": history}


@router.get(
    "/profile/{profile_id}/skills",
    response_model=SkillsViewResponse,
    summary="Combined skill view (resume + user + assessment evidence)",
)
def profile_skills(profile_id: str):
    try:
        return combined_skill_view(profile_id)
    except Exception as exc:  # noqa: BLE001 - mapped below
        raise _http_error(exc) from exc
