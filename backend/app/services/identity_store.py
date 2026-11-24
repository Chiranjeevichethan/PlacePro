"""Additive identity metadata in the dedicated account database.

Three tables are created lazily on first use: account provenance (how an
account was provisioned), external provider links and single-use OAuth
challenges. Account rows, the account schema version and the session tables
are never altered or migrated.
"""
from contextlib import contextmanager
from datetime import datetime, timezone

from .account_store import AccountStore, AccountStorageError
from .session_service import digest

ORIGINS = ('GOOGLE', 'LOCAL_DEVELOPMENT')
ORIGIN_COLUMNS = ('account_id', 'origin', 'recorded_at')
LINK_COLUMNS = ('provider', 'subject', 'account_id', 'linked_at')
CHALLENGE_COLUMNS = ('state_hash', 'nonce', 'code_verifier', 'context',
                     'created_at', 'expires_at', 'consumed_at')
DDL = (
    '''CREATE TABLE account_origins (
        account_id TEXT PRIMARY KEY NOT NULL REFERENCES accounts(account_id),
        origin TEXT NOT NULL CHECK(origin IN ('GOOGLE','LOCAL_DEVELOPMENT')),
        recorded_at TEXT NOT NULL)''',
    '''CREATE TABLE oauth_identities (
        provider TEXT NOT NULL, subject TEXT NOT NULL,
        account_id TEXT NOT NULL REFERENCES accounts(account_id),
        linked_at TEXT NOT NULL, PRIMARY KEY(provider, subject),
        UNIQUE(account_id, provider))''',
    '''CREATE TABLE oauth_challenges (
        state_hash TEXT PRIMARY KEY NOT NULL, nonce TEXT NOT NULL,
        code_verifier TEXT NOT NULL, context TEXT NOT NULL,
        created_at REAL NOT NULL, expires_at REAL NOT NULL, consumed_at REAL)''',
)
TABLES = {
    'account_origins': ORIGIN_COLUMNS,
    'oauth_identities': LINK_COLUMNS,
    'oauth_challenges': CHALLENGE_COLUMNS,
}


def _now():
    return datetime.now(timezone.utc).isoformat()


class IdentityStore:
    def __init__(self, accounts: AccountStore):
        self.accounts = accounts

    @contextmanager
    def transaction(self, *, write=False):
        if not write and not self.accounts.path.exists():
            yield None
            return
        with self.accounts._connection() as connection:
            connection.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
            names = {row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            expected = set(TABLES)
            if not expected.intersection(names):
                if not write:
                    yield None
                    return
                for statement in DDL:
                    connection.execute(statement)
            elif not expected <= names:
                raise AccountStorageError()
            for table, columns in TABLES.items():
                if tuple(row[1] for row in connection.execute(f'PRAGMA table_info({table})')) != columns:
                    raise AccountStorageError()
            try:
                yield connection
            except Exception:
                if connection is not None:
                    connection.rollback()
                raise
            else:
                connection.commit()

    def record_origin(self, account_id: str, origin: str) -> bool:
        """Record provenance once; never overwrite an existing origin."""
        if origin not in ORIGINS:
            raise ValueError('Unsupported account origin.')
        with self.transaction(write=True) as connection:
            cursor = connection.execute(
                'INSERT INTO account_origins VALUES (?,?,?) ON CONFLICT(account_id) DO NOTHING',
                (account_id, origin, _now()))
            return cursor.rowcount == 1

    def origin(self, account_id: str) -> str | None:
        with self.transaction() as connection:
            if connection is None:
                return None
            row = connection.execute('SELECT origin FROM account_origins WHERE account_id=?',
                                     (account_id,)).fetchone()
            return row['origin'] if row else None

    def link(self, provider: str, subject: str, account_id: str) -> bool:
        """Bind an external subject to one account; duplicates are not replaced."""
        with self.transaction(write=True) as connection:
            cursor = connection.execute(
                'INSERT INTO oauth_identities VALUES (?,?,?,?) ON CONFLICT DO NOTHING',
                (provider, subject, account_id, _now()))
            return cursor.rowcount == 1

    def linked_account(self, provider: str, subject: str) -> str | None:
        with self.transaction() as connection:
            if connection is None:
                return None
            row = connection.execute(
                'SELECT account_id FROM oauth_identities WHERE provider=? AND subject=?',
                (provider, subject)).fetchone()
            return row['account_id'] if row else None

    def account_providers(self, account_id: str) -> list[str]:
        with self.transaction() as connection:
            if connection is None:
                return []
            return [row['provider'] for row in connection.execute(
                'SELECT provider FROM oauth_identities WHERE account_id=? ORDER BY provider',
                (account_id,))]

    def create_challenge(self, state: str, nonce: str, verifier: str, context: str, *,
                         now: float, ttl: int) -> None:
        with self.transaction(write=True) as connection:
            # Only expired anonymous challenges are removed, never account data.
            connection.execute('DELETE FROM oauth_challenges WHERE expires_at <= ?', (now,))
            connection.execute('INSERT INTO oauth_challenges VALUES (?,?,?,?,?,?,NULL)',
                               (digest(state), nonce, verifier, context, now, now + ttl))

    def consume_challenge(self, state: str, context: str, *, now: float):
        """Single-use state/nonce lookup; expired or replayed state returns None."""
        with self.transaction(write=True) as connection:
            identifier = digest(state)
            row = connection.execute(
                'SELECT * FROM oauth_challenges WHERE state_hash=? AND context=?',
                (identifier, context)).fetchone()
            if not row or row['consumed_at'] is not None or now >= row['expires_at']:
                return None
            connection.execute(
                'UPDATE oauth_challenges SET consumed_at=? WHERE state_hash=? AND consumed_at IS NULL',
                (now, identifier))
            return dict(row)
