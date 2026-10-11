# ============================================================
# PLACEPRO - PHASE 9 - RESUME SERVICE
# ============================================================
#
# Secure upload handling + orchestration:
#
#   validate -> temp storage -> text extraction -> structured parse
#
# SECURITY
#   - Allowed extensions only (.pdf / .docx)
#   - Magic-byte validation (authoritative) + MIME check where sent
#   - Hard file-size limit
#   - Empty / corrupted files rejected with useful errors
#   - Uploads go to a random temp file (client filename is NEVER used
#     for path construction -> no path traversal) and are deleted
#     after processing (TemporaryDirectory cleanup)
#   - Uploaded files are only parsed - never executed
#
# ============================================================

import os
import tempfile
import uuid

from .resume_parser import (
    ExtractionError,
    NoTextExtractionError,
    extract_text,
    parse_resume,
)

# ------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

ALLOWED_EXTENSIONS = {
    ".pdf": "pdf",
    ".docx": "docx",
}

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

# Magic bytes (authoritative file-type check)
PDF_MAGIC = b"%PDF"
ZIP_MAGIC = b"PK\x03\x04"  # DOCX is a ZIP archive


# ------------------------------------------------------------
# CUSTOM ERRORS
# ------------------------------------------------------------


class ResumeServiceError(Exception):
    status_code = 400


class UnsupportedFileTypeError(ResumeServiceError):
    status_code = 415


class EmptyFileError(ResumeServiceError):
    status_code = 400


class FileTooLargeError(ResumeServiceError):
    status_code = 413


class CorruptedFileError(ResumeServiceError):
    status_code = 422


# ------------------------------------------------------------
# VALIDATION
# ------------------------------------------------------------


def _detect_magic_type(content: bytes):
    """Return 'pdf' / 'docx' from magic bytes, or None."""
    if content.startswith(PDF_MAGIC):
        return "pdf"
    if content.startswith(ZIP_MAGIC):
        return "docx"
    return None


def validate_upload(filename: str, content: bytes, content_type=None) -> str:
    """Validate an upload and return the resolved file_type ('pdf'/'docx')."""
    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise UnsupportedFileTypeError(
            f"Unsupported file type '{ext or 'none'}'. Allowed: {allowed}"
        )

    if len(content) == 0:
        raise EmptyFileError("The uploaded file is empty.")

    if len(content) > MAX_FILE_SIZE:
        raise FileTooLargeError(
            f"File too large ({len(content)} bytes). "
            f"Maximum size is {MAX_FILE_SIZE // (1024 * 1024)} MB."
        )

    declared_type = ALLOWED_EXTENSIONS[ext]
    magic_type = _detect_magic_type(content)

    if magic_type is None:
        raise CorruptedFileError(
            f"The file does not look like a valid {declared_type.upper()} "
            "(magic bytes do not match any supported format)."
        )

    if magic_type != declared_type:
        raise UnsupportedFileTypeError(
            f"File content does not match its extension: expected "
            f"{declared_type.upper()} but content looks like "
            f"{magic_type.upper()}."
        )

    # MIME type check where the client provides one (magic bytes stay
    # authoritative; application/octet-stream is treated as unknown).
    if content_type and content_type != "application/octet-stream":
        if content_type not in ALLOWED_MIME_TYPES:
            raise UnsupportedFileTypeError(
                f"Unsupported MIME type '{content_type}'. "
                "Allowed: application/pdf, "
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )

    return declared_type


# ------------------------------------------------------------
# ORCHESTRATION
# ------------------------------------------------------------


def process_resume_upload(filename: str, content: bytes, content_type=None) -> dict:
    """Validate, extract and parse an uploaded resume.

    Returns the ResumeUploadResponse payload (dict). Raises a
    ResumeServiceError subclass on any validation/extraction failure.
    """
    response, _ = _process_resume_upload_full(filename, content, content_type)
    return response


def _process_resume_upload_full(filename: str, content: bytes, content_type=None):
    """Like process_resume_upload, but also returns the FULL raw text.

    Returns (response_dict, full_raw_text). The public function above
    drops the full text (Phase 9 contract); Phase 16's resume
    intelligence layer needs it for provenance evidence snippets.
    """
    file_type = validate_upload(filename, content, content_type)

    # Temp storage: random name (never the client filename), removed on exit.
    with tempfile.TemporaryDirectory(prefix="placepro_resume_") as tmp_dir:
        tmp_path = os.path.join(tmp_dir, f"upload_{uuid.uuid4().hex}.{file_type}")
        with open(tmp_path, "wb") as f:
            f.write(content)

        try:
            extraction = extract_text(content, file_type)
        except NoTextExtractionError as exc:
            # Structurally valid but contains NO extractable text
            # (scanned/image-only PDF). Not corruption: report it as
            # OCR_REQUIRED instead of silently returning an empty
            # profile or a misleading 422.
            response = {
                "success": False,
                "filename": filename,
                "file_type": file_type,
                "extraction": {
                    "raw_text_preview": "",
                    "page_count": None,
                    "extraction_success": False,
                    "ocr_required": True,
                },
                "extracted_profile": {
                    "name": None, "email": None, "phone": None,
                    "location": None, "linkedin": None, "github": None,
                    "portfolio": None,
                    "education": {"degree": None, "branch": None,
                                  "college": None, "cgpa": None,
                                  "graduation_year": None},
                    "skills": {"programming_languages": [], "frameworks": [],
                                "databases": [], "cloud": [], "ai_ml": [],
                                "web_technologies": [], "tools": [],
                                "other_skills": []},
                    "experience": [], "internships": [], "projects": [],
                    "certifications": [],
                    "achievements": {"hackathons": [], "awards": [],
                                      "coding_achievements": []},
                },
                "verification": {
                    "confidence": {},
                    "needs_verification": [],
                },
            }
            return response, ""
        except ExtractionError as exc:
            # A file that passes magic bytes but cannot be parsed
            # (e.g. truncated PDF / damaged DOCX) is a 422, not a 500.
            raise CorruptedFileError(str(exc)) from exc

    raw_text = extraction["raw_text"]
    profile, confidence, needs_verification = parse_resume(raw_text)

    preview = raw_text[:500]

    # ocr_required: a PDF with no extractable text (scanned document).
    # We surface it explicitly instead of silently returning an empty
    # profile. DOCX is never flagged (python-docx reads the XML stream).
    ocr_required = bool(file_type == "pdf" and not raw_text.strip())

    response = {
        "success": True,
        "filename": filename,
        "file_type": file_type,
        "extraction": {
            "raw_text_preview": preview,
            "page_count": extraction.get("page_count"),
            "extraction_success": extraction["extraction_success"],
            "ocr_required": ocr_required,
        },
        "extracted_profile": profile,
        "verification": {
            "confidence": confidence,
            "needs_verification": needs_verification,
        },
    }
    return response, raw_text
