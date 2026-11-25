"""CI-only release verifier. Never train, provision, publish or read user stores.

The three SHA-256 baselines match the approved consolidated-cleanup record
verified on 2026-11-24. They are fixed expectations, not regenerated from files
being tested. The salary hash also matches the aggregate-only test provenance.
Only --backend-tests writes isolated synthetic test artifacts to runner temp.
"""

import argparse
import hashlib
import importlib
from importlib import metadata
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET


PYTHON_VERSION = "3.14.6"
NODE_VERSION = "24.15.0"
NPM_VERSION = "11.12.1"
MODEL_HASHES = {
    "models/placepro_final_model.pkl":
        "bbf1dc03808499bb9f97124b4dab7e00c1a645a9073edae3bc8d5c5fd1bc9de8",
    "models/placepro_salary_model_v2.pkl":
        "cd652f0056324984db56f2347aee46c1528adbea6bc86dbe62e764715e1b9958",
    "experimental/v1/placepro_v1_production_fields.pkl":
        "49468b8800cdd5bb1d38ed0a7ef52fdabe6ccfa6e21fb18be0310ef9f114448a",
}

# The reviewed synthetic sample already used by scripts/check_environment.py
# and backend/tests/test_setup.py; these are explicit inputs, not missing-value
# imputation. Production parity expectations below come from those existing tests.
SMOKE_INPUT = {
    "branch": "CSE", "college_tier": "Tier-1", "cgpa": 8.5,
    "backlogs": 0, "coding_skills": 8.2, "dsa_score": 8.0,
    "aptitude_score": 85.0, "communication_skills": 7.5,
    "ml_knowledge": 6.5, "system_design": 5.0, "internships": 2,
    "projects_count": 4, "certifications": 2, "hackathons": 1,
    "open_source_contributions": 1, "extracurriculars": 1,
}


class VerificationError(RuntimeError):
    """A safe-to-print prerequisite or verification failure."""


def require(condition, message):
    if not condition:
        raise VerificationError(message)


def verify_python():
    require(platform.python_implementation() == "CPython"
            and platform.python_version() == PYTHON_VERSION
            and platform.machine().lower() in {"amd64", "x86_64"}
            and not sysconfig_free_threaded(),
            f"Use regular x64 CPython {PYTHON_VERSION}; no version fallback is allowed.")


def sysconfig_free_threaded():
    import sysconfig
    return bool(sysconfig.get_config_var("Py_GIL_DISABLED"))


def verify_hashes(root):
    for relative, expected in MODEL_HASHES.items():
        path = root / relative
        require(path.is_file() and not path.is_symlink(),
                f"Missing trusted model artifact: {relative}. Do not train or substitute a model.")
        require(hashlib.sha256(path.read_bytes()).hexdigest() == expected,
                f"Approved SHA-256 mismatch: {relative}.")
    print("PASS: all three model artifacts match approved SHA-256 baselines.")


def verify_source(root):
    required = (
        ".python-version", ".node-version", "requirements.txt", "requirements-dev.txt",
        "Dockerfile", ".dockerignore", "backend/__init__.py", "backend/container_start.py",
        "backend/DEPLOYMENT.md", "backend/app/main.py", "src/pipeline.py",
        "experimental/v1/feature_schema.py",
        "experimental/v1/placepro_v1_production_fields_metadata.json",
        "backend/tests/conftest.py", "backend/tests/tls_support.py",
        "backend/tests/test_session_http.py", "backend/tests/salary_summary.py",
        "backend/tests/fixtures/salary_training_summary.json", "scripts/demo.py",
        "scripts/demo_frontend.mjs", "frontend/package.json", "frontend/package-lock.json",
        "frontend/vite.config.js", "frontend/vercel.json", "frontend/.env.example",
    )
    for relative in required:
        require((root / relative).is_file(), f"Required clean-checkout file is missing: {relative}.")
    for filename, expected in ((".python-version", PYTHON_VERSION), (".node-version", NODE_VERSION)):
        require((root / filename).read_text().strip() == expected,
                f"{filename} differs from the approved release version.")
    manifest = json.loads((root / "frontend/package.json").read_text())
    lock = json.loads((root / "frontend/package-lock.json").read_text())
    require(lock.get("lockfileVersion") == 3, "Use the reviewed frontend lockfile v3.")
    for key in ("dependencies", "devDependencies"):
        require(manifest.get(key) == lock["packages"][""].get(key),
                f"Frontend manifest/lock mismatch in {key}; do not regenerate the lock in CI.")
    print("PASS: required release files, version files and frontend lock agreement.")


def tool_version(name, expected=None):
    executable = shutil.which(name)
    require(executable is not None, f"Required tool is unavailable: {name}.")
    result = subprocess.run([executable, "--version" if name != "openssl" else "version"],
                            capture_output=True, text=True, timeout=15, check=False)
    require(result.returncode == 0, f"Required tool cannot execute: {name}.")
    if expected is not None:
        require(result.stdout.strip().removeprefix("v") == expected,
                f"Require {name} {expected}; CI will not install a replacement or upgrade.")
    else:
        require(result.stdout.startswith("OpenSSL "), "TLS tests require a working trusted OpenSSL.")


def read_pins(path, seen=None):
    seen = set() if seen is None else seen
    path = path.resolve()
    require(path not in seen, "Circular pinned requirements include.")
    seen.add(path)
    pins = {}
    for raw in path.read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("-r "):
            entries = read_pins(path.parent / line[3:].strip(), seen)
        else:
            require(re.fullmatch(r"[A-Za-z0-9_.-]+==[A-Za-z0-9_.+-]+", line),
                    "Every backend release dependency must retain an exact version pin.")
            name, version = line.split("==")
            entries = {name: version}
        for name, version in entries.items():
            require(name not in pins or pins[name] == version, f"Conflicting dependency pin: {name}.")
            pins[name] = version
    seen.remove(path)
    return pins


def verify_dependencies(root, development):
    pins = read_pins(root / ("requirements-dev.txt" if development else "requirements.txt"))
    for name, expected in pins.items():
        try:
            actual = metadata.version(name)
        except metadata.PackageNotFoundError:
            raise VerificationError(f"Missing pinned dependency: {name}=={expected}.") from None
        require(actual == expected, f"Pinned dependency mismatch: require {name}=={expected}.")
    for module in ("backend.app.main", "docx", "pypdf", "python_multipart"):
        importlib.import_module(module)
    print(f"PASS: {len(pins)} exact dependency pins and runtime imports.")


def verify_models(root):
    from src import pipeline
    from backend.app.services import experimental_v1_service as v1
    from backend.app.services.salary_prediction_service import predict_salary
    from experimental.v1.feature_schema import INPUT_COLUMNS, MODEL_FEATURES, MODEL_VERSION, IGNORED_INPUTS

    require(pipeline.TARGET_COLUMN == "placement_status", "Production placement target drift.")
    require("salary_package_lpa" not in pipeline.RAW_FEATURE_COLUMNS
            and "salary_package_lpa" not in MODEL_FEATURES
            and "placement_status" not in MODEL_FEATURES,
            "Placement classifier feature leakage detected.")
    require(set(SMOKE_INPUT) == set(INPUT_COLUMNS) == set(pipeline.RAW_FEATURE_COLUMNS)
            and len(INPUT_COLUMNS) == 16 and len(MODEL_FEATURES) == 11,
            "Production/V1 input or supported V1 model feature schema drift.")
    placement = pipeline.predict_placement(SMOKE_INPUT)
    salary = predict_salary(SMOKE_INPUT)
    experimental = v1.predict_experimental_v1(SMOKE_INPUT)
    require(set(placement) == {"placement_probability", "prediction", "confidence", "model_version"}
            and placement["model_version"] == "placepro-final-v1"
            and placement["prediction"] == "PLACED"
            and math.isclose(placement["placement_probability"], 0.947732, abs_tol=1e-9, rel_tol=0),
            "Production placement contract or approved sample inference parity failed.")
    require(set(salary) == {"predicted_salary_lpa", "model_version"}
            and salary["model_version"] == "placepro-salary-v2"
            and math.isclose(salary["predicted_salary_lpa"], 14.86612781395452, abs_tol=1e-9, rel_tol=0),
            "Salary contract or approved sample inference parity failed.")
    require(set(experimental) == {"placement_probability", "prediction", "confidence",
                                  "model_version", "experimental", "synthetic_data_notice"}
            and experimental["model_version"] == MODEL_VERSION
            and experimental["experimental"] is True
            and "synthetic" in experimental["synthetic_data_notice"].lower()
            and "not a validated" in experimental["synthetic_data_notice"],
            "Experimental V1 contract or synthetic limitation disclosure failed.")
    for result in (placement, experimental):
        probability, confidence = result["placement_probability"], result["confidence"]
        require(math.isfinite(probability) and 0 <= probability <= 1
                and math.isfinite(confidence) and 0.5 <= confidence <= 1
                and math.isclose(confidence, max(probability, 1 - probability), abs_tol=1e-6),
                "Invalid classifier probability or confidence.")
    require(experimental["prediction"] == ("Placed" if experimental["placement_probability"] >= 0.5 else "Not Placed"),
            "Experimental V1 threshold/label mismatch.")
    altered = SMOKE_INPUT | {key: 0 if key != "dsa_score" else 1 for key in IGNORED_INPUTS}
    require(v1.predict_experimental_v1(altered) == experimental,
            "Unsupported V1 inputs unexpectedly influence inference.")
    require(pipeline.predict_placement(SMOKE_INPUT) == placement, "V1 inference changed production output.")
    verify_hashes(root)
    print("PASS: real production placement, salary and separate synthetic V1 inference.")


def verify_image(root):
    require(hasattr(os, "getuid") and os.getuid() == os.getgid() == 10001,
            "Image verification must run as production UID/GID 10001.")
    fixed = set(MODEL_HASHES) | {"requirements.txt", "backend/__init__.py", "backend/container_start.py",
                               "src/pipeline.py", "experimental/v1/feature_schema.py"}
    allowed_python = re.compile(r"backend/app/(?:[A-Za-z0-9_]+/)?[A-Za-z0-9_]+\.py")
    files = list(root.rglob("*"))
    require(not any(path.is_symlink() for path in files), "Unexpected link in runtime image source.")
    actual = {path.relative_to(root).as_posix() for path in files if path.is_file()}
    require(fixed <= actual and "backend/app/main.py" in actual, "Required image runtime file is missing.")
    require(all(path in fixed or allowed_python.fullmatch(path) for path in actual),
            "Image contains files outside the reviewed runtime allowlist; do not print private filenames.")
    print("PASS: non-root image /app contains only approved runtime code, requirements and three models.")


def run_backend_tests(root):
    directory = Path(tempfile.mkdtemp(prefix="placepro-ci-", dir=os.environ.get("RUNNER_TEMP")))
    directory.chmod(0o700)
    report = directory / "backend.xml"
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    # Existing conftest selects and owns all synthetic stores before collection.
    # Raw failures can contain request/session values; keep logs private and never
    # upload them. Only counts and parameter-free test identifiers reach CI logs.
    with (directory / "backend.log").open("x", encoding="utf-8") as log:
        result = subprocess.run([sys.executable, "-B", "-m", "pytest", "backend/tests", "-q",
                                 "-p", "no:cacheprovider", "--tb=no", f"--junitxml={report}"],
                                cwd=root, env=environment, stdout=log, stderr=subprocess.STDOUT,
                                timeout=840, check=False)
    require(report.is_file(), "Backend test collection/execution failed before producing its private report.")
    cases = ET.parse(report).findall(".//testcase")
    failures = [case for case in cases if case.find("failure") is not None or case.find("error") is not None]
    skips = [case for case in cases if case.find("skipped") is not None]
    print(f"Backend: {len(cases)} cases; {len(failures)} failures/errors; {len(skips)} skips.")
    for case in failures:
        identifier = case.get("classname", "") + "." + case.get("name", "").split("[", 1)[0]
        print("FAILED: " + re.sub(r"[^A-Za-z0-9_.]", "?", identifier))
    for case in skips:
        require(case.get("classname", "").endswith("test_setup")
                and case.get("name", "").startswith("test_powershell_")
                and "Windows PowerShell unavailable" in case.find("skipped").get("message", ""),
                "Unexpected skipped backend coverage; security/TLS checks must execute.")
    tls = [case for case in cases if case.get("name") ==
           "test_actual_production_server_security_and_reliable_shutdown[True]"]
    require(len(tls) == 1 and not any(tls[0].find(tag) is not None for tag in ("skipped", "failure", "error")),
            "Real production HTTPS/TLS security verification did not pass.")
    require(result.returncode == 0 and cases and not failures,
            "Full default backend suite failed; rerun pytest backend/tests locally. Private logs are not uploaded.")
    print("PASS: full default backend suite, including live HTTP/HTTPS and owned Vite harness.")
    if skips:
        print("Existing Windows PowerShell-only tests require separate Windows verification.")


def verify_container_http(base):
    parsed = urlsplit(base)
    require(parsed.scheme == "http" and parsed.hostname == "127.0.0.1" and parsed.port
            and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment
            and parsed.path in {"", "/"}, "Container smoke URL must be an explicit loopback HTTP origin.")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def status(path, headers=None):
        request = urllib.request.Request(base.rstrip("/") + path, headers=headers or {})
        try:
            with opener.open(request, timeout=2) as response:
                return response.status
        except urllib.error.HTTPError as error:
            error.close()
            return error.code

    deadline = time.monotonic() + 45
    while True:
        try:
            if status("/health") == 200:
                break
        except urllib.error.URLError:
            pass
        require(time.monotonic() < deadline, "Production container did not become healthy within 45 seconds.")
        time.sleep(0.25)
    require(status("/docs") == 404, "Production documentation unexpectedly exposed.")
    require(status("/api/auth/session") == 401, "Anonymous container session access was not denied.")
    for headers in ({"Origin": "https://app.example.test"},
                    {"Origin": "https://app.example.test", "X-Forwarded-Proto": "https"},
                    {"Origin": "https://untrusted.example.test", "X-Forwarded-Proto": "https"}):
        require(status("/api/auth/login-challenge", headers) == 403,
                "Production HTTP, untrusted forwarded-header or origin denial failed.")
    print("PASS: actual production startup, liveness and anonymous/HTTP/proxy/origin denials.")
    print("This HTTP smoke does not establish public HTTPS ingress or persistent-volume readiness.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path,
        help="Repository or runtime directory; required outside scripts/ci.",
    )
    for flag in ("source", "runtime", "development", "node", "openssl", "models", "image", "backend-tests"):
        parser.add_argument("--" + flag, action="store_true")
    parser.add_argument("--container-http", metavar="LOOPBACK_ORIGIN")
    args = parser.parse_args(argv)
    try:
        if args.root is not None:
            root = args.root.resolve()
        else:
            script = Path(__file__).resolve()
            require(script.parent.name == "ci" and script.parent.parent.name == "scripts",
                    "Specify --root when running the verifier outside scripts/ci.")
            root = script.parent.parent.parent
        require(root.is_dir(), "Verification root must be an existing directory.")
        verify_python()
        verify_hashes(root)
        if args.source:
            verify_source(root)
        if args.node or args.backend_tests:
            tool_version("node", NODE_VERSION)
            tool_version("npm", NPM_VERSION)
            print("PASS: exact Node and npm baselines; no upgrades.")
        if args.openssl or args.backend_tests:
            tool_version("openssl")
            print("PASS: trusted OpenSSL available; certificate verification remains enabled.")
        if args.image:
            verify_image(root)
        sys.path.insert(0, str(root))
        if args.runtime or args.development or args.models or args.backend_tests:
            verify_dependencies(root, args.development or args.backend_tests)
        if args.models:
            verify_models(root)
        if args.backend_tests:
            run_backend_tests(root)
        if args.container_http:
            verify_container_http(args.container_http)
        verify_hashes(root)
    except VerificationError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    except Exception as error:
        # Do not echo arbitrary library/HTTP errors, environment values, bodies,
        # cookies or tokens. Prerequisite checks above supply safe diagnostics.
        print(f"FAIL: release verification raised {type(error).__name__}; "
              "rerun the named check locally for private diagnostics.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
