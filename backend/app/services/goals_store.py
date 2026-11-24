"""Separate, additive SQLite persistence for authenticated student goals."""
from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3

from .account_store import DEFAULT_AUTH_DB

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_GOALS_DB = PROJECT_ROOT / 'data' / 'goals' / 'goals.sqlite3'
APPLICATION_ID = 0x5050474C  # PPGL, distinct from account and company stores.
SCHEMA_VERSION = 2
LEGACY_SCHEMA_VERSION = 1
TABLES = {
    'goal_profiles': ('profile_id', 'account_id', 'created_at'),
    'goals': ('goal_id', 'profile_id', 'account_id', 'title', 'description', 'category',
              'target_date', 'priority', 'status', 'related_module', 'created_at', 'updated_at', 'completed_at'),
    'milestones': ('milestone_id', 'goal_id', 'profile_id', 'account_id', 'title', 'description',
                   'target_date', 'status', 'created_at', 'updated_at', 'completed_at'),
    'notifications': ('notification_id', 'profile_id', 'account_id', 'goal_id', 'milestone_id', 'event_key',
                      'kind', 'title', 'message', 'relevant_date', 'created_at', 'read_at'),
}

LEGACY_TABLES = {name: columns for name, columns in TABLES.items() if name != 'notifications'}

SCHEMA = '''
CREATE TABLE goal_profiles (
 profile_id TEXT PRIMARY KEY NOT NULL CHECK(length(profile_id)=36),
 account_id TEXT NOT NULL CHECK(length(account_id)=36),
 created_at TEXT NOT NULL,
 UNIQUE(profile_id,account_id)
);
CREATE TABLE goals (
 goal_id TEXT PRIMARY KEY NOT NULL CHECK(length(goal_id)=36),
 profile_id TEXT NOT NULL,
 account_id TEXT NOT NULL,
 title TEXT NOT NULL CHECK(length(trim(title)) BETWEEN 1 AND 120),
 description TEXT NOT NULL DEFAULT '' CHECK(length(description)<=2000),
 category TEXT NOT NULL CHECK(category IN ('skill','preparation','mock_test','profile','opportunity','weekly_target','other')),
 target_date TEXT CHECK(target_date IS NULL OR (length(target_date)=10 AND date(target_date) IS NOT NULL)),
 priority TEXT NOT NULL CHECK(priority IN ('high','medium','low')),
 status TEXT NOT NULL CHECK(status IN ('active','paused','completed')),
 related_module TEXT CHECK(related_module IS NULL OR related_module IN ('readiness','skillgap','mocktests','performance','profile','companies','prediction')),
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 completed_at TEXT,
 UNIQUE(goal_id,profile_id,account_id),
 FOREIGN KEY(profile_id,account_id) REFERENCES goal_profiles(profile_id,account_id) ON DELETE CASCADE,
 CHECK((status='completed' AND completed_at IS NOT NULL) OR (status!='completed' AND completed_at IS NULL))
);
CREATE INDEX goals_owner_status ON goals(account_id,profile_id,status,updated_at);
CREATE TABLE milestones (
 milestone_id TEXT PRIMARY KEY NOT NULL CHECK(length(milestone_id)=36),
 goal_id TEXT NOT NULL,
 profile_id TEXT NOT NULL,
 account_id TEXT NOT NULL,
 title TEXT NOT NULL CHECK(length(trim(title)) BETWEEN 1 AND 120),
 description TEXT NOT NULL DEFAULT '' CHECK(length(description)<=1000),
 target_date TEXT CHECK(target_date IS NULL OR (length(target_date)=10 AND date(target_date) IS NOT NULL)),
 status TEXT NOT NULL CHECK(status IN ('pending','completed')),
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 completed_at TEXT,
 FOREIGN KEY(goal_id,profile_id,account_id) REFERENCES goals(goal_id,profile_id,account_id) ON DELETE CASCADE,
 CHECK((status='completed' AND completed_at IS NOT NULL) OR (status!='completed' AND completed_at IS NULL))
);
CREATE INDEX milestones_goal_status_date ON milestones(goal_id,status,target_date);
CREATE UNIQUE INDEX milestones_owner_link ON milestones(milestone_id,goal_id,profile_id,account_id);
CREATE TABLE notifications (
 notification_id TEXT PRIMARY KEY NOT NULL CHECK(length(notification_id)=36),
 profile_id TEXT NOT NULL,
 account_id TEXT NOT NULL,
 goal_id TEXT NOT NULL,
 milestone_id TEXT,
 event_key TEXT NOT NULL CHECK(length(event_key)<=180),
 kind TEXT NOT NULL CHECK(kind IN ('milestone_upcoming','milestone_due_today','milestone_overdue',
                                  'goal_upcoming','goal_due_today','goal_overdue','milestone_completed','goal_completed')),
 title TEXT NOT NULL CHECK(length(title) BETWEEN 1 AND 120),
 message TEXT NOT NULL CHECK(length(message)<=500),
 relevant_date TEXT CHECK(relevant_date IS NULL OR (length(relevant_date)=10 AND date(relevant_date) IS NOT NULL)),
 created_at TEXT NOT NULL,
 read_at TEXT,
 UNIQUE(event_key,profile_id,account_id),
 FOREIGN KEY(goal_id,profile_id,account_id) REFERENCES goals(goal_id,profile_id,account_id) ON DELETE CASCADE,
 FOREIGN KEY(milestone_id,goal_id,profile_id,account_id)
   REFERENCES milestones(milestone_id,goal_id,profile_id,account_id) ON DELETE CASCADE
);
CREATE INDEX notifications_owner_recent ON notifications(account_id,profile_id,created_at DESC,notification_id);
CREATE INDEX notifications_owner_unread ON notifications(account_id,profile_id,read_at,created_at DESC);
CREATE TRIGGER goal_completed_requires_milestones BEFORE UPDATE OF status ON goals
WHEN NEW.status='completed' AND OLD.status!='completed'
 AND EXISTS(SELECT 1 FROM milestones WHERE goal_id=OLD.goal_id AND status!='completed')
BEGIN SELECT RAISE(ABORT,'Complete every milestone before completing this goal.'); END;
CREATE TRIGGER milestone_insert_requires_open_goal BEFORE INSERT ON milestones
WHEN (SELECT status FROM goals WHERE goal_id=NEW.goal_id)='completed'
BEGIN SELECT RAISE(ABORT,'Reopen the goal before adding a milestone.'); END;
CREATE TRIGGER completed_goal_milestones_stay_complete BEFORE UPDATE OF status ON milestones
WHEN NEW.status!='completed' AND (SELECT status FROM goals WHERE goal_id=OLD.goal_id)='completed'
BEGIN SELECT RAISE(ABORT,'Reopen the goal before reopening a milestone.'); END;
'''


class GoalStorageUnavailable(Exception):
    pass


def _database_path():
    path = Path(os.environ.get('PLACEPRO_GOALS_DB') or DEFAULT_GOALS_DB).resolve()
    protected = {Path(DEFAULT_AUTH_DB).resolve()}
    if os.environ.get('PLACEPRO_AUTH_DB'):
        protected.add(Path(os.environ['PLACEPRO_AUTH_DB']).resolve())
    companies = PROJECT_ROOT / 'data' / 'companies.db'
    protected.add(companies.resolve())
    if os.environ.get('PLACEPRO_COMPANIES_DB'):
        protected.add(Path(os.environ['PLACEPRO_COMPANIES_DB']).resolve())
    if path in protected or path.suffix.lower() not in {'.db', '.sqlite', '.sqlite3'}:
        raise GoalStorageUnavailable()
    return path


class GoalsStore:
    def __init__(self, path=None):
        self.path = Path(path or _database_path()).resolve()
        if self.path.suffix.lower() not in {'.db', '.sqlite', '.sqlite3'}:
            raise GoalStorageUnavailable()

    @contextmanager
    def transaction(self):
        connection = None
        try:
            if self.path.is_symlink():
                raise GoalStorageUnavailable()
            self.path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self.path, timeout=5, isolation_level=None)
            connection.row_factory = sqlite3.Row
            connection.execute('PRAGMA foreign_keys=ON')
            connection.execute('BEGIN IMMEDIATE')
            app_id = connection.execute('PRAGMA application_id').fetchone()[0]
            version = connection.execute('PRAGMA user_version').fetchone()[0]
            names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if app_id == 0 and version == 0 and not names:
                statement = ''
                for line in SCHEMA.splitlines(keepends=True):
                    statement += line
                    if sqlite3.complete_statement(statement):
                        connection.execute(statement)
                        statement = ''
                if statement.strip():
                    raise GoalStorageUnavailable()
                connection.execute(f'PRAGMA application_id={APPLICATION_ID}')
                connection.execute(f'PRAGMA user_version={SCHEMA_VERSION}')
            elif app_id == APPLICATION_ID and version == LEGACY_SCHEMA_VERSION:
                self._validate_schema(connection, LEGACY_TABLES,
                                      {'goal_completed_requires_milestones', 'milestone_insert_requires_open_goal',
                                       'completed_goal_milestones_stay_complete'})
                connection.execute('CREATE UNIQUE INDEX milestones_owner_link ON milestones(milestone_id,goal_id,profile_id,account_id)')
                connection.execute('''CREATE TABLE notifications (
                    notification_id TEXT PRIMARY KEY NOT NULL CHECK(length(notification_id)=36),
                    profile_id TEXT NOT NULL, account_id TEXT NOT NULL, goal_id TEXT NOT NULL, milestone_id TEXT,
                    event_key TEXT NOT NULL CHECK(length(event_key)<=180),
                    kind TEXT NOT NULL CHECK(kind IN ('milestone_upcoming','milestone_due_today','milestone_overdue',
                      'goal_upcoming','goal_due_today','goal_overdue','milestone_completed','goal_completed')),
                    title TEXT NOT NULL CHECK(length(title) BETWEEN 1 AND 120),
                    message TEXT NOT NULL CHECK(length(message)<=500),
                    relevant_date TEXT CHECK(relevant_date IS NULL OR (length(relevant_date)=10 AND date(relevant_date) IS NOT NULL)),
                    created_at TEXT NOT NULL, read_at TEXT,
                    UNIQUE(event_key,profile_id,account_id),
                    FOREIGN KEY(goal_id,profile_id,account_id) REFERENCES goals(goal_id,profile_id,account_id) ON DELETE CASCADE,
                    FOREIGN KEY(milestone_id,goal_id,profile_id,account_id)
                      REFERENCES milestones(milestone_id,goal_id,profile_id,account_id) ON DELETE CASCADE
                )''')
                connection.execute('CREATE INDEX notifications_owner_recent ON notifications(account_id,profile_id,created_at DESC,notification_id)')
                connection.execute('CREATE INDEX notifications_owner_unread ON notifications(account_id,profile_id,read_at,created_at DESC)')
                connection.execute(f'PRAGMA user_version={SCHEMA_VERSION}')
            elif app_id != APPLICATION_ID or version != SCHEMA_VERSION:
                raise GoalStorageUnavailable()
            self._validate(connection)
            yield connection
            connection.commit()
        except GoalStorageUnavailable:
            raise
        except (sqlite3.Error, OSError):
            raise GoalStorageUnavailable() from None
        finally:
            if connection is not None:
                if connection.in_transaction:
                    connection.rollback()
                connection.close()

    @staticmethod
    def _validate(connection):
        GoalsStore._validate_schema(connection, TABLES,
                                    {'goal_completed_requires_milestones', 'milestone_insert_requires_open_goal',
                                     'completed_goal_milestones_stay_complete'})

    @staticmethod
    def _validate_schema(connection, expected_tables, expected_triggers):
        names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if names != set(expected_tables):
            raise GoalStorageUnavailable()
        for name, expected in expected_tables.items():
            actual = tuple(row[1] for row in connection.execute(f'PRAGMA table_info({name})'))
            if actual != expected:
                raise GoalStorageUnavailable()
        if connection.execute('PRAGMA foreign_key_check').fetchone() is not None:
            raise GoalStorageUnavailable()
        triggers = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
        if triggers != expected_triggers:
            raise GoalStorageUnavailable()
