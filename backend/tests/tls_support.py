"""Portable trusted OpenSSL prerequisite for actual HTTPS regression tests."""
import os
from pathlib import Path
import shutil
import sys


def openssl_executable():
    configured = os.environ.get("PLACEPRO_TEST_OPENSSL")
    if configured:
        path = Path(configured)
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
        raise RuntimeError("PLACEPRO_TEST_OPENSSL must identify an available trusted executable.")
    found = shutil.which("openssl")
    if found:
        return found
    if sys.platform == "win32":
        program_files = os.environ.get("ProgramFiles")
        if program_files:
            path = Path(program_files) / "Git" / "usr" / "bin" / "openssl.exe"
            if path.is_file():
                return str(path)
    raise RuntimeError("TLS regression requires trusted OpenSSL on PATH or PLACEPRO_TEST_OPENSSL.")
