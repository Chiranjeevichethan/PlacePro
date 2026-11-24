# Session security — Phase 29.6.3

> Historical snapshot: the original phase dates, design decisions and recorded
> test results below are preserved. Statements about the then-current inventory,
> unavailable features and pre-authentication behavior are superseded by the
> [reviewed 2026-11-24 release snapshot](../backend/DEPLOYMENT.md#reviewed-release-snapshot-2026-11-24).
> This documentation change reruns no application tests and establishes no new
> Linux/Docker or browser acceptance.

Implemented 2026-11-09 against the complete working tree on `bhargav-frontend`, HEAD
`f84099349d104e4e77c7080fba4465ca4e3470a4`. This is the backend session foundation,
not a production release or completed student-resource authorization.

> Latest state, Phase 29.6.6: owned analytics and authenticated stateless forms are
> enabled. See [prediction ownership](prediction-ownership.md) for the current matrix.
>
> Historical Phase 29.6.5: owned assessments are enabled alongside owned profiles,
> with session/CSRF/Origin security reused unchanged. Twelve deferred operations remain
> blocked. See [assessment ownership](assessment-ownership.md) for the current complete
> matrix, contracts and tests. Earlier inventory/results below are historical snapshots.

## Executive summary

The normal [FastAPI application](../backend/app/main.py) always installs a centralized,
fail-closed [ASGI gate](../backend/app/security.py). Opaque persistent sessions now
support login, restoration, server expiration, explicit rotation and logout. Cookies
are HttpOnly and production cookies require HTTPS. CSRF and exact Origin checks
precede mutations. No JWT, frontend bypass, activation shortcut or ownership inference.

At Phase 29.6.3 completion, **all 20 student operations were inaccessible**: anonymous requests receive 401;
authenticated requests with missing/incorrect required CSRF receive 403; requests
passing authentication/CSRF still receive 503 pending ownership enforcement. This
also conservatively stages the four stateless upload/form operations until their
account-only processing policy is approved. UUIDs, matching emails and confirmed
claims confer no student permission. The existing React mock login is unchanged
and cannot access these routes. Backend domain implementations remain intact.

**Current Phase 29.6.4 update:** five ownership operations (including the new
`GET /api/account/profiles`) are now available only through authoritative server-side
ownership. Profile creation/read/edit/confirmation enforce session/CSRF and safe
publication; foreign, missing and legacy targets receive uniform 404. Sixteen deferred
student operations remain blocked, including owned assessment/prediction/history APIs.
Profile responses omit assessment evidence and prediction history without rewriting
them. See [profile ownership](profile-ownership.md) for implementation, current tests
and the complete updated matrix. Historical Phase 29.6.3 results below remain intact.

The approved [architecture](authentication-architecture.md) and [account foundation](account-authentication-foundation.md)
remain historical design/phase records. This document describes the actual new
session implementation and supersedes their statements that production has no gate.

## Storage, secrets and account validation

[SessionStore](../backend/app/services/session_store.py) adds `sessions` and
`login_challenges` within the existing dedicated `PLACEPRO_AUTH_DB`, default
`data/auth/accounts.sqlite3`. Account table, application ID and account schema
version 1 remain unchanged. No import/startup database creation, ORM, student JSON
migration or company database replacement occurs in the session layer.
Phase 29.6.4 additionally creates an authoritative ownership table on first reservation;
it does not rewrite account/session rows. Session-table column compatibility is checked; incomplete/incompatible tables fail
closed. Existing account-store refusal of unrelated databases remains.

| Session field | Meaning |
| --- | --- |
| session_id / family_id | Server UUIDs; family preserves explicit renewal/logout lineage; never API/cookie payloads |
| account_id | Foreign key to immutable account UUID |
| secret_hash | Unique SHA-256 of a freshly generated 256-bit random secret |
| csrf_nonce | Independent 256-bit random nonce for server-side CSRF binding |
| context | production/development namespace; development sessions cannot resolve as production sessions |
| auth_version / password_changed_at | Snapshot checked against the current account on every resolution |
| created_at / last_activity_at | UTC Unix-epoch seconds; API expiry values use timezone-aware ISO UTC |
| idle_expires_at / absolute_expires_at | Server-enforced deadlines; idle never exceeds absolute |
| revoked_at / revocation_reason | Terminal revocation, observed expiration or rotation metadata |

Anonymous challenges contain only hashed random secret, independent nonce, context,
creation/expiry, attempt count and consumption time. They carry no account or student
identity and cannot authorize anything. New challenge issuance removes only expired
anonymous challenge rows; accounts, sessions and historical student records are not
deleted. No other retention/deletion job is introduced.

`secrets.token_urlsafe(32)` supplies 256 random bits (43 URL-safe characters). Only
hashes are persisted, never raw cookie secrets. Database lookup uses the hash/index;
CSRF comparison uses `hmac.compare_digest`. Passwords retain the existing Argon2id
implementation, bounds, dummy work, no-downgrade rehash and generic failures.

Short per-operation SQLite transactions serialize create/rotate/revoke. Credential
acceptance rechecks ACTIVE, verified email, auth_version and password_changed_at
inside the session transaction. Account disable/deactivation or version/timestamp
changes invalidate requests; a future password-change operation must update these
fields and revoke sessions atomically. Internal `revoke_account` exists; no password
change, activation, recovery or logout-all endpoint was added.

## Session lifecycle

Login commits the session and challenge consumption before returning a cookie. A
database failure cannot report login success. Pending, unverified, disabled,
deactivated, unknown, wrong-password and malformed-hash accounts receive the same
401 credential response. Registration remains 503: no approved verification provider
or activation flow exists. Synthetic activation SQL exists only in isolated tests.

Defaults: **30-minute idle**, **12-hour absolute**, **30-second activity-write
throttle**, **10 active sessions per account**. `PLACEPRO_SESSION_IDLE_SECONDS` and
`PLACEPRO_SESSION_ABSOLUTE_SECONDS` configure the bounded lifetimes; capacity and
throttle are validated internal configuration fields. Capacity returns 409 after
valid credentials; it never silently revokes another browser. Same-browser valid
credential login can replace its previous session at capacity; switching accounts
revokes the old browser family atomically. Independent browsers remain independent.

Session restoration/CSRF retrieval revalidate and renew idle activity only within the
fixed absolute limit. Denied student requests never touch last activity. Expiration
at the exact deadline is invalid and observed expiration is persisted as EXPIRED,
preventing revival after a clock rollback. This changes only authentication metadata,
not assessment deadlines, attempts or history. Server time remains authoritative;
deployment needs reliable UTC clock synchronization.

Explicit renewal revokes the old row and inserts one replacement in the same family,
preserving absolute expiry and changing cookie/CSRF binding. Concurrent renewals have
one winner. Ordinary GETs never issue replacement cookies. A lost renewal response
requires credential login again; no old-token grace period or new retry ledger exists.
Generic 401 responses do not clear cookies, so late failures cannot erase a renewed
cookie. Revoked/expired cookies cannot restore/renew sessions.

Logout durably revokes the current family before clearing both PlacePro cookies.
Repeated logout without a cookie returns 204 with approved Origin; it grants no data
or mutation permission. Revoked LOGOUT and old ROTATED cookies with their original
valid CSRF can only repeat/revoke their own family. They cannot resolve, read,
renew or retrieve CSRF. This narrowly handles concurrent renewal/logout: no surviving
child session remains. Expired, unknown, forged and ambiguous cookies return 401.
Missing/wrong CSRF with an existing eligible cookie returns 403, with no revocation.

## Cookie and deployment configuration

[SecurityConfig](../backend/app/services/security_config.py) defaults to production.
Invalid modes, wildcard/path/userinfo origins, insecure production origins and invalid
lifetimes fail configuration. There is no security-disable variable.

| Setting | Production | Explicit development |
| --- | --- | --- |
| Mode | `PLACEPRO_SECURITY_MODE=production` (default) | `PLACEPRO_SECURITY_MODE=development` |
| Session cookie | `__Host-placepro_session` | `placepro_dev_session` |
| Pre-login cookie | `__Host-placepro_login` | `placepro_dev_login` |
| Flags | Secure, HttpOnly, SameSite=Lax, Path=/, no Domain | HttpOnly, SameSite=Lax, Path=/, no Domain; Secure=false |
| Session persistence | Browser-session cookie; server expiry authoritative | Same |
| Challenge lifetime | Max-Age 300 seconds, server expiry authoritative | Same |
| Transport | ASGI request scheme must be HTTPS | Host and actual client address must both be loopback |
| Allowed origins | Explicit comma-separated HTTPS origins, **empty by default** | Default `http://127.0.0.1:5173`; configured origins must be loopback |
| Framework docs | Disabled, 404 | GET/HEAD only, loopback transport/client; rejected Origin denied |

Empty production origins intentionally prevent challenge/login issuance until
deployment is configured. Do not change cookie flags automatically based on a request.
`localhost` and `127.0.0.1` are different cookie hosts. Ports do not isolate cookies;
avoid untrusted services on the same development host. Split cross-site deployment
is not supported by the Lax policy; prefer same-site HTTPS topology.

Local example, shell variables only (no existing .env overwritten):

```powershell
$env:PLACEPRO_SECURITY_MODE = 'development'
$env:PLACEPRO_ALLOWED_ORIGINS = 'http://127.0.0.1:5173'
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8765 --no-proxy-headers
```

This enables the session foundation, development docs and owned profile APIs; it does
not enable deferred assessment/prediction/history operations or a frontend login.
Production needs trusted HTTPS termination, host/firewall/filesystem ACL review and
explicit origin configuration. Do not trust client-supplied forwarding headers to
assert HTTPS/loopback. Real-server tests disable proxy headers; proxy trust and final
deployment hostnames have not been approved or validated. HttpOnly is not XSS defense.

## CSRF and Origin/CORS

Tokens are synchronizer tokens bound to the current server session. A stable
HMAC-SHA-256 uses the random raw cookie secret and persisted random CSRF nonce; the
server reconstructs it without storing raw credentials. Each session/rotation gets
a different binding. Return the token only through an authorized exact-origin JSON
response, never a URL, log or browser-persistent storage. Send `X-CSRF-Token`.

`GET /api/auth/login-challenge` deliberately adds a separate anonymous bootstrap:
strict Origin/transport, short-lived HttpOnly challenge cookie, random bound token.
`POST /api/auth/login` checks it **before body parsing/credential hashing**, increments
the bounded attempt count, then consumes it atomically with successful login. Maximum
five attempts and five-minute lifetime; consumed/expired/foreign challenge tokens fail
403. This preserves the user's requirement that `/api/auth/csrf` itself is authenticated
and prevents login CSRF. Login buffers at most 16 KiB and redacts validation failures.
It is not email verification or an authentication session.

All unsafe private methods and the two lifecycle GET paths require active session,
exact Origin and CSRF before parsing/domain calls, recovery, expiry or retry lookup:
`GET /api/assessment/{assessment_id}` and
`GET /api/profile/{profile_id}/assessments`. HEAD variants also receive the lifecycle
policy before method rejection. Missing/wrong/cross-session/cross-account tokens fail
403; expired/revoked sessions fail 401. Duplicate Origin/CSRF/cookie values are rejected.
No Referer fallback or token in query strings is implemented.

CORS uses explicit allowed origins, credentials=true, methods GET/POST/PUT and headers
Content-Type/X-CSRF-Token/Idempotency-Key (plus Starlette's standard safelisted headers).
No wildcard credential origin, regex or arbitrary Origin reflection. It wraps the
gate, so approved preflight succeeds without credentials or domain writes and gate
errors carry approved CORS headers. Bad-origin/method/header preflight returns 400.
Public responses to unapproved origins have no allow-origin header; authenticated
private requests additionally reject unapproved Origin server-side. CORS itself
does not grant authentication/authorization. Unexpected framework 500 responses
outside handled gate/auth errors are not claimed to have global CORS decoration.

## Default-private gate and endpoint matrix

Method/path-specific public exceptions are health, two company reads and necessary
auth entry points. [FastAPI effective route contexts](https://github.com/fastapi/fastapi)
are inspected without invoking handlers; this handles the installed FastAPI 0.141.1
lazy router architecture. New registered routes default private automatically, even
without a manually added dependency. Unknown API paths: anonymous 401; authenticated
404 after required CSRF. Unsupported methods: anonymous 401; authenticated 405 after
required CSRF; no alternate-method bypass. Trailing-slash variants do not redirect
through an unprotected path. WebSockets are denied (1008); none currently exist.

Recorded phase inventory: **31 application operations across 30 paths**, including seven auth
operations. Four development framework paths additionally support GET/HEAD (eight
framework operations); production registers none of those. OPTIONS preflight is a
middleware operation, never a student handler.

Matrix shorthand: **D** = anonymous 401, bad required CSRF 403, otherwise 503 with
`Student operations are unavailable pending ownership enforcement.` No resource
lookup occurs. **P** test references `test_session_security.py::test_every_student_operation_denies_anonymous_before_parsing`
and `test_every_student_operation_denies_authenticated_accounts_pending_ownership`;
**C** adds `test_private_mutations_and_lifecycle_gets_require_csrf_before_pending_ownership`.
All cited paths are covered by parametrized tests generated from the actual inventory.
The pending-ownership parametrization now covers only sixteen deferred operations;
all twenty-one private student/account-profile-list operations retain anonymous and
required CSRF coverage. **O** below means authoritative profile ownership is enforced:
owner success 200, foreign/missing/unowned/corrupt target 404. **OA/OR/OU/OC** refer to
the exact ownership test references in [profile ownership](profile-ownership.md).

| Method | API path | Classification | Authentication | CSRF | Ownership | Ownership status | Current behavior | Future behavior | Test reference |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GET | `/health` | Public | No | No | No | N/A | 200 static liveness | Public liveness | public_health_and_company_contracts |
| GET | `/api/companies` | Public | No | No | No | N/A | 200 demo requirements; first-use seed possible | Public sanitized reads | public_health_and_company_contracts |
| GET | `/api/companies/{company_id}` | Public | No | No | No | N/A | 200/404 | Public sanitized reads | public_health_and_company_contracts |
| POST | `/api/predict` | Private | Yes | Yes | No resource target | Account processing pending | D | Account + quota; stateless inference | P,C |
| POST | `/api/salary-predict` | Private | Yes | Yes | No resource target | Account processing pending | D | Account + quota; stateless inference | P,C |
| POST | `/api/resume/upload` | Private | Yes | Yes | No resource target | Account processing pending | D | Account + upload limits | P,C |
| POST | `/api/resume/analyze` | Private | Yes | Yes | No resource target | Account processing pending | D | Account + upload limits | P,C |
| GET | `/api/account/profiles` | Private | Yes | No | Own ACTIVE associations | Implemented | 200 own IDs only; 503 unavailable | Same | anonymous coverage; OA |
| POST | `/api/profile/from-resume` | Private | Yes | Yes | New association | Implemented | O | Safe owned publication | anonymous/CSRF coverage; OC |
| POST | `/api/profile/verify` | Private | Yes | Yes | Existing/new association | Implemented | O | Owned confirmation or server-ID creation | anonymous/CSRF coverage; OA,OR,OU |
| GET | `/api/profile/{profile_id}` | Private | Yes | No | Profile | Implemented | O | Owned reads; history/evidence omitted | anonymous coverage; OA,OR |
| PUT | `/api/profile/{profile_id}` | Private | Yes | Yes | Profile | Implemented | O; revision required | Owned revision-guarded edit | anonymous/CSRF coverage; OR,OU |
| POST | `/api/profile/{profile_id}/predict` | Private | Yes | Yes | Profile/history | Pending | D | Owned prediction before key lookup | P,C |
| GET | `/api/profile/{profile_id}/readiness` | Private | Yes | No | Profile | Pending | D | Owned shared-evidence projection | P |
| GET | `/api/profile/{profile_id}/placement-summary` | Private | Yes | No | Profile | Pending | D | Owned read-only summary | P |
| GET | `/api/profile/{profile_id}/eligibility` | Private | Yes | No | Profile | Pending | D | Owned eligibility | P |
| GET | `/api/profile/{profile_id}/eligibility/{company_id}` | Private | Yes | No | Profile | Pending | D | Owned eligibility before company lookup | P |
| GET | `/api/profile/{profile_id}/recommendations` | Private | Yes | No | Profile | Pending | D | Owned recommendations + quotas | P |
| POST | `/api/assessment/start` | Private | Yes | Yes | Profile/new assessment link | Pending | D | Owned reservation before lifecycle sync | P,C |
| POST | `/api/assessment/{assessment_id}/submit` | Private | Yes | Yes | Stored assessment/profile link | Pending | D | Owned attempt before acceptance | P,C |
| GET | `/api/assessment/{assessment_id}` | Private | Yes | Yes | Stored assessment/profile link | Pending | D | Owned lifecycle GET before recovery/expiry | P,C; denied_lifecycle_gets |
| GET | `/api/profile/{profile_id}/assessments` | Private | Yes | Yes | Profile/assessment inventory | Pending | D | Owned history before recovery/expiry | P,C; denied_lifecycle_gets |
| GET | `/api/profile/{profile_id}/skills` | Private | Yes | No | Profile/evidence | Pending | D | Owned evidence | P |
| GET | `/api/profile/{profile_id}/performance` | Private | Yes | No | Profile/history | Pending | D | Owned performance/history | P |
| POST | `/api/auth/register` | Public entry, restricted | No | No operation allowed | No | N/A | 503 before parsing (HTTP prod 403) | Approved verification + bootstrap CSRF | registration_stays_unavailable |
| GET | `/api/auth/login-challenge` | Public entry | No | Issues bootstrap token; exact Origin | No | N/A | 200 or Origin/transport 403 | Bounded bootstrap | login_requires_bootstrap_csrf |
| POST | `/api/auth/login` | Public entry | Credentials | Pre-login challenge + Origin | No | N/A | 200/401/403/409/413/422/503 | Active verified account session | login_failure_is_generic; real_login_session |
| GET | `/api/auth/session` | Private account | Yes | No | Current account/session only | Implemented via session | 200/401/403/503 | Restore current account only | real_login_session; expired_cookie |
| GET | `/api/auth/csrf` | Private account | Yes | Issues session token; exact Origin | Current account/session only | Implemented via session | 200/401/403/503 | Session-bound token | tokens_not_disclosed |
| POST | `/api/auth/session/renew` | Private account | Yes | Yes + Origin | Current session only | Implemented via session | 200/401/403/503 | Atomic rotation | rotation_cookie_and_token |
| POST | `/api/auth/logout` | Private account; no-cookie no-op | Valid cookie to revoke | Yes when cookie exists + Origin | Current family only | Implemented via session | 204/401/403/503 | Durable family revocation | real_login_session; logout_and_renew_reject_wrong_csrf |

Test names in short matrix references omit the `test_` prefix and occasionally use a
unique prefix of the full function name; [security tests](../backend/tests/test_session_security.py)
contain the complete names. Exact lifecycle reference:
`test_denied_lifecycle_gets_cannot_expire_or_recover_synthetic_attempts`.
Framework and method policy references: `test_framework_documentation_policy`,
`test_variants_unknown_paths_and_unsupported_methods_cannot_bypass_gate`,
`test_authenticated_unknown_and_unsupported_methods_have_controlled_semantics`,
`test_new_api_route_defaults_private_without_policy_opt_in`.

## Authentication API and future React contract

1. `GET /api/auth/login-challenge`, cookies included and exact Origin; receive
   `{csrf_token}` and short-lived HttpOnly bootstrap cookie.
2. `POST /api/auth/login`, JSON `{email,password}` + X-CSRF-Token + cookies; receive
   `{account:{account_id,email},idle_expires_at,absolute_expires_at}` and session cookie.
   The bootstrap cookie is cleared. No session IDs, token hashes, versions or password
   metadata are returned. Login is real authentication; student access separately
   requires the implemented profile ownership checks, with other operations deferred.
3. `GET /api/auth/session` restores the same minimal current account/expiry contract.
4. `GET /api/auth/csrf`, valid session and exact Origin; token stays in React memory.
5. `POST /api/auth/session/renew`, valid token/Origin; replace cookie and fetch new
   CSRF. Serialize renewals across tabs; lost response requires login, not old-token reuse.
6. `POST /api/auth/logout`, token/Origin; only 204 confirms durable revocation. Then
   future React integration clears private state and broadcasts invalidation.

All auth/gate responses are private/no-store. 401 credential failures are generic;
422 validation is fixed/redacted; 413 bounds auth buffering; 409 is session capacity;
503 storage/hash errors contain no database exception/path. Fetch must use
`credentials: include`; do not put credentials or tokens in localStorage/sessionStorage,
URLs, logs or VITE variables. Browser automatically supplies Origin; controlled CLI
tests explicitly supply the approved Origin. No frontend changes were made.

## Legacy isolation and regression strategy

Phase 29.6.3 implemented no account/profile mapping. Phase 29.6.4 now adds mapping
for newly created profiles only; no legacy claim/migration, assessment ownership,
prediction ownership or idempotency change. Denied production requests never enter
existing domain operations, including SUBMITTING recovery,
expired assessments, quota scanning and history key replay.

Existing API business regressions retain their assertions through
[domain_app](../backend/tests/domain_app.py), an explicitly test-only ASGI harness.
It refuses missing/project/non-isolated storage, has no auth routes, and cannot be
selected through any production flag. Only test imports and the test HTTP wrapper
switch to it. Historical audit access expectations describe underlying domain logic,
not current production exposure. Its old CORS exposure assertion is replaced with
normal-app CORS/401 denial. The two old staged auth expectations now check registration
503 and login Origin rejection before parsing; isolated .2 foundation contracts remain.

Normal-app security tests use `backend.app.main.create_app` with real credential
services, temporary accounts, true cookie/login/CSRF and an unconditional gate. No
dependency override grants authorization. [Production-server tests](../backend/tests/test_session_http.py)
launch the same default-production application over real HTTP and trusted synthetic
HTTPS, without proxy headers, prove restoration/logout/denials and graceful shutdown.
Temporary certificate/key generation uses the existing Git-bundled OpenSSL on this
Windows baseline; TLS validation trusts only that generated certificate, never disables
verification. Test identity headers identify only the owned server. Existing shutdown
regression preserves an unrelated synthetic listener. Every test store is temporary.

## Actual validation results

Focused runs overlap the full suite. The initial import/request probe failed on a lazy `_IncludedRouter.path`; effective
route iteration corrected it before security tests. Initial focused 220 passed;
expanded focused 234 passed. The first lifecycle/HTTP/domain/infrastructure run had
94 passed/1 failed: a new CORS assertion expected 403 instead of correct anonymous
401. Its expectation was corrected, retaining origin/header/cache checks. Real HTTP
and HTTPS startup/session/shutdown passed in that run. The first full run had 819
passed/1 failed because one existing CORS test still used the domain-only harness
(405 instead of expected 200). That test now exercises the normal secured app with
the explicit intended loopback origin, retaining both original assertions.

| Run | Passed | Failed | Errors | Skipped | Deselected | Warnings | Seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Initial session/security/account selection | 220 | 0 | 0 | 0 | 0 | 0 | 64.93 |
| Expanded selection | 234 | 0 | 0 | 0 | 0 | 0 | 66.65 |
| Lifecycle + HTTP/HTTPS + domain audit + infrastructure | 94 | 1 | 0 | 0 | 0 | 0 | 37.47 |
| First full backend | 819 | 1 | 0 | 0 | 0 | 10 | 115.73 |
| **Final full backend** | **820** | **0** | **0** | **0** | **0** | **10** | **122.25** |

Final full coverage includes all session/account tests, corrected CORS tests, terminal
expiry/rotation/logout races, all 20 private operations, original model/domain tests,
six domain live-HTTP cases and two normal-production HTTP/HTTPS cases. Do not add
overlapping runs as unique tests. Both production servers exit 0 with application
shutdown completion and closed/rebindable owned ports. Frontend/build/browser suites
were not rerun; no frontend file changed and frontend authentication is deferred.
`git diff --check` passes. Final import, exact matrix/link/AST checks and full baseline
preservation details are recorded in the journal and retained evidence.

## Remaining vulnerabilities, future phases and deployment restrictions

Profile ownership is implemented in Phase 29.6.4; arbitrary UUIDs and legacy records
remain denied. Assessment/prediction/frontend/idempotency phases remain separate;
none started in Phase 29.6.4. The original deadline, cooldown, scoring, evidence and model business
rules remain unchanged in the domain harness.

Email delivery/activation/recovery, reset/change workflows, common-password checks,
per-account/network/distributed login throttling, bounded anonymous challenge issuance,
abuse quotas, retention/ACL/backup policy, security audit events and production proxy
configuration are still unavailable or unvalidated. Five attempts per challenge plus
two concurrent Argon2 jobs bound individual work; attackers can request new challenges,
so this is **not complete rate limiting**. Session rows are retained; no historical
deletion policy is silently introduced. SQLite/JSON deployment remains one cooperating
host; no multi-host durability, load/penetration test or browser authentication/XSS
certification is claimed. HTTP-only development cookies are suitable only for isolated
loopback work. Full production HTTPS cookie flags and real trusted TLS are tested,
but real deployment topology and browser/tab integration are future validation.

No Python/Node dependency or lockfile changes. No models trained/resaved. The ten
existing joblib/NumPy warnings remain a compatibility issue documented in the setup
audit. Do not expose real student data publicly or describe PlacePro as production
secure after this stage. Current next phase: **29.6.5 — Assessment Ownership**,
separately authorized. Historical Phase 29.6.3 validation remains above; Phase 29.6.4
validation is recorded in [profile ownership](profile-ownership.md) and the journal.
