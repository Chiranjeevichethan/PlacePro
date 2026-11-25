# Experimental V1: production form alignment

> Publication refresh (2026-11-24): current capabilities, 50 operations/45 paths,
> required artifacts and verification boundaries are summarized in the
> [reviewed release snapshot](../../backend/DEPLOYMENT.md#reviewed-release-snapshot-2026-11-24). Earlier dated results remain historical;
> no new application tests, browser acceptance or Linux/Docker success are claimed.

The production UI, API, dataset, preprocessing and model are unchanged. V1 now
reuses the existing `StudentForm` component, with a separate profile draft and
request builder. Its API accepts all 16 production-form fields on the same scales
and enforces the form's validation bounds. No salary or placement label is an input.

## Synthetic training projection

The existing 100,000-row `placepro_improved_synthetic_dataset.csv` is read only.
`placement_status` remains the target; `salary_package_lpa`, `student_id` and
`is_synthetic` are never classifier features. No new dataset or labels are generated.

| Form / API field | Synthetic training source | Handling |
|---|---|---|
| Branch / branch | branch | EEE -> EE, Mechanical -> ME, Civil -> CE |
| College Tier / college_tier | college_tier | Tier 1/2/3 -> Tier-1/2/3 |
| CGPA / cgpa | cgpa | Unchanged |
| Backlogs / backlogs | backlogs | Unchanged |
| Coding Skill / coding_skills | coding_skill_score | Divide synthetic score by 10 during training |
| DSA Score / dsa_score | None | Required and validated; excluded from inference |
| ML Knowledge / ml_knowledge | None | Required and validated; excluded from inference |
| System Design / system_design | None | Required and validated; excluded from inference |
| Projects / projects_count | projects_count | Unchanged count |
| Certifications / certifications | certifications_count | Unchanged count |
| Aptitude Score / aptitude_score | aptitude_score | Unchanged |
| Communication Skill / communication_skills | communication_skill_score | Divide synthetic score by 10 during training |
| Internships / internships | internships_count | Unchanged count |
| Hackathons / hackathons | hackathons_participated | Unchanged count |
| Open Source Contributions / open_source_contributions | None | Required and validated; excluded from inference |
| Extracurricular Activities / extracurriculars | None | Required and validated; excluded from inference |

The 11-feature classifier is retrained on this projection, using the original
stratified 80/20 split and seed 42, a StandardScaler, OneHotEncoder and Logistic
Regression. Unsupported fields cannot affect its output. Logical reasoning is
not DSA; GitHub repositories are not open-source contributions; an extracurricular
score is not an activity count. These columns are not substituted.

The 12 former V1 features removed from this classifier are `age`, `gender`,
`logical_reasoning_score`, `github_repos`, `linkedin_connections`,
`mock_interview_score`, `attendance_percentage`, `extracurricular_score`,
`leadership_score`, `volunteer_experience`, `sleep_hours`, and `study_hours_per_day`.

The synthetic coding/communication scores are semantically the same kinds of
scores, but no evidence establishes calibration against human 1-10 ratings. The
explicit division changes units only. Low scores below the synthetic training
range, CGPA below 4.5 and unusually large counts are extrapolation. Test metrics
measure fit to generated labels, not real-world placement accuracy.

The unchanged dropdown includes ISE and Chemical. Neither has training rows in
this synthetic dataset. They are accepted without mapping to CSE or another
department: OneHotEncoder's existing unknown-category handling makes all branch
indicators zero. The result notice explicitly identifies this limitation.

## Artifacts and operation

The training projection above records the historical V1 model preparation.
Training code, training data and the obsolete 23-feature artifact are excluded
from the runtime release. Do not retrain or replace an artifact as a deployment
repair. Serving requires the unchanged `placepro_v1_production_fields.pkl`, its
metadata and `feature_schema.py`; model version is
`placepro-experimental-v1-16-inputs`. Mismatched schemas are rejected.
A separately authorized offline reproducibility exercise would require approved
original inputs and training code; no such run is performed by these instructions.

Profile prefill copies matching saved values in production units, including
explicitly supplied ML scores and counts. Named internship/project/certification
records and listed hackathons supply their structural counts. Missing scores
stay empty; age, gender, attendance, social counts and habits no longer appear.
Current-session manual edits, including blanks, override refreshed saved values.

## Verification

- Frontend: 423 Node tests passed; ESLint and Vite production build passed.
- Backend: 51 V1 tests passed. The broader V1, prediction ownership, profile
  ownership, resume update and extraction run had 288 passes and one existing
  historical failure in `test_owned_router_standalone_does_not_provide_an_authentication_bypass`.
  It expects the separate V1 path on a standalone production analytics router
  (401 expected, 404 returned). The same failure was reproduced with the original
  V1 schema/service loaded from the starting snapshot in a disposable test process.
  That obsolete test expectation was later corrected in the approved test-only
  cleanup: production-router 401 coverage and full-application V1 security remain.
  Routers and application behavior were not changed by that correction.
- Historical browser record (not current release acceptance): real security and isolated storage, resume confirmation/persistence,
  latest prefill, manual edits and blanks, navigation/reload, 10 validation cases
  on both forms, and equal labels/options/CSS geometry at widths 1280, 900 and 390.
  Both production and V1 inference returned 200; no page errors occurred.
- Existing-file hash audit: production form, prediction page, defaults, profile
  mapping, CSS, application wiring, API route, security, preprocessing, model
  artifacts and datasets are unchanged. `api.js` changes are confined to a V1
  helper import and its existing experimental request block.

The production build reports the existing bundle-size warning. Backend model
loading reports joblib's NumPy shape deprecation warning. Neither prevented checks.
All browser mutations used disposable fictional profiles and an isolated API;
the operator's running backend was not restarted or used for test writes.
