# PlacePro — Phase 10: Resume → Verified Student Profile

Date: August 2026
Branch: `phase9-resume-extraction` (Phase 10 work)

## 1. Goal

Connect **resume → extracted profile → student verification → unified
student profile**. Raw resume extraction is **never** sent straight to the
ML model — the student must review, correct, and explicitly confirm the
profile first. No prediction is made yet (that is Phase 11).

```
RESUME
  │  POST /api/profile/from-resume   (reuses Phase 9 extraction)
  ▼
DRAFT PROFILE   (verified: false, provenance.resume populated)
  │  student reviews & edits  →  PUT /api/profile/{id}
  ▼
EDITING (verified resets to false on any edit)
  │  POST /api/profile/verify   (explicit confirmation)
  ▼
VERIFIED PROFILE   (verified: true, provenance.user computed)
  │  GET /api/profile/{id}
  ▼
completion check → missing_fields / ml_feature_mapping   (Phase 11 will consume)
```

## 2. Canonical student profile

One structure (`backend/app/schemas_profile.py`), used by every profile
endpoint. It clearly separates where information came from:

| Source | Tracked in | Meaning |
|--------|-----------|---------|
| A. Resume-extracted | `provenance.resume` | Values pulled from the uploaded resume |
| B. User-provided | `provenance.user` | Values the student typed / edited |
| C. ML-derived | `provenance.ml` | **Reserved** for Phase 11 model outputs (empty now) |

```json
{
  "profile_id": "…",
  "personal":   {"name", "email", "phone", "location", "linkedin", "github", "portfolio"},
  "education":  {"degree", "branch", "college", "cgpa", "graduation_year"},
  "skills":     {"programming_languages": [], "frameworks": [], "databases": [],
                 "cloud": [], "ai_ml": [], "web_technologies": [], "tools": [],
                 "other_skills": []},
  "experience": [{"company", "role", "duration", "technologies"}],
  "internships":[…],
  "projects":   [{"project_name", "description", "technologies"}],
  "certifications": [{"name", "issuer", "year"}],
  "achievements": {"hackathons": [], "awards": [], "coding_achievements": []},
  "ml_inputs":  {"college_tier", "backlogs", "coding_skills", "dsa_score",
                 "aptitude_score", "communication_skills", "ml_knowledge",
                 "system_design", "open_source_contributions", "extracurriculars"},
  "provenance": {"resume": [], "user": [], "ml": []},
  "verified": false
}
```

- `ml_inputs` holds the Phase 8 model features with **no defensible resume
  source** — the student supplies them manually.
- Reuses Phase 9 structures (`schemas_resume.py`) — no duplicated schemas.

## 3. Resume → profile mapping (from-resume)

`POST /api/profile/from-resume` runs the Phase 9 extraction internally and
builds the draft profile:

- All extractable fields populate the profile; `provenance.resume` records
  every non-empty field path (e.g. `personal.name`, `education.cgpa`,
  `skills.frameworks`, `internships`).
- `ml_inputs` starts empty; `verified` is `false`; `provenance.user` is empty.
- **Nothing is assumed correct** — the draft is a proposal for review.

## 4. Verification process

- The student reviews every extracted value (all fields are editable via
  `PUT /api/profile/{id}`).
- `POST /api/profile/verify` is the **explicit confirmation**. It requires
  `name` and `email` (so the student is identifiable), then:
  - computes `provenance.user` by diffing the submitted profile against the
    stored draft (edited paths become user-provided);
  - sets `verified: true`.
- **Any edit after verification resets `verified` to `false`** — the student
  must confirm again.

## 5. Missing-field handling

- Missing scalar fields → `null`; missing collections → `[]`. Never invented.
- The completion check (`completion` in every response) returns:

```json
{
  "profile_complete": false,
  "missing_fields": ["aptitude_score", "coding_skills", "dsa_score", "…"],
  "ml_feature_mapping": { "branch": "CSE", "cgpa": 8.2, "aptitude_score": null, "…": "…" }
}
```

The frontend can tell the student: *"Your resume was processed, but we need
a few additional details before making a prediction."*

## 6. ML feature mapping (the important part)

The mapping layer (`backend/app/services/ml_feature_mapping.py`) is the
**only** place that connects the verified profile to the Phase 8 model.
It imports the feature contract directly from
`src.pipeline.RAW_FEATURE_COLUMNS` (single source of truth — no duplicate
list, nothing guessed) and never touches the trained model.

Only **defensible** mappings exist:

| ML feature | Source |
|------------|--------|
| `cgpa` | `education.cgpa` |
| `branch` | `education.branch` via a documented synonym table (`Computer Science→CSE`, `IT→IT`, `ECE→ECE`, `Mechanical→ME`, `Civil→CE`, `Electrical→EE`, `Chemical→Chemical`); unknown branches → `null` |
| `internships` | count of `profile.internships` |
| `projects_count` | count of `profile.projects` |
| `certifications` | count of `profile.certifications` |
| `hackathons` | count of `achievements.hackathons` |
| the other 10 (`college_tier`, `backlogs`, `coding_skills`, `dsa_score`, `aptitude_score`, `communication_skills`, `ml_knowledge`, `system_design`, `open_source_contributions`, `extracurriculars`) | **user-provided via `ml_inputs` only** — never derived |

**Explicitly NOT done:** `"Python"` is never converted into
`coding_skill_score = 90`; no such deterministic mapping exists in this
project. Skills are reported as skills; scored features come only from the
student. Branches like AI/ML/Data Science are not in the dataset's branch
list and therefore require manual selection (defensible mapping only).

## 7. API endpoints

| Endpoint | Purpose |
|----------|---------|
| `POST /api/profile/from-resume` | multipart resume → draft profile (+ completion) |
| `POST /api/profile/verify` | body = full edited profile → explicit confirmation (`verified: true`) |
| `GET /api/profile/{id}` | fetch a stored profile (+ completion) |
| `PUT /api/profile/{id}` | apply student edits (resets `verified` to `false`) |

Error codes: `400` empty file, `413` too large, `415` unsupported type,
`422` corrupted/unparseable file or invalid profile (e.g. verify without
name/email, bad types), `404` unknown profile id.

Storage: lightweight JSON files under `data/profiles/` (dev-grade, gitignored;
a real database is a later phase). Uploaded resumes are never stored.

## 8. Limitations

- No prediction yet — completion/mapping are informational for the frontend
  (Phase 11 wires `verified profile → src.pipeline.predict_placement`).
- File-based profile store: no auth, no multi-user isolation, single-process
  safe only (a threading lock protects writes).
- `branch` mapping is limited to documented synonyms; unknown branches and
  AI/ML/Data Science branches require manual selection.
- 10 of 16 model features have no resume source and always require manual
  input unless provided.
- Profile edits that add/remove whole entries (e.g. an internship) mark the
  whole list as user-provided (coarse-grained provenance).

## 9. Testing

```bash
python backend/tests/test_profile.py        # 69 checks (service + HTTP)
uvicorn backend.app.main:app --reload       # required for HTTP part
```

Coverage: complete resume, missing CGPA, missing internship, multiple
projects, multiple skills, manual edits, verification, missing ML-required
fields, invalid profiles, plus regression for `/api/predict`,
`/api/resume/upload` and `/health`.

## 10. How to run

```bash
uvicorn backend.app.main:app --reload
# POST /api/profile/from-resume   (multipart field "file")
# PUT  /api/profile/{id}          (edited profile JSON)
# POST /api/profile/verify        (confirmed profile JSON)
# GET  /api/profile/{id}
```
