"""The reported development cookie failure must remain a CSRF denial before credentials."""
import re
import sqlite3

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.services.security_config import SecurityConfig
from backend.tests.test_session_security import active_account
from backend.tests.test_sessions import PASSWORD

ORIGINS = ('http://localhost:5173', 'http://127.0.0.1:5173')
EMAIL = 'login-regression@example.test'


@pytest.fixture
def development_app(isolated_storage):
    return create_app(SecurityConfig(mode='development', origins=ORIGINS))


@pytest.mark.parametrize('case', ['missing-cookie', 'wrong-token', 'duplicate-cookie', 'wrong-origin'])
def test_bootstrap_rejection_happens_before_credentials(development_app, monkeypatch, case):
    config = development_app.state.security_config
    with TestClient(development_app, base_url='http://127.0.0.1:8000', client=('127.0.0.1', 12345)) as client:
        challenge = client.get('/api/auth/login-challenge', headers={'Origin': ORIGINS[0]})
        assert challenge.status_code == 200
        assert re.fullmatch('[a-f0-9]{64}', challenge.json()['csrf_token'])
        assert challenge.headers['access-control-allow-origin'] == ORIGINS[0]
        headers = {'Origin': ORIGINS[0], 'X-CSRF-Token': challenge.json()['csrf_token']}
        if case == 'missing-cookie':
            client.cookies.clear()
        elif case == 'wrong-token':
            headers['X-CSRF-Token'] = 'f' * 64
        elif case == 'duplicate-cookie':
            cookie = client.cookies.get(config.challenge_cookie)
            headers['Cookie'] = f'{config.challenge_cookie}={cookie}; {config.challenge_cookie}={cookie}'
        else:
            headers['Origin'] = 'http://untrusted.example.test'

        def reject_credential_work(*args, **kwargs):
            pytest.fail('Credential verification ran after a rejected security proof.')

        monkeypatch.setattr(development_app.state.accounts, 'verify_credentials', reject_credential_work)
        result = client.post('/api/auth/login', headers=headers, json={'email': EMAIL, 'password': PASSWORD})
        assert result.status_code == 403
        assert 'set-cookie' not in result.headers
        assert result.json()['detail'] == ('Request origin is not allowed.' if case == 'wrong-origin' else 'CSRF validation failed.')
        with sqlite3.connect(development_app.state.accounts.store.path) as connection:
            assert connection.execute('SELECT count(*) FROM sessions').fetchone()[0] == 0
            assert connection.execute('SELECT attempts FROM login_challenges').fetchone()[0] == 0


@pytest.mark.parametrize('api,origin', [
    ('http://localhost:8000', ORIGINS[0]),
    ('http://127.0.0.1:8000', ORIGINS[1]),
])
def test_development_login_csrf_restore_and_logout(development_app, api, origin):
    active_account(development_app, email=EMAIL)
    config = development_app.state.security_config
    with TestClient(development_app, base_url=api, client=('127.0.0.1', 12345)) as client:
        assert client.get('/api/auth/csrf', headers={'Origin': origin}).status_code == 401
        challenge = client.get('/api/auth/login-challenge', headers={'Origin': origin})
        assert challenge.status_code == 200
        cookie = challenge.headers['set-cookie'].lower()
        assert 'httponly' in cookie and 'samesite=lax' in cookie and 'path=/' in cookie
        assert 'domain=' not in cookie and 'secure' not in cookie and 'max-age=300' in cookie
        headers = {'Origin': origin, 'X-CSRF-Token': challenge.json()['csrf_token']}
        invalid = client.post('/api/auth/login', headers=headers, json={'email': EMAIL, 'password': 'Incorrect synthetic password'})
        assert invalid.status_code == 401 and invalid.json() == {'detail': 'Invalid credentials.'}
        assert client.cookies.get(config.cookie_name) is None
        assert 'set-cookie' not in invalid.headers
        challenge = client.get('/api/auth/login-challenge', headers={'Origin': origin})
        headers['X-CSRF-Token'] = challenge.json()['csrf_token']
        success = client.post('/api/auth/login', headers=headers, json={'email': EMAIL, 'password': PASSWORD})
        assert success.status_code == 200 and success.json()['account']['email'] == EMAIL
        assert client.cookies.get(config.challenge_cookie) is None
        assert client.cookies.get(config.cookie_name) is not None
        restored = client.get('/api/auth/session', headers={'Origin': origin})
        assert restored.status_code == 200 and restored.json()['account'] == success.json()['account']
        token = client.get('/api/auth/csrf', headers={'Origin': origin})
        assert token.status_code == 200 and re.fullmatch('[a-f0-9]{64}', token.json()['csrf_token'])
        headers['X-CSRF-Token'] = token.json()['csrf_token']
        assert client.post('/api/auth/logout', headers=headers).status_code == 204
        assert client.get('/api/auth/session', headers={'Origin': origin}).status_code == 401
        assert client.get('/api/auth/csrf', headers={'Origin': origin}).status_code == 401
