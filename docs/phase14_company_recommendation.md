# Phase 14 — Company Recommendation Engine

> Built on the Phase 8 → Phase 13 architecture. No previous phase was
> rebuilt, no model was retrained or modified, and the Phase 8
> prediction pipeline is untouched.

## 1. What this phase adds

One read-only endpoint that ranks the active **SAMPLE/DEMO** companies
for a **verified** profile and explains *why* each one is (or isn't) a
match:

```
GET /api/profile/{profile_id}/recommendations[?limit=N]
```

## 2. Recommendation architecture

```
verified profile
   │
   ├─ Phase 13 eligibility_service  ──> eligibility per company (PASS/FAIL/UNKNOWN)
   ├─ Phase 12 readiness_service    ──> readiness_score + level + completeness
   ├─ Phase 12 skill taxonomy       ──> normalized verified skills
   ├─ Phase 8 model (via Phase 10   ──> model-estimated placement probability
   │    ML-feature mapping)            (read-only - no history written)
   │
   ▼
recommendation_service  ──> weighted 0-100 score + status + reasons + actions
```

Everything is computed **server-side** — clients never submit scores,
statuses, probabilities or readiness values.

## 3. Recommendation score (transparent weighted formula)

| Component | Weight | Rule |
|-----------|--------|------|
| Eligibility | 30 | `ELIGIBLE` → 30; `INCOMPLETE` → 30 × (mandatory passed ÷ total); `NOT_ELIGIBLE` → 0 |
| Skill match | 25 | 25 × (0.75 × required matched fraction + 0.25 × preferred matched fraction) |
| Readiness | 20 | readiness_score ÷ 100 × 20 |
| Placement probability | 15 | probability × 15 (0 when the model cannot run — missing ML features are never invented) |
| Profile completeness | 10 | completeness % ÷ 100 × 10 |

The score is a transparent heuristic — **not** a machine-learning
probability.

## 4. Eligibility override (critical)

Mandatory eligibility failures **override** the numerical score:

| Eligibility | Recommendation status |
|-------------|------------------------|
| `ELIGIBLE` and score ≥ 75 | `RECOMMENDED` |
| `ELIGIBLE` and score < 75 | `ELIGIBLE` |
| `INCOMPLETE` | `INCOMPLETE` (eligibility unconfirmed — score is provisional) |
| `NOT_ELIGIBLE` | `NOT_RECOMMENDED` (score shown but informational) |

An ineligible company can never become "recommended" just because its
number looks high — with eligibility at 0 the score is capped well
below the recommended threshold, and the status is overridden outright.

## 5. Skill matching

Reuses the Phase 12 taxonomy and verified skills (one normalization
system — a resume that says "ReactJS" matches a requirement of
"React"). For each company:

- `required_matched` / `required_missing` — required skills present /
  absent in the verified profile
- `preferred_matched` / `preferred_missing` — preferred skills
  (contribute positively, **never** override mandatory eligibility)

Skill-match score = 0.75 × required fraction + 0.25 × preferred
fraction, on a 0–100 scale.

## 6. Readiness & ML probability integration

- **Readiness**: the Phase 12 `readiness_score` and `readiness_level`
  are reported as-is (no duplicated calculation).
- **ML probability**: the Phase 8 model is called through the Phase 10
  ML-feature mapping — the same values the Phase 11 prediction uses.
  Recommendations are a **read-only view** and do **not** write to
  prediction history. It is always labeled *"Model-estimated placement
  probability"* and never interpreted as a guaranteed placement.

## 7. Ranking & statuses

Companies are grouped into `recommended` / `eligible` / `incomplete` /
`not_recommended`, each sorted by `recommendation_score` descending.
Recommended companies appear before merely-eligible ones, incomplete
companies are separated, and not-recommended companies are never
presented as good matches.

### Optional `?limit=N`

Validated to 1–50 (else 422). Caps the **total** number of items,
filling buckets in priority order (recommended → eligible →
incomplete → not_recommended) so semantics are preserved.

## 8. Explanability & honesty

Every item answers "why":

- `RECOMMENDED`: *"All mandatory eligibility requirements satisfied"*,
  skill match %, readiness score + level, model-estimated probability,
  *"Strong overall fit — top recommendation"*
- `INCOMPLETE`: *"Not enough information to confirm eligibility
  because: cgpa, Data Structures."*
- `NOT_RECOMMENDED`: *"Not recommended because Your CGPA is 6.8, while
  the minimum requirement is 7.5."*

**Honesty rules:** the ML probability is only the model's estimate of
the placement target in the existing dataset — the system never claims
"you will get this company" or "85% chance of getting hired". Demo
company requirements are clearly **SAMPLE/DEMO** and are not official
criteria for any real company.

## 9. Response example (values are real, from the engine)

```json
{
  "profile_id": "...",
  "recommendations": {
    "recommended": [
      {
        "company_id": "company_001",
        "company_name": "DemoTech",
        "status": "RECOMMENDED",
        "recommendation_score": 90.1,
        "eligibility_status": "ELIGIBLE",
        "skill_match": {
          "score": 100.0,
          "required_matched": ["Python", "SQL", "Data Structures"],
          "required_missing": [],
          "preferred_matched": ["AWS", "Docker"],
          "preferred_missing": []
        },
        "readiness_score": 87,
        "readiness_level": "Strong",
        "placement_probability": 0.886,
        "reasons": [
          "All mandatory eligibility requirements satisfied",
          "Skill match: 100.0% (3/3 required skills matched)",
          "Readiness score: 87 (Strong)",
          "Model-estimated placement probability: 89%",
          "Strong overall fit - top recommendation"
        ],
        "improvement_actions": []
      }
    ],
    "eligible": [],
    "incomplete": [],
    "not_recommended": []
  }
}
```

## 10. Limitations

- Rankings are based on the **SAMPLE/DEMO** company requirements
  (Phase 13 dataset) — not official hiring criteria.
- Skill detection is limited to the Phase 12 taxonomy.
- When ML features are missing, the probability component is simply
  absent (0 weight) — the other four signals still work.
- No company-admin management, no authentication, no dashboards, no
  frontend (future phases).

## 11. Testing

- `backend/tests/test_recommendations.py` — 105 checks covering all 25
  required scenarios (strong/weak/incomplete/unverified/unknown,
  skill matching, required/preferred skill handling, eligibility
  failure, ranking, score range, readiness + ML integration,
  eligibility override, top-N limit, empty scenario, explanations,
  improvement actions, normalization reuse, and HTTP regression of
  Phases 8–13 + the new endpoint).
- All prior suites re-run in final verification.

## 12. Run it

```bash
uvicorn backend.app.main:app --reload
python backend/tests/test_recommendations.py   # 105 checks (server needed for HTTP part)
```

Flow: `POST /api/profile/from-resume` → `PUT /api/profile/{id}` →
`POST /api/profile/verify` →
`GET /api/profile/{id}/recommendations` (and `?limit=3`).
