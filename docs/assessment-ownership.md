# Assessment ownership — Phase 29.6.5

> Historical snapshot: the original phase dates, design decisions and recorded
> test results below are preserved. Statements about the then-current inventory,
> unavailable features and pre-authentication behavior are superseded by the
> [reviewed 2026-11-24 release snapshot](../backend/DEPLOYMENT.md#reviewed-release-snapshot-2026-11-24).
> This documentation change reruns no application tests and establishes no new
> Linux/Docker or browser acceptance.

Implemented scope: account-bound start, retrieval, submission and assessment-only
history. The existing session/CSRF/Origin gate and authoritative ACTIVE profile
associations are reused. Predictions, salary, recommendations, readiness, mixed
performance/skills and general history remain unavailable. No frontend changes,
historical backfill, database migration or account-bound idempotency were introduced.

> Current state, Phase 29.6.6: ten prediction/derived-data operations now enforce the
> approved account/stateless or ACTIVE profile/bound-history policy. Two standalone
> resume routes remain blocked. See [prediction ownership](prediction-ownership.md)
> for the current matrix/results. The .5 scope and results below are historical.

## Architecture and storage compatibility

The relationship is `validated account → ACTIVE owned profile → bound assessment`.
`OwnershipStore.authorize` remains the authority in the authentication SQLite database;
profile JSON, email, request fields and UUID knowledge cannot grant access. The shared
session service revalidates the identity, account status, revocation and authentication
version during authorization and again before protected writes. Pending, suspended,
failed, missing, legacy-unowned or invalid associations cannot grant access.

New assessment JSON retains its original fields and receives three server-only fields:

| Field | Meaning |
| --- | --- |
| `account_id` | Immutable account UUID from the validated server session |
| `ownership_schema_version` | Integer 1 identifying the supported binding contract |
| `profile_ownership_version` | ACTIVE association version captured at creation |

The existing `profile_id`, server-generated `assessment_id`, skill and positive attempt
ordinal complete the relationship. Every record must match its filename, parent profile,
account and current association version before lifecycle processing. Changing an
association version invalidates its previous bindings; there is no automatic rebinding.
Updates reject changes to these identity fields. There is no new table or migration.
New evidence receives server-only `account_id`; public assessment schemas omit it and
all ownership versions. Profile-only responses still omit stored assessment evidence
and prediction history, so they cannot bypass their specialized contracts.

New sessions use exclusive creation plus flush/fsync, preventing UUID collisions from
overwriting existing files. Later writes retain unique temporary files and atomic
replacement. Existing per-profile thread/OS locks serialize quota, ordinals, submission,
evidence and concurrent profile edits; profile locks precede assessment record locks.
The profile/session files and authentication database remain separate stores, not one
atomic transaction. Existing durable submission recovery is retained.

## Authorization execution order

1. The unconditional production gate classifies the actual method/path and resolves
   the real opaque cookie session. Its existing transport/Origin checks can reject
   requests before session resolution; this ordering was not replaced.
2. Required CSRF and exact Origin checks run before body parsing or domain operations.
   Both assessment GETs require them because they can recover or expire records.
3. For profile-scoped requests, authorize the profile before loading private JSON or
   exposing quota. For start, minimally decode the requested profile target before
   Pydantic field validation. Client ownership metadata is forbidden.
4. For assessment-scoped requests, read only stored binding metadata under the existing
   reader lock to discover the parent. Reject foreign/unbound records before parent
   lifecycle work; then authorize the ACTIVE profile and verify the complete binding.
   Discovery necessarily reads the assessment record before its parent is known; it
   never runs recovery/expiry. The reader may create a lock artifact, but denied
   requests do not change JSON, evidence, revisions, history or quota.
5. Under the existing profile transaction, reload/validate private storage and
   reauthorize. Filter records before synchronization. Recheck authorization before
   each protected assessment/evidence write, then execute original lifecycle rules.

An authenticated foreign or nonexistent assessment receives identical
`404 {"detail":"Assessment not found."}`. Profile-scoped missing, foreign, unowned,
inactive or corrupt targets receive `404 {"detail":"Profile not found."}`. No target
UUID, questions, answers, attempt count, completion/cooldown or score is returned.
Malformed target JSON fails closed as 404; genuine IO/ownership-store failures use
safe 503, not a misleading 404. A structurally bound record with corrupt lifecycle
state/evidence uses safe 503. Exceptions, internal paths and supplied answers are not
logged or echoed. All assessment responses use `Cache-Control: private, no-store`.

## Verified assessment endpoint inventory

Backend route/service searches and actual production ASGI inventory found four
assessment-specific operations and two mixed projections. There are no separate
public retake, recovery, expiry, result or evidence-write endpoints. Start performs
retake/reservation policy; retrieval/history/start/submission can synchronize lifecycle;
submission/result retrieval provide aggregate results. Profile responses redact the
stored evidence; readiness/eligibility/recommendations consume it only in deferred code.

| Method/path | Auth | CSRF + Origin | Profile ownership | Assessment binding | Read/write and existing lifecycle | Current authorization |
| --- | --- | --- | --- | --- | --- | --- |
| POST `/api/assessment/start` | Required | Required | ACTIVE owner before quota/sync | New server binding | Reserve IN_PROGRESS attempt; randomized selection; possible recovery/expiry | Owner 200; unauthorized 401/403/404; existing 422/429 |
| GET `/api/assessment/{assessment_id}` | Required | Required | ACTIVE stored parent | Account/profile/ID/version | Read safe questions/result; possible recovery/expiry | Owner 200; expired owner 410; unauthorized 401/403/404 |
| POST `/api/assessment/{assessment_id}/submit` | Required | Required | ACTIVE stored parent | Stored binding and submitted profile equality | Validate deadline/state; accept/score/project evidence/recover | Owner 200; completed 409; expired 410; limits 429; unauthorized 401/403/404 |
| GET `/api/profile/{profile_id}/assessments` | Required | Required | ACTIVE owner | Every projected record | Read bound evidence; possible recovery/expiry | Owner 200; unauthorized 401/403/404 |
| GET `/api/profile/{profile_id}/performance` | Required | Optional Origin validated | Deferred | Deferred | Consolidates assessment history, prediction history, readiness and skills | Authenticated 503 before handler, including owner |
| GET `/api/profile/{profile_id}/skills` | Required | Optional Origin validated | Deferred | Deferred | Combined claim/evidence projection | Authenticated 503 before handler, including owner |

These mixed routes remain blocked because enabling them would expose later-phase
derived prediction/general history data. They are tested for denial for both owner
and foreign accounts. There is no unsecured alternative method, path or router in
the normal app; original assessment routes remain solely in the guarded isolated
domain harness for regression testing.

## Start, retrieve, submit and evidence contracts

Start accepts `{profile_id, skill, num_questions?}`. Only a verified owned profile may
start, preserving the original confirmation rule. The account UUID comes from the
gate-issued identity. Ownership precedes quota, expiry, recovery and reservations.
The response retains its existing ID/skill/attempt/questions/deadline/server-time
contract; keys/explanations/internal ownership fields are excluded.

Retrieval requires the current cookie and `X-CSRF-Token`/Origin, and returns only
the original public session/aggregate result. **Secured expired GET now returns 410**
as requested by this phase. The original isolated domain GET still returns 200 with
EXPIRED state, preserving historical business regression assertions. This deliberate
transport distinction must be handled by future frontend integration.

Submission accepts `{profile_id, answers:{question_id:answer}}`. Direct assessment
authorization occurs before body parsing; a different submitted profile is 404 even
if the account owns both profiles, and is checked before answer validation. Spoofed
account/owner/version fields are redacted 422. JSON requests are capped at 1 MiB (413).
Scoring remains server-side with existing randomized-bank, deadline and answer rules.

Accepted answers, report and timestamp persist as SUBMITTING before evidence writes.
Evidence is bound to the validated account/profile/assessment and checked against
the stored score, level, skill, ordinal, timestamp and provenance. It is appended by
assessment ID without replacing existing evidence or claim provenance. The shared
profile writer preserves revision rules and histories. Completion then persists as
COMPLETED. A failed projection leaves recoverable accepted work; foreign/CSRF-denied
requests cannot recover it. Owner recovery after the deadline does not rescore or
duplicate evidence/revisions. Identical retry of interrupted accepted work returns
the original result; a later completed submission remains 409. No idempotency ledger.

Assessment history returns `{profile_id, assessments:[...]}` with the existing safe
history fields, selecting only evidence backed by a bound SUBMITTING/COMPLETED record.
Only authorized records are considered for recovery, attempts, completed quota and
cooldown. Unbound historical evidence is kept in JSON but omitted from this projection.

## Lifecycle and legacy handling

The conceptual `RESERVED → IN_PROGRESS → SUBMITTING → COMPLETED → COOLDOWN → RETAKE`
lifecycle is unchanged. An IN_PROGRESS persisted record represents the reservation;
COOLDOWN/RETAKE remain computed policy rather than new stored status fields. Three
completed or active slots per skill/profile, positive unique ordinals, one minute per
question, 24-hour cooldown, 410 expiry, 409 duplicate completion, Retry-After details
and existing evidence hierarchy remain. Expiry never scores incomplete answers.
Expired reservations release slots but preserve IDs and ordinals; retake numbers can
have gaps. Corrupt duplicate bound ordinals fail 503 rather than renumbering history.

Legacy assessment records have no account binding. They are never auto-claimed,
backfilled, scored, recovered, expired, counted or returned by owned APIs, including
legacy records referencing a newly owned profile. Historical evidence stays stored.
Missing records do not become owned through an email or guessed UUID. Administrative
association/recovery remains separately unimplemented.

## Historical application security matrix

Recorded phase production inventory was **31 operations / 30 paths**: three public reads,
three auth entries, four session operations, five profile operations, four assessment
operations and twelve deferred operations. Unknown/new routes stay private. Framework
docs remain disabled in production; explicit development adds four GET/HEAD paths.
CORS preflight is middleware, not an application operation.

Matrix test keys: **S** = `test_session_security.py` inventory/anonymous/CSRF/public/auth
regressions; **P** = `test_profile_ownership.py` production ownership regressions;
**A** = `test_assessment_ownership.py` bound success, cross-account denial and lifecycle
tests; **D** = its parametrized `test_non_assessment_operations_remain_blocked_for_owner_and_other_account`.
All exact functions are retained in those files. O means owner success 200,
foreign/missing/legacy/inactive 404; X means 401 anonymous, required CSRF 403,
otherwise authenticated 503 before the handler. Future behavior is design only.

| Method | Path | Class | Authentication | CSRF/Origin | Ownership | Status | Current | Future | Tests |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GET | `/health` | Public | No | No | No | N/A | 200 liveness | Same | S |
| GET | `/api/companies` | Public | No | No | No | N/A | 200 demo company info | Sanitized public read | S |
| GET | `/api/companies/{company_id}` | Public | No | No | No | N/A | 200/404 | Same | S |
| POST | `/api/auth/register` | Restricted entry | No operation | Origin/transport; no registration | No | Activation pending | 503; production HTTP 403 | Approved verified-email flow | S |
| GET | `/api/auth/login-challenge` | Entry | No | Exact Origin; issues token | No | Implemented | 200/403 | Same | S |
| POST | `/api/auth/login` | Entry | Credentials | Bootstrap token + Origin | No | Implemented | 200/401/403/409/413/422/503 | Verified ACTIVE login | S |
| GET | `/api/auth/session` | Account | Yes | Optional Origin checked | Current account/session | Implemented | 200/401/403/503 | Same | S |
| GET | `/api/auth/csrf` | Account | Yes | Exact Origin; issues token | Current session | Implemented | 200/401/403/503 | Same | S |
| POST | `/api/auth/session/renew` | Account | Yes | Required | Current session family | Implemented | 200/401/403/503 | Same rotation | S |
| POST | `/api/auth/logout` | Account | Cookie when present | Token with cookie; Origin always | Current session family | Implemented | 204/401/403/503 | Same revocation | S |
| GET | `/api/account/profiles` | Private | Yes | Optional Origin checked | Own ACTIVE associations | Implemented | 200 own references | Same | S,P |
| POST | `/api/profile/from-resume` | Private | Yes | Required | New own profile | Implemented | O; safe publication | Same | S,P |
| POST | `/api/profile/verify` | Private | Yes | Required | Own existing/server-created profile | Implemented | O; revision checks | Same | S,P |
| GET | `/api/profile/{profile_id}` | Private | Yes | Optional Origin checked | ACTIVE profile | Implemented | O; histories omitted | Same | S,P |
| PUT | `/api/profile/{profile_id}` | Private | Yes | Required | ACTIVE profile | Implemented | O; 409 stale/422 invalid | Same | S,P |
| POST | `/api/assessment/start` | Private | Yes | Required | ACTIVE profile/new bound session | Implemented | O; existing quota/cooldown | Same | S,A |
| GET | `/api/assessment/{assessment_id}` | Private | Yes | Required even on GET | ACTIVE profile + stored binding | Implemented | O; 410 expired | Same | S,A |
| POST | `/api/assessment/{assessment_id}/submit` | Private | Yes | Required | ACTIVE profile + stored binding | Implemented | O; 409 completed/410 expired | Same | S,A |
| GET | `/api/profile/{profile_id}/assessments` | Private | Yes | Required even on GET | ACTIVE profile + every projected session | Implemented | O; bound history only | Same | S,A |
| POST | `/api/predict` | Private | Yes | Required | Account processing | Pending | X | Approved account/quota inference | S,D |
| POST | `/api/salary-predict` | Private | Yes | Required | Account processing | Pending | X | Approved account/quota inference | S,D |
| POST | `/api/resume/upload` | Private | Yes | Required | Account upload policy | Pending | X | Approved account upload | S,D |
| POST | `/api/resume/analyze` | Private | Yes | Required | Account analysis policy | Pending | X | Approved account analysis | S,D |
| POST | `/api/profile/{profile_id}/predict` | Private | Yes | Required | Profile/prediction history | Pending | X | Owned inference/history | S,D |
| GET | `/api/profile/{profile_id}/placement-summary` | Private | Yes | Optional Origin checked | Profile/history | Pending | X | Owned summary | S,D |
| GET | `/api/profile/{profile_id}/readiness` | Private | Yes | Optional Origin checked | Profile/derived evidence | Pending | X | Owned readiness | S,D |
| GET | `/api/profile/{profile_id}/eligibility` | Private | Yes | Optional Origin checked | Profile | Pending | X | Owned eligibility | S,D |
| GET | `/api/profile/{profile_id}/eligibility/{company_id}` | Private | Yes | Optional Origin checked | Profile | Pending | X | Owned eligibility | S,D |
| GET | `/api/profile/{profile_id}/recommendations` | Private | Yes | Optional Origin checked | Profile | Pending | X | Owned recommendations | S,D |
| GET | `/api/profile/{profile_id}/skills` | Private | Yes | Optional Origin checked | Profile/combined evidence | Pending | X | Owned derived skills | S,D |
| GET | `/api/profile/{profile_id}/performance` | Private | Yes | Optional Origin checked | Mixed private history | Pending | X | Owned performance | S,D |

## Test strategy and actual results

Tests use fresh retained temporary JSON/auth stores and synthetic verified accounts;
test-only activation never appears as a production workflow. `test_assessment_ownership.py`
uses the real production-mode app/cookies/CSRF; original domain assertions remain in
the guarded harness. `test_session_http.py` also executes owned start/get/submit/history
over real HTTPS with certificate validation and graceful owned-server shutdown.

Focused coverage includes all four operations across anonymous, forged/revoked
sessions, CSRF, Origin and cross-account tokens; both account directions; parent/session
mismatches; inactive/corrupt/legacy isolation; denied requests preserving JSON hashes;
spoofed metadata; quota/concurrency/ordinals; expiry/cooldown/retake; evidence/completion
failures and owner-only recovery without rescore; collisions; corrupt JSON; IO/database
failures; account disable/auth-version invalidation; and twelve deferred routes.

| Retained run label | Passed | Failed | Errors | Skipped | Deselected | Warnings | Time |
| --- | --- | --- | --- | --- | --- | --- | --- |
| assessment-ownership-initial | 139 | 0 | 0 | 0 | 0 | 0 | 61.45 s |
| assessment-failure-paths-initial | 5 | 9 | 0 | 0 | 67 | 0 | 12.10 s |
| assessment-focused-final | 153 | 0 | 0 | 0 | 0 | 0 | 69.74 s |
| security-regressions | 316 | 0 | 0 | 0 | 0 | 0 | 128.86 s |
| backend-full-final | 980 | 0 | 0 | 0 | 0 | 10 | 234.20 s |

Runs overlap. The final 153 includes all 81 new ownership cases plus existing lifecycle/
retry tests. The final suite count reconciles as 907 previous cases minus eight old
deferred parametrizations plus 81 new cases = 980. The enabled four paths retain
inventory auth/CSRF denial checks and gain positive/cross-account/legacy/lifecycle tests;
no business assertion was weakened or deleted.

Eight initial added failures reproduced corrupt profile JSON returning 422 and corrupt
structure returning 503. Authorized profile loading now validates safely as 404 while
genuine IO errors remain 503. A ninth failure used a nonexistent password_version
column in a synthetic fixture; corrected to the existing auth_version, without a
schema change. Expanded focused and full runs pass. An initial evidence-helper
SyntaxError (reserved keyword as dictionary argument) was corrected before the
successful import/lifespan/31-operation/30-path check; it did not run application code.

Ten existing warnings come from `joblib/numpy_pickle.py:207`: assigning `array.shape`
is deprecated by NumPy 2.5. They remain visible; model loading/inference regressions
pass, with no dependency upgrades or warning filters. Frontend tests were not run
because frontend source and contracts were not implemented in this phase.

Exact child commands, outputs, exits, timing, baseline hashes and runtime inventory
are summarized in the dated results above. Reproduction uses the pinned Python
environment and `python -B -m pytest backend/tests/ -q -p no:cacheprovider`,
with the existing fixture-owned temporary stores. Startup/lifespan and nine source ASTs pass, with zero import/startup storage writes. Actual HTTPS assessment flow is included in both security and full-suite runs.

Preservation uses 2,789 baseline hashes, includes ignored prior evidence, and excludes
.git, virtual environments/node_modules/caches/agent settings and this new phase scratch
directory. All original paths and statuses remain; 558 protected root and 80 frontend
files are byte-identical, including 487 profile-store and 54 assessment-store files.
No live auth database existed at baseline and none was created. All 242,085 prior
journal suffix bytes are preserved. Branch/HEAD remain unchanged; index empty.
Detailed final hash and owned-process checks are retained with the phase evidence.
The final process audit verifies seven logged server identities, four production
graceful shutdown logs and five closed/rebindable ports; it terminates zero processes.
Two earlier audit failures arose from Windows reusing a former server PID for an
unrelated protected non-Python process. Read-only native identity resolved that reuse;
the unrelated process was left untouched. Three complete matrices, 48 local links and
nine Python ASTs pass the final static check. `git diff --check` passes.

## Remaining limitations and future integration

No general ownership/full security validation or public release approval is claimed.
Registration still has no approved email activation provider. Frontend mock login,
private browser caches, credentials/CSRF wiring and 410 GET handling need separately
authorized integration. Future React must include cookies plus current in-memory
CSRF and exact Origin for **both** lifecycle GETs, handle 401/403/404/409/410/429/503,
refresh CSRF after rotation and clear private state after logout/account switch.

Storage scanning is linear across assessment files; malformed unrelated files can
fail closed with 503 rather than being silently discarded. File/backup ACLs, manual
tampering, multi-host/network-filesystem locking, power-loss directory durability,
large-scale load, generalized abuse throttling and administrative legacy recovery
remain outside the validated scope. Partial exclusive writes can leave inaccessible
corrupt records requiring separately approved repair; no destructive compensation.
Short DB authorization transactions are not held throughout filesystem processing:
revocation before a subsequent authorization/write is rejected, but an administrative
change after acceptance cannot retroactively undo already accepted work.

Next separately authorized phase: **29.6.6 — Prediction, History and Recommendation
Ownership**. It has not been started. Frontend authentication and account-bound
idempotency also remain deferred; student deployment stays restricted until the
remaining ownership/security release requirements are complete.
