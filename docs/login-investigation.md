# PlacePro login security and focus investigation — 2026-11-21/22

> Historical snapshot: the original phase dates, design decisions and recorded
> test results below are preserved. Statements about the then-current inventory,
> unavailable features and pre-authentication behavior are superseded by the
> [reviewed 2026-11-24 release snapshot](../backend/DEPLOYMENT.md#reviewed-release-snapshot-2026-11-24).
> This documentation change reruns no application tests and establishes no new
> Linux/Docker or browser acceptance.

The supplied development configuration reproduces the security failure because
`localhost` and `127.0.0.1` are different cookie sites. The confirmed email-loss
path is a Login component remount during anonymous background session validation.
The focused frontend corrections and the specified regressions are implemented.

## 1. Login failure: exact cause and complete flow

Before correction, the frontend at `http://localhost:5173` sent requests to
`http://127.0.0.1:8000`. Development mode and both allowed frontend origins were
configured exactly as reported.

| Stage | Observed behavior |
| --- | --- |
| Anonymous session restoration | GET `/api/auth/session` returned 401 without a session cookie; this is the expected anonymous result. |
| Bootstrap CSRF acquisition | GET `/api/auth/login-challenge` returned 200 and a 64-character hexadecimal CSRF token. Login correctly uses this bootstrap endpoint. GET `/api/auth/csrf` requires an authenticated session. |
| Challenge cookie creation | The response set `placepro_dev_login`: host-only `127.0.0.1`, path `/`, HttpOnly, SameSite=Lax, Secure=false, Max-Age=300. Chromium explicitly blocked it with reason `SameSiteLax`. |
| Login request | POST `/api/auth/login` included Origin `http://localhost:5173`, Content-Type `application/json`, and X-CSRF-Token. Fetch used `credentials: include`. No Cookie header was sent. |
| Origin/transport/CORS | The configured Origin was accepted. The response allowed that explicit origin and credentials. Development loopback transport was accepted. |
| Backend denial | `SessionRoute` invokes `SessionService.begin_login` before credential verification/body parsing. `single_cookie` returned no challenge secret; `valid_secret(None)` failed and raised InvalidCSRF. The response was 403 `{ "detail": "CSRF validation failed." }`. |
| Frontend handling | `jsonRequest` mapped 403 to `Security check failed. Refresh the session and try again.` |
| Unchanged control | With frontend `127.0.0.1:5173` and API `127.0.0.1:8000`, challenge/login/session/CSRF succeeded. The cookie was present and unblocked. |

The CSRF header alone cannot validate a challenge: the backend also needs the
HttpOnly cookie that identifies the stored challenge and its HMAC nonce. The
failure happens before password verification. Cookie path and development Secure
attributes were correct; permitting both origins does not override SameSite.
Cookies belong to hosts, independently of ports.

The correction changes only HTTP loopback URL selection in Vite development.
The configured API port and base path are retained; its hostname follows the
page's `localhost` or `127.0.0.1` hostname. Thus the supplied `.env.local` still
contains `VITE_API_BASE_URL=http://127.0.0.1:8000`, while a localhost page requests
`http://localhost:8000` from the same backend. Production, HTTPS and external
destinations retain their explicitly configured URLs. Vite configuration and
environment files were preserved.

Normal successful authentication remains: Argon2id credential verification,
ACTIVE/verified account checks and version rechecks; transactional single-use
challenge validation and opaque session creation; host-only HttpOnly session
cookie; safe account/expiry response; frontend validation and request identity
acceptance. Session restoration still validates that server cookie. Session-bound
CSRF is obtained for authenticated mutations, and stale request/identity guards
and server revocation remain intact.

## 2. Email loss: confirmed cause and evidence boundary

`SessionApp` registers a window focus listener that calls
`authSession.restore({ background: true })`. Previously, the restore method
published `restoring` whenever the current state was anonymous. `SessionApp`
then rendered its restoration placeholder, removing Login. The real anonymous
GET returned 401, and the subsequent anonymous render mounted a new Login whose
email state started as an empty string.

The controlled browser focus test captured `anonymous -> restoring -> anonymous`,
a disconnected original input and a replacement input, unchanged URL and
`performance.timeOrigin`, and no Vite reload/disconnect event. This was a
component remount within the same document. Login has no reload/blur/visibility
handler; native form submission is prevented. Assessment timer visibility/focus
listeners are outside the anonymous Login tree. Demo copy-button feedback does
not navigate or reset the parent. Development StrictMode can repeat initial
restoration effects; it does not itself cause a document reload on tab return.

The installed Vite client reloads documents for full-reload messages and successful
reconnection after a lost server connection. Its visibility listener assists
reconnection polling. No such reload was observed during this reproduction.

Native tab activation did not deliver observable focus/visibility events in the
automation session, including after disabling Playwright's focus emulation.
The focus stimulus is therefore explicitly labelled as controlled. The original
physical-browser tab event and any separate historical document reload remain
uncaptured. The confirmed application handler path is sufficient to reproduce
the remount; no Vite behavior was changed on an assumed cause.

Background validation now keeps the settled anonymous Login mounted. The real
session request and its 401/403/error handling still run. Invalid authenticated
sessions still remove the private UI.

Login immediately records only its bounded email text under
`sessionStorage['placepro_login_email:v1']`. Independent Login mounts restore it;
storage denial falls back to memory. Password and confirmation fields remain
component state and initialize empty on a remount/reload. Validated server
authentication clears the draft centrally, including successful session
restoration. Invalid credentials retain the email. Independent tabs have
independent email drafts. Full reload recovery requires available sessionStorage;
the memory fallback covers remounts when storage is unavailable.

## 3. Files inspected

Read or searched these relevant files before their corresponding changes:

Phase 32 and 32.1 records were present; no Phase 32.2 entry was found in knowledge. The user's login scope governs this continuation. - Frontend configuration and lifecycle: `frontend/.env.local`,
  `frontend/.env.example`, `frontend/vite.config.js`, `frontend/package.json`,
  `frontend/eslint.config.js`, `frontend/src/main.jsx`, `frontend/src/App.jsx`,
  `frontend/src/hooks/useAuth.js`, `frontend/src/hooks/useTestTimer.js`,
  `frontend/src/services/auth.js`, `frontend/src/services/apiTransport.js`,
  `frontend/src/pages/Login.jsx`, `frontend/src/components/DemoCredentials.jsx`,
  `frontend/src/components/Navbar.jsx`, `frontend/src/components/ProfileDropdown.jsx`. - Backend flow: `backend/app/main.py`, `backend/app/routes/auth.py`,
  `backend/app/security.py`, `backend/app/schemas_auth.py`, and services
  `security_config.py`, `session_service.py`, `session_store.py`,
  `account_service.py`, `account_store.py`, `password_service.py`, `dev_account.py`. - Existing tests/tooling: frontend `authentication.test.js`,
  `resumeSessionGate.test.js`, `browser-tests/README.md`, `resumeBuilder.cdp.mjs`;
  backend `test_session_security.py`, `test_sessions.py`, `support.py`,
  `conftest.py`, `secure_http_server.py`; installed Vite client reload and
  visibility code. Final source/test changes were also inspected.

Git branch/status and existing diffs were inspected first. No repository or
ancestor AGENTS.md was found. Agent-browser was unavailable; the Playwright
connector refused isolated tab creation under its `never` approval policy.
Prepared local Chromium tests ran through the workspace permission flow using
existing installed tooling. No dependency installation was needed.

## 4. Files modified or added by this task

| Path | Change |
| --- | --- |
| `frontend/src/services/apiTransport.js` | Development HTTP loopback hostname alignment; transport/CSRF/identity guards retained. |
| `frontend/src/services/auth.js` | Preserve settled UI during background restoration; clear email after validated authentication. |
| `frontend/src/pages/Login.jsx` | Restore/write email draft; clear visible email after success. |
| `frontend/src/services/loginEmailDraft.js` | Added bounded tab email storage with memory fallback. |
| `frontend/tests/loginRecovery.test.js` | Added actual transport/environment, Login mount and auth-state regressions. |
| `frontend/tests/loginEmailDraft.test.js` | Added partial input, clearing, bounds and storage-denial regressions. |
| `backend/tests/test_login_cookie_boundary.py` | Added pre-credential cookie/CSRF/Origin rejection and both development-host flows. |
| `frontend/browser-tests/loginRecovery.browser.js` | Added real browser, session, CSRF, reload/remount and persistence regression. |
| `frontend/browser-tests/README.md` | Added execution/evidence notes for the login regression. |
| `docs/login-investigation.md` | This report. |

The isolated backend used fresh temporary test storage, not the repository's
accounts/profiles/assessments. No backend implementation, environment, credential,
ownership, prediction, salary, model, dataset, dependency or existing UI styling
was changed. Existing user changes were preserved; nothing was staged or committed.

## 5. Security impact

CSRF, strict Origin validation, CORS, challenge validation/expiry/attempt limits,
opaque server sessions, account status/version checks, revocation and cookie
attributes are unchanged. Production URL selection is unchanged. The explicit
cross-site test still fails with 403, and a missing token remains denied.
Passwords, authentication flags and tokens are never stored in the new email
draft. The draft provides input recovery and grants no authentication or ownership.

## 6. Tests and results

| Verification | Result |
| --- | --- |
| Existing focused frontend auth/session gate baseline | 38 passed. |
| Existing focused backend security baseline | 10 passed. |
| New frontend regressions before correction | 8 passed, 7 expected failures confirming the identified causes/missing recovery. |
| Focused corrected auth/lifecycle regressions | 53 passed; four additional email-storage tests passed. |
| New backend cookie-boundary tests | 6 passed. |
| Full frontend `npm.cmd --prefix frontend test` | 356 passed; zero failed/cancelled/skipped/todo. |
| Relevant backend authentication suites | 282 passed; zero failures/errors/skips or warnings reported. |
| Real Chromium browser regression | 20 scenarios passed: 10 on localhost and 10 on 127.0.0.1. |
| Frontend lint, including final browser harness | Passed. |
| Production build to fresh task output | Passed; 95 modules. |
| Final browser script syntax check | Passed. |

Browser coverage includes tab activation; controlled focus/blur/visibility events
with held real requests; input-node preservation; full document reload; forced
real component remount; email recovery and password absence; invalid credentials;
missing-CSRF/cross-site denials; valid login/challenge consumption; session/CSRF
acquisition and restoration; real UI logout and retained revoked-cookie rejection;
independent tab drafts. No successful API response or security proof was mocked.
Unit/controller tests use explicit synthetic HTTP fixtures as labelled.

Exact commands/output are in the task's JSON evidence. Main commands:

```powershell
node --test frontend/tests/loginRecovery.test.js frontend/tests/authentication.test.js frontend/tests/resumeSessionGate.test.js
node --test frontend/tests/loginEmailDraft.test.js
.\.venv\Scripts\python.exe -B -m pytest backend/tests/test_login_cookie_boundary.py backend/tests/test_authentication.py backend/tests/test_dual_authentication.py backend/tests/test_dev_student_login.py backend/tests/test_session_security.py backend/tests/test_sessions.py -q -p no:cacheprovider
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run lint
```

The Python commands used the existing workspace `.venv` interpreter. The browser
command requires this task's owned temporary server/run ID. Preliminary native
focus timeouts, a Vite module-URL synchronization issue and an outdated logout
selector were harness failures, retained in the historical harness-failure summary;
they are not counted as passing browser runs. A Python evidence wrapper initially
could not print Unicode test symbols; its saved Node result was already 38/38
passing, and the wrapper encoding was corrected.

## 7. Remaining issues and scope limits

No specified login/persistence regression remains failing. Validation used isolated
synthetic accounts. The original native window-focus event and any genuine
historical Vite document reload were not captured. Establishing such a separate
reload requires its navigation/document request and Vite websocket/console trace;
no speculative reload suppression was added. Email recovery after an actual
reload was verified independently.

The full backend domain suite was not rerun because backend implementation did
not change. The journal's separate concurrent-profile-update 503 remains outside
this task.

Preservation verification passed: all 12,352 original inventoried files remain;
the current inventory has 12,358 files. Only the five listed existing files changed
and the six listed files were added. All other original hashes match, including
backend implementation, data/models, prediction code and configuration. The
complete preceding 654,467 knowledge bytes remain an exact prefix. All 291
original expanded Git entries remain. Branch `bhargav-frontend`, HEAD
`f84099349d104e4e77c7080fba4465ca4e3470a4` and the empty staged diff are unchanged.
The final status has 65 modified tracked files and 232 expanded untracked files;
these totals include the extensive pre-existing work. `git diff --check` passed
with existing LF/CRLF notices only. A final after-documentation audit rechecks
these assertions in the recorded preservation check.

The final browser contexts were closed. The verified temporary backend PID 35316
and Vite PID 45284 were stopped; neither process nor a listener on 8000/5173
remains. Stdin had been closed by the execution tool, so the prepared graceful
stop could not be delivered. The first non-interactive PowerShell stop raised a
NullReferenceException; the approved `Stop-Process -Force` succeeded. Graceful
shutdown is not claimed. the recorded shutdown check retains the verified result. No original
application server was stopped or replaced, and all temporary evidence/storage
was retained.
