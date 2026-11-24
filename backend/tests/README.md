# Backend tests

> Publication refresh (2026-11-24): current capabilities, 50 operations/45 paths,
> required artifacts and verification boundaries are summarized in the
> [reviewed release snapshot](../DEPLOYMENT.md#reviewed-release-snapshot-2026-11-24). Earlier dated results remain historical;
> no new application tests, browser acceptance or Linux/Docker success are claimed.

Install the pinned [runtime/test dependencies](../../requirements-dev.txt) with
CPython 3.14.6 Windows x64. The [root Windows guide](../../README.md) covers fresh
venvs, startup, configuration and the retained joblib/NumPy warning analysis.
`scripts/placepro.ps1 -Command TestBackend` preflights packages and selects a free
loopback port when `PLACEPRO_API_URL` is unset; it returns a nonzero exit on failure.

Run from the repository root with the project's Python environment. Pytest binds temporary
profile, assessment and company stores before collection and creates fresh stores for every
test. Existing `PLACEPRO_PROFILES_DIR`, `PLACEPRO_ASSESSMENTS_DIR` and `PLACEPRO_COMPANIES_DB`
values are overridden inside the test process, then restored when pytest finishes.

```powershell
# Service and in-process API tests; no live server starts.
.\.venv\Scripts\python.exe -B -m pytest backend/tests/ -q -p no:cacheprovider -m "not live_http"

# Live HTTP tests only; pytest starts and stops its own isolated server.
.\.venv\Scripts\python.exe -B -m pytest backend/tests/ -q -p no:cacheprovider -m live_http

# Full suite, including live HTTP.
.\.venv\Scripts\python.exe -B -m pytest backend/tests/ -q -p no:cacheprovider
```

All live HTTP cases carry the `live_http` marker, including production-mode
HTTP/HTTPS security and the isolated Vite demo harness. The shared default domain test URL is
`http://127.0.0.1:8765`, matching the documented development startup:

```powershell
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8765
```

Use a free port for tests. An existing development server on that port causes fixture setup
to fail; it is never reused or stopped. Choose a different test address when needed:

```powershell
$env:PLACEPRO_API_URL = "http://127.0.0.1:8766"
.\.venv\Scripts\python.exe -B -m pytest backend/tests/ -q -p no:cacheprovider -m live_http
```

`PLACEPRO_API_URL` must be a loopback HTTP URL with an explicit port and no API path,
credentials, query or fragment. Pytest launches `backend.tests.http_server:app` in a separate
Uvicorn process with fresh storage paths. A test-only response header verifies that the health
response belongs to this process before tests send requests. This wrapper forwards the
unchanged business contracts through an explicitly isolated domain harness and adds
no test-only JSON fields. Connection failures, unexpected HTTP errors and startup
failures fail the run.

Temporary storage directories and server logs are retained, and their paths are printed in the
test summary. No cleanup of existing project data, backups or temporary files is performed.
PDF/DOCX fixtures are generated in memory; normal resume processing uses its own temporary upload
directory. Default tests read model artifacts and the aggregate-only
`fixtures/salary_training_summary.json`; no training CSV is required. Its dataset,
served-model and training-script SHA-256 provenance was recorded from the original
data, independently of service constants. A model hash mismatch fails the tests.
The two population/holdout checks remain in the separately invoked
[offline-data suite](../offline_tests/README.md); they read approved data without
training or changing it. Aggregate assertions do not remeasure holdout quality.

The existing resume, readiness, performance, prediction and company-store script entry points
delegate to pytest, so they use the same assertion and isolation rules. The aggregate
`test_service_suite` cases are retained alongside individual cases for compatibility; pytest's
case counts include those aggregate runners, not a count of unique assertions. Returned test
values are treated as errors by `pytest.ini`.

Assessment lifecycle coverage is in `test_assessment_lifecycle.py` and the existing
`test_assessment_retry.py`. Run the new file with the same isolated server configuration:

```powershell
$env:PLACEPRO_API_URL = "http://127.0.0.1:8766"
.\.venv\Scripts\python.exe -B -m pytest backend/tests/test_assessment_lifecycle.py -q -p no:cacheprovider
```

An active assessment reserves one of three completion slots per profile/skill. Session attempt
numbers increase at start; expired reservations release quota while their records and ordinals
remain, so later numbers can have gaps. Invalid answers leave the same session retryable.
Both passing and failing scored completions count toward the three-completion limit and start
the 24-hour cooldown. Outstanding submissions also recheck cooldown and completed quota.

The server stores `created_at` and `expires_at` with one minute per selected question. Submission
at or after expiry returns 410, preserves `EXPIRED`, and records no score/evidence. Session GET,
history, start and submission lazily refresh expiry. Legacy sessions derive deadlines from original
creation; unusable session timing expires closed. Existing malformed evidence timestamps retain
their earlier defensive treatment. Public responses never include answer keys or explanations.

Accepted submissions persist `SUBMITTING` with answers/report/server timestamp, then append
evidence by session ID and mark `COMPLETED`. An interrupted write can be recovered without
scoring again; a repeated completed submission returns 409. An identical retry while a durable
submission still needs recovery returns the original result. Recovery can finish after the deadline
because it finalizes answers already accepted before expiry.

Per-profile reentrant thread locks and OS file locks cover the entire update, including profile
edit, verification and prediction-history writers. Lock files and test-worker artifacts are retained.
Concurrency tests synchronize 12 in-process HTTP requests and four independent Python processes
sharing temporary JSON stores; another marked case exercises concurrent requests over the owned
live HTTP server. Seeded RNG injection is service-only; HTTP clients cannot supply selection seeds.

These locks require cooperating processes on one host using the same storage paths. JSON scanning
is linear and the session/profile pair is not a single atomic database transaction. Failure-injection
tests cover recovery at both projection writes; power-loss, multiple-host/network-filesystem and
POSIX locking behavior are not validated here. One local SQLite transaction owning authoritative
assessment sessions/evidence is the next step for stronger single-host crash guarantees or scale;
multiple hosts need a suitable database service. Frontend server-deadline/Retake
integration and browser results were subsequently validated in Phases 29.3.3–29.3.6;
those historical results and their limits are summarized in the dated phase documents.
Current release verification and commands are linked above.

`test_setup.py` checks environment failures, pinned dependency closure, manifest/lock
agreement, model loading without storage writes and PowerShell occupied-port/error
behavior. It uses the retained `isolated_storage` fixture, not pytest's shared
`tmp_path` cleanup. Never point `--basetemp` at an existing directory.

Phase 29.6.3 separates business and external security coverage. `domain_app.py` refuses
missing/project/non-isolated storage; old business API tests retain their assertions
without a production bypass. The normal `backend.app.main` always enforces the gate;
deferred student requests remain blocked until their ownership phase. CORS tests exercise that app.
`test_sessions.py` covers storage/lifecycle; `test_session_security.py` exercises the
actual secured ASGI app, synthetic credentials, cookies, CSRF and every private route.
`test_session_http.py` launches the default-production app on owned ephemeral ports,
checks real HTTP/HTTPS and graceful shutdown. TLS discovers trusted OpenSSL on PATH,
or uses an explicit `PLACEPRO_TEST_OPENSSL` executable. On Windows it also checks
Git under `ProgramFiles`. It generates isolated temporary certificates,
and validates their trust without disabling TLS verification. A missing executable is
an explicit failed prerequisite, not hidden skipped TLS coverage. Production import,
startup, shutdown and student-data preservation are checked separately from domain
success. No frontend or browser authentication coverage is claimed in this phase.

Phase 29.6.4 adds `test_ownership_store.py` and `test_profile_ownership.py`. They use
the normal secured production-mode app, real synthetic credentials/cookies/CSRF and
temporary ownership/profile stores. They cover publication failures, legacy/cross-account
404 isolation, server IDs, revisions, database constraints/rollback and concurrency.
In that phase sixteen student operations remained deferred. Phase 29.6.5 now excludes
the four secured assessment operations from the deferred selection, retaining denial
coverage for all twelve remaining operations even with an owned profile.
`test_session_security.py` retains anonymous and CSRF checks across
the complete 31-operation inventory. Live HTTPS additionally
creates/reads/lists an owned profile and denies owned readiness. Original business
assertions stay in the isolated domain harness; no production bypass is introduced.
See [profile ownership](../../docs/profile-ownership.md) for exact results and limits.

Phase 29.6.5 adds `test_assessment_ownership.py`, using the actual production-mode app,
synthetic sessions/accounts and isolated profile/assessment/authentication stores.
It verifies ownership before lifecycle effects, cross-account and legacy denial,
storage failures, account invalidation, quotas, concurrency, deadlines and owner-only
durable evidence recovery. Existing lifecycle/retry assertions stay in the guarded
domain harness. Live production HTTPS also starts/reads/submits an owned assessment
and reads its bound history. No production bypass or frontend edit is added.
See [assessment ownership](../../docs/assessment-ownership.md) for exact results,
the expired GET contract distinction and all deferred restrictions.

Phase 29.6.6 adds `test_prediction_ownership.py`, exercising all ten newly enabled
operations on the normal secured app. It covers unchanged real stateless calculators,
ACTIVE ownership before private lookup/inference/replay, bound history/evidence,
concurrency, stale revisions, failed/lost-response retries and non-disclosing errors.
Only the two standalone resume routes remain in the deferred parametrizations; the
ten enabled paths retain inventory auth/CSRF checks and gain owner/foreign success/
denial tests. Real HTTPS additionally exercises both forms, owned prediction/replay,
readiness and mixed performance. Original domain assertions are unchanged.
See [prediction ownership](../../docs/prediction-ownership.md) for the current matrix,
exact counts and the approved stateless policy. Frontend integration is the next phase.
# Phase32 owned resume update coverage

The production-mode test suite now includes test_resume_profile_update.py.
Run with the existing interpreter: python -m pytest backend/tests/test_resume_profile_update.py -q.
The shared conftest creates temporary stores before imports/fixtures; no historical
profiles, databases or histories are reset. TestClient uses the secured production
ASGI application, not the legacy domain harness. PDF/DOCX preview checks ownership
before multipart parsing and rechecks session/revision after extraction; explicit
confirmation/retry tests preserve existing histories and refresh source revisions.
At the historical Phase32 checkpoint, the inventory increased to 32 operations/31 paths and six
profile operations; the current inventory is 50 operations/45 paths; existing anonymous/CSRF/default-private regressions include
the new route. Parameter IDs for large byte fixtures stay short on Windows.
See [feature documentation](../../docs/resume-upload-workflow.md) for exact evidence.

Phase32 manual-rehearsal corrections add test_resume_extraction_mapping.py. Its
known fictional sample covers PDF/DOCX/canonical mapping, fresh generator content
and metadata, project descriptions, internship versus experience, dates, ordered
DOCX tables, repeated sections, skill aliases, no fabricated records, owned preview,
explicit corrected confirmation and stale/cross-account denial. Run it with
python -m pytest backend/tests/test_resume_extraction_mapping.py -q using the
existing isolated fixtures. test_resume_integrity.py additionally checks that a
later skill section is retained without leaking project content. Frontend source
separation and complete record display are tested in resumeExtractionMapping.test.js.
Manual Chrome acceptance is still pending; automated tests do not prove rendering.


## Resume fixture publication provenance

`fixtures/resume_integrity_fictional.txt` was newly authored on 2026-11-25 solely
for public regression testing. It uses a non-person identity, reserved
`example.test` contact/credential domains, invented organizations and newly written
education, project, internship and contribution text. Its own header declares
fictional authorship; it is not based on the unverified local resume.

The exact project/activity labels, public certification title/issuer and expected
graduation/certification years are parser assertion tokens retained from the tests.
They do not attest to real qualifications, employment or participation. Both
`test_resume_integrity.py` and `test_integration.py` now read the fictional file;
their assertions remain unchanged.

Release inclusion replaces `fixtures/resume_integrity.txt` with
`fixtures/resume_integrity_fictional.txt`: the proposed release again has 331
paths, with the original unverified file excluded. The original remains local,
untouched and untracked. Its provenance is still unconfirmed and no public test
requires it; its SHA-256 remains
`9fe1ed1c83ff9ed657b8ba62505deaf8ea46c6de27c10017c284b370d9d2bbd9`.
