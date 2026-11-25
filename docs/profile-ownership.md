# Profile ownership — Phase 29.6.4

> Historical snapshot: the original phase dates, design decisions and recorded
> test results below are preserved. Statements about the then-current inventory,
> unavailable features and pre-authentication behavior are superseded by the
> [reviewed 2026-11-24 release snapshot](../backend/DEPLOYMENT.md#reviewed-release-snapshot-2026-11-24).
> This documentation change reruns no application tests and establishes no new
> Linux/Docker or browser acceptance.

Implemented 2026-11-09 against the complete working tree on `bhargav-frontend`, HEAD
`f84099349d104e4e77c7080fba4465ca4e3470a4`. This phase implements profile ownership
only. Assessment, prediction, history, recommendation and frontend authentication
work remains deferred. This is not a production release or penetration-test report.

> Latest state, Phase 29.6.6: owned analytics and authenticated stateless forms are
> enabled. See [prediction ownership](prediction-ownership.md) for the current matrix.
>
> Historical Phase 29.6.5: four assessment operations enforce account/profile/
> assessment binding; twelve other student operations remain blocked. The implementation,
> current complete matrix and latest tests are in [assessment ownership](assessment-ownership.md).
> The Phase 29.6.4 inventory/results below are retained as historical phase snapshots.

## Ownership architecture

The normal [application](../backend/app/main.py) keeps the existing unconditional
[default-private gate](../backend/app/security.py). That gate resolves the real
server-side session, validates transport/Origin and required CSRF, and puts its
internal identity in `request.state.authenticated_account`. The
[owned profile router](../backend/app/routes/owned_profile.py) and
[service](../backend/app/services/owned_profile_service.py) receive that identity;
no request account ID, profile ID, email, confirmation flag or browser state is
trusted as ownership. The router refuses a missing gate identity even when mounted
without the gate.

An account can own multiple profiles. Each profile has exactly one immutable
association, with ACTIVE status required for access. The authoritative mapping lives
in SQLite, separately from student JSON. Profile contact email can differ from the
account email; matching another account or legacy contact email creates no rights.
There is no claim, transfer, merge, activation or recovery endpoint.

Five operations now pass the gate into ownership enforcement: owned reference list,
profile read/edit, resume-based creation and profile confirmation/creation. All
sixteen other student operations still fail closed, even for an owned profile.

## Database schema and lifecycle

[OwnershipStore](../backend/app/services/ownership_store.py) uses the existing
dedicated `PLACEPRO_AUTH_DB` (default `data/auth/accounts.sqlite3`) and the existing
account/session connection and transaction machinery. No import/startup writes,
company database changes, new database, account rewrite or student migration occurs.
The table is added transactionally on first successful reservation; reads/listing do
not initialize it. Existing account application ID and schema version 1 remain.

| Field | Implemented constraint / purpose |
| --- | --- |
| `profile_id` | Server canonical lowercase UUID v4; NOT NULL primary key, single association per profile |
| `account_id` | Immutable existing account UUID; NOT NULL foreign key to `accounts(account_id)` |
| `status` | CHECK: PENDING, ACTIVE, FAILED or SUSPENDED; only PENDING → ACTIVE is implemented |
| `association_version` | Positive integer; 1 at reservation, 2 at activation |
| `created_at`, `updated_at` | Timezone-aware UTC ISO timestamps, validated on reads |
| `creation_sha256` | SHA-256 fingerprint of the exact originally serialized bytes; 64 lowercase hex characters validated by service |

The `(account_id,status)` index supports own-profile lookup. A database trigger rejects
changes to profile/account ID, creation timestamp and creation fingerprint. Table SQL,
columns, foreign key and immutable trigger are checked before use; incompatible or
missing security structure is rejected, never silently repaired. Rows are validated
for canonical IDs, status, integer version, timestamps and hash encoding. The
fingerprint is publication evidence, not a permanent integrity checksum after edits.
No passwords, cookie secrets, CSRF tokens or authentication hashes are in this table.

Reservation/activation use short `BEGIN IMMEDIATE` transactions. PK/FK/CHECK/trigger
constraints enforce integrity independently of browser requests. Concurrent accounts
reserving the same profile have one winner; a duplicate cannot change that winner or
activate its pending record. Existing account rows, sessions and login challenges are
unchanged by ownership transactions. Existing connection checks use a five-second
busy timeout and briefly take a write lock even for schema validation on reads; this
can limit concurrency and returns safe failures rather than bypassing authorization.

## Server-generated IDs and safe creation

`POST /api/profile/verify` without a `profile_id` (or with null) creates a new reviewed
profile. A supplied ID means **confirm this existing ACTIVE owned profile**, never
create/claim a chosen ID. Missing, empty, malformed, legacy or foreign supplied IDs
receive the same 404. Root owner/account/association fields are forbidden and yield
redacted 422; unknown nested fields cannot influence the trusted session identity.
The normal PUT mismatch rule remains. Client creation revision, histories, evidence,
resume originals and provenance cannot select ownership or forge server history.
New manual profiles always start revision 1 with freshly computed user provenance,
empty server histories/evidence/originals/ML provenance, and `verified=true` as claim
confirmation. This flag is not account verification or authorization.

`POST /api/profile/from-resume` requires exactly one multipart `file` field. Extra
profile/account/owner fields are rejected before extraction. Existing PDF/DOCX file
validation, 5 MiB limit, OCR refusal, extraction and analysis remain. The server
generates an independent UUID; a successful resume draft starts revision 1,
`verified=false`, with existing provenance/original-value/analysis contracts. Confirmation
keeps that same ID and association. Raw uploaded resumes are not added to profile storage.

Creation follows:

1. Authenticate and validate Origin/CSRF before parsing or extraction.
2. Prepare/validate the profile and complete resume analysis without persistence.
3. Generate a server UUID, serialize completely, and calculate the byte fingerprint.
4. Refuse any existing generated target path; reserve PENDING ownership transactionally.
5. Acquire the existing cooperating per-profile thread/OS lock and revalidate the session.
6. Create JSON with exclusive binary mode `xb`, flush and fsync. A racing file or
   existing symlink cannot be replaced by this creation write.
7. Under that lock, re-read and validate schema, exact ID, revision 1 and byte fingerprint.
8. Revalidate account/session in the activation transaction; activate only the same
   account's PENDING association with the same fingerprint.
9. Return safe profile/analysis information only after durable activation commits.

The new [preparation/exclusive-write helpers](../backend/app/services/profile_service.py)
reuse the existing domain code. Production uses the owned router; the original domain
router is retained for isolated business regressions. No application bypass flag exists.

## Cross-storage consistency and recovery limitations

SQLite metadata and profile JSON cannot participate in one shared transaction. The
staged workflow guarantees **fail-closed publication**, not distributed atomicity.

| Failure boundary | Retained state / external behavior |
| --- | --- |
| Invalid input/extraction or initial path collision | No publication; existing profile untouched; 422/413/415/409 as applicable |
| Reservation failure/rollback | No new profile write; generic 503; no activated association |
| Exclusive write failure or racing collision | PENDING association, possibly partial/orphan JSON; generic 503/409 |
| Verification mismatch or failed activation commit | JSON and PENDING association retained, inaccessible; generic 503/409 |
| Session/account revoked before acceptance/activation | 401, no activation; an already written new JSON stays inaccessible |
| Activation committed but response lost | Valid owned profile remains; a new creation retry can create another profile |

No historical deletion is used as compensation. Pending/orphan records are never
listed or read/confirmed through student APIs. There is no automatic repair, pending
activation, email claim or ownership reassignment. Any future recovery requires a
separately approved administrative process with auditable publication evidence.
Account-bound idempotency is explicitly **not implemented**; sending an Idempotency-Key
to creation does not deduplicate it. Repeated creations generate distinct IDs.

Fsync and exclusive writes are tested on the current Windows host. Multi-host/network
filesystem consistency, filesystem tampering, directory durability after power loss
and administrative recovery are not validated. Filesystem/backup ACLs remain essential.

## Profile reads, edits and confirmation

Ownership must be established before loading private JSON, validating target profile
fields, creating target lock artifacts or calling domain operations. Canonical foreign,
missing, legacy-unowned, PENDING and corrupt-association targets receive indistinguishable
`404 {"detail":"Profile not found."}`. A PUT foreign target is rejected before JSON
parsing; verification identifies its supplied target before profile-field validation.
Malformed JSON itself receives redacted 422 because it cannot identify a target.

After initial authorization, the service requires an existing regular non-symlink
file, takes the existing profile lock, and rechecks session/account and ACTIVE ownership
in a short acceptance transaction. Missing files do not create new lock artifacts.
Stored JSON must validate as a profile, match the target ID and retain a positive
revision; missing/corrupt/mismatched JSON receives 404 and is not repaired. Filesystem
IO failures and failed persistence use safe generic 503 responses without private paths.

PUT and existing confirmation require the reviewed revision (422 if omitted). They
reuse the original editable-field validation, optimistic comparison, reentrant locks,
atomic replacement and protected-field restoration. A material edit advances revision
and clears claim confirmation; explicit confirmation advances revision when changed.
Identical retries remain harmless, differing stale revisions receive 409, and concurrent
distinct edits have one success with stale losers. No revision reset, silent newer-data
overwrite or history rewrite is added. Existing legacy revision acceptance remains only
in the isolated original domain API; production owned edits require a revision.

The acceptance transaction establishes permission for that operation. A logout or
administrative change after acceptance does not retroactively undo an accepted update;
future requests fail. Auth SQLite is not held locked across every JSON update. Tests
cover revocation before acceptance and between new-file write and activation.

Production profile responses preserve the profile/completion/message envelope and
resume analysis fields, but deliberately **omit `prediction_history` and
`assessment_evidence`**. These remain unchanged in stored JSON and cannot be edited by
clients. This prevents profile GET from becoming a shortcut to deferred history/evidence
APIs. ML feature completion maps existing claim inputs; it performs no model inference
or assessment recovery. Original resume values are available only within the owned
profile contract. Full frontend integration remains a later phase.

## Error and security boundary

| Request | Current response |
| --- | --- |
| Anonymous private operation | 401 before parsing/private data access |
| Invalid transport/Origin or required CSRF | 403 before protected operations |
| Foreign/missing/unowned/pending/corrupt ownership target | Uniform 404, no target disclosure |
| Own valid profile read/edit/creation/confirmation | 200 when successful |
| Invalid fields, root ownership spoof or missing reviewed revision | Redacted 422 |
| Stale differing edit / creation collision | Safe 409 |
| Ownership storage unavailable for target lookup | Uniform 404; never grant access |
| List/creation/persistence/auth storage unavailable | Safe 503; never expose internals |
| Authenticated deferred operation with required CSRF | 503 with the unchanged pending-ownership message |

Auth/session failures preserve their existing 401/403/503 semantics; they cannot be
masked as ownership successes. Every profile response uses `Cache-Control: private,
no-store`. Resume errors preserve status codes but use fixed messages, including parser
failures; no client MIME/extension or internal extraction exception is echoed.
No private payload, credentials, session secrets or SQL errors are logged.
Cookie policy, CSRF tokens, logout/renewal, Origin/CORS and production HTTPS requirements
are reused from [session security](session-security.md), with no dependency changes.
Owned requests revalidate sessions; idle renewal remains through the existing session/
CSRF/explicit-renew endpoints. Rejected requests do not extend session activity.

## Legacy isolation

No legacy profile is scanned, rewritten, merged, assigned, renamed or deleted. No
historical ID changes. Missing associations mean denied access, including matching
account/profile emails. No migration script or ownership-claiming route exists.
Authentication storage remains separate from student profiles, assessment records,
prediction histories, company recruitment data and ML artifacts. Existing records
remain available to existing trusted offline/domain code, never arbitrary authenticated
student APIs. Administrative association decisions are still unimplemented.

## Historical application security matrix

Recorded phase production inventory: **31 operations / 30 paths**. Breakdown: 3 public reads,
3 auth entries, 4 account/session operations, 5 ownership operations, 16 deferred
student operations. Development additionally registers four framework paths with
GET/HEAD; production documentation routes remain 404. OPTIONS is CORS middleware,
not an application operation. Unknown new registered routes stay private by default;
anonymous 401, authenticated 503 unless explicitly approved. Unknown API paths become
authenticated 404; unsupported methods become 405 only after required security checks.

Shorthand: **O** = anonymous 401; invalid required CSRF/Origin 403; foreign/unowned/
missing/corrupt target 404; owner success 200. **D** = anonymous 401; invalid required
CSRF 403; authenticated 503 pending later authorization, before any domain call.
Future column describes design intent only. Test references:

- **OA**: [test_profile_ownership.py](../backend/tests/test_profile_ownership.py),
  `test_account_bound_creation_server_uuid_multiple_profiles_and_persistent_associations`.
- **OR**: `test_missing_foreign_legacy_and_pending_targets_have_identical_404_before_validation`.
- **OU**: `test_owned_edit_confirmation_exact_retry_stale_conflict_and_revision_requirement`.
- **OC**: `test_resume_creation_is_owned_draft_with_stable_id_through_confirmation`.
- **OD**: `test_owned_profile_cannot_unlock_deferred_operations` (all 16 operations).
- **SA**: [test_session_security.py](../backend/tests/test_session_security.py),
  `test_every_student_operation_denies_anonymous_before_parsing` (all 21 private student/account-list operations).
- **SC**: `test_private_mutations_and_lifecycle_gets_require_csrf_before_pending_ownership`.
- **SP**: `test_public_health_and_company_contracts`.
- **SL**: `test_real_login_session_csrf_restore_logout_and_revoked_cookie`.
- **SO**: `test_tokens_not_disclosed_to_missing_or_disallowed_origins`.
- **SR**: `test_rotation_cookie_and_token_replacement`.

| Method | API path | Class | Auth | CSRF | Ownership | Implementation | Current | Future | Test |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GET | `/health` | Public | No | No | No | N/A | 200 liveness | Public liveness | SP |
| GET | `/api/companies` | Public | No | No | No | N/A | 200 demo requirements; first-use seed possible | Sanitized company reads | SP |
| GET | `/api/companies/{company_id}` | Public | No | No | No | N/A | 200/404 | Sanitized company read | SP |
| POST | `/api/predict` | Private | Yes | Yes | No profile target | Account processing pending | D | Account/quota stateless inference | SA,SC,OD |
| POST | `/api/salary-predict` | Private | Yes | Yes | No profile target | Account processing pending | D | Account/quota stateless inference | SA,SC,OD |
| POST | `/api/resume/upload` | Private | Yes | Yes | No profile target | Account processing pending | D | Approved account upload policy | SA,SC,OD |
| POST | `/api/resume/analyze` | Private | Yes | Yes | No profile target | Account processing pending | D | Approved account analysis policy | SA,SC,OD |
| GET | `/api/account/profiles` | Private | Yes | No | Own ACTIVE associations | Implemented | 200 own ID references only; safe 503 failure | Same | SA,OA |
| POST | `/api/profile/from-resume` | Private | Yes | Yes | New own association | Implemented | O; safe publication only | Same with future retries | SA,SC,OC |
| POST | `/api/profile/verify` | Private | Yes | Yes | Existing own / server-created | Implemented | O; revision required for existing target | Same with future retries | SA,SC,OA,OR,OU |
| GET | `/api/profile/{profile_id}` | Private | Yes | No | Profile | Implemented | O; history/evidence omitted | Owned profile-only read | SA,OA,OR |
| PUT | `/api/profile/{profile_id}` | Private | Yes | Yes | Profile | Implemented | O; stale 409 / invalid 422 | Same | SA,SC,OR,OU |
| POST | `/api/profile/{profile_id}/predict` | Private | Yes | Yes | Profile/history | Operation pending | D | Owned prediction before key lookup | SA,SC,OD |
| GET | `/api/profile/{profile_id}/readiness` | Private | Yes | No | Profile/evidence | Operation pending | D | Owned derived readiness | SA,OD |
| GET | `/api/profile/{profile_id}/placement-summary` | Private | Yes | No | Profile/history | Operation pending | D | Owned read-only summary | SA,OD |
| GET | `/api/profile/{profile_id}/eligibility` | Private | Yes | No | Profile | Operation pending | D | Owned eligibility | SA,OD |
| GET | `/api/profile/{profile_id}/eligibility/{company_id}` | Private | Yes | No | Profile | Operation pending | D | Own profile before company lookup | SA,OD |
| GET | `/api/profile/{profile_id}/recommendations` | Private | Yes | No | Profile | Operation pending | D | Owned recommendations | SA,OD |
| POST | `/api/assessment/start` | Private | Yes | Yes | Profile/new assessment | Assessment ownership pending | D | Owned reservation before lifecycle sync | SA,SC,OD |
| POST | `/api/assessment/{assessment_id}/submit` | Private | Yes | Yes | Stored assessment/profile | Assessment ownership pending | D | Owned attempt before acceptance | SA,SC,OD |
| GET | `/api/assessment/{assessment_id}` | Private | Yes | Yes | Stored assessment/profile | Assessment ownership pending | D | Own attempt before expiry/recovery | SA,SC,OD |
| GET | `/api/profile/{profile_id}/assessments` | Private | Yes | Yes | Profile/attempt inventory | Assessment ownership pending | D | Ownership before expiry/recovery | SA,SC,OD |
| GET | `/api/profile/{profile_id}/skills` | Private | Yes | No | Profile/evidence | Operation pending | D | Owned evidence | SA,OD |
| GET | `/api/profile/{profile_id}/performance` | Private | Yes | No | Profile/history | Operation pending | D | Owned history/performance | SA,OD |
| POST | `/api/auth/register` | Restricted public entry | No | No operation allowed | No | Activation pending | 503 before parsing; HTTP production 403 | Approved verified-email workflow | registration_stays_unavailable_before_parsing_and_no_activation_route |
| GET | `/api/auth/login-challenge` | Public entry | No | Issues pre-login token; Origin | No | Implemented | 200/403 | Bounded bootstrap | login_requires_bootstrap_csrf_origin_before_credentials_and_body |
| POST | `/api/auth/login` | Public entry | Credentials | Challenge + Origin | No | Implemented | 200/401/403/409/413/422/503 | ACTIVE verified account session | login_failure_is_generic_and_never_creates_sessions; SL |
| GET | `/api/auth/session` | Private account | Yes | No | Current session/account | Implemented | 200/401/403/503 | Same restoration | SL |
| GET | `/api/auth/csrf` | Private account | Yes | Issues session token; Origin | Current session | Implemented | 200/401/403/503 | Same session binding | SO |
| POST | `/api/auth/session/renew` | Private account | Yes | Yes | Current family | Implemented | 200/401/403/503 | Atomic rotation | SR |
| POST | `/api/auth/logout` | Private account; no-cookie no-op | Valid cookie to revoke | Yes with cookie; Origin always | Current family | Implemented | 204/401/403/503 | Durable family revocation | SL |

Full short test names in authentication rows refer to `test_`-prefixed functions in
`test_session_security.py`. GET lifecycle CSRF remains deliberate even though those
operations are blocked. The original handler for profile prediction is registered
unchanged; the gate rejects it before its request body, key replay or model/history
operation. No owned-profile permission spills into later phases.

## Regression strategy and actual results

New [ownership-store tests](../backend/tests/test_ownership_store.py) exercise FK/PK/
immutable constraints, persistence, pending isolation, simultaneous reservation,
duplicate activation, commit rollback, lock failure, corrupt schema/rows, forged
internal identities and revoked/status/version/password-invalidated sessions.
Ownership HTTP tests use the actual normal production-mode ASGI application, real
Argon2 credentials, real session cookies and real CSRF, with two synthetic accounts
and temporary auth/profile/assessment/company stores. No dependency override grants
ownership. They cover reads/edits/confirmation, collision and write/activation failures,
cross-account and matching-email isolation, numeric validation, exact retries,
concurrent reads/edits/creation, no sensitive errors/logs, stored history preservation
and all deferred operations remaining blocked without side effects.

The existing domain harness retains original business assertions and has no production
enable switch. Session tests now distinguish the five owned operations from sixteen
deferred ones while retaining anonymous and CSRF coverage over all private routes.
The real [production HTTP/HTTPS tests](../backend/tests/test_session_http.py) additionally
create/read/list an owned profile over trusted synthetic TLS, deny legacy 404 and owned
readiness 503, and retain cookie/logout/shutdown and sentinel preservation assertions.
This explains changes to old 503 expectations; business assertions were not weakened.

Application/tests use the existing validated
CPython 3.14.6 environment at
`this document's dated verification summary`; the root environment
does not contain Argon2 and was not modified. All pytest runs use `-B -m pytest`,
`-q -p no:cacheprovider`, temporary stores and retained artifacts.

| Run | Passed | Failed | Errors | Skipped | Deselected | Warnings | Seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Initial ownership selection | 70 | 4 | 0 | 0 | 0 | 0 | 69.26 |
| Expanded corrected ownership selection | 83 | 1 | 0 | 0 | 0 | 0 | 59.91 |
| Final ownership selection | 84 | 0 | 0 | 0 | 0 | 0 | 56.80 |
| First full backend | 901 | 0 | 0 | 0 | 0 | 10 | 182.52 |
| Resume error redaction | 6 | 0 | 0 | 0 | 67 | 0 | 7.69 |
| **Final full backend** | **907** | **0** | **0** | **0** | **0** | **10** | **184.60** |

The initial run found a nested SQLite connection on an absent ownership table: the
outer schema read retained a transaction while an inner session revalidation needed
the account-store write lock. Moving that second validation after the outer transaction
closed corrected three empty-list/reservation/revocation failures. The fourth failure
was a new test using production origins with development configuration; explicit empty
development origins corrected the test without relaxing production policy. Expanded
failure: an ACTIVE association pointing to a missing synthetic file created a lock
artifact on denied access. The service now checks file existence after ownership and
before locking, and repeats its check inside the lock. Invalid stored JSON/identity/
revision is also denied rather than repaired. All earlier failing cases pass finally. A subsequent source review found the
new resume route could expose an existing extraction exception string. It now
uses fixed safe messages; six new malformed/empty/truncated/oversized/internal-error
tests pass before the final full repetition. The initial 901 full passes remain
historical evidence; 907 validates the final executable code.

Full-suite coverage includes ownership/storage, account/password, sessions/CSRF/gate,
original profile/resume/revision, assessment lifecycle/retry/concurrency, placement and
salary inference and all eight live HTTP cases. The final 907 total is 820 previous cases
+ 90 new ownership cases - 4 obsolete pending-profile-route parametrizations + 1 new
anonymous owned-list parametrization. No test functions/assertions were deleted; the
profile pending expectations now have stronger ownership tests. Focused runs overlap
the full suite and must not be summed as unique coverage. Ten existing warnings are
joblib's `array.shape` use deprecated by NumPy 2.5, emitted by integration model loads;
they remain visible and are not suppressed. No frontend, lint/build or browser suite
was rerun because frontend files are unchanged and frontend authentication is deferred.

Standalone final checks pass: import/startup/shutdown with no database/storage writes,
ungated router refusing identity, exact 31/30 inventory in both matrices, 44 valid local
documentation links and AST parsing of all twelve changed/new executable files.
The knowledge updater emitted one scratch-only SyntaxWarning for literal
PowerShell backslashes; its template was changed to a raw string without
suppressing warnings. This is separate from pytest warning totals.
`git diff --check` passes. Real HTTP/HTTPS tests prove owned ports close/rebind and
processes exit 0 with application shutdown complete; existing infrastructure coverage
also preserves an unrelated synthetic listener.

## Preservation and baseline reconciliation

The fresh baseline contains **2,761 files**, 56 modified tracked files, 73 grouped
untracked entries and 93 expanded untracked paths; index empty. SHA-256 inventory
excludes Git internals, virtual environments, node_modules, caches, agent configuration
and its own new phase scratch folder. It includes prior retained ignored scratch
evidence. Branch/HEAD are recorded above; no Git mutation is part of this work.

The earlier **2,675 → 2,728 difference is exactly 53 additions and zero removals**:
nine Phase 29.6.2 application/test/documentation files and 44 retained Phase 29.6.2
scratch evidence files. Each phase excluded its own then-current scratch directory;
Phase 29.6.3 included the completed earlier evidence. This is timing of an otherwise
comparable inventory, not data loss, profile migration or count manipulation. Paths
and grouping are retained in the historical baseline-reconciliation summary. No files were deleted
to reconcile counts. The **2,728 → 2,761** increase is another 33 additions: ten
Phase 29.6.3 project files plus 23 retained earlier scratch evidence files, zero removals.

Final preservation checks retain every one of the 2,761 baseline paths. Exactly ten
existing files have intentional scoped changes, and seven project files are added.
All other baseline hashes match, including **558 protected root files** and **80
frontend files**. Models, datasets, student JSON, assessment/prediction histories,
company data, authentication records, environment files, backups and earlier evidence
are untouched. Prior **224,876 historical phase report suffix bytes** remain identical.
Branch/HEAD unchanged; index empty; final 56 modified tracked / 79 grouped untracked /
100 expanded untracked paths. Full path/hash/status evidence is retained in the phase
preservation JSON. The current scratch helpers/results are excluded from this count,
as specified by the baseline method; environments/cache contents are outside hash scope
and were not edited by this phase.

## Remaining gaps and deployment restrictions

Assessment ownership is not implemented: reservation/submission/results/history
remain 503 after session/CSRF. Prediction, readiness, eligibility, skills/performance,
recommendation and history authorization remain blocked for a later phase. No model
or scoring/lifecycle rule changes. No frontend authentication, account-bound retries,
legacy association/transfer/recovery, ownership suspension administration or migration.

Registration remains restricted: real email verification/activation/recovery is absent.
Tests activate only synthetic temporary accounts. The existing frontend mock login and
browser profile IDs confer no permission and are unchanged. Session/network abuse
throttling, upload/CPU/storage quotas, audit events, ACL/backup/retention policy, proxy
trust, browser/tab integration and deployment approval remain incomplete. Creation
retries may duplicate; incomplete records require a separately approved recovery design.
SQLite/JSON concurrency is validated for cooperating processes on one host, not a
distributed deployment. Ten existing model dependency warnings remain documented in
the [setup audit](setup-dependency-audit.md). Do not expose real student data publicly
or describe this phase as completed production security.

Next separately authorized phase: **29.6.5 — Assessment Ownership**. Stop after
Phase 29.6.4; no subsequent phase is implemented here.
