"""Additive ownership integrity, using only synthetic temporary authentication stores."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import sqlite3
from threading import Barrier
import uuid

import pytest

from backend.app.services.ownership_store import (
    OwnershipStore, OwnershipConflict, OwnershipNotFound, OwnershipUnavailable,
)
from backend.app.services.session_service import InvalidSession
from backend.tests.test_profile_ownership import pair, encoded_password, identity


@pytest.fixture
def store(pair):
    app, a, b, _, _ = pair
    return app.state.owned_profiles.store, identity(app, a), identity(app, b)


def rows(store):
    with sqlite3.connect(store.sessions.store.accounts.path) as connection:
        return connection.execute('SELECT * FROM profile_ownership').fetchall()


def test_lazy_read_does_not_create_ownership_schema(store):
    owner, a, _ = store
    assert owner.list_owned(a) == []
    with pytest.raises(OwnershipNotFound):
        owner.authorize(a, str(uuid.uuid4()))
    with sqlite3.connect(owner.sessions.store.accounts.path) as connection:
        assert not connection.execute("SELECT 1 FROM sqlite_master WHERE name='profile_ownership'").fetchone()


def test_persistence_pending_isolation_multiple_owned_profiles_and_account_session_preservation(store):
    owner, a, b = store
    with owner.sessions.store.transaction() as connection:
        before = {table: [tuple(r) for r in connection.execute('SELECT * FROM '+table)]
                  for table in ('accounts', 'sessions', 'login_challenges')}
    ids = [str(uuid.uuid4()), str(uuid.uuid4())]
    for profile_id in ids:
        owner.reserve(a, profile_id, 'a'*64)
        with pytest.raises(OwnershipNotFound):
            owner.authorize(a, profile_id)
        assert owner.list_owned(a) == ([] if profile_id == ids[0] else [owner.authorize(a, ids[0])])
        owner.activate(a, profile_id, 'a'*64)
        assert owner.authorize(a, profile_id)['association_version'] == 2
        with pytest.raises(OwnershipNotFound):
            owner.authorize(b, profile_id)
    restarted = OwnershipStore(owner.sessions)
    assert {r['profile_id'] for r in restarted.list_owned(a)} == set(ids)
    assert restarted.list_owned(b) == []
    with owner.sessions.store.transaction() as connection:
        after = {table: [tuple(r) for r in connection.execute('SELECT * FROM '+table)] for table in before}
        assert connection.execute('PRAGMA foreign_keys').fetchone()[0] == 1
        assert connection.execute('PRAGMA user_version').fetchone()[0] == 1
        assert connection.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='profile_ownership_account'").fetchone()
    assert before == after


def test_database_foreign_key_unique_owner_and_immutable_identity_constraints(store):
    owner, a, b = store
    profile_id = str(uuid.uuid4())
    owner.reserve(a, profile_id, 'a'*64)
    before = rows(owner)
    with owner.transaction(write=True) as connection:
        for column, value in (('account_id', b.account_id), ('profile_id', str(uuid.uuid4())),
                              ('created_at', '2026-11-10T00:00:00+00:00'), ('creation_sha256', 'b'*64)):
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute('UPDATE profile_ownership SET '+column+'=?', (value,))
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute('INSERT INTO profile_ownership SELECT * FROM profile_ownership')
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO profile_ownership VALUES (?,?,'PENDING',1,?,?,?)",
                               (str(uuid.uuid4()), str(uuid.uuid4()), before[0][4], before[0][5], 'a'*64))
    assert rows(owner) == before


def test_two_accounts_racing_same_profile_have_only_one_reservation_and_no_transfer(store):
    owner, a, b = store
    profile_id = str(uuid.uuid4())
    barrier = Barrier(2)
    def reserve(ident):
        barrier.wait(timeout=10)
        try:
            owner.reserve(ident, profile_id, 'a'*64)
            return ident
        except OwnershipConflict:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(reserve, (a, b)))
    assert sum(r is not None for r in results) == 1
    winner = next(r for r in results if r is not None)
    loser = b if winner.account_id == a.account_id else a
    with pytest.raises(OwnershipConflict):
        owner.activate(loser, profile_id, 'a'*64)
    owner.activate(winner, profile_id, 'a'*64)
    assert rows(owner)[0][1] == winner.account_id and len(rows(owner)) == 1
    with pytest.raises(OwnershipConflict):
        owner.reserve(winner, profile_id, 'a'*64)
    with pytest.raises(OwnershipConflict):
        owner.activate(winner, profile_id, 'a'*64)


@pytest.mark.parametrize('action', ['reserve', 'activate'])
def test_commit_failure_rolls_back_ownership_changes(store, monkeypatch, action):
    from backend.app.services import account_store
    owner, a, _ = store
    profile_id = str(uuid.uuid4())
    # Initialize additive schema, then fail only the operation's final commit.
    owner.reserve(a, str(uuid.uuid4()), 'c'*64)
    if action == 'activate':
        owner.reserve(a, profile_id, 'a'*64)
    before = rows(owner)
    real_connect = sqlite3.connect
    class FailingCommit(sqlite3.Connection):
        commits = 0
        def commit(self):
            self.commits += 1
            if self.commits == 2:
                raise sqlite3.OperationalError('Synthetic commit failure')
            return super().commit()
    with monkeypatch.context() as patch:
        patch.setattr(account_store.sqlite3, 'connect',
                      lambda *args, **kw: real_connect(*args, **kw, factory=FailingCommit))
        with pytest.raises(OwnershipUnavailable):
            getattr(owner, action)(a, profile_id, 'a'*64)
    assert rows(owner) == before
    if action == 'activate':
        with pytest.raises(OwnershipNotFound):
            owner.authorize(a, profile_id)


def test_database_lock_is_fail_closed_without_modifying_ownership(store):
    owner, a, _ = store
    profile_id = str(uuid.uuid4())
    owner.reserve(a, profile_id, 'a'*64)
    owner.activate(a, profile_id, 'a'*64)
    before = rows(owner)
    with sqlite3.connect(owner.sessions.store.accounts.path, isolation_level=None) as lock:
        lock.execute('BEGIN IMMEDIATE')
        with pytest.raises(OwnershipUnavailable):
            owner.reserve(a, str(uuid.uuid4()), 'b'*64)
        with pytest.raises(OwnershipNotFound):
            owner.authorize(a, profile_id, acceptance=True)
        lock.rollback()
    assert rows(owner) == before


@pytest.mark.parametrize('change', ["status='DISABLED'", 'auth_version=auth_version+1',
                                   "password_changed_at='2026-11-10T00:00:00+00:00'"])
def test_account_changes_prevent_acceptance_of_previously_valid_identity(store, change):
    owner, a, _ = store
    profile_id = str(uuid.uuid4())
    owner.reserve(a, profile_id, 'a'*64)
    owner.activate(a, profile_id, 'a'*64)
    before = rows(owner)
    with sqlite3.connect(owner.sessions.store.accounts.path) as connection:
        connection.execute('UPDATE accounts SET '+change+' WHERE account_id=?', (a.account_id,))
    for action in (lambda: owner.authorize(a, profile_id), lambda: owner.list_owned(a),
                   lambda: owner.reserve(a, str(uuid.uuid4()), 'b'*64)):
        with pytest.raises(InvalidSession):
            action()
    assert rows(owner) == before


@pytest.mark.parametrize('existing_table', [False, True])
def test_revocation_is_revalidated_even_for_empty_owned_list(store, existing_table):
    owner, a, _ = store
    if existing_table:
        owner.reserve(a, str(uuid.uuid4()), 'a'*64)
    owner.sessions.revoke_account(a.account_id)
    with pytest.raises(InvalidSession):
        owner.list_owned(a)


def test_forged_internal_identity_and_context_cannot_authorize(store):
    owner, a, b = store
    profile_id = str(uuid.uuid4())
    owner.reserve(a, profile_id, 'a'*64)
    owner.activate(a, profile_id, 'a'*64)
    for forged in (replace(a, account_id=b.account_id), replace(a, session_id=str(uuid.uuid4())),
                   replace(a, family_id=str(uuid.uuid4())), object()):
        with pytest.raises(InvalidSession):
            owner.authorize(forged, profile_id)
    owner.sessions.config = replace(owner.sessions.config, mode='development', origins=())
    with pytest.raises(InvalidSession):
        owner.authorize(a, profile_id)


@pytest.mark.parametrize('broken', ['missing-trigger', 'fake-trigger', 'incompatible-table', 'bad-timestamp'])
def test_corruption_is_never_repaired_or_used_for_authorization(store, broken):
    owner, a, _ = store
    profile_id = str(uuid.uuid4())
    if broken != 'incompatible-table':
        owner.reserve(a, profile_id, 'a'*64)
        owner.activate(a, profile_id, 'a'*64)
    with sqlite3.connect(owner.sessions.store.accounts.path) as connection:
        if broken == 'incompatible-table':
            connection.execute('CREATE TABLE profile_ownership (profile_id TEXT, account_id TEXT)')
        elif broken == 'bad-timestamp':
            connection.execute("UPDATE profile_ownership SET updated_at='not-a-timestamp'")
        else:
            connection.execute('DROP TRIGGER profile_ownership_immutable')
            if broken == 'fake-trigger':
                connection.execute('CREATE TRIGGER profile_ownership_immutable BEFORE UPDATE ON profile_ownership BEGIN SELECT 1; END')
    before = rows(owner)
    with pytest.raises(OwnershipNotFound):
        owner.authorize(a, profile_id)
    with pytest.raises(OwnershipUnavailable):
        owner.list_owned(a)
    assert rows(owner) == before
