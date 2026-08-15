# ============================================================
# PLACEPRO - PHASE 16 - RESUME INTELLIGENCE 2.0
# ============================================================
#
# An additive ANALYSIS layer on top of the Phase 9 extraction.
# It adds, without changing the Phase 9 extraction contract:
#
#   1. FIELD PROVENANCE  - every extracted field carries
#      {value, source, evidence}. Source is "resume" for
#      extraction, "user" after the student edits, "calculated"
#      for derived counts, "system" for diagnostics.
#   2. FIELD CONFIDENCE  - high / medium / low labels derived
#      from the Phase 9 heuristic (0..1) scores. This is
#      EXTRACTION confidence - never "ML confidence" and never
#      a claim about whether the student possesses a skill.
#   3. EVIDENCE          - short, truncated snippets of the
#      resume text that support each field (raw resume text is
#      never exposed in full through the APIs).
#   4. RESUME DIAGNOSTICS- page count, word count, detected
#      sections, extraction completeness %, OCR-required flag.
#   5. EXTRACTION SUMMARY- what was found (counts per section).
#   6. analyze_resume()  - full analysis WITHOUT creating a
#      profile (used by POST /api/resume/analyze and by the
#      enhanced POST /api/profile/from-resume).
#
# HONESTY RULES
#   - Nothing is invented: absent fields stay null / [].
#   - Extracted != verified: profiles built from this stay
#     verified=false until the student explicitly confirms.
#   - Skills are NEVER converted into numerical scores here.
#
# ============================================================

from .ml_feature_mapping import (
    RAW_FEATURE_COLUMNS,  # noqa: F401 (exact contract, re-exported)
)
from .profile_service import collect_nonempty_paths
from .resume_service import _process_resume_upload_full

# ------------------------------------------------------------
# CONFIDENCE LABELS (heuristic extraction confidence)
# ------------------------------------------------------------
# Derived from the Phase 9 per-field 0..1 heuristic:
#   >= 0.85 -> high | 0.60..0.84 -> medium | < 0.60 -> low
# These are extraction-confidence labels for review guidance -
# NOT ML confidence and NOT a probability that the student
# possesses the value.
HIGH = "high"
MEDIUM = "medium"
LOW = "low"


def _confidence_label(score: float) -> str:
    if score >= 0.85:
        return HIGH
    if score >= 0.60:
        return MEDIUM
    return LOW


# Field paths that are validated by strict patterns -> can be "high".
_STRICT_HIGH = {
    "email": 0.97, "phone": 0.90, "linkedin": 0.95, "github": 0.95,
    "education.cgpa": 0.98, "education.graduation_year": 0.90,
}


def classify_confidence(confidence: dict) -> dict:
    """Map the Phase 9 0..1 heuristic scores to high/medium/low labels.

    Returns {field: "high"|"medium"|"low"} - heuristic extraction
    confidence, never ML confidence.
    """
    labels = {}
    for field, score in (confidence or {}).items():
        labels[field] = _confidence_label(float(score or 0.0))
    return labels


# ------------------------------------------------------------
# PROVENANCE (value + source + evidence per extracted field)
# ------------------------------------------------------------


def _resolve_path(obj, dotted_path):
    """Resolve 'education.cgpa' against a nested dict."""
    current = obj
    for part in dotted_path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _evidence_line(raw_text, needle):
    """First resume line containing needle (truncated to ~120 chars)."""
    if not needle:
        return None
    needle = str(needle)
    for line in (raw_text or "").splitlines():
        stripped = line.strip()
        if stripped and needle.lower() in stripped.lower():
            return stripped[:120]
    return None


def build_field_provenance(extracted: dict, raw_text: str) -> list:
    """Per-field provenance for the extracted profile.

    Each entry: {field, value, source, evidence}. `source` is
    "resume" for everything here (extraction). The `user` source
    appears later, after the student edits a field (Phase 10
    provenance.diff / original_resume_values).
    """
    entries = []
    for path in collect_nonempty_paths(extracted):
        value = _resolve_path(extracted, path)
        if isinstance(value, list):
            evidence = f"{path} section ({len(value)} item(s))"
            entry_value = len(value)
        elif isinstance(value, dict):
            continue  # parent containers are covered by their leaves
        else:
            needle = value
            line = _evidence_line(raw_text, needle)
            evidence = line if line else f"found in resume ({path})"
            entry_value = value
        entries.append({
            "field": path,
            "value": entry_value,
            "source": "resume",
            "evidence": evidence,
        })
    return entries


# ------------------------------------------------------------
# RESUME DIAGNOSTICS
# ------------------------------------------------------------

# Section keywords (mirrors the Phase 9 parser's section detector)
_SECTION_KEYWORDS = {
    "education": ["education", "academic"],
    "skills": ["skills", "technical skills", "technologies"],
    "experience": ["experience", "work experience"],
    "internships": ["internship", "internships"],
    "projects": ["projects", "project"],
    "certifications": ["certification", "certifications"],
    "achievements": ["achievement", "achievements", "awards",
                     "publications", "open source"],
}


def _detected_sections(raw_text: str) -> list:
    found = []
    lowered = (raw_text or "").lower()
    for section, keywords in _SECTION_KEYWORDS.items():
        if any(kw in lowered for kw in keywords):
            found.append(section)
    return found


def _word_count(raw_text: str) -> int:
    return len(str(raw_text or "").split())


def build_diagnostics(raw_text: str, extraction: dict, extracted: dict) -> dict:
    """Resume quality diagnostics.

    - extraction_completeness: fraction of extractable sections
      that yielded data (0-100), not a claim of accuracy.
    - ocr_required: PDF with no extractable text (scanned).
    """
    text = str(raw_text or "")
    # The extraction layer sets ocr_required explicitly for PDFs with
    # no extractable text; fall back to detecting it here defensively.
    ocr_required = bool(
        extraction.get("ocr_required")
        or (extraction.get("file_type") == "pdf" and not text.strip())
    )
    detected = _detected_sections(text)
    populated = [
        section for section in detected if _section_populated(extracted, section)
    ]
    completeness = round(
        len(populated) / len(detected) * 100) if detected else 0
    return {
        "page_count": extraction.get("page_count"),
        "word_count": _word_count(text),
        "detected_sections": detected,
        "extraction_completeness": completeness,
        "ocr_required": ocr_required,
        "scanned_document_warning": ocr_required,
    }


def _section_populated(extracted: dict, section: str) -> bool:
    if section == "education":
        edu = extracted.get("education") or {}
        return any(v for v in edu.values())
    if section in ("experience", "internships", "projects", "certifications"):
        return bool(extracted.get(section))
    if section == "skills":
        skills = extracted.get("skills") or {}
        return any(skills.values())
    if section == "achievements":
        ach = extracted.get("achievements") or {}
        return any(ach.values())
    return False


# ------------------------------------------------------------
# EXTRACTION SUMMARY
# ------------------------------------------------------------


def build_extraction_summary(extracted: dict) -> dict:
    """What was found: counts + presence flags."""
    skills = extracted.get("skills") or {}
    skill_count = sum(len(v) for v in skills.values() if isinstance(v, list))
    achievements = extracted.get("achievements") or {}
    return {
        "fields_extracted": len(collect_nonempty_paths(extracted)),
        "counts": {
            "skills": skill_count,
            "projects": len(extracted.get("projects") or []),
            "internships": len(extracted.get("internships") or []),
            "experience": len(extracted.get("experience") or []),
            "certifications": len(extracted.get("certifications") or []),
            "hackathons": len(achievements.get("hackathons") or []),
        },
        "has_education": bool((extracted.get("education") or {}).get("cgpa")
                              or (extracted.get("education") or {}).get("degree")),
        "has_cgpa": (extracted.get("education") or {}).get("cgpa") is not None,
        "has_github": bool(extracted.get("github")),
        "has_linkedin": bool(extracted.get("linkedin")),
    }


# ------------------------------------------------------------
# COMPLETENESS (Phase 16 statuses, reuses Phase 10 mapping)
# ------------------------------------------------------------


def feature_availability_for_extraction(extracted: dict) -> list:
    """Classify the 16 Phase 8 features for an EXTRACTED profile.

    Statuses: AVAILABLE_FROM_RESUME / AVAILABLE_FROM_USER /
    CALCULATED / REQUIRES_MANUAL_INPUT / UNKNOWN.
    Reuses ml_feature_mapping's rules - nothing is invented.
    """
    from .ml_feature_mapping import BRANCH_SYNONYMS

    education = extracted.get("education") or {}
    statuses = []

    # cgpa
    cgpa = education.get("cgpa")
    statuses.append({
        "field": "cgpa",
        "status": "AVAILABLE_FROM_RESUME" if cgpa is not None
                  else "REQUIRES_MANUAL_INPUT",
        "reason": ("CGPA extracted from the resume." if cgpa is not None
                   else "CGPA was not found in the resume."),
    })

    # branch
    branch = (education.get("branch") or "").strip().lower()
    if branch in BRANCH_SYNONYMS:
        statuses.append({
            "field": "branch",
            "status": "AVAILABLE_FROM_RESUME",
            "reason": f"Branch '{education['branch']}' mapped to "
                      f"{BRANCH_SYNONYMS[branch]} (documented synonym).",
        })
    elif branch:
        statuses.append({
            "field": "branch",
            "status": "REQUIRES_MANUAL_INPUT",
            "reason": f"Resume branch '{education['branch']}' is not in the "
                      "documented synonym list - select it manually.",
        })
    else:
        statuses.append({
            "field": "branch",
            "status": "REQUIRES_MANUAL_INPUT",
            "reason": "Branch was not found in the resume.",
        })

    # calculated counts
    for field, section in [
        ("internships", "internships"),
        ("projects_count", "projects"),
        ("certifications", "certifications"),
        ("hackathons", "achievements"),
    ]:
        count = 0
        if section == "achievements":
            count = len((extracted.get("achievements") or {}).get("hackathons")
                        or [])
        else:
            count = len(extracted.get(section) or [])
        statuses.append({
            "field": field,
            "status": "CALCULATED",
            "reason": f"Counted {count} from the {section} section.",
        })

    # manual-input features (the 10 with no defensible resume source)
    manual = [
        "college_tier", "backlogs", "coding_skills", "dsa_score",
        "aptitude_score", "communication_skills", "ml_knowledge",
        "system_design", "open_source_contributions", "extracurriculars",
    ]
    for field in manual:
        statuses.append({
            "field": field,
            "status": "REQUIRES_MANUAL_INPUT",
            "reason": ("A resume cannot supply a validated value for this "
                       "field - it requires a manual assessment or the "
                       "student's input (never inferred from skill names)."),
        })
    return statuses


# ------------------------------------------------------------
# ANALYSIS ORCHESTRATION
# ------------------------------------------------------------


def analyze_resume(filename: str, content: bytes, content_type=None) -> dict:
    """Full Resume Intelligence analysis WITHOUT creating a profile.

    Returns the same base fields as /api/resume/upload PLUS
    provenance, confidence labels, diagnostics, and completeness.
    """
    base, full_raw_text = _process_resume_upload_full(
        filename, content, content_type
    )
    return build_analysis(base, full_raw_text)


def build_analysis(base: dict, full_raw_text: str = "") -> dict:
    """Add the intelligence layer to a process_resume_upload() result.

    `full_raw_text` is the complete extracted text, used only for
    short evidence snippets - the raw resume text is never exposed
    in full through the APIs (the preview stays truncated).
    """
    extracted = base["extracted_profile"]
    raw_text = full_raw_text or (base.get("extraction") or {}).get(
        "raw_text_preview"
    ) or ""

    diagnostics = build_diagnostics(raw_text, base["extraction"], extracted)
    return {
        "success": base["success"],
        "filename": base["filename"],
        "file_type": base["file_type"],
        "extraction": base["extraction"],
        "extracted_profile": extracted,
        "verification": base["verification"],
        "provenance": build_field_provenance(extracted, raw_text),
        "confidence": classify_confidence(
            base["verification"].get("confidence") or {}
        ),
        "diagnostics": diagnostics,
        "extraction_summary": build_extraction_summary(extracted),
        "completeness": {
            "profile_complete": False,
            "feature_availability": feature_availability_for_extraction(
                extracted),
        },
    }
