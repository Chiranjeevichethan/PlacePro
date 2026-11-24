"""Discovery never turns missing TLS prerequisites into skipped coverage."""
import pytest

from backend.tests import tls_support


def test_openssl_uses_portable_path_discovery(monkeypatch):
    monkeypatch.delenv("PLACEPRO_TEST_OPENSSL", raising=False)
    monkeypatch.setattr(tls_support.sys, "platform", "linux")
    monkeypatch.setattr(tls_support.shutil, "which", lambda name: "/usr/bin/openssl")
    assert tls_support.openssl_executable() == "/usr/bin/openssl"


def test_openssl_missing_on_linux_is_an_explicit_failure(monkeypatch):
    monkeypatch.delenv("PLACEPRO_TEST_OPENSSL", raising=False)
    monkeypatch.setattr(tls_support.sys, "platform", "linux")
    monkeypatch.setattr(tls_support.shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError, match="requires trusted OpenSSL"):
        tls_support.openssl_executable()


def test_invalid_openssl_override_does_not_silently_fall_back(monkeypatch, isolated_storage):
    monkeypatch.setenv("PLACEPRO_TEST_OPENSSL", str(isolated_storage.root / "missing-openssl"))
    monkeypatch.setattr(tls_support.shutil, "which", lambda name: "/usr/bin/openssl")
    with pytest.raises(RuntimeError, match="available trusted executable"):
        tls_support.openssl_executable()


def test_windows_git_fallback_uses_program_files(monkeypatch, isolated_storage):
    monkeypatch.delenv("PLACEPRO_TEST_OPENSSL", raising=False)
    monkeypatch.setattr(tls_support.sys, "platform", "win32")
    monkeypatch.setattr(tls_support.shutil, "which", lambda name: None)
    monkeypatch.setenv("ProgramFiles", str(isolated_storage.root))
    executable = isolated_storage.root / "Git" / "usr" / "bin" / "openssl.exe"
    executable.parent.mkdir(parents=True)
    executable.write_text("synthetic discovery fixture", encoding="utf-8")
    assert tls_support.openssl_executable() == str(executable)
