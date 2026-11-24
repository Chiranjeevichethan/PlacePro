# PlacePro development setup (Windows PowerShell)

> Publication refresh (2026-11-24): current capabilities, 50 operations/45 paths,
> required artifacts and verification boundaries are summarized in the
> [reviewed release snapshot](backend/DEPLOYMENT.md#reviewed-release-snapshot-2026-11-24). Earlier dated results remain historical;
> no new application tests, browser acceptance or Linux/Docker success are claimed.

PlacePro runs a FastAPI API and a React/Vite frontend on one development machine.
Profiles and assessments use local JSON; company requirements use SQLite. Placement
and salary inference load the two existing model artifacts. Login uses server-side
cookie sessions; profile confirmation is claim review. This guide is for local development.

Use the complete reviewed release candidate and its pinned dependencies. An
older commit alone does not include the later frontend, security, V1 and container
integration. This guide covers local development; public hosting has separate
configuration and acceptance requirements.

## Prerequisites

| Tool | Validated baseline | Notes |
| --- | --- | --- |
| CPython | **3.14.6, Windows x64** | [.python-version](.python-version); regular CPython, not ARM64/free-threaded. Other versions are not validated against the saved models. |
| Node.js | **24.15.0** | [.node-version](.node-version). Vite supports 20.19+/22.12+; ESLint additionally requires 22.13+ on Node 22. This phase validates only Node 24.15.0. |
| npm | **11.12.1** | Lockfile v3; use npm bundled with this baseline or install the matching npm version in your own environment. |
| PowerShell | **5.1+** | Helpers use Windows PowerShell-compatible syntax. |
| Git | Available on PATH | No Git mutation is required to run the app. |

Install Python from [python.org](https://www.python.org/downloads/windows/) and
Node from [nodejs.org](https://nodejs.org/en/download). No database server, compiler,
OCR engine or additional test runner is required by the documented wheel-based setup.
Run commands from the project root unless stated otherwise; paths may contain spaces
or apostrophes, so use quoted paths and PowerShell's `&` call operator.

```powershell
python.exe --version
node.exe --version
npm.cmd --version
git --version
```

Confirm Python prints 3.14.6 before creating a venv. `py -3.14` is an alternative
if the Windows launcher can find that installation. On the audited machine the
bare Python command selects 3.13 and the launcher reports no installations; the
existing `.venv` explicitly selects 3.14.6. Do not rely on machine PATH ordering.

## Backend installation

For a **new environment** (do not recreate an existing `.venv`):

```powershell
if (Test-Path -LiteralPath .venv) { throw 'Existing .venv: use it or choose a new venv path.' }
python.exe -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
.\.venv\Scripts\Activate.ps1
python.exe -m pip install --only-binary=:all: -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Runtime dependency installation failed.' }
# Development/test tools include all runtime dependencies:
python.exe -m pip install --only-binary=:all: -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw 'Test dependency installation failed.' }
python.exe -m pip check
python.exe -B -W default scripts/check_environment.py --development --models
```

Activation is optional. Every Python command can use
`& .\.venv\Scripts\python.exe ...` explicitly. Use a new path such as
`.venv-placepro-local` if `.venv` belongs to existing work; pass its interpreter
to helpers with `-PythonExecutable`. Do not reinstall packages into another
developer's environment as a repair step. Environments at other paths may need
their own local ignore rule.

[requirements.txt](requirements.txt) pins 32 runtime packages, including active
transitive and Argon2 dependencies. [requirements-dev.txt](requirements-dev.txt) adds eight
test dependencies (40 total), including `httpx2` used by Starlette 1.6 TestClient.
[requirements-analysis.txt](requirements-analysis.txt) is optional legacy plotting
support and is not required by the API/tests. No package was removed from the
existing environment. Experimental boosters remain outside the API install.

These are version snapshots generated from installed distribution metadata and
active dependency markers for the validated platform, not hash-locked wheels or
claims of universal compatibility. See [dependency audit](docs/setup-dependency-audit.md)
for dependency generation, warning triage and fresh-install evidence. Online access to
the matching package releases, or a separately provided trusted wheelhouse, is needed.

Fresh backend installation, imports, original-model inference, startup and the full
536-case backend suite were validated in Phase 29.3.7-R using the unchanged pins and
36 cached PyPI release wheels checked against cached index SHA-256 metadata. Direct
online/empty-cache installation remains unverified because registry sockets are denied.
For an approved local wheelhouse containing every declared compatible wheel:

```powershell
python.exe -m pip install --no-index --find-links 'C:\path\to\approved-wheelhouse' --only-binary=:all: -r requirements-dev.txt
python.exe -m pip check
```

Do not substitute untrusted wheels or copy installed site-packages. See the dated
follow-up in the dependency audit for provenance and validation limits.

Required runtime artifacts are `models/placepro_final_model.pkl`,
`models/placepro_salary_model_v2.pkl`, and
`experimental/v1/placepro_v1_production_fields.pkl`. The production models use
`src/pipeline.py`; V1 uses `experimental/v1/feature_schema.py`. The release verifier
checks all three approved SHA-256 baselines without training or rewriting them.
The CI verifier loads all three and runs read-only inference without creating
profiles or initialising SQLite; the older development preflight checks only
the two production models. It prints dependency warnings; `/health` alone does not test models.
Do not execute root `main.py`, `src/feature_analysis.py` or salary training as setup
checks: they can train or write datasets/model/analysis artifacts. The legacy tuned
model referenced by `src/predictor.py` is absent and is not the production API model.

## Environment configuration

Local server startup needs no OAuth secrets. Student login requires a password
supplied privately through backend provisioning. Never store credentials in
`VITE_` variables: Vite embeds them in browser assets.

| Variable | Consumer | Default / requirement |
| --- | --- | --- |
| `PLACEPRO_PROFILES_DIR` | Backend, read at import | `<repo>/data/profiles`; optional JSON directory override. |
| `PLACEPRO_ASSESSMENTS_DIR` | Backend, read at import | `<repo>/data/assessments`; optional session directory override. |
| `PLACEPRO_COMPANIES_DB` | Backend, read at import | `<repo>/data/companies.db`; optional SQLite file path. First company access creates/seeds **DEMO** data if empty. |
| `PLACEPRO_SALARY_DEFAULT_COLLEGE_TIER` | Backend, read at import | `Tier 2`; optional salary fallback for missing tier. |
| `UVICORN_HOST`, `UVICORN_PORT` | Uvicorn/helper | Helper defaults `127.0.0.1`, `8765`; CLI `--host`/`--port` or helper parameters take precedence. |
| `VITE_API_BASE_URL` | Frontend, build/dev startup | `http://127.0.0.1:8765`; no `/api` suffix or trailing slash. |
| `VITE_DEMO_PROFILE_ID` | Legacy frontend reference | Ignored for authenticated profile access; accounts see only ACTIVE owned profiles. |
| `PLACEPRO_API_URL` | Backend pytest only | Owned isolated loopback HTTP server; direct pytest defaults to 8765. Helper selects a free port if unset. Never a production API. |
| `PLACEPRO_TEST_STORAGE_ROOT`, `PLACEPRO_TEST_RUN_ID` | Test-only ASGI wrapper | Set by the fixture; do not configure these for normal development. |

[.env.example](.env.example) is a backend reference. **Python does not automatically
load `.env`** and no dotenv dependency is added. Set backend variables in the same
PowerShell session before starting the process. Use absolute paths for overrides:

```powershell
# Optional separate development storage; these are not test overrides.
$env:PLACEPRO_PROFILES_DIR = Join-Path $PWD 'scratch\my-development\profiles'
$env:PLACEPRO_ASSESSMENTS_DIR = Join-Path $PWD 'scratch\my-development\assessments'
$env:PLACEPRO_COMPANIES_DB = Join-Path $PWD 'scratch\my-development\companies.db'
```

Vite loads `frontend/.env.local`. Copy its example only if the destination is absent:

```powershell
if (-not (Test-Path -LiteralPath frontend/.env.local)) {
    Copy-Item -LiteralPath frontend/.env.example -Destination frontend/.env.local
}
```

Existing `.env` files are never overwritten by helpers. Shell variables override
Vite file values. Restart Vite after configuration changes and rebuild production
assets after changing build-time values. Backend CORS now uses exact
`PLACEPRO_ALLOWED_ORIGINS` with explicit methods/headers and credentials. Default
production mode requires HTTPS and leaves origins empty, preventing login until
configured. Explicit development mode permits only loopback hosts and clients.
See [session security](docs/session-security.md). Model paths remain code-defined.

## Frontend installation

In a **new frontend directory with no `node_modules`**:

```powershell
Push-Location -LiteralPath frontend
try {
    if (Test-Path -LiteralPath node_modules) { throw 'Existing node_modules: preserve it; validate in a separate source copy.' }
    npm.cmd ci
    if ($LASTEXITCODE -ne 0) { throw 'Frontend installation failed; inspect lockfile/version/network diagnostics.' }
} finally { Pop-Location }
```

Use `frontend/package-lock.json`, not the unrelated empty root lockfile.
`npm ci` uses exact lockfile versions and fails on manifest mismatch. It also
removes an existing `node_modules`, so run it only in a fresh directory during
preservation-sensitive work. No React/Vite/ESLint major upgrade or lock regeneration
was performed. Dev dependencies are needed for Vite, lint and builds; do not install
with `--omit=dev` for this workflow.

## Running PlacePro

Two terminals, from the root:

```powershell
# Terminal 1: preflight + API (Ctrl+C stops the foreground server).
$env:PLACEPRO_SECURITY_MODE = 'development'
$env:PLACEPRO_ALLOWED_ORIGINS = 'http://127.0.0.1:5173'
powershell.exe -NoProfile -File scripts/placepro.ps1 -Command Backend
# Optional: -Reload, -Port 8767, -BindAddress 127.0.0.1, -PythonExecutable <new-venv-python>

# Terminal 2: preflight + Vite (Ctrl+C stops the foreground server).
powershell.exe -NoProfile -File scripts/placepro.ps1 -Command Frontend
# Optional: -Port 5174, -BindAddress 127.0.0.1
```

Open `http://127.0.0.1:5173`; API health is `http://127.0.0.1:8765/health`
and API docs are `/docs` only in explicit loopback development mode. Helpers refuse occupied ports and never stop or attach
to existing servers. Hosts must be numeric IP addresses for the port probe.
Changing backend port requires matching `VITE_API_BASE_URL`; it is not auto-discovered.
Login establishes a real server-side HttpOnly session for either a student
email/password account or Google OAuth 2.0. Both methods use the same account,
profile ownership, predictions, assessments and dashboard; see
[dual authentication](docs/dual-authentication.md).

The local development student account is created only by the backend. For a
new account, use hidden-prompt provisioning in explicit development mode:

```powershell
$env:PLACEPRO_SECURITY_MODE = 'development'
$env:PLACEPRO_ALLOWED_ORIGINS = 'http://127.0.0.1:5173'
$env:PLACEPRO_DEV_STUDENT_EMAIL = 'student@placepro.com'
& .\.venv\Scripts\python.exe scripts/seed_dev_student.py --password
```

Sign in with `student@placepro.com` and the password you entered. Use `--email`
when `PLACEPRO_DEV_STUDENT_EMAIL` is unset to choose a different local email.
Existing accounts retain their existing
password, status and hash; rerunning the seed script does not reset credentials.
Startup provisioning remains available when the development email and password
are supplied privately through the backend environment.

Development provisioning is refused outside development mode. Passwords are
stored as Argon2id hashes and are not logged; the frontend displays setup
instructions without embedding or copying a password. Registration and password
recovery still await an approved email workflow.

Google sign-in is enabled only when `GOOGLE_CLIENT_ID` and
`GOOGLE_CLIENT_SECRET` are configured; otherwise the button reports that this
server has no Google configuration. See
[dual authentication](docs/dual-authentication.md) for the exact redirect URI
and Google Cloud Console steps.

Equivalent direct commands:

```powershell
& .\.venv\Scripts\python.exe -B -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8765
# In frontend/:
npm.cmd run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

A fresh checkout contains no student profiles/sessions. Profile creation/read/edit
now require a real session and authoritative ownership. Bound assessments and
owned prediction/history/analytics are enabled. Existing-profile resume review
and selective updates use the owned revision-bound preview/profile flow. The two
standalone resume-processing routes remain blocked. The frontend restores sessions, sends CSRF and selects owned
profiles. Stateless placement/salary forms retain their contracts; the dashboard
has a separate Save profile prediction action for owned history. Do not fabricate
demo student records or assume a historical seed script exists. Companies remain
the existing labelled DEMO seed; fresh company reads can create the local database.

## Tests and builds

```powershell
powershell.exe -NoProfile -File scripts/placepro.ps1 -Command Check
powershell.exe -NoProfile -File scripts/placepro.ps1 -Command TestBackend
powershell.exe -NoProfile -File scripts/placepro.ps1 -Command TestFrontend
$env:NODE_ENV = 'production'
$env:VITE_API_BASE_URL = 'https://api.example.test' # build-only verification origin
powershell.exe -NoProfile -File scripts/placepro.ps1 -Command ValidateFrontend
git diff --check
```

Helpers return nonzero on failure and install nothing. `ValidateFrontend` runs
Node tests, lint and a production build in a **new** `scratch/frontend-build-<id>`
directory; it retains all earlier builds. The backend suite selects temporary stores
before collection, rebinds per test, and owns its separate HTTP child. Project
profiles/sessions/company DB are never writable test fixtures. Logs and temporary
artifacts are retained. Do not supply `--basetemp` pointing to an existing directory;
pytest can erase it. Setup tests use the project's retained isolation fixture.

Direct backend commands (no development server is required):

```powershell
$env:PLACEPRO_API_URL = 'http://127.0.0.1:8766' # choose a free port
& .\.venv\Scripts\python.exe -B -m pytest backend/tests/ -q -p no:cacheprovider
& .\.venv\Scripts\python.exe -B -m pytest backend/tests/test_setup.py -q -p no:cacheprovider
# Services only: add -m "not live_http"; live cases only: add -m live_http
```

Direct frontend commands, from `frontend/`:

```powershell
npm.cmd run test
npm.cmd run lint
$placeproBuild = Join-Path $PWD ('..\scratch\frontend-build-' + [guid]::NewGuid().ToString('N'))
$env:NODE_ENV = 'production'
$env:VITE_API_BASE_URL = 'https://api.example.test' # build-only example; use the reviewed real API for deployment
npm.cmd run build -- --outDir $placeproBuild
```

Node tests use the native runner and in-memory fixtures. Browser regressions are separate scripts in `frontend/browser-tests/` and
require externally supplied browser tooling. They are not part of `npm test`
and do not establish current browser acceptance.

## Troubleshooting

| Problem | Action |
| --- | --- |
| Python version/architecture mismatch | Check the selected executable with `--version`; use CPython 3.14.6 x64 and an explicit venv path. Never recreate an existing venv. |
| Missing/wrong Python packages | Run the preflight and `python -m pip check`; install the manifests in a new environment. Use `python -m pip`, not a potentially foreign `pip` executable. |
| Pip reports no matching distribution / socket error 10013 | Inspect network/index availability and Python wheel compatibility. Direct registry sockets are blocked here; fresh installation passed from a verified local wheel cache. Online empty-cache installation remains unverified. Do not drop pins or disable TLS to bypass it. |
| Node/npm mismatch | Use baseline versions. `npm.cmd` avoids execution-policy problems with `npm.ps1`. Older Node may fail ESLint/Vite before application code runs. |
| npm manifest/lockfile mismatch | Use the frontend manifest and its lock from the same reviewed snapshot. Do not delete the lock or run `npm install` to silently regenerate it. |
| Port already in use | Select another port and update the frontend API URL as needed. Do not terminate an unrelated process. |
| Frontend cannot reach API | Confirm backend is running, check `/health`, base URL/port and browser network errors; restart Vite after environment changes. |
| Environment value ignored | Backend reads shell variables at import and has no dotenv loader. Vite reads files in `frontend/` and embeds `VITE_` values at build time. |
| Missing model artifact | Restore the trusted project artifact through the owner. Do not train or resave a model as a setup repair. |
| Profile 404 on a fresh environment | Create/review/confirm a resume explicitly. Local profiles are ignored and not distributed with source. |
| PowerShell blocks Activate.ps1/helper | Use the venv `.exe` and `npm.cmd` directly. If local policy permits, a **process-only** `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned` can allow scripts; do not change machine policy. |
| Test port/storage failure | Use a free loopback `PLACEPRO_API_URL`; inspect the retained HTTP log. Never target real API/storage. Avoid pytest's shared `tmp_path` directory if its ACL is inaccessible; the project isolation fixture creates fresh retained paths. |
| Model-load joblib/NumPy warnings | Read [warning triage](docs/setup-dependency-audit.md). They remain visible; current model loads/inference pass. Do not upgrade ML dependencies blindly. |

See [the reviewed release snapshot](backend/DEPLOYMENT.md#reviewed-release-snapshot-2026-11-24) for current evidence and limitations, and
[backend test guidance](backend/tests/README.md) / [frontend test guidance](frontend/tests/README.md)
for test boundaries. Phase 29.3.7 adds development setup only; it does not migrate
student records, retrain models or establish production deployment readiness.

## Account foundation — Phase 29.6.2

The runtime manifest now includes four tested Argon2 dependency pins (32 runtime,
40 with test tools). Existing environments were preserved; install current manifests
in a new virtual environment, or use the retained validated environment described in
[the account foundation guide](docs/account-authentication-foundation.md).

Phase 29.6.2 originally staged registration/login. Phase 29.6.3 now implements real
opaque sessions, login CSRF, secure cookies, restoration, renewal and durable logout.
Registration remains **503** pending approved email verification. There is no security
disable flag or temporary token. Account services use a
separate lazy `PLACEPRO_AUTH_DB` (default `data/auth/accounts.sqlite3`); importing or
starting this app does not create it. Tests always override that path with temporary
storage. Do not modify an existing .env or point account storage at companies.db.

Registration creates only pending/unverified accounts. Email delivery and activation
remain unavailable; Phase 29.6.7 implements real frontend login and session restoration.
Phase 29.6.4 adds persistent authoritative
profile associations, server-generated IDs and fail-closed creation. Owners can create,
read, edit and confirm profiles, and list only their ACTIVE profile references.
Foreign, missing and legacy-unowned targets receive the same 404. Reviewed revisions
and CSRF remain required for edits. Existing profiles are not claimed or migrated.
Phase 29.6.5 enables owned assessment start, retrieval, submission and assessment-only
history. Both lifecycle GETs require CSRF and Origin because they can recover or expire
records. New sessions carry server-controlled account/profile bindings; legacy records
remain inaccessible and unchanged. Secured expired assessment GET returns 410.
Phase 29.6.6 now enables authenticated stateless placement/salary forms and eight
owned prediction/history/readiness/eligibility/recommendation/skills/performance
operations, preserving existing calculators and response contracts. New stored
prediction history is account/profile-bound; legacy records remain inaccessible.
Two standalone resume-processing operations remain 503 after authentication/CSRF;
anonymous private requests remain 401. Profile responses omit assessment evidence
and prediction history, preserving both in storage. Assessment-only history is available
through its secured endpoint; owned skills/performance are also available.
See [prediction ownership](docs/prediction-ownership.md) for its historical phase matrix; use the release snapshot for the current
50-operation/45-path inventory, approved stateless policy and latest validation; [assessment ownership](docs/assessment-ownership.md) for the assessment
matrix and validation, [profile ownership](docs/profile-ownership.md) for
creation failure/retry limitations, and [session security](docs/session-security.md)
for exact environment/cookie policy and remaining release gaps.

## Isolated synthetic demonstration — Phase 30

With the already installed frontend dependencies and validated Python environment,
run from an interactive terminal:

```powershell
.\.venv\Scripts\python.exe -B scripts/demo.py
```

Choose a password at the masked prompts. The launcher prints the local browser URL,
three synthetic student login addresses and a synthetic DOCX resume path. Each run
uses a new temporary database/profile/assessment store and an owned loopback Vite
development server with isolated cache/logs;
existing student records are never loaded or claimed. Login, CSRF and ownership
remain enforced. Ctrl+C stops only the owned servers and retains all demo records.
Ports default to 5173/8765 and must be free; optional `--frontend-port` and
`--api-port` select other loopback ports.

Follow the [demo walkthrough](docs/phase-30-demo-workflow.md). The dashboard now
offers profile completion guidance, placement probability and a qualified salary
preview; model explanations distinguish estimates from measured outcomes. Self-service
activation/recovery remain unavailable; optional Google OAuth requires reviewed
configuration and provider acceptance. Owned resume review/update is implemented;
standalone resume analysis remains blocked. See
[Phase 30 validation](docs/phase-30-validation.md) for exact results and the blocked
new browser/visual checks; this is a local demonstration, not public deployment approval.
