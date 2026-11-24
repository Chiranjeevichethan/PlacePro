"""Setup checks use temporary stores and never install into existing environments."""

import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
import pytest

from scripts import check_environment as check

ROOT = check.ROOT
POWERSHELL = shutil.which("powershell.exe")


def test_runtime_manifest_pins_complete_active_dependency_closure():
    pins = {canonicalize_name(k): v for k, v in check.read_pins(ROOT / "requirements.txt").items()}
    for name in pins:
        for raw in metadata.requires(name) or []:
            dependency = Requirement(raw)
            if dependency.marker is None or dependency.marker.evaluate({"extra": ""}):
                key = canonicalize_name(dependency.name)
                assert key in pins, (name, raw)
                assert pins[key] in dependency.specifier, (name, raw, pins[key])


def test_manifest_includes_runtime_without_optional_analysis():
    runtime = check.read_pins(ROOT / "requirements.txt")
    development = check.read_pins(ROOT / "requirements-dev.txt")
    analysis = check.read_pins(ROOT / "requirements-analysis.txt")
    assert runtime.items() <= development.items()
    assert runtime.items() <= analysis.items()
    assert "pytest" in development and "httpx2" in development
    assert "matplotlib" in analysis and "matplotlib" not in runtime


def test_conflicting_dependency_pin_fails(isolated_storage):
    manifest = isolated_storage.root / "requirements.txt"
    manifest.write_text("sample==1\nsample==2\n")
    with pytest.raises(ValueError, match="Conflicting"):
        check.read_pins(manifest)


@pytest.mark.parametrize("actual,expected", [(None, "Missing"), ("2", "installed 2"), ("1", None)])
def test_preflight_reports_missing_and_wrong_packages(monkeypatch, actual, expected):
    def version(name):
        if actual is None:
            raise metadata.PackageNotFoundError(name)
        return actual
    monkeypatch.setattr(check.metadata, "version", version)
    errors = check.dependency_errors({"sample": "1"})
    assert (expected in errors[0]) if expected else errors == []


@pytest.mark.parametrize("version,machine", [("3.13.15", "AMD64"), ("3.14.6", "ARM64")])
def test_unsupported_python_fails_before_imports(monkeypatch, capsys, version, machine):
    monkeypatch.setattr(check.platform, "python_version", lambda: version)
    monkeypatch.setattr(check.platform, "machine", lambda: machine)
    monkeypatch.setattr(check, "dependency_errors", lambda _: pytest.fail("Must fail before dependency checks"))
    assert check.main([]) == 1
    assert "Selected:" in capsys.readouterr().err


def test_missing_model_does_not_run_training(monkeypatch, isolated_storage):
    from src import pipeline
    missing = isolated_storage.root / "missing.pkl"
    monkeypatch.setattr(pipeline, "DEFAULT_MODEL_PATH", str(missing))
    with pytest.raises(FileNotFoundError, match="do not run training"):
        check.model_smoke()
    assert not missing.exists()


def test_preflight_import_and_inference_preserve_isolated_stores_and_models(isolated_storage):
    paths = [ROOT / "models/placepro_final_model.pkl", ROOT / "models/placepro_salary_model_v2.pkl"]
    before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
    result = subprocess.run([sys.executable, "-B", "-W", "default", str(ROOT / "scripts/check_environment.py"),
                             "--development", "--models"], cwd=ROOT.parent, capture_output=True, text=True,
                            env=os.environ.copy(), timeout=30)
    assert result.returncode == 0, result.stderr
    assert '"placement_probability": 0.947732' in result.stdout
    output = json.JSONDecoder().raw_decode(result.stdout)[0]
    assert output["salary"]["predicted_salary_lpa"] == pytest.approx(14.86612781395452, abs=1e-9)
    assert "Preflight passed" in result.stdout
    assert [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths] == before
    assert not list(isolated_storage.profiles.iterdir())
    assert not list(isolated_storage.assessments.iterdir())
    assert not isolated_storage.companies_db.exists()


def ps_run(arguments):
    if not POWERSHELL:
        pytest.skip("Windows PowerShell unavailable on this platform")
    return subprocess.run([POWERSHELL, "-NoProfile", "-File", str(ROOT / "scripts/placepro.ps1"),
                            *arguments], cwd=ROOT.parent, capture_output=True, text=True, timeout=45)


def test_powershell_missing_environment_fails_clearly(isolated_storage):
    result = ps_run(["-Command", "Backend", "-PythonExecutable", str(isolated_storage.root / "missing.exe")])
    assert result.returncode != 0
    assert "Python environment not found" in result.stderr


@pytest.mark.parametrize("command", ["Backend", "Frontend"])
def test_powershell_occupied_port_never_reuses_or_stops_server(command):
    with socket.socket() as owned_socket:
        if sys.platform == "win32":
            owned_socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        owned_socket.bind(("127.0.0.1", 0))
        owned_socket.listen()
        port = owned_socket.getsockname()[1]
        result = ps_run(["-Command", command, "-Port", str(port), "-PythonExecutable", sys.executable])
        assert result.returncode != 0
        assert "Choose a free port" in result.stderr
        # The original listener is still reachable after the refused start.
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            pass


@pytest.mark.parametrize("port", ["0", "65536"])
def test_powershell_invalid_port_fails(port):
    result = ps_run(["-Command", "Frontend", "-Port", port])
    assert result.returncode != 0
    assert "ValidateRange" in result.stderr or "greater than" in result.stderr or "less than" in result.stderr


def test_frontend_lock_manifest_and_scripts_match():
    manifest = json.loads((ROOT / "frontend/package.json").read_text())
    lock = json.loads((ROOT / "frontend/package-lock.json").read_text())
    assert lock["lockfileVersion"] == 3
    for key in ("dependencies", "devDependencies"):
        assert manifest[key] == lock["packages"][""][key]
    assert manifest["scripts"] == {
        "dev": "vite", "build": "vite build", "lint": "eslint .",
        "test": "node --test", "preview": "vite preview",
    }
