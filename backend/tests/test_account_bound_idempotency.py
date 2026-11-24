"""Production ASGI retries: synthetic accounts, no historical records or bypasses."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import sqlite3
from threading import Barrier

import pytest

from backend.tests.test_profile_ownership import pair,encoded_password,identity,resume,body
from backend.tests.test_prediction_ownership import owned,snapshot,predict
from backend.app.services import profile_service as profiles,assessment_service as assessments
from backend.app.services.ownership_store import OwnershipConflict


def create(client,headers,key='create-intent',values=None):
    return client.post('/api/profile/verify',json=values or body(),headers=headers|{'Idempotency-Key':key})


def start(client,headers,profile,key='start-intent',skill='Python',count=3):
    return client.post('/api/assessment/start',json={'profile_id':profile,'skill':skill,'num_questions':count},
                       headers=headers|{'Idempotency-Key':key})


def test_creation_retry_has_one_profile_and_original_response(pair,monkeypatch):
    app,a,b,ha,hb=pair
    first=create(a,ha)
    assert first.status_code==200
    monkeypatch.setattr(profiles,'prepare_confirmed_profile',lambda *args: pytest.fail('Creation replay prepared a second record'))
    assert create(a,ha).json()==first.json()
    assert len(a.get('/api/account/profiles').json()['profiles'])==1
    raw=profiles._load(first.json()['profile']['profile_id'])
    assert raw['_creation_receipt']['account_id']==identity(app,a).account_id
    assert '_creation_receipt' not in first.text and 'account_id' not in first.text


def test_same_creation_key_different_payload_conflicts_without_mutation(pair,isolated_storage):
    _,a,b,ha,hb=pair
    assert create(a,ha).status_code==200
    before=snapshot(isolated_storage)
    changed=body();changed['personal']['name']='Changed payload'
    response=create(a,ha,values=changed)
    assert response.status_code==409 and 'Changed payload' not in response.text
    assert snapshot(isolated_storage)==before


def test_cross_account_creation_keys_are_independent_and_not_email_bound(pair):
    _,a,b,ha,hb=pair
    first,second=create(a,ha),create(b,hb)
    assert first.status_code==second.status_code==200
    pa,pb=first.json()['profile']['profile_id'],second.json()['profile']['profile_id']
    assert pa!=pb
    assert a.get('/api/profile/'+pb).status_code==b.get('/api/profile/'+pa).status_code==404


def test_concurrent_creation_delivers_one_record(pair):
    _,a,b,ha,hb=pair
    barrier=Barrier(6)
    def send(_):
        barrier.wait(timeout=10)
        return create(a,ha)
    with ThreadPoolExecutor(max_workers=6) as pool: responses=list(pool.map(send,range(6)))
    assert all(r.status_code==200 for r in responses)
    assert all(r.json()==responses[0].json() for r in responses)
    assert len(a.get('/api/account/profiles').json()['profiles'])==1


def test_resume_retry_replays_exact_analysis_without_reextracting(pair,monkeypatch):
    _,a,b,ha,hb=pair
    file=resume()
    def send():return a.post('/api/profile/from-resume',files={'file':file},headers=ha|{'Idempotency-Key':'upload-intent'})
    first=send();assert first.status_code==200
    monkeypatch.setattr(profiles,'prepare_draft_with_analysis',lambda *args,**kwargs: pytest.fail('Resume replay extracted again'))
    assert send().json()==first.json()
    assert len(a.get('/api/account/profiles').json()['profiles'])==1


def test_pending_creation_is_quarantined_and_retry_never_creates_another_record(pair,isolated_storage,monkeypatch):
    app,a,b,ha,hb=pair
    monkeypatch.setattr(app.state.owned_profiles.store,'activate',lambda *args: (_ for _ in ()).throw(OwnershipConflict()))
    assert create(a,ha).status_code==409
    before=snapshot(isolated_storage)
    assert create(a,ha).status_code==409
    assert snapshot(isolated_storage)==before
    assert a.get('/api/account/profiles').json()=={'profiles':[]}
    record=json.loads(next(isolated_storage.profiles.glob('*.json')).read_text())
    assert a.get('/api/profile/'+record['profile_id']).status_code==404


def test_creation_storage_failure_keeps_reservation_pending(pair,isolated_storage,monkeypatch):
    app,a,b,ha,hb=pair
    monkeypatch.setattr(profiles,'persist_new_profile',lambda *args: (_ for _ in ()).throw(OSError('private storage marker')))
    assert create(a,ha).status_code==503
    response=create(a,ha);assert response.status_code==409 and 'private storage marker' not in response.text
    assert not list(isolated_storage.profiles.glob('*.json'))
    with sqlite3.connect(app.state.accounts.store.path) as c: assert c.execute('SELECT status FROM profile_ownership').fetchall()==[('PENDING',)]


def test_legacy_profile_collision_is_not_claimed(pair,isolated_storage,monkeypatch):
    from backend.app.services import owned_profile_service
    _,a,b,ha,hb=pair
    legacy='11111111-1111-4111-8111-111111111111'
    profiles.verify_profile(body()|{'profile_id':legacy})
    before=snapshot(isolated_storage)
    monkeypatch.setattr(owned_profile_service,'creation_id',lambda *args:legacy)
    assert create(a,ha).status_code==409
    assert snapshot(isolated_storage)==before
    assert a.get('/api/profile/'+legacy).status_code==404


@pytest.mark.parametrize('operation',['update','confirm'])
def test_profile_retry_payload_and_revision_integrity(owned,isolated_storage,operation):
    app,a,b,ha,hb,pa,pb=owned
    values=deepcopy(pa);values['personal']['name']='Reviewed change'
    path='/api/profile/verify' if operation=='confirm' else '/api/profile/'+pa['profile_id']
    method='POST' if operation=='confirm' else 'PUT'
    headers=ha|{'Idempotency-Key':'edit-intent'}
    first=a.request(method,path,json=values,headers=headers);assert first.status_code==200
    revision=first.json()['profile']['revision']
    assert a.request(method,path,json=values,headers=headers).json()==first.json()
    before=snapshot(isolated_storage)
    values['personal']['name']='Different payload'
    assert a.request(method,path,json=values,headers=headers).status_code==409
    assert snapshot(isolated_storage)==before
    newer=deepcopy(first.json()['profile']);newer['personal']['name']='Newer revision'
    assert a.put('/api/profile/'+pa['profile_id'],json=newer,headers=ha).status_code==200
    values['personal']['name']='Reviewed change'
    assert a.request(method,path,json=values,headers=headers).status_code==409
    assert profiles._load(pa['profile_id'])['revision']>revision


def test_failed_receipt_write_is_recoverable_without_duplicate_revision(owned,monkeypatch):
    _,a,b,ha,hb,pa,pb=owned
    original=profiles._save
    failed=False
    def save(record):
        nonlocal failed
        if record.get('_request_receipts') and not failed:
            failed=True;raise OSError('Synthetic metadata failure')
        return original(record)
    monkeypatch.setattr(profiles,'_save',save)
    values=deepcopy(pa);values['personal']['name']='Recoverable edit'
    path='/api/profile/'+pa['profile_id'];headers=ha|{'Idempotency-Key':'receipt-intent'}
    assert a.put(path,json=values,headers=headers).status_code==503
    revision=profiles._load(pa['profile_id'])['revision']
    assert a.put(path,json=values,headers=headers).status_code==200
    assert profiles._load(pa['profile_id'])['revision']==revision


def test_assessment_start_retry_has_one_reservation_and_questions(owned,monkeypatch):
    _,a,b,ha,hb,pa,pb=owned
    first=start(a,ha,pa['profile_id']);assert first.status_code==200
    monkeypatch.setattr(assessments,'start_assessment',lambda *args,**kwargs:pytest.fail('Replay reserved another attempt'))
    second=start(a,ha,pa['profile_id']);assert second.status_code==200
    assert {k:v for k,v in first.json().items() if k!='server_now'}=={k:v for k,v in second.json().items() if k!='server_now'}
    assert len(assessments._sessions_for_profile(pa['profile_id']))==1


@pytest.mark.parametrize('change',['payload','revision'])
def test_assessment_retry_conflict_cannot_trigger_expiry_or_recovery(owned,isolated_storage,monkeypatch,change):
    _,a,b,ha,hb,pa,pb=owned
    assert start(a,ha,pa['profile_id']).status_code==200
    if change=='revision':
        values=deepcopy(pa);values['personal']['name']='Updated profile'
        assert a.put('/api/profile/'+pa['profile_id'],json=values,headers=ha).status_code==200
    before=snapshot(isolated_storage)
    monkeypatch.setattr(assessments,'_sync_sessions',lambda *args,**kwargs:pytest.fail('Rejected replay triggered lifecycle'))
    response=start(a,ha,pa['profile_id'],count=4 if change=='payload' else 3)
    assert response.status_code==409 and snapshot(isolated_storage)==before


def test_concurrent_assessment_start_same_key_reserves_once(owned):
    _,a,b,ha,hb,pa,pb=owned
    barrier=Barrier(6)
    def send(_):barrier.wait(timeout=10);return start(a,ha,pa['profile_id'])
    with ThreadPoolExecutor(max_workers=6) as pool:responses=list(pool.map(send,range(6)))
    assert all(r.status_code==200 for r in responses)
    assert len({r.json()['assessment_id'] for r in responses})==1
    assert len(assessments._sessions_for_profile(pa['profile_id']))==1


def test_submission_payload_mismatch_cannot_recover_accepted_evidence(owned,isolated_storage,monkeypatch):
    _,a,b,ha,hb,pa,pb=owned
    response=start(a,ha,pa['profile_id']);aid=response.json()['assessment_id']
    session=assessments._load_session(aid);answers={session['questions'][0]['id']:session['questions'][0]['correct_answer']}
    original=assessments._finish_submission
    monkeypatch.setattr(assessments,'_finish_submission',lambda *args,**kwargs:(_ for _ in ()).throw(OSError('Synthetic evidence failure')))
    path='/api/assessment/'+aid+'/submit';headers=ha|{'Idempotency-Key':'submit-intent'}
    assert a.post(path,json={'profile_id':pa['profile_id'],'answers':answers},headers=headers).status_code==503
    before=snapshot(isolated_storage)
    assert a.post(path,json={'profile_id':pa['profile_id'],'answers':{}},headers=headers).status_code==409
    assert b.post(path,json={'profile_id':pa['profile_id'],'answers':answers},headers=hb).status_code==404
    assert snapshot(isolated_storage)==before
    monkeypatch.setattr(assessments,'_finish_submission',original)
    assert a.post(path,json={'profile_id':pa['profile_id'],'answers':answers},headers=headers).status_code==200
    assert a.post(path,json={'profile_id':pa['profile_id'],'answers':answers},headers=headers).status_code==409
    assert len(profiles._load(pa['profile_id'])['assessment_evidence'])==1


@pytest.mark.parametrize('failure',['revoked','expired','suspended'])
@pytest.mark.parametrize('operation',['create','start','predict'])
def test_invalidated_identity_cannot_replay_or_write(owned,isolated_storage,failure,operation):
    app,a,b,ha,hb,pa,pb=owned
    def send():
        if operation=='create':return create(a,ha)
        if operation=='start':return start(a,ha,pa['profile_id'])
        return predict(owned)
    assert send().status_code==200
    if failure=='revoked':app.state.sessions.revoke_account(identity(app,a).account_id)
    elif failure=='expired':app.state.sessions.clock=lambda:10**12
    else:
        with sqlite3.connect(app.state.accounts.store.path) as c:c.execute("UPDATE accounts SET status='DISABLED' WHERE account_id=?",(identity(app,a).account_id,))
    before=snapshot(isolated_storage)
    assert send().status_code==401 and snapshot(isolated_storage)==before


@pytest.mark.parametrize('key',['',' '*3,'x'*129])
@pytest.mark.parametrize('operation',['create','start','update'])
def test_invalid_retry_keys_are_redacted(owned,operation,key):
    _,a,b,ha,hb,pa,pb=owned
    if operation=='create':r=create(a,ha,key=key)
    elif operation=='start':r=start(a,ha,pa['profile_id'],key=key)
    else:r=a.put('/api/profile/'+pa['profile_id'],json=pa,headers=ha|{'Idempotency-Key':key})
    assert r.status_code==422 and 'account_id' not in r.text


def test_duplicate_headers_rejected_after_foreign_ownership_denial(owned,isolated_storage):
    _,a,b,ha,hb,pa,pb=owned
    headers=list(ha.items())+[('Idempotency-Key','one'),('Idempotency-Key','two')]
    before=snapshot(isolated_storage)
    assert a.put('/api/profile/'+pb['profile_id'],content='invalid',headers=headers).status_code==404
    assert a.put('/api/profile/'+pa['profile_id'],json=pa,headers=headers).status_code==422
    assert snapshot(isolated_storage)==before


def test_creation_replay_after_profile_change_conflicts_instead_of_restoring_old_data(pair):
    _,a,b,ha,hb=pair
    first=create(a,ha).json()['profile']
    changed=deepcopy(first);changed['personal']['name']='New revision'
    assert a.put('/api/profile/'+first['profile_id'],json=changed,headers=ha).status_code==200
    assert create(a,ha).status_code==409
    assert profiles._load(first['profile_id'])['personal']['name']=='New revision'


def test_assessment_same_key_other_profile_does_not_replay_questions(owned):
    _,a,b,ha,hb,pa,pb=owned
    first=start(a,ha,pa['profile_id'])
    assert b.post('/api/assessment/start',json={'profile_id':pa['profile_id'],'skill':'Python','num_questions':3},
                  headers=hb|{'Idempotency-Key':'start-intent'}).status_code==404
    second=start(b,hb,pb['profile_id'])
    assert first.status_code==second.status_code==200
    assert first.json()['assessment_id']!=second.json()['assessment_id']


def test_owned_prediction_stale_key_preserves_history(owned,isolated_storage,monkeypatch):
    _,a,b,ha,hb,pa,pb=owned
    assert predict(owned).status_code==200
    changed=deepcopy(pa);changed['education']['cgpa']=9
    assert a.put('/api/profile/'+pa['profile_id'],json=changed,headers=ha).status_code==200
    before=snapshot(isolated_storage)
    monkeypatch.setattr(profiles,'predict_with_model',lambda *args:pytest.fail('Stale replay inferred'))
    assert predict(owned).status_code==409
    assert predict(owned,client=b,headers=hb).status_code==404
    assert snapshot(isolated_storage)==before
