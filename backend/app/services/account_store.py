"""Dedicated SQLite account records. No student/profile/history association."""
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
import uuid

from .account_validation import normalize_account_email

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_AUTH_DB = PROJECT_ROOT / "data" / "auth" / "accounts.sqlite3"
_APPLICATION_ID = 0x50504155  # PPAU, distinct from the company database.
_SCHEMA_VERSION = 1
_SCHEMA = """
CREATE TABLE accounts (
    account_id TEXT PRIMARY KEY NOT NULL,
    email_normalized TEXT NOT NULL UNIQUE CHECK(email_normalized = lower(email_normalized)),
    password_hash TEXT NOT NULL CHECK(password_hash LIKE '$argon2id$%'),
    status TEXT NOT NULL CHECK(status IN ('PENDING_EMAIL','ACTIVE','DISABLED','DEACTIVATED')),
    email_verified_at TEXT,
    auth_version INTEGER NOT NULL DEFAULT 1 CHECK(auth_version >= 1),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    password_changed_at TEXT NOT NULL,
    CHECK(status != 'ACTIVE' OR email_verified_at IS NOT NULL)
)
"""


class AccountStorageError(Exception):
    def __init__(self):
        super().__init__("Account storage is temporarily unavailable.")


@dataclass(frozen=True, repr=False)
class Account:
    account_id: str
    email_normalized: str = field(repr=False)
    password_hash: str = field(repr=False)
    status: str
    email_verified_at: str | None
    auth_version: int
    created_at: str
    updated_at: str
    password_changed_at: str


def _now():
    return datetime.now(timezone.utc).isoformat()


class AccountStore:
    def __init__(self, path=None):
        self.path = Path(path or os.environ.get("PLACEPRO_AUTH_DB") or DEFAULT_AUTH_DB).resolve()
        company_paths = {PROJECT_ROOT / "data" / "companies.db"}
        if os.environ.get("PLACEPRO_COMPANIES_DB"):
            company_paths.add(Path(os.environ["PLACEPRO_COMPANIES_DB"]).resolve())
        if self.path in company_paths or self.path.suffix.lower() not in {".db", ".sqlite", ".sqlite3"}:
            raise AccountStorageError()
        # Construction/import performs no filesystem writes.

    @contextmanager
    def _connection(self):
        connection = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self.path, timeout=5, isolation_level=None)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("BEGIN IMMEDIATE")
            application_id = connection.execute("PRAGMA application_id").fetchone()[0]
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            tables = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            if application_id == 0 and version == 0 and not tables:
                connection.execute(_SCHEMA)
                connection.execute(f"PRAGMA application_id = {_APPLICATION_ID}")
                connection.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
            elif application_id != _APPLICATION_ID or version != _SCHEMA_VERSION:
                raise AccountStorageError()
            connection.commit()
            yield connection
        except (sqlite3.Error, OSError):
            raise AccountStorageError() from None
        finally:
            if connection is not None:
                if connection.in_transaction:
                    connection.rollback()
                connection.close()

    def create_account(self, email: str, password_hash: str) -> Account | None:
        email = normalize_account_email(email)
        if not isinstance(password_hash, str) or not password_hash.startswith("$argon2id$"):
            raise ValueError("A supported password hash is required.")
        account_id, now = str(uuid.uuid4()), _now()
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                "INSERT INTO accounts VALUES (?, ?, ?, 'PENDING_EMAIL', NULL, 1, ?, ?, ?) "
                "ON CONFLICT(email_normalized) DO NOTHING",
                (account_id, email, password_hash, now, now, now),
            )
            connection.commit()
            if cursor.rowcount == 0:
                return None
            row = connection.execute("SELECT * FROM accounts WHERE account_id = ?", (account_id,)).fetchone()
            return Account(**dict(row))

    def get_by_email(self, email: str) -> Account | None:
        email = normalize_account_email(email)
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM accounts WHERE email_normalized = ?", (email,)).fetchone()
            return Account(**dict(row)) if row else None

    def get_by_id(self, account_id: str) -> Account | None:
        if not isinstance(account_id, str):
            return None
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM accounts WHERE account_id = ?", (account_id,)).fetchone()
            return Account(**dict(row)) if row else None

    def activate_pending(self, account_id: str) -> bool:
        """Activate a PENDING_EMAIL account once; never re-enable a terminal account."""
        now = _now()
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                "UPDATE accounts SET status = 'ACTIVE', email_verified_at = ?, updated_at = ? "
                "WHERE account_id = ? AND status = 'PENDING_EMAIL' AND email_verified_at IS NULL",
                (now, now, account_id),
            )
            connection.commit()
            return cursor.rowcount == 1

    def upgrade_hash(self, account: Account, replacement: str) -> bool:
        """CAS for same-password parameter upgrade; never changes auth_version/IDs."""
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                "UPDATE accounts SET password_hash = ?, updated_at = ? WHERE account_id = ? "
                "AND password_hash = ? AND auth_version = ? AND status = 'ACTIVE' "
                "AND email_verified_at IS NOT NULL",
                (replacement, _now(), account.account_id, account.password_hash, account.auth_version),
            )
            connection.commit()
            return cursor.rowcount == 1
