"""Regression checks for failures and isolation in the test infrastructure."""

import importlib
import io
import urllib.error
from pathlib import Path

import pytest

from backend.tests import support


@pytest.mark.parametrize("module_name", ["test_resume", "test_readiness", "test_performance"])
def test_failed_check_raises_and_preserves_diagnostics(module_name):
    module = importlib.import_module(f"backend.tests.{module_name}")
    with pytest.raises(AssertionError, match="failed condition: actual value"):
        module.check(False, "failed condition", "actual value")


@pytest.mark.parametrize("status", [422, 500])
def test_prediction_http_errors_fail_instead_of_skipping(monkeypatch, status):
    from backend.tests import test_predict

    def reject_request(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url, status, "rejected", {},
            io.BytesIO(b'{"detail":"injected failure"}'),
        )

    monkeypatch.setattr(support.urllib.request, "urlopen", reject_request)
    with pytest.raises(AssertionError, match=f"HTTP prediction failed: {status}"):
        test_predict.test_http(support.DEFAULT_API_URL)


def test_prediction_connection_errors_fail_instead_of_skipping(monkeypatch):
    from backend.tests import test_predict

    def reject_request(request, timeout):
        raise urllib.error.URLError("injected connection failure")

    monkeypatch.setattr(support.urllib.request, "urlopen", reject_request)
    with pytest.raises(AssertionError, match="Server not reachable: injected connection failure"):
        test_predict.test_http(support.DEFAULT_API_URL)


def test_default_http_url_matches_documented_backend_port(monkeypatch):
    monkeypatch.delenv("PLACEPRO_API_URL", raising=False)
    assert support.get_api_url() == support.DEFAULT_API_URL
    assert support.DEFAULT_API_URL.endswith(":8765")


def test_http_url_can_configure_a_different_loopback_port(monkeypatch):
    monkeypatch.setenv("PLACEPRO_API_URL", "http://localhost:9876/")
    assert support.get_api_url() == "http://localhost:9876"


@pytest.mark.parametrize("url", [
    "http://example.com:8765",
    "https://127.0.0.1:8765",
    "http://127.0.0.1:8765/api",
    "http://user:password@127.0.0.1:8765",
    "http://127.0.0.1:0",
])
def test_http_url_rejects_external_or_ambiguous_servers(monkeypatch, url):
    monkeypatch.setenv("PLACEPRO_API_URL", url)
    with pytest.raises(ValueError, match="PLACEPRO_API_URL must be a loopback HTTP URL"):
        support.get_api_url()


def test_all_service_stores_are_bound_to_fresh_test_storage(isolated_storage):
    from backend.app.services import assessment_service, company_store, profile_service

    assert Path(profile_service.PROFILES_DIR) == isolated_storage.profiles
    assert Path(assessment_service.ASSESSMENTS_DIR) == isolated_storage.assessments
    assert Path(company_store.DB_PATH) == isolated_storage.companies_db
    assert list(isolated_storage.profiles.iterdir()) == []
    assert list(isolated_storage.assessments.iterdir()) == []
    assert not isolated_storage.companies_db.exists()
    assert not isolated_storage.root.is_relative_to(support.PROJECT_ROOT / "data")


def test_owned_server_shutdown_stops_redirector_tree_and_preserves_other_listener(isolated_storage):
    import socket
    import subprocess
    import sys
    import time
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    with socket.socket() as other:
        other.bind(("127.0.0.1", 0))
        other.listen()
        other_port = other.getsockname()[1]
        code = ("import os,socket,time; s=socket.socket(); "
                f"s.bind(('127.0.0.1',{port})); s.listen(); "
                "print(os.getpid(),flush=True); time.sleep(60)")
        process = subprocess.Popen(
            [sys.executable, "-B", "-c", code],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        server_pid = None
        try:
            server_pid = int(process.stdout.readline())
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                        break
                except OSError:
                    time.sleep(0.05)
            else:
                pytest.fail("Owned synthetic HTTP process failed to start.")
        finally:
            support.stop_owned_process(process, server_pid)
            process.stdout.close()
        assert process.poll() is not None
        with socket.socket() as connection:
            connection.settimeout(1)
            assert connection.connect_ex(("127.0.0.1", port)) != 0
        with socket.create_connection(("127.0.0.1", other_port), timeout=1):
            pass
