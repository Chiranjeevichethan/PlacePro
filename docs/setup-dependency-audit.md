# Setup and dependency audit — Phase 29.3.7

> Historical snapshot: the original phase dates, design decisions and recorded
> test results below are preserved. Statements about the then-current inventory,
> unavailable features and pre-authentication behavior are superseded by the
> [reviewed 2026-11-24 release snapshot](../backend/DEPLOYMENT.md#reviewed-release-snapshot-2026-11-24).
> This documentation change reruns no application tests and establishes no new
> Linux/Docker or browser acceptance.

Audited 2026-11-07 using the complete working tree, not HEAD alone. The existing
`.venv` and frontend `node_modules` were preserved. There was no Python manifest,
Python/Node version file, environment example, root README or setup script.
The frontend README described obsolete mock prediction/localStorage-only profiles.
No authentication, database, ML architecture or application contract changes belong
to this phase. Current setup commands are in [the root guide](../README.md).

## Dependency strategy and generation

Validated baseline: CPython 3.14.6, Windows AMD64; Node 24.15.0/npm 11.12.1;
FastAPI 0.141.1, Starlette 1.6.0, Pydantic 2.13.4, Uvicorn 0.52.3;
NumPy 2.5.2, SciPy 1.18.0, pandas 3.0.5, scikit-learn 1.9.0, joblib 1.5.3.
The bare Python/launcher configuration is not equivalent to the existing venv.
Other Python/architecture/version combinations have not been validated here.

Runtime imports were audited in backend, `src`, test fixtures and legacy analysis.
Direct runtime roots: FastAPI, Uvicorn, Pydantic, python-multipart, pypdf,
python-docx, pandas, NumPy, scikit-learn and joblib. Installed `importlib.metadata`
distribution requirements were traversed recursively, evaluating active markers
with `extra=''` on the validated platform. Every resulting distribution version
was pinned in `requirements.txt` (28 packages). No blanket pip freeze was used.

`requirements-dev.txt` includes runtime and the closure of pytest/httpx2 (eight
additional packages). Actual Starlette 1.6 source prefers httpx2 and falls back
to older httpx; the former is installed and tested. No FastAPI `standard` or
Uvicorn `standard` extra is necessary. `requirements-analysis.txt` adds the
installed matplotlib/seaborn closure (nine packages) for optional legacy plotting.
No installed booster/analysis package was uninstalled; unused experimental packages
are not claimed to be fully supported by the runtime manifest.

Pins were checked against the installed metadata and active transitive requirements.
`pip check` succeeds. They are **version snapshots**, not hash locks, an original
training-environment record or a cross-platform guarantee. Fresh wheel installation
must be validated before making a stronger distribution claim. A trusted offline
wheelhouse would need original release wheels and checksums; copying site-packages
is not a fresh dependency installation and was not substituted for that check.

Frontend manifest and tracked lock root agree exactly; npm lockfile version is 3.
Installed versions include React/React DOM 19.2.8, Vite 8.2.1, React plugin 6.0.5,
ESLint 10.8.1. Vite/plugin engines are `^20.19.0 || >=22.12.0`; ESLint/@eslint/js
require `^20.19.0 || ^22.13.0 || >=24`. Use the tested Node 24 baseline.
The manifest, lockfile and existing dependencies remain byte-identical. npm ci is
appropriate only in a new directory because it removes existing node_modules.

## Exact warning origin

The baseline full backend suite completed: **520 passed, 0 failed/errors/skipped/
deselected, 10 warnings, 37.95 seconds**. A read-only pytest hook recorded every
warning without changing warning filters. They are all the same category/message:

```text
joblib/numpy_pickle.py:207: DeprecationWarning:
Setting the shape on a NumPy array has been deprecated in NumPy 2.5.
As an alternative, you can create a new view using np.reshape (with copy=False if needed).
    array.shape = self.shape
```

| Warnings | Trigger/test | Dependency operation | Correctness / artifact impact |
| --- | --- | --- | --- |
| 1–8 | `test_performance.py::test_prediction_history_summary` | First uncached placement inference → `src.pipeline.predict_placement` → `joblib.load(placepro_final_model.pkl)` → `NumpyArrayWrapper.read_array`, C-order shape restoration | Existing arrays load; placement regression/HTTP tests pass. This is not eight failed assessments or corrupt history. |
| 9–10 | `test_salary_prediction.py::test_salary_prediction_success` | First salary API inference → `_load_model` → `joblib.load(placepro_salary_model_v2.pkl)` → the same C-order shape restoration | Existing salary arrays load; API, prediction and reconstructed holdout regression pass. No model resave needed. |

Pytest warning counts depend on its per-test filters and module-level model caches;
the first cold loads own these warnings in this collection order. They are not
ten distinct defects or a warning on every prediction. Joblib 1.5.3 restores newly
allocated arrays using direct `.shape` assignment; the F-order path uses similar
assignment at a different line, but **the ten observed warnings are all line 207**.
NumPy 2.5 introduced this deprecation to avoid unsafe mutation of shared arrays.
The loader is operating on newly read private arrays in this path; no failing
runtime operation or prediction discrepancy was observed in the tested baseline.
This is a serialization-loader deprecation, not a scikit-learn inconsistent-version
warning, ABI exception or evidence of student-data corruption.

## Resolution decision

Retain the currently tested NumPy/joblib/scikit-learn versions. No global warning
filter, monkey patch, dependency source edit, downgrade, upgrade, retraining or
artifact rewrite is introduced. Current loading/inference succeeds; future NumPy
removal could break this joblib loader. A later compatible joblib release may fix
the operation, but changing it requires isolated original-artifact load, prediction
parity, salary holdout and full backend tests before adopting new pins.

The original artifact training-environment metadata is incomplete. Do not infer
original versions from current installed packages or claim arbitrary upgrades are
supported. scikit-learn explicitly does not support loading across different
training/library versions; joblib also limits cross-Python pickle compatibility.
Warnings are retained as actionable compatibility debt, not hidden for a clean log.

Sources inspected, alongside actual installed dependency code:

- [NumPy 2.5 release notes, shape deprecation](https://numpy.org/doc/stable/release/2.5.0-notes.html).
- [scikit-learn model persistence and version compatibility](https://scikit-learn.org/stable/model_persistence.html).
- [joblib persistence and Python compatibility](https://joblib.readthedocs.io/en/latest/user_guide/persistence.html) (latest documentation is newer than installed 1.5.3).
- [npm ci behavior](https://docs.npmjs.com/cli/v11/commands/npm-ci/).

## Configuration and failure boundaries

Storage and salary fallback variables are read before app imports. Python has no
dotenv loader; root `.env.example` is a reference. Vite reads its own frontend
environment files at dev/build startup. All required/optional/test-only variables,
hard-coded CORS/model paths and host/port choices are inventoried in README.
Helpers do not install dependencies, seed students, load real records, replace
environment files, empty builds, migrate stores or terminate existing servers.
Normal development API requests still intentionally persist application state.

Setup tests cover pin closure/conflicts, missing/wrong packages, Python mismatch,
model absence, imports/inference without storage writes, manifest/lock agreement,
PowerShell failure exits, occupied ports and invalid ports. The first new-test run
had **13 passed / 3 setup errors** due to an inaccessible shared pytest tmp_path
directory (WinError 5). Tests now use the existing retained isolated_storage fixture,
avoiding ACL changes and pytest cleanup of existing directories.

## Fresh-environment evidence

Wheel-only pip install of requirements-dev.txt failed at
annotated-doc==0.0.5 (no available distribution); direct PyPI/npm socket probes
failed with **WinError 10013**, and pip cache contained no required backend wheels. No unrestricted network permission was requested. Fresh backend dependency install,
imports, startup and full tests therefore remain **unverified**; existing-environment
validation is reported separately. No package availability/version incompatibility
is inferred solely from this restricted-network failure.

A separate frontend source copy received `npm ci --fetch-retries=0
--fetch-timeout=15000`: **135 packages installed, exit 0, no warnings**. Available
npm package data supported installation despite direct socket restrictions; an
empty-cache online npm install is not established. That copy passed **121 Node
tests, 0 failures/cancelled/skipped/todo**, lint and production build (64 modules,
239 ms). The build notice that an outside-root outDir will not be emptied is
intentional preservation behavior. Existing node_modules and lockfiles are intact.

The dated results below summarize startup, script validation, full-suite and
preservation checks. Current public commands and platform boundaries are in the
[reviewed release snapshot](../backend/DEPLOYMENT.md#reviewed-release-snapshot-2026-11-24). Do not represent incomplete fresh Python validation as complete.

Final existing-environment full suite via the PowerShell helper: **536 passed,
0 failed/errors/skipped/deselected, 10 warnings, 46.49 seconds** (520 preserved
cases plus 16 setup cases). Focused setup: **16 passed**, no errors/warnings/skips,
11.92 seconds. Current frontend helper: **121 passed**, lint/build exit 0 (64 modules,
345 ms). Preflight imports/model inference/pip check passed with two visible
shape-deprecation notices under the default filter. The initial helper's deprecated
`multipart` import was corrected to the package's `python_multipart` namespace.

Startup checks passed **6/6**: production ASGI startup, fresh Vite startup,
missing-profile 404, placement/salary inference and isolated DEMO store. Real
Chromium 156.0.8078.80 smoke checks passed **3/3**, no page errors: fresh login,
configured API URL and explicit missing-profile creation without automatic writes.
Two earlier browser harness attempts had a response-metadata TypeError and are not
counted as passes. Browser checks used external Playwright tools and the read skill,
with agent-browser CLI unavailable. This is smoke coverage, not a repeat of prior
phases' broad browser scenarios or fresh Python startup verification.

Owned startup processes were stopped; PID/start-time identity checks preceded the
fallback Stop-Process calls after initial PTY stop input was not delivered. The
launcher then completed cleanup after `STOP\r`; model/API/node PIDs are absent and
no listeners remain on the owned ports. Socket probes time out in this sandbox,
so connection-refused behavior is not claimed. Optional WMI process inspection
returned Access denied; no escalation or unrelated process stop was attempted.
All 530 protected phase-start files remain unchanged and no baseline file was deleted.


## 2026-11-07 follow-up — Phase 29.3.7-R

The original fresh-backend blocker above is resolved for offline validation. A new
CPython 3.14.6 AMD64 venv with system-site-packages disabled installed unchanged
requirements.txt (28 packages) and requirements-dev.txt (eight additional packages).
Pip 26.1.2, pip check and all 36 exact declared versions pass. Existing environments,
manifests, model files and runtime records were preserved.

Direct HTTPS to PyPI and files.pythonhosted.org still fails with socket WinError
10013 despite successful DNS. No proxy or approved mirror is configured; WinHTTP
reports direct access and read-only firewall inspection returns Access denied.
These checks cannot identify the exact sandbox/firewall/endpoint-security owner.
No controls were changed or bypassed and no unrestricted access was requested.

The previous conventional pip wheel-list check omitted the HTTP cache. Read-only
inspection found 831 cached response bodies, including 300 wheels. Cached simple
indexes are gzip encoded. All 36 pins have Windows/CPython-compatible original
release wheels whose SHA-256 matches the cache-addressed PyPI index metadata.
Release URLs/cache keys, package Name/Version, tags and ZIP CRCs are checked before
copying bytes to a new wheelhouse. Both installs use --no-index/--no-cache-dir and
--find-links to that wheelhouse. No network install retry, arbitrary download,
installed-site-packages copy, dependency upgrade or model rewrite is used.

Fresh app import generates 22 OpenAPI paths. Preflight and HTTP predictions match
placement 0.947732 and salary 14.86612781395452 LPA. Original-artifact regression,
including the unchanged salary reconstructed-holdout quality test, passes in the
full suite. Focused setup: **16 passed**, zero failures/errors/skips/deselections,
10.73 seconds. Full backend: **536 passed**, zero failures/errors/skips/deselections,
**10 existing joblib/NumPy warnings**, 40.05 seconds, including all five live-HTTP
cases. Final production ASGI startup: **6/6 HTTP smoke checks pass**. The initial
harness's incorrect salary URL caused a 404; source inspection corrected the harness
to /api/salary-predict without application changes. Earlier harness failures/results
are retained and documented in the journal.

Every process receives new temporary storage before imports. Import/preflight
create no records or SQLite; startup creates no profiles/sessions and only its own
DEMO SQLite. Owned servers are stopped, and all 530 protected files retain hashes.
The two model-shape notices in preflight and ten full-suite warnings remain visible.
Frontend/browser validation was not repeated in this backend-only follow-up.

Direct online/empty-cache install, other
platforms/Python versions, optional plotting install and portable wheelhouse
distribution remain unverified. Cache-index hashes were verified locally, not
re-fetched over a newly authenticated connection. This completes the assigned
fresh-backend validation, not a broader OS install or training-version guarantee. 
