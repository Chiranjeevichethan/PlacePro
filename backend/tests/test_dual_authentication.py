"""Dual authentication: local development student and Google OAuth 2.0.

Every account is synthetic. Google network calls are replaced by an injected
client; state/nonce handling, claim validation, account creation/linking and
session issuance are the real implementation.
"""
import sqlite3
from urllib.parse import parse_qs, urlencode, urlsplit

from fastapi.testclient import TestClient
import pytest
from starlette.responses import Response

from backend.app.main import create_app
from backend.app.services.account_service import AccountService, InvalidCredentials
from backend.app.services.account_store import AccountStore
from backend.app.services.dev_account import (
    DevelopmentAccountError,
    provision_development_student,
)
from backend.app.services.google_auth import (
    AUTHORIZATION_ENDPOINT,
    GoogleAuthError,
    GoogleAuthService,
    GoogleIdentity,
    GoogleOAuthConfig,
    verify_claims,
)
from backend.app.services.identity_store import IdentityStore
from backend.app.services.security_config import SecurityConfig
from backend.app.services.session_service import SessionService
from backend.app.services.session_store import InvalidSession, SessionStore

PASSWORD = 'Local development passphrase 13'
DEV_EMAIL = 'student@placepro.com'
CLIENT_ID = 'synthetic-client.apps.googleusercontent.com'
ORIGIN = 'http://127.0.0.1:5173'
BASE = 'http://127.0.0.1:8765'
NOW = 1794170000.0
NONCE = 'n' * 64


def account_rows(accounts):
    if not accounts.store.path.exists():
        return []
    with sqlite3.connect(accounts.store.path) as connection:
        return connection.execute('SELECT * FROM accounts').fetchall()


def configured_development(email=DEV_EMAIL, password=PASSWORD, monkeypatch=None):
    if monkeypatch is not None:
        monkeypatch.setenv('PLACEPRO_DEV_STUDENT_EMAIL', email)
        monkeypatch.setenv('PLACEPRO_DEV_STUDENT_PASSWORD', password)
    return SecurityConfig(mode='development', origins=(ORIGIN,))


@pytest.fixture
def accounts(isolated_storage):
    return AccountService(AccountStore())


class FakeGoogleClient:
    def __init__(self, identity=None, failure=None):
        self.identity, self.failure = identity, failure
        self.calls, self.last_nonce = [], None

    def authorization_url(self, state, nonce, code_challenge):
        self.last_nonce = nonce
        return AUTHORIZATION_ENDPOINT + '?' + urlencode(
            {'state': state, 'nonce': nonce, 'code_challenge': code_challenge})

    def exchange_code(self, code, code_verifier, nonce):
        self.calls.append((code, code_verifier, nonce))
        if self.failure:
            raise self.failure
        return self.identity


def start_flow(service):
    response = Response()
    url = service.begin(response)
    query = parse_qs(urlsplit(url).query)
    return query['state'][0], query['nonce'][0], response, url


@pytest.fixture
def google(accounts):
    config = GoogleOAuthConfig(
        client_id=CLIENT_ID, client_secret='synthetic-client-secret',
        redirect_uri=BASE + '/api/auth/google/callback', app_url=ORIGIN)
    config_security = SecurityConfig(mode='development', origins=(ORIGIN,))
    sessions = SessionService(SessionStore(accounts.store), config_security)
    sessions.clock = lambda: NOW
    client = FakeGoogleClient(GoogleIdentity('google-subject-a', DEV_EMAIL, True))
    service = GoogleAuthService(accounts, sessions, config, security=config_security, client=client)
    service.clock = lambda: NOW
    return service


# --------------------------------------------------------------------------
# Local development student account
# --------------------------------------------------------------------------

def test_development_student_is_provisioned_once_and_is_marked(accounts, monkeypatch):
    config = configured_development(monkeypatch=monkeypatch)
    result = provision_development_student(accounts, config)
    assert result == {'email': DEV_EMAIL, 'created': True, 'activated': True,
                      'origin': 'LOCAL_DEVELOPMENT'}
    account = accounts.store.get_by_email(DEV_EMAIL)
    assert account.status == 'ACTIVE' and account.email_verified_at
    assert account.password_hash.startswith('$argon2id$') and PASSWORD not in account.password_hash
    assert IdentityStore(accounts.store).origin(account.account_id) == 'LOCAL_DEVELOPMENT'
    assert accounts.verify_credentials(DEV_EMAIL, PASSWORD).account_id == account.account_id
    with pytest.raises(InvalidCredentials):
        accounts.verify_credentials(DEV_EMAIL, 'Wrong local password 13')

    before = account.password_hash
    second = provision_development_student(accounts, config)
    assert second['created'] is False and second['activated'] is False
    assert len(account_rows(accounts)) == 1
    assert accounts.store.get_by_email(DEV_EMAIL).password_hash == before


def test_development_provisioning_refuses_production_and_absent_configuration(accounts, monkeypatch):
    configured_development(monkeypatch=monkeypatch)
    with pytest.raises(DevelopmentAccountError):
        provision_development_student(
            accounts, SecurityConfig(mode='production', origins=('https://frontend.example.test',)))
    assert not accounts.store.path.exists()

    monkeypatch.delenv('PLACEPRO_DEV_STUDENT_EMAIL')
    monkeypatch.delenv('PLACEPRO_DEV_STUDENT_PASSWORD')
    assert provision_development_student(
        accounts, SecurityConfig(mode='development', origins=(ORIGIN,))) is None
    assert not accounts.store.path.exists()


def test_development_provisioning_rejects_invalid_email_or_short_password(accounts, monkeypatch):
    config = configured_development(email='not-an-email', password=PASSWORD, monkeypatch=monkeypatch)
    with pytest.raises(DevelopmentAccountError):
        provision_development_student(accounts, config)
    config = configured_development(password='tiny', monkeypatch=monkeypatch)
    with pytest.raises(DevelopmentAccountError):
        provision_development_student(accounts, config)
    assert not accounts.store.path.exists()


def test_disabled_development_student_cannot_sign_in(accounts, monkeypatch):
    config = configured_development(monkeypatch=monkeypatch)
    provision_development_student(accounts, config)
    with sqlite3.connect(accounts.store.path) as connection:
        connection.execute("UPDATE accounts SET status='DISABLED'")
    with pytest.raises(InvalidCredentials):
        accounts.verify_credentials(DEV_EMAIL, PASSWORD)


def test_configured_development_account_signs_in_through_the_api(monkeypatch, isolated_storage):
    monkeypatch.setenv('PLACEPRO_DEV_STUDENT_EMAIL', DEV_EMAIL)
    monkeypatch.setenv('PLACEPRO_DEV_STUDENT_PASSWORD', PASSWORD)
    app = create_app(SecurityConfig(mode='development', origins=(ORIGIN,)))
    with TestClient(app, base_url=BASE, client=('127.0.0.1', 50000)) as client:
        challenge = client.get('/api/auth/login-challenge', headers={'Origin': ORIGIN}).json()
        accepted = client.post('/api/auth/login',
                              headers={'Origin': ORIGIN, 'X-CSRF-Token': challenge['csrf_token']},
                              json={'email': DEV_EMAIL, 'password': PASSWORD})
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()['account']['email'] == DEV_EMAIL
        assert client.get('/api/auth/session').status_code == 200

        challenge = client.get('/api/auth/login-challenge', headers={'Origin': ORIGIN}).json()
        rejected = client.post('/api/auth/login',
                              headers={'Origin': ORIGIN, 'X-CSRF-Token': challenge['csrf_token']},
                              json={'email': DEV_EMAIL, 'password': 'Wrong local password 13'})
        assert rejected.status_code == 401 and 'set-cookie' not in rejected.headers


# --------------------------------------------------------------------------
# Google claim validation (no network)
# --------------------------------------------------------------------------

def claims(**changes):
    base = {'iss': 'https://accounts.google.com', 'aud': CLIENT_ID, 'sub': '1234567890',
            'email': 'Student@PlacePro.com', 'email_verified': True, 'nonce': NONCE,
            'exp': NOW + 60, 'iat': NOW}
    return {**base, **changes}


@pytest.mark.parametrize('change', [
    {'iss': 'https://evil.example.test'}, {'aud': 'other-client'},
    {'exp': NOW - 120}, {'exp': 'invalid'}, {'iat': NOW + 600},
    {'nonce': 'x' * 64}, {'nonce': None}, {'sub': ''}, {'sub': 'bad subject'},
    {'email': 'invalid'}, {'email': None},
    {'email_verified': False}, {'email_verified': 'false'}, {'email_verified': None},
    {'azp': 'other-client'},
])
def test_invalid_google_claims_are_rejected(change):
    with pytest.raises(GoogleAuthError):
        verify_claims(claims(**change), client_id=CLIENT_ID, nonce=NONCE, now=NOW)


def test_valid_google_claims_normalize_the_email():
    identity = verify_claims(claims(), client_id=CLIENT_ID, nonce=NONCE, now=NOW)
    assert identity == GoogleIdentity('1234567890', DEV_EMAIL, True)


# --------------------------------------------------------------------------
# Google account creation, linking and sessions
# --------------------------------------------------------------------------

def test_first_google_login_creates_one_active_account_and_session(google, accounts):
    state, nonce, _, _ = start_flow(google)
    secret, session = google.complete(state, state, 'synthetic-code', None)
    account = accounts.store.get_by_email(DEV_EMAIL)
    assert account.status == 'ACTIVE' and account.email_verified_at
    assert session.account_id == account.account_id and session.email == DEV_EMAIL
    assert google.store.origin(account.account_id) == 'GOOGLE'
    assert google.store.linked_account('google', 'google-subject-a') == account.account_id
    assert len(google.client.calls) == 1
    code, verifier, exchanged_nonce = google.client.calls[0]
    assert code == 'synthetic-code' and exchanged_nonce == nonce and len(verifier) >= 43
    assert google.sessions.resolve(secret).account_id == account.account_id
    # A Google-only account never gains a usable local password.
    with pytest.raises(InvalidCredentials):
        accounts.verify_credentials(DEV_EMAIL, 'Any guessed passphrase 2026')


def test_returning_google_user_reuses_the_same_account(google, accounts):
    ids = []
    for _ in range(2):
        state, _, _, _ = start_flow(google)
        _, session = google.complete(state, state, 'synthetic-code', None)
        ids.append(session.account_id)
    assert len(set(ids)) == 1
    assert len(account_rows(accounts)) == 1


def test_google_login_links_an_existing_verified_password_account(google, accounts):
    accounts.register(DEV_EMAIL, PASSWORD)
    accounts.store.activate_pending(accounts.store.get_by_email(DEV_EMAIL).account_id)
    state, _, _, _ = start_flow(google)
    _, session = google.complete(state, state, 'synthetic-code', None)
    account = accounts.store.get_by_email(DEV_EMAIL)
    assert session.account_id == account.account_id
    assert google.store.linked_account('google', 'google-subject-a') == account.account_id
    assert google.store.origin(account.account_id) is None  # Provenance is never rewritten.
    assert accounts.verify_credentials(DEV_EMAIL, PASSWORD).account_id == account.account_id


def test_unverified_google_email_creates_and_links_nothing(google, accounts):
    google.client.identity = GoogleIdentity('google-subject-a', DEV_EMAIL, False)
    state, _, _, _ = start_flow(google)
    with pytest.raises(GoogleAuthError) as error:
        google.complete(state, state, 'synthetic-code', None)
    assert error.value.reason == 'google_unverified'
    assert account_rows(accounts) == []
    assert google.store.linked_account('google', 'google-subject-a') is None


def test_invalid_google_token_creates_nothing(google, accounts):
    google.client.failure = GoogleAuthError('google_invalid')
    state, _, _, _ = start_flow(google)
    with pytest.raises(GoogleAuthError) as error:
        google.complete(state, state, 'synthetic-code', None)
    assert error.value.reason == 'google_invalid'
    assert account_rows(accounts) == []


def test_pending_password_account_is_never_linked_by_email_claim(google, accounts):
    accounts.register(DEV_EMAIL, PASSWORD)
    state, _, _, _ = start_flow(google)
    with pytest.raises(GoogleAuthError) as error:
        google.complete(state, state, 'synthetic-code', None)
    assert error.value.reason == 'google_unverified'
    account = accounts.store.get_by_email(DEV_EMAIL)
    assert account.status == 'PENDING_EMAIL' and account.email_verified_at is None
    assert google.store.linked_account('google', 'google-subject-a') is None


def test_disabled_password_account_is_not_reachable_through_google(google, accounts):
    accounts.register(DEV_EMAIL, PASSWORD)
    account = accounts.store.get_by_email(DEV_EMAIL)
    assert accounts.store.activate_pending(account.account_id)
    with sqlite3.connect(accounts.store.path) as connection:
        connection.execute("UPDATE accounts SET status='DEACTIVATED'")
    state, _, _, _ = start_flow(google)
    with pytest.raises(GoogleAuthError) as error:
        google.complete(state, state, 'synthetic-code', None)
    assert error.value.reason == 'google_inactive'
    assert google.store.linked_account('google', 'google-subject-a') is None


def test_account_already_linked_to_another_subject_is_not_hijacked(google, accounts):
    accounts.register(DEV_EMAIL, PASSWORD)
    account = accounts.store.get_by_email(DEV_EMAIL)
    assert accounts.store.activate_pending(account.account_id)
    assert google.store.link('google', 'different-subject', account.account_id)
    state, _, _, _ = start_flow(google)
    with pytest.raises(GoogleAuthError) as error:
        google.complete(state, state, 'synthetic-code', None)
    assert error.value.reason == 'google_conflict'
    assert google.store.linked_account('google', 'google-subject-a') is None


def test_linked_subject_with_a_changed_email_is_refused(google, accounts):
    state, _, _, _ = start_flow(google)
    google.complete(state, state, 'synthetic-code', None)
    google.client.identity = GoogleIdentity('google-subject-a', 'changed@example.org', True)
    state, _, _, _ = start_flow(google)
    with pytest.raises(GoogleAuthError) as error:
        google.complete(state, state, 'synthetic-code', None)
    assert error.value.reason == 'google_conflict'


def test_state_is_single_use_and_bound_to_the_browser_cookie(google):
    state, _, _, _ = start_flow(google)
    with pytest.raises(GoogleAuthError) as error:
        google.complete(state, 'x' * 43, 'synthetic-code', None)
    assert error.value.reason == 'google_state'
    google.complete(state, state, 'synthetic-code', None)
    with pytest.raises(GoogleAuthError) as error:
        google.complete(state, state, 'synthetic-code', None)
    assert error.value.reason == 'google_state'


def test_expired_state_and_provider_error_do_not_issue_a_session(google, accounts):
    state, _, _, _ = start_flow(google)
    google.clock = lambda: NOW + 301
    with pytest.raises(GoogleAuthError) as error:
        google.complete(state, state, 'synthetic-code', None)
    assert error.value.reason == 'google_state'
    with pytest.raises(GoogleAuthError) as error:
        google.complete(None, None, None, 'access_denied')
    assert error.value.reason == 'google_denied'
    assert account_rows(accounts) == []


def test_session_revocation_invalidates_the_google_session(google):
    state, _, _, _ = start_flow(google)
    secret, session = google.complete(state, state, 'synthetic-code', None)
    google.sessions.revoke_account(session.account_id)
    with pytest.raises(InvalidSession):
        google.sessions.resolve(secret)


def test_disabled_google_service_refuses_to_start_a_flow(accounts):
    sessions = SessionService(SessionStore(accounts.store), SecurityConfig(mode='development', origins=(ORIGIN,)))
    service = GoogleAuthService(accounts, sessions, GoogleOAuthConfig(), security=sessions.config)
    assert service.enabled is False
    with pytest.raises(GoogleAuthError) as error:
        service.begin(Response())
    assert error.value.reason == 'google_not_configured'
    assert not accounts.store.path.exists()


# --------------------------------------------------------------------------
# HTTP contracts
# --------------------------------------------------------------------------

def google_app(monkeypatch):
    monkeypatch.setenv('GOOGLE_CLIENT_ID', CLIENT_ID)
    monkeypatch.setenv('GOOGLE_CLIENT_SECRET', 'synthetic-client-secret')
    monkeypatch.setenv('GOOGLE_REDIRECT_URI', BASE + '/api/auth/google/callback')
    monkeypatch.setenv('PLACEPRO_APP_URL', ORIGIN)
    return create_app(SecurityConfig(mode='development', origins=(ORIGIN,)))


def test_http_google_flow_issues_a_real_session_and_logout_revokes(monkeypatch, isolated_storage):
    app = google_app(monkeypatch)
    app.state.google_auth.client.exchange_code = (
        lambda code, verifier, nonce: GoogleIdentity('google-http-subject', DEV_EMAIL, True))
    with TestClient(app, base_url=BASE, client=('127.0.0.1', 50000)) as client:
        started = client.get('/api/auth/google/start', headers={'Origin': ORIGIN})
        assert started.status_code == 200, started.text
        url = started.json()['authorization_url']
        assert url.startswith(AUTHORIZATION_ENDPOINT + '?')
        query = parse_qs(urlsplit(url).query)
        assert query['code_challenge_method'] == ['S256'] and query['client_id'] == [CLIENT_ID]
        state = query['state'][0]
        oauth_cookie = client.cookies.get(app.state.security_config.oauth_cookie)
        assert oauth_cookie == state
        assert 'HttpOnly' in started.headers.get('set-cookie', '')

        callback = client.get('/api/auth/google/callback',
                              params={'code': 'synthetic-code', 'state': state},
                              follow_redirects=False)
        assert callback.status_code == 303
        assert callback.headers['location'] == ORIGIN + '/?auth=google'
        assert client.cookies.get(app.state.security_config.oauth_cookie) is None
        assert app.state.security_config.cookie_name in client.cookies
        assert 'HttpOnly' in callback.headers.get('set-cookie', '')

        session = client.get('/api/auth/session')
        assert session.status_code == 200
        assert session.json()['account']['email'] == DEV_EMAIL

        replay = client.get('/api/auth/google/callback',
                            params={'code': 'synthetic-code', 'state': state},
                            follow_redirects=False)
        assert replay.headers['location'] == ORIGIN + '/?auth_error=google_state'

        token = client.get('/api/auth/csrf', headers={'Origin': ORIGIN}).json()['csrf_token']
        assert client.post('/api/auth/logout', headers={'Origin': ORIGIN, 'X-CSRF-Token': token}).status_code == 204
        assert client.get('/api/auth/session').status_code == 401


@pytest.mark.parametrize('outcome,expected', [
    ('invalid', 'google_invalid'),
    ('unverified', 'google_unverified'),
])
def test_http_google_failures_redirect_without_a_session(monkeypatch, isolated_storage, outcome, expected):
    app = google_app(monkeypatch)
    if outcome == 'invalid':
        def exchange(code, verifier, nonce):
            raise GoogleAuthError('google_invalid')
    else:
        def exchange(code, verifier, nonce):
            return GoogleIdentity('google-http-subject', DEV_EMAIL, False)
    app.state.google_auth.client.exchange_code = exchange
    with TestClient(app, base_url=BASE, client=('127.0.0.1', 50000)) as client:
        started = client.get('/api/auth/google/start', headers={'Origin': ORIGIN})
        state = parse_qs(urlsplit(started.json()['authorization_url']).query)['state'][0]
        callback = client.get('/api/auth/google/callback',
                              params={'code': 'synthetic-code', 'state': state},
                              follow_redirects=False)
        assert callback.status_code == 303
        assert callback.headers['location'] == ORIGIN + '/?auth_error=' + expected
        assert app.state.security_config.cookie_name not in client.cookies
        assert client.get('/api/auth/session').status_code == 401
    assert account_rows(app.state.accounts) == []


def test_http_google_start_requires_exact_origin_and_configuration(monkeypatch, isolated_storage):
    app = google_app(monkeypatch)
    with TestClient(app, base_url=BASE, client=('127.0.0.1', 50000)) as client:
        assert client.get('/api/auth/google/start').status_code == 403
        assert client.get('/api/auth/google/start',
                          headers={'Origin': 'https://evil.example.test'}).status_code == 403
        assert 'authorization_url' not in client.get(
            '/api/auth/google/start', headers={'Origin': 'https://evil.example.test'}).text

    monkeypatch.delenv('GOOGLE_CLIENT_ID')
    monkeypatch.delenv('GOOGLE_CLIENT_SECRET')
    unconfigured = create_app(SecurityConfig(mode='development', origins=(ORIGIN,)))
    with TestClient(unconfigured, base_url=BASE, client=('127.0.0.1', 50000)) as client:
        response = client.get('/api/auth/google/start', headers={'Origin': ORIGIN})
        assert response.status_code == 503 and 'not configured' in response.text
        assert 'set-cookie' not in response.headers


@pytest.mark.parametrize('variable,value', [
    ('GOOGLE_CLIENT_ID', 'partial-client'),
    ('GOOGLE_CLIENT_SECRET', 'partial-secret'),
])
def test_partial_google_configuration_fails_closed(monkeypatch, isolated_storage, variable, value):
    from backend.app.services.google_auth import GoogleOAuthConfigurationError
    monkeypatch.setenv(variable, value)
    with pytest.raises(GoogleOAuthConfigurationError):
        create_app(SecurityConfig(mode='development', origins=(ORIGIN,)))


def test_production_google_configuration_requires_https(monkeypatch, isolated_storage):
    from backend.app.services.google_auth import GoogleOAuthConfigurationError
    monkeypatch.setenv('GOOGLE_CLIENT_ID', CLIENT_ID)
    monkeypatch.setenv('GOOGLE_CLIENT_SECRET', 'synthetic-client-secret')
    monkeypatch.setenv('GOOGLE_REDIRECT_URI', 'http://api.example.test/api/auth/google/callback')
    monkeypatch.setenv('PLACEPRO_APP_URL', 'https://frontend.example.test')
    with pytest.raises(GoogleOAuthConfigurationError):
        create_app(SecurityConfig(mode='production', origins=('https://frontend.example.test',)))
