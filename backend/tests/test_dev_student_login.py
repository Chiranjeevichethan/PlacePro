"""Local development credentials retain the existing password/session guards."""
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.main import create_app
from backend.app.schemas_auth import RegistrationRequest
from backend.app.services.account_service import InvalidCredentials
from backend.app.services.dev_account import provision_development_student
from backend.app.services.identity_store import IdentityStore
from backend.app.services.security_config import SecurityConfig

EMAIL = 'student@placepro.com'
ORIGIN = 'http://127.0.0.1:5173'
BASE = 'http://127.0.0.1:8765'
# Synthetic passwords exercise the local minimum without retaining operator input.
PASSWORD = 'fixture13'
CHANGED_PASSWORD = 'Different fixture password 13'


def login(client, password):
    challenge = client.get('/api/auth/login-challenge', headers={'Origin': ORIGIN})
    assert challenge.status_code == 200
    return client.post('/api/auth/login', headers={
        'Origin': ORIGIN, 'X-CSRF-Token': challenge.json()['csrf_token'],
    }, json={'email': EMAIL, 'password': password})


def test_existing_development_password_is_not_replaced_and_real_login_logout_revocation_work(
    isolated_storage, monkeypatch,
):
    monkeypatch.setenv('PLACEPRO_DEV_STUDENT_EMAIL', EMAIL)
    monkeypatch.setenv('PLACEPRO_DEV_STUDENT_PASSWORD', PASSWORD)
    config = SecurityConfig(mode='development', origins=(ORIGIN,))
    app = create_app(config)
    accounts = app.state.accounts
    account = accounts.store.get_by_email(EMAIL)
    assert accounts.store.path == isolated_storage.auth_db
    assert app.state.sessions.store.accounts is accounts.store
    assert account.status == 'ACTIVE' and account.email_verified_at
    assert IdentityStore(accounts.store).origin(account.account_id) == 'LOCAL_DEVELOPMENT'

    # Changing provisioning configuration does not change an existing credential.
    monkeypatch.setenv('PLACEPRO_DEV_STUDENT_PASSWORD', CHANGED_PASSWORD)
    repeated = provision_development_student(accounts, config)
    assert repeated['created'] is False and repeated['activated'] is False
    assert accounts.store.get_by_email(EMAIL).password_hash == account.password_hash
    assert accounts.verify_credentials(EMAIL, PASSWORD).account_id == account.account_id
    with pytest.raises(InvalidCredentials):
        accounts.verify_credentials(EMAIL, CHANGED_PASSWORD)
    with pytest.raises(ValidationError):
        RegistrationRequest(email=EMAIL, password=PASSWORD)

    with TestClient(app, base_url=BASE, client=('127.0.0.1', 50000)) as client:
        denied = login(client, CHANGED_PASSWORD)
        assert denied.status_code == 401
        assert denied.json() == {'detail': 'Invalid credentials.'}
        assert 'set-cookie' not in denied.headers
        accepted = login(client, PASSWORD)
        assert accepted.status_code == 200
        assert client.get('/api/auth/session').status_code == 200
        retained = client.cookies.get(config.cookie_name)
        csrf_response = client.get('/api/auth/csrf', headers={'Origin': ORIGIN})
        assert csrf_response.status_code == 200
        csrf = csrf_response.json()['csrf_token']
        logged_out = client.post('/api/auth/logout', headers={'Origin': ORIGIN, 'X-CSRF-Token': csrf})
        assert logged_out.status_code == 204
        assert client.get('/api/auth/session').status_code == 401
        client.cookies.set(config.cookie_name, retained)
        assert client.get('/api/auth/session').status_code == 401
        assert client.get('/api/account/profiles').status_code == 401
        client.cookies.clear()
        assert login(client, PASSWORD).status_code == 200
        app.state.sessions.revoke_account(account.account_id)
        assert client.get('/api/auth/session').status_code == 401
        assert client.get('/api/account/profiles').status_code == 401
    assert accounts.store.get_by_email(EMAIL).password_hash == account.password_hash
