# ============================================================
# PLACEPRO - PHASE 10 - PROFILE ROUTES
# ============================================================
#
#   POST /api/profile/from-resume   resume -> draft profile
#   POST /api/profile/verify        explicit student confirmation
#   GET  /api/profile/{id}          fetch a profile
#   PUT  /api/profile/{id}          edit a profile
#
# NOTE: no prediction endpoint yet - that is Phase 11.
#
# ============================================================

from fastapi import APIRouter, File, HTTPException, UploadFile

from ..schemas_profile import (
    ProfileFromResumeResponse,
    ProfilePredictionResponse,
    ProfileResponse,
    StudentProfile,
)
from ..services.profile_service import (
    InvalidProfileError,
    ProfileNotFoundError,
    ProfileServiceError,
    create_draft_with_analysis,
    get_profile,
    predict_for_profile,
    update_profile,
    verify_profile,
)
from ..services.resume_service import MAX_FILE_SIZE, ResumeServiceError

router = APIRouter(prefix="/api/profile", tags=["profile"])

DRAFT_MESSAGE = (
    "Resume processed. Review the extracted information, correct "
    "anything wrong, then confirm the profile."
)


@router.post(
    "/from-resume",
    response_model=ProfileFromResumeResponse,
    summary=(
        "Create a draft student profile from an uploaded resume "
        "(with provenance, confidence, diagnostics and completeness)"
    ),
)
async def profile_from_resume(
    file: UploadFile = File(..., description="Resume file (.pdf or .docx)"),
):
    """Upload a resume and build a DRAFT canonical profile for review.

    Nothing is assumed correct: `verified` is False until the student
    explicitly confirms via POST /api/profile/verify.
    """
    filename = file.filename or ""
    try:
        content = await file.read(MAX_FILE_SIZE + 1)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(
            status_code=400, detail=f"Could not read the uploaded file: {exc}"
        ) from exc

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024 * 1024)} MB.",
        )

    try:
        profile, completion, analysis = create_draft_with_analysis(
            filename, content, file.content_type
        )
    except ResumeServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except ProfileServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(
            status_code=500, detail=f"Profile creation failed: {exc}"
        ) from exc

    if analysis.get("diagnostics", {}).get("ocr_required"):
        # A scanned PDF cannot build a profile - fail loudly instead of
        # silently returning an empty draft.
        raise HTTPException(
            status_code=422,
            detail=(
                "OCR_REQUIRED: the PDF contains no extractable text "
                "(scanned document). OCR is not implemented yet - no "
                "profile can be created from this file."
            ),
        )

    # Phase 16 additive fields - the original Phase 10 contract
    # (profile / completion / message) is fully preserved.
    return {
        "profile": profile,
        "completion": completion,
        "message": DRAFT_MESSAGE,
        "provenance": analysis["provenance"],
        "confidence": analysis["confidence"],
        "diagnostics": analysis["diagnostics"],
        "extraction_summary": analysis["extraction_summary"],
        "feature_availability": analysis["completeness"][
            "feature_availability"
        ],
    }


@router.post(
    "/verify",
    response_model=ProfileResponse,
    summary="Verify (explicitly confirm) a student profile",
)
def profile_verify(profile: StudentProfile):
    """Explicitly confirm the reviewed profile.

    The request body is the full profile as edited by the student.
    `verified` becomes True only after this call.
    """
    try:
        verified, completion = verify_profile(profile.model_dump())
    except ProfileServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(
            status_code=500, detail=f"Verification failed: {exc}"
        ) from exc

    if completion["profile_complete"]:
        message = "Profile verified. All ML-required fields are available."
    else:
        missing = len(completion["missing_fields"])
        message = (
            "Profile verified, but "
            f"{missing} ML-required field(s) still need manual input "
            "before a prediction can be made."
        )
    return {"profile": verified, "completion": completion, "message": message}


@router.get(
    "/{profile_id}",
    response_model=ProfileResponse,
    summary="Fetch a stored profile",
)
def profile_get(profile_id: str):
    try:
        profile, completion = get_profile(profile_id)
    except ProfileServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return {
        "profile": profile,
        "completion": completion,
        "message": "Profile retrieved.",
    }


@router.put(
    "/{profile_id}",
    response_model=ProfileResponse,
    summary="Edit a stored profile (resets verified to False)",
)
def profile_update(profile_id: str, profile: StudentProfile):
    """Apply student edits. Any edit resets `verified` to False."""
    try:
        updated, completion = update_profile(profile_id, profile.model_dump())
    except ProfileServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return {
        "profile": updated,
        "completion": completion,
        "message": "Profile updated. Re-confirm the profile to verify it.",
    }


@router.post(
    "/{profile_id}/predict",
    response_model=ProfilePredictionResponse,
    summary="Predict placement for a verified, complete profile (Phase 8 model)",
)
def profile_predict(profile_id: str):
    """Predict placement using the existing Phase 8 final model.

    Guards (model is NEVER called otherwise):
      - profile must exist (else 404)
      - profile must be verified
      - all 16 ML features must be present (missing ones are returned,
        never invented)

    The model path is fixed (models/placepro_final_model.pkl) - the
    client cannot choose a model.
    """
    try:
        return predict_for_profile(profile_id)
    except ProfileServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(
            status_code=500, detail=f"Prediction failed: {exc}"
        ) from exc
