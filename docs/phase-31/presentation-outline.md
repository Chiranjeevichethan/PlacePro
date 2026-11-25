# PlacePro — final-year presentation outline

> Publication refresh (2026-11-24): current capabilities, 50 operations/45 paths,
> required artifacts and verification boundaries are summarized in the
> [reviewed release snapshot](../../backend/DEPLOYMENT.md#reviewed-release-snapshot-2026-11-24). Earlier dated results remain historical;
> no new application tests, browser acceptance or Linux/Docker success are claimed.

Audience: Information Science and Engineering faculty/external examiners.
Suggested format: **18 slides, approximately 13 minutes 20 seconds**, followed by
the **10–12 minute synthetic live demonstration** and questions. Confirm the
college's allotted time before producing slides. This is an outline/speaker guide,
not a generated PowerPoint, completed screenshot set or new experiment report.

Use the existing PlacePro identity, one readable font family, short bullets and
consistent diagram colours. Put source/evidence limitations in speaker notes or
small readable footnotes. Take screenshots manually from the isolated synthetic
demo; exclude passwords, cookies, developer tools and historical student records.
Diagrams can be taken from [system architecture](system-architecture.md).

### Slide 1 — PlacePro: student placement preparation in one platform

**Time:** 20 seconds.

**Exact slide points:**

- AI-Based Student Placement Prediction and Recommendation System.
- Final-year Information Science and Engineering project.
- [Student names and USNs], [guide], [college], [academic year].
- “Local demonstration uses synthetic student data.”

**Visual:** Existing PlacePro logo and one synthetic dashboard screenshot.

**Say:** “PlacePro combines student information, model estimates and preparation
guidance in one authenticated application. Our demonstration uses fictional profiles.”

### Slide 2 — Problem: fragmented placement preparation

**Time:** 45 seconds.

**Exact slide points:**

- Academic, skill, resume and practice information is often handled separately.
- Students need understandable preparation gaps and progress tracking.
- Eligibility depends on company-specific requirements.
- Student information must remain private across accounts.

**Visual:** Four boxes—resume, profile, company requirements, practice tests—leading
to an unconnected student workflow. This is a conceptual problem diagram.

**Say:** “The project addresses integration and clarity. We are not claiming a
measured survey result or that every commercial placement platform lacks these functions.”

### Slide 3 — Objectives

**Time:** 35 seconds.

**Exact slide points:**

- Create and review structured student profiles.
- Estimate placement probability and annual salary.
- Explain readiness, skill gaps and company matches.
- Track practice assessments and performance.
- Enforce authenticated account/profile data isolation.

**Visual:** Five objective icons from the existing design, or five simple labelled boxes.

**Say:** “Prediction is one part of the system. Our engineering contribution also
includes the complete workflow, evidence handling, revisions and private data access.”

### Slide 4 — Existing approach and proposed workflow

**Time:** 35 seconds.

**Exact slide points:**

- Conceptual baseline: spreadsheets, separate calculators and independent tests.
- Proposed: one profile shared across preparation features.
- Backend-generated results with clear explanations.
- Consistent private history and profile switching.

**Visual:** Two-column comparison. Label the baseline “conceptual,” not “competitor benchmark.”

**Say:** “We reduce repeated entry and connect preparation activities. This is a
design comparison, not an experimentally measured productivity improvement.”

### Slide 5 — Technology stack

**Time:** 35 seconds.

**Exact slide points:**

- React 19, JavaScript/JSX, CSS and Vite.
- Python, FastAPI, Pydantic and Uvicorn.
- scikit-learn, pandas, NumPy and joblib.
- SQLite for authentication/company data; JSON for profile/assessment records.
- pypdf and python-docx for readable resume extraction.

**Visual:** Frontend → backend → storage/model stack diagram.

**Say:** “React manages presentation; FastAPI validates and serves requests;
scikit-learn loads saved estimators. There is no dependency on a cloud AI service.”

### Slide 6 — Complete system architecture

**Time:** 70 seconds.

**Exact slide points:**

- Browser → cookie/CSRF transport → FastAPI private gate.
- Owned profile, assessment and analytics services.
- Separate authentication SQLite, company SQLite and JSON stores.
- Two saved ML pipelines plus rule-based analysis.

**Visual:** Main component diagram in [system-architecture.md](system-architecture.md).

**Say:** “The server authenticates the request before it authorizes the student
resource. Saved model inference and rule-based analytics then operate on permitted
inputs. This is a modular local application, not a claimed cloud microservice system.”

### Slide 7 — Profile, resume and storage integrity

**Time:** 50 seconds.

**Exact slide points:**

- PDF/DOCX → text extraction → structured claims → student review.
- Missing numeric skill inputs require explicit entry.
- Server-generated profile IDs; one account owns multiple profiles.
- Revisions prevent stale edits; provenance separates claims and assessment evidence.

**Visual:** Resume/profile workflow and account-to-profile relationship diagram.

**Say:** “Mentioning Python in a resume does not establish a numeric coding score.
Confirmation records reviewed claims; it does not independently certify competence.”

### Slide 8 — Dataset and evidence boundaries

**Time:** 65 seconds.

**Exact slide points:**

- Available CSV: 100,000 rows, 26 columns; root and salary copies are identical.
- Available labels: 54,459 Placed and 45,541 Not Placed.
- Historically described as synthetic; source/generator not verified.
- Final placement training dataset/run is missing.
- Dataset rows are not registered users or verified recruitment outcomes.

**Visual:** A schema/count table, not a real-student sample. Clearly separate
“available dataset” from “final placement model's unverified training lineage.”

**Say:** “We can verify the files and schema we have. We cannot claim a Kaggle
source, real placement-cell outcomes, or that this CSV reproduces the final classifier.”

### Slide 9 — Placement prediction pipeline

**Time:** 50 seconds.

**Exact slide points:**

- 16 raw features and 10 deterministic derived features.
- Numeric imputation/scaling; categorical imputation/one-hot encoding.
- Served estimator: Logistic Regression.
- Outputs: placed probability, class, class confidence and model version.
- Confidence is `max(p, 1-p)`, not accuracy.
- Experimental V1 is separate: 16 validated form inputs, 11 supported synthetic
  inference features and no claim of real-world placement accuracy.

**Visual:** Input → feature engineering → preprocessing → classifier → response.

**Say:** “Inference applies the saved transformations and learned coefficients.
The probability is a model estimate; no verified final placement accuracy or
real-world probability calibration is claimed.”

### Slide 10 — Salary estimation

**Time:** 45 seconds.

**Exact slide points:**

- Served estimator: Ridge regression; 12 model inputs.
- Estimated annual salary in LPA, conditional on placement.
- Explicit branch/tier/score mapping and feature-range guards.
- Provisional activity mapping; no individual confidence interval.
- Stateless calculation; no salary-history API.

**Visual:** Synthetic salary result with the existing qualification text visible.

**Say:** “Ridge penalizes very large coefficients. The estimate is not an offer.
The shared form contains some fields the salary model does not use; input clipping
also does not guarantee a target-range output.”

### Slide 11 — Readiness and skill gaps

**Time:** 45 seconds.

**Exact slide points:**

- Transparent rule-based score separate from ML probability.
- Weights: technical 30, projects 20, internships 15, certifications 8,
  communication 7, completeness 20.
- Latest qualifying assessment evidence can strengthen the technical component.
- Missing evidence is not proof of inability.

**Visual:** Readiness breakdown and one actionable synthetic skill gap.

**Say:** “The weights describe our preparation policy, not learned model accuracy.
The assessment bonus stays within the technical cap and cannot grow through unlimited retries.”

### Slide 12 — Eligibility and recommendations

**Time:** 40 seconds.

**Exact slide points:**

- Mandatory requirements: PASS, FAIL or UNKNOWN.
- Overall status: ELIGIBLE, NOT_ELIGIBLE or INCOMPLETE.
- Weighted ranking: eligibility 30, skill match 25, readiness 20,
  probability 15, completeness 10.
- Mandatory failure overrides recommendation status.
- Current company criteria are DEMO/sample data.

**Visual:** Company card with reasons and missing information expanded.

**Say:** “Eligibility checks requirements; ranking helps order matches. Neither
is a hiring guarantee or a trained recommendation model.”

### Slide 13 — Assessments and performance

**Time:** 50 seconds.

**Exact slide points:**

- Randomized practice questions; server-controlled deadlines.
- Difficulty-weighted scoring and private result/history.
- Three completed-or-active slots per skill/profile; 24-hour cooldown.
- Recoverable submission and duplicate-evidence protection.
- Prediction freshness and assessment progress in performance analytics.

**Visual:** IN_PROGRESS → SUBMITTING → COMPLETED, with EXPIRED alternative;
synthetic assessment result/history screenshot.

**Say:** “Cooldown and retake are policies, not extra stored status strings.
The assessment measures question-bank performance, not guaranteed real-world expertise.”

### Slide 14 — Authentication and student isolation

**Time:** 55 seconds.

**Exact slide points:**

- Argon2id password hashing and opaque HttpOnly session cookies.
- CSRF plus allowed Origin; HTTPS required in production mode.
- ACTIVE server-side profile ownership and bound assessment/prediction records.
- Non-disclosing foreign/missing responses; legacy profiles are unclaimed.
- Account-bound retry identity and revision validation.

**Visual:** Account A/B separation plus authorization-before-operation sequence.

**Say:** “Authentication identifies the account. Authorization decides which profile
and record it may access. UUIDs and frontend hiding are not authorization.”

### Slide 15 — Frontend student experience

**Time:** 50 seconds.

**Exact slide points:**

- Session restoration and logout.
- Shared owned profile selection and safe switching.
- Dashboard probability, salary preview, readiness, companies and history.
- Resume completion guidance; explicit empty/loading/error states.
- Late responses cannot populate a different account/profile workspace.

**Visual:** Two or three synthetic screenshots: dashboard, incomplete resume
profile guidance and profile selector. No credentials or developer tools.

**Say:** “React Context shares the selected profile. The workspace and asynchronous
results are tied to account/profile/revision, so switching does not carry old results forward.”

### Slide 16 — Validation evidence

**Time:** 40 seconds.

**Exact slide points:**

- Recorded Phase30: 1,125 backend tests and 195 frontend tests passed.
- Recorded Phase30: 54 real HTTP assertions; lint/build passed.
- Recorded Phase29: 40 Chromium assertions.
- Owner reports manual rehearsal across three synthetic accounts.
- Phase31 is a source/documentation audit; suites were not rerun.

**Visual:** Evidence table with date/phase labels. Use “tests passed,” not “accuracy.”

**Say:** “These validate specified software behaviours, not ML generalization or
security certification. Manual rehearsal is reported observation without an invented assertion count.”

### Slide 17 — Limitations and future scope

**Time:** 35 seconds.

**Exact slide points:**

- Activation/recovery and OCR unavailable; Google OAuth is implemented but requires configured provider/hosting acceptance.
- Company criteria are sample data; final placement training provenance incomplete.
- No guaranteed outcomes or independently verified placement accuracy.
- Local SQLite/JSON architecture has concurrency/crash/deployment limits.
- Future: approved data, reproducible ML evaluation and production onboarding/deployment review.

**Visual:** Three columns—available now, unavailable, future—with no roadmap dates invented.

**Say:** “The local demo is functional within these boundaries. Future work needs
approved data and engineering decisions; it was not implemented during Phase31.”

### Slide 18 — Conclusion and live demonstration

**Time:** 35 seconds.

**Exact slide points:**

- Integrated student preparation workflow.
- Two production models, separate synthetic Experimental V1, and explainable domain rules.
- Authenticated, owned, revision-aware student data.
- Synthetic local demonstration follows.
- Questions welcome.

**Visual:** Resume → profile → estimates/guidance → assessment → performance journey.

**Say:** “PlacePro demonstrates how prediction, preparation guidance and private
student workflows can work together. We will now show the implementation using synthetic accounts.”

## Timing and delivery checklist

The slide allocations total **800 seconds (13:20)**. If the full slot is only
15 minutes, use a condensed 8-slide talk (1, 2/3, 6, 8/9, 10/11/12, 13/14,
16/17, 18) and a shortened five-minute demo. Keep dataset/metric limitations
visible even when shortening; do not rush through every form field.

Before the final presentation:

- Replace identity/college/guide placeholders with confirmed information.
- Collect real screenshots only from a fresh isolated synthetic demo.
- Keep probability, confidence, salary, readiness and assessment scores distinct.
- Rehearse the [live-demo script](live-demo-script.md) and record the actual elapsed time.
- Prepare two backup slides: storage/retry recovery and dataset/evaluation provenance.
- Quote no placement accuracy or company hiring claim unsupported by evidence.
- Keep the demo terminal accessible for diagnosis, with password input hidden.
- Practise the [viva answers](viva-questions-and-answers.md) in your own words.
