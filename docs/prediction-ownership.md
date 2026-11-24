# Prediction, history and recommendation ownership — Phase 29.6.6

> Historical snapshot: the original phase dates, design decisions and recorded
> test results below are preserved. Statements about the then-current inventory,
> unavailable features and pre-authentication behavior are superseded by the
> [reviewed 2026-11-24 release snapshot](../backend/DEPLOYMENT.md#reviewed-release-snapshot-2026-11-24).
> This documentation change reruns no application tests and establishes no new
> Linux/Docker or browser acceptance.

## Implemented scope and approved form policy

Ten existing operations now run through the normal secured application: direct
placement/salary forms, stored-profile prediction, readiness/skill gaps, placement
summary, both eligibility routes, recommendations, skills and performance/history.
The existing sessions, CSRF/Origin gate, authoritative ACTIVE profile associations,
profile locks, response schemas and calculators are reused. No database migration,
new database, dependency, frontend field or ML/model/dataset/mathematics change.

The user explicitly approved preserving **independent authenticated stateless forms**.
`POST /api/predict` and `POST /api/salary-predict` keep their exact existing input and
output schemas. They require a real session, CSRF and Origin; they do not require a
profile ID/revision or create/read student storage, history, ownership or retry cache.
Optional/extraneous client identity fields cannot establish server identity. Existing
unused salary compatibility fields and college-tier behavior remain unchanged.

All operations that target stored student data require the trusted account to own an
ACTIVE profile. Ownership is established before private reads, query/key validation,
company lookup, model inference, replay or writes. Foreign/missing/legacy-unowned,
pending/suspended/corrupt targets receive identical `404 Profile not found.` Existing
session failures stay 401; Origin/required CSRF failures stay 403; internal/storage
failures use redacted 503. Responses are `Cache-Control: private, no-store`.

## Account/profile/history relationship

`OwnedAnalyticsService` uses the existing owned-assessment profile access context,
which delegates to authoritative `OwnershipStore.authorize` and shared session
revalidation. It introduces no parallel ownership authority. The existing profile
transaction covers private loading, evidence/history filtering, calculations and
prediction persistence. Calculators receive one validated snapshot through internal
optional `snapshot` parameters; original isolated domain callers keep their contracts.

New stored prediction entries retain original fields and add server-only metadata:

| Field | Source/purpose |
| --- | --- |
| `prediction_id` | Server UUID; checked for uniqueness among bound entries |
| `account_id` | Trusted session's immutable account UUID |
| `profile_id` | Authorized parent profile UUID |
| `ownership_schema_version` | Supported integer binding version, currently 1 |
| `profile_ownership_version` | ACTIVE association version captured at creation |
| `source_revision`, `source_inputs` | Existing actual locked revision/mapped inputs |

Only records matching account, profile and association/version binding are projected.
Bound records must have a valid ID, UTC timestamp, positive source revision no newer
than the parent, finite probability/confidence and consistent unique IDs/keys. Corrupt
bound history fails closed without repair. Unbound/foreign/mismatched entries stay
stored but are not returned or replayed. Public history schemas retain their existing
fields, including source inputs/request ID, and omit new internal binding metadata.

There is no independent history/result-ID endpoint. Profile prediction returns its
owned history; performance returns owned prediction/assessment history plus summaries.
Historical source revisions remain historical: an older owned result can be listed,
but it cannot masquerade as current prediction or be replayed after a revision change.

## Prediction execution, revision and replay

The execution order is session → transport/Origin/CSRF policy → ACTIVE ownership →
locked private snapshot → bound history/evidence → revision/input/lifecycle checks →
unchanged inference → permission/current-snapshot recheck → atomic history append.
The existing gate can reject invalid transport/Origin before session resolution;
this policy is retained. Direct forms stop at account authorization and calculation.

Stored-profile prediction retains the existing verified/complete gate and response:
incomplete/unverified profiles return `ready_for_prediction=false` without inference
or history. Model features come only from the existing mapper, never client-supplied
owner identifiers or invented skill scores.

The existing optional `Idempotency-Key` is checked **after ownership**. Same key on
the same bound account/profile and unchanged verified/complete revision/inputs returns
the original result without inference or append. Different accounts/profiles use
independent scopes. Stale revision or changed inputs return redacted 409. Duplicate,
empty or oversized profile prediction headers receive redacted 422. Keys matching
unbound historical entries cannot promote them into authenticated replay: they return
a generic 409 requiring a new intent, without returning the record.

Concurrent keyed requests serialize under existing profile locks and append once.
History-only persistence does not increment revision. Concurrent profile edits retain
optimistic revision behavior; later performance flags older predictions as not current.
Failed pre-save writes preserve storage; a lost response after successful persistence
can replay the same bound key without duplicating history. Unkeyed explicit prediction
POSTs remain new intents and can append separate entries, as before.

This is the existing profile prediction retry contract secured by ownership, not the
general Phase 29.6.8 idempotency ledger. No TTL, durable PENDING ledger, new-key
namespace, direct/salary result cache, profile-creation or upload deduplication is added.

## Readiness, evidence, recommendations and performance

Readiness, skills, eligibility, recommendations, summary and performance use the same
locked profile snapshot. Existing eligibility thresholds, recommendation ranking,
readiness/evidence hierarchy, model preprocessing and score mathematics are unchanged.
Internal snapshot parameters avoid reloading a different revision through another
service. Company information is looked up only after profile authorization.

Assessment evidence is accepted only through the existing bound session/evidence
validator. Analytics scan/read records but **never run assessment recovery or expiry**.
Missing, legacy or mismatched session evidence is not projected. Previously durable
accepted evidence remains subject to the existing validator; corrupt matched evidence
fails safely. Assessment lifecycle GETs retain CSRF and their separately secured
recovery/expiry behavior. No assessment histories are rewritten by these analytics.

Profile-only responses still omit history/evidence; authorized specialized endpoints
provide them. No email inference, historical association, migration or claiming occurs.

## Historical API security matrix

Recorded phase production inventory was **31 operations / 30 paths**. Ten analytics
operations are enabled; only two standalone resume processing routes remain deferred
to their separately authorized integration scope. Framework docs remain production
404 and controlled in explicit development. Unknown/new registered routes remain
private by default; method variants and CORS policy are unchanged.

Test keys: **S** = `test_session_security.py`; **P** = `test_profile_ownership.py`;
**A** = `test_assessment_ownership.py`; **D** = `test_prediction_ownership.py`;
**H** = `test_session_http.py`. These are actual secured-app regressions; original
domain tests are separately isolated. O: owner 200 when domain prerequisites pass,
foreign/missing/legacy/inactive target 404. X: anonymous 401, required CSRF 403,
authenticated 503 before any handler. Future column denotes planned work only.

| Method | Path | Class | Authentication | CSRF/Origin | Ownership | Status | Current behavior | Future behavior | Tests |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GET | `/health` | Public | No | No | No | N/A | 200 liveness | Same | S,H |
| GET | `/api/companies` | Public | No | No | No | N/A | 200 demo company info | Sanitized public info | S |
| GET | `/api/companies/{company_id}` | Public | No | No | No | N/A | 200/404 | Same | S |
| POST | `/api/auth/register` | Restricted entry | No operation | Existing transport/Origin | No | Activation pending | 503; production HTTP 403 | Approved verification provider | S,H |
| GET | `/api/auth/login-challenge` | Entry | No | Exact Origin; issues token | No | Implemented | 200/403 | Same | S,H |
| POST | `/api/auth/login` | Entry | Credentials | Bootstrap CSRF/Origin | No | Implemented | Existing login contract | Same | S,H |
| GET | `/api/auth/session` | Account | Yes | Optional Origin checked | Current session/account | Implemented | Existing restoration contract | Same | S,H |
| GET | `/api/auth/csrf` | Account | Yes | Exact Origin; issues token | Current session | Implemented | Existing token contract | Same | S,H |
| POST | `/api/auth/session/renew` | Account | Yes | Required | Current family | Implemented | Rotation | Same | S |
| POST | `/api/auth/logout` | Account | Cookie when present | Token with cookie; Origin always | Current family | Implemented | Durable logout/no-cookie no-op | Same | S,H |
| GET | `/api/account/profiles` | Private | Yes | Optional Origin checked | Own ACTIVE associations | Implemented | 200 own references | Same | S,P,H |
| POST | `/api/profile/from-resume` | Private | Yes | Required | New own profile | Implemented | O; safe publication | Future retry integrity | S,P |
| POST | `/api/profile/verify` | Private | Yes | Required | Own existing/new profile | Implemented | O; reviewed revisions | Future retry integrity | S,P,H |
| GET | `/api/profile/{profile_id}` | Private | Yes | Optional Origin checked | ACTIVE profile | Implemented | O; history omitted | Same | S,P |
| PUT | `/api/profile/{profile_id}` | Private | Yes | Required | ACTIVE profile | Implemented | O; stale 409/invalid 422 | Same | S,P,D |
| POST | `/api/assessment/start` | Private | Yes | Required | ACTIVE profile/new binding | Implemented | Owned reservation | Future start retry integrity | S,A,H |
| GET | `/api/assessment/{assessment_id}` | Private | Yes | Required on lifecycle GET | ACTIVE profile + assessment binding | Implemented | Owned result/recovery; expiry 410 | Same | S,A,H |
| POST | `/api/assessment/{assessment_id}/submit` | Private | Yes | Required | ACTIVE profile + assessment binding | Implemented | Owned submission; duplicate 409/expiry 410 | Future retry validation | S,A,H |
| GET | `/api/profile/{profile_id}/assessments` | Private | Yes | Required on lifecycle GET | ACTIVE profile + each bound record | Implemented | Owned history/recovery | Same | S,A,H |
| POST | `/api/predict` | Private stateless | Yes | Required | No stored resource | Account authorization implemented | Existing form result; no history | Optional account retry cache | S,D,H |
| POST | `/api/salary-predict` | Private stateless | Yes | Required | No stored resource | Account authorization implemented | Existing salary form result; no history | Optional account retry cache | S,D,H |
| POST | `/api/profile/{profile_id}/predict` | Private | Yes | Required | ACTIVE profile + bound history | Implemented | O; keyed replay/409; no model for incomplete | General retry integrity | S,D,H |
| GET | `/api/profile/{profile_id}/placement-summary` | Private | Yes | Optional Origin checked | ACTIVE profile/snapshot | Implemented | O; read-only existing calculation | Same | S,D |
| GET | `/api/profile/{profile_id}/readiness` | Private | Yes | Optional Origin checked | ACTIVE profile/bound evidence | Implemented | O; existing readiness/gaps | Same | S,D,H |
| GET | `/api/profile/{profile_id}/eligibility` | Private | Yes | Optional Origin checked | ACTIVE profile | Implemented | O; existing eligibility | Same | S,D |
| GET | `/api/profile/{profile_id}/eligibility/{company_id}` | Private | Yes | Optional Origin checked | ACTIVE profile before company | Implemented | O; existing eligibility | Same | S,D |
| GET | `/api/profile/{profile_id}/recommendations` | Private | Yes | Optional Origin checked | ACTIVE profile/bound evidence | Implemented | O; existing ranking/limit | Same | S,D |
| GET | `/api/profile/{profile_id}/skills` | Private | Yes | Optional Origin checked | ACTIVE profile/bound evidence | Implemented | O; existing skills | Same | S,D |
| GET | `/api/profile/{profile_id}/performance` | Private | Yes | Optional Origin checked | ACTIVE profile + bound histories | Implemented | O; owned history and analytics | Same | S,D,H |
| POST | `/api/resume/upload` | Private deferred | Yes | Required | Account processing policy pending | Deferred to integration | X | Approved authenticated processing | S,P,A |
| POST | `/api/resume/analyze` | Private deferred | Yes | Required | Account processing policy pending | Deferred to integration | X | Approved authenticated processing | S,P,A |

## Tests, environment and actual validation

Synthetic verified accounts and multiple synthetic profiles use retained temporary
authentication/company/profile/assessment stores. Test-only activation remains isolated.
Direct forms are compared to actual unchanged calculators; profile analytics are
compared to original calculators through their existing response models. Cross-account
cases cover every stored-profile operation before query/key validation or side effects.
Authentication/Origin cases cover all ten operations; CSRF covers all three POSTs.
Additional tests cover bound history, legacy isolation, concurrent keyed requests,
same-key account/profile separation, stale revisions, lost responses, failed writes,
mid-inference revocation/suspension/auth-version changes, corrupt bindings/history,
bound assessment projection and concurrent profile edits.

The initial focused run had **113 passed, one failed, ten warnings** in 66.19 s.
The failure compared raw service output with API schema defaults; it was corrected by
rendering the original response schema before exact comparison. Final focused run:
**120 passed, ten warnings**, no failures/errors/skips/deselections, in 82.99 s.
The existing profile/assessment/lifecycle/retry/revision/session/HTTP/performance
selection passed **336 tests with eight warnings** in 148.98 s; no failures/errors/
skips/deselections. The additional contract-boundary selection passed **8 tests**
with **120 deselected**, ten warnings and no failures/errors/skips in 9.69 s. Those
cases cover empty/oversized/duplicate retry headers, ignored foreign identity fields
on stateless forms, unverified/incomplete profile inference gating and same-revision
source-input mismatch. There are now 128 cases in the ownership file.

The first full run passed **1,070 tests / ten warnings** in 278.15 s. The final full
run, including the eight added boundary cases, passed **1,078 tests / ten warnings**
in 285.32 s: **zero failed, errors, skipped or deselected**. Runs overlap and
must not be added. The previous 980-case suite loses 30 deferred parametrizations
(ten newly enabled operations in each of the session/profile/assessment deferred
selections) and gains 128 ownership cases: 980 - 30 + 128 = 1,078. Every enabled path
retains anonymous/CSRF inventory checks and gains actual production ownership tests.
No existing business assertion or test file was removed or weakened.

Runtime import/startup/shutdown, 31-operation/30-path inventory and 13 source ASTs pass;
cold startup writes no storage. Original and secured stateless request/response model
types match exactly. One runtime helper initially used an unsupported FastAPI ModelField
attribute; corrected to its installed field_info.annotation, with no application change.
HTTPS tests use real production cookies and trusted synthetic certificates, including
stateless calculations and owned prediction/replay/history/evidence flows.

No dependencies were installed or upgraded. Existing CPython 3.14.6/Argon2-capable
environment is used. Warnings remain visible: joblib assigning array.shape is deprecated
by NumPy 2.5. Frontend source/tests/build are unchanged and outside this phase.

## Remaining limits and next phase

This is not public deployment readiness or full security certification. Registration
still awaits approved email activation; frontend authentication/in-memory CSRF/profile
switching are not implemented here. Two standalone resume operations stay blocked.
No real historical record is claimed or tested. Existing local cooperating file locks
and atomic replacement remain; multi-host/network-FS, manual tampering, power-loss,
general throttling, administrative association and stronger storage guarantees remain
outside this validation. Corrupt unrelated assessment files can fail closed during a
scan. Short authorization transactions cannot retroactively undo already accepted work.

No retry TTL/model-version fingerprint ledger, direct/salary cache or creation/upload
idempotency is claimed. General account-bound retry integrity belongs to 29.6.8.
The next phase is **29.6.7 — Frontend Authentication Integration**, after this phase's
completion report. It has not been started.


## Final preservation and process verification

The phase baseline contains **2,818 files**: the same documented inventory method
excludes .git, virtual environments/node_modules, caches/agent settings and this
phase's own evidence directory; prior scratch/backup evidence remains included.
All original paths and pre-existing modified/untracked entries remain. Sixteen
baseline files are intentionally edited and four project files are created; no
baseline file is deleted. All **558 protected root files**, including **487 profile
store files and 54 assessment store files**, and **80 frontend files** are identical
to their baseline hashes. Datasets, model artifacts, salary assets, company storage,
historical prediction arrays and prior scratch evidence are preserved. No live
authentication database existed at baseline or was created; existing authentication
services/configuration/schema and prior synthetic authentication evidence remain.
Earlier historical phase report suffix bytes, including the pre-implementation checkpoint,
remain identical: **260,117 bytes**. The original preflight journal suffix is also
preserved. Branch is `bhargav-frontend`, HEAD is
`f84099349d104e4e77c7080fba4465ca4e3470a4`, index empty; final working tree has
**56 modified tracked files, 85 grouped untracked entries and 108 expanded untracked
paths**. No Git mutation was executed. `git diff --check` passes.

The post-suite read-only process audit confirms 9
logged server PIDs, 6 production
graceful-shutdown logs and 7 closed,
rebindable ports. It terminates zero processes. An earlier audit ran while the final
suite was still using its intentionally reused loopback test port and failed its
port-closed check; the audit was rerun after suite shutdown without weakening the
check. A WMI process-inventory attempt was access-denied; native read-only checks
succeeded. Neither event changed or terminated an unrelated process.
