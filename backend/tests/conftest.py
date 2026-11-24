"""Bind storage before collection and give every test its own writable stores."""

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from urllib.parse import urlsplit

import pytest

from backend.tests.support import (
    PROJECT_ROOT,
    STORAGE_ENV_VARS,
    create_test_storage,
    get_api_url,
    stop_owned_process,
)


def pytest_configure(config):
    storage = create_test_storage()
    config._placepro_storage = storage
    config._placepro_original_env = {
        key: os.environ.get(key) for key in STORAGE_ENV_VARS
    }
    os.environ.update(storage.environment())


def pytest_unconfigure(config):
    for key, value in getattr(config, "_placepro_original_env", {}).items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


@pytest.fixture(autouse=True)
def isolated_storage(monkeypatch, request):
    from backend.app.services import (
        assessment_service,
        company_store,
        profile_service,
    )

    storage = create_test_storage(request.config._placepro_storage.root)
    for key, value in storage.environment().items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(profile_service, "PROFILES_DIR", str(storage.profiles))
    monkeypatch.setattr(assessment_service, "ASSESSMENTS_DIR", str(storage.assessments))
    monkeypatch.setattr(company_store, "DB_PATH", str(storage.companies_db))
    monkeypatch.setattr(company_store, "_initialized", False)
    return storage


@pytest.fixture(scope="session")
def live_server_url(request):
    """Start a separate process; never reuse/stop an existing application server."""
    try:
        api_url = get_api_url()
    except ValueError as exc:
        pytest.fail(str(exc))
    parsed = urlsplit(api_url)
    host = "127.0.0.1" if parsed.hostname == "localhost" else parsed.hostname
    family = socket.AF_INET6 if host == "::1" else socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM) as probe:
        if sys.platform == "win32":
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            probe.bind((host, parsed.port))
        except OSError as exc:
            pytest.fail(
                f"Cannot start an isolated test server at {api_url}: {exc}. "
                "Choose a free loopback port with PLACEPRO_API_URL; "
                "existing servers are never reused."
            )

    storage = create_test_storage(request.config._placepro_storage.root)
    run_id = uuid.uuid4().hex
    environment = os.environ.copy()
    environment.update(storage.environment())
    environment["PLACEPRO_TEST_STORAGE_ROOT"] = str(storage.root)
    environment["PLACEPRO_TEST_RUN_ID"] = run_id
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    log_path = storage.root / "server.log"
    process = None
    server_pid = None
    with log_path.open("w", encoding="utf-8") as log:
        try:
            process = subprocess.Popen(
                [sys.executable, "-B", "-m", "uvicorn",
                 "backend.tests.http_server:app", "--host", host,
                 "--port", str(parsed.port)],
                cwd=PROJECT_ROOT, env=environment, stdout=log, stderr=log,
                creationflags=(subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0),
            )
            deadline = time.monotonic() + 30
            last_error = "No health response received"
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    pytest.fail(
                        f"Isolated test server exited with code {process.returncode}. "
                        f"Log: {log_path}\n{log_path.read_text(encoding='utf-8')}"
                    )
                try:
                    with urllib.request.urlopen(f"{api_url}/health", timeout=1) as response:
                        if response.headers.get("X-PlacePro-Test-Run-ID") != run_id:
                            pytest.fail(
                                f"Server at {api_url} is not the owned isolated test process."
                            )
                        server_pid = int(response.headers["X-PlacePro-Test-Process-ID"])
                        body = json.loads(response.read().decode("utf-8"))
                        assert response.status == 200 and body.get("status") == "ok", body
                        break
                except urllib.error.URLError as exc:
                    last_error = str(exc)
                    time.sleep(0.1)
            else:
                pytest.fail(
                    f"Isolated test server was not ready within 30s: {last_error}. "
                    f"Log: {log_path}"
                )
            request.config._placepro_http_storage = storage
            yield api_url
        finally:
            if process is not None:
                stop_owned_process(process, server_pid)


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    terminalreporter.write_line(
        f"Isolated test artifacts retained: {config._placepro_storage.root}"
    )
    storage = getattr(config, "_placepro_http_storage", None)
    if storage is not None:
        terminalreporter.write_line(f"HTTP server storage/log: {storage.root}")
