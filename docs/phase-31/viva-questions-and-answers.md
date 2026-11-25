# PlacePro — viva questions and answers

> Publication refresh (2026-11-24): current capabilities, 50 operations/45 paths,
> required artifacts and verification boundaries are summarized in the
> [reviewed release snapshot](../../backend/DEPLOYMENT.md#reviewed-release-snapshot-2026-11-24). Earlier dated results remain historical;
> no new application tests, browser acceptance or Linux/Docker success are claimed.

Prepared 2026-11-09 against the current working tree. These **70 questions** cover
ten topics, with an examiner-style follow-up for each. Practise explaining the
idea, then connect it to PlacePro. Do not memorize unsupported accuracy or data-source claims.

“Verified” refers to this source/artifact/documentation audit. Test counts below
are historical evidence, not newly executed Phase31 tests. The owner's manual
rehearsal is reported observation. All demonstration students are synthetic.
See the [overview](project-overview.md), [architecture](system-architecture.md)
and [limitations](limitations-and-future-scope.md) for the supporting explanations.

## Basic project questions

### 1. What is PlacePro?

**Answer:** PlacePro is an authenticated student placement preparation application.
It combines structured profiles, resume extraction, placement and salary estimates,
readiness, company requirement checks, mock assessments and private performance
history. It uses two production models and separate synthetic Experimental V1 alongside explicit preparation rules.

**Follow-up — Does it place students in jobs?** No. It supports preparation and
estimation; it does not issue job offers, submit employer applications or guarantee placement.

### 2. What problem are you solving?

**Answer:** Academic information, resumes, skills, company requirements and practice
results can be scattered across separate tools. PlacePro connects them through a
shared student profile and explains useful next steps. Keeping one account's
student records separate from another's is part of that engineering problem.

**Follow-up — How many students experience this problem?** We have no verified
survey or prevalence measurement. This is our project problem framing, not a statistical claim.

### 3. What are your main objectives?

**Answer:** Create reviewed student profiles; calculate placement and salary
estimates; explain readiness and skill gaps; check company eligibility; provide
practice assessments and performance history; and enforce authenticated, owned
access throughout stored student workflows.

**Follow-up — Is every onboarding objective complete?** No. Owned profile/resume
onboarding works for available accounts, but self-service email activation and
recovery are unavailable. The local demo uses freshly provisioned synthetic accounts.

### 4. How is the proposed system different from the existing approach?

**Answer:** Our conceptual baseline is separate spreadsheets, calculators, resume
reviews and practice tools. PlacePro uses a shared profile, consistent backend
rules and private history to connect those tasks in one interface.

**Follow-up — Is this a proven improvement over commercial products?** No
competitor benchmark or measured productivity study is available. Explain the
integration design without claiming that all other products lack it.

### 5. What is your engineering contribution?

**Answer:** The implementation integrates frontend workflows, validated APIs,
saved ML inference, evidence-aware analytics, recoverable assessment submission,
profile revisions and account/resource ownership. These are concrete system
features that can be explained from source and demonstrated locally.

**Follow-up — Which parts did you personally write?** Answer using your actual
team contribution and project history. This preparation package cannot invent
individual authorship, independent algorithm novelty or a research publication.

### 6. Describe the complete student workflow.

**Answer:** Sign in, choose or create an owned profile, extract and review a readable
resume, complete missing inputs, confirm the profile, view the dashboard, calculate
estimates, inspect gaps and company reasons, take an assessment, review history,
switch profiles/accounts safely and log out.

**Follow-up — Must an independent calculator save a profile?** No. Authenticated
placement and salary forms support independent stateless calculations. The
owned-profile placement save action is a separate persistent operation.

### 7. Is everything in PlacePro machine learning?

**Answer:** No. Placement uses Logistic Regression and salary uses Ridge regression.
Readiness, eligibility, recommendations and assessment scoring use explicit rules.
Resume extraction uses document libraries and rule-based parsing rather than an
LLM, trained NER model or OCR engine.

**Follow-up — Why retain rules?** They make requirements and evidence decisions
explainable. Calling a weighted rule score “ML accuracy” would be incorrect.

## Machine learning questions

Source anchors: [placement pipeline](../../src/pipeline.py) and
[salary inference service](../../backend/app/services/salary_prediction_service.py).
The served artifact objects were inspected; other saved experiment files are not
proof of which model the API uses.

### 8. Which model predicts placement, and how does it work?

**Answer:** The served estimator is Logistic Regression. It learns coefficients
for transformed features, combines them into a value z, and maps z to a binary
class probability through the sigmoid, p = 1 / (1 + exp(-z)). The saved pipeline
also contains feature engineering and preprocessing.

**Follow-up — Which settings are verified?** The inspected artifact has C = 0.01,
solver liblinear and maximum iterations 2000. C controls inverse regularization
strength. We cannot infer a fully documented model-selection experiment from
these settings alone.

### 9. Which model predicts salary?

**Answer:** The served salary estimator is Ridge regression with alpha = 1.0.
It fits a linear salary estimate while penalizing large coefficients using an
L2 penalty. The returned unit is annual lakhs per annum, conditional on placement.

**Follow-up — Is Ridge a classification model here?** No. It predicts a numeric
salary target. Logistic Regression predicts a binary placement class/probability.
The similar word “regression” does not make their tasks identical.

### 10. Why use separate placement and salary models?

**Answer:** Placement is classification; salary is numeric regression. Their
targets, fitted feature contracts and preprocessing differ. The salary training
source selects placed rows, so salary estimation is conditional on that setting.

**Follow-up — Does a low placement probability imply a zero salary output?**
The stateless APIs are independent calculations. The salary service does not
multiply its estimate by placement probability or convert it into expected income.

### 11. What is feature engineering in your placement pipeline?

**Answer:** It creates ten deterministic features from sixteen raw inputs:
overall skill score, academic skill index, log-scaled experience score, high-CGPA
flag, internship flag, project level, coding/experience interaction, CGPA/project
interaction, backlog flag and strong-candidate flag.

**Follow-up — Do interactions prove causation?** No. An interaction represents a
combined input pattern. It does not prove that increasing a project count causes
placement. The feature formulas are fixed rules, not a new training run.

### 12. How do you preprocess data?

**Answer:** The placement pipeline uses median imputation and StandardScaler for
numeric inputs, and most-frequent imputation with one-hot encoding for branch
and college tier. The saved salary pipeline uses numeric imputation and categorical
one-hot preprocessing; its numeric pipeline does not include StandardScaler.

**Follow-up — Why is scaling useful?** It expresses numeric features on comparable
scales, which helps regularized models. However, it would be inaccurate to claim
that both current artifacts use identical scaling.

### 13. What do placement probability, predicted class and confidence mean?

**Answer:** The wrapper uses the placed-class probability from predict_proba and
the estimator's class from predict. It reports confidence as max(p, 1-p). For an
illustrative p = 0.70, confidence is 0.70; this is not measured accuracy or a
verified 70% real-world chance for that individual.

**Follow-up — Can changing a threshold constant change the current response?**
The wrapper calls the saved estimator's predict. A separate source constant is
not used to implement the returned class. Any future configurable policy needs
an explicitly approved implementation and evaluation.

### 14. How are readiness and recommendations calculated?

**Answer:** Readiness allocates technical 30, projects 20, internships 15,
certifications 8, communication 7 and completeness 20 points. Recommendation
ranking weights eligibility 30, skill match 25, readiness 20, placement probability
15 and completeness 10. Mandatory eligibility failure overrides recommendation.

**Follow-up — Is a recommendation score of 80 an 80% hiring chance?** No. It is a
weighted heuristic score against configured sample requirements. Eligible scores
at least 75 can be labelled RECOMMENDED; this is a policy threshold, not calibration.

## Dataset and preprocessing questions

### 15. What is the dataset source?

**Answer:** Two available files, placement.csv and salary_model/placement.csv, are
byte-identical: 100,000 rows and 26 columns. Historical notes describe the data as
synthetic, but the original source or generator is not verified. We must not claim
Kaggle, placement-cell data or real recruitment outcomes.

**Follow-up — Did 100,000 students use your application?** No. Dataset rows are not
registered users. The isolated demonstration has three newly provisioned fixture accounts.

### 16. What inputs does the placement model use?

**Answer:** Its sixteen raw features are branch, college tier, CGPA, backlogs,
coding skills, DSA, aptitude, communication, ML knowledge, system design, internships,
project count, certifications, hackathons, open-source contributions and extracurriculars.
The API validates the contract before inference.

**Follow-up — Are all these columns in the available CSV?** No. The available CSV
uses a different schema. The cited final placement dataset is missing, so we
cannot assert that the available file reproduces the served classifier.

### 17. What inputs does the salary model actually use?

**Answer:** It uses ten numeric inputs—CGPA, internship/project/certification counts,
coding, aptitude and communication scores, hackathons, backlogs and extracurricular
score—and two categorical inputs, branch and college tier.

**Follow-up — Why do DSA and system-design changes not affect salary?** DSA, ML
knowledge, system design and open-source counts belong to the broader shared form
contract but are not inputs to this salary model. Shared request fields do not
imply that every estimator consumes them.

### 18. How do you prevent target leakage?

**Answer:** Placement inference selects the permitted raw inputs and excludes
student ID and salary target columns. The saved pipeline contains preprocessing.
In a sound training experiment, imputers/scalers must be fitted on training data,
and targets or post-outcome information must never become input features.

**Follow-up — Can you certify that the final training split had no leakage?**
No. Input exclusions are verified, but the exact final placement training run
is unavailable. A saved pipeline alone does not establish dataset/split provenance.

### 19. How do you handle missing values?

**Answer:** The inspected available CSV has no blank or null-like cells under the
audit's CSV check. The models still contain imputation. Separately, profile evidence
can be incomplete, and stored-profile prediction requires reviewed usable inputs
rather than inventing missing self-assessed skill scores.

**Follow-up — Does no blank cell mean excellent data quality?** No. It does not
establish accuracy, representativeness, realistic correlations or authentic outcomes.
Zero, missing evidence and an inferred default also have different meanings.

### 20. How do branch, tier and score mappings work?

**Answer:** The salary service normalizes branch/tier spellings to its trained
categories, converts shared coding/communication scales to the salary score scale,
and uses a provisional extracurricular mapping. A missing tier defaults to Tier 2;
a known supplied tier is retained.

**Follow-up — Can an unseen category fail silently?** The fitted encoders use
handle_unknown = ignore. This avoids an encoding exception but does not provide
reliable learned information for an unseen category. Do not present that as proven generalization.

### 21. What do salary feature-range guards guarantee?

**Answer:** The service clips individual numeric inputs to configured observed
feature-support bounds. This limits individual input extrapolation and preserves
supported zero values. It does not constrain the predicted salary to the observed
target range or validate unusual combinations of individually supported inputs.

**Follow-up — Can Ridge predict beyond observed salaries?** Yes. Linear regression
has no inherent target-range constraint. This corrects an overstatement in existing
service comments without altering any prediction mathematics.

## Model evaluation questions

### 22. What is the placement model's accuracy?

**Answer:** This audit establishes the served model, transformations and response,
but no verified final-artifact-linked placement accuracy. I would explain the
working inference and state that independent model evaluation and provenance
remain incomplete.

**Follow-up — Why not quote an older notebook result?** A result must be tied to
the exact artifact, dataset, split and evaluation method. Historical experiments
or a polished output card do not prove current model accuracy.

### 23. Which classification metrics would you use?

**Answer:** Accuracy measures overall correct classifications. Precision measures
how many predicted positives are correct; recall measures how many actual positives
are found; F1 balances precision and recall. A confusion matrix shows TP, FP, TN
and FN. ROC-AUC measures ranking across thresholds.

**Follow-up — Have all of these been independently measured here?** No. These are
correct evaluation concepts and future evaluation requirements, not newly obtained PlacePro results.

### 24. Which metrics evaluate salary regression?

**Answer:** MAE is average absolute salary error; RMSE gives larger errors more
weight; R² compares squared error with a mean-target baseline. MAE/RMSE use LPA
when the salary target uses LPA; R² is dimensionless and can be negative.

**Follow-up — Are any salary figures recorded?** The historical salary-evaluation summary reports
MAE 0.797784 LPA, RMSE 0.998541 LPA and R² 0.606406 on 10,892 rows in a historical
reconstructed split evaluation dated 2026-11-06. These were not rerun in Phase31
and are not an independent real-world holdout or fully provenance-linked original training report.

### 25. What is overfitting, and how would you check it?

**Answer:** Overfitting means learning patterns specific to the training data that
do not generalize. Compare training and held-out performance, use appropriate
cross-validation, and consider regularization. Placement's C and salary's alpha
are regularization settings, not proof that overfitting is absent.

**Follow-up — Does 100,000 rows remove this risk?** No. Synthetic or correlated
records can still provide a misleading evaluation regardless of row count.

### 26. What is your train/test split?

**Answer:** The available salary training source selects placed rows and uses an
80/20 split with random_state 42. It compares Ridge, Random Forest, Gradient
Boosting and Extra Trees using MAE. The exact final placement split cannot be
verified because its referenced training files are missing.

**Follow-up — Can you reproduce both final models today?** No such claim is
supported. Reading the salary source does not establish complete original-run
provenance. Running it would write a model artifact and is prohibited in this phase.

### 27. What is probability calibration?

**Answer:** Calibration asks whether predictions near 0.70 correspond to roughly
70% positives over an appropriate observed population. Reliability plots and
Brier score can help evaluate it. A valid predict_proba value is not itself proof
of real-world calibration.

**Follow-up — Is class confidence an uncertainty interval?** No. PlacePro's
max(p, 1-p) is a derived class score. The salary API also provides no individual
prediction interval.

### 28. What about bias and real-world validity?

**Answer:** Branch, tier, self-reported inputs and unknown data-generation choices
can introduce bias. Responsible deployment would need consented representative
data, subgroup/error analysis, calibration, documented intended use and monitoring.
These are future requirements.

**Follow-up — Can this model decide whom a company should hire?** We have no
evidence supporting that use. Present it as preparation guidance, with limitations,
rather than an automated recruitment authority.

## Backend and API questions

### 29. Why use FastAPI, Pydantic and Uvicorn?

**Answer:** FastAPI defines the API routes and application. Pydantic validates
request/response structures. Uvicorn runs the ASGI application locally. Python
also lets the services use pandas/scikit-learn without a separate inference language.

**Follow-up — Does async support guarantee high throughput?** No. CPU-bound
inference and blocking SQLite/JSON operations have their own limits. No load-test
or cloud scalability claim was established in this audit.

### 30. How many endpoints exist, and which are public?

**Answer:** The current application has 50 method/path operations across 45 paths.
Health liveness and company catalogue/detail are public; login initiation has
specific entry security. Student operations are authenticated and stored-resource
operations require ownership. The complete inventory is in the architecture guide.

**Follow-up — Are old route files also open to students?** No. The production app
installs secured owned routers. Legacy domain routers are used only in guarded
isolated regression harnesses, not as a public alternative.

### 31. What is the authorization execution order?

**Answer:** The gate enforces transport/Origin rules, resolves a valid session and
checks required CSRF. Owned services establish ACTIVE profile and relevant record
binding, then validate revision/retry/lifecycle conditions before protected effects.
Resource acceptance can recheck session/ownership under locks.

**Follow-up — Why authorize before expiry or recovery?** These can mutate private
records or reveal state. A foreign assessment request must not expire, score,
recover or write another student's session.

### 32. Why support stateless and stored-profile predictions separately?

**Answer:** Stateless placement/salary forms calculate from authenticated supplied
inputs without profile IDs or history writes. Stored-profile prediction uses an
ACTIVE owned profile, reviewed revision and bound history/receipt. This preserves
the established form contracts while protecting persistence.

**Follow-up — Can an independent calculation retrieve another student's history?**
No. It has no stored target. Any stored history/result access must pass the
owned-profile service, account binding and applicable source checks.

### 33. What is idempotency, and how does PlacePro implement it?

**Answer:** Idempotency makes a compatible retry reuse an accepted operation rather
than duplicate its effect. Applicable identities include the authenticated account,
operation, resource and key. Payload/source/revision validation prevents treating
a different request as the same operation.

**Follow-up — Does knowing an idempotency key grant access?** No. Authentication
and ownership precede replay. Different accounts' keys do not share authorization
or results; old keys cannot bypass a revoked session.

### 34. How do assessment deadlines and scoring work?

**Answer:** The UI offers 5, 10 or 25 questions; the server permits 1–25 and gives
one minute per question. It stores the selected randomized questions and deadline,
then scores correct answers using difficulty-weighted points. Evidence qualification
requires at least 60%.

**Follow-up — Can changing the JavaScript timer extend the assessment?** No. The
backend's deadline controls acceptance. Browser timing is presentation, not authority.

### 35. How do you return safe API errors?

**Answer:** Anonymous private requests receive 401, required CSRF/Origin failures
403, concealed foreign/missing/unowned targets 404, stale or completed-duplicate
conflicts generally 409, owned expired assessments 410, and cooldown/quota limits
429. Deferred or unavailable services can return safe 503.

**Follow-up — Why not return 404 for every failure?** A genuine service/storage
failure should be reported safely as unavailable rather than falsely described as
missing. Non-disclosure does not justify hiding all operational faults.

## Frontend questions

### 36. What is the actual frontend architecture?

**Answer:** React 19 with JavaScript/JSX, CSS and Vite. App switches the active page
using the existing URL mapping/History API and state. Context and hooks share authentication/selected-profile state with
the dashboard and other pages. There is no React Router or Redux dependency.

**Follow-up — Why mention this distinction?** Examiners may ask about routing or
global state. Explain the implementation that exists, rather than claiming a
familiar library that the project does not use.

### 37. How does the frontend communicate with the backend?

**Answer:** A shared fetch transport includes cookie credentials, obtains CSRF
tokens for required requests and validates responses/errors. Feature service
modules call the appropriate API. The backend remains the authority for ownership,
scores, revisions and lifecycle.

**Follow-up — Is CORS an ownership check?** No. CORS controls browser cross-origin
interaction. Direct clients can make requests too, so server authentication and
resource authorization remain necessary.

### 38. How do you restore a session after refresh?

**Answer:** The browser retains the server's HttpOnly cookie. On startup, the
frontend checks the session API, restores public account information, obtains
needed CSRF state and loads owned profiles. It does not restore authentication
from a localStorage flag or token.

**Follow-up — What if the cookie is expired or revoked?** The server rejects it;
the frontend clears the authenticated workspace and presents login/expiry feedback.
Stored profile references cannot override the server's decision.

### 39. How do you prevent stale data when switching profiles?

**Answer:** The workspace is keyed/remounted on account/profile changes. Resource
hooks and request-generation/revision checks discard late results for an older
selection. Dashboard/model/assessment drafts are associated with their current
context rather than carried blindly into the next profile.

**Follow-up — Is remounting enough for security?** No. It improves UI isolation;
the backend must still deny foreign profiles and records independently.

### 40. What does browser storage contain?

**Answer:** Limited account-scoped profile references and assessment/retry draft
information may use sessionStorage. Passwords, session cookie secrets and CSRF
tokens are not used as localStorage authorization. Login/CSRF state is handled by
the cookie and in-memory transport.

**Follow-up — Are draft answers therefore harmless?** They are still account-related
UI data and require careful scoping/clearing. They never authorize submission or
replace the server's session, ownership, deadline or accepted receipt.

### 41. How does the UI handle missing data and failures?

**Answer:** It shows empty-profile onboarding, extraction-review guidance,
loading/error states and source freshness. Unknown company eligibility stays
INCOMPLETE rather than becoming a fabricated failure or success. Invalid backend
responses and failed requests produce visible errors.

**Follow-up — Can an extractor provide a coding score from a skill mention?**
No. A readable resume can supply claims, but missing numeric self-assessed inputs
require explicit entry and review.

### 42. Which frontend screens and limitations should you explain?

**Answer:** Dashboard, Student Profile, Placement Prediction, Salary Prediction,
Skill Gap Analysis, Company Recommendations, Mock Tests and Performance Analysis
are integrated, alongside Experimental V1, Career Readiness, Goals, Notifications
and Resume Builder. History appears within the relevant assessment/performance views.
Standalone resume upload/analyze and real activation/recovery are unavailable.

**Follow-up — Is the UI accessibility-certified?** No. Source includes responsive
styles, focus/keyboard improvements and accessible controls, but no independent
accessibility certification or complete device-validation claim is supported.

## Authentication and security questions

Sources: [request gate](../../backend/app/security.py),
[sessions](../../backend/app/services/session_service.py) and
[ownership store](../../backend/app/services/ownership_store.py).

### 43. What is the difference between authentication and authorization?

**Answer:** Authentication establishes which account has a valid session.
Authorization establishes which profile, assessment or stored result that account
may access. A valid login never grants access to all profiles.

**Follow-up — Is a difficult-to-guess UUID sufficient?** No. UUIDs identify records.
Every owned operation must verify the authoritative association regardless of ID secrecy.

### 44. How are passwords stored?

**Answer:** Passwords use Argon2id hashing with salts and configured work factors.
The system compares a supplied password through the password service; it does
not store plaintext passwords in profiles or the frontend.

**Follow-up — Why hash rather than encrypt them?** Password verification needs a
one-way comparison, not recovery of the original password. Slow password hashing
also differs from the fast SHA256 hashes used for high-entropy session secrets.

### 45. Why use HttpOnly server-side sessions instead of a frontend token?

**Answer:** Login creates an opaque random cookie secret. The backend stores its
hash and session metadata in SQLite. HttpOnly prevents ordinary JavaScript access
to the cookie, and server-side records support revocation, expiry and account-version checks.

**Follow-up — Does HttpOnly eliminate XSS?** No. Malicious script could still
initiate actions in a compromised page. It reduces secret exposure; it does not
replace safe rendering, ownership, Origin or CSRF controls.

### 46. How do CSRF and Origin protection work?

**Answer:** Required requests carry a session-bound HMAC CSRF token, and the server
checks permitted Origin/transport policy. Login uses a bootstrap challenge.
Lifecycle GETs for assessment retrieval/history require CSRF because they can
perform expiry/recovery effects.

**Follow-up — Why is SameSite alone insufficient?** Cookie policy is one layer.
Explicit token and Origin checks support the application's complete request policy,
and none of these controls replaces resource ownership.

### 47. How do session expiration and revocation work?

**Answer:** Defaults are 30-minute idle and 12-hour absolute lifetimes. Validation
checks revocation, ACTIVE verified account state, account authentication version
and password-change metadata. Rotation replaces the secret while retaining the
absolute limit; logout revokes its session family.

**Follow-up — Can a previously valid retry key revive a revoked session?** No.
Replay remains an authenticated operation and must pass current account/session checks.

### 48. How do you protect legacy profiles and account isolation?

**Answer:** Ownership is authoritative in authentication SQLite. Only an ACTIVE
association for the session's account grants access. Missing, foreign, legacy-unowned,
pending or suspended targets do not become accessible by matching email or
client-supplied account ID.

**Follow-up — Why not claim an old profile when its email matches?** Historical
email claims are not verified ownership proof. Automatic claiming could expose
someone else's data and is deliberately absent.

### 49. Is the synthetic demo an authentication bypass?

**Answer:** No. The local launcher creates new fixture accounts and profiles in
fresh temporary storage, then uses normal login, CSRF and owned APIs. The operator
chooses a hidden password; there is no hard-coded frontend credential or public
demo administrator.

**Follow-up — Can anyone register normally today?** Public registration returns
503 because activation is unfinished. Also, the prompt says 12 characters while
the actual backend minimum is 15; use 15–128 for the demo. This audit changes neither policy nor code.

## Database and storage questions

### 50. What databases and files does PlacePro use?

**Answer:** Authentication SQLite stores accounts, sessions, challenges and profile
ownership. Separate company, goals/milestones/notifications and resume-builder
SQLite stores persist their owned data.
Profile and assessment JSON files store student sections, revisions, histories,
evidence and assessment lifecycle. Saved model artifacts provide inference.

**Follow-up — Is it MongoDB or a single relational database?** No. It is a hybrid
local SQLite/JSON architecture. Describe that actual boundary and its limitations.

### 51. What is the account-to-profile relationship?

**Answer:** One account can own multiple profiles, but each profile has at most one
owner. The ownership table uses a unique/primary profile ID, an account foreign
key, state/version/timestamps and immutable identity protection.

**Follow-up — Can the student update the owner field in profile JSON?** That does
not establish authority. Ownership is checked from the server-side association,
and client-supplied ownership fields cannot override validated identity.

### 52. How is safe profile creation implemented?

**Answer:** The service reserves a PENDING ownership association, exclusively writes
a new server-generated profile, validates publication and activates ownership.
Unkeyed creation uses a random UUID; keyed creation derives a server UUID from
account/operation/key identity to locate the same reservation safely.

**Follow-up — Is this one atomic SQLite/JSON transaction?** No. It is staged
publication across two stores. Failed or interrupted pending data remains
quarantined; it is not automatically claimed or exposed.

### 53. Why are profile revisions important?

**Answer:** A revision records the source version used for review, edits and
derived results. An edit based on an old revision is rejected rather than silently
overwriting a newer update. Predictions can remain in history while being marked
stale for the current source.

**Follow-up — Does a stale result become false history?** No. It remains a result
for its original input/version. It must not be presented or replayed as a fresh
result for a different current profile revision.

### 54. What does assessment recovery preserve?

**Answer:** Persisted states are IN_PROGRESS, SUBMITTING, COMPLETED and EXPIRED.
After valid answers are accepted, SUBMITTING enables authorized recovery of
evidence and completion. Completed duplicates return 409 without awarding evidence again.

**Follow-up — Are RESERVED, COOLDOWN and RETAKE stored states too?** No. They are
workflow/quota/eligibility concepts. Three completed-or-active slots per skill/profile
and a 24-hour scored-completion cooldown remain policies.

### 55. How do locks and transactions protect concurrency?

**Answer:** SQLite transactions/constraints protect ownership uniqueness. Cooperating
thread and OS file locks serialize JSON profile/assessment operations on one host.
Revision and retry checks protect compatible updates and accepted effects.

**Follow-up — Does this guarantee multi-host or power-loss safety?** No. There is
no cross-store atomic transaction, multi-host coordinator or certified crash/network-filesystem
guarantee. Explain the local limits rather than claiming enterprise scalability.

### 56. How is demonstration storage isolated?

**Answer:** Each launcher run creates a fresh placepro_demo_* temporary workspace
with its own authentication/company/profile/assessment storage, generated DOCX
and frontend build. Project models are read-only. Shutdown stops owned servers
and retains the demonstration records.

**Follow-up — Does restarting automatically load the last demo?** No. The launcher
is fresh-only. Keep current printed paths for that session; do not redirect it
to production data or overwrite an existing workspace.

## Testing questions

### 57. What test results can you honestly report?

**Answer:** Recorded Phase30 results are 1,125 backend tests and 195 frontend tests
passed, plus 54 real HTTP assertions and passing lint/build. Phase29 recorded
40 Chromium assertions. These are historical software validation results, not
new Phase31 suite runs.

**Follow-up — Was Phase30 browser automation fully successful?** No. New automated
browser/visual execution was blocked. The owner subsequently reports successful
manual main-workflow rehearsal across three synthetic accounts; no numerical assertion count is supplied.

### 58. What kinds of tests exist?

**Answer:** Backend pytest tests cover services, storage, inference contracts,
ownership, HTTP/HTTPS security, assessment lifecycle and concurrency. Frontend
tests use Node's built-in test runner for transport/controller/state helpers.
Lint checks source rules; the Vite build checks production bundling.

**Follow-up — Does a Node helper test prove browser rendering?** No. Real browser
interaction/rendering is separate evidence. A passing build also does not establish
all usability or accessibility behaviours.

### 59. How is cross-account isolation tested?

**Answer:** Isolated fixtures use multiple synthetic accounts/profiles and request
foreign profiles, assessments, histories and replay targets through secured APIs.
Tests check safe denials and that denied requests cause no private JSON effects.

**Follow-up — Is hiding B's profile in A's menu sufficient?** No. Server denial
must work even when the attacker knows the exact profile or assessment ID.

### 60. How are lifecycle, retries and concurrency checked?

**Answer:** Tests exercise reservations/quota, unique attempt numbering, deadlines,
expiry, duplicate submissions, cooldown, evidence-write recovery, compatible
replays, conflicting payloads and stale revisions. Concurrent operations test
once-only history/evidence and local locking guarantees.

**Follow-up — Does every retry return HTTP 200?** No. An accepted compatible replay
can reuse a result, but a completed duplicate assessment submission retains 409
and conflicting/stale requests may fail. Idempotency protects effects, not one universal status.

### 61. How do tests avoid altering historical student data?

**Answer:** Synthetic accounts and temporary databases/directories isolate storage.
Real secured HTTP/HTTPS tests use isolated server fixtures. Phase31 only inspects
source/model/CSV structure and verifies file hashes; it does not run training,
historical-data fixtures or application mutation.

**Follow-up — Why record a preservation baseline?** It makes non-interference
reviewable: original paths/hashes, branch, HEAD, index and previous journal bytes
can be compared after the documentation changes.

### 62. How do you handle warnings and unsupported checks?

**Answer:** Recorded Phase30 backend runs passed with ten existing joblib/NumPy
shape-deprecation warnings. Build evidence retains the intentional outside-root
output notice. Unsupported or blocked browser/visual scenarios are listed rather
than marked passed or silently skipped.

**Follow-up — Should you suppress warnings for the examiner?** No. Explain their
known scope and distinguish a warning from a failing test. Do not invent a clean
result by deleting tests or changing dependencies during presentation preparation.

### 63. Do passing software tests prove model quality or security certification?

**Answer:** No. They establish specified behaviour under tested conditions.
They do not demonstrate representative real-world ML generalization, complete
threat coverage, high-load deployment safety or independent certification.

**Follow-up — What was validated freshly in Phase31?** Documentation consistency,
source/artifact/schema/route claims, links, question/slide structure, Git state
and preservation. Historical test results remain explicitly labelled.

## Limitations and future enhancements

### 64. What are the most important current limitations?

**Answer:** Self-service activation/recovery are unavailable; configured Google OAuth is
implemented but provider/hosting acceptance remains pending;
two standalone resume routes remain blocked; OCR is absent; company requirements
are sample data; final placement training provenance/evaluation is incomplete;
and local SQLite/JSON has deployment/recovery limits.

**Follow-up — Why present limitations openly?** Examiners need to distinguish a
working local product from unsupported production or real-world outcome claims.
Honest boundaries make the implementation easier to defend.

### 65. What would you improve first after the presentation?

**Answer:** With separate approval, establish trustworthy account activation/recovery,
recover dataset/model-run provenance, acquire permitted representative evaluation
data and review deployment/storage requirements. Prioritize actual product gaps
instead of adding unverified accuracy claims.

**Follow-up — Are these enhancements implemented in Phase31?** No. Phase31 is
documentation and preparation only; it adds no application logic or dependency changes.

### 66. How could you improve resume processing?

**Answer:** Current readable PDF/DOCX extraction uses pypdf/python-docx and rules.
Future work could evaluate OCR and better parsing on permitted labelled documents,
with file security/privacy and accuracy measurements. Review and provenance should
remain even if extraction improves.

**Follow-up — Can you advertise current extraction as AI resume understanding?**
Not as an LLM, trained entity recognizer or scanned-document capability. Explain
the actual text extraction and rule-based normalization.

### 67. How could company recommendations become more realistic?

**Answer:** Obtain approved, current requirement data with provenance/versioning,
validate eligibility rules with domain experts and evaluate ranking usefulness.
Current weighting is explainable but not learned from recruitment outcomes.

**Follow-up — Can you scrape or invent current company cutoffs for the viva?**
No. Show the configured DEMO requirements and identify real recruitment-data
integration as future work, subject to permission and source verification.

### 68. What would public deployment require?

**Answer:** Review account onboarding/recovery, HTTPS/cookie/Origin configuration,
secrets, storage/backup/recovery, multi-worker coordination, monitoring, privacy
and load/security validation. These are planning requirements, not current certifications.

**Follow-up — Can you expose the local demo publicly instead?** No. It is an
explicit loopback synthetic workflow and not evidence of an approved public trust
boundary. Do not change its network or authentication restrictions for convenience.

### 69. Can students manipulate their self-reported scores?

**Answer:** Some academic/technical inputs are student claims. Confirmation means
review in the application's workflow, not independent certification. Server-scored
assessments provide distinct provenance; evidence resolution should not equate
resume mentions with measured competence.

**Follow-up — Does a 60% practice score prove job readiness?** No. It satisfies
the project's assessment evidence threshold for its question bank. It does not
independently verify professional capability or placement probability.

### 70. How would you conclude the viva honestly?

**Answer:** PlacePro demonstrates an integrated authenticated preparation workflow,
two served ML estimators, explainable guidance and account/profile-isolated history.
The local rehearsal uses synthetic students. We can defend the implementation
and recorded tests while clearly separating incomplete provenance, onboarding and deployment work.

**Follow-up — What evidence would make the next version stronger?** Artifact-linked
reproducible training/evaluation, approved representative data, completed account
activation/recovery and recorded end-to-end/device/deployment validation. These
are recommended next steps, not promises of already achieved results.

## Final practice checklist

- Explain probability, confidence, salary, readiness and assessment score separately.
- Draw browser → secured API → authorized service → storage/model from memory.
- Explain one real request, one rejected foreign request and one compatible retry.
- Know which model is served rather than listing every artifact in the models folder.
- Do not confuse a synthetic dataset count, test count and application user count.
- Use the [demo script](live-demo-script.md) for observable workflows and the
  [limitations guide](limitations-and-future-scope.md) when evidence is incomplete.
