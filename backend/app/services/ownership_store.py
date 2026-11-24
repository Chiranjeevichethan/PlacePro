"""Authoritative additive ownership metadata; never infer an owner from profile JSON."""
from contextlib import contextmanager
from datetime import datetime,timezone
import re
import sqlite3
import uuid

from .account_store import AccountStorageError

COLUMNS=('profile_id','account_id','status','association_version','created_at','updated_at','creation_sha256')
DDL='''CREATE TABLE profile_ownership (
 profile_id TEXT PRIMARY KEY NOT NULL CHECK(length(profile_id)=36 AND profile_id=lower(profile_id)),
 account_id TEXT NOT NULL REFERENCES accounts(account_id),
 status TEXT NOT NULL CHECK(status IN ('PENDING','ACTIVE','FAILED','SUSPENDED')),
 association_version INTEGER NOT NULL DEFAULT 1 CHECK(association_version>=1),
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 creation_sha256 TEXT NOT NULL CHECK(length(creation_sha256)=64)
)'''
IMMUTABLE='''CREATE TRIGGER profile_ownership_immutable BEFORE UPDATE ON profile_ownership
WHEN NEW.profile_id IS NOT OLD.profile_id OR NEW.account_id IS NOT OLD.account_id
 OR NEW.created_at IS NOT OLD.created_at OR NEW.creation_sha256 IS NOT OLD.creation_sha256
BEGIN SELECT RAISE(ABORT,'Immutable ownership identity'); END'''


class OwnershipUnavailable(Exception):
    pass


class OwnershipCorrupt(OwnershipUnavailable):
    """Ownership schema cannot safely establish permission."""


class OwnershipNotFound(Exception):
    pass


class OwnershipConflict(Exception):
    pass


def canonical_id(value):
    if not isinstance(value,str):
        return False
    try:
        parsed=uuid.UUID(value)
        return parsed.version==4 and str(parsed)==value
    except ValueError:
        return False


def valid_row(row):
    try:
        return (canonical_id(row['profile_id']) and canonical_id(row['account_id'])
                and row['status'] in {'PENDING','ACTIVE','FAILED','SUSPENDED'}
                and type(row['association_version']) is int and row['association_version']>=1
                and re.fullmatch('[0-9a-f]{64}',row['creation_sha256']) is not None
                and all(datetime.fromisoformat(row[k]).utcoffset().total_seconds()==0 for k in ('created_at','updated_at')))
    except (KeyError,TypeError,ValueError,AttributeError):
        return False


class OwnershipStore:
    def __init__(self,sessions):
        self.sessions=sessions

    @contextmanager
    def transaction(self, *, write=False):
        try:
            with self.sessions.store.transaction(write=write) as connection:
                if connection is None:
                    yield None
                    return
                exists=connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='profile_ownership'").fetchone()
                if not exists:
                    if not write:
                        yield None
                        return
                    connection.execute(DDL)
                    connection.execute('CREATE INDEX profile_ownership_account ON profile_ownership(account_id,status)')
                    connection.execute(IMMUTABLE)
                table=connection.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='profile_ownership'").fetchone()
                if (' '.join(table[0].split())!=' '.join(DDL.split())
                        or tuple(r[1] for r in connection.execute('PRAGMA table_info(profile_ownership)'))!=COLUMNS):
                    raise OwnershipCorrupt()
                trigger=connection.execute("SELECT sql FROM sqlite_master WHERE type='trigger' AND name='profile_ownership_immutable'").fetchone()
                if not trigger or ' '.join(trigger[0].split())!=' '.join(IMMUTABLE.split()):
                    raise OwnershipCorrupt()
                foreign=connection.execute('PRAGMA foreign_key_list(profile_ownership)').fetchall()
                if not any(r[2]=='accounts' and r[3]=='account_id' and r[4]=='account_id' for r in foreign):
                    raise OwnershipCorrupt()
                yield connection
        except AccountStorageError:
            raise OwnershipUnavailable() from None

    def _owned(self,connection,identity,profile_id):
        self.sessions.validate_identity(connection,identity)
        row=connection.execute('SELECT * FROM profile_ownership WHERE profile_id=? AND account_id=? AND status=\'ACTIVE\'',
                               (profile_id,identity.account_id)).fetchone()
        if not row or not valid_row(row):
            raise OwnershipNotFound()
        return dict(row)

    def authorize(self,identity,profile_id, *, acceptance=False, unavailable_as_not_found=True):
        if not canonical_id(profile_id):
            raise OwnershipNotFound()
        try:
            with self.transaction(write=acceptance) as connection:
                if connection is None:
                    raise OwnershipNotFound()
                return self._owned(connection,identity,profile_id)
        except OwnershipCorrupt:
            raise OwnershipNotFound() from None
        except OwnershipUnavailable:
            if unavailable_as_not_found:
                raise OwnershipNotFound() from None
            raise

    def list_owned(self,identity):
        with self.transaction() as connection:
            if connection is not None:
                self.sessions.validate_identity(connection,identity)
                rows=connection.execute("SELECT * FROM profile_ownership WHERE account_id=? AND status='ACTIVE' ORDER BY created_at,profile_id",
                                        (identity.account_id,)).fetchall()
                if any(not valid_row(r) for r in rows):
                    raise OwnershipUnavailable()
                return [dict(r) for r in rows]
        # Close the schema-read transaction before opening another connection.
        # AccountStore checks its schema under BEGIN IMMEDIATE even for reads.
        with self.sessions.store.transaction() as connection:
            self.sessions.validate_identity(connection,identity)
        return []

    def reserve(self,identity,profile_id,content_hash):
        if not canonical_id(profile_id) or not re.fullmatch('[0-9a-f]{64}',content_hash):
            raise OwnershipConflict()
        now=datetime.fromtimestamp(self.sessions.clock(),timezone.utc).isoformat()
        try:
            with self.transaction(write=True) as connection:
                self.sessions.validate_identity(connection,identity)
                if connection.execute('SELECT 1 FROM profile_ownership WHERE profile_id=?',(profile_id,)).fetchone():
                    raise OwnershipConflict()
                connection.execute("INSERT INTO profile_ownership VALUES (?,?,'PENDING',1,?,?,?)",
                                   (profile_id,identity.account_id,now,now,content_hash))
        except sqlite3.IntegrityError:
            raise OwnershipConflict() from None

    def activate(self,identity,profile_id,content_hash):
        now=datetime.fromtimestamp(self.sessions.clock(),timezone.utc).isoformat()
        with self.transaction(write=True) as connection:
            self.sessions.validate_identity(connection,identity)
            row=connection.execute('SELECT * FROM profile_ownership WHERE profile_id=?',(profile_id,)).fetchone()
            if (not row or not valid_row(row) or row['account_id']!=identity.account_id or row['status']!='PENDING'
                    or row['creation_sha256']!=content_hash):
                raise OwnershipConflict()
            connection.execute("UPDATE profile_ownership SET status='ACTIVE',association_version=association_version+1,updated_at=? WHERE profile_id=?",
                               (now,profile_id))
