"""Synthetic launcher uses actual secured app, never historical stores."""
import hashlib
import json
import socket
import sqlite3

import pytest

from scripts.demo import (EMAILS, ROOT, checked_workspace, create_resume, launch_api, launch_frontend, main, new_workspace,
                          request, seed_accounts, seed_profiles, synthetic_profile)
from backend.tests.test_sessions import PASSWORD
import http.cookiejar
import urllib.request


def port():
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


def login(base, origin, email):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    headers = {'Origin': origin}
    challenge = request(opener, base, '/api/auth/login-challenge', headers=headers)[1]
    assert request(opener, base, '/api/auth/login', 'POST', {'email': email, 'password': PASSWORD},
                   headers | {'X-CSRF-Token': challenge['csrf_token']})[0] == 200
    token = request(opener, base, '/api/auth/csrf', headers=headers)[1]['csrf_token']
    return opener, headers | {'X-CSRF-Token': token}


def test_demo_requires_fresh_storage_and_never_reprovisions_existing_accounts(isolated_storage):
    root = new_workspace(isolated_storage.root)
    seed_accounts(root, PASSWORD)
    before = hashlib.sha256((root / 'accounts.sqlite3').read_bytes()).hexdigest()
    with pytest.raises(ValueError, match='new authentication database'):
        seed_accounts(root, PASSWORD)
    assert hashlib.sha256((root / 'accounts.sqlite3').read_bytes()).hexdigest() == before
    with sqlite3.connect(root / 'accounts.sqlite3') as connection:
        records = connection.execute('SELECT email_normalized,status,password_hash FROM accounts').fetchall()
    assert {row[0] for row in records} == set(EMAILS)
    assert all(row[1] == 'ACTIVE' and row[2].startswith('$argon2id$') and PASSWORD not in row[2] for row in records)
    assert PASSWORD not in (root / 'demo-workspace.json').read_text()


def test_demo_rejects_historical_and_unmarked_storage(isolated_storage):
    for parent in (ROOT / 'data', ROOT / 'models', ROOT / 'scratch'):
        with pytest.raises(ValueError):
            new_workspace(parent)
    with pytest.raises(ValueError):
        checked_workspace(ROOT / 'data')
    with pytest.raises(ValueError):
        checked_workspace(isolated_storage.root)


def test_demo_identity_payload_has_no_client_owner_or_profile_id():
    body = synthetic_profile('a', 1)
    assert not {'account_id', 'owner_id', 'profile_id'} & body.keys()
    assert body['personal']['name'].startswith('Synthetic')
    assert body['personal']['email'].endswith('@example.test')


def test_demo_noninteractive_launch_refuses_to_echo_password(monkeypatch):
    from io import StringIO
    import sys
    monkeypatch.setattr(sys, 'argv', ['demo.py', '--api-port', str(port()), '--frontend-port', str(port())])
    monkeypatch.setattr(sys, 'stdin', StringIO(''))
    with pytest.raises(ValueError, match='input stays hidden'):
        main()


def test_demo_corrupt_marker_is_rejected(isolated_storage):
    root = new_workspace(isolated_storage.root)
    (root / 'demo-workspace.json').write_text('{}')
    with pytest.raises(ValueError, match='workspace marker'):
        checked_workspace(root)


def test_demo_resume_creation_never_replaces_an_existing_file(isolated_storage):
    root = new_workspace(isolated_storage.root)
    path = create_resume(root)
    before = path.read_bytes()
    with pytest.raises(ValueError, match='replace an existing resume'):
        create_resume(root)
    assert path.read_bytes() == before


def test_demo_frontend_refuses_an_occupied_port(isolated_storage):
    root = new_workspace(isolated_storage.root)
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        listener.listen()
        occupied = listener.getsockname()[1]
        with pytest.raises(OSError):
            with launch_frontend(root, port(), occupied):
                pytest.fail('Occupied frontend port was reused.')
        assert listener.fileno() != -1
    assert not (root / 'frontend.log').exists()


@pytest.mark.live_http
def test_real_vite_demo_deep_links_api_configuration_and_owned_shutdown(isolated_storage):
    root = new_workspace(isolated_storage.root)
    api, frontend = port(), port()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    marker = json.loads((root / 'demo-workspace.json').read_text())
    with launch_api(root, api, frontend), launch_frontend(root, api, frontend) as process:
        for route in ('/', '/experimental-v1-prediction', '/student-resume-builder'):
            with opener.open(f'http://127.0.0.1:{frontend}' + route) as response:
                html = response.read().decode()
                assert response.status == 200
                assert response.headers['X-PlacePro-Demo-Run'] == marker['run_id']
                assert '/@vite/client' in html and '/src/main.jsx' in html
        with opener.open(f'http://127.0.0.1:{frontend}/src/services/apiTransport.js') as response:
            source = response.read().decode()
            assert f'http://127.0.0.1:{api}' in source
            assert '"DEV":true' in source or '"DEV": true' in source
        # The released example exists in both trees; an absent local env takes SPA fallback.
        assert (ROOT / 'frontend' / '.env.example').is_file()
        with pytest.raises(urllib.error.HTTPError) as denied:
            opener.open(f'http://127.0.0.1:{frontend}/.env.example')
        assert denied.value.code in (403, 404)
    assert process.returncode == 0
    assert not (root / 'bundle').exists()
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', frontend))


@pytest.mark.live_http
def test_real_demo_server_normal_login_ownership_stateless_predictions_and_shutdown(isolated_storage):
    root = new_workspace(isolated_storage.root)
    seed_accounts(root, PASSWORD)
    api, frontend = port(), port()
    base, origin = f'http://127.0.0.1:{api}', f'http://127.0.0.1:{frontend}'
    with launch_api(root, api, frontend):
        references = seed_profiles(base, origin, PASSWORD)
        a, ha = login(base, origin, EMAILS[0])
        b, hb = login(base, origin, EMAILS[1])
        assert len(references['a']) == len(references['b']) == 2 and not references['empty']
        target = '/api/profile/' + references['a'][0]
        assert request(a, base, target)[0] == 200
        assert request(b, base, target, headers=hb) == (404, {'detail': 'Profile not found.'})
        assert request(b, base, target + '/predict', 'POST', headers=hb)[0] == 404
        assert request(a, base, '/api/account/profiles')[1] == {'profiles': [{'profile_id': p} for p in references['a']]}
        assert request(a, base, '/api/auth/register', 'POST', {}, ha)[0] == 503
        assert request(a, base, target, 'PUT', {}, {'Origin': origin})[0] == 403
        from backend.tests.test_predict import SAMPLE_STUDENT
        from backend.tests.test_salary_prediction import VALID_PAYLOAD
        assert request(a, base, '/api/predict', 'POST', SAMPLE_STUDENT, ha)[0] == 200
        assert request(a, base, '/api/salary-predict', 'POST', VALID_PAYLOAD, ha)[0] == 200
        assert request(a, base, '/api/auth/logout', 'POST', headers=ha)[0] == 204
        assert request(a, base, target)[0] == 401
    assert 'Application shutdown complete' in (root / 'server.log').read_text()
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', api))
