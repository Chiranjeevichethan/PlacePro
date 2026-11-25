# Resume experience browser regression

> Publication refresh (2026-11-24): current capabilities, 50 operations/45 paths,
> required artifacts and verification boundaries are summarized in the
> [reviewed release snapshot](../../backend/DEPLOYMENT.md#reviewed-release-snapshot-2026-11-24). Earlier dated results remain historical;
> no new application tests, browser acceptance or Linux/Docker success are claimed.

`resumeExperience.browser.js` is a Playwright page-function regression against
the real frontend and secured API. It is deliberately separate from
`npm test`, whose Node tests cannot navigate a browser. No dependency or package
script is added. The installed Playwright browser tool executes this function
with `browser_run_code` using `filename`.

1. Start the interactive `scripts/demo.py` launcher using the existing
   validated Python environment. Use its printed URL and generated DOCX. Never
   use historical storage or an account outside the synthetic demo.
2. Open a **new isolated browser context**. Read the new workspace's
   `demo-workspace.json` to obtain its `run_id`.
3. In the browser tool's page-function context, set `page.__placeproDemo` to an
   object with `url` (frontend origin, no trailing slash), `api` (API origin),
   `runId`, `resume` (accessible path to that generated file), `password` (chosen
   synthetic password), and `screenshot` (a new evidence file path). Keep the
   password in memory; do not put it in a file, report, browser storage or HAR.
4. Execute `resumeExperience.browser.js` through the browser tool's `filename`
   argument. Assertion failures throw. Preserve the returned redacted evidence.
   The test checks the demo run identity and refuses a context with cookies.
5. Close only the contexts and launcher created for this test. Retain artifacts.

The six scenarios cover anonymous denial, generated-DOCX extraction and all
four controlled experience values, explicit editing/confirmation, selection
transitions without saving, valid session restoration without unmounting, and
real server revocation with a visible sign-in notice and private-tree unmounts.
They use real login challenges, passwords, HttpOnly sessions, CSRF and ownership.
No HTTP response is mocked. For the revocation test a second isolated consumer
receives the already authenticated synthetic cookie and performs the actual
CSRF-protected logout; the first consumer retains its now revoked cookie.

Focus events are deliberately dispatched to exercise the existing focus handler.
They do not claim that the operator's original two 401s came from that handler.
The passive React diagnostic hook observes committed trees and the actual modal
state; it is confined to the fresh test document and never changes application
props, state or rendering. DOM/value assertions remain the rendering oracle.

The reported blank-editor failure was **not reproduced** in the recorded
2026-11-09/10 investigation. These tests pass on unchanged application code;
they are coverage for the expected behavior, not proof of a correction.

## Phase 32.1 lifecycle follow-up (2026-11-10)

The earlier unchanged-app conclusion above is historical. Phase 32.1 confirmed
and corrected two separate defects: background profile-list revalidation
unmounted/reset the resume review, and navbar stacking intercepted its Close
button. The loading/refreshing distinction and body portal fix these defects. Five final browser repetitions, refresh/pointer checks, delayed real extraction
and confirmation responses, real UI logout, and a fresh six-scenario session
security run passed.

The earlier deselection failure reused a profile already updated by the
confirmation scenario. It incorrectly assumed stored Experience was empty.
`resumeExperience.browser.js` now compares deselection with the captured stored
list and DOM values, supporting both empty and nonempty profiles. This final
harness generalization was syntax/lint checked; the saved fresh security pass
predates it. No new live-browser execution of the generalized harness is claimed.

`resumeModalLifecycle.browser.js` operates on an already authenticated isolated
synthetic page. Set `page.__resumeConfig` to `{ api, runId, resume, evidence,
operation, idleMs }`; no password belongs in that object. Supported operations
include repeat, pointer, refresh, cancel, confirm, logout, stale-extraction and
stale-confirmation. It holds real responses without substituting their bodies;
mutating scenarios must use disposable synthetic records and the real security
controls. The lifecycle script depends on opt-in application diagnostics.

Final application diagnostics require **development mode** and
`VITE_RESUME_DIAGNOSTICS=1`. All production builds remain silent even with that
flag. The launcher now runs an owned loopback Vite development server with
isolated cache/log paths; its default diagnostics remain off. This validates
development rendering, not an HTTPS production bundle. To rerun diagnostic cases,
use an isolated development frontend at the secured backend's configured allowed
origin; a production bundle will not provide the diagnostic events. The
experience/session browser harness uses its own test-document observer and
does not depend on production application logging. Never inject these observers
into a real account or retain private resumes/authentication secrets in artifacts.

For `resumeBuilder.cdp.mjs`, set `PLACEPRO_DEMO_CDP_URL` to the
`http://127.0.0.1:<port>/json/version` endpoint of a browser you launched for
this test with a new isolated user-data directory. There is no fixed CDP port.
The endpoint must be loopback and contain no credentials, query or fragment.
Keep `PLACEPRO_DEMO_TEST_PASSWORD` only in the process environment, never in
command arguments, artifacts or logs. Close only the browser/processes created
for this test. Chromium and Node must already be installed; this harness does
not install or attach to an operator's normal browser session.

## Login cookie and email recovery regression

`loginRecovery.browser.js` is a page-function regression for the real Vite
development frontend and secured API with disposable existing test fixtures.
Use a fresh isolated browser context and set `page.__placeproLogin` to
`{ url, api, expectedApi, runId, email, password }` in memory. `expectedApi` uses
the frontend's loopback hostname and the configured backend port. The function
verifies `X-PlacePro-Test-Run-ID` and refuses a context with existing cookies.

It checks tab activation, controlled focus/blur/visibility handlers with held
real session requests, full document reload and an actual Login remount, email
recovery, password non-persistence, invalid/valid login, missing-CSRF/cross-site
denials, session restoration, CSRF acquisition, real UI logout, retained revoked
cookies and independent tab drafts. Response bodies are not substituted. Its
forced remount uses the exact authentication module URL loaded by App, including
any Vite HMR timestamp. The current Logout control is a native button.

The recorded investigation passed all ten scenarios at each frontend origin:
`http://localhost:5173` and `http://127.0.0.1:5173`. Native focus delivery was not
observable under automation, so the focus-handler stimulus is explicitly
controlled. Document/node identity distinguishes remounts from reloads. The
implementation, commands, redacted evidence and limits are documented in
`docs/login-investigation.md` and the appended historical phase report.
