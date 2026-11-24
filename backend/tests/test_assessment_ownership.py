"""Real secured ASGI assessment ownership, with synthetic accounts and temporary JSON."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3
from threading import Barrier
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from backend.app.routes.owned_assessment import create_owned_assessment_router
from backend.app.services import assessment_service as assessments, profile_service as profiles
from backend.app.services.ownership_store import OwnershipUnavailable
from backend.tests.test_profile_ownership import pair, encoded_password, create, identity
from backend.tests.test_assessment_lifecycle import clock
from backend.tests.test_session_security import ASSESSMENTS, DEFERRED, BASE, ORIGIN


@pytest.fixture
def owned(pair, clock):
    app,a,b,ha,hb=pair
    pa,pb=create(a,ha),create(b,hb)
    return app,a,b,ha,hb,pa,pb,clock


def start(owned, *, client=None, headers=None, profile=None, skill='Python', count=5):
    app,a,b,ha,hb,pa,pb,clock=owned
    return (client or a).post('/api/assessment/start',json={
        'profile_id':profile or pa['profile_id'],'skill':skill,'num_questions':count},headers=headers or ha)


def session(owned, **kwargs):
    response=start(owned,**kwargs)
    assert response.status_code==200,response.text
    return response.json()


def answers(value):
    keys={q['id']:q['correct_answer'] for q in assessments.get_questions(value['skill'])}
    return {q['question_id']:keys[q['question_id']] for q in value['questions']}


def submit(owned,value, *, client=None,headers=None,profile=None,values=None):
    _,a,_,ha,_,pa,_,_=owned
    return (client or a).post('/api/assessment/'+value['assessment_id']+'/submit',
                            json={'profile_id':profile or pa['profile_id'],'answers':answers(value) if values is None else values},
                            headers=headers or ha)


def snapshot(storage):
    # Metadata-reader locks are necessary before discovering a session's stored profile.
    return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for directory in (storage.profiles,storage.assessments)
            for p in directory.glob('*.json')}


def test_owned_start_get_submit_history_and_profile_revision_are_bound_to_same_account(owned):
    app,a,b,ha,hb,pa,pb,clock=owned
    value=session(owned)
    stored=assessments._load_session(value['assessment_id'])
    assert stored['account_id']==identity(app,a).account_id and stored['profile_id']==pa['profile_id']
    assert stored['ownership_schema_version']==1 and stored['profile_ownership_version']==2
    assert value['attempt']==1 and len(value['questions'])==5
    for field in ('account_id','profile_ownership_version','ownership_schema_version','answers','correct_answer','correct_ids','score_report','explanation'):
        assert '"'+field+'"' not in json.dumps(value)
    loaded=a.get('/api/assessment/'+value['assessment_id'],headers=ha)
    assert loaded.status_code==200 and loaded.json()['status']=='IN_PROGRESS'
    result=submit(owned,value)
    assert result.status_code==200 and result.json()['skill_score']==100
    assert a.get('/api/assessment/'+value['assessment_id'],headers=ha).json()['result']==result.json()
    history=a.get('/api/profile/'+pa['profile_id']+'/assessments',headers=ha)
    assert history.status_code==200 and len(history.json()['assessments'])==1
    assert 'account_id' not in history.text
    saved=profiles._load(pa['profile_id'])
    assert saved['revision']==pa['revision']+1 and saved['verified'] is True
    assert saved['assessment_evidence'][0]['account_id']==identity(app,a).account_id
    for field in ('skills','ml_inputs','provenance','original_resume_values','prediction_history'):
        assert saved[field]==pa[field] if field in pa else saved[field]==[]
    assert profiles._load(pb['profile_id'])['assessment_evidence']==[]
    assert submit(owned,value).status_code==409
    assert len(profiles._load(pa['profile_id'])['assessment_evidence'])==1


@pytest.mark.parametrize('operation',['start','get','submit','history'])
@pytest.mark.parametrize('failure',['anonymous','forged-session','revoked-session','csrf','origin','cross-csrf'])
def test_authentication_and_csrf_rejections_precede_any_lifecycle_mutation(owned,isolated_storage,operation,failure):
    app,a,b,ha,hb,pa,pb,clock=owned
    value=session(owned)
    clock.advance(minutes=10)
    before=snapshot(isolated_storage)
    headers=ha
    if failure=='csrf':
        headers={'Origin':ORIGIN}
    elif failure=='origin':
        headers=ha|{'Origin':'https://foreign.example.test'}
    elif failure=='cross-csrf':
        headers=ha|{'X-CSRF-Token':hb['X-CSRF-Token']}
    if failure in {'anonymous','forged-session'}:
        client=TestClient(app,base_url=BASE)
        if failure=='forged-session':
            client.cookies.set(app.state.security_config.cookie_name,'x'*43)
    else:
        client=a
    if failure=='revoked-session':
        app.state.sessions.revoke_account(identity(app,a).account_id)
    try:
        if operation=='start':
            response=client.post('/api/assessment/start',json={'profile_id':pa['profile_id'],'skill':'Python'},headers=headers)
        elif operation=='get':
            response=client.get('/api/assessment/'+value['assessment_id'],headers=headers)
        elif operation=='submit':
            response=client.post('/api/assessment/'+value['assessment_id']+'/submit',json={'profile_id':pa['profile_id'],'answers':answers(value)},headers=headers)
        else:
            response=client.get('/api/profile/'+pa['profile_id']+'/assessments',headers=headers)
        assert response.status_code==(401 if failure in {'anonymous','forged-session','revoked-session'} else 403)
    finally:
        if client is not a:
            client.close()
    assert snapshot(isolated_storage)==before


def test_cross_account_operations_and_known_correct_answers_do_not_disclose_or_mutate(owned,isolated_storage):
    _,a,b,ha,hb,pa,pb,clock=owned
    value=session(owned)
    clock.advance(minutes=10)
    before=snapshot(isolated_storage)
    responses=[start(owned,client=b,headers=hb,profile=pa['profile_id']),
               b.get('/api/assessment/'+value['assessment_id'],headers=hb),
               submit(owned,value,client=b,headers=hb),
               b.get('/api/profile/'+pa['profile_id']+'/assessments',headers=hb)]
    assert [r.status_code for r in responses]==[404]*4
    for response in responses:
        for sensitive in (pa['profile_id'],value['assessment_id'],'questions','attempt','answers','score','IN_PROGRESS','cooldown'):
            assert sensitive not in response.text
    assert snapshot(isolated_storage)==before
    missing=b.get('/api/assessment/'+str(uuid.uuid4()),headers=hb)
    assert missing.json()==responses[1].json()
    other=session(owned,client=b,headers=hb,profile=pb['profile_id'])
    assert a.get('/api/assessment/'+other['assessment_id'],headers=ha).json()==missing.json()


@pytest.mark.parametrize('status',['legacy','PENDING','SUSPENDED','FAILED','corrupt'])
def test_non_active_or_unowned_profiles_deny_start_history_and_assessments(owned,isolated_storage,status):
    app,a,b,ha,hb,pa,pb,clock=owned
    value=session(owned)
    if status=='legacy':
        legacy=str(uuid.uuid4())
        profiles.verify_profile({'profile_id':legacy,'personal':{'name':'Synthetic Legacy','email':'one@example.org'}})
        selected=legacy
        record=deepcopy(assessments._load_session(value['assessment_id']))
        record['assessment_id']=str(uuid.uuid4())
        record['profile_id']=selected
        record.pop('account_id')
        assessments._save_session(record)
        target=record['assessment_id']
    else:
        selected=pa['profile_id']; target=value['assessment_id']
        with sqlite3.connect(app.state.accounts.store.path) as c:
            if status=='corrupt':
                c.execute('PRAGMA ignore_check_constraints=ON')
            c.execute('UPDATE profile_ownership SET status=? WHERE profile_id=?',('INVALID' if status=='corrupt' else status,selected))
    clock.advance(minutes=10)
    before=snapshot(isolated_storage)
    assert start(owned,profile=selected).status_code==404
    assert a.get('/api/profile/'+selected+'/assessments',headers=ha).status_code==404
    assert a.get('/api/assessment/'+target,headers=ha).status_code==404
    assert submit(owned,{'assessment_id':target,'skill':value['skill'],'questions':value['questions']},profile=selected).status_code==404
    assert snapshot(isolated_storage)==before


@pytest.mark.parametrize('field',['account_id','owner_id','profile_ownership_version','ownership_schema_version'])
def test_client_identity_metadata_cannot_override_start_or_submission(owned,isolated_storage,field):
    app,a,b,ha,hb,pa,pb,clock=owned
    value=session(owned)
    before=snapshot(isolated_storage)
    for response in (a.post('/api/assessment/start',json={'profile_id':pa['profile_id'],'skill':'Python',field:identity(app,b).account_id},headers=ha),
                     a.post('/api/assessment/'+value['assessment_id']+'/submit',json={'profile_id':pa['profile_id'],'answers':answers(value),field:identity(app,b).account_id},headers=ha)):
        assert response.status_code==422 and identity(app,b).account_id not in response.text
    assert snapshot(isolated_storage)==before


@pytest.mark.parametrize('field',['account_id','profile_id','assessment_id','profile_ownership_version','ownership_schema_version'])
def test_mismatched_session_binding_fails_before_recovery_or_expiry(owned,isolated_storage,field):
    app,a,b,ha,hb,pa,pb,clock=owned
    value=session(owned)
    record=assessments._load_session(value['assessment_id'])
    record[field]=identity(app,b).account_id if field=='account_id' else pb['profile_id'] if field=='profile_id' else str(uuid.uuid4()) if field=='assessment_id' else 0
    Path(assessments._session_path(value['assessment_id'])).write_text(json.dumps(record),encoding='utf-8')
    clock.advance(minutes=10)
    before=snapshot(isolated_storage)
    assert a.get('/api/assessment/'+value['assessment_id'],headers=ha).status_code==404
    assert submit(owned,value).status_code==404
    assert snapshot(isolated_storage)==before


def test_client_profile_mismatch_is_rejected_before_answer_validation(owned,isolated_storage):
    _,a,b,ha,hb,pa,pb,clock=owned
    extra=create(a,ha)
    value=session(owned)
    before=snapshot(isolated_storage)
    response=a.post('/api/assessment/'+value['assessment_id']+'/submit',json={'profile_id':extra['profile_id'],'answers':'PRIVATE-MARKER'},headers=ha)
    assert response.status_code==404 and 'PRIVATE-MARKER' not in response.text
    assert snapshot(isolated_storage)==before


def test_legacy_unbound_records_on_owned_profile_are_not_recovered_expired_counted_or_returned(owned,isolated_storage):
    _,a,b,ha,hb,pa,pb,clock=owned
    legacy=assessments.start_assessment(pa['profile_id'],'Python',5)
    legacy_record=assessments._load_session(legacy['assessment_id'])
    legacy_record.update(status='SUBMITTING',answers=answers(legacy),submitted_at=clock.now.isoformat(),
                         score_report=assessments.compute_score(legacy_record,answers(legacy)))
    assessments._save_session(legacy_record)
    retained=Path(assessments._session_path(legacy['assessment_id'])).read_bytes()
    history=a.get('/api/profile/'+pa['profile_id']+'/assessments',headers=ha)
    assert history.status_code==200 and history.json()['assessments']==[]
    assert a.get('/api/assessment/'+legacy['assessment_id'],headers=ha).status_code==404
    value=session(owned)
    assert value['attempt']==1 and submit(owned,value).status_code==200
    assert Path(assessments._session_path(legacy['assessment_id'])).read_bytes()==retained
    assert len(a.get('/api/profile/'+pa['profile_id']+'/assessments',headers=ha).json()['assessments'])==1


def test_concurrent_reservations_and_submissions_preserve_quota_and_unique_attempts(owned):
    app,a,b,ha,hb,pa,pb,clock=owned
    barrier=Barrier(6)
    def reserve(_):
        barrier.wait(timeout=10)
        return start(owned)
    with ThreadPoolExecutor(max_workers=6) as pool:
        results=list(pool.map(reserve,range(6)))
    assert sorted(r.status_code for r in results)==[200]*3+[429]*3
    successful=[r.json() for r in results if r.status_code==200]
    assert sorted(r['attempt'] for r in successful)==[1,2,3]
    barrier=Barrier(6)
    def complete(_):
        barrier.wait(timeout=10)
        return submit(owned,successful[0])
    with ThreadPoolExecutor(max_workers=6) as pool:
        results=list(pool.map(complete,range(6)))
    assert sorted(r.status_code for r in results)==[200]+[409]*5
    assert len(profiles._load(pa['profile_id'])['assessment_evidence'])==1


def test_deadlines_expired_reservations_cooldown_and_retake_remain_server_controlled(owned):
    _,a,b,ha,hb,pa,pb,clock=owned
    first,second,third=[session(owned) for _ in range(3)]
    assert submit(owned,first).status_code==200
    assert submit(owned,second).status_code==429
    clock.advance(minutes=5)
    assert submit(owned,second).status_code==410
    assert a.get('/api/assessment/'+third['assessment_id'],headers=ha).status_code==410
    clock.advance(hours=24)
    retake=session(owned)
    assert retake['attempt']==4 and submit(owned,retake).status_code==200
    assert [e['attempt'] for e in profiles._load(pa['profile_id'])['assessment_evidence']]==[1,4]


@pytest.mark.parametrize('write',['profile','completion'])
def test_failed_projection_remains_recoverable_only_by_owner_after_deadline(owned,isolated_storage,monkeypatch,write):
    app,a,b,ha,hb,pa,pb,clock=owned
    value=session(owned)
    name='_save_profile' if write=='profile' else '_save_session'
    original=getattr(assessments,name)
    failed=False
    def fail(record,**kw):
        nonlocal failed
        if not failed and (write=='profile' or record['status']=='COMPLETED'):
            failed=True
            raise OSError('SYNTHETIC-PRIVATE-PERSISTENCE-PATH')
        return original(record,**kw)
    monkeypatch.setattr(assessments,name,fail)
    response=submit(owned,value)
    assert response.status_code==503 and 'PRIVATE-PERSISTENCE' not in response.text
    assert assessments._load_session(value['assessment_id'])['status']=='SUBMITTING'
    clock.advance(minutes=10)
    before=snapshot(isolated_storage)
    assert b.get('/api/assessment/'+value['assessment_id'],headers=hb).status_code==404
    assert b.get('/api/profile/'+pa['profile_id']+'/assessments',headers=hb).status_code==404
    assert snapshot(isolated_storage)==before
    def no_rescore(*args):
        pytest.fail('Accepted submission must not be scored again')
    monkeypatch.setattr(assessments,'compute_score',no_rescore)
    restored=a.get('/api/assessment/'+value['assessment_id'],headers=ha)
    assert restored.status_code==200 and restored.json()['status']=='COMPLETED'
    assert len(profiles._load(pa['profile_id'])['assessment_evidence'])==1
    revision=profiles._load(pa['profile_id'])['revision']
    assert a.get('/api/assessment/'+value['assessment_id'],headers=ha).status_code==200
    assert submit(owned,value).status_code==409
    assert profiles._load(pa['profile_id'])['revision']==revision


@pytest.mark.parametrize('operation',['start','get','submit','history'])
def test_genuine_storage_failures_are_safe_503_not_misleading_404(owned,monkeypatch,operation,caplog):
    app,a,b,ha,hb,pa,pb,clock=owned
    value=session(owned)
    from contextlib import contextmanager
    @contextmanager
    def unavailable(**kw):
        raise OwnershipUnavailable()
        yield
    monkeypatch.setattr(app.state.owned_profiles.store,'transaction',unavailable)
    response=start(owned) if operation=='start' else a.get('/api/assessment/'+value['assessment_id'],headers=ha) if operation=='get' else submit(owned,value) if operation=='submit' else a.get('/api/profile/'+pa['profile_id']+'/assessments',headers=ha)
    assert response.status_code==503 and response.json()=={'detail':'Assessment storage is temporarily unavailable.'}
    assert 'Traceback' not in caplog.text


@pytest.mark.parametrize('operation',['start','get','submit','history'])
def test_revocation_before_domain_acceptance_prevents_mutation(owned,isolated_storage,monkeypatch,operation):
    app,a,b,ha,hb,pa,pb,clock=owned
    value=session(owned)
    ident=identity(app,a)
    before=snapshot(isolated_storage)
    original=app.state.owned_assessments.profile_access
    def revoke(identity,profile_id):
        app.state.sessions.revoke_account(ident.account_id)
        return original(identity,profile_id)
    monkeypatch.setattr(app.state.owned_assessments,'profile_access',revoke)
    response=start(owned) if operation=='start' else a.get('/api/assessment/'+value['assessment_id'],headers=ha) if operation=='get' else submit(owned,value) if operation=='submit' else a.get('/api/profile/'+pa['profile_id']+'/assessments',headers=ha)
    assert response.status_code==401 and snapshot(isolated_storage)==before


@pytest.mark.parametrize('method,path',DEFERRED)
def test_non_assessment_operations_remain_blocked_for_owner_and_other_account(owned,isolated_storage,method,path):
    _,a,b,ha,hb,pa,pb,clock=owned
    value=session(owned)
    assert submit(owned,value).status_code==200
    before=snapshot(isolated_storage)
    target=path.replace('{profile_id}',pa['profile_id']).replace('{company_id}','company_001')
    for client,headers in ((a,ha),(b,hb)):
        assert client.request(method,target,json={'profile_id':pa['profile_id']},headers=headers).status_code==503
    assert snapshot(isolated_storage)==before


def test_standalone_assessment_router_has_no_identity_bypass(owned):
    app,*_=owned
    isolated=FastAPI()
    isolated.include_router(create_owned_assessment_router(app.state.owned_assessments))
    with TestClient(isolated) as client:
        for method,path in ASSESSMENTS:
            target=path.replace('{profile_id}',str(uuid.uuid4())).replace('{assessment_id}',str(uuid.uuid4()))
            assert client.request(method,target,json={}).status_code==401


@pytest.mark.parametrize('operation',['start','get','submit','history'])
@pytest.mark.parametrize('corruption',['json','structure'])
def test_corrupt_owned_profile_is_not_disclosed_or_treated_as_bad_request(owned,isolated_storage,operation,corruption):
    _,a,b,ha,hb,pa,pb,clock=owned
    value=session(owned)
    Path(profiles._profile_path(pa['profile_id'])).write_text(
        '{PRIVATE-CORRUPT-PROFILE' if corruption=='json' else '[]',encoding='utf-8')
    before=snapshot(isolated_storage)
    response=start(owned) if operation=='start' else a.get('/api/assessment/'+value['assessment_id'],headers=ha) if operation=='get' else submit(owned,value) if operation=='submit' else a.get('/api/profile/'+pa['profile_id']+'/assessments',headers=ha)
    assert response.status_code==404 and 'PRIVATE-CORRUPT' not in response.text
    assert snapshot(isolated_storage)==before


def test_corrupt_assessment_discovery_is_indistinguishable_from_missing(owned,isolated_storage):
    _,a,b,ha,hb,pa,pb,clock=owned
    value=session(owned)
    Path(assessments._session_path(value['assessment_id'])).write_text('{PRIVATE-CORRUPT-ASSESSMENT',encoding='utf-8')
    before=snapshot(isolated_storage)
    missing=a.get('/api/assessment/'+str(uuid.uuid4()),headers=ha)
    for client,headers in ((a,ha),(b,hb)):
        response=client.get('/api/assessment/'+value['assessment_id'],headers=headers)
        assert response.status_code==404 and response.json()==missing.json()
        assert submit(owned,value,client=client,headers=headers).json()==missing.json()
    assert snapshot(isolated_storage)==before


def test_assessment_id_collision_cannot_overwrite_an_existing_foreign_record(owned,isolated_storage,monkeypatch):
    _,a,b,ha,hb,pa,pb,clock=owned
    foreign=session(owned,client=b,headers=hb,profile=pb['profile_id'])
    before=snapshot(isolated_storage)
    monkeypatch.setattr(assessments.uuid,'uuid4',lambda:uuid.UUID(foreign['assessment_id']))
    response=start(owned)
    assert response.status_code==409
    assert snapshot(isolated_storage)==before


def test_identical_retry_recovers_accepted_submission_without_duplicate_evidence(owned,monkeypatch):
    _,a,b,ha,hb,pa,pb,clock=owned
    value=session(owned)
    original=assessments._save_profile
    def fail(*args,**kw):
        raise OSError('Synthetic interrupted evidence write')
    monkeypatch.setattr(assessments,'_save_profile',fail)
    assert submit(owned,value).status_code==503
    assert assessments._load_session(value['assessment_id'])['status']=='SUBMITTING'
    monkeypatch.setattr(assessments,'_save_profile',original)
    monkeypatch.setattr(assessments,'compute_score',lambda *args:pytest.fail('Do not rescore accepted work'))
    clock.advance(minutes=10)
    restored=submit(owned,value)
    assert restored.status_code==200 and restored.json()['skill_score']==100
    assert submit(owned,value).status_code==409
    assert len(profiles._load(pa['profile_id'])['assessment_evidence'])==1


@pytest.mark.parametrize('change',['disabled','password'])
def test_account_changes_invalidate_assessment_requests_before_mutation(owned,isolated_storage,change):
    app,a,b,ha,hb,pa,pb,clock=owned
    value=session(owned)
    account_id=identity(app,a).account_id
    with sqlite3.connect(app.state.accounts.store.path) as connection:
        if change=='disabled':
            connection.execute("UPDATE accounts SET status='DISABLED' WHERE account_id=?",(account_id,))
        else:
            connection.execute('UPDATE accounts SET auth_version=auth_version+1 WHERE account_id=?',(account_id,))
    clock.advance(minutes=10)
    before=snapshot(isolated_storage)
    for response in (start(owned),a.get('/api/assessment/'+value['assessment_id'],headers=ha),submit(owned,value),
                     a.get('/api/profile/'+pa['profile_id']+'/assessments',headers=ha)):
        assert response.status_code==401
    assert snapshot(isolated_storage)==before


def test_real_profile_io_failure_is_safe_unavailable_response(owned,isolated_storage,monkeypatch):
    _,a,b,ha,hb,pa,pb,clock=owned
    value=session(owned)
    before=snapshot(isolated_storage)
    def unavailable(*args):
        raise PermissionError('PRIVATE-STORAGE-PATH')
    monkeypatch.setattr(assessments,'_load_profile',unavailable)
    assert start(owned).status_code==503
    response=a.get('/api/assessment/'+value['assessment_id'],headers=ha)
    assert response.status_code==503 and 'PRIVATE-STORAGE' not in response.text
    assert snapshot(isolated_storage)==before
