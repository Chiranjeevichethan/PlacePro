# Account-bound retry integrity — Phase 29.6.8

> Historical snapshot: the original phase dates, design decisions and recorded
> test results below are preserved. Statements about the then-current inventory,
> unavailable features and pre-authentication behavior are superseded by the
> [reviewed 2026-11-24 release snapshot](../backend/DEPLOYMENT.md#reviewed-release-snapshot-2026-11-24).
> This documentation change reruns no application tests and establishes no new
> Linux/Docker or browser acceptance.

Existing sessions, ACTIVE ownership, JSON records, SQLite associations and local
cooperating file locks are reused. No database, schema migration, model change or
historical backfill is introduced. Idempotency is optional through the existing
CORS-approved `Idempotency-Key` header (one nonblank value, at most 128 characters).
Clients cannot supply account identity. Keys are not authorization credentials.
Authentication and required Origin/CSRF run first. Target ownership is verified
before key/payload checks, discovery, inference, expiry, recovery or writes.

| Operation | Retry behavior |
| --- | --- |
| POST /api/profile/verify without a profile | Account/operation/key determines a server resource UUID; identical receipt replays the original revision-1 profile. Different payload or later revision: generic 409. |
| POST /api/profile/from-resume | Same account/key/file bytes/name/type replays the original profile and extraction analysis without re-extracting. Changed file or subsequently edited/confirmed profile: 409. |
| PUT profile / POST confirmation of existing profile | Account/profile/operation/key and canonical payload fingerprint must match a receipt at the current revision and ACTIVE association version. Conflict: 409, no write. |
| POST /api/assessment/start | Account/profile/key, skill/count and current source revision must match. Valid IN_PROGRESS retry returns the same reservation/questions/deadline with current server time. Completed: 409; expired: 410. |
| POST assessment submission | Existing immutable account/profile/session binding, accepted answers and optional scoped key/fingerprint are checked before recovery. Changed accepted payload/key: 409. Interrupted same submission recovers once; completed duplicate stays 409 and GET provides the result. |
| POST owned profile prediction | Existing account/profile/ACTIVE association, source revision and exact mapper inputs are required before cached replay. One keyed history entry under the profile lock. Changed source: 409; foreign target: 404. |
| Stateless placement and salary forms | Independent authenticated calculations retain their bodies/results, with no stored operation/history or private cached replay. Repetition calculates again; no duplicate stored history can result. |
| GET analytics/history | Every request reauthorizes; assessment lifecycle GETs also require CSRF and can recover only owned bound sessions. |
| Standalone resume processing | Remains 503 at the default-private gate. |

New profile records carry private `_creation_receipt` metadata. An unkeyed creation
still uses random uuid4. For keyed creation the server hashes immutable account,
operation and key into a UUID with version-4 format; this resource identifier is
deterministic, never a session secret or permission proof. The same reservation is
found after a lost response, including PENDING state. No client-selected profile ID,
email inference or legacy claim is allowed. ACTIVE association and receipt payload
must match before replay. Existing/symlink/legacy collisions cannot be overwritten.

The existing reserve → exclusive profile write → verify digest → activate workflow
persists the creation receipt with the profile. Pending/failed/incomplete writes
stay inaccessible and conflicting retries cannot publish another profile or rerun
extraction. Recovery/repair of these records needs a separate authorized maintenance
decision; this phase neither deletes orphans nor claims unfinished records.

Profile update/confirmation receipts are private `_request_receipts`, preserved by
domain updates along with creation metadata, prediction history and assessment
evidence. Metadata writes do not advance the profile revision. The existing domain
update commits before its receipt write; if the latter fails, HTTP 503 is returned.
Retry with the original reviewed revision/payload uses existing optimistic exact
edit replay and writes the receipt without duplicating a revision. A newer/different
edit conflicts. This is a recoverable two-write protocol, not an atomic database
transaction. Response schemas omit all receipt/account binding fields.

Assessment start receipts are saved in the same exclusive session write as the
reservation. Submission receipts are saved with accepted answers/score/SUBMITTING
state before existing evidence recovery. Evidence hierarchy, cooldown, quota,
unique attempt numbering, randomized questions and deadlines remain unchanged.
Unauthorized requests cannot trigger recovery, expiry or evidence writes.

The frontend keeps keys with a reviewed mounted intent; changed payload/profile/
revision generates a new intent. Resume retries keep the file-selection key.
Assessment start persists a scoped pending key before delivery even without an
assessment ID, and submission keys accompany existing pending answer drafts.
Keys contain no auth secret and are never an authentication fallback. Account and
profile switching remounts controllers; server authorization remains mandatory.

Validation uses actual production ASGI with temporary synthetic stores and existing
lifecycle/model suites. Tests cover cross-account keys, multiple profiles, concurrent
creation/start, stale revisions, changed payloads, duplicate headers, legacy
collisions, pending activation/storage failures, lost receipt writes, revoked/expired/
disabled sessions, recovery and once-only evidence/history. Frontend tests cover
intent changes, lost start delivery and unchanged request bodies with retry headers.
The historical focused/full/test/lint/build results and initial failures are
summarized below; current public reproduction commands are linked above. The initial test run found that first creation used
an ownership transaction before that table existed; session-store validation fixes
it without a migration. The synthetic answer fixture uses `correct_answer`.

Limitations: keys have no TTL/garbage collection; choosing a new key or sending an
unkeyed request represents new intent. Direct calculators are not cached. There
is no durable browser File recovery after closing an upload dialog; reopening and
reselecting is new intent. Pending creation is quarantined, not auto-repaired.
File-lock guarantees require cooperating processes sharing local storage. SQLite
and JSON do not form one shared transaction; network filesystems/multi-host/manual
tampering/power loss and abuse limits are not certified. Model artifacts/version
are unchanged; no model-content version ledger was added. General deployment
hardening and approved activation/provider remain prerequisites for public release.
Next authorized phase: 29.6.9 full integration and security validation.

Final results: 1,116 backend passed, zero failed/errors/skipped/deselected,
ten existing joblib/NumPy warnings (311.95 s). Focused corrected retry run:
34 passed/eight warnings; extended compatibility selection: 132 passed/eight
warnings. The broader lifecycle/prediction selection had 308 passed/one setup
error/ten warnings because two owned runners requested the same loopback port;
the failed live test passed alone on a distinct port (one passed, no warnings).
Initial full run: 1,110 passed/two failed/ten warnings. Empty metadata was removed
from untouched legacy profiles; the historical no-idempotency test now exercises
unkeyed creation and retains its four-distinct-record assertion. New keyed tests
assert one record under concurrency. Initial first-creation run: eight failed,
26 setup errors; corrected without weakening authentication. All outputs retained.

Frontend: 181 passed, zero failed/cancelled/skipped/todo. Lint and fresh production
build pass; Vite's outside-root/no-empty warning remains visible. Three Chromium
assertions verify the separate dashboard Save profile prediction action: one
history write, disabled repeated intent and refreshed trend. This action never
converts stateless form inputs into stored profile data. Production import/startup/
shutdown, 31-operation/30-path inventory, unchanged stateless schema types, 96
Python ASTs and 73 local documentation links pass; cold startup writes no storage.
