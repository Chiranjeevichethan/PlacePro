# Frontend/backend integration validation — Phase 29.4

> Historical snapshot: the original phase dates, design decisions and recorded
> test results below are preserved. Statements about the then-current inventory,
> unavailable features and pre-authentication behavior are superseded by the
> [reviewed 2026-11-24 release snapshot](../backend/DEPLOYMENT.md#reviewed-release-snapshot-2026-11-24).
> This documentation change reruns no application tests and establishes no new
> Linux/Docker or browser acceptance.

Completed 2026-11-07 on Windows. This validates the complete uncommitted working
tree, rather than HEAD alone. Earlier work, profiles, sessions, company storage,
datasets, trained artifacts, environments and backups were preserved.

## Architecture and isolation

React 19/Vite 8 uses page-state navigation, a shared StudentProfileProvider and
revision-aware resources. API services call FastAPI JSON endpoints or multipart
resume endpoints. Profiles/assessment sessions are JSON; company requirements use
SQLite; placement and salary load the existing LogisticRegression/Ridge pipelines.
There is no backend authentication or verified email ownership. Claim confirmation
does not establish ownership. No architecture, dependency, business-rule, model or
historical migration change was made.

The existing pytest storage fixture and owned HTTP wrapper were reused. Browser
validation used an isolated wrapper around that application, unique temporary
profile/session/company stores, and a run-ID health response checked before tests.
Its clock, fixture, answer-oracle and one-shot save-failure controls exist only in
the ignored validation wrapper, require its run ID and never enter production
routes. Correct/wrong answers make expected scores deterministic despite normal
server question sampling. Production quota, scoring and cooldown rules remain.

Controlled loopback ports: API **53039**, Vite production preview **53040**, pytest
HTTP child **53041**. The build embeds that API URL; CORS was checked with the
actual frontend origin. Production builds use new retained scratch directories.
No existing dist/node_modules/environment was erased. The scripts start hidden
owned children, refuse occupied ports, and stop only those children on STOP/EOF.
Final socket binds succeed on all three ports; owned PID checks return no processes.
Termination returned code 1 on Windows; this is a controlled forced stop, not a
claim of graceful Uvicorn/Vite shutdown. Browser contexts/tabs were closed.

## Reproduced defects and corrections

| Problem | Cause | Small correction |
| --- | --- | --- |
| Missing assessment average became 0% | Number(null) coercion in Dashboard/Performance readers | Shared finite-number reader keeps unknown values null and preserves actual zero |
| Unavailable placement showed 0% risk/confidence | Same null coercion | Render the existing unavailable-prediction state |
| Salary ignored a known college tier | Prefill/payload intentionally dropped the supported optional field | Preserve known profile tier, disclose it; omitted tier retains existing backend fallback |
| Prediction displayed an assessment's timestamp | Flattened summaries overwrote latest_timestamp | Read prediction and assessment timestamps from their own nested summary |
| Fractional counts were silently rounded | Math.round in request integer conversion | Reject fractions before inference; salary form validates whole counts |
| Malformed successful inference responses could become results | Numeric coercion and permissive status/version checks | Require finite numeric values, supported placement labels, valid ranges and model version |
| Switching tabs could restore the previous profile | Mirror invalidation refreshed the other tab's old controller ID; queued ID events could be old | Focus/storage refreshes read the active shared ID at delivery time, keeping existing request guards |
| Company details displayed null probability as 0% | Independent Number(null) reader | Reuse the null-safe reader; hide unavailable probability row |
| Skill-gap view omitted insufficiency explanations | Backend reason/evidence fields were discarded | Show actual backend explanations in a details control and distinguish claims from tested proficiency |
| About misidentified current models/integration | Legacy experiment copy remained in the page | Describe the served models and current integration; remove legacy accuracy/current-best claims |
| Empty company success showed only profile summary | No empty-result state | Add explicit empty-result message and demonstration-data label |

Each rendering defect was reproduced in Chromium before its correction. Node
regressions cover payload/response/numeric contracts and tab event delivery;
browser regression records cover rendering and cross-module behavior. No new test
framework or production dependency was installed. The original eight company
requirement sets remain demonstration data; these checks do not verify live jobs.

## Contract and dependency inventory

| Consumer/workflow | Live contract and source | Validation |
| --- | --- | --- |
| Canonical profile | GET/PUT /api/profile/{id}, POST /api/profile/verify; server revision and confirmation | Pending edits/confirmation, identical retry, conflict 409, failure 503, two independent profiles |
| New resume profile | POST /api/profile/from-resume; unconfirmed UUID draft | DOCX extraction, skill/certification correction, preserved originals, explicit confirmation selects ID |
| Existing resume review | POST /api/resume/analyze; read-only | Same selected ID/claims/assessment and prediction histories remain; malformed DOCX gives 422 |
| Placement form | POST /api/predict; 16 required inputs; placement_probability/prediction/confidence/model_version | Actual request capture, existing-model execution and percentage rendering; input stamps invalidate results |
| Profile prediction | POST /api/profile/{id}/predict with optional Idempotency-Key | Append-only source revision/inputs; keyed replay returns one record |
| Salary | POST /api/salary-predict; 16-field request, optional tier, 12 used model features | Known tier reaches model, LPA matches response; DSA/ML/system-design/open-source fields are required compatibility fields but do not affect salary |
| Readiness / skills | GET /api/profile/{id}/readiness and /skills; shared evidence resolver | Source revision, assessment score/claim separation, insufficient/missing explanations; frontend does not classify readiness anew |
| Eligibility / recommendations | GET /api/companies, /api/companies/{id}, /api/profile/{id}/eligibility[/company], /recommendations | Actual group/rank/card/status/reason equality; empty and failed refresh states; current source revision |
| Dashboard / performance | GET /placement-summary and /performance plus recommendations | Matching revision joins, no summary history writes, nullable scores, separate historical timestamps |
| Assessment | POST /api/assessment/start, GET /api/assessment/{id}, POST /submit, GET /api/profile/{id}/assessments | Reservation/deadline, drafts/navigation/refresh, scoring, recovery, duplicate/cooldown/expiry integrity |

The start response intentionally lacks status/profile_id; GET supplies authoritative
session status/ownership. The frontend fills only its known profile/session context,
then validates restoration. An unknown skill returns 404, not 422. Incorrect new
test expectations were corrected without changing backend response contracts.
HTTP 400/404/409/410/422/429/500/503 and network failures remain errors; they never
become invented success values. Existing assessment tests additionally cover 403.

Current profile projections are calculated on demand and carry source_revision;
browser resource guards reject foreign, late or mixed revisions. Form predictions
are associated with actual submitted inputs/identity/revision. Profile editing
does not rewrite completed attempts, scores, timestamps or evidence. Explicit new
prediction records have revision/inputs; legacy source stays unknown. Direct form
placement/salary are stateless and do not append profile history. Confirmed claims
remain authoritative over original extraction; trusted assessment sufficiency uses
the existing shared policy. Empty/failed data never becomes verified proficiency.

## Browser coverage

Chromium **156.0.8078.80**, desktop **1440 × 1000**: **32 unique final scenarios
pass**, 0 failed/errors/skipped/deselected, 0 unhandled page errors. There are **14
expected console errors** from intentional HTTP rejection/failure or network-abort
tests; none is an unexpected success-path console error.

| Scenario | Actual execution |
| --- | --- |
| A — New student | Dedicated confirmed fixture; profile, skills, recommendations, performance and About navigation; live placement form/result; manual creation API tested separately |
| B — Resume student | Missing selected profile -> explicit creation -> real DOCX extraction -> structural correction -> confirmation -> manual model inputs -> readiness/prediction; original certification text retained |
| C — Assessment student | Start five questions, select answers, leave/cancel/navigate/refresh, restore draft, submit correct fixture, score 100, readiness 43 -> 48, skills/performance update |
| D — Revision | CGPA/certification edits, pending confirmation, revisions 1 -> 2 -> 3, all downstream source revisions agree; placement/salary input changes hide earlier results |
| E — Switching | Two tabs and independent profiles; delay old response; switch through existing storage-ID mechanism; new name/tier/assessment state remain selected |
| F — Failure/retry | One-shot save 503 keeps profile/modal edits; stale edit 409 reloads; dashboard/profile/recommendation refresh failures retry; duplicate prediction clicks send once; lost/pre-acceptance/partial assessment delivery recovers once |
| G — History | Edits preserve assessment evidence and prediction arrays; completed result stays identical; performance labels the old prediction historical; summary GET is read-only |
| Additional | Missing values, correct tier/LPA, distinct timestamps, cooldown/eligible retake, expiry 410, automatic deadline submission, empty-answer 400, insufficient assessment explanation, company ranking/empty state/demo label and mock login |

The 28 core scenarios use build-evidence-final; the final company-message/ranking/
login scenarios use build-complete, which adds only company empty/demo messages.
The final storage-fallback and adjacent tab-switch/prediction checks use build-storage-final.
They inject an unavailable localStorage read and retain the in-memory selected ID.
The additional unique scenario brings the final total to 32; adjacent reruns are not added.
Selected results are deduplicated by scenario name: a premature confirmation test
read was replaced by its completed-state retry, not counted as another scenario.
All final frontend files pass the final Node/lint/build validation. There is no
profile chooser UI: tab/storage synchronization, not a nonexistent chooser, was tested.

## Exact validation and earlier failures

| Completed command/check | Pass | Fail | Errors | Skip | Deselect | Warnings |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| pytest backend/tests/test_integration.py -q -p no:cacheprovider | 11 | 0 | 0 | 0 | 0 | 10 |
| pytest backend/tests/ -q -p no:cacheprovider | 547 | 0 | 0 | 0 | 0 | 10 |
| npm run test (final) | 156 | 0 | 0 | 0 | 0 | 0 |
| node --test tests/integrationApi.test.js tests/profileState.test.js | 53 | 0 | 0 | 0 | 0 | 0 |
| Chromium unique scenarios | 32 | 0 | 0 | 0 | 0 | See expected console errors above |
| Live HTTP smoke checks | 20 | 0 | 0 | 0 | 0 | 0 |

Focused backend tests are included in the 547; the 53 focused Node tests are
included in the 156. Browser/HTTP workflows overlap backend unit/API coverage;
do not add executions into a unique overall test total. Full backend includes
six owned live-HTTP cases. Pytest reports 8.15 s focused / 44.36 s full; final Node
runner reports 232.4563 ms / focused 142.4713 ms. All cancelled/todo Node counts
are zero. Lint exits 0; production build exits 0 (65 modules, 315 ms, retained
build-storage-final directory). Its outDir-not-emptied notice is deliberate preservation.
git diff --check exits 0 with the existing main.py LF/CRLF notice.

Earlier runs remain evidence, not final passing results:

- Initial backend: **531 passed / 5 setup errors / 0 failed**, ten warnings
  (40.22 s). Live-server health received `http.client.BadStatusLine: GET /health
  HTTP/1.1`. Its transient cause is unverified; no backend source was changed to
  explain it away. Later owned HTTP/full runs pass.
- First new backend selection: **10 passed / 1 failed**, ten warnings (8.28 s),
  due to expecting 422 instead of existing unknown-skill 404. Final selection passes.
- Baseline Node: **121 passed**. Intermediate corrections: **153 passed**; the
  three tab-delivery tests bring the final total to 156. Intermediate lint/build pass.
- Initial browser regressions: **0 passed / 3 failed**, then **0 / 1** for the
  timestamp defect. Company null/evidence baseline is **0 / 2**; empty-company
  baseline is **1 / 1**. Tab switching failures reproduced the actual mirror race.
- Other browser checkpoint failures were test assumptions: About heading text,
  case-sensitive error text, expecting status on start, exact text of the historical
  paragraph, and waiting for the button label to change instead of confirmation
  completion. One script had a syntax error before scenarios. All are retained.
- A final browser batch's automatic permission review timed out before execution;
  its single permitted retry passes three scenarios. No approval rejection remains.
- A read-only diff-print command hit Windows cp1252 UnicodeEncodeError; rerun with
  UTF-8 stdout succeeds. This was not an application or test failure.

The ten dependency warnings still originate from joblib's NumPy array-shape
restoration on original model loads, as triaged in setup-dependency-audit.md.
No dependency change, warning filter, retraining or artifact resave was made.

## Commands and retained evidence

Executed from the root with the existing CPython 3.14.6 venv:

```powershell
# Browser code/outputs: retained JSON; STOP sent to this owned launcher afterward.
git diff --check
```

Node focused command ran from frontend/. Validation JSON records contain the
expanded actual subprocess commands and durations. the historical final-browser result
contains the 32 selected records (earlier 31-record artifact retained); the historical browser-run record preserves executions;
the historical API smoke result records 20 checks; baseline/source-before/knowledge-before preserve
the phase-start snapshot; preservation-final and shutdown-final record safeguards.
Full Git inventory is in preservation-final's current status/untracked fields.
Existing test/fixture infrastructure remains the supported pytest/Node entry point.
Scratch scripts refuse evidence overwrite; a rerun needs a new evidence directory
and matching server run ID/ports. Browser records are manual Playwright-tool scripts,
not a newly installed npm/CI browser suite. Agent-browser was unavailable, so the
existing Playwright/Chromium tool was used following the browser skills.

## Files and preservation

Application/test changes in this phase (not the full accumulated Git diff):

- Backend: new backend/tests/test_integration.py (11 cross-module cases). - Frontend services/hooks: api.js, profileConfig.js, salaryPrediction.js,
  profileState.js, useProfile.js; new resultDisplay.js. - Frontend components/pages: CompanyCard.jsx, SkillGapCard.jsx, About.jsx,
  CompanyRecommendations.jsx, Dashboard.jsx, PerformanceAnalysis.jsx,
  SalaryPrediction.jsx. - Frontend tests: profileState.test.js; new integrationApi.test.js (32 cases).

Total **18 source/documentation files**. They are retained; no existing artifact/backup/scratch file was cleaned.

Final Git: branch **bhargav-frontend**, HEAD
**f84099349d104e4e77c7080fba4465ca4e3470a4**, **56 modified tracked files + 55
grouped untracked entries = 111**, **71 expanded untracked files**, empty index.
All **107 initial Git entries** and previous journal bytes remain. The **530
protected files** retain baseline SHA-256 hashes. Existing unrelated inspected
files remain unchanged; only the listed intended changes modify baseline files.
No profiles/sessions/company records were deleted/migrated/merged. Models, datasets,
ML source, requirements, environments, .env files and backups were preserved.

## Remaining boundaries and next phase

This is desktop Chromium and deterministic isolated fixtures, not independent
real-student/model accuracy, arbitrary resume templates, mobile/other browsers or
production deployment validation. Pending edits keep the profile-wide confirmation
gate; legacy clients without revision guards remain compatible and less protected.
Legacy predictions without source metadata remain unknown. Direct salary has no
stored profile history. The schema still requires four unused salary compatibility
fields; tests prove they do not affect inference, rather than silently dropping them.

Backend ISE-family normalization still differs from frontend CSE mapping; salary
Chemical/category support, clipping/scales and original training metadata remain
documented limitations. Authentication/ownership and session GET authorization are
absent. Lost start/create responses have no idempotent discovery. Local cooperating
writer locks and SUBMITTING recovery are not multi-file crash transactions or
multi-host guarantees. The malformed baseline health-response origin remains unknown.
The ten dependency warnings and restricted empty-cache online setup remain separate
known boundaries. No historical source revision/record migration was invented.

Recommended next assignment: **Phase 29.5 ownership/access-control design and
retry-identity audit**, with an explicit threat model and scope before adding auth
or migrations. Reusable CI browser automation can be scoped separately. Phase 29.4
is complete; no later phase was started.
