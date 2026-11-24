# Persistent Linux container deployment

This prepares the existing FastAPI backend for one Linux AMD64 container with
one Uvicorn worker and a persistent local volume. The frontend is a separate
Vercel project. No application security, API contracts, models, datasets or
existing databases are changed by this configuration. No deployment or database
migration is performed by adding these files.

## Reviewed release snapshot (2026-11-24)

This section describes the reviewed 331-file release candidate. Earlier dated
phase documents preserve their original historical test results and design
decisions; their older inventories and unavailable-feature descriptions are not
the current implementation. No new application test run, deployment or account
provisioning is performed by this documentation update.

The production application mounts **50 method/path operations across 45 distinct
paths**, excluding development documentation routes. Its security inventory has
38 private operations, three public reads, three authentication entry operations,
four session operations and two Google OAuth operations. The private inventory
includes 10 profile/resume-builder, four assessment, 11 analytics (including V1)
and 11 goal/notification operations, plus two deferred standalone resume routes.
Ownership, CSRF and revision checks remain required wherever the existing policy
requires them. See [the inventory/security regression](tests/test_session_security.py)
and [the application entrypoint](app/main.py).

Current implemented features include password login, session restoration/logout,
optional configured Google OAuth, owned profile/resume review and updates, resume
field selection and Select All, profile editing, goals/milestones, notifications,
resume-builder persistence/PDF export, production placement and salary inference,
and separate Experimental V1 inference. Client navigation uses the existing URL
mapping and History API; it does not require React Router. Public registration
and password recovery remain disabled pending approved email verification.
Google provider/hosting acceptance, manual browser acceptance and public account
onboarding still need their separately reviewed configuration and verification.

The three required unchanged runtime artifacts are:

| Artifact | SHA-256 baseline |
| --- | --- |
| `models/placepro_final_model.pkl` | `bbf1dc03808499bb9f97124b4dab7e00c1a645a9073edae3bc8d5c5fd1bc9de8` |
| `models/placepro_salary_model_v2.pkl` | `cd652f0056324984db56f2347aee46c1528adbea6bc86dbe62e764715e1b9958` |
| `experimental/v1/placepro_v1_production_fields.pkl` | `49468b8800cdd5bb1d38ed0a7ef52fdabe6ccfa6e21fb18be0310ef9f114448a` |

Production preprocessing still requires `src/pipeline.py`; V1 requires
`experimental/v1/feature_schema.py`. V1 validates the 16 production-form inputs
but infers only from 11 semantically supported synthetic features. DSA, ML
knowledge, system design, open-source contributions and extracurricular counts
are validated but excluded from V1 inference. Its target is `placement_status`;
salary is never a placement-classifier feature or label. Synthetic results are
not validated real-world placement probabilities.

Previously recorded Windows verification, reviewed for this release, reports
**1,362 default backend tests**, **462 frontend tests**, **two explicitly invoked
offline analyses**, passing lint/build and all three inference checks. The backend
total includes 10 live HTTP tests, including two production HTTP/HTTPS cases;
do not add overlapping counts. The obsolete-artifact dependency, CSV-dependent
runtime salary tests, two stale inventory assertions, OpenSSL discovery and local
Vite demo harness were corrected in the approved test/supporting-tool cleanup.
The runtime salary suite uses [aggregate-only provenance](tests/fixtures/salary_training_summary.json);
the [offline suite](offline_tests/README.md) requires separately supplied approved
data and is not run by default CI. These are recorded Windows results, not fresh
tests in this documentation change or real-world ML evaluation.

The [Linux workflow](../.github/workflows/release-linux.yml) defines three independent
Ubuntu 24.04 jobs for backend tests, the production Docker image and frontend
tests/lint/build. [Its verifier](../scripts/ci/verify_release.py) enforces Python
3.14.6, Node 24.15.0, npm 11.12.1, pinned dependencies, trusted model hashes and
real inference. **Clean Linux installation, Docker execution and current browser
acceptance remain unverified until their checks actually pass.** The workflow
does not deploy, publish or upload models, test data or private logs.

From the repository root, use the existing pinned environment for these public
verification commands. They are instructions, not claims of a new run:

```sh
python -B scripts/ci/verify_release.py --source
python -B -m pytest backend/tests/ -q -p no:cacheprovider
npm --prefix frontend test
npm --prefix frontend run lint
```

For a production frontend build, set `NODE_ENV=production` and
`VITE_API_BASE_URL` to the reviewed non-loopback HTTPS API origin before running
`npm --prefix frontend run build`. A reserved `https://api.example.test` origin
can be used for build-only verification; it does not represent a running API.
The existing production guard rejects missing, HTTP and loopback API settings.

The 331-file release inclusion plan now includes the newly authored
`backend/tests/fixtures/resume_integrity_fictional.txt` and excludes the original
`backend/tests/fixtures/resume_integrity.txt`. The original is preserved locally
and remains untracked; its provenance is still unconfirmed. Public parser and
integration regressions use only the explicitly fictional replacement, with their
assertions unchanged. See [the fixture provenance and release-plan note](tests/README.md#resume-fixture-publication-provenance).

### Current operation inventory

This is the method/path inventory read from the production application during
the documentation check; no endpoint requests or persistence operations were run.

| Method | Path |
| --- | --- |
| DELETE | `/api/profile/{profile_id}/goals/{goal_id}` |
| DELETE | `/api/profile/{profile_id}/goals/{goal_id}/milestones/{milestone_id}` |
| GET | `/api/account/profiles` |
| GET | `/api/assessment/{assessment_id}` |
| GET | `/api/auth/csrf` |
| GET | `/api/auth/google/callback` |
| GET | `/api/auth/google/start` |
| GET | `/api/auth/login-challenge` |
| GET | `/api/auth/session` |
| GET | `/api/companies` |
| GET | `/api/companies/{company_id}` |
| GET | `/api/profile/{profile_id}` |
| GET | `/api/profile/{profile_id}/assessments` |
| GET | `/api/profile/{profile_id}/eligibility` |
| GET | `/api/profile/{profile_id}/eligibility/{company_id}` |
| GET | `/api/profile/{profile_id}/goals` |
| GET | `/api/profile/{profile_id}/notifications` |
| GET | `/api/profile/{profile_id}/notifications/unread-count` |
| GET | `/api/profile/{profile_id}/performance` |
| GET | `/api/profile/{profile_id}/placement-summary` |
| GET | `/api/profile/{profile_id}/readiness` |
| GET | `/api/profile/{profile_id}/recommendations` |
| GET | `/api/profile/{profile_id}/resume-builder` |
| GET | `/api/profile/{profile_id}/skills` |
| GET | `/health` |
| POST | `/api/assessment/start` |
| POST | `/api/assessment/{assessment_id}/submit` |
| POST | `/api/auth/login` |
| POST | `/api/auth/logout` |
| POST | `/api/auth/register` |
| POST | `/api/auth/session/renew` |
| POST | `/api/experimental/v1/predict` |
| POST | `/api/predict` |
| POST | `/api/profile/from-resume` |
| POST | `/api/profile/verify` |
| POST | `/api/profile/{profile_id}/goals` |
| POST | `/api/profile/{profile_id}/goals/{goal_id}/milestones` |
| POST | `/api/profile/{profile_id}/notifications/read-all` |
| POST | `/api/profile/{profile_id}/predict` |
| POST | `/api/profile/{profile_id}/resume-builder/export.pdf` |
| POST | `/api/profile/{profile_id}/resume-builder/import` |
| POST | `/api/profile/{profile_id}/resume-preview` |
| POST | `/api/resume/analyze` |
| POST | `/api/resume/upload` |
| POST | `/api/salary-predict` |
| PUT | `/api/profile/{profile_id}` |
| PUT | `/api/profile/{profile_id}/goals/{goal_id}` |
| PUT | `/api/profile/{profile_id}/goals/{goal_id}/milestones/{milestone_id}` |
| PUT | `/api/profile/{profile_id}/notifications/{notification_id}` |
| PUT | `/api/profile/{profile_id}/resume-builder` |

## Hosting settings

| Setting | Required configuration |
| --- | --- |
| Build context | Repository root, not `backend/` |
| Dockerfile | Root `Dockerfile` |
| Architecture | Linux AMD64, CPython 3.14.6, Debian Bookworm/glibc |
| Startup | Image default: `python -B -m backend.container_start`, working directory `/app` |
| Internal HTTP port | `PORT` supplied by the host, or `8000` |
| Instances / workers | Exactly one instance and one worker; disable autoscaling and overlapping rolling deployments |
| Persistent disk mount | `/var/lib/placepro`, writable by UID/GID `10001:10001` |
| Temporary filesystem | Writable `/tmp` for bounded multipart spooling; it need not persist |
| Health check | HTTP `GET /health` on the internal port |
| Public ingress | HTTPS only, through the host's trusted reverse proxy; restrict allowed Host values there |
| Starting resources | 1 CPU, 1 GiB RAM and a 1 GiB persistent disk for a small demonstration; measure actual use and grow as needed |

`/health` is static liveness. It does not test model inference or database/disk
readiness. Do not use it as proof that login or persistence works.

The image uses a non-root user and copies only backend runtime code, the
production pipeline source, V1 schema, pinned runtime requirements and three
trusted artifacts. It does not copy frontend files, training code/data, local
databases, student records, env files, credentials, tests or backup code.
Do not add `COPY . .`, credential build arguments or startup account seeding.
Runtime-only development provisioning code remains importable because the
application imports it, but production startup rejects development credential
variables and never invokes provisioning.

## Environment

Set these through the host's runtime environment, not image build arguments.
The application reads `os.environ`; it does not automatically load `.env`.

| Variable | Configuration |
| --- | --- |
| `PLACEPRO_SECURITY_MODE` | `production` (image default; launcher refuses development) |
| `PLACEPRO_ALLOWED_ORIGINS` | Exact, comma-separated HTTPS frontend origins, with no paths or trailing slash; required |
| `FORWARDED_ALLOW_IPS` | Host-documented trusted ingress proxy IPs/CIDRs; required; no `*` or all-address CIDRs |
| `PORT` | Host's internal port; defaults to `8000` |
| `PLACEPRO_SESSION_IDLE_SECONDS` | Optional; default `1800` |
| `PLACEPRO_SESSION_ABSOLUTE_SECONDS` | Optional; default `43200`; existing lifetime validation applies |
| `GOOGLE_CLIENT_ID` | Optional Google configuration; required together with the other Google settings when enabling OAuth |
| `GOOGLE_CLIENT_SECRET` | Optional runtime secret, never a `VITE_*` value or build argument |
| `GOOGLE_REDIRECT_URI` | Exact public HTTPS callback URL ending `/api/auth/google/callback`; see callback limitation below |
| `PLACEPRO_APP_URL` | Exact frontend origin already listed in `PLACEPRO_ALLOWED_ORIGINS`; required for enabled OAuth |

Keep `PLACEPRO_DEV_STUDENT_EMAIL`, `PLACEPRO_DEV_STUDENT_PASSWORD` and test-only
variables absent. Do not set `WEB_CONCURRENCY` to scale this backend; the launcher
explicitly starts one worker. Preserve the existing salary-tier default by
leaving `PLACEPRO_SALARY_DEFAULT_COLLEGE_TIER` unset.

The image already supplies the six storage settings below. Keep these defaults
unless an individually reviewed path change keeps every store on persistent
storage. Empty or missing overrides can make existing code fall back to `/app/data`.

## Persistent storage

| Variable | Container path | Contents |
| --- | --- | --- |
| `PLACEPRO_AUTH_DB` | `/var/lib/placepro/auth/accounts.sqlite3` | Accounts, sessions, login challenges, OAuth identities/states, ownership and retry records |
| `PLACEPRO_COMPANIES_DB` | `/var/lib/placepro/companies.db` | Company requirements and provenance; empty DB seeds existing DEMO companies on first access |
| `PLACEPRO_GOALS_DB` | `/var/lib/placepro/goals/goals.sqlite3` | Goals, milestones and notifications |
| `PLACEPRO_RESUME_BUILDER_DB` | `/var/lib/placepro/resume_builder/resume_builder.sqlite3` | Saved resume documents and revisions |
| `PLACEPRO_PROFILES_DIR` | `/var/lib/placepro/profiles` | Canonical profile JSON and retained `.locks` files |
| `PLACEPRO_ASSESSMENTS_DIR` | `/var/lib/placepro/assessments` | Assessment JSON and retained `.locks` files |

Mount the entire directory, not individual SQLite files: SQLite journal files,
atomic JSON replacement files and locks must share the same persistent local
filesystem. Use a disk with reliable SQLite locking, POSIX `flock` and atomic
rename. Do not use object storage or an unverified NFS/SMB mount for these stores.
The OS/thread locks and SQLite transactions support this conservative single
instance arrangement; they do not establish safe multi-instance deployment.

The host must prepare ownership before starting the non-root container; mounting
a root-owned disk can hide the image directory's permissions. Restrict volume
access to the application/operator. Do not run the service as root to solve
permission errors. An unmounted image directory is ephemeral, so verify the
actual mount and a stop/restart persistence check before accepting user data.

Stores initialise schemas lazily on first use. Construction and the image build
do not create application databases. A fresh volume has no student accounts or
profiles. Existing local data is not imported automatically. Any later migration
must preserve the auth/ownership database and matching profiles together and
must be a separately authorised operation. Back up the whole volume during a
maintenance stop for consistency across SQLite and JSON stores; retain locks
and test restore procedures before relying on backups.

Resume uploads are bounded to 5 MiB PDF/DOCX, extracted in memory, and not saved
as original files. Multipart parsing can spool to temporary disk. DOCX expansion
is limited to 25 MiB and 1,000 members; PDF extraction allows up to 50 pages and
200,000 extracted characters. Set ingress body limits to allow a 5 MiB file plus
multipart overhead (for example, 6 MiB). Saved resume documents are limited to
1 MiB. PDF generation is synchronous, uses built-in PDF fonts, and returns bytes
from the saved resume; no LibreOffice, browser, system font installation, PDF
binary or persistent PDF directory is required. No external queue or scheduled
worker is needed for current functionality; larger traffic needs separate review.

## Model/runtime verification

The image includes exactly these unchanged artifacts:

| Artifact | Bytes |
| --- | ---: |
| `models/placepro_final_model.pkl` | 7,478 |
| `models/placepro_salary_model_v2.pkl` | 4,300 |
| `experimental/v1/placepro_v1_production_fields.pkl` | 4,081 |

Their preprocessing is embedded in scikit-learn pipelines. Production unpickling
also requires unchanged `src/pipeline.py`. No additional scaler/encoder artifact,
XGBoost, TensorFlow or training dataset is needed. Total model bytes are 15,859;
Python, native wheels and the base image dominate image size.

Preparation checks resolved and downloaded all 32 pinned Linux AMD64 wheels
into temporary storage without installing them. The pinned official Python
image manifest includes Linux AMD64. A temporary copy of the 83 runtime files
passed application imports and production placement/salary/V1 inference in
the existing Windows environment without creating databases. These checks do
not substitute for a Linux container build/run: Docker and WSL were unavailable
in the preparation environment.

Keep the existing pinned `requirements.txt`. NumPy, SciPy, scikit-learn,
pydantic-core, lxml, CFFI and Argon2 have native components; the build installs
binary wheels only and supplies `libgomp1` and CA certificates. It fails rather
than silently compiling or changing package versions. Linux AMD64 wheel
resolution is separate from actual container execution. The build imports the
real app and loads all three artifacts without training or touching databases.
It cannot prove numerical parity by loading alone: require Linux inference
smokes for production placement, salary and V1 before release, then compare
against local test expectations. Existing joblib/NumPy shape-deprecation warnings
must not be confused with failed inference. Do not retrain or rewrite artifacts
as a deployment workaround. Record the built image digest and resolved base
image digest for the release.

Both classifiers retain placement classification and exclude salary features.
V1 remains separate and explicitly synthetic; it validates 16 inputs but uses
only 11 supported dataset features. Do not claim real-world accuracy.

## Security prerequisites and remaining blockers

1. Configure ingress to replace untrusted forwarded headers, preserve the public
   Host, and forward `X-Forwarded-Proto: https`. Set `FORWARDED_ALLOW_IPS` only to
   that ingress's actual addresses/networks. Do not expose the internal HTTP port
   directly. If the host cannot provide a trustworthy proxy boundary/address
   configuration, this setup is not ready there; do not use wildcard trust or
   development mode to suppress 403 responses. Existing production transport
   checks and all CSRF/ownership/session enforcement remain active.
2. Use same-site HTTPS frontend and API domains, such as two subdomains of an
   owned domain, so existing host-only, Secure, HttpOnly, `SameSite=Lax`,
   `__Host-` cookies work. A default `vercel.app` frontend and an unrelated API
   host are cross-site and will not reliably support this session flow. The
   frontend sends credentials and must use this API's HTTPS origin through
   `VITE_API_BASE_URL`. CORS origins must be explicit; previews require their
   own approved origins and storage arrangement. Do not relax cookies or CSRF.
3. Registration remains disabled pending approved email verification. A fresh
   disk cannot offer password login until an approved account onboarding path
   exists. Development accounts/databases are not an approved public substitute.
   Google sign-in is an existing optional onboarding path; leave all Google
   settings unset if it will not be used.
4. Google configuration currently requires an explicit callback port. A usual
   portless HTTPS callback fails configuration validation. An explicitly
   registered `:443` callback must be tested with Google and the host end to end;
   default-port URL normalisation may cause a mismatch. If it does not work, a
   separate narrow OAuth change is required before enabling it. Do not change
   state, PKCE, nonce, verified-email or session checks.
5. The launcher disables Uvicorn access logging because ordinary access logs
   include OAuth `code`/`state` query strings. Configure host/CDN/proxy logs and
   tracing likewise: omit query strings, bodies, cookies, authorization headers
   and CSRF values. Keep safe operational error logs. Do not enable debug/trace
   or raw request capture on a public deployment.
6. Configure edge rate limiting for public login challenge/login/OAuth routes.
   The existing per-challenge attempt limit does not provide a global public
   request rate limit. Do not bypass session, authorization or origin checks.
7. Disable caching for every `/api` response at the host/CDN. Existing auth,
   owned-profile and production analytics responses set `private, no-store`.
   V1 prediction responses currently lack that explicit header; configure the
   edge to add it and bypass caching, including POSTs, or obtain a separate
   backend fix. Frontend Vercel headers cannot control this external API.

Historical container-preparation verification recorded 28 cases for the launcher/proxy,
two real HTTP/HTTPS security cases and 924 cases passing in a broader selection.
That earlier selection had two stale inventory assertions. Both were subsequently
corrected in the approved test-only cleanup: the full app expects 50 operations,
and the standalone production analytics router checks only its mounted operations
while full-application V1 security coverage remains. The later Windows default
suite recorded 1,362 passes. These historical counts do not establish a Linux
container or public-hosting acceptance result.

## Release sequence (nothing deployed by this preparation)

1. Select a host meeting the proxy, private persistent disk and single-instance
   requirements. Arrange approved account access and the same-site domains.
2. Build from the root with `docker build --platform linux/amd64 -t placepro-backend:demo .`.
   Never send secrets as build arguments. Review image contents and run Linux
   tests/inference; no Docker/Linux execution is implied by local Windows tests.
3. Attach the persistent volume at `/var/lib/placepro` and prepare UID/GID
   `10001:10001` access. Do not copy local databases during this preparation.
4. Configure the environment table, HTTPS ingress, Host restrictions, trusted
   proxy addresses, upload limit, logging redaction, rate limits and cache policy.
5. After deployment is authorised, start the image with its default command,
   using one instance and no overlapping updates. Verify startup and `/health`.
6. In the deployed browser verify login, refresh/session restoration, logout,
   disallowed-origin/CSRF rejection, ownership isolation, production placement,
   salary, V1 synthetic disclosure, resume extraction/review/profile update,
   saved resume/PDF export and a container restart retaining all saved data.
7. Verify volume backups/restores and graceful shutdown, record release digests,
   and monitor memory, latency, disk capacity and safe error logs.
