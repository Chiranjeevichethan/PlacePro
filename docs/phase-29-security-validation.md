# Phase 29 final integration and security validation

> Historical snapshot: the original phase dates, design decisions and recorded
> test results below are preserved. Statements about the then-current inventory,
> unavailable features and pre-authentication behavior are superseded by the
> [reviewed 2026-11-24 release snapshot](../backend/DEPLOYMENT.md#reviewed-release-snapshot-2026-11-24).
> This documentation change reruns no application tests and establishes no new
> Linux/Docker or browser acceptance.

Phases 29.6.7, 29.6.8 and 29.6.9 are completed within the existing backend
restrictions. This validates the implemented foundation; it does not certify
public deployment, email activation or every possible attack/load scenario.
No later phase or unrelated product-development work was started.

## Implementation and API behavior

Real cookie login, session restoration, session expiry/revocation handling,
CSRF transport, logout and ACTIVE owned-profile switching replace mock login.
Private pages use authenticated APIs and clear old account/profile state.
Registration has validation/error UI but honestly returns the backend activation
restriction; OAuth/password recovery remain unavailable. New owned resume profiles
can be extracted/reviewed/confirmed; standalone comparison remains unavailable.
Placement/salary forms remain independent stateless calculations with unchanged
models/contracts. The dashboard has a separate retry-protected Save profile
prediction action for owned history and refreshes analytics after confirmation.

Optional scoped retry keys protect new profile/resume creation, existing profile
update/confirmation and assessment reservation/submission. Existing owned prediction
replay continues to require current source inputs/revision and ACTIVE ownership.
Pending creations stay quarantined; legacy records are never claimed. Assessment
deadlines, quota, attempts, cooldown, scoring and recoverable evidence remain.
See [frontend integration](frontend-authentication.md) and
[retry integrity](account-bound-idempotency.md) for exact contracts/storage limits.

## Exact validation results

| Final run | Passed | Failed | Errors | Skipped | Deselected | Warnings |
| --- | --- | --- | --- | --- | --- | --- |
| Phase 29.6.7 backend | 1,078 | 0 | 0 | 0 | 0 | 10 |
| Phase 29.6.7 frontend | 175 | 0 | 0 | 0 | N/A | 0 |
| Phase 29.6.8 backend | 1,116 | 0 | 0 | 0 | 0 | 10 |
| Phase 29.6.8 frontend | 181 | 0 | 0 | 0 | N/A | 0 |
| Phase 29.6.9 combined ASGI workflows | 2 | 0 | 0 | 0 | 0 | 10 |
| Phase 29.6.9 full backend | 1,118 | 0 | 0 | 0 | 0 | 10 |
| Phase 29.6.9 full frontend | 181 | 0 | 0 | 0 | N/A | 0 |
| Phase 29.6.9 Chromium assertions | 40 | 0 | 0 | 0 | N/A | See below |

Frontend runner also reports zero cancelled/todo. Runs overlap; do not sum them.
The final backend full run took 316.89 s; frontend 344.55 ms. Lint and a fresh
production build exit 0. Build processes write only new evidence folders. Vite
reports that outside-root output will not be emptied; no empty/cleanup override
is used. Existing joblib/NumPy shape-assignment DeprecationWarnings remain visible
and are explained in the existing dependency audit. Models/dependencies are unchanged.

Actual production-mode ASGI validates every registered private operation's
anonymous denial, imports, startup/shutdown, unchanged stateless schema types
and zero cold-start storage writes. The full backend suite includes real TCP
HTTP and certificate-verified HTTPS production-cookie/CSRF/owned-profile/prediction/
assessment flows, graceful shutdown and released ports. It also covers disabled
accounts, version changes, clock-based idle/absolute expiry, rotation, session
revocation, corrupt ownership, legacy denial, concurrent reservations/submission,
recovery, stale retries and cross-account denial before side effects.

Browser validation uses the production bundle against the same secured app in
explicit isolated loopback development mode. Two separate accounts each have
two synthetic profiles; a third starts empty. Real frontend clicks/forms/uploads
cover models, stored prediction, dashboard, readiness/recommendations, assessments,
history/performance, profile edits, switching, refresh, logout and restricted
registration. Network interception is used only for explicit unavailable/malformed/
CSRF error tests, separately from successful real-backend workflows.
Browser HTTPS, real provider activation, long-running wall-clock cooldown/expiry
and multi-host/load validation were not run; API TLS and controlled lifecycle
tests provide their specified evidence. There is no full security certification.

## Browser assertion inventory

- readiness analysis loaded: passed.
- assessment navigation preserves answer: passed.
- assessment refresh restores selected answer: passed.
- assessment UI submits and displays confirmed score: passed.
- performance analytics loads after completion: passed.
- browser refresh restores profile workspace: passed.
- foreign Origin rejected before creation: passed.
- logout removes protected UI: passed.
- registration activation restriction displayed without false success: passed.
- backend unavailable hides private workspace: passed.
- connection retry restores selection: passed.
- malformed session cannot mount private UI: passed.
- CSRF failure visible without false save: passed.
- explicit retry obtains fresh CSRF and saves: passed.
- owned assessment history and result: passed.
- completed duplicate submission returns 409: passed.
- retake cooldown enforced: passed.
- foreign performance concealed: passed.
- owned company eligibility operational: passed.
- profile switch clears old history view: passed.
- protected mobile workspace fits: passed.
- second browser has two owned profiles: passed.
- second browser has no account A UI: passed.
- cross-account assessment history performance recommendations and submission denied: passed.
- client account fields rejected without disclosure: passed.
- revoked cookie cannot restore session: passed.
- anonymous refresh stays outside workspace: passed.
- no auth secrets in browser storage: passed.
- stateless placement form real result: passed.
- stateless salary form real result: passed.
- stored prediction refreshes dashboard trend: passed.
- recommendations render backend groups: passed.
- readiness skill gaps page visible: passed.
- profile UI update advances revision and requires confirmation: passed.
- profile confirmation preserves ID and advances revision: passed.
- stale reviewed update rejected: passed.
- empty account does not use demo profile: passed.
- owned resume upload creates server profile: passed.
- resume confirmation preserves ID and missing ML inputs: passed.
- resume-created profile remains inaccessible to another account: passed.

One browser error-test attempt used a strict text selector that matched a visible
dashboard error and a hidden assessment error. The corrected visible-alert selector
passes; the original failed tool output is retained in phase9-browser-errors.json.
No application security or test assertion was weakened. Console network errors
correspond to intentionally exercised 401/403/404/409/429/503 and aborted requests.
Chromium emitted a verbose optional username-field advisory during registration;
source inspection confirms the visible labelled email input has autocomplete=username
and is disabled during submission. No hidden field or warning suppression was added.
There were no recorded uncaught application exceptions in these browser scenarios.
Phase7/8 initial failures and their corrections remain in their journal/evidence,
including missing test CSRF fixtures, preserved-error-cause lint failures, first
ownership-table creation validation, legacy empty metadata, the obsolete unsupported
retry-header test and an isolated-runner port collision. Final suites pass.

## Complete actual endpoint security inventory

31 application operations across 30 paths. All private requests authenticate first;
required CSRF/Origin then precede ownership and business effects. Anonymous 401,
invalid Origin/required CSRF 403, foreign/missing/inactive/legacy target 404, genuine
storage failures safe 503, stale retry 409 and owned expiry 410 are retained.
Unknown registered operations remain private/default-denied. Public company data
is the existing DEMO seed. Framework docs are production 404.

| Method | Path | Class | Authentication | CSRF/Origin | Ownership | Current behavior | Tests |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GET | `/api/account/profiles` | profile | Yes | Origin checked when present | New/ACTIVE account profile | Owner success; safe denial/lifecycle/retry errors | profile_ownership/account_bound_idempotency |
| GET | `/api/assessment/{assessment_id}` | assessment | Yes | Required | ACTIVE profile + bound session | Owner success; safe denial/lifecycle/retry errors | assessment_ownership/lifecycle/retry |
| GET | `/api/auth/csrf` | session | Yes | Exact Origin; issues CSRF | Session/account | Existing auth/session contract | session_security/session_http |
| GET | `/api/auth/login-challenge` | entry | No | Exact Origin; issues CSRF | Credentials/challenge | Existing auth/session contract | session_security/session_http |
| GET | `/api/auth/session` | session | Yes | Origin checked when present | Session/account | Existing auth/session contract | session_security/session_http |
| GET | `/api/companies` | public | No | No | None | 200/404 existing public contract | session_security/session_http |
| GET | `/api/companies/{company_id}` | public | No | No | None | 200/404 existing public contract | session_security/session_http |
| GET | `/api/profile/{profile_id}` | profile | Yes | Origin checked when present | New/ACTIVE account profile | Owner success; safe denial/lifecycle/retry errors | profile_ownership/account_bound_idempotency |
| GET | `/api/profile/{profile_id}/assessments` | assessment | Yes | Required | ACTIVE profile + bound session | Owner success; safe denial/lifecycle/retry errors | assessment_ownership/lifecycle/retry |
| GET | `/api/profile/{profile_id}/eligibility` | analytics | Yes | Origin checked when present | ACTIVE profile + bound history/evidence | Owner success; safe denial/lifecycle/retry errors | prediction_ownership/phase29_integration |
| GET | `/api/profile/{profile_id}/eligibility/{company_id}` | analytics | Yes | Origin checked when present | ACTIVE profile + bound history/evidence | Owner success; safe denial/lifecycle/retry errors | prediction_ownership/phase29_integration |
| GET | `/api/profile/{profile_id}/performance` | analytics | Yes | Origin checked when present | ACTIVE profile + bound history/evidence | Owner success; safe denial/lifecycle/retry errors | prediction_ownership/phase29_integration |
| GET | `/api/profile/{profile_id}/placement-summary` | analytics | Yes | Origin checked when present | ACTIVE profile + bound history/evidence | Owner success; safe denial/lifecycle/retry errors | prediction_ownership/phase29_integration |
| GET | `/api/profile/{profile_id}/readiness` | analytics | Yes | Origin checked when present | ACTIVE profile + bound history/evidence | Owner success; safe denial/lifecycle/retry errors | prediction_ownership/phase29_integration |
| GET | `/api/profile/{profile_id}/recommendations` | analytics | Yes | Origin checked when present | ACTIVE profile + bound history/evidence | Owner success; safe denial/lifecycle/retry errors | prediction_ownership/phase29_integration |
| GET | `/api/profile/{profile_id}/skills` | analytics | Yes | Origin checked when present | ACTIVE profile + bound history/evidence | Owner success; safe denial/lifecycle/retry errors | prediction_ownership/phase29_integration |
| GET | `/health` | public | No | No | None | 200 liveness | session_security/session_http |
| POST | `/api/assessment/start` | assessment | Yes | Required | ACTIVE profile + bound session | Owner success; safe denial/lifecycle/retry errors | assessment_ownership/lifecycle/retry |
| POST | `/api/assessment/{assessment_id}/submit` | assessment | Yes | Required | ACTIVE profile + bound session | Owner success; safe denial/lifecycle/retry errors | assessment_ownership/lifecycle/retry |
| POST | `/api/auth/login` | entry | No | Required | Credentials/challenge | Existing auth/session contract | session_security/session_http |
| POST | `/api/auth/logout` | session | Cookie when present | Origin always; token with cookie | Session/account | 204 revocation; no-cookie no-op | session_security/session_http |
| POST | `/api/auth/register` | entry | No | Required | Credentials/challenge | 503 activation unavailable | session_security/session_http |
| POST | `/api/auth/session/renew` | session | Yes | Required | Session/account | Existing auth/session contract | session_security/session_http |
| POST | `/api/predict` | analytics | Yes | Required | No stored resource | Existing stateless calculation; no history | prediction_ownership/phase29_integration |
| POST | `/api/profile/from-resume` | profile | Yes | Required | New/ACTIVE account profile | Owner success; safe denial/lifecycle/retry errors | profile_ownership/account_bound_idempotency |
| POST | `/api/profile/verify` | profile | Yes | Required | New/ACTIVE account profile | Owner success; safe denial/lifecycle/retry errors | profile_ownership/account_bound_idempotency |
| POST | `/api/profile/{profile_id}/predict` | analytics | Yes | Required | ACTIVE profile + bound history/evidence | Owner success; safe denial/lifecycle/retry errors | prediction_ownership/phase29_integration |
| POST | `/api/resume/analyze` | deferred | Yes | Required | Pending | 503 before handler | session_security/session_http |
| POST | `/api/resume/upload` | deferred | Yes | Required | Pending | 503 before handler | session_security/session_http |
| POST | `/api/salary-predict` | analytics | Yes | Required | No stored resource | Existing stateless calculation; no history | prediction_ownership/phase29_integration |
| PUT | `/api/profile/{profile_id}` | profile | Yes | Required | New/ACTIVE account profile | Owner success; safe denial/lifecycle/retry errors | profile_ownership/account_bound_idempotency |


Test names denote backend/tests/test_*.py. New test_phase29_integration.py covers
the full sequential product workflow and denied requests with forbidden inference/
recovery spies. Frontend auth/retry/domain tests retain validation assertions.

## Files and environment

No dependencies, package/lockfiles,
database schema, environment/secrets, deployment settings, model or dataset change. Only additive private receipts on newly operated synthetic JSON records are tested;
the live authentication database and historical records are not mutated.

- `README.md`
- `backend/app/routes/owned_assessment.py`
- `backend/app/routes/owned_profile.py`
- `backend/app/services/assessment_service.py`
- `backend/app/services/owned_assessment_service.py`
- `backend/app/services/owned_profile_service.py`
- `backend/app/services/profile_service.py`
- `backend/tests/test_profile_ownership.py`
- `frontend/README.md`
- `frontend/src/App.css`
- `frontend/src/App.jsx`
- `frontend/src/components/EditProfileModal.jsx`
- `frontend/src/components/Navbar.jsx`
- `frontend/src/components/ProfileDropdown.jsx`
- `frontend/src/components/ResumeUploadModal.jsx`
- `frontend/src/hooks/StudentProfileProvider.jsx`
- `frontend/src/hooks/useProfile.js`
- `frontend/src/hooks/useProfileResource.js`
- `frontend/src/pages/Dashboard.jsx`
- `frontend/src/pages/Login.jsx`
- `frontend/src/pages/MockTests.jsx`
- `frontend/src/pages/StudentProfile.jsx`
- `frontend/src/services/api.js`
- `frontend/src/services/assessmentSession.js`
- `frontend/src/services/auth.js`
- `frontend/src/services/mockTest.js`
- `frontend/src/services/profileReview.js`
- `frontend/src/services/profileState.js`
- `frontend/tests/assessmentApi.test.js`
- `frontend/tests/integrationApi.test.js`
- `frontend/tests/profileReview.test.js`
- `frontend/tests/profileState.test.js`
- `frontend/tests/readinessEvidenceApi.test.js`
- `backend/app/services/retry_integrity.py`
- `backend/tests/test_account_bound_idempotency.py`
- `backend/tests/test_phase29_integration.py`
- `docs/account-bound-idempotency.md`
- `docs/frontend-authentication.md`
- `frontend/src/components/OwnedProfileSelector.jsx`
- `frontend/src/hooks/useAuth.js`
- `frontend/src/services/apiTransport.js`
- `frontend/src/services/ownedProfiles.js`
- `frontend/src/services/retryIntent.js`
- `frontend/tests/authFixtures.js`
- `frontend/tests/authentication.test.js`
- `frontend/tests/retryIntegrity.test.js`
- `docs/phase-29-security-validation.md`
- `docs/phase-29-product-readiness.md`

## Preservation and deployment limits

Baselines contain 2,849 files before .7, 2,860 before .8 and 2,865 before .9.
The same inventory excludes .git, node_modules, virtual environments, caches,
agent settings and this assignment's own evidence directory; earlier scratch and
backups remain included. Growth is from new source/tests/docs and browser evidence.
The .7 versus .6 baseline difference is four .6 project files plus 27 retained .6
evidence files. No files were deleted to reconcile counts. The protected selector
here is broader than .6: data/models/salary/src/datasets plus outputs/analysis and
placement.csv/main.py. It checks 579 files, including all historical stores.

Every baseline path and original modified/untracked path remains. Historical profile
UUIDs, assessment/prediction arrays, model artifacts, datasets, salary assets and
live account/session data are unchanged. Original journal suffix bytes are preserved
through append-only entries. One prior browser log received 146 appended bytes;
all original 442 bytes are hash-verified intact. No scratch/backups were replaced.
Owned test/browser servers shut down; process audits terminate zero unrelated
processes. Branch bhargav-frontend, HEAD
f84099349d104e4e77c7080fba4465ca4e3470a4 and empty index are unchanged. No prohibited
Git operation was executed. Exact final counts/hash/process results are in the journal.

Final confirmed audit retains all 2,849 assignment-start files and all 2,865
pre-.9 files, with zero deletions; the inventory now has 2,869 files. Across
this assignment, 34 existing files were edited and 15 source/test/documentation
files created, plus five browser evidence files. The separate assignment evidence
directory is excluded from these inventory counts. All 579 protected hashes,
274,390 assignment-start journal bytes and 290,576 pre-.9 journal bytes are
preserved. Final Git has 60 modified tracked files, 93 grouped untracked entries,
128 expanded untracked paths and an empty index; all original 56 modified entries
and 108 expanded untracked paths remain. Branch and full HEAD above are unchanged.

The handoff audit also verifies 173 source/test files match the passing full-suite
checkpoint and 15 manifest/environment/configuration files remain unchanged. Five 31-operation matrices and 80 local documentation links pass. Four owned
browser server pairs stopped; six suite server PIDs and four graceful secured
shutdown logs were audited. All nine audited loopback ports are closed/rebindable;
the audit terminated zero processes. `git diff --check` passes. One stale README
sentence about frontend login was corrected.

Registration/recovery still require approved email verification/provider work.
Standalone resume upload/analyze stay blocked. Legacy records remain unowned and
inaccessible. JSON/SQLite cross-store writes and local cooperating locks do not
certify multi-host/network-FS/manual-tampering/power-loss guarantees. Pending
creation is quarantined; repair requires separate authorization. Keys lack TTL
cleanup; stateless calculators are not cached. Throttling, hosting/TLS/proxy/CORS/ACL
review and real-user deployment testing remain before public release. No real
historical student record was used for validation.

See [product readiness](phase-29-product-readiness.md). Stop after Phase 29.6.9.
