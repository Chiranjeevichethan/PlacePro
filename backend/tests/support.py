"""Shared test configuration and HTTP helpers; never select project data stores."""

import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_API_URL = "http://127.0.0.1:8765"
STORAGE_ENV_VARS = (
    "PLACEPRO_PROFILES_DIR",
    "PLACEPRO_ASSESSMENTS_DIR",
    "PLACEPRO_COMPANIES_DB",
    "PLACEPRO_AUTH_DB",
    "PLACEPRO_GOALS_DB",
    "PLACEPRO_RESUME_BUILDER_DB",
)


def get_api_url():
    """Configure an owned local server, never an external application's data."""
    value = os.environ.get("PLACEPRO_API_URL", DEFAULT_API_URL).strip()
    parsed = urlsplit(value)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or not parsed.port
    ):
        raise ValueError(
            "PLACEPRO_API_URL must be a loopback HTTP URL with an explicit free "
            f"port and no path or credentials (default {DEFAULT_API_URL}). "
            "Pytest starts its own isolated server."
        )
    return value.rstrip("/")


@dataclass(frozen=True)
class TestStorage:
    root: Path
    profiles: Path
    assessments: Path
    companies_db: Path
    auth_db: Path
    goals_db: Path
    resume_builder_db: Path

    def environment(self):
        return dict(zip(STORAGE_ENV_VARS, map(str, (
            self.profiles, self.assessments, self.companies_db, self.auth_db, self.goals_db, self.resume_builder_db,
        ))))


def create_test_storage(parent=None):
    """Keep unique test artifacts in temporary storage; do not clean old files."""
    root = Path(tempfile.mkdtemp(prefix="placepro_tests_", dir=parent)).resolve()
    if root.is_relative_to(PROJECT_ROOT / "data"):
        raise ValueError("Test storage must be outside the project's data directory.")
    profiles = root / "profiles"
    assessments = root / "assessments"
    profiles.mkdir()
    assessments.mkdir()
    return TestStorage(root, profiles, assessments, root / "companies.db", root / "accounts.sqlite3",
                       root / "goals.sqlite3", root / "resume-builder.sqlite3")


def stop_owned_process(process, server_pid=None):
    """Stop this Popen launcher and its verified server; never enumerate/kill peers.

    server_pid must come from this test's run-ID-verified wrapper or own child
    stdout. Windows venv launchers may have a different PID from their server.
    """
    if sys.platform == "win32" and server_pid and server_pid != process.pid:
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel.TerminateProcess.restype = wintypes.BOOL
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        handle = kernel.OpenProcess(0x00100001, False, server_pid)  # SYNCHRONIZE | TERMINATE only.
        if handle:
            try:
                if kernel.WaitForSingleObject(handle, 0) != 0:
                    if not kernel.TerminateProcess(handle, 1):
                        raise RuntimeError("Could not stop the verified test server.")
                    if kernel.WaitForSingleObject(handle, 5000) != 0:
                        raise RuntimeError("Verified test server did not stop.")
            finally:
                kernel.CloseHandle(handle)
        elif ctypes.get_last_error() != 87:  # PID no longer exists.
            raise RuntimeError("Could not access the verified test server process.")
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def _http_request(request, timeout=60):
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, {"detail": body}
    except urllib.error.URLError as exc:
        raise AssertionError(f"Server not reachable: {exc.reason}") from exc


def http_get(url):
    return _http_request(url, timeout=30)


def _http_json(method, url, payload):
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method=method,
    )
    return _http_request(request)


def http_post_json(url, payload):
    return _http_json("POST", url, payload)


def http_put_json(url, payload):
    return _http_json("PUT", url, payload)


def multipart_post(url, field_name, filename, content, content_type):
    boundary = "----PlaceProBoundary" + uuid.uuid4().hex
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field_name}"; '
        f'filename="{filename}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
    request = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    return _http_request(request)
