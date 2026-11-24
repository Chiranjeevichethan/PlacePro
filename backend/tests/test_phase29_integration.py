"""Combined final product/security workflows on the real production ASGI app."""
from copy import deepcopy

from backend.tests.test_prediction_ownership import owned,predict,snapshot
from backend.tests.test_profile_ownership import pair,encoded_password,identity
from backend.tests.test_assessment_ownership import answers
from backend.tests.test_predict import SAMPLE_STUDENT
from backend.tests.test_salary_prediction import VALID_PAYLOAD
from backend.tests.test_account_bound_idempotency import start
from backend.app.services import assessment_service as assessments,profile_service as profiles


def test_two_accounts_multiple_profiles_complete_product_workflow(owned,isolated_storage):
    app,a,b,ha,hb,pa,pb=owned
    additional=deepcopy(pa);additional.pop('profile_id');additional['personal']['name']='Second profile'
    second=a.post('/api/profile/verify',json=additional,headers=ha|{'Idempotency-Key':'additional-profile'})
    assert second.status_code==200
    own_ids=[r['profile_id'] for r in a.get('/api/account/profiles').json()['profiles']]
    assert len(own_ids)==2 and pb['profile_id'] not in own_ids
    assert len(b.get('/api/account/profiles').json()['profiles'])==1
    for client,headers in ((a,ha),(b,hb)):
        assert client.post('/api/predict',json=SAMPLE_STUDENT,headers=headers).status_code==200
        assert client.post('/api/salary-predict',json=VALID_PAYLOAD,headers=headers).status_code==200
    assert predict(owned).status_code==200
    first=start(a,ha,pa['profile_id']);assert first.status_code==200
    session=first.json();aid=session['assessment_id']
    submission={'profile_id':pa['profile_id'],'answers':answers(session)}
    path='/api/assessment/'+aid
    assert a.get(path,headers=ha).status_code==200
    assert a.post(path+'/submit',json=submission,headers=ha|{'Idempotency-Key':'final-submit'}).status_code==200
    assert a.post(path+'/submit',json=submission,headers=ha|{'Idempotency-Key':'final-submit'}).status_code==409
    assert a.get(path,headers=ha).json()['status']=='COMPLETED'
    assert len(a.get('/api/profile/'+pa['profile_id']+'/assessments',headers=ha).json()['assessments'])==1
    raw=profiles._load(pa['profile_id'])
    assert len(raw['assessment_evidence'])==len(raw['prediction_history'])==1
    assert predict(owned).status_code==409  # Evidence advanced the revision.
    assert predict(owned,key='post-assessment-prediction').status_code==200
    for suffix in ('readiness','placement-summary','eligibility','eligibility/company_001','recommendations','skills','performance'):
        response=a.get('/api/profile/'+pa['profile_id']+'/'+suffix,headers=ha)
        assert response.status_code==200,response.text
        assert response.json()['profile_id']==pa['profile_id'] and identity(app,b).account_id not in response.text
    before=snapshot(isolated_storage)
    for method,target,body in [('GET',path,None),('POST',path+'/submit',submission),
                              ('GET','/api/profile/'+pa['profile_id']+'/assessments',None),
                              ('POST','/api/profile/'+pa['profile_id']+'/predict',None)]:
        response=b.request(method,target,json=body,headers=hb)
        assert response.status_code==404 and pa['profile_id'] not in response.text and aid not in response.text
    assert snapshot(isolated_storage)==before
    assert a.post('/api/auth/logout',headers=ha).status_code==204
    assert a.get('/api/auth/session').status_code==401
    assert a.get('/api/profile/'+pa['profile_id']).status_code==401
    assert b.get('/api/profile/'+pb['profile_id']).status_code==200


def test_denied_integrated_requests_have_no_recovery_inference_or_json_side_effect(owned,isolated_storage,monkeypatch):
    _,a,b,ha,hb,pa,pb=owned
    session=start(a,ha,pa['profile_id']).json()
    def forbidden(*args,**kwargs):raise AssertionError('Denied request reached a business side effect')
    monkeypatch.setattr(assessments,'_sync_sessions',forbidden)
    monkeypatch.setattr(profiles,'predict_with_model',forbidden)
    before=snapshot(isolated_storage)
    for suffix in ('','/readiness','/placement-summary','/eligibility','/recommendations','/skills','/performance','/assessments'):
        response=b.get('/api/profile/'+pa['profile_id']+suffix,headers=hb)
        assert response.status_code==404 and response.json()=={'detail':'Profile not found.'}
    assert b.put('/api/profile/'+pa['profile_id'],json=pa,headers=hb).status_code==404
    assert b.post('/api/profile/verify',json=pa,headers=hb).status_code==404
    assert b.post('/api/profile/'+pa['profile_id']+'/predict',headers=hb|{'Idempotency-Key':'shared'}).status_code==404
    assert b.get('/api/assessment/'+session['assessment_id'],headers=hb).status_code==404
    assert b.post('/api/assessment/'+session['assessment_id']+'/submit',json={'profile_id':pa['profile_id'],'answers':answers(session)},headers=hb).status_code==404
    assert snapshot(isolated_storage)==before
