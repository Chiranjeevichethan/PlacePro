"""Additive metadata tables in the account DB. Existing account rows are untouched."""
from contextlib import contextmanager

from .account_store import AccountStore, AccountStorageError

SESSION_COLUMNS = ('session_id', 'family_id', 'account_id', 'secret_hash', 'csrf_nonce', 'context',
                   'auth_version', 'password_changed_at', 'created_at', 'last_activity_at',
                   'idle_expires_at', 'absolute_expires_at', 'revoked_at', 'revocation_reason')
CHALLENGE_COLUMNS = ('secret_hash', 'csrf_nonce', 'context', 'created_at', 'expires_at', 'attempts', 'consumed_at')
DDL = (
    '''CREATE TABLE sessions (
        session_id TEXT PRIMARY KEY NOT NULL, family_id TEXT NOT NULL,
        account_id TEXT NOT NULL REFERENCES accounts(account_id),
        secret_hash TEXT NOT NULL UNIQUE, csrf_nonce TEXT NOT NULL, context TEXT NOT NULL,
        auth_version INTEGER NOT NULL, password_changed_at TEXT NOT NULL,
        created_at REAL NOT NULL, last_activity_at REAL NOT NULL,
        idle_expires_at REAL NOT NULL, absolute_expires_at REAL NOT NULL,
        revoked_at REAL, revocation_reason TEXT,
        CHECK(idle_expires_at <= absolute_expires_at))''',
    'CREATE INDEX sessions_account ON sessions(account_id)',
    'CREATE INDEX sessions_family ON sessions(family_id)',
    '''CREATE TABLE login_challenges (
        secret_hash TEXT PRIMARY KEY NOT NULL, csrf_nonce TEXT NOT NULL, context TEXT NOT NULL,
        created_at REAL NOT NULL, expires_at REAL NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
        consumed_at REAL)''',
)


class InvalidSession(Exception):
    pass


class SessionExpired(InvalidSession):
    def __init__(self, session_id, now):
        self.session_id, self.now = session_id, now


class SessionStore:
    def __init__(self, accounts: AccountStore):
        self.accounts = accounts

    @contextmanager
    def transaction(self, *, write=False):
        if not write and not self.accounts.path.exists():
            yield None
            return
        with self.accounts._connection() as connection:
            connection.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
            names = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            expected = {'sessions', 'login_challenges'}
            if not expected.intersection(names):
                if not write:
                    yield None
                    return
                for ddl in DDL:
                    connection.execute(ddl)
            elif not expected <= names:
                raise AccountStorageError()
            for table, columns in (('sessions', SESSION_COLUMNS), ('login_challenges', CHALLENGE_COLUMNS)):
                if tuple(r[1] for r in connection.execute(f'PRAGMA table_info({table})')) != columns:
                    raise AccountStorageError()
            try:
                yield connection
            except SessionExpired as expired:
                # Terminal authentication expiry, never a student lifecycle mutation.
                connection.execute("UPDATE sessions SET revoked_at=?,revocation_reason='EXPIRED' "
                                   'WHERE session_id=? AND revoked_at IS NULL AND (idle_expires_at<=? OR absolute_expires_at<=?)',
                                   (expired.now,expired.session_id,expired.now,expired.now))
                connection.commit()
                raise
            connection.commit()

    @staticmethod
    def session(connection, digest, context):
        if connection is None:
            return None
        row = connection.execute('SELECT * FROM sessions WHERE secret_hash=? AND context=?', (digest, context)).fetchone()
        return dict(row) if row else None

    @staticmethod
    def account(connection, account_id):
        row = connection.execute('SELECT * FROM accounts WHERE account_id=?', (account_id,)).fetchone()
        return dict(row) if row else None

    @staticmethod
    def insert_session(connection, row):
        connection.execute('INSERT INTO sessions VALUES (' + ','.join('?' for _ in SESSION_COLUMNS) + ')',
                           tuple(row[c] for c in SESSION_COLUMNS))
