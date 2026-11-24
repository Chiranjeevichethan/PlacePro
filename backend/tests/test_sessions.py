"""Session/storage regression tests: every account and activation is synthetic."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import hashlib
import sqlite3

import pytest

from backend.app.services.account_service import AccountService, InvalidCredentials
from backend.app.services.account_store import AccountStore, AccountStorageError
from backend.app.services.security_config import SecurityConfig
from backend.app.services.session_service import SessionService, InvalidSession, InvalidCSRF, SessionCapacity, csrf_token
from backend.app.services.session_store import SessionStore

PASSWORD = 'Synthetic session passphrase 29.6.3'


@pytest.fixture
def sessions(isolated_storage):
    accounts = AccountService(AccountStore())
    accounts.register('one@example.org',PASSWORD)
    with sqlite3.connect(accounts.store.path) as connection:
        connection.execute("UPDATE accounts SET status='ACTIVE',email_verified_at='2026-11-09T00:00:00+00:00'")
    service = SessionService(SessionStore(accounts.store),SecurityConfig())
    service.test_time = [1794170000.0]
    service.clock = lambda: service.test_time[0]
    service.test_accounts = accounts
    return service


def issue(service, email='one@example.org'):
    challenge, token = service.challenge()
    service.begin_login(challenge,token)
    proof = service.test_accounts.verify_credentials(email,PASSWORD)
    secret, identity = service.create(proof,challenge,token)
    return secret, identity, csrf_token(secret,identity.csrf_nonce)


def rows(service):
    with sqlite3.connect(service.store.accounts.path) as c:
        return c.execute('SELECT * FROM sessions').fetchall()


def test_persistent_secrets_hash_only_and_account_rows_unchanged(sessions):
    account = sessions.test_accounts.store.get_by_email('one@example.org')
    secret, identity, token = issue(sessions)
    assert len(secret)==43 and len(token)==64
    stored = rows(sessions)
    assert secret not in repr(stored) and token not in repr(stored) and PASSWORD not in repr(stored)
    assert hashlib.sha256(secret.encode()).hexdigest() in repr(stored)
    restart = SessionService(SessionStore(AccountStore(sessions.store.accounts.path)),sessions.config,sessions.clock)
    assert restart.resolve(secret)==identity
    assert sessions.test_accounts.store.get_by_email('one@example.org')==account
    assert 'secret' not in repr(identity) and 'csrf' not in repr(identity)


@pytest.mark.parametrize('secret',[None,'','forged','x'*43,'x'*42,'x'*44,'é'*43])
def test_missing_forged_and_modified_cookie_rejected(sessions,secret):
    with pytest.raises(InvalidSession):
        sessions.resolve(secret)


@pytest.mark.parametrize('boundary',['idle','absolute'])
def test_expiration_is_server_controlled_and_cannot_be_renewed(sessions,boundary):
    secret, identity, token = issue(sessions)
    sessions.test_time[0] = identity.idle_expires_at if boundary=='idle' else identity.absolute_expires_at
    for action in (lambda:sessions.resolve(secret),lambda:sessions.touch(secret),lambda:sessions.rotate(secret,token)):
        with pytest.raises(InvalidSession):
            action()
    assert rows(sessions)[0][13]=='EXPIRED'
    sessions.test_time[0] -= sessions.config.absolute_seconds
    with pytest.raises(InvalidSession):
        sessions.resolve(secret)  # Observed expiry remains terminal after clock rollback.


def test_activity_renewal_is_throttled_and_absolute_lifetime_is_fixed(sessions):
    secret, initial, _ = issue(sessions)
    before = rows(sessions)
    sessions.test_time[0] += 10
    assert sessions.touch(secret)==initial and rows(sessions)==before
    sessions.test_time[0] += 25
    refreshed = sessions.touch(secret)
    assert refreshed.idle_expires_at == initial.idle_expires_at+35
    assert refreshed.absolute_expires_at==initial.absolute_expires_at
    # Renew activity near the absolute boundary through valid periodic requests.
    while sessions.test_time[0]+1000 < initial.absolute_expires_at:
        sessions.test_time[0] += 1000
        sessions.touch(secret)
    assert sessions.touch(secret).idle_expires_at <= initial.absolute_expires_at


def test_rotation_invalidates_old_cookie_and_csrf_preserving_absolute_expiry(sessions):
    old, identity, token = issue(sessions)
    sessions.test_time[0] += 60
    new, replacement = sessions.rotate(old,token)
    assert new != old and replacement.family_id==identity.family_id
    assert replacement.absolute_expires_at==identity.absolute_expires_at
    with pytest.raises(InvalidSession):
        sessions.resolve(old)
    with pytest.raises(InvalidCSRF):
        sessions.check_csrf(new,replacement,token)
    assert sessions.resolve(new)==replacement


def test_logout_and_repeated_logout_revoke_server_family(sessions):
    secret, _, token = issue(sessions)
    sessions.logout(secret,token)
    sessions.logout(secret,token)
    with pytest.raises(InvalidSession):
        sessions.resolve(secret)
    assert rows(sessions)[0][13]=='LOGOUT'


@pytest.mark.parametrize('change',["status='DISABLED'", "status='DEACTIVATED'", "auth_version=auth_version+1",
                                  "password_changed_at='2026-11-10T00:00:00+00:00'"])
def test_account_and_password_changes_invalidate_sessions(sessions,change):
    secret, _, token = issue(sessions)
    with sqlite3.connect(sessions.store.accounts.path) as c:
        c.execute('UPDATE accounts SET '+change)
    with pytest.raises(InvalidSession):
        sessions.resolve(secret)
    with pytest.raises(InvalidSession):
        sessions.rotate(secret,token)


def test_credential_status_race_cannot_create_session(sessions):
    challenge, token = sessions.challenge()
    sessions.begin_login(challenge,token)
    proof = sessions.test_accounts.verify_credentials('one@example.org',PASSWORD)
    with sqlite3.connect(sessions.store.accounts.path) as c:
        c.execute("UPDATE accounts SET status='DISABLED'")
    with pytest.raises(InvalidCredentials):
        sessions.create(proof,challenge,token)
    assert not rows(sessions)


def test_password_timestamp_race_cannot_create_session(sessions):
    challenge, token = sessions.challenge()
    sessions.begin_login(challenge,token)
    proof = sessions.test_accounts.verify_credentials('one@example.org',PASSWORD)
    with pytest.raises(InvalidCredentials):
        sessions.create(replace(proof,password_changed_at='old'),challenge,token)
    assert not rows(sessions)


@pytest.mark.parametrize('token',[None,'','bad','0'*64,'é'*64])
def test_invalid_csrf_cannot_rotate_or_revoke(sessions,token):
    secret, identity, _ = issue(sessions)
    before = rows(sessions)
    for action in (lambda:sessions.check_csrf(secret,identity,token),lambda:sessions.rotate(secret,token),lambda:sessions.logout(secret,token)):
        with pytest.raises(InvalidCSRF):
            action()
    assert rows(sessions)==before


def test_cross_session_and_cross_account_csrf_are_rejected(sessions):
    first, _, token = issue(sessions)
    second, identity, _ = issue(sessions)
    with pytest.raises(InvalidCSRF):
        sessions.check_csrf(second,identity,token)
    sessions.test_accounts.register('two@example.org',PASSWORD)
    with sqlite3.connect(sessions.store.accounts.path) as c:
        c.execute("UPDATE accounts SET status='ACTIVE',email_verified_at='2026-11-09' WHERE email_normalized='two@example.org'")
    third, other, _ = issue(sessions,'two@example.org')
    assert other.account_id != sessions.resolve(first).account_id
    with pytest.raises(InvalidCSRF):
        sessions.logout(third,token)


def test_concurrent_creation_has_unique_secrets_and_session_cap(sessions):
    proof = sessions.test_accounts.verify_credentials('one@example.org',PASSWORD)
    def create(_):
        challenge, token = sessions.challenge()
        sessions.begin_login(challenge,token)
        try:
            return sessions.create(proof,challenge,token)[0]
        except SessionCapacity:
            return None
    with ThreadPoolExecutor(max_workers=4) as pool:
        secrets = list(pool.map(create,range(12)))
    assert len({s for s in secrets if s})==10 and secrets.count(None)==2
    assert sum(r[12] is None for r in rows(sessions))==10


def test_concurrent_rotation_has_one_winner(sessions):
    secret, _, token = issue(sessions)
    def rotate(_):
        try:
            return sessions.rotate(secret,token)
        except InvalidSession:
            return None
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(rotate,range(4)))
    assert sum(r is not None for r in results)==1 and len(rows(sessions))==2


def test_concurrent_logout_and_renew_leave_no_valid_family(sessions):
    secret, _, token = issue(sessions)
    def rotate():
        try:
            return sessions.rotate(secret,token)
        except InvalidSession:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        renewal = pool.submit(rotate)
        logout = pool.submit(sessions.logout,secret,token)
        result = renewal.result()
        logout.result()
    with pytest.raises(InvalidSession):
        sessions.resolve(result[0] if result else secret)
    assert all(r[12] is not None for r in rows(sessions))


def test_concurrent_revocation_is_idempotent(sessions):
    secret, _, token = issue(sessions)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _:sessions.logout(secret,token),range(4)))
    assert len(rows(sessions))==1 and rows(sessions)[0][13]=='LOGOUT'


def test_session_insert_failure_rolls_back_rotation(sessions,monkeypatch):
    secret, identity, token = issue(sessions)
    before = rows(sessions)
    def fail(*args):
        raise sqlite3.OperationalError('synthetic private path')
    monkeypatch.setattr(sessions.store,'insert_session',fail)
    with pytest.raises(AccountStorageError):
        sessions.rotate(secret,token)
    assert rows(sessions)==before and sessions.resolve(secret)==identity


def test_login_insert_failure_does_not_consume_challenge(sessions,monkeypatch):
    challenge, token = sessions.challenge()
    sessions.begin_login(challenge,token)
    proof = sessions.test_accounts.verify_credentials('one@example.org',PASSWORD)
    def fail(*args):
        raise sqlite3.OperationalError('synthetic write failure')
    with monkeypatch.context() as patch:
        patch.setattr(sessions.store,'insert_session',fail)
        with pytest.raises(AccountStorageError):
            sessions.create(proof,challenge,token)
    assert not rows(sessions)
    assert sessions.resolve(sessions.create(proof,challenge,token)[0])


def test_login_challenge_expiry_attempt_limit_and_replay(sessions):
    challenge, token = sessions.challenge()
    for _ in range(5):
        sessions.begin_login(challenge,token)
    with pytest.raises(InvalidCSRF):
        sessions.begin_login(challenge,token)
    sessions.test_time[0] += sessions.config.challenge_seconds
    with pytest.raises(InvalidCSRF):
        sessions.begin_login(challenge,token)
    challenge, token = sessions.challenge()
    sessions.begin_login(challenge,token)
    proof = sessions.test_accounts.verify_credentials('one@example.org',PASSWORD)
    sessions.create(proof,challenge,token)
    with pytest.raises(InvalidCSRF):
        sessions.create(proof,challenge,token)


def test_dev_session_cannot_be_resolved_in_production_context(sessions):
    sessions.config = SecurityConfig(mode='development')
    secret, _, _ = issue(sessions)
    sessions.config = SecurityConfig()
    with pytest.raises(InvalidSession):
        sessions.resolve(secret)


def test_revoke_account_hook_revokes_multiple_sessions(sessions):
    first, identity, _ = issue(sessions)
    second, _, _ = issue(sessions)
    sessions.revoke_account(identity.account_id)
    for secret in (first,second):
        with pytest.raises(InvalidSession):
            sessions.resolve(secret)


def test_session_tables_are_additive_and_preserve_account_schema_version(sessions):
    before = sessions.test_accounts.store.get_by_email('one@example.org')
    issue(sessions)
    with sqlite3.connect(sessions.store.accounts.path) as c:
        assert c.execute('PRAGMA user_version').fetchone()[0]==1
        assert {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}=={'accounts','sessions','login_challenges'}
    assert sessions.test_accounts.store.get_by_email('one@example.org')==before


def test_database_lock_failure_is_generic_and_does_not_change_rows(sessions):
    issue(sessions)
    before = rows(sessions)
    with sqlite3.connect(sessions.store.accounts.path,isolation_level=None) as lock:
        lock.execute('BEGIN IMMEDIATE')
        with pytest.raises(AccountStorageError) as error:
            sessions.challenge()
        assert str(error.value)=='Account storage is temporarily unavailable.'
        lock.rollback()
    assert rows(sessions)==before


def test_session_lookup_does_not_create_a_database(isolated_storage):
    service=SessionService(SessionStore(AccountStore()),SecurityConfig())
    with pytest.raises(InvalidSession):
        service.resolve('x'*43)
    assert not isolated_storage.auth_db.exists()


@pytest.mark.parametrize('action',['touch','rotate','logout'])
def test_malformed_service_cookie_fails_safely(sessions,action):
    with pytest.raises(InvalidSession):
        getattr(sessions,action)(None,*(() if action=='touch' else ('bad',)))


def test_incompatible_session_table_refused_without_account_changes(sessions):
    before=sessions.test_accounts.store.get_by_email('one@example.org')
    with sqlite3.connect(sessions.store.accounts.path) as c:
        c.execute('CREATE TABLE sessions (wrong_column TEXT)')
    with pytest.raises(AccountStorageError):
        sessions.challenge()
    assert sessions.test_accounts.store.get_by_email('one@example.org')==before


@pytest.mark.parametrize('bad', ["csrf_nonce='malformed'", "last_activity_at='invalid'"])
def test_corrupted_session_metadata_fails_closed(sessions,bad):
    secret,_,_=issue(sessions)
    with sqlite3.connect(sessions.store.accounts.path) as c:
        c.execute('UPDATE sessions SET '+bad)
    with pytest.raises(InvalidSession):
        sessions.resolve(secret)
