# Phase 13 — Company Eligibility Engine

> Built on the Phase 8 → Phase 12 architecture. No previous phase was
> rebuilt, no model was retrained or modified, and the Phase 8
> prediction pipeline is untouched.

## 1. What this phase adds

A transparent **company eligibility engine** that answers two questions:

1. *Is this verified student eligible for this company?*
2. *Why — or why not?* (requirements satisfied / not satisfied /
   missing information / reasons / optional improvement actions)

| Endpoint | Purpose |
|----------|---------|
| `GET /api/companies` | List active demo companies |
| `GET /api/companies/{company_id}` | One company's requirements |
| `GET /api/profile/{profile_id}/eligibility/{company_id}` | Eligibility of a verified profile for one company |
| `GET /api/profile/{profile_id}/eligibility` | Eligibility against all active companies, grouped by status |

## 2. Company data model

All company data lives in **one configured server-side module**
(`backend/app/data/companies.py`). Routes never hard-code company
logic and clients can never modify requirements or supply company
files.

```
company_id, company_name, industry, roles, active
requirements:
  min_cgpa, max_backlogs, allowed_branches,
  allowed_graduation_years, required_skills, preferred_skills,
  min_internships, min_projects, min_certifications,
  min_aptitude_score
```

Any requirement field may be absent — absent fields are simply not
evaluated.

### Demo companies (SAMPLE / DEMO only)

7 active demo companies + 1 inactive example (`ArchiveTech`,
excluded everywhere — it demonstrates the `active` flag):

| id | name | highlights |
|----|------|------------|
| company_001 | DemoTech | CGPA 7.5, 0 backlogs, CSE/IT/ECE, Python+SQL+DS, 1 internship, 2 projects, aptitude 60 |
| company_002 | FinTech Solutions | CGPA 8.0, Java+SQL+OOP, aptitude 70 |
| company_003 | CloudWorks | AWS+Linux+Python, ≥1 certification |
| company_004 | DataSystems | Python+SQL+ML, 2 projects |
| company_005 | WebTech | JavaScript+HTML+CSS, all branches |
| company_006 | AI Solutions | Python+ML+DS, 3 projects, 1 cert, aptitude 70 |
| company_007 | InnovateLabs | Python+Git+Communication, 1 internship |

**These are clearly labeled DEMO requirements** (`industry` shows
"DEMO requirements"). They are NOT official hiring criteria for any
real company — real requirements must be supplied by an authorized
placement/admin user in a future phase.

## 3. Requirement types (PASS / FAIL / UNKNOWN)

Every requirement is evaluated to exactly one of:

| Status | Meaning |
|--------|---------|
| PASS | The verified value satisfies the requirement |
| FAIL | The verified value does **not** satisfy the requirement |
| UNKNOWN | The required information is **missing** — never treated as failure |

| Type | Example | UNKNOWN when |
|------|---------|--------------|
| CGPA | `min_cgpa = 7.5` | cgpa not provided |
| Backlogs | `max_backlogs = 0` | backlogs not provided |
| Branch | `allowed_branches = [CSE, IT, ECE]` | branch not provided |
| Graduation year | `allowed_graduation_years = [2026, 2027]` | year not provided |
| Internships / projects / certifications | `min_projects = 2` | (counts always come from verified lists) |
| Required skills | `required_skills = [Python, SQL]` | skill not found in verified profile |
| Aptitude | `min_aptitude_score = 60` | aptitude not provided |

A missing required skill is reported as **"not found in the verified
profile"** with the action *"Add verified evidence of {skill}
knowledge or complete the relevant assessment"* — never as "the
student does not know X".

## 4. Eligibility states

| Status | Rule |
|--------|------|
| `ELIGIBLE` | all mandatory requirements PASS |
| `NOT_ELIGIBLE` | one or more mandatory requirements FAIL |
| `INCOMPLETE` | no mandatory FAIL, but ≥1 mandatory UNKNOWN |

`UNKNOWN` is **never** silently classified as `NOT_ELIGIBLE`: the
engine never tells a student "you are not eligible" when the real
problem is "we don't have your CGPA".

## 5. Required vs preferred skills

- **Required skills** are mandatory — a missing one blocks eligibility
  (as UNKNOWN → INCOMPLETE).
- **Preferred skills** are optional — a missing preferred skill is
  reported as UNKNOWN with `mandatory: false` and **never** blocks
  eligibility.

## 6. Eligibility is NOT the ML probability

Eligibility is driven **only** by the configured company requirements.
The Phase 8 placement probability is never consulted for eligibility —
the two systems are completely separate (the response contains no
`placement_probability` field).

## 7. Response format

```json
{
  "company_id": "company_001",
  "company_name": "DemoTech",
  "status": "INCOMPLETE",
  "requirements": {
    "passed": [
      { "requirement": "Minimum CGPA", "student_value": 8.2,
        "required_value": 7.5, "status": "PASS", "mandatory": true,
        "explanation": "CGPA meets the minimum requirement." }
    ],
    "failed": [],
    "unknown": [
      { "requirement": "Required skill: Data Structures",
        "student_value": null, "required_value": "Data Structures",
        "status": "UNKNOWN", "mandatory": true,
        "explanation": "Required skill 'Data Structures' was not found in the verified profile.",
        "action": "Add verified evidence of Data Structures knowledge or complete the relevant assessment." }
    ]
  },
  "missing_information": ["Data Structures"],
  "explanation": [
    "Eligibility cannot be confirmed because the following required information is missing: Required skill: Data Structures.",
    "Required skill 'Data Structures' was not found in the verified profile."
  ]
}
```

Explanations are human-readable:
- ELIGIBLE: *"Your CGPA, branch, internship count, project count and
  required skills satisfy all mandatory DemoTech requirements."*
- NOT_ELIGIBLE: *"Your CGPA is 6.8, while the minimum requirement is
  7.5."*
- INCOMPLETE: *"Eligibility cannot be confirmed because the following
  required information is missing: Minimum CGPA, Allowed Branch, …"*

## 8. Reuse (no duplicate implementations)

- **Skill normalization + verified skills** come from Phase 12
  (`readiness_service.collect_verified_skills` + the taxonomy) —
  a resume that says "ReactJS" normalizes to "React", so a company
  requirement of "React" PASSes.
- **cgpa / branch / counts / backlogs / aptitude** come from the
  Phase 10 ML-feature mapping (single source of truth) — the same
  values the Phase 8 model uses.

## 9. Security

- Company requirements come **only** from the configured server-side
  dataset — clients cannot modify them or supply company files.
- No filesystem paths are exposed; company IDs are matched against
  the configured dataset (unknown → 404).
- Profile IDs are validated as before (letters/digits/`-`/`_` only;
  unknown → 404); unverified profiles → 422.
- The trained model and Phase 8 pipeline are untouched.

## 10. Limitations (honest)

- Demo company requirements are **SAMPLE data** — not official
  criteria for any real company (real requirements need an authorized
  placement/admin source, future phase).
- Skill detection is limited to the Phase 12 taxonomy.
- `allowed_branches` uses the dataset branch values (CSE, IT, ECE,
  EE, ME, CE, Chemical); a branch with no documented synonym is
  UNKNOWN.
- No company recommendation, skill-gap-to-company matching, or
  eligibility history yet (later phases).
- No authentication yet (later phase).

## 11. Testing

- `backend/tests/test_eligibility.py` — 74 checks covering all 21
  required scenarios (eligible, CGPA/backlog/branch failures, missing
  CGPA/branch/skill, required-skill honesty, preferred-skill
  non-blocking, multiple failures/unknowns, unknown company/profile,
  unverified profile, all-company eligibility, skill normalization,
  and HTTP regression of Phase 8/9/10/11/12 + the new endpoints).
- All prior suites re-run in final verification.

## 12. Run it

```bash
uvicorn backend.app.main:app --reload
python backend/tests/test_eligibility.py     # 74 checks (server needed for HTTP part)
```

Flow: `POST /api/profile/from-resume` → `PUT /api/profile/{id}` →
`POST /api/profile/verify` → `GET /api/profile/{id}/eligibility` →
`GET /api/profile/{id}/eligibility/{company_id}`.
