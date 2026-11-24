"""Actual secured FastAPI application: no test dependency disables the gate."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import sqlite3

import pytest
from fastapi.routing import iter_route_contexts
from fastapi.testclient import TestClient

from backend.app.main import create_app, app as default_app
from backend.app.security import PUBLIC, ENTRY, SESSION, OAUTH, PROFILES, ASSESSMENTS, ANALYTICS, GOALS, SIDE_EFFECT_GET, OWNERSHIP_PENDING
from backend.app.services.security_config import SecurityConfig
from backend.tests.test_sessions import PASSWORD

ORIGIN='https://frontend.example.test'
BASE='https://api.example.test'


def inventory(application):
    return [(method,r.path) for r in iter_route_contexts(application.routes) for method in sorted(r.methods or ())]


OPERATIONS=inventory(default_app)
PRIVATE=[op for op in OPERATIONS if op not in PUBLIC | ENTRY | SESSION | OAUTH]
DEFERRED=[op for op in PRIVATE if op not in PROFILES | ASSESSMENTS | ANALYTICS | GOALS]


def actual(path):
    return path.replace('{profile_id}','synthetic-profile').replace('{assessment_id}','synthetic-assessment').replace('{company_id}','company_001')


@pytest.fixture
def secured(isolated_storage):
    application=create_app(SecurityConfig(origins=(ORIGIN,)))
    yield application


def active_account(application,email='one@example.org',status='ACTIVE'):
    service=application.state.accounts
    service.register(email,PASSWORD)
    with sqlite3.connect(service.store.path) as c:
        c.execute('UPDATE accounts SET status=?,email_verified_at=? WHERE email_normalized=?',
                  (status,'2026-11-09T00:00:00+00:00' if status!='PENDING_EMAIL' else None,email))


def login(client,email='one@example.org',password=PASSWORD):
    challenge=client.get('/api/auth/login-challenge',headers={'Origin':ORIGIN})
    assert challenge.status_code==200,challenge.text
    return client.post('/api/auth/login',headers={'Origin':ORIGIN,'X-CSRF-Token':challenge.json()['csrf_token']},
                       json={'email':email,'password':password})


def csrf(client):
    response=client.get('/api/auth/csrf',headers={'Origin':ORIGIN})
    assert response.status_code==200,response.text
    return {'Origin':ORIGIN,'X-CSRF-Token':response.json()['csrf_token']}


@pytest.fixture
def signed_in(secured):
    active_account(secured)
    with TestClient(secured,base_url=BASE) as client:
        assert login(client).status_code==200
        yield client,secured


@pytest.mark.parametrize('method,path',PRIVATE)
def test_every_student_operation_denies_anonymous_before_parsing(secured,isolated_storage,method,path):
    with TestClient(secured,base_url=BASE) as client:
        response=client.request(method,actual(path),content='not-json',headers={'Origin':ORIGIN})
    assert response.status_code==401 and response.json()=={'detail':'Authentication is required.'}
    assert response.headers['Cache-Control']=='private, no-store'
    assert not isolated_storage.auth_db.exists()
    assert not list(isolated_storage.profiles.iterdir()) and not list(isolated_storage.assessments.iterdir())
    assert not isolated_storage.goals_db.exists()


@pytest.mark.parametrize('method,path',DEFERRED)
def test_every_student_operation_denies_authenticated_accounts_pending_ownership(signed_in,method,path,isolated_storage):
    client,app=signed_in
    headers=csrf(client)
    before=app.state.accounts.store.path.read_bytes()
    response=client.request(method,actual(path),content='malformed-secret-body',headers=headers)
    assert response.status_code==503 and response.json()=={'detail':OWNERSHIP_PENDING}
    assert app.state.accounts.store.path.read_bytes()==before  # Denied work does not extend idle TTL.
    assert not list(isolated_storage.profiles.iterdir()) and not list(isolated_storage.assessments.iterdir())


@pytest.mark.parametrize('method,path',[op for op in PRIVATE if op[0]!='GET' or op[1] in SIDE_EFFECT_GET])
def test_private_mutations_and_lifecycle_gets_require_csrf_before_pending_ownership(signed_in,method,path):
    client,_=signed_in
    response=client.request(method,actual(path),headers={'Origin':ORIGIN},content='not-json')
    assert response.status_code==403 and response.json()=={'detail':'CSRF validation failed.'}


def test_inventory_contains_all_application_operations_and_defaults_private():
    assert len(OPERATIONS)==50 and len({path for _,path in OPERATIONS})==45
    assert len(PRIVATE)==38 and len(DEFERRED)==2 and len(PROFILES)==10 and len(ASSESSMENTS)==4 and len(ANALYTICS)==11 and len(GOALS)==11 and len(PUBLIC)==3 and len(ENTRY)==3 and len(SESSION)==4 and len(OAUTH)==2
    assert set(PRIVATE).isdisjoint(PUBLIC | ENTRY | SESSION | OAUTH)
    assert OAUTH=={('GET','/api/auth/google/start'),('GET','/api/auth/google/callback')}


def test_real_login_session_csrf_restore_logout_and_revoked_cookie(signed_in):
    client,app=signed_in
    secret=client.cookies.get(app.state.security_config.cookie_name)
    restored=client.get('/api/auth/session')
    assert restored.status_code==200 and set(restored.json())=={'account','idle_expires_at','absolute_expires_at'}
    assert set(restored.json()['account'])=={'account_id','email'}
    headers=csrf(client)
    assert csrf(client)==headers  # Stable per-session token for concurrent tabs.
    response=client.post('/api/auth/logout',headers=headers)
    assert response.status_code==204 and not response.content
    assert client.post('/api/auth/logout',headers={'Origin':ORIGIN}).status_code==204
    with TestClient(app,base_url=BASE) as attacker:
        attacker.cookies.set(app.state.security_config.cookie_name,secret)
        assert attacker.get('/api/auth/session').status_code==401
        assert attacker.get('/api/auth/csrf',headers={'Origin':ORIGIN}).status_code==401
        assert attacker.post('/api/auth/logout',headers=headers).status_code==204


@pytest.mark.parametrize('case',['unknown','wrong','pending','disabled','deactivated','corrupt','unverified'])
def test_login_failure_is_generic_and_never_creates_sessions(secured,case):
    if case!='unknown':
        active_account(secured,status={'pending':'PENDING_EMAIL','disabled':'DISABLED','deactivated':'DEACTIVATED'}.get(case,'ACTIVE'))
        with sqlite3.connect(secured.state.accounts.store.path) as c:
            if case=='corrupt':
                c.execute("UPDATE accounts SET password_hash='$argon2id$garbage'")
            if case=='unverified':
                c.execute('PRAGMA ignore_check_constraints=ON')
                c.execute('UPDATE accounts SET email_verified_at=NULL')
    with TestClient(secured,base_url=BASE) as client:
        response=login(client,password='Incorrect synthetic passphrase' if case=='wrong' else PASSWORD)
        assert response.status_code==401 and response.json()=={'detail':'Invalid credentials.'}
        assert 'set-cookie' not in response.headers
    with sqlite3.connect(secured.state.accounts.store.path) as c:
        assert c.execute('SELECT count(*) FROM sessions').fetchone()[0]==0


def test_login_requires_bootstrap_csrf_origin_before_credentials_and_body(secured,monkeypatch,isolated_storage):
    def must_not_run(*args):
        pytest.fail('Credential verification executed before login CSRF rejection.')
    monkeypatch.setattr(secured.state.accounts,'verify_credentials',must_not_run)
    with TestClient(secured,base_url=BASE) as client:
        assert client.post('/api/auth/login',content='sensitive-invalid-body',headers={'Origin':ORIGIN}).status_code==403
        assert client.post('/api/auth/login',content='not-json').status_code==403
        assert client.get('/api/auth/login-challenge',headers={'Origin':'https://attacker.example.test'}).status_code==403
    assert not isolated_storage.auth_db.exists()


@pytest.mark.parametrize('body',[{}, {'email':'bad','password':PASSWORD}, {'email':'one@example.org','password':'x'*129}])
def test_login_validation_errors_redact_inputs(secured,body):
    with TestClient(secured,base_url=BASE) as client:
        token=client.get('/api/auth/login-challenge',headers={'Origin':ORIGIN}).json()['csrf_token']
        response=client.post('/api/auth/login',headers={'Origin':ORIGIN,'X-CSRF-Token':token},json=body)
        assert response.status_code==422 and PASSWORD not in response.text and 'input' not in response.text


def test_oversized_login_body_is_bounded_and_redacted(secured):
    with TestClient(secured,base_url=BASE) as client:
        token=client.get('/api/auth/login-challenge',headers={'Origin':ORIGIN}).json()['csrf_token']
        response=client.post('/api/auth/login',headers={'Origin':ORIGIN,'X-CSRF-Token':token},content='private'*4000)
        assert response.status_code==413 and 'private' not in response.text


def test_registration_stays_unavailable_before_parsing_and_no_activation_route(secured,isolated_storage):
    with TestClient(secured,base_url=BASE) as client:
        response=client.post('/api/auth/register',content='not-json')
        assert response.status_code==503 and 'verification' in response.text and 'set-cookie' not in response.headers
        assert client.post('/api/auth/email/verify',json={'account_id':'spoofed'}).status_code==401
    assert not isolated_storage.auth_db.exists()


@pytest.mark.parametrize('mode',['production','development'])
def test_cookie_policy_is_explicit_host_only_and_httponly(mode,isolated_storage):
    origin=ORIGIN if mode=='production' else 'http://127.0.0.1:5173'
    base=BASE if mode=='production' else 'http://127.0.0.1:8765'
    app=create_app(SecurityConfig(mode=mode,origins=(origin,)))
    active_account(app)
    with TestClient(app,base_url=base,client=('127.0.0.1',50000)) as client:
        challenge=client.get('/api/auth/login-challenge',headers={'Origin':origin})
        response=client.post('/api/auth/login',headers={'Origin':origin,'X-CSRF-Token':challenge.json()['csrf_token']},
                             json={'email':'one@example.org','password':PASSWORD})
        assert response.status_code==200,response.text
        cookie=response.headers.get_list('set-cookie')[0]
        assert 'HttpOnly' in cookie and 'SameSite=lax' in cookie and 'Path=/' in cookie
        assert 'Domain=' not in cookie and 'Max-Age=' not in cookie
        assert ('Secure' in cookie)==(mode=='production')
        assert cookie.startswith(app.state.security_config.cookie_name+'=')
        assert PASSWORD not in cookie and 'one@example.org' not in cookie


def test_production_http_never_silently_uses_development_cookie(secured,isolated_storage):
    with TestClient(secured,base_url='http://127.0.0.1:8765') as client:
        assert client.get('/api/auth/login-challenge',headers={'Origin':ORIGIN}).status_code==403
    assert not isolated_storage.auth_db.exists()


@pytest.mark.parametrize('config',[
    {'origins':('*',)}, {'origins':('http://frontend.example.test',)}, {'origins':('https://frontend.example.test/path',)},
    {'origins':('null',)}, {'mode':'development','origins':('http://external.example.test',)}, {'mode':'invalid'},
])
def test_invalid_security_configuration_fails_closed(config):
    with pytest.raises(ValueError):
        SecurityConfig(**config)


def test_localhost_and_127_cookies_are_not_interchangeable(isolated_storage):
    config=SecurityConfig(mode='development',origins=('http://127.0.0.1:5173','http://localhost:5173'))
    app=create_app(config)
    active_account(app)
    with TestClient(app,base_url='http://127.0.0.1:8765',client=('127.0.0.1',50000)) as client:
        challenge=client.get('/api/auth/login-challenge',headers={'Origin':config.origins[0]}).json()
        assert client.post('/api/auth/login',headers={'Origin':config.origins[0],'X-CSRF-Token':challenge['csrf_token']},
                           json={'email':'one@example.org','password':PASSWORD}).status_code==200
        assert client.get('http://localhost:8765/api/auth/session').status_code==401
        assert client.get('/api/auth/session').status_code==200


@pytest.mark.parametrize('token',['missing','invalid','other-session','other-account'])
def test_logout_and_renew_reject_wrong_csrf_without_mutation(signed_in,token):
    client,app=signed_in
    if token.startswith('other'):
        if token=='other-account':
            active_account(app,'two@example.org')
        with TestClient(app,base_url=BASE) as other:
            assert login(other,email='two@example.org' if token=='other-account' else 'one@example.org').status_code==200
            headers=csrf(other)
    else:
        headers={'Origin':ORIGIN}
        if token=='invalid':
            headers['X-CSRF-Token']='0'*64
    before=app.state.accounts.store.path.read_bytes()
    assert client.post('/api/auth/logout',headers=headers).status_code==403
    assert client.post('/api/auth/session/renew',headers=headers).status_code==403
    assert app.state.accounts.store.path.read_bytes()==before
    assert client.get('/api/auth/session').status_code==200


def test_rotation_cookie_and_token_replacement(signed_in):
    client,app=signed_in
    old=client.cookies.get(app.state.security_config.cookie_name)
    headers=csrf(client)
    response=client.post('/api/auth/session/renew',headers=headers)
    assert response.status_code==200 and client.cookies.get(app.state.security_config.cookie_name)!=old
    assert csrf(client)!=headers
    with TestClient(app,base_url=BASE) as stale:
        stale.cookies.set(app.state.security_config.cookie_name,old)
        assert stale.get('/api/auth/session').status_code==401
        assert stale.post('/api/auth/logout',headers=headers).status_code==204
    assert client.get('/api/auth/session').status_code==401


@pytest.mark.parametrize('endpoint',['/api/auth/csrf','/api/auth/login-challenge'])
def test_tokens_not_disclosed_to_missing_or_disallowed_origins(signed_in,endpoint):
    client,_=signed_in
    for headers in ({},{'Origin':'null'},{'Origin':'https://evil.example.test'}):
        response=client.get(endpoint,headers=headers)
        assert response.status_code==403 and 'csrf_token' not in response.text


def test_cors_preflight_and_origin_policies(secured,isolated_storage):
    with TestClient(secured,base_url=BASE) as client:
        good={'Origin':ORIGIN,'Access-Control-Request-Method':'POST',
              'Access-Control-Request-Headers':'content-type,x-csrf-token'}
        accepted=client.options('/api/assessment/start',headers=good)
        assert accepted.status_code==200
        assert accepted.headers['Access-Control-Allow-Origin']==ORIGIN
        assert accepted.headers['Access-Control-Allow-Credentials']=='true'
        for changed in ({'Origin':'https://evil.example.test'},{'Access-Control-Request-Method':'TRACE'},
                        {'Access-Control-Request-Headers':'authorization'}):
            rejected=client.options('/api/assessment/start',headers=good|changed)
            assert rejected.status_code==400
        deletion=client.options('/api/profile/example/goals/example',headers=good|{'Access-Control-Request-Method':'DELETE'})
        assert deletion.status_code==200
        assert client.get('/health',headers={'Origin':'https://evil.example.test'}).status_code==200
        assert 'Access-Control-Allow-Origin' not in client.get('/health',headers={'Origin':'https://evil.example.test'}).headers
    assert not isolated_storage.auth_db.exists() and not list(isolated_storage.assessments.iterdir())


def test_origin_mismatch_and_duplicate_security_headers_do_not_mutate(signed_in):
    client,app=signed_in
    good=csrf(client)
    before=app.state.accounts.store.path.read_bytes()
    response=client.post('/api/auth/logout',headers=good|{'Origin':'https://evil.example.test'})
    assert response.status_code==403 and app.state.accounts.store.path.read_bytes()==before
    assert client.post('/api/auth/logout',headers=[('Origin',ORIGIN),('X-CSRF-Token',good['X-CSRF-Token']),
                                                ('X-CSRF-Token',good['X-CSRF-Token'])]).status_code==403
    assert client.get('/api/auth/csrf',headers=[('Origin',ORIGIN),('Origin',ORIGIN)]).status_code==403


@pytest.mark.parametrize('method,path',[('HEAD','/api/companies'),('POST','/api/companies'),('OPTIONS','/api/profile/synthetic-profile'),
    ('PATCH','/api/profile/synthetic-profile'),('DELETE','/health'),('GET','/api/unknown'),
    ('POST','/api/auth/login/'),('GET','/api/profile/synthetic-profile/'),('GET','/api//companies')])
def test_variants_unknown_paths_and_unsupported_methods_cannot_bypass_gate(secured,method,path):
    with TestClient(secured,base_url=BASE) as client:
        response=client.request(method,path,headers={'Origin':ORIGIN},follow_redirects=False)
        assert response.status_code==401,response.text


def test_authenticated_unknown_and_unsupported_methods_have_controlled_semantics(signed_in):
    client,_=signed_in
    headers=csrf(client)
    assert client.get('/api/unknown').status_code==404
    assert client.post('/api/unknown',headers=headers).status_code==404
    assert client.delete('/api/profile/synthetic-profile',headers=headers).status_code==405
    assert client.delete('/api/profile/synthetic-profile',headers={'Origin':ORIGIN}).status_code==403


def test_new_api_route_defaults_private_without_policy_opt_in(secured):
    called=[]
    @secured.get('/api/new-private-route')
    def future():
        called.append(True)
        return {'private':'synthetic'}
    active_account(secured)
    with TestClient(secured,base_url=BASE) as client:
        assert client.get('/api/new-private-route').status_code==401
        assert login(client).status_code==200
        assert client.get('/api/new-private-route').status_code==503
    assert not called


@pytest.mark.parametrize('mode',['production','development'])
def test_framework_documentation_policy(mode,isolated_storage):
    app=create_app(SecurityConfig(mode=mode))
    base=BASE if mode=='production' else 'http://127.0.0.1:8765'
    with TestClient(app,base_url=base,client=('127.0.0.1',50000)) as client:
        for path in ('/docs','/docs/oauth2-redirect','/redoc','/openapi.json'):
            for method in ('GET','HEAD'):
                assert client.request(method,path).status_code==(404 if mode=='production' else 200)
        assert client.post('/docs').status_code==404
    assert not isolated_storage.auth_db.exists()


def test_public_health_and_company_contracts(secured,isolated_storage):
    with TestClient(secured,base_url=BASE) as client:
        assert client.get('/health').json()['status']=='ok'
        assert client.get('/api/companies').status_code==200
        assert client.get('/api/companies/company_001').status_code==200
        assert client.get('/api/companies/missing-synthetic').status_code==404
    assert not isolated_storage.auth_db.exists() and not list(isolated_storage.profiles.iterdir())


def test_denied_lifecycle_gets_cannot_expire_or_recover_synthetic_attempts(signed_in,isolated_storage,monkeypatch):
    from datetime import datetime,timezone
    from backend.tests.domain_app import app as domain
    from backend.tests.test_ownership_access_audit import synthetic,confirm,start,submit
    from backend.app.services import assessment_service as assessments
    client,application=signed_in
    monkeypatch.setattr(assessments,'_utc_now',lambda:datetime(2026,11,8,tzinfo=timezone.utc))
    with TestClient(domain) as business:
        profile=confirm(business,synthetic('synthetic-profile'))
        expiring=start(business,profile['profile_id'],'SQL')
        accepted=start(business,profile['profile_id'])
        with monkeypatch.context() as patch:
            patch.setattr(assessments,'_save_profile',lambda body:(_ for _ in ()).throw(OSError('synthetic projection failure')))
            assert submit(business,accepted,profile['profile_id']).status_code==500
    monkeypatch.setattr(assessments,'_utc_now',lambda:datetime(2026,11,10,tzinfo=timezone.utc))
    def snapshot():
        return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for directory in (isolated_storage.profiles,isolated_storage.assessments)
                for p in directory.rglob('*') if p.is_file()}
    before=snapshot()
    headers=csrf(client)
    with TestClient(application,base_url=BASE) as anonymous:
        for path in ('/api/assessment/'+expiring['assessment_id'],'/api/profile/synthetic-profile/assessments'):
            assert anonymous.get(path).status_code==401
            assert client.get(path,headers={'Origin':ORIGIN}).status_code==403
            assert client.get(path,headers=headers).status_code==404
    assert snapshot()==before
    assert assessments._load_session(accepted['assessment_id'])['status']=='SUBMITTING'
    assert assessments._load_session(expiring['assessment_id'])['status']=='IN_PROGRESS'


def test_authenticated_identity_cannot_be_changed_by_supplied_account_or_profile_id(signed_in):
    client,app=signed_in
    identity=client.get('/api/auth/session').json()['account']
    response=client.get('/api/auth/session?account_id=other&profile_id=other',headers={'X-Account-ID':'other'})
    assert response.json()['account']==identity
    assert client.get('/api/profile/other').status_code==404


def test_no_password_session_hash_or_csrf_logging(signed_in,caplog):
    client,app=signed_in
    secret=client.cookies.get(app.state.security_config.cookie_name)
    headers=csrf(client)
    account=app.state.accounts.store.get_by_email('one@example.org')
    response=client.get('/api/auth/session')
    assert PASSWORD not in caplog.text and secret not in caplog.text and headers['X-CSRF-Token'] not in caplog.text
    assert account.password_hash not in caplog.text and account.password_hash not in response.text and secret not in response.text


def test_storage_failure_returns_generic_503_without_cookie(secured,monkeypatch):
    from backend.app.services.account_store import AccountStorageError
    def fail():
        raise AccountStorageError()
    monkeypatch.setattr(secured.state.sessions,'challenge',fail)
    with TestClient(secured,base_url=BASE) as client:
        response=client.get('/api/auth/login-challenge',headers={'Origin':ORIGIN})
        assert response.status_code==503 and 'set-cookie' not in response.headers
        assert response.headers['Access-Control-Allow-Origin']==ORIGIN


def test_concurrent_login_creates_independent_sessions(secured):
    active_account(secured)
    def request(_):
        with TestClient(secured,base_url=BASE) as client:
            response=login(client)
            assert response.status_code==200,response.text
            return client.cookies.get(secured.state.security_config.cookie_name)
    with ThreadPoolExecutor(max_workers=3) as pool:
        secrets=list(pool.map(request,range(3)))
    assert len(set(secrets))==3
    assert len({secured.state.sessions.resolve(s).session_id for s in secrets})==3


def test_account_changing_login_revokes_previous_browser_session(signed_in):
    from backend.app.services.session_service import InvalidSession
    client,app=signed_in
    previous=client.cookies.get(app.state.security_config.cookie_name)
    first=client.get('/api/auth/session').json()['account']['account_id']
    active_account(app,'two@example.org')
    assert login(client,email='two@example.org').status_code==200
    assert client.get('/api/auth/session').json()['account']['account_id'] != first
    with pytest.raises(InvalidSession):
        app.state.sessions.resolve(previous)


def test_session_capacity_returns_409_without_revoking_other_browsers(secured):
    app=secured
    from dataclasses import replace
    app.state.sessions.config=replace(app.state.sessions.config,max_sessions=1)
    active_account(app)
    with TestClient(app,base_url=BASE) as first, TestClient(app,base_url=BASE) as second:
        assert login(first).status_code==200
        rejected=login(second)
        assert rejected.status_code==409 and 'set-cookie' not in rejected.headers
        assert first.get('/api/auth/session').status_code==200
        # Re-authenticating this browser can replace its own session at capacity.
        assert login(first).status_code==200


def test_production_default_gate_remains_enabled_despite_unsupported_bypass_variables(monkeypatch,isolated_storage):
    monkeypatch.setenv('PLACEPRO_AUTH_DISABLED','true')
    monkeypatch.setenv('PLACEPRO_AUTH_FOUNDATION_ENABLED','true')
    monkeypatch.setenv('PLACEPRO_SECURITY_MODE','production')
    monkeypatch.delenv('PLACEPRO_ALLOWED_ORIGINS',raising=False)
    app=create_app()
    assert app.state.security_config.secure and app.state.security_config.origins==()
    with TestClient(app,base_url=BASE) as client:
        assert client.get('/api/profile/synthetic-profile').status_code==401
        assert client.get('/api/auth/login-challenge',headers={'Origin':ORIGIN}).status_code==403
    with TestClient(app,base_url='http://127.0.0.1:8765') as client:
        assert client.get('/api/profile/synthetic-profile').status_code==401
    assert not isolated_storage.auth_db.exists()


def test_durable_login_failure_does_not_issue_session_cookie(secured,monkeypatch):
    from backend.app.services.account_store import AccountStorageError
    active_account(secured)
    def fail(*args,**kwargs):
        raise AccountStorageError()
    monkeypatch.setattr(secured.state.sessions,'create',fail)
    with TestClient(secured,base_url=BASE) as client:
        response=login(client)
        assert response.status_code==503 and 'set-cookie' not in response.headers
        assert response.json()=={'detail':'Account processing is temporarily unavailable.'}


def test_forged_modified_and_duplicate_cookies_do_not_resolve(signed_in):
    client,app=signed_in
    name=app.state.security_config.cookie_name
    secret=client.cookies.get(name)
    with TestClient(app,base_url=BASE) as other:
        for cookie in ('x'*43,secret[:-1]+('A' if secret[-1]!='A' else 'B')):
            assert other.get('/api/auth/session',headers={'Cookie':name+'='+cookie}).status_code==401
        ambiguous=name+'='+secret+'; '+name+'='+secret
        assert other.get('/api/auth/session',headers={'Cookie':ambiguous}).status_code==401
        assert other.post('/api/auth/logout',headers={'Cookie':ambiguous,'Origin':ORIGIN}).status_code==401


@pytest.mark.parametrize('boundary',['idle','absolute'])
def test_expired_cookie_cannot_restore_or_retrieve_csrf(signed_in,boundary):
    client,app=signed_in
    identity=app.state.sessions.resolve(client.cookies.get(app.state.security_config.cookie_name))
    app.state.sessions.clock=lambda:identity.idle_expires_at if boundary=='idle' else identity.absolute_expires_at
    assert client.get('/api/auth/session').status_code==401
    assert client.get('/api/auth/csrf',headers={'Origin':ORIGIN}).status_code==401


def test_account_disable_rejects_existing_cookie_without_touching_student_records(signed_in,isolated_storage):
    client,app=signed_in
    with sqlite3.connect(app.state.accounts.store.path) as c:
        c.execute("UPDATE accounts SET status='DISABLED'")
    assert client.get('/api/auth/session').status_code==401
    assert client.post('/api/assessment/start',headers={'Origin':ORIGIN,'X-CSRF-Token':'0'*64}).status_code==401
    assert not list(isolated_storage.profiles.iterdir()) and not list(isolated_storage.assessments.iterdir())


def test_development_mode_rejects_remote_client_with_spoofed_loopback_host(isolated_storage):
    app=create_app(SecurityConfig(mode='development',origins=('http://127.0.0.1:5173',)))
    with TestClient(app,base_url='http://127.0.0.1:8765',client=('203.0.113.10',50000)) as remote:
        assert remote.get('/api/auth/login-challenge',headers={'Origin':'http://127.0.0.1:5173'}).status_code==403
        assert remote.get('/docs').status_code==404
    assert not isolated_storage.auth_db.exists()
