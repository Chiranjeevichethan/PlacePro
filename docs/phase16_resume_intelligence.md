# Phase 16 — Resume Intelligence 2.0

Phase 16 upgrades the Phase 9 resume extraction into a robust **Resume
Intelligence layer** without breaking any Phase 8–15 functionality.

---

## 1. Extraction architecture

```
Resume (PDF / DOCX)
      │  validate (extension, MIME, magic bytes, size, empty)
      ▼
Phase 9 extraction (resume_service.resume_parser - UNCHANGED)
      │
      ▼
Phase 16 intelligence layer (resume_intelligence.py - ADDITIVE)
      ├─ field provenance (value + source + evidence)
      ├─ confidence labels (high / medium / low)
      ├─ resume diagnostics (pages, words, sections, OCR)
      ├─ extraction summary (counts, presence flags)
      └─ feature availability (AVAILABLE_FROM_RESUME / USER /
                               CALCULATED / REQUIRES_MANUAL_INPUT /
                               UNKNOWN)
```

The Phase 9 extraction contract (`POST /api/resume/upload`) is untouched.
The intelligence layer is a **read-only analysis** on top of it.

## 2. Supported formats

| Format | Library | Page count | Notes |
|--------|---------|-----------|-------|
| PDF | `pypdf` | yes | Scanned (text-less) PDFs → `OCR_REQUIRED` status |
| DOCX | `python-docx` | no (`None`) | Never OCR-flagged |

Validation (unchanged from Phase 9 + hardened): extension whitelist,
magic-byte check (authoritative), MIME check where sent, 5 MB size cap,
empty / corrupted rejection. Files go to a random temp path and are
deleted after processing. No path traversal, no arbitrary file access,
no execution.

## 3. Extracted fields

Only what is **explicitly present** is returned; everything else is
`null` / `[]` (nothing is invented):

- **Personal:** name, email, phone, location, LinkedIn, GitHub, portfolio
- **Education:** degree, branch, college, CGPA, graduation year
- **Skills:** programming languages, frameworks, databases, cloud,
  AI/ML, web technologies, tools, other skills
- **Experience / Internships:** company, role, duration, technologies
- **Projects:** name, description, technologies
- **Certifications:** name, issuer, year
- **Achievements:** hackathons, awards, coding achievements

## 4. Provenance

Every extracted field carries `{field, value, source, evidence}`:

```json
{
  "field": "education.cgpa",
  "value": 8.2,
  "source": "resume",
  "evidence": "B.Tech in Computer Science, IIT Delhi, CGPA: 8.2, 2022-2026"
}
```

Sources: `resume` (extraction), `user` (after the student edits),
`calculated` (derived counts), `system` (diagnostics). Evidence is a
**short truncated snippet** — the raw resume text is never exposed in
full through the APIs (the preview stays at ~500 chars).

When the student edits an extracted field, `source` becomes `user` and
the **original resume value is preserved** server-side in the profile's
`original_resume_values` map (e.g. CGPA 8.1 extracted → student edits to
8.2 → `value=8.2`, `source=user`, `original_resume_values["education.cgpa"]=8.1`).

## 5. Confidence

Confidence labels are **heuristic extraction confidence**, derived from
the Phase 9 per-field 0..1 heuristic:

| Score | Label |
|-------|-------|
| ≥ 0.85 | `high` |
| 0.60 – 0.84 | `medium` |
| < 0.60 | `low` |

Confidence is about **how reliably the value was extracted from the
text** — it is NEVER "ML confidence" and NEVER a claim that the student
possesses a skill. Where confidence cannot be trusted, fields appear in
`needs_verification`.

## 6. Verification

**Extracted ≠ verified.** Profiles built from resumes start with
`verified: false` and only become verified after the student explicitly
confirms via `POST /api/profile/verify`. Editing a verified profile
resets `verified` to `false`. Nothing is assumed correct from a resume.

## 7. Skill normalization

Reuses **Phase 12 `skill_taxonomy.py`** — there is exactly one
normalization system in the project. Documented aliases include:

`JS → JavaScript`, `ReactJS → React`, `Node → Node.js`,
`ML → Machine Learning`, `DSA → [Data Structures, Algorithms]`,
`scikit learn → Scikit-learn`.

Unknown skills are left as-is (never misclassified into a wrong bucket).

## 8. ML feature mapping

Reuses **Phase 10 `ml_feature_mapping.py`** — only defensible
relationships are mapped:

| Feature | Source |
|---------|--------|
| `cgpa` | education.cgpa |
| `branch` | education.branch via documented synonyms |
| `internships` | count of internships |
| `projects_count` | count of projects |
| `certifications` | count of certifications |
| `hackathons` | count of achievements.hackathons |
| other 10 (college_tier, backlogs, coding_skills, dsa_score, aptitude_score, communication_skills, ml_knowledge, system_design, open_source_contributions, extracurriculars) | **manual input only** |

A skill name like "Python" is NEVER converted into
`coding_skill_score`; listing "DSA" never becomes `dsa_score`. Those
require actual assessments / the student's input.

## 9. Completeness

New statuses for the Phase 16 completeness report:

- `AVAILABLE_FROM_RESUME` — defensible value extracted from the resume
- `AVAILABLE_FROM_USER` — value supplied by the student via `ml_inputs`
- `CALCULATED` — deterministic count from a profile list
- `REQUIRES_MANUAL_INPUT` — no defensible resume source
- `UNKNOWN` — no value anywhere

Example:

```json
{
  "field": "dsa_score",
  "status": "REQUIRES_MANUAL_INPUT",
  "reason": "A resume cannot supply a validated value for this field - it requires the student's input or an assessment (never inferred from skill names)."
}
```

## 10. OCR limitation

A PDF with no extractable text (scanned / image-only) is detected and
reported explicitly as **`OCR_REQUIRED`** (HTTP 422 with a clear
message). It is never silently treated as a valid empty resume or
mislabeled as corrupted. **OCR itself is not implemented** — that
remains a documented limitation (adding it reliably without breaking the
existing architecture was judged out of scope for this phase).

## 11. Security

- Extension + MIME + magic-byte validation; 5 MB limit
- Random temp filenames — the client filename is never used for path
  construction (no path traversal)
- Temp storage cleaned up after processing
- Files are parsed only, never executed
- No filesystem paths exposed in responses
- No secrets in code

## 12. API examples

### POST /api/resume/analyze (NEW — analysis without creating a profile)

```
POST /api/resume/analyze   (multipart/form-data, field "file")
```

```json
{
  "success": true,
  "filename": "resume.pdf",
  "file_type": "pdf",
  "extraction": { "raw_text_preview": "...", "page_count": 1,
                  "extraction_success": true, "ocr_required": false },
  "extracted_profile": { ... },
  "verification": { "confidence": {...}, "needs_verification": [...] },
  "provenance": [ { "field": "education.cgpa", "value": 8.2,
                    "source": "resume", "evidence": "..." } ],
  "confidence": { "email": "high", "education.cgpa": "high" },
  "diagnostics": { "page_count": 1, "word_count": 120,
                   "detected_sections": ["education", "skills", "..."],
                   "extraction_completeness": 80,
                   "ocr_required": false, "scanned_document_warning": false },
  "extraction_summary": { "fields_extracted": 18, "counts": {...} },
  "completeness": { "profile_complete": false,
                    "feature_availability": [ ... ] }
}
```

### POST /api/profile/from-resume (ENHANCED — backward compatible)

The Phase 10 response (`profile` / `completion` / `message`) is
unchanged; these fields are **added**:

`provenance`, `confidence`, `diagnostics`, `extraction_summary`,
`feature_availability`.

### POST /api/resume/upload (UNCHANGED)

The Phase 9 contract is fully preserved (one additive field,
`extraction.ocr_required`).

## 13. Limitations

- OCR for scanned PDFs is not implemented (explicit `OCR_REQUIRED` status)
- Extraction is heuristic — not 100% accurate; nothing is auto-verified
- Skills are limited to the Phase 12 taxonomy
- 10 of 16 ML features still require manual input
- No authentication yet (later phase)
- Resume text is never stored; only the extracted profile
