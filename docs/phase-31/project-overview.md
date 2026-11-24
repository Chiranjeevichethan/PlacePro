# PlacePro — project explanation for presentation and viva

> Publication refresh (2026-11-24): current capabilities, 50 operations/45 paths,
> required artifacts and verification boundaries are summarized in the
> [reviewed release snapshot](../../backend/DEPLOYMENT.md#reviewed-release-snapshot-2026-11-24). Earlier dated results remain historical;
> no new application tests, browser acceptance or Linux/Docker success are claimed.

Prepared 2026-11-09 for a final-year Information Science and Engineering project.
This guide explains the current working tree, not a clean checkout of historical
HEAD. Application code, models, datasets, authentication and student records were
not changed during Phase31. See [architecture](system-architecture.md),
[presentation](presentation-outline.md), [demo](live-demo-script.md),
[viva practice](viva-questions-and-answers.md) and [limitations](limitations-and-future-scope.md).

## Evidence language to use throughout

| Label | Meaning in this preparation package |
| --- | --- |
| Verified implementation | Confirmed from current source, served model objects, dataset structure or route inventory during this audit. |
| Synthetic demonstration | Newly provisioned fictional student accounts/profiles in isolated temporary storage; model calculations on these inputs are estimates, not placement outcomes. |
| User-reported manual rehearsal | The project owner reports that the main workflows appeared to work across all three synthetic accounts. No assertion count, screenshot set or complete scenario record was supplied. |
| Historical automated evidence | Phase30 recorded 1,125 backend tests, 195 frontend tests, 54 HTTP assertions and passing lint/build. Phase29 recorded 40 Chromium assertions. These suites were not rerun in Phase31. |
| Unavailable/future | Clearly identified functions that cannot be demonstrated as current capabilities. |

The manual rehearsal adds useful observed evidence; it does not rewrite the earlier
Phase30 report that automated browser/visual execution was blocked.

## 1. Introduction

**Project title:** PlacePro — AI-Based Student Placement Prediction and Recommendation System.

**Suggested opening:** “PlacePro brings a student's profile, placement estimate,
salary estimate, preparation gaps, company eligibility and practice assessments
into one authenticated application. It combines two production machine-learning models, a separate synthetic Experimental V1 model, and
explainable rules. Today we demonstrate fictional students in an isolated local environment.”

The product supports a student preparation workflow. It is not a placement guarantee,
an employer application portal, or a deployed placement-cell decision system.

## 2. Problem statement

Placement preparation involves academic information, technical skills, projects,
internships, resumes, eligibility requirements and practice results. When these
are handled separately, a student can struggle to identify missing information,
choose the next preparation task and track progress consistently.

The engineering problem is to combine this information into one understandable
workflow while keeping every account's student data separate. This is the project's
problem framing; no market survey or measured prevalence study is claimed.

## 3. Motivation

The application aims to turn scattered inputs into useful guidance: a model estimate,
an explanation of missing evidence, company requirement checks and assessment history.
It also addresses a practical software issue: a student must not gain access to
another student's profile by knowing its ID.

Say “help students prepare and understand their information,” rather than “prove
exact placement chances” or “replace recruitment decisions.”

## 4. Objectives

1. Maintain student profiles with resume extraction and explicit review.
2. Calculate placement probability and an annual salary estimate using saved models.
3. Explain readiness, strengths and skill gaps using transparent evidence rules.
4. Compare profiles with company requirements and rank eligible matches.
5. Provide server-scored mock assessments and private performance history.
6. Authenticate accounts and enforce server-side profile/resource ownership.
7. Present these features in a shared React dashboard without stale cross-profile data.

Real self-service activation, recovery, OCR and public deployment are future work.

## 5. Existing system and limitations

Use a conceptual baseline: manual spreadsheets, isolated calculators, separate
resume reviews and independent practice tests. Such a fragmented workflow requires
repeated entry and makes consistent progress tracking difficult.

Do not claim that every commercial platform lacks these functions. No formal
competitor benchmark, interview study or quantitative improvement experiment exists
in this preparation audit. The comparison explains the design motivation.

## 6. Proposed system

PlacePro combines a browser interface, a FastAPI server, local storage and saved
scikit-learn pipelines. The server validates requests, authorizes private resources
and supplies results. The browser displays them; it does not invent scores or decide ownership.

The proposed workflow is implemented for authenticated local accounts. Its demo
provisions synthetic fixture accounts because public account activation is unavailable.

## 7. Complete system architecture

Think of three responsibilities:

- **Presentation:** React pages collect inputs and show results.
- **Application:** FastAPI services apply security, validation, inference and domain rules.
- **Persistence/inference:** SQLite and JSON retain authorized records; saved model files provide inference.

“Three responsibilities” describes separation of concerns, not three independently
deployed cloud tiers. Current deployment is one local development machine. The
[architecture diagrams](system-architecture.md) show actual storage boundaries.

## 8. Frontend architecture

The frontend uses React 19, JavaScript/JSX, CSS and Vite. `App.jsx` switches pages
through the existing URL mapping/History API and state; no routing library is installed.
Pages also include Experimental V1, Career Readiness, Goals, Notifications and
Resume Builder alongside Dashboard, Profile, placement/salary, companies, mock
tests and performance views.

A React context shares the selected profile. Account/profile changes remount the
workspace and invalidate older asynchronous responses, form drafts and results.
The API transport sends cookie credentials and CSRF headers where required.
Authentication/CSRF secrets stay out of localStorage; limited account-scoped
sessionStorage references/draft answers are not authorization.

## 9. Backend architecture

The backend uses FastAPI, Pydantic schemas, Uvicorn and Python service modules.
Routes are the HTTP entry points. Schemas validate structure/types/ranges. Services
implement profiles, resume processing, assessments, predictions and analytics.

A default-private gate authenticates private requests and enforces Origin/CSRF.
The production app installs owned-profile, owned-assessment, owned-analytics, owned-goals, owned-resume-builder
and authentication/OAuth routers, plus the separate Experimental V1 route. Older domain routes remain in source for guarded isolated regressions;
their existence does not mean they are unrestricted public endpoints.

The current application registers **50 operations across 45 paths**. Generated
development documentation routes are separate from this application-operation count.

## 10. Database and storage

PlacePro uses two types of local storage:

- A dedicated authentication SQLite database contains accounts, sessions, login
  challenges and authoritative profile ownership associations.
- A separate company SQLite database stores company records and versioned requirements.
- Profile JSON files retain structured student information, revisions, provenance
  and histories/evidence. Assessment JSON files retain session/lifecycle data.

One account can own several profiles. Each profile has at most one account owner.
Ownership is not inferred from email, browser state or a secret-looking UUID.
SQLite/JSON cross-store operations cannot share one atomic transaction; staged
creation, local locks and recoverable writes mitigate this within documented limits.

## 11. Machine-learning workflow

**Training** learns model parameters from labelled examples. **Inference** uses
already learned parameters for a new input. Normal PlacePro requests perform
inference; they do not train models.

The available root `placement.csv` and `salary_model/placement.csv` are byte-identical:
100,000 rows, 26 columns, with 54,459 `Placed` and 45,541 `Not Placed` labels. This
is a dataset row count, not a user count. The data is historically described as
synthetic; its original source/generator is unavailable.

The final placement artifact accepts a different 16-feature contract. Its cited
`data/placement_phase6.csv` and training entry point `phase8_final_pipeline.py` are
absent. The available CSV therefore cannot be asserted to reproduce that model.
Historical salary-source inspection selected placed rows. Training code and
CSV rows are excluded from the runtime release; aggregate-only provenance is
retained in the test summary. Complete original-run reproduction is not established.

## 12. Placement prediction

The served artifact is `models/placepro_final_model.pkl`, version `placepro-final-v1`:
feature engineering → preprocessing → **Logistic Regression**.

Sixteen raw inputs include branch, college tier, CGPA, backlogs, skill scores and
experience/activity counts. Ten deterministic derived features include overall
skill score, experience score and interactions. Numeric features use median
imputation and standardization; categorical features use most-frequent imputation
and one-hot encoding.

The API returns the placed-class probability, the estimator's class label, class
confidence `max(p, 1-p)` and a version string. The current binary estimator has
classes `[0,1]`; its ordinary decision is at approximately 0.5. The wrapper calls
the estimator's `predict`, not a separate user-adjustable threshold.

An illustrative 0.70 probability means “the model assigns 0.70 to its placed class.”
It does not establish a calibrated 70% real-world chance. Class confidence is not
accuracy. No verified final placement-model accuracy is established here.

Independent form calculations are authenticated and stateless. The separate
owned-profile prediction action saves account/profile/revision-bound history.

## 13. Salary prediction

The served artifact is `models/placepro_salary_model_v2.pkl`, version `placepro-salary-v2`:
preprocessing → **Ridge regression**, with alpha 1.0. It estimates annual salary
in lakhs per annum, conditional on placement.

The service maps shared form fields to 12 trained inputs. DSA, ML knowledge, system
design and open-source contributions are not inputs to this salary model even
though they appear in the broader shared form contract. Coding/communication scores
are converted to the salary dataset's scale; extracurricular-count mapping is provisional.
Missing tier has a documented Tier 2 fallback. Known profile tier is retained.

Numeric inputs are clipped to configured observed feature ranges. This reduces
input extrapolation; it does not mathematically guarantee an output within the
observed salary-target range. There is no individual confidence interval, guaranteed
offer or salary-history endpoint. Dashboard salary preview is stateless too.

## 14. Readiness and skill-gap analysis

Readiness is a **rule-based preparation score**, not the placement probability.
Maximum component points are technical skills 30, projects 20, internships 15,
certifications 8, communication 7 and profile completeness 20. Qualifying latest
assessment evidence can contribute a capped bonus of up to 5 within the existing
30-point technical cap.

Skill gaps compare available, accepted profile/assessment evidence with canonical
requirements. “Evidence missing” is different from “the student cannot do this.”
Student confirmation verifies reviewed claims in the application's workflow; it
does not independently certify real-world competence. Learning resources are a
static curated frontend catalogue.

## 15. Company recommendations

Eligibility first evaluates mandatory requirements as PASS, FAIL or UNKNOWN.
The combined result is ELIGIBLE, NOT_ELIGIBLE or INCOMPLETE. Missing evidence
does not automatically become failure; preferred skills do not block eligibility.

Recommendation ranking combines eligibility 30 points, skill match 25, readiness
20, placement probability 15 and completeness 10. Required/preferred matches use
75%/25% within the skill-match component. A mandatory failure prevents a
RECOMMENDED status; eligible score at least 75 becomes RECOMMENDED.

This is an explainable weighted heuristic, not a third trained ML model or hiring
probability. Current company requirements are explicitly DEMO/sample data.

## 16. Assessments and performance analytics

The server selects randomized practice questions and controls deadlines. The UI
offers 5, 10 or 25 questions; one minute per selected question sets the server limit.
Difficulty-weighted correct points produce a 0–100 score. A score of at least 60
can satisfy assessment evidence policy; it is not proof of professional mastery.

Three completed-or-active attempts per profile/skill are allowed, with 24-hour
cooldown after scored completion. Expired reservations release quota without
erasing attempt records. Accepted submissions pass through SUBMITTING so evidence
and completion can be recovered without duplicate credit. Completed duplicates
retain 409 behavior; expired owned sessions retain 410.

Performance views combine private assessment/prediction history, readiness and
source-revision freshness. A stale prediction remains a historical estimate, not
the current profile's prediction.

## 17. Authentication and student data isolation

Passwords use Argon2id hashes. Login produces an opaque HttpOnly session cookie;
the authentication database stores the session secret's hash. Private write and
lifecycle requests require session-bound CSRF plus permitted Origin. Production
mode requires HTTPS; local demo mode is explicitly restricted to loopback.

The server checks ACTIVE account/profile ownership and assessment/prediction
bindings before protected effects. Foreign, missing and legacy-unowned targets
receive non-disclosing responses. Account-scoped retry identities cannot replace
these checks. Legacy profiles are never automatically claimed by matching email.

Public registration remains unavailable (503) while activation is unfinished.
The demo creates three new fixture accounts in its own new database; it does not
activate historical students or introduce a web authentication exception.

## 18. Complete end-to-end workflow

Sign in → choose/create an owned profile → extract/review a readable PDF/DOCX →
complete missing academic/ML inputs → confirm → inspect dashboard → calculate
placement/salary → optionally save an owned placement prediction → inspect
readiness/gaps/company reasons → take an assessment → inspect score/history/
performance → safely switch profile/account → log out.

Your viva explanation should keep five quantities separate: placement probability,
model class confidence, salary estimate, readiness score and assessment score.
Different inputs, algorithms and evidence support each quantity.
