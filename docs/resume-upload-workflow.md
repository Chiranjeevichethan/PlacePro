# Phase 32 — Authenticated resume upload, review and profile update

> Publication refresh (2026-11-24): current capabilities, 50 operations/45 paths,
> required artifacts and verification boundaries are summarized in the
> [reviewed release snapshot](../backend/DEPLOYMENT.md#reviewed-release-snapshot-2026-11-24). Earlier dated results remain historical;
> no new application tests, browser acceptance or Linux/Docker success are claimed.

Implemented in the normal secured application, not behind the synthetic-demo flag.
Prepared 2026-11-09. Manual Chrome validation is pending the student's interactive
rehearsal; no browser navigation was automated.

## Existing functionality and the missing integration

PlacePro already extracted readable PDF/DOCX documents with pypdf/python-docx,
parsed structured sections and created new account-owned resume draft profiles.
The draft editor and explicit profile confirmation already existed. Extractable
fields include name/contact links, education, categorized skills, projects,
internships/experience, certifications and activities when text provides evidence.
Missing information stays null/empty; numeric skill scores are not inferred.

Updating an existing profile from a resume was unavailable: its button was
disabled and the previous analysis helper called a blocked standalone route.
Those standalone upload/analyze routes still return 503 after valid authentication/
CSRF. They are not enabled as a shortcut.

## Smallest implementation and student workflow

1. Log in and open an ACTIVE owned profile.
2. Choose **Update from Resume**, select a readable PDF/DOCX and upload.
3. The new owned-profile endpoint returns an extraction preview for the requested
   current revision. It saves no profile, history, ownership or extracted resume copy.
4. The comparison shows current and extracted values. All choices start unchecked,
   preserving every current value. Select only the fields to import.
5. Edit the resulting scalar, skill, record and activity values. Selecting an
   extracted list replaces that list; it does not silently merge records or invent counts.
6. Check the explicit review acknowledgement and click **Confirm & Update My Profile**.
7. The existing confirmation service saves the reviewed payload under the same
   profile ID, using ownership, revision and account-bound retry checks.
8. The frontend reloads its authoritative profile. Existing revision/request guards
   refresh dashboard inputs and derived views; old predictions remain history and
   are not replayed for the changed source.

New-profile resume creation retains its existing separate draft/review/confirmation
workflow. No existing profile is silently overwritten at upload time.

## Endpoint contract and authorization

| Operation | Authentication / authorization | Effect |
| --- | --- | --- |
| POST /api/profile/{profile_id}/resume-preview | Valid session, CSRF/allowed Origin, ACTIVE ownership and existing valid profile before multipart parsing; reviewed revision before extraction; session/ownership/revision checked again afterward. | Extraction response only; no student-record write. |
| POST /api/profile/from-resume | Existing session/CSRF and account-bound safe creation. | Creates a new unconfirmed owned draft. |
| POST /api/profile/verify | Existing session/CSRF, ACTIVE ownership for a target, reviewed revision and request receipt checks. | Explicit confirmation of reviewed student information. |
| GET /api/profile/{profile_id} | Existing ACTIVE ownership. | Authorized current profile. |
| POST /api/resume/upload and /api/resume/analyze | Existing authentication/CSRF, then default-deny. | Remain blocked with 503. |

The preview uses multipart fields **file** and **revision**, exactly once each.
Extra fields, duplicate files/revisions and client ownership identifiers are
rejected. Its response uses the existing OwnedResumeResponse structure: profile,
completion, message, provenance, confidence, diagnostics, extraction_summary and
feature_availability. The preview profile ID/revision identify its source; they
do not mean the extraction was saved. The frontend rejects a mismatched source.

At the historical Phase32 checkpoint the inventory was **32 operations across 31 paths**. The
current release mounts **50 operations across 45 paths**. At that checkpoint, only this
explicit owned operation was added to the private gate's profile set. Unknown
routes stay private; auth/session policies and the other operations remain intact.

Foreign, missing, legacy-unowned, pending, suspended and invalid/corrupt profile
targets receive the same safe 404. Anonymous requests receive 401 and security
failures 403. Stale source revisions receive 409. Genuine unavailable services
can return 503; parser internals and private paths are not echoed.

## Upload and extraction validation

- Supported extensions: PDF and DOCX, case-insensitive; no DOC, images, executable
  or other formats. Maximum file size: 5 MiB (the UI calls this 5 MB).
- Extension, magic bytes and any supplied meaningful MIME declaration must agree.
  Absent/octet-stream MIME is treated as unknown, not proof of the file type.
- DOCX must be a readable ZIP document with the required OOXML members. Malformed,
  encrypted or duplicate-member archives are rejected; maximum 1,000 members and
  25 MiB declared total expanded size.
- PDF extraction is limited to 50 pages; extracted text is limited to 200,000
  characters. Text is parsed with the existing rules.
- Both owned resume routes bound the full multipart body to 5 MiB plus 64 KiB
  overhead before file spooling, and bound the file read independently.
- Uploaded bytes are parsed directly. The redundant service-written temporary
  copy was removed; multipart resources are closed after the request.
- No uploaded file is executed or used to construct a filesystem path. Parser
  failures return safe errors; empty DOCX does not falsely claim that PDF OCR is required.

Unsupported/type-mismatch files receive 415; empty files 400; oversized files/
requests 413; malformed/unreadable or extraction-limit documents 422. Scanned/
image-only PDFs require OCR, which remains unavailable. Filename/MIME/browser
validation alone cannot authorize or validate a file.

These bounds are safeguards, not a certified adversarial parsing sandbox or
guaranteed CPU/time limit. Existing document libraries are reused without upgrades.

## Integrity, provenance and downstream use

Imported fields are explicitly reviewed student changes. The existing server
computes user provenance and preserves earlier original_resume_values, prediction
history, assessment evidence and request metadata. A preview's heuristic extraction
confidence is not independent competence verification or calibrated accuracy.
This phase does not persist a second resume-source archive or newest extraction
audit record for an existing profile.

Existing ML inputs and additional information are retained exactly in the review
payload. New extraction cannot import account IDs, ownership, revisions, ML scores
or server evidence/history. Record counts continue to derive from reviewed lists.
Changed confirmed data advances the existing domain revision; compatible no-op/
retry behavior is preserved. No placement/salary mathematics or model files change.

## Tests and current evidence

The new backend tests exercise the actual production-mode secured ASGI app with
temporary accounts/databases/profile directories. They cover PDF/DOCX, file/body/
archive/page/text limits, missing fields, malformed and encrypted files, anonymous/
CSRF/Origin denial, foreign/legacy/inactive/corrupt targets, revision/session/ownership
changes during extraction, student correction, conflict/retry behavior, history
preservation and downstream readiness/recommendation/prediction sources.

Frontend tests cover authenticated multipart/source validation, preserved default
values, explicit selection/clearing, corrected numeric values, protected-field
rejection, wrong/stale responses, failed requests without creation fallback, and
refreshed prediction/salary drafts. They are Node controller/API tests; they do not
prove browser rendering or replace the manual Chrome check.

Recorded initial corrections: first frontend run 208 passed/4 failed due to null
handling, exact preservation of partial ML fixtures and a Headers mock assumption.
These were corrected without removing tests. First backend focus: 237 passed,
1 failed, 4 errors, 8 warnings; corrupt target authorization needed to precede
multipart parsing, and huge automatic parameter IDs exceeded Windows environment
limits. Short explicit IDs and the stronger preflight corrected these issues.

Corrected overlapping focus: **240 passed**, 0 failed/errors/skipped/deselected,
8 existing joblib/NumPy warnings, 81.67 seconds. Five additional malformed/empty/
encrypted/correction cases were then included in the full suite. Final frontend:
**212 passed**, 0 failed/cancelled/skipped/todo, deselection N/A, 503.5107 ms.
Lint passed; production build passed with 75 modules and the intentional notice
that a fresh outside-root output directory would not be emptied.
Full backend/final verification results are appended below when available.

The first full backend run recorded **1,151 passed, 1 failed, 0 errors/skipped/
deselected, 10 warnings, 364.00 seconds**. The failing unchanged assessment concurrency
test observed one duplicate submission returning 503 rather than 409. Its unchanged
isolated recheck passed (1 passed, no failures/errors/skips/deselections/warnings,
6.32 seconds). The cause was not established and assessment/locking source was not
modified. A full recheck is recorded separately; the first failure is retained
and must not be presented as a passing run.

No fixture-reset tests use historical storage.

## Manual validation — run the actual application safely

Account activation is still unavailable. The existing isolated launcher runs the
same secured backend/services and current frontend with fresh local accounts;
it is the safe validation environment, not a separate implementation of the feature.
Use an interactive PowerShell terminal and the already installed dependencies:

~~~powershell
# Run from the repository root with the existing pinned Python environment activated.
python -B scripts/demo.py
~~~

Choose a private **15–128-character** password at the two hidden prompts. The
launcher and backend now both state this existing policy. No fixed credential
is supplied. Defaults are http://127.0.0.1:5173 for Chrome and API port 8765.
If occupied, use the documented --api-port and --frontend-port options with other
free loopback ports; do not stop an unrelated server.

Follow the guide one step at a time, confirming each before proceeding:

1. Start the launcher; report when it prints Open and the generated resume path.
2. Manually open the printed Chrome address; sign in as demo-student-a@example.test
   using the password you chose.
3. Open its existing Student Profile, then Update from Resume.
4. Upload the current launcher's Synthetic-Resume.docx; inspect extraction and
   confirm that the stored profile has not yet changed.
5. Select one field, correct it, retain others, acknowledge review and confirm.
6. Check the same profile ID, updated reviewed information and dashboard inputs.
7. Check placement, salary, readiness and recommendations using actual returned
   results. Old saved predictions must not appear current for changed inputs.
8. Repeat with a readable synthetic PDF, invalid/empty file and an unchanged field.
9. Switch A's profile, then log out/sign in as B; verify separate profile data.
10. Use demo-empty for regression of new-profile resume onboarding, then log out.

Use only fictional information during validation. Do not disclose your password
or cookie values. Ctrl+C in the owned terminal stops its servers and retains
temporary demo records. Manual results must be recorded as observed, not assumed.
See the [existing launcher guide](phase-30-demo-workflow.md).

## Exact Phase32 project file inventory

Created:

- backend/tests/test_resume_profile_update.py
- frontend/tests/resumeUpdate.test.js
- docs/resume-upload-workflow.md

Modified:

- backend/app/routes/owned_profile.py
- backend/app/security.py
- backend/app/services/owned_profile_service.py
- backend/app/services/profile_service.py
- backend/app/services/resume_parser.py
- backend/app/services/resume_service.py
- backend/tests/test_session_security.py
- backend/tests/README.md
- frontend/src/components/ResumeUploadModal.jsx
- frontend/src/pages/StudentProfile.jsx
- frontend/src/services/api.js
- frontend/src/services/profileReview.js
- frontend/src/App.css
- frontend/tests/profileReview.test.js
- frontend/README.md

No manifest/lockfile, model, dataset,
authentication policy or historical student record was changed.

## Final verified implementation results

The final complete backend recheck passed **1,152 tests**, **0 failed, 0 errors,
0 skipped, 0 deselected**, **10 existing joblib/NumPy deprecation warnings**,
344.53 seconds. No assessment code or test was changed to achieve this result.
The earlier intermittent assessment duplicate-submission 503 remains recorded
with an unestablished cause; a passing recheck is not a claim that it was repaired.

The final frontend suite passed **212 tests**, zero failed/cancelled/skipped/todo
(deselection N/A), 503.5107 ms. Final lint and production build both exited0;
build transformed75 modules in623 ms and retained the intentional outside-root/
no-empty notice. Existing installed dependencies were reused.

Isolated import/startup/shutdown and32-operation/31-path inventory checks passed;
62 backend application Python sources parsed and cold start wrote zero storage
files. Preservation checks retain all3,199 original paths,579 protected data/model/
dataset/source assets, all496,632 earlier knowledge bytes and every original Git
entry. Only the listed16 existing files and3 new project files differ; own evidence
is excluded from that count. Branch/HEAD/index unchanged,61 modified tracked,
100 grouped untracked,149 expanded untracked, deleted0; diff check passes.

Implementation and automated verification are complete. **Manual Chrome workflow
validation is pending** and must proceed interactively using the steps above.
No browser assertion or rendering success is claimed.

## Manual rehearsal findings and correction — 2026-11-09

Phase32 is **not yet complete**: the operator reported unexpected personal-looking
values, missing projects, possible role misclassification and incomplete skills.
Corrected code/automated evidence does not replace the pending manual recheck.

### Content source and observed personal values

Inspection of the original `scripts/demo.py:create_resume` found only hardcoded
fictional student/college/email text. It constructed a new python-docx document;
it did not read student profiles, historical resumes or existing extraction test
fixtures. No real personal information was found in that generator. Some tests
use realistic-looking sample identities, but they are not inputs to the launcher.
The exact file bytes and comparison column observed in Chrome were not provided,
so the origin of the operator's unexpected values is **not established**.

The existing-profile editor deliberately preserved current name/email and records
until an import was checked. Calling the surrounding form “Extracted Information”
could make current values appear to be extracted. The comparison also summarized
records by title alone, hiding descriptions, dates and technologies. It now shows
the uploaded filename, explicitly labels **Current profile**, **Extracted from
uploaded file**, and **Profile values to save after your review**, and displays
complete structured record values. This corrects a confirmed presentation issue;
it is not a claim that the personal-information observation has been conclusively
diagnosed or that a data leak was demonstrated.

The generator now uses an explicit self-contained fictional fixture with synthetic
DOCX metadata: Synthetic Demo Learner, synthetic-resume@example.test, Synthetic
Demonstration College, Synthetic Library Planner, Synthetic Study Board, Synthetic
Practice Lab, Synthetic Community Workshop and Synthetic Learning Academy. No real
phone, address, social account, external document link or resume source is used.
It validates the existing fresh-workspace marker and never replaces an existing
file. The operator must restart their own launcher and select the new printed path;
previous temporary records/files are preserved unchanged.

### Confirmed extraction defects and fixes

- The old generated plain `Title — description` project lacked a bullet/next
  Technologies line and was silently dropped. Plain inline titles and titles
  followed by description bullets now work. Descriptions retain additional body
  lines; unattributed prose and numeric counts do not manufacture project records.
- Generic Experience headings previously put explicit Intern roles in employment
  experience. Explicit internship roles now enter the internship list; otherwise
  the document's declared section remains authoritative. Internship Experience and
  combined Experience/Internships headings are recognized. Month/year and numeric
  month/year ranges stay complete instead of leaving months in company names.
- The first occurrence of a skills/projects section previously discarded later
  spans. All relevant spans now contribute while every recognized section still
  bounds content; reference/certification prose cannot bleed into skills/projects.
- DOCX paragraphs were read before all tables, moving table content outside its
  section. Paragraphs and tables now follow document order, including nested and
  merged cells, using the already installed python-docx 1.2.0 APIs.
- Skill matching could select React inside React Native and suppress a separately
  stated Spring after Spring Boot. Longest overlapping mentions now win at each
  text position; separate mentions remain. React.js/ReactJS, NodeJS, VueJS,
  ExpressJS and NextJS normalize to existing canonical names. Unknown skills stay
  absent; no skill scores, dates, companies or missing personal fields are guessed.

No endpoint contract, authentication, CSRF, Origin, ownership, profile revision,
retry mechanism, stored history, model, dataset or prediction formula was changed.
Preview and confirmation retain their existing safeguards. Selected corrected
records map into their respective canonical projects/internships/experience/skills
fields, remain unconfirmed until review, and use existing revision/downstream rules.

### Correction regression coverage

`backend/tests/test_resume_extraction_mapping.py` uses known wholly fictional
content through text, real PDF bytes, DOCX bytes and the secured owned preview/
confirmation endpoints. It checks generator body/metadata/no external links,
all eight skill categories, projects/descriptions/technologies, role separation,
complete durations, table ordering, repeated sections, aliases, missing/ambiguous
data, account denial, student correction and stale revisions. The earlier repeated
section regression now additionally requires the later stated Java skill while
retaining its project-section boundary check; it was strengthened, not removed.

`frontend/tests/resumeExtractionMapping.test.js` checks independent current and
extracted sources, missing extraction, full record display, every skill category,
explicit selection and student corrections without overwriting retained identity.
These are controller/helper tests, not browser rendering validation.

Initial reproducer: 13 failed, 4 passed, 2 fixture setup errors in 5.44s. The two
setup errors were a missing import of the existing encoded_password fixture in
the new test file; the test was corrected. No security test was weakened. The
corrected extraction/integrity focus passed81 tests in6.27s with no warnings.
Broader resume/demo/security focus passed243 tests in63.41s with8 existing
joblib/NumPy warnings. Frontend passed216 tests in426.7686ms with0 failed/cancelled/
skipped/todo. Lint passed; build passed75 modules/320ms with the visible intentional
outside-root/no-empty notice. Complete backend results are recorded after it finishes.

Exact correction changes: modified scripts/demo.py, backend/app/services/resume_parser.py,
backend/tests/test_resume_integrity.py, backend/tests/README.md,
frontend/src/components/ResumeUploadModal.jsx, frontend/src/services/profileReview.js,
docs/phase-30-demo-workflow.md and this document. Created the two test files above.

### Pending manual acceptance

Stop only your previous owned launcher with Ctrl+C, then run the documented
PowerShell command again. Confirm when Open and Resume onboarding file appear.
Subsequent steps must be confirmed individually: inspect the newly generated DOCX,
check Synthetic Demo Learner in the **extracted** identity column, verify both
project details, one internship/one experience and all eight skill categories,
select/correct/confirm an owned profile update, verify downstream refresh and
account isolation. Unexpected real information in the actual file or extraction
column remains a blocker to investigate without exposing it publicly. No automated
browser navigation is authorized or performed.

Final correction automated verification: **1,171 backend tests passed**, zero
failed/errors/skipped/deselected, **10 existing joblib/NumPy warnings**, **335.87s**.
All **216 frontend tests passed**, zero failed/cancelled/skipped/todo, **426.7686ms**.
Lint and production build passed; isolated startup/shutdown, 32-operation/31-path
inventory and 62 backend Python AST checks passed with zero cold-start storage
writes. All 3,238 original baseline paths remain; all 579 protected assets are
unchanged. Only the nine expressly listed source/test/doc/journal files changed;
no original path was deleted. All 506,228 earlier journal bytes are preserved. Branch/HEAD/index
remain unchanged:61 modified tracked/101 grouped untracked/151 expanded untracked.
The corrected synthetic resume still requires **manual Chrome acceptance**; the
operator's original personal-looking-content observation is not conclusively traced.

## Volunteer Experience card discrepancy — 2026-11-09

The operator confirmed a resume update containing Volunteer Developer at Synthetic
Community Workshop, Jan 2026 - Mar 2026, HTML/CSS. Reopened preview/current profile
showed the correct experience, but Student Profile displayed Volunteer Experience:
Not set. Source tracing and a controlled mapping reproducer establish a frontend
display mismatch, not backend data loss.

| Field | Meaning and path through the application |
| --- | --- |
| experience[] | Structured roles with company, role, duration and technologies; extraction -> canonical profile -> explicit confirmation -> secured profile GET. The volunteer role is stored here. |
| additional_info.volunteer_experience | Separate optional manually supplied context. The Edit Profile select provides Yes/No; resume extraction does not fill it. It is not an ML feature. |
| flattened volunteerExperience | Reads only the manual additional_info field and feeds the existing edit state/payload builder. This mapping remains unchanged. |
| Student Profile Volunteer Experience card | Previously read only flattened volunteerExperience. Now uses a display-only presentation of explicit volunteer roles from the current raw profile, with the separate manual declaration shown if present. |

The minimal fix adds getVolunteerExperienceDisplay in
frontend/src/services/profileConfig.js and uses it in
frontend/src/pages/StudentProfile.jsx. It displays the observed role/company/dates/
technologies without writing or backfilling additional_info, inferring employment,
counting internships as volunteer experience or changing revisions/model form
inputs. Only explicit volunteer/volunteering role text is selected; a volunteer
company name or Non-volunteer role does not qualify. Missing details remain missing.
With both records and a manual declaration, the card shows recorded roles and
separately labels the self-reported value, including a conflicting No.

Related fields were checked: project/internship/certification/hackathon counts
already read their structural lists; skills combine the eight categories. General
experience details were not previously displayed by the card summary and remain
available in the structured review/editor. Open Source Contributions reads
ml_inputs.open_source_contributions, not achievements.open_source_contributions;
extracurricular model input is similarly separate from activity records. GitHub
repository/LinkedIn connection counts are manual additional_info values, not counts
inferred from social URLs. These deliberate source distinctions were preserved;
their presentation was not expanded or prediction inputs inferred in this fix.

Regression coverage: frontend/tests/volunteerExperienceDisplay.test.js adds15
cases for the exact reported record, missing/manual-only sources, contradictory
declarations, partial/multiple records, negative classification, profile switching,
unaltered editing/save payloads/model forms and other field sources. Existing
backend/tests/test_resume_extraction_mapping.py now additionally checks exact
confirmed/GET experience records and unchanged manual volunteering for both
PDF/DOCX, while retaining ownership, correction and revision assertions.

Current validation:44 relevant backend tests passed,0 failed/errors/skipped/
deselected,8 existing joblib/NumPy warnings,21.53s. Complete frontend231 passed,
0 failed/cancelled/skipped/todo,445.8751ms (deselection N/A). Lint passed; production
build passed75 modules/362ms with intentional outside-root/no-empty notice. The
complete backend suite was not rerun for this frontend display-only fix; the earlier
1171-pass full run is historical evidence, not a current full-suite claim.

Exact change inventory: modified frontend/src/services/profileConfig.js,
frontend/src/pages/StudentProfile.jsx, backend/tests/test_resume_extraction_mapping.py,
this feature document. Created
frontend/tests/volunteerExperienceDisplay.test.js. No backend
application, security/session/ownership/CSRF, model/dataset/calculation, schema,
dependency or historical record changes. No automated browser navigation.

Manual recheck remains pending: the demo launcher serves a production bundle, so
an already running launch has the earlier frontend build. Stop only that launch
with Ctrl+C, restart using the documented command, and use its fresh printed
workspace/resume path. After explicitly selecting/confirming experience, verify
the Volunteer Experience card shows Synthetic Community Workshop, Volunteer
Developer, Jan 2026 - Mar 2026 and HTML/CSS. Existing records were not edited or
backfilled by this display fix. Phase32 overall manual acceptance remains pending.

## Experience import shows blank editable inputs — investigation pending

The operator reported that selecting only **Use resume: experience** shows
Experience (1), with role/company/duration/technologies blank despite a correct
extraction preview. This observation remains **unresolved**. No application mapping
or state-initialization defect has yet been reproduced; no speculative source fix
has been made.

The current source path was traced through validateDraftFromResumeResponse ->
loadResumeReview -> mergeResumeSelection(current, draft, ['experience']) ->
applyReviewEdits(reviewBase, edits, false) -> ResumeEvidenceEditor. Record arrays
are retained, only the selected experience is imported, and the actual editor
binds entry.role/company/duration and the joined technologies list to its inputs.
The controlled reproduction yields all four expected values both in editor props
and server-rendered input markup. A public-static-only read at the documented
default loopback address also found the latest source labels/volunteer-display
code in the served bundle. The address of the actual failing tab remains to be
confirmed; this is not a complete diagnosis of its runtime state.

New frontend/tests/resumeExperienceEditor.test.js compiles the actual JSX editor
in memory with the already installed Vite/Oxc tool and renders it with React.
Eight regressions cover the exact API response/select-only-experience scenario
with existing, empty and blank current records,
all four populated input values, unchecked preservation, deselect/reselect,
correction callbacks/valid submission, missing fields and unrelated record values.
This closes the earlier helper-test coverage gap. Tests use fictional data and
mocked HTTP; they do not navigate Chrome, require a new dependency or validate
the live modal/browser event state.

Initial results:6 rendered-editor regressions passed in503.0755ms; complete frontend237
passed in934.0394ms. After adding the empty/blank starting-record cases, final
complete frontend239 passed in1011.003ms,0 failed/cancelled/skipped/todo (deselection N/A). Relevant
backend44 passed in24.64s,0 failed/errors/skipped/deselected,8 existing joblib/NumPy
warnings. Lint passed; production build passed75 modules/468ms with the intentional
outside-root/no-empty notice. Complete backend suite was not rerun; prior full
results remain historical evidence. Application/security/profile data/model/
prediction/dependency code is unchanged.

Required next diagnostic, with the blank fields visible **only in the isolated
synthetic demo**: confirm the launcher's actual Open URL/restart status and run
the following read-only command manually in Chrome DevTools Console. It reads
only these four form inputs, sends no requests, and changes nothing:

```javascript
JSON.stringify(['role', 'company', 'duration', 'technologies'].map(field => {
  const input = document.getElementById('evidence-experience.0.' + field);
  const key = Object.keys(input || {}).find(k => k.startsWith('__reactProps$'));
  return {
    field,
    domValue: input?.value,
    attributeValue: input?.getAttribute('value'),
    reactValue: key ? input[key]?.value : null,
  };
}), null, 2)
```

The values distinguish missing/overridden React state from DOM input differences.
React's internal props key is diagnostic only and is not an application API or
implementation dependency. Do not use this command on real student records.
Runtime results are pending; do not describe the blank-field bug as repaired or
Phase32 as complete merely because the controlled component regression passes.

Changed files:created frontend/tests/resumeExperienceEditor.test.js; modified
this document. Public bundle capture
and its hash are retained; no account/profile APIs or private browser storage
were queried. Its first command evidence wrapper refused to replace an identically
named child summary JSON (FileExistsError); the original summary/asset were
preserved and independently verified using distinct evidence filenames. No
application or regression test failed in these current checks.

## Live session and missing-editor investigation — 2026-11-09

The operator confirmed the failing URL is `http://127.0.0.1:5173/`. The
extraction contains the correct fictional volunteer role, company, duration and
HTML/CSS, but the editor appears blank after selecting experience. Chrome also
recorded two `/api/auth/session` 401s, and the earlier input diagnostic found no
matching elements. **The live root cause is not established; no application fix
or successful manual reproduction is claimed.**

Verified source behavior:

- `main.jsx` uses React StrictMode; `SessionApp` restores the session in an
  effect and revalidates it on window focus. In development, StrictMode can
  repeat the initial effect. The launcher serves a production build, so this
  alone does **not** explain two requests in the reported tab. Focus or separate
  page loads can also issue session requests; request timing is required.
- `GET /api/auth/session` requires the server-issued cookie. Missing/ambiguous,
  invalid, expired, revoked, wrong-context or account-invalid sessions receive
  the same safe 401. Its GET does not require CSRF. A transport/Origin rejection
  is 403, not evidence that these 401s were caused by a missing CSRF token.
  Cookie hosts `localhost` and `127.0.0.1` differ; ports do not isolate cookies.
  These are supported rejection scenarios, not a diagnosis of this tab.
- `authSession.restore` ignores superseded responses. An initial anonymous 401
  does not by itself explain a later blank authenticated review. A current
  background 401 clears authentication and increments the workspace epoch;
  `SessionApp` then renders Login instead of the provider/private workspace.
  The profile/modal subtree cannot remain mounted under that branch.
- `StudentProfile` renders its resume modal only when `resumeOpen`, not loading,
  and without an error except missing-profile onboarding. Navigation/profile
  switching also changes the parent. Which condition applied during the
  operator's DOM query remains unknown.
- Current selection/merge/editor code supplies all four known experience values.
  Input IDs have the exact form `evidence-experience.0.role`, `.company`,
  `.duration`, `.technologies`. An absent element cannot establish an empty
  React input value; it requires checking the document context and parent mount.

A public-only HTML/JS fetch from the reported loopback URL found a production
page and the same previously captured `index-BUzbCHXR.js` (407570 bytes,
SHA256 `b7783d25dbc4b9eb75b8447f91fe884d461d811e6b2dde1c675edb255c4a26df`).
The served code includes the editor IDs, field bindings and selection controls.
This checks the server asset; it does not inspect Chrome's mounted React tree,
prove the tab loaded that asset, or rule out a browser-context/lifecycle problem.
No authenticated API, cookie, historical record or private browser storage was read.

Direct browser inspection was unavailable. The connected document tool failed
with its own revoked connector OAuth token; this is **separate from PlacePro's
session 401s**. The browser tab-list action did not execute because automatic
approval review was interrupted (`content_filter`, incomplete review). It was
not determined unsafe, and no alternate browser access bypassed that review.
No navigation, login, form interaction or process termination was automated.

### Required manual runtime evidence

Keep the failing screen open before restarting or reloading. In the isolated
synthetic demo, manually run this read-only Chrome Console command and supply
its output, plus whether the session 401s occurred before login or during review.
It sends no requests and reads no cookies/passwords. The `topFrame`/`rootPresent`
fields help detect a Console execution context that is not the PlacePro document.

```javascript
(() => {
  const dialog = document.querySelector('[role="dialog"][aria-labelledby="resume-modal-title"]');
  const row = [...document.querySelectorAll('.resume-import-option')].find(el => el.querySelector('label')?.textContent.includes('Use resume: experience'));
  return JSON.stringify({
    page: location.origin + location.pathname,
    topFrame: window === window.top,
    frameCount: document.querySelectorAll('iframe').length,
    rootPresent: !!document.getElementById('root'),
    modalTitle: dialog?.querySelector('#resume-modal-title')?.textContent ?? null,
    loginVisible: !!document.querySelector('input[type="password"]'),
    experienceChecked: row?.querySelector('input[type="checkbox"]')?.checked ?? null,
    extractedRolePresent: row?.textContent.includes('Volunteer Developer') ?? false,
    controlsInModal: dialog?.querySelectorAll('input, textarea').length ?? 0,
    experienceControls: [...document.querySelectorAll('input, textarea')].filter(el => el.id.includes('experience')).map(el => {
      const key = Object.keys(el).find(k => k.startsWith('__reactProps$'));
      return { id: el.id, value: el.value, reactValue: key ? el[key]?.value : null };
    }),
    sessionRequests: performance.getEntriesByType('resource').filter(el => {
      try { return new URL(el.name).pathname === '/api/auth/session'; } catch { return false; }
    }).map(el => ({ startMs: Math.round(el.startTime), durationMs: Math.round(el.duration), status: el.responseStatus ?? null }))
  }, null, 2);
})()
```

Browser resource timing may omit cross-origin timings/status; absence/zero values
are not proof of a successful request. Use only the status and timing from the
relevant Network entries if needed, without sharing Cookie/Set-Cookie headers,
CSRF tokens, credentials or full HAR files. React's internal props key remains
an optional diagnostic, not an application dependency. Capture further selection
state only after this evidence identifies the actual mounted review.

### Regression and preservation checkpoint

Created `frontend/tests/resumeSessionGate.test.js` with 13 tests. These render
the actual SessionApp branch logic and StudentProfile parent conditions in memory
with test-only snapshot/context/leaf probes, and exercise real auth/transport
generation handling with mocked HTTP. Coverage includes duplicate initial 401s,
login after denial, late/superseded failures, successful background restoration,
active-session invalidation, pending extraction rejection, preview 401, temporary
service failure and modal open/loading/error/missing/closed parent conditions.
These are **not** live DOM, full modal event/state or React mount/unmount tests.
The earlier eight real-editor render tests still cover populated experience values,
unchecked preservation and corrections, but do not reproduce the live report.

Current focused frontend: 21 passed, 0 failed/cancelled/skipped/todo, 546.323 ms.
Complete frontend: 252 passed, 0 failed/cancelled/skipped/todo, 1044.8849 ms.
Relevant resume backend: 44 passed, 0 failed/errors/skipped/deselected, 8 existing
joblib/NumPy warnings, 25.18 s. Targeted session backend: 8 passed, 0 failed/errors/
skipped/deselected/warnings, 7.57 s. Lint passed. Production build passed, 75
modules, 470 ms, with the intentional outside-root/no-empty notice. Build used a
new retained directory and did not replace the running demo bundle. The complete
backend suite was not rerun; prior full-suite results remain historical evidence.

Changed only this feature document and append-only knowledge; added the session
gate test. Application, authentication,
ownership, CSRF, revisions, models, datasets, calculations, dependencies and
historical records are unchanged. **Phase32 manual acceptance and the blank-field
investigation remain pending the Chrome runtime evidence.**

## Phase 32 real browser investigation — 2026-11-09/10

This entry supersedes the earlier browser-access limitation for the **fresh
reproduction**, not the unresolved findings in the operator's original tab.
The agent-browser CLI was unavailable; the installed Playwright browser tools
successfully navigated the actual running application in isolated contexts.

The unchanged interactive `scripts/demo.py` launcher refused both default-port
attempts with Windows error 10048. Its exact `free_port` checks subsequently
also failed for 5173 and 8765; listener queries did not identify their owner.
Nothing was stopped or reconfigured to force those ports. The actual demo used
`--api-port 8766 --frontend-port 5174`, generated fresh external temporary storage
and a fresh production build. The hidden password prompts were used normally.

Observed sequence: open `http://127.0.0.1:5174/`; sign in as
`demo-student-a@example.test`; open the Student Profile link; click Update from
Resume; upload this launcher's generated `Synthetic-Resume.docx`; click Upload
& Extract; inspect the owned resume-preview response and extracted experience;
check only Use resume: experience; inspect the actual controls and React tree.
The browser tool could not stat the external temporary upload directly, so a
byte-identical copy was placed in the investigation's scratch directory.

**Result: the blank editor was not reproduced.** The real API returned Volunteer
Developer, Synthetic Community Workshop, Jan 2026 - Mar 2026, HTML/CSS. Selecting
only Experience rendered `Experience (1)` and four visible enabled inputs:
`evidence-experience.0.role`, `.company`, `.duration`, `.technologies`. Their
DOM properties, value attributes and React value props held all four expected
values. Inputs have no name attribute; labels are Experience 0 role/company/
duration/technologies. They are inside the Experience 1 fieldset in the modal.

`ResumeUploadModal` held step=review, the complete extracted draft,
selectedFields=[experience], edits={}, mounted.current=true. Its preserved
base profile correctly still had experience=[] at revision 1. That empty stored
list does not replace the selected extraction. `ResumeEvidenceEditor` received
the extracted list through its profile prop and has no separate experience
useState. A passive test-only React commit observer confirmed the provider,
StudentProfile, modal and editor mount once, stay mounted through corrections,
deselection/reselection and a valid background restoration, then unmount only
when the deliberately revoked session was rejected.

Trace: resume_parser.parse_resume/_extract_dated_entries ->
profile_service.prepare_draft_with_analysis/_draft_from_extraction ->
OwnedProfileService.preview_resume (authorization/revision checks before and
after extraction) -> owned_profile.resume_preview ->
api.analyzeResumeForReview/validateDraftFromResumeResponse -> loadResumeReview ->
ResumeUploadModal.handleUpload -> draft/extractionInfo -> selection onChange ->
mergeResumeSelection(baseProfile,draft,selectedFields) ->
applyReviewEdits(reviewBase,edits,false) -> ResumeEvidenceEditor.profile -> inputs.
There was no observed point where selected experience disappeared. Uploading
an existing-profile preview does not call onDraftCreated or save/refresh the
profile. Confirmation remains disabled without the explicit acknowledgement.

In the initial uninstrumented workflow, exactly **one** session request was
observed: mount restoration before login, no cookies, backend 401 Authentication
is required. The later controlled regression independently inspected a mount
restoration and a deliberately dispatched anonymous focus restoration: both
GETs to the correct API origin had no Cookie header and received that same
missing-cookie gate response. They are separate triggers, not duplicate mount
effects. Neither removed an authenticated profile, because login had not occurred.
A valid background restoration carried the unblocked HttpOnly Lax
placepro_dev_session cookie for 127.0.0.1, path /, to port 8766 and returned 200;
the same editor nodes, selected state and authentication epoch survived.
Cookies are host/path scoped, not port scoped. A separate real logout then
revoked the test session; the first consumer retained the cookie, sent it to
the same API, received 401, transitioned to anonymous with an incremented epoch,
showed Your session has expired. Sign in again., and unmounted the private tree.
This is evidence about those captured test requests, **not identification of
the original tab's two requests**, whose initiators, cookies and timing remain
unavailable. The original manual diagnostic above is still useful for that tab.

No application correction is justified by this evidence and none was made. Added a real browser regression and backend idle-expired/absolute-expired/revoked
session tests; existing component regressions supplement them. All browser
scenarios pass on unchanged application code, so no fail-before/pass-after
claim is made. See `frontend/browser-tests/README.md` for execution and security
details.

Validation for this entry: focused component/session frontend tests 21 passed;
focused backend 205 passed (including three new session-denial cases); full
backend 1174 passed with 10 existing NumPy/joblib shape-deprecation warnings;
full frontend 252 passed; lint, production build and the existing PowerShell
startup/dependency/model checks passed. Browser scenarios are separate from the
Node suite and all six passed. The first new backend run had three fixture-setup
errors because encoded_password was not imported; that test-only import was
corrected and the failure log retained. An early diagnostic observer labelled
other useAuth consumers as SessionApp; its predicate was tightened, and the
verified lifecycle artifact shows one SessionApp mount and no SessionApp unmount.

After switching between test contexts, a later revisit of the initial tab found
no modal, no new session requests, and still-authenticated state at epoch 2 with
AppContent.resumeProfileOpen=false. Its close trigger was not captured. This is
an absent-modal observation, not a reproduction of Experience (1) with blank
fields. Reopening/uploading/selecting Experience in that same tab again rendered
all four values; the recorded synthetic fieldset observation captures the actual fieldset.

The historical preservation check reported no changes to protected project
files. Temporary process identifiers and private operational receipts are omitted.
That run used targeted forced shutdown; it did not establish graceful shutdown.


### 2026-11-10 -- Phase 32.1 modal lifecycle investigation -- completed

This entry supersedes the earlier conclusion that no application defect was confirmed, for the two controlled lifecycle/stacking defects below. It does not retrospectively identify the trigger in the operator's uncaptured original tab or claim reproduction of a still-mounted Experience (1) editor with four blank values.

**Confirmed defects and corrections.** Profile-list revalidation previously set `listLoading` even when an authoritative profile was already loaded. `useStudentProfile.loading` treated this background refresh as an initial load. StudentProfile's `!loading` modal condition then unmounted the resume review; remounting kept the parent open flag but reset the modal to Upload and discarded unsaved selection/corrections. The real list response was held and forwarded unchanged: before correction, dialog absent/0 controls during the request, reopened dialog/0 controls afterwards, different nodes; after correction, 4 controls during and afterwards, identical dialog/input nodes, correction retained and authentication unchanged. `frontend/src/hooks/useProfile.js` now reports initial `loading` only without `rawProfile`, and reports `refreshing` when valid profile data is present. Existing authorization/error/identity/revision guards remain intact.

The modal previously lived inside `.app-body`, which creates a stacking context at z-index 1. Its overlay z-index 3000 could not escape that ancestor to compete with the navbar at z-index 1000. At the Close button's actual coordinates, `elementFromPoint` returned `navbar-user-trigger`; a pointer click was intercepted even though keyboard activation could close the dialog. `ResumeUploadModal` now uses `createPortal(..., document.body)`, placing its overlay above the navbar. Retained pointer-before/after evidence changes from receivesPointer=false/navbar interception to true. No global stacking rewrite was needed. Explicit Close/Cancel/backdrop/Escape, confirmation and navigation retain their existing busy-state restrictions and callbacks.

**Final code review.** Reviewed the full current hook, modal, App, provider/page conditions, profile/owned-profile controllers, auth/transport behavior, CSS stacking contexts, diagnostic call sites and relevant callers/tests. Verdict APPROVE, confidence HIGH; no P0/P1 findings in the two corrections. the historical scoped-diff review retains the Git diff against HEAD (which also includes earlier integration work); Phase 32.1 baseline hashes identify the scoped existing-file changes. Current API/authentication, CSRF, ACTIVE ownership, revision, retry, extraction and model protections were neither changed nor weakened. All 63 baseline backend application files are byte-identical.

**Browser regression evidence.** The five final recorded browser repetition runs passed, each observing 15 seconds idle, all four visible editable Experience controls, preserved corrections while open, an explicit close, navigation away/back without reopening, unchanged stored profile and a real session 200. Runs 1/2/5 use Close, run 3 Escape, run 4 backdrop. Pointer hit testing separately verifies the Close button receives pointer events. refresh observation, tab-return observation, cancel observation, confirmation observation and logout observation retain successful refresh, tab return, Cancel, real confirmation and real UI logout. Delayed real extraction and confirmation responses were paused after actual requests, then released after a newer modal opened; stale-extraction observation and stale-confirmation observation show `*.ignored` with reason unmounted and the newer modal preserved. No synthetic successful HTTP response replaced the backend. CDP response pausing avoids replaying a file upload through route.fetch, which can omit its binary body. Focus/refetch stimuli were deliberate test actions, not proof of the original tab's initiators.

**Fresh session security succeeded.** the historical fresh-session security summary contains six passing checks: two independent anonymous denials, real parser/preview and four values, editing with mandatory acknowledgement, deselect/reselect with unchanged stored data/revision, valid background restoration with identical nodes, and genuine server revocation with sign-in notice and private-tree unmounts. Its session responses are 401,401,200,401; cookies absent for both anonymous requests, present for valid restoration and retained-but-revoked restoration. Cookie metadata records only name/domain/path/flags/blocked reasons, never values. The final revoked request received the generic authentication-required denial, cleared account state and incremented the auth epoch; StudentProfileProvider, StudentProfile, ResumeUploadModal and ResumeEvidenceEditor unmounted. Real CSRF-protected logout in a second synthetic consumer revoked the session; no fake 401 supplied this evidence. The separate UI logout run received real 204 and removed AppContent/modal.

**Earlier deselection failure was a harness/setup issue.** the historical deselection-test summary retains the failed assertion "Deselection must restore the empty stored list." That scenario reused the corrected demo after the successful confirmation/stale-confirmation scenarios. Its owned profile `[isolated synthetic profile]` is revision 2 with one saved Experience record, confirmed by the real confirmation artifacts and retained isolated profile JSON. Deselecting correctly restores that stored record; expecting no input was invalid for that fixture. The new `placepro_demo_ss9febwe` fixture has empty revision-1 profiles and its fresh six-check run passed. The browser harness now asserts the captured stored Experience list, record count and four DOM values rather than assuming an empty list. Its revised source passed syntax/lint checks; that generalized harness was not rerun against another live browser after this final test-only edit. Existing real-editor regressions cover both nonempty and empty stored lists. No application or authorization change was made to satisfy the failed assertion.

**Diagnostics are opt-in and development-only.** Final `resumeDiagnostics.js` requires `import.meta.env.DEV === true` and `VITE_RESUME_DIAGNOSTICS === '1'`; the earlier explicitly flagged synthetic-production exception was removed. Production stays silent even with both diagnostics and synthetic flags set. All trace call sites pass fixed lifecycle/event/source/reason metadata, profile identifiers, boolean states or numeric status; none pass resume text/fields, files/names, HTTP bodies/headers, cookie values, tokens, passwords or exception messages. `safeResumeDiagnostic` permits only named primitive metadata, not arbitrary keys/objects; the logger reads only auth status/epoch, uses no persistent storage/network sink and caps its in-memory record list at 1000. The final environment-matrix test executes the actual module in memory, verifies disabled variants need no browser globals, enabled output excludes secrets, and the cap works. The flagged synthetic production bundle contains none of `__placeproResumeDiagnostics`, `[PlacePro resume]`, `modal.state`, `extraction.ignored`. Test-only React/CDP observers remain in browser harnesses/isolated synthetic documents; they are not injected by application code. Historical diagnostic bundles/evidence are retained for preservation, but their servers are stopped. Future diagnostic runs must use an opted-in development server with isolated synthetic storage.

**Validation (overlapping runs, no suppressed failures).** Original Phase 32.1 backend-focused run: 186 passed, 8 existing joblib/NumPy warnings, 85.87 seconds. Original full backend: 1,174 passed, 0 failures/errors/skips/deselections, 10 existing shape-deprecation warnings, 369.20 seconds (the historical full-backend result). Original focused frontend: 44 passed; original complete frontend: 254 passed, zero failures/cancellations/skips/todos, 854.2465 ms. Original lint/build and startup/dependency/model smoke checks passed. The current continuation has no backend edits and therefore reuses the confirmed full backend result; new focused actual API denial/revocation/recheck validation passed 8/8, zero failures/errors/skips/deselections/warnings, 51.06 seconds (the historical focused-security result). Two additional Node parent/controller tests prove 403/404 ownership denial after an accepted profile clears data, removes the private resume modal and avoids false missing-profile onboarding. The diagnostic environment test adds one case. Final focused frontend: 47/47, zero failures/cancellations/skips/todos, 3791.559 ms. Final full frontend: 257/257, zero failures/cancellations/skips/todos, 6308.6139 ms; Node deselection is not applicable. Final lint exit 0; final production build exit 0, 76 modules, 2.79 seconds, fresh retained output with emptyOutDir=false. Build was deliberately run with both flags set to prove production logging exclusion. Exact argv/stdout/stderr/elapsed/exit are retained in the completion JSON files.

**Shutdown.** The Phase 32.1 temporary demos `placepro_demo_mtqpgqvv`, `placepro_demo_rfwnd4tb`, `placepro_demo_ss9febwe` have no live matching process in the final read-only Win32 query; recorded backend PIDs 44416/32396/32552 are gone. Prior Phase 32 PIDs 37216/39440 are also gone. Ports 5174/5175/5176/5177 and 8766/8767/8768/8769 reject connections and all pass exclusive loopback binding. All 19 files in each of the three Phase 32.1 demo workspaces remain byte-identical to continuation entry. These demos have no "Application shutdown complete" log, so graceful shutdown is not claimed. No process was terminated by this continuation. The older default-port demo `placepro_demo_ljbnb780`, with launcher chain 20728 -> 19204 -> 11092 -> 35180 on 5173/8765, is unrelated to this investigation and was left running. Windows denied the sandboxed CIM metadata query; the required read-only escalation succeeded and its final result is retained in the historical owned-process check. This is evidence of ownership/shutdown, not authority to stop the unrelated demo.

**Historical preservation:** The recorded check retained protected files and
prior work. Private path inventories, process details and journal-byte receipts
are omitted; this is not a new release verification result.

**Remaining limits/failures.** The earlier failing deselection log remains retained and explained; the fresh browser security replacement passed. The reported original manual-tab trigger/two 401 initiators and any still-mounted blank-field symptom remain unobserved. No new browser HTTPS/public-deployment/load/email-provider or long wall-clock expiry test is claimed; controlled expiry tests use existing isolated fixture clocks. Browser internal React/CDP probes are diagnostic harness assumptions; real DOM values/real requests remain the behavior evidence. Generalized deselection-harness changes were syntax/lint verified only after the saved fresh pass. Graceful shutdown logs are absent for the interactive demos. Existing 10 full-backend dependency deprecation warnings remain. Auxiliary read-only PowerShell output serialized annotated strings noisily; file-based Python summaries replaced it. A Windows rg wildcard pathname was rejected and corrected with a glob search; no application or data operation failed. No outstanding focused suite failure remains. Phase 32.1 completion does not start a later phase.


**Historical completion receipt:** Preservation was recorded at that phase.
Current release acceptance still requires its own checks; no new browser, Linux
or Docker success is asserted by this documentation update.
