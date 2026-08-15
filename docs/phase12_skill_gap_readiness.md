# Phase 12 — Skill Gap + Placement Readiness Engine

> Built on the Phase 8 → Phase 11 architecture. No previous phase was
> rebuilt, no model was retrained or modified, and the Phase 8
> prediction pipeline is untouched.

## 1. What this phase adds

Two read-only analysis endpoints over a **verified** student profile:

| Endpoint | Purpose |
|----------|---------|
| `GET /api/profile/{profile_id}/readiness` | Transparent rule-based readiness score + strengths + skill gaps + improvement plan |
| `GET /api/profile/{profile_id}/placement-summary` | Phase 11 ML prediction **and** Phase 12 readiness, reported side by side |

## 2. Conceptual separation (never merged)

| Concept | Source | Meaning |
|---------|--------|---------|
| `placement_probability` / `prediction` | **Only** the trained Phase 8 model (`src/pipeline.py` via the Phase 11 flow) | ML probability of placement |
| `readiness_score` | Transparent rule-based formula (this phase) | How ready the profile looks for placements — **not** ML accuracy |
| `skill_gaps` | Verified profile skills vs `PLACEMENT_REQUIREMENTS` | What placement-relevant skills are missing |
| `improvement_plan` | Derived from the skill-gap analysis | What to work on first |

The two scores are **never merged or mathematically combined** — they
measure different things and are reported separately.

## 3. Architecture

```
backend/app/
  services/skill_taxonomy.py    <- configurable taxonomy + normalization + requirements
  services/readiness_service.py <- the engine (skills, strengths, gaps, score, plan)
  schemas_readiness.py          <- response models
  routes/readiness.py           <- the two GET endpoints
  main.py                       <- additive router registration only
```

The engine reads profiles through the existing `profile_service.get_profile()`
— there is no second storage layer, and only **verified** profiles are
analyzed (unverified → HTTP 422).

## 4. Skill taxonomy

All skill logic lives in one configurable module
(`backend/app/services/skill_taxonomy.py`), not scattered across files:

- **8 categories**: Programming, Web, Database, Data / AI, Core CS,
  Tools, Cloud, Interview.
- **Normalization map** (`SKILL_ALIASES`): `js`→JavaScript,
  `reactjs`→React, `node`→Node.js, `mysql`→MySQL, `ml`→Machine
  Learning, `scikit learn`→Scikit-learn, `dsa`→[Data Structures,
  Algorithms], `cpp`→C++, … Matching is **exact** (lowercased,
  punctuation-stripped) — no fuzzy/contains matching, so unrelated
  skills are never falsely classified. Unknown names simply produce no
  canonical skill.
- **Requirements** (`PLACEMENT_REQUIREMENTS`): a generic software
  placement set — 6 Core CS skills (each required), a programming
  language OR-group (Python OR Java OR C++), plus Git, SQL and
  Communication.

## 5. Skill sources (all verified, with provenance)

| Source | Where from |
|--------|------------|
| `resume` / `user` | `profile.skills.*` lists, attributed via `provenance` |
| `projects` | `projects[].technologies` |
| `internships` | `internships[].technologies` |
| `experience` | `experience[].technologies` |
| `certifications` | certification names (exact match, then token-level scan, e.g. "AWS Certified Solutions Architect" → AWS) |

Each entry keeps its provenance:
```json
{ "skill": "Python", "source": "projects", "verified": true, "original": "Python" }
```
Skill presence is **never** converted into an artificial numeric skill
score.

## 6. Strengths (evidence-based)

A skill is a **strength** when it has evidence from at least **2
distinct sources** (e.g. 3 projects + 1 internship). Evidence strings
are factual counts from the profile — nothing fabricated:
```json
{ "skill": "Python", "category": "Programming",
  "evidence": ["2 projects", "1 internship", "listed in user skills"] }
```

## 7. Skill-gap logic

A gap is produced only when a defined placement requirement is **not
found in the verified profile**. The reason always says exactly that —
it never claims "the student does not know X", because the resume may
simply not mention it:
```json
{ "skill": "Data Structures", "category": "Core CS",
  "priority": "HIGH",
  "reason": "Required placement skill not found in verified profile" }
```

## 8. Priority system (documented)

| Priority | Applies to | Rationale |
|----------|------------|-----------|
| `HIGH` | 6 Core CS skills + the programming-language OR-group | Foundational: standard placement filters, and they unlock most other skills |
| `MEDIUM` | Git, SQL, Communication | Important, but often evaluated later or only for some roles |
| `LOW` | reserved (none configured today) | Optional / nice-to-have requirements |

Priorities are configured per requirement in `PLACEMENT_REQUIREMENTS`
— there are no unexplained hidden scores.

## 9. Readiness score formula (0–100, fully documented)

| Component | Max | Rule |
|-----------|-----|------|
| `technical_skills` | 30 | (requirements met ÷ 7 slots) × 30 — 6 Core CS + 1 language OR-group |
| `projects` | 20 | 0→0, 1→10, 2→16, ≥3→20 |
| `internships` | 15 | 0→0, 1→10, ≥2→15 |
| `certifications` | 8 | 0→0, 1→4, ≥2→8 |
| `communication` | 7 | Communication skill present → 7 |
| `profile_completeness` | 20 | (filled ÷ 8 canonical sections) × 20 |

**Rationale:** foundational technical skills and demonstrated
experience (projects/internships) dominate; merely listing many skills
cannot produce a high score (a student with 20 listed skills but no
projects or internships stays capped well below the top). The
breakdown is returned in the API response (`readiness_breakdown`) so
the score is auditable.

## 10. Readiness levels

| Score | Level |
|-------|-------|
| 0–39 | Needs Improvement |
| 40–59 | Developing |
| 60–74 | Placement Ready |
| 75–89 | Strong |
| 90–100 | Highly Ready |

## 11. Improvement plan

Generated from the skill gaps, ordered HIGH → MEDIUM → LOW, numbered
1..n ("1 = do this first"). Every item has a generic, educational
action:
```json
{ "priority": 1, "skill": "Data Structures",
  "reason": "Required placement skill not found in verified profile",
  "action": "Practice arrays, strings, linked lists, stacks, queues, trees and graphs" }
```
Recommendations are educational guidance — **never** a placement
guarantee.

## 12. API

### `GET /api/profile/{profile_id}/readiness`

- 404 if the profile does not exist; **422 if unverified**.
- Response:
```json
{
  "profile_id": "...",
  "readiness_score": 68,
  "readiness_level": "Placement Ready",
  "readiness_breakdown": { "technical_skills": 25, "projects": 15,
    "internships": 10, "certifications": 5, "communication": 5,
    "profile_completeness": 8 },
  "strengths": [],
  "skill_gaps": [],
  "improvement_plan": [],
  "profile_completeness": { "percentage": 82, "missing_fields": [] }
}
```

### `GET /api/profile/{profile_id}/placement-summary`

- Requires a verified profile (else 422). The prediction part runs the
  exact Phase 11 flow (verified → completeness check →
  `src.pipeline.predict_placement()`), so prediction history is
  recorded exactly as Phase 11 does.
- Response: Phase 11 prediction fields (`ready_for_prediction`,
  `prediction`, `placement_probability`, `confidence`, `model_version`,
  `missing_fields`, `reason`) **plus** the Phase 12 readiness fields —
  reported side by side, never merged.

## 13. Security / data integrity

- Profile IDs validated as before (letters/digits/`-`/`_` only) — no
  path traversal; unknown IDs → 404.
- The readiness engine is **read-only**: it never modifies the profile,
  never stores fabricated attributes, and never overwrites verified
  user data with derived values (provenance rules from Phase 10 still
  apply).
- The trained model (`models/placepro_final_model.pkl`) and the Phase 8
  pipeline are untouched.

## 14. Limitations (honest)

- The readiness score is a **rule-based heuristic**, not ML accuracy
  and not calibrated to outcomes. ML placement probability is ~63%
  accuracy / 0.685 ROC-AUC (Phase 8 metrics, unchanged).
- Skill detection is limited to the taxonomy; skills not in it are
  ignored by the gap analysis (never misclassified).
- The placement requirements are a single *generic* profile — real
  company/role-specific requirements are a later phase.
- Only verified profile information is used; anything not confirmed by
  the student is invisible to the analysis.
- No authentication yet (later phase).

## 15. Testing

- `backend/tests/test_readiness.py` — 82 checks covering all 18
  required scenarios (verified complete, unverified → error, strong
  technical skills, few skills, multiple projects, internships,
  missing skills, normalization, provenance, score range, levels,
  priorities, improvement plan, empty skills, and HTTP regression of
  Phase 8/9/10/11 endpoints + the two new endpoints).
- All prior suites re-run in the final verification (Phase 8, 9, 10, 11).

## 16. Run it

```bash
uvicorn backend.app.main:app --reload
python backend/tests/test_readiness.py     # 82 checks (server needed for HTTP part)
```

Flow: `POST /api/profile/from-resume` → `PUT /api/profile/{id}` →
`POST /api/profile/verify` → `GET /api/profile/{id}/readiness` →
`GET /api/profile/{id}/placement-summary`.
