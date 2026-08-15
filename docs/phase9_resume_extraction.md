# PlacePro — Phase 9: Resume Upload & Intelligent Resume Extraction

Date: August 2026
Branch: `phase9-resume-extraction` (built on the Phase 8 foundation)

## 1. Architecture

```
Resume (PDF / DOCX)
   │
   ▼
POST /api/resume/upload  (backend/app/routes/resume.py)
   │  multipart/form-data
   ▼
resume_service.py  (backend/app/services/resume_service.py)
   │  extension check → size check → magic-byte check → MIME check
   │  temp file (random name) → extract text → cleanup (TemporaryDirectory)
   ▼
resume_parser.py  (backend/app/services/resume_parser.py)
   │  extract_text()  : pypdf / python-docx
   │  parse_resume()  : section detection → regex/keyword extraction
   ▼
schemas_resume.py  (backend/app/schemas_resume.py)
   └─ ResumeUploadResponse (structured JSON + verification)
```

New modules (Phase 8 files untouched):

| File | Purpose |
|------|---------|
| `backend/app/routes/resume.py` | `POST /api/resume/upload` endpoint |
| `backend/app/services/resume_service.py` | Validation, temp storage, orchestration |
| `backend/app/services/resume_parser.py` | Text extraction + structured parsing |
| `backend/app/schemas_resume.py` | Response schemas |
| `backend/tests/test_resume.py` | Test suite |

> Note on schemas: Phase 8's `schemas.py` is a protected do-not-modify file,
> so the resume schemas live in a separate module (`schemas_resume.py`)
> rather than a `schemas/` package (a directory cannot coexist with the
> existing `schemas.py` file).

## 2. Supported formats

| Format | Library | Notes |
|--------|---------|-------|
| PDF | `pypdf` | page count reported; text must be extractable (no scanned/image-only PDFs yet) |
| DOCX | `python-docx` | paragraphs + table cells; page count reported as `null` (not determinable without rendering) |

Anything else (`.txt`, `.png`, `.exe`, …) is rejected with HTTP 415.

## 3. Extraction process

1. **Validation** — extension whitelist, 5 MB size cap, empty check,
   magic-byte check (`%PDF` / ZIP `PK\x03\x04`), MIME check when the
   client supplies one.
2. **Text extraction** — raw text + page count. Failures raise useful
   errors (never silent).
3. **Section detection** — whole-line heading matching
   (education, skills, experience, internships, projects, certifications,
   achievements) with support for bullets/numbering.
4. **Structured extraction** — personal (name, email, phone, location,
   LinkedIn, GitHub, portfolio), education (degree, branch, college, CGPA,
   graduation year), skills (8 categories from a keyword taxonomy),
   experience/internships (company, role, duration, technologies),
   projects (name, description, technologies), certifications
   (name, issuer, year), achievements (hackathons, awards, coding).
5. **Confidence/verification** — heuristic per-field confidence + a
   `needs_verification` list (missing or uncertain fields).

### Honesty rules (never invent data)

- A field is returned **only** when evidence exists in the text.
- Missing scalar fields → `null`; missing list fields → `[]`.
- No inference: `"cgpa": null` when no CGPA appears; skills are returned
  as found (`["Python", "Java", "SQL"]`), **never** converted into scores
  like `coding_skill_score: 85`.
- **Raw data vs derived data are kept separate**: Phase 9 produces only
  `resume_extracted_data`. No placement probability, readiness score, or
  skill scores are calculated (that is Phase 10+).

## 4. API endpoint

### `POST /api/resume/upload`

- Content-Type: `multipart/form-data`
- Field: `file` (the resume file, `.pdf` or `.docx`)

### Request example (curl)

```bash
curl -X POST http://127.0.0.1:8000/api/resume/upload \
     -F "file=@resume.pdf;type=application/pdf"
```

### Response (200)

```json
{
  "success": true,
  "filename": "resume.pdf",
  "file_type": "pdf",
  "extraction": {
    "raw_text_preview": "John Doe\nBengaluru, Karnataka\n...",
    "page_count": 1,
    "extraction_success": true
  },
  "extracted_profile": {
    "name": "John Doe",
    "email": "john.doe@gmail.com",
    "phone": "+91 98765 43210",
    "location": "Bengaluru, Karnataka",
    "linkedin": "linkedin.com/in/johndoe",
    "github": "github.com/johndoe",
    "portfolio": null,
    "education": {
      "degree": "B.Tech",
      "branch": "Computer Science",
      "college": "IIT Delhi",
      "cgpa": 8.2,
      "graduation_year": 2026
    },
    "skills": {
      "programming_languages": ["Python", "Java", "SQL"],
      "frameworks": ["Django", "React"],
      "databases": ["MySQL"],
      "cloud": ["AWS", "Docker"],
      "ai_ml": ["TensorFlow"],
      "web_technologies": [],
      "tools": ["Git"],
      "other_skills": []
    },
    "experience": [
      {"company": "Google", "role": "Software Engineer",
       "duration": "2022-2024", "technologies": ["Python", "Go", "Kubernetes"]}
    ],
    "internships": [
      {"company": "Microsoft", "role": "Summer Intern",
       "duration": "2023", "technologies": ["Azure"]}
    ],
    "projects": [
      {"project_name": "Project Alpha",
       "description": "A web dashboard for analytics",
       "technologies": ["React", "Node.js", "MongoDB"]}
    ],
    "certifications": [
      {"name": "AWS Certified Solutions Architect", "issuer": "Amazon", "year": 2023}
    ],
    "achievements": {
      "hackathons": ["Winner, Smart India Hackathon 2024"],
      "awards": [],
      "coding_achievements": ["LeetCode rating 1800"]
    }
  },
  "verification": {
    "confidence": {
      "name": 0.5, "email": 0.97, "phone": 0.9,
      "education.cgpa": 0.9, "skills": 0.8, "...": 0.0
    },
    "needs_verification": ["name", "location", "portfolio",
                           "education.college", "education.graduation_year"]
  }
}
```

### Error responses

| Code | Case |
|------|------|
| 400 | Empty file |
| 413 | File larger than 5 MB |
| 415 | Unsupported extension / MIME / extension-content mismatch |
| 422 | Corrupted or unparseable file (passes magic bytes, fails parsing) |

## 5. Security measures

- **Allowed extensions only** (`.pdf`, `.docx`)
- **Size limit** (5 MB, enforced before full read)
- **Magic-byte validation** (authoritative; MIME is advisory where sent)
- **Temp storage**: random filename (client filename is never used for
  path construction → no path traversal); files deleted after processing
  via `TemporaryDirectory`
- **No execution**: files are only parsed by `pypdf` / `python-docx`
- **No persistence**: resumes are not stored
- **Safe exception handling**: structured errors; no stack traces leaked
- **No secrets in code**
- Authentication deliberately NOT added (a later phase)

## 6. Limitations (honest)

- **Heuristic, not ML-based**: extraction is regex + keyword rules. Layouts
  that don't match the supported patterns will extract less.
- **Scanned/image-only PDFs** are not supported (no OCR yet).
- **Skills are taxonomy-limited**: skills outside the keyword list are not
  returned. The taxonomy is easy to extend in `resume_parser.py`.
- **Experience/internship splitting** relies on date ranges/years in the
  section; entries without dates are not fabricated.
- **Confidence is heuristic**, not calibrated — treat it as a review aid;
  uncertain fields are flagged in `needs_verification`.
- **DOCX page count is `null`** (page count is a rendering concept).
- Resume extraction is **not yet connected to ML prediction** (Phase 10).
- No auth, rate limiting, or persistent storage yet.

## 7. Testing

Run (server optional for service tests; required for HTTP tests):

```bash
python backend/tests/test_resume.py
uvicorn backend.app.main:app --reload   # then re-run for HTTP tests
```

Coverage (all passing — 82 checks):

1. Valid PDF 2. Valid DOCX 3. Unsupported file (415)
4. Empty file (400) 5. Corrupted file (422)
6. Complete resume information 7. Missing information (null/[] not invented)
8. Multiple projects 9. Multiple internships
+ `GET /health` and `POST /api/predict` (Phase 8 regression — still works)

## 8. Dependencies added

```text
python-multipart   # multipart/form-data parsing in FastAPI
pypdf              # PDF text extraction
python-docx        # DOCX parsing
```

## 9. How to run

```bash
uvicorn backend.app.main:app --reload
# POST /api/resume/upload (multipart field "file")
# GET  /health
# POST /api/predict  (Phase 8, unchanged)
```
