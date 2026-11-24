"""Small additive SQLite store for student-authored resume builder drafts."""
from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3

from .account_store import DEFAULT_AUTH_DB
from .goals_store import DEFAULT_GOALS_DB

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RESUME_BUILDER_DB = PROJECT_ROOT / 'data' / 'resume_builder' / 'resume_builder.sqlite3'
APPLICATION_ID = 0x50505242  # PPRB
SCHEMA_VERSION = 1
SCHEMA = '''
CREATE TABLE resume_drafts (
 profile_id TEXT PRIMARY KEY NOT NULL CHECK(length(profile_id)=36),
 account_id TEXT NOT NULL CHECK(length(account_id)=36),
 revision INTEGER NOT NULL CHECK(revision>0),
 document_json TEXT NOT NULL CHECK(length(document_json)<=1048576),
 updated_at TEXT NOT NULL,
 UNIQUE(profile_id,account_id)
);
CREATE INDEX resume_drafts_owner_updated ON resume_drafts(account_id,profile_id,updated_at);
'''


class ResumeDraftStorageUnavailable(Exception):
    pass


def _database_path():
    path = Path(os.environ.get('PLACEPRO_RESUME_BUILDER_DB') or DEFAULT_RESUME_BUILDER_DB).expanduser().absolute()
    protected = {Path(DEFAULT_AUTH_DB).resolve(), Path(DEFAULT_GOALS_DB).resolve(),
                 (PROJECT_ROOT / 'data' / 'companies.db').resolve()}
    for name in ('PLACEPRO_AUTH_DB', 'PLACEPRO_GOALS_DB', 'PLACEPRO_COMPANIES_DB'):
        if os.environ.get(name):
            protected.add(Path(os.environ[name]).resolve())
    if (path.is_symlink() or path.resolve() in protected
            or path.suffix.lower() not in {'.db', '.sqlite', '.sqlite3'}):
        raise ResumeDraftStorageUnavailable()
    return path


class ResumeBuilderStore:
    def __init__(self, path=None):
        self.path = Path(path or _database_path()).expanduser().absolute()
        if self.path.suffix.lower() not in {'.db', '.sqlite', '.sqlite3'}:
            raise ResumeDraftStorageUnavailable()

    @contextmanager
    def transaction(self):
        connection = None
        try:
            if self.path.is_symlink():
                raise ResumeDraftStorageUnavailable()
            self.path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self.path, timeout=5, isolation_level=None)
            connection.row_factory = sqlite3.Row
            connection.execute('BEGIN IMMEDIATE')
            app_id = connection.execute('PRAGMA application_id').fetchone()[0]
            version = connection.execute('PRAGMA user_version').fetchone()[0]
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if app_id == 0 and version == 0 and not tables:
                statement = ''
                for line in SCHEMA.splitlines(keepends=True):
                    statement += line
                    if sqlite3.complete_statement(statement):
                        connection.execute(statement)
                        statement = ''
                if statement.strip():
                    raise ResumeDraftStorageUnavailable()
                connection.execute(f'PRAGMA application_id={APPLICATION_ID}')
                connection.execute(f'PRAGMA user_version={SCHEMA_VERSION}')
            elif app_id != APPLICATION_ID or version != SCHEMA_VERSION:
                raise ResumeDraftStorageUnavailable()
            self._validate(connection)
            yield connection
            connection.commit()
        except ResumeDraftStorageUnavailable:
            raise
        except (sqlite3.Error, OSError):
            raise ResumeDraftStorageUnavailable() from None
        finally:
            if connection is not None:
                if connection.in_transaction:
                    connection.rollback()
                connection.close()

    @staticmethod
    def _validate(connection):
        names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if names != {'resume_drafts'}:
            raise ResumeDraftStorageUnavailable()
        columns = tuple(row[1] for row in connection.execute('PRAGMA table_info(resume_drafts)'))
        if columns != ('profile_id', 'account_id', 'revision', 'document_json', 'updated_at'):
            raise ResumeDraftStorageUnavailable()

    def get(self, identity, profile_id):
        if not self.path.exists():
            return None
        with self.transaction() as connection:
            row = connection.execute('SELECT revision,document_json,updated_at FROM resume_drafts '
                                     'WHERE profile_id=? AND account_id=?',
                                     (profile_id, identity.account_id)).fetchone()
            return dict(row) if row else None

    def save(self, identity, profile_id, expected_revision, document_json, now):
        with self.transaction() as connection:
            row = connection.execute('SELECT revision FROM resume_drafts WHERE profile_id=? AND account_id=?',
                                     (profile_id, identity.account_id)).fetchone()
            current_revision = row['revision'] if row else 0
            if current_revision != expected_revision:
                return None
            revision = current_revision + 1
            connection.execute('INSERT INTO resume_drafts(profile_id,account_id,revision,document_json,updated_at) '
                               'VALUES(?,?,?,?,?) ON CONFLICT(profile_id) DO UPDATE SET '
                               'revision=excluded.revision,document_json=excluded.document_json,updated_at=excluded.updated_at '
                               'WHERE resume_drafts.account_id=excluded.account_id',
                               (profile_id, identity.account_id, revision, document_json, now))
            saved = connection.execute('SELECT revision,document_json,updated_at FROM resume_drafts '
                                       'WHERE profile_id=? AND account_id=?',
                                       (profile_id, identity.account_id)).fetchone()
            if not saved or saved['revision'] != revision:
                raise ResumeDraftStorageUnavailable()
            return dict(saved)
