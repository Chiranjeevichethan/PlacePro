# ============================================================
# PLACEPRO - PHASE 9 - RESUME UPLOAD ROUTE
# ============================================================

from fastapi import APIRouter, File, HTTPException, UploadFile

from ..schemas_resume import ResumeAnalysisResponse, ResumeUploadResponse
from ..services.resume_intelligence import analyze_resume
from ..services.resume_service import (
    MAX_FILE_SIZE,
    CorruptedFileError,
    EmptyFileError,
    FileTooLargeError,
    ResumeServiceError,
    UnsupportedFileTypeError,
    process_resume_upload,
)

router = APIRouter(prefix="/api/resume", tags=["resume"])


@router.post(
    "/upload",
    response_model=ResumeUploadResponse,
    summary="Upload a resume (PDF/DOCX) and extract a structured student profile",
)
async def upload_resume(
    file: UploadFile = File(..., description="Resume file (.pdf or .docx)"),
):
    """Accept a PDF or DOCX resume and return structured extracted data.

    The file is validated (extension, size, magic bytes, MIME), stored
    in a temporary location for processing, then deleted. Only parsed -
    never executed, never persisted.
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
            detail=(
                f"File too large. Maximum size is "
                f"{MAX_FILE_SIZE // (1024 * 1024)} MB."
            ),
        )

    try:
        return process_resume_upload(filename, content, file.content_type)
    except UnsupportedFileTypeError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except EmptyFileError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except FileTooLargeError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except CorruptedFileError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except ResumeServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(
            status_code=500, detail=f"Resume processing failed: {exc}"
        ) from exc


@router.post(
    "/analyze",
    response_model=ResumeAnalysisResponse,
    summary=(
        "Analyze a resume WITHOUT creating a profile "
        "(extraction + provenance + confidence + diagnostics)"
    ),
)
async def analyze_resume_route(
    file: UploadFile = File(..., description="Resume file (.pdf or .docx)"),
):
    """Preview resume extraction before profile creation.

    Same validation as /api/resume/upload, but no profile is stored.
    Returns extracted information, detected skills, diagnostics,
    provenance and completeness. A scanned PDF (no extractable text)
    returns an explicit OCR_REQUIRED error instead of an empty profile.
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
            detail=(
                f"File too large. Maximum size is "
                f"{MAX_FILE_SIZE // (1024 * 1024)} MB."
            ),
        )

    try:
        analysis = analyze_resume(filename, content, file.content_type)
    except UnsupportedFileTypeError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except EmptyFileError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except FileTooLargeError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except CorruptedFileError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except ResumeServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(
            status_code=500, detail=f"Resume analysis failed: {exc}"
        ) from exc

    if analysis.get("diagnostics", {}).get("ocr_required"):
        raise HTTPException(
            status_code=422,
            detail=(
                "OCR_REQUIRED: the PDF contains no extractable text "
                "(scanned document). OCR is not implemented yet - no "
                "profile can be built from this file."
            ),
        )

    return analysis
