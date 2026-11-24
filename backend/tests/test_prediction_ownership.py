"""Real secured production app; synthetic accounts and retained isolated storage only."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3
from threading import Barrier, Event
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from backend.app.routes.owned_analytics import create_owned_analytics_router
from backend.app.services import profile_service as profiles, assessment_service as assessments
from backend.app.services import readiness_service, eligibility_service, recommendation_service, performance_service
from backend.app.services.ownership_store import OwnershipUnavailable
from backend.tests.test_profile_ownership import pair,encoded_password,identity
from backend.tests.test_session_security import ANALYTICS,BASE,ORIGIN,PUBLIC,inventory
from backend.tests.test_integration import student
from backend.tests.test_predict import SAMPLE_STUDENT
from backend.tests.test_salary_prediction import VALID_PAYLOAD

PROFILE_OPERATIONS=sorted((m,p) for m,p in ANALYTICS if '{profile_id}' in p)

@pytest.fixture
def owned(pair):
    app,a,b,ha,hb=pair
    values=[]
    for client,headers,name in ((a,ha,'Synthetic A'),(b,hb,'Synthetic B')):
        body=student()
        body.pop('profile_id')
        body['personal']['name']=name
        response=client.post('/api/profile/verify',json=body,headers=headers)
        assert response.status_code==200,response.text
        values.append(response.json()['profile'])
    return app,a,b,ha,hb,*values

def target(path,profile_id):
    return path.replace('{profile_id}',profile_id).replace('{company_id}','company_001')

def predict(owned,*,client=None,headers=None,profile=None,key='synthetic-intent'):
    _,a,_,ha,_,pa,_=owned
    return (client or a).post('/api/profile/'+(profile or pa['profile_id'])+'/predict',headers=(headers or ha)|({'Idempotency-Key':key} if key is not None else {}))

def snapshot(storage):
    return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for d in (storage.profiles,storage.assessments)
            for p in d.glob('*.json')}

def test_real_models_preserve_stateless_request_response_contract_and_write_no_student_data(owned,isolated_storage):
    _,a,b,ha,hb,pa,pb=owned
    from backend.app.services.prediction_service import predict as raw_predict
    from backend.app.services.salary_prediction_service import predict_salary
    before=snapshot(isolated_storage)
    for client,headers in ((a,ha),(b,hb)):
        for path,payload,expected in (('/api/predict',SAMPLE_STUDENT,raw_predict(SAMPLE_STUDENT)),
                                      ('/api/salary-predict',VALID_PAYLOAD,predict_salary(VALID_PAYLOAD))):
            response=client.post(path,json=payload,headers=headers)
            assert response.status_code==200 and response.json()==expected
            assert response.headers['Cache-Control']=='private, no-store'
            assert 'profile_id' not in response.json() and 'source_revision' not in response.json()
    assert snapshot(isolated_storage)==before

@pytest.mark.parametrize('method,path',sorted(ANALYTICS))
@pytest.mark.parametrize('failure',['anonymous','forged','revoked','origin'])
def test_every_analysis_operation_rejects_invalid_authentication_or_origin_before_business_work(owned,isolated_storage,method,path,failure):
    app,a,b,ha,hb,pa,pb=owned
    headers=ha
    client=a
    if failure in {'anonymous','forged'}:
        client=TestClient(app,base_url=BASE)
        if failure=='forged':
            client.cookies.set(app.state.security_config.cookie_name,'x'*43)
    elif failure=='revoked':
        app.state.sessions.revoke_account(identity(app,a).account_id)
    else:
        headers=ha|{'Origin':'https://foreign.example.test'}
    before=snapshot(isolated_storage)
    try:
        response=client.request(method,target(path,pa['profile_id']),content='PRIVATE-INVALID-INPUT',headers=headers)
        assert response.status_code==(403 if failure=='origin' else 401)
        assert 'PRIVATE-INVALID' not in response.text
    finally:
        if client is not a:
            client.close()
    assert snapshot(isolated_storage)==before and not isolated_storage.companies_db.exists()

@pytest.mark.parametrize('method,path',[op for op in sorted(ANALYTICS) if op[0]=='POST'])
@pytest.mark.parametrize('csrf',['missing','invalid','cross-account'])
def test_analysis_mutations_require_session_bound_csrf_before_inference_or_history(owned,isolated_storage,method,path,csrf):
    _,a,b,ha,hb,pa,pb=owned
    headers={'Origin':ORIGIN}
    if csrf!='missing':
        headers['X-CSRF-Token']='wrong' if csrf=='invalid' else hb['X-CSRF-Token']
    before=snapshot(isolated_storage)
    response=a.request(method,target(path,pa['profile_id']),content='PRIVATE-INVALID-INPUT',headers=headers)
    assert response.status_code==403 and snapshot(isolated_storage)==before

@pytest.mark.parametrize('method,path',PROFILE_OPERATIONS)
@pytest.mark.parametrize('case',['foreign','missing','legacy','PENDING','SUSPENDED','corrupt'])
def test_profile_targets_deny_before_query_key_validation_company_lookup_or_history(owned,isolated_storage,method,path,case):
    app,a,b,ha,hb,pa,pb=owned
    profile_id=pa['profile_id']
    if case=='missing':
        profile_id=str(uuid.uuid4())
    elif case=='legacy':
        profile_id=str(uuid.uuid4())
        profiles.verify_profile(student(profile_id))
    elif case!='foreign':
        with sqlite3.connect(app.state.accounts.store.path) as c:
            if case=='corrupt':
                c.execute('PRAGMA ignore_check_constraints=ON')
            c.execute('UPDATE profile_ownership SET status=? WHERE profile_id=?',('INVALID' if case=='corrupt' else case,profile_id))
    client=b if case=='foreign' else a
    headers=hb if case=='foreign' else ha
    before=snapshot(isolated_storage)
    response=client.request(method,target(path,profile_id)+'?limit=INVALID-PRIVATE',headers=headers|{'Idempotency-Key':'x'*129})
    assert response.status_code==404 and response.json()=={'detail':'Profile not found.'}
    assert profile_id not in response.text and 'INVALID-PRIVATE' not in response.text
    assert snapshot(isolated_storage)==before and not isolated_storage.companies_db.exists()

def test_owned_prediction_history_is_bound_persistent_and_replay_is_checked_before_inference(owned,monkeypatch):
    app,a,b,ha,hb,pa,pb=owned
    first=predict(owned)
    assert first.status_code==200 and first.json()['ready_for_prediction'] is True
    raw=profiles._load(pa['profile_id'])
    assert raw['revision']==pa['revision'] and len(raw['prediction_history'])==1
    entry=raw['prediction_history'][0]
    assert entry['account_id']==identity(app,a).account_id and entry['profile_id']==pa['profile_id']
    assert uuid.UUID(entry['prediction_id']).version==4 and entry['source_revision']==pa['revision']
    assert entry['ownership_schema_version']==1 and entry['profile_ownership_version']==2
    for private in ('account_id','prediction_id','profile_ownership_version','ownership_schema_version'):
        assert private not in first.text
    def forbidden(*args):
        pytest.fail('Cached or foreign prediction invoked inference')
    monkeypatch.setattr(profiles,'predict_with_model',forbidden)
    assert predict(owned).json()==first.json()
    assert predict(owned,client=b,headers=hb).status_code==404
    assert len(profiles._load(pa['profile_id'])['prediction_history'])==1
    performance=a.get('/api/profile/'+pa['profile_id']+'/performance',headers=ha)
    assert performance.status_code==200 and performance.json()['summary']['predictions']['predictions_count']==1
    assert performance.json()['summary']['predictions']['latest_is_current'] is True
    assert 'account_id' not in performance.text

def test_owner_analytics_match_existing_calculators_without_history_or_lifecycle_writes(owned,isolated_storage):
    _,a,b,ha,hb,pa,pb=owned
    predict(owned)
    raw=profiles._load(pa['profile_id'])
    before=snapshot(isolated_storage)
    cases=[('readiness',readiness_service.readiness_for_profile(raw)),
           ('placement-summary',readiness_service.get_placement_summary(pa['profile_id'])),
           ('eligibility',eligibility_service.get_all_eligibility(pa['profile_id'])),
           ('eligibility/company_001',eligibility_service.get_eligibility(pa['profile_id'],'company_001')),
           ('recommendations?limit=2',recommendation_service.get_recommendations(pa['profile_id'],2)),
           ('skills',assessments.skills_for_profile(raw)),
           ('performance',performance_service.get_performance(pa['profile_id']))]
    for suffix,expected in cases:
        response=a.get('/api/profile/'+pa['profile_id']+'/'+suffix,headers=ha)
        assert response.status_code==200,response.text
        # Compare the existing rendered API contract, including schema defaults.
        from backend.app.schemas_performance import PerformanceResponse
        from backend.app.schemas_readiness import ReadinessResponse,PlacementSummaryResponse
        from backend.app.schemas_eligibility import AllCompanyEligibilityResponse,CompanyEligibilityResponse
        from backend.app.schemas_recommendation import RecommendationsResponse
        from backend.app.schemas_assessment import SkillsViewResponse
        models={'performance':PerformanceResponse,'placement-summary':PlacementSummaryResponse,
                'readiness':ReadinessResponse,'eligibility':AllCompanyEligibilityResponse,
                'eligibility/company_001':CompanyEligibilityResponse,'recommendations?limit=2':RecommendationsResponse,
                'skills':SkillsViewResponse}
        expected=models[suffix].model_validate(expected).model_dump()
        assert response.json()==expected
    assert snapshot(isolated_storage)==before

def test_same_key_is_independent_across_accounts_and_profiles_and_concurrent_retries_write_once(owned):
    app,a,b,ha,hb,pa,pb=owned
    barrier=Barrier(8)
    def request(_):
        barrier.wait(timeout=10)
        return predict(owned)
    with ThreadPoolExecutor(max_workers=8) as pool:
        responses=list(pool.map(request,range(8)))
    assert all(r.status_code==200 for r in responses)
    assert all(r.json()==responses[0].json() for r in responses)
    assert len(profiles._load(pa['profile_id'])['prediction_history'])==1
    assert predict(owned,client=b,headers=hb,profile=pb['profile_id']).status_code==200
    body=student(); body.pop('profile_id')
    extra=a.post('/api/profile/verify',json=body,headers=ha).json()['profile']
    assert predict(owned,profile=extra['profile_id']).status_code==200
    assert all(len(profiles._load(p['profile_id'])['prediction_history'])==1 for p in (pa,pb,extra))

def test_stale_revision_and_changed_source_inputs_cannot_replay_old_prediction(owned,isolated_storage):
    _,a,b,ha,hb,pa,pb=owned
    assert predict(owned).status_code==200
    update=deepcopy(pa); update['education']['cgpa']=7.0
    changed=a.put('/api/profile/'+pa['profile_id'],json=update,headers=ha)
    assert changed.status_code==200 and changed.json()['profile']['revision']==2
    confirmed=a.post('/api/profile/verify',json=changed.json()['profile'],headers=ha)
    assert confirmed.status_code==200
    before=snapshot(isolated_storage)
    assert predict(owned).status_code==409 and snapshot(isolated_storage)==before
    assert predict(owned,key='new-intent').status_code==200
    assert len(profiles._load(pa['profile_id'])['prediction_history'])==2

def test_legacy_history_and_assessments_are_retained_but_not_projected_or_replayed(owned,isolated_storage):
    app,a,b,ha,hb,pa,pb=owned
    profiles.predict_for_profile(pa['profile_id'],request_id='legacy-key')
    legacy=assessments.start_assessment(pa['profile_id'],'Python',1)
    legacy_bytes=Path(assessments._session_path(legacy['assessment_id'])).read_bytes()
    before=snapshot(isolated_storage)
    assert predict(owned,key='legacy-key').status_code==409
    assert snapshot(isolated_storage)==before
    assert predict(owned).status_code==200
    raw=profiles._load(pa['profile_id'])
    assert len(raw['prediction_history'])==2 and 'account_id' not in raw['prediction_history'][0]
    result=a.get('/api/profile/'+pa['profile_id']+'/performance',headers=ha)
    assert result.status_code==200 and len(result.json()['prediction_history'])==1
    assert result.json()['assessment_history']==[]
    assert Path(assessments._session_path(legacy['assessment_id'])).read_bytes()==legacy_bytes

@pytest.mark.parametrize('failure',['before-save','after-save'])
def test_failed_or_lost_prediction_response_can_retry_without_duplicate_history(owned,monkeypatch,failure):
    app,a,b,ha,hb,pa,pb=owned
    owner=app.state.owned_analytics
    original=profiles._save if failure=='before-save' else owner.predict
    def fail(*args,**kw):
        if failure=='after-save':
            original(*args,**kw)
        raise OSError('PRIVATE-PERSISTENCE-FAILURE')
    monkeypatch.setattr(profiles if failure=='before-save' else owner,'_save' if failure=='before-save' else 'predict',fail)
    response=predict(owned)
    assert response.status_code==503 and 'PRIVATE-PERSISTENCE' not in response.text
    assert len(profiles._load(pa['profile_id'])['prediction_history'])==(0 if failure=='before-save' else 1)
    monkeypatch.setattr(profiles if failure=='before-save' else owner,'_save' if failure=='before-save' else 'predict',original)
    assert predict(owned).status_code==200 and predict(owned).status_code==200
    assert len(profiles._load(pa['profile_id'])['prediction_history'])==1

@pytest.mark.parametrize('change',['revoked','suspended','version'])
def test_invalidation_during_inference_prevents_history_write(owned,isolated_storage,monkeypatch,change):
    app,a,b,ha,hb,pa,pb=owned
    account_id=identity(app,a).account_id
    def infer(inputs):
        if change=='revoked':
            app.state.sessions.revoke_account(account_id)
        else:
            with sqlite3.connect(app.state.accounts.store.path) as c:
                if change=='suspended':
                    c.execute("UPDATE profile_ownership SET status='SUSPENDED' WHERE profile_id=?",(pa['profile_id'],))
                else:
                    c.execute('UPDATE accounts SET auth_version=auth_version+1 WHERE account_id=?',(account_id,))
        return {'model_version':'synthetic-model','prediction':'PLACED','placement_probability':.8,'confidence':.8}
    monkeypatch.setattr(profiles,'predict_with_model',infer)
    before=snapshot(isolated_storage)
    assert predict(owned).status_code==(404 if change=='suspended' else 401)
    assert snapshot(isolated_storage)==before

@pytest.mark.parametrize('field',['account_id','profile_id','profile_ownership_version','ownership_schema_version'])
def test_mismatched_stored_binding_is_not_projected_or_replayed(owned,isolated_storage,field):
    app,a,b,ha,hb,pa,pb=owned
    predict(owned)
    raw=profiles._load(pa['profile_id'])
    entry=raw['prediction_history'][0]
    entry[field]=identity(app,b).account_id if field=='account_id' else pb['profile_id'] if field=='profile_id' else 0
    profiles._save(raw)
    before=snapshot(isolated_storage)
    result=a.get('/api/profile/'+pa['profile_id']+'/performance',headers=ha)
    assert result.status_code==200 and result.json()['prediction_history']==[]
    assert predict(owned).status_code==409 and snapshot(isolated_storage)==before

def test_owned_router_standalone_does_not_provide_an_authentication_bypass(owned):
    app,*_=owned
    standalone=FastAPI()
    standalone.include_router(create_owned_analytics_router(app.state.owned_analytics))
    mounted={operation for operation in inventory(standalone) if operation[1].startswith('/api/')}
    public={operation for operation in PUBLIC if operation[1].startswith('/api/')}
    assert mounted==(ANALYTICS-{('POST','/api/experimental/v1/predict')})|public
    with TestClient(standalone) as client:
        for method,path in sorted(mounted-public):
            assert client.request(method,target(path,str(uuid.uuid4())),json=SAMPLE_STUDENT).status_code==401
        assert client.post('/api/experimental/v1/predict',json=SAMPLE_STUDENT).status_code==404

def test_storage_failure_does_not_disclose_paths_or_allow_analysis(owned,monkeypatch,caplog):
    from contextlib import contextmanager
    app,a,b,ha,hb,pa,pb=owned
    @contextmanager
    def fail(**kw):
        raise OwnershipUnavailable()
        yield
    monkeypatch.setattr(app.state.owned_profiles.store,'transaction',fail)
    response=predict(owned)
    assert response.status_code==503 and response.json()=={'detail':'Student analysis is temporarily unavailable.'}
    assert a.get('/api/profile/'+pa['profile_id']+'/performance',headers=ha).status_code==503
    assert 'Traceback' not in caplog.text

def test_bound_assessment_evidence_is_projected_without_exposing_account_metadata_or_recovery(owned,isolated_storage):
    _,a,b,ha,hb,pa,pb=owned
    started=a.post('/api/assessment/start',json={'profile_id':pa['profile_id'],'skill':'Python','num_questions':2},headers=ha)
    assert started.status_code==200
    value=started.json()
    keys={q['id']:q['correct_answer'] for q in assessments.get_questions('Python')}
    completed=a.post('/api/assessment/'+value['assessment_id']+'/submit',json={'profile_id':pa['profile_id'],
        'answers':{q['question_id']:keys[q['question_id']] for q in value['questions']}},headers=ha)
    assert completed.status_code==200
    before=snapshot(isolated_storage)
    performance=a.get('/api/profile/'+pa['profile_id']+'/performance',headers=ha)
    assert performance.status_code==200 and performance.json()['summary']['assessments']['assessments_count']==1
    assert performance.json()['assessment_history'][0]['score']==100
    assert 'account_id' not in performance.text
    assert b.get('/api/profile/'+pa['profile_id']+'/performance',headers=hb).status_code==404
    assert snapshot(isolated_storage)==before

@pytest.mark.parametrize('field',['source_revision','prediction_id','timestamp','placement_probability'])
def test_corrupt_bound_history_fails_closed_without_repair_or_replay(owned,isolated_storage,field):
    _,a,b,ha,hb,pa,pb=owned
    assert predict(owned).status_code==200
    raw=profiles._load(pa['profile_id'])
    raw['prediction_history'][0][field]=99 if field in {'source_revision','placement_probability'} else 'PRIVATE-CORRUPT-HISTORY'
    profiles._save(raw)
    before=snapshot(isolated_storage)
    assert predict(owned).status_code==503
    response=a.get('/api/profile/'+pa['profile_id']+'/performance',headers=ha)
    assert response.status_code==503 and 'PRIVATE-CORRUPT' not in response.text
    assert snapshot(isolated_storage)==before

def test_concurrent_profile_edit_preserves_prediction_snapshot_and_marks_history_stale(owned,monkeypatch):
    _,a,b,ha,hb,pa,pb=owned
    entered,release,editing=Event(),Event(),Event()
    def infer(inputs):
        entered.set()
        assert release.wait(timeout=10)
        return {'model_version':'synthetic-model','prediction':'PLACED','placement_probability':.8,'confidence':.8}
    monkeypatch.setattr(profiles,'predict_with_model',infer)
    def edit():
        body=deepcopy(pa); body['education']['cgpa']=7
        editing.set()
        return a.put('/api/profile/'+pa['profile_id'],json=body,headers=ha)
    with ThreadPoolExecutor(max_workers=2) as pool:
        prediction=pool.submit(predict,owned)
        assert entered.wait(timeout=10)
        update=pool.submit(edit)
        assert editing.wait(timeout=10)
        release.set()
        result=prediction.result(timeout=10)
        changed=update.result(timeout=10)
    assert result.status_code==200 and result.json()['source_revision']==1
    assert changed.status_code==200 and changed.json()['profile']['revision']==2
    raw=profiles._load(pa['profile_id'])
    assert raw['prediction_history'][0]['source_inputs']['cgpa']==pa['education']['cgpa']
    assert raw['education']['cgpa']==7 and len(raw['prediction_history'])==1


@pytest.mark.parametrize('keys', [[], ['x'*129], ['first-intent','second-intent']])
def test_invalid_retry_headers_are_redacted_before_inference_and_do_not_write(owned,isolated_storage,monkeypatch,keys):
    _,a,_,ha,_,pa,_=owned
    def forbidden(*args):
        pytest.fail('Invalid retry headers reached inference')
    monkeypatch.setattr(profiles,'predict_with_model',forbidden)
    headers=list(ha.items())+([('Idempotency-Key',key) for key in keys] if keys else [('Idempotency-Key','')])
    before=snapshot(isolated_storage)
    response=a.post('/api/profile/'+pa['profile_id']+'/predict',headers=headers)
    assert response.status_code==422 and response.json()=={'detail':'Invalid analysis request.'}
    assert snapshot(isolated_storage)==before


@pytest.mark.parametrize('path,payload', [('/api/predict',SAMPLE_STUDENT),('/api/salary-predict',VALID_PAYLOAD)])
def test_stateless_identity_and_retry_fields_cannot_access_or_associate_foreign_data(owned,isolated_storage,path,payload):
    app,a,b,ha,hb,pa,pb=owned
    assert predict(owned,client=b,headers=hb,profile=pb['profile_id']).status_code==200
    normal=a.post(path,json=payload,headers=ha)
    assert normal.status_code==200
    injected={**payload,'account_id':identity(app,b).account_id,'owner_account_id':identity(app,b).account_id,
              'profile_id':pb['profile_id'],'revision':pb['revision'],'request_id':'synthetic-intent'}
    before=snapshot(isolated_storage)
    response=a.post(path,json=injected,headers=ha|{'Idempotency-Key':'synthetic-intent'})
    assert response.status_code==200 and response.json()==normal.json()
    assert snapshot(isolated_storage)==before


@pytest.mark.parametrize('state',['unverified','incomplete'])
def test_unready_owned_profile_never_infers_or_writes_history(owned,isolated_storage,monkeypatch,state):
    _,a,_,ha,_,pa,_=owned
    body=deepcopy(pa)
    if state=='incomplete':
        body['ml_inputs']['coding_skills']=None
    else:
        body['personal']['name']='Synthetic Unconfirmed Edit'
    updated=a.put('/api/profile/'+pa['profile_id'],json=body,headers=ha)
    assert updated.status_code==200
    if state=='incomplete':
        confirmed=a.post('/api/profile/verify',json=updated.json()['profile'],headers=ha)
        assert confirmed.status_code==200 and not confirmed.json()['completion']['profile_complete']
    def forbidden(*args):
        pytest.fail('An unready owned profile reached inference')
    monkeypatch.setattr(profiles,'predict_with_model',forbidden)
    before=snapshot(isolated_storage)
    response=predict(owned)
    assert response.status_code==200 and response.json()['ready_for_prediction'] is False
    assert response.json()['placement_probability'] is None and response.json()['prediction_history']==[]
    assert snapshot(isolated_storage)==before


def test_bound_replay_requires_matching_source_inputs_even_at_same_revision(owned,isolated_storage,monkeypatch):
    _,a,_,ha,_,pa,_=owned
    assert predict(owned).status_code==200
    raw=profiles._load(pa['profile_id'])
    raw['prediction_history'][0]['source_inputs']['cgpa']=1
    profiles._save(raw)
    assert profiles._load(pa['profile_id'])['revision']==pa['revision']
    def forbidden(*args):
        pytest.fail('A mismatched stored retry reached inference')
    monkeypatch.setattr(profiles,'predict_with_model',forbidden)
    before=snapshot(isolated_storage)
    response=predict(owned)
    assert response.status_code==409 and snapshot(isolated_storage)==before
