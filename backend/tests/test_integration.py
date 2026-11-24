"""Cross-module contracts with original models and retained isolated test stores."""
import copy
from io import BytesIO
from pathlib import Path

import pytest
from docx import Document
from fastapi.testclient import TestClient

from backend.tests.domain_app import app
from backend.app.services import assessment_service as assessments, profile_service as profiles
from backend.app.services.ml_feature_mapping import map_profile_to_ml_features
from backend.app.services.question_bank import get_questions
from backend.tests.support import http_get, http_post_json


@pytest.fixture
def client():
    return TestClient(app)


def student(profile_id='integration_student'):
    return {
        'profile_id': profile_id, 'personal': {'name': 'Integration Student', 'email': profile_id+'@example.test'},
        'education': {'branch': 'CSE', 'cgpa': 8.5, 'degree': 'B.Tech', 'college': 'Fixture College', 'graduation_year': 2027},
        'skills': {'programming_languages': ['Python', 'Java'], 'databases': ['SQL']},
        'projects': [{'project_name': 'Fixture Portal', 'technologies': ['React']}],
        'internships': [{'role': 'Developer', 'company': 'Fixture Organization'}],
        'certifications': [{'name': 'AWS Certified Cloud Practitioner', 'issuer': 'AWS', 'year': 2024}],
        'ml_inputs': {'college_tier': 'Tier-3', 'backlogs': 0, 'coding_skills': 7, 'dsa_score': 7,
            'aptitude_score': 80, 'communication_skills': 7, 'ml_knowledge': 5, 'system_design': 5,
            'open_source_contributions': 0, 'extracurriculars': 0},
    }


def confirm(client, body):
    response=client.post('/api/profile/verify', json=body)
    assert response.status_code==200, response.text
    return response.json()['profile']


def docx_resume():
    text=(Path(__file__).parent/'fixtures/resume_integrity_fictional.txt').read_text(encoding='utf-8')
    document=Document()
    for line in text.splitlines(): document.add_paragraph(line)
    stream=BytesIO(); document.save(stream)
    return ('integration.docx', stream.getvalue(), 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')


def complete(client, profile_id, skill='Python'):
    start=client.post('/api/assessment/start', json={'profile_id':profile_id,'skill':skill,'num_questions':5})
    assert start.status_code==200, start.text
    session=start.json()
    assert all('correct_answer' not in q and 'explanation' not in q for q in session['questions'])
    bank={q['id']:q['correct_answer'] for q in get_questions(skill)}
    answers={q['question_id']:bank[q['question_id']] for q in session['questions']}
    submit=client.post('/api/assessment/'+session['assessment_id']+'/submit', json={'profile_id':profile_id,'answers':answers})
    assert submit.status_code==200, submit.text
    return session,answers,submit.json()


def test_new_student_predictions_and_read_only_current_snapshots(client, isolated_storage):
    profile=confirm(client,student())
    path=Path(profiles._profile_path(profile['profile_id']))
    before=path.read_bytes()
    prefix='/api/profile/'+profile['profile_id']
    for endpoint in ('readiness','skills','eligibility','recommendations','performance','placement-summary'):
        response=client.get(prefix+'/'+endpoint)
        assert response.status_code==200, response.text
        assert response.json()['source_revision']==profile['revision']
    assert path.read_bytes()==before
    features=map_profile_to_ml_features(profile)
    direct=client.post('/api/predict',json=features).json()
    summary=client.get(prefix+'/placement-summary').json()
    assert summary['placement_probability']==direct['placement_probability']
    recorded=client.post(prefix+'/predict',headers={'Idempotency-Key':'integration-prediction'}).json()
    repeated=client.post(prefix+'/predict',headers={'Idempotency-Key':'integration-prediction'}).json()
    assert repeated==recorded and len(recorded['prediction_history'])==1
    assert recorded['prediction_history'][0]['source_inputs']==features
    assert client.get(prefix).json()['profile']['revision']==profile['revision']
    salary=client.post('/api/salary-predict',json=features)
    assert salary.status_code==200 and salary.json()['predicted_salary_lpa']>0
    assert salary.json()['model_version']=='placepro-salary-v2'
    without_tier=dict(features); without_tier.pop('college_tier')
    assert client.post('/api/salary-predict',json=without_tier).json()!=salary.json()
    assert len(list(isolated_storage.profiles.glob('*.json')))==1


def test_resume_review_correct_confirm_reupload_preserves_claims_and_history(client):
    uploaded=client.post('/api/profile/from-resume',files={'file':docx_resume()})
    assert uploaded.status_code==200,uploaded.text
    draft=uploaded.json()['profile']
    assert draft['revision']==1 and not draft['verified']
    assert len(draft['certifications'])==2
    originals=copy.deepcopy(draft['original_resume_values'])
    draft['skills']['programming_languages']=['Java']
    draft['certifications']=[]
    draft['ml_inputs']=student()['ml_inputs']
    profile=confirm(client,draft)
    prefix='/api/profile/'+profile['profile_id']
    session,_,_=complete(client,profile['profile_id'])
    client.post(prefix+'/predict',headers={'Idempotency-Key':'resume-history'})
    before=profiles._load(profile['profile_id'])
    for _ in range(2):
        preview=client.post('/api/resume/analyze',files={'file':docx_resume()})
        assert preview.status_code==200,preview.text
        assert profiles._load(profile['profile_id'])==before
    skills=client.get(prefix+'/skills').json()['skills']
    python=next(s for s in skills if s['skill']=='Python')
    assert python['assessment_score']==100 and not python['resume_detected']
    assert profiles._load(profile['profile_id'])['original_resume_values']==originals
    assert client.get('/api/assessment/'+session['assessment_id']).json()['status']=='COMPLETED'


def test_assessment_revision_downstream_and_historical_integrity(client):
    profile=confirm(client,student())
    prefix='/api/profile/'+profile['profile_id']
    client.post(prefix+'/predict',headers={'Idempotency-Key':'historical'})
    session,answers,result=complete(client,profile['profile_id'])
    assert result['skill_score']==100
    public=client.get('/api/assessment/'+session['assessment_id']).json()
    assert public['result']==result and public['status']=='COMPLETED'
    session_bytes=Path(assessments._session_path(session['assessment_id'])).read_bytes()
    previous=profiles._load(profile['profile_id'])
    assert previous['revision']==profile['revision']+1
    assert client.post('/api/assessment/'+session['assessment_id']+'/submit',json={'profile_id':profile['profile_id'],'answers':answers}).status_code==409
    cooldown=client.post('/api/assessment/start',json={'profile_id':profile['profile_id'],'skill':'Python','num_questions':5})
    assert cooldown.status_code==429 and int(cooldown.headers['Retry-After'])>0
    edited=copy.deepcopy(previous); edited['skills']['programming_languages']=[]; edited['education']['cgpa']=7
    saved=client.put(prefix,json=edited).json()['profile']
    assert not saved['verified'] and saved['revision']==previous['revision']+1
    assert client.get(prefix+'/readiness').status_code==422
    updated=confirm(client,saved)
    assert updated['assessment_evidence']==previous['assessment_evidence']
    assert updated['prediction_history']==previous['prediction_history']
    assert Path(assessments._session_path(session['assessment_id'])).read_bytes()==session_bytes
    for endpoint in ('readiness','eligibility','recommendations','skills','performance','placement-summary'):
        response=client.get(prefix+'/'+endpoint)
        assert response.status_code==200,response.text
        assert response.json()['source_revision']==updated['revision']
    performance=client.get(prefix+'/performance').json()
    assert performance['summary']['predictions']['latest_is_current'] is False
    assert performance['assessment_history']==previous['assessment_evidence']


def test_profile_persistence_failure_and_identical_retry(client,monkeypatch):
    profile=confirm(client,student()); path=Path(profiles._profile_path(profile['profile_id'])); before=path.read_bytes()
    original=profiles.os.replace
    def fail(source,target):
        if str(target)==str(path): raise OSError('isolated replacement failure')
        return original(source,target)
    edited=copy.deepcopy(profile); edited['education']['cgpa']=7
    with monkeypatch.context() as patch:
        patch.setattr(profiles.os,'replace',fail)
        failed=client.put('/api/profile/'+profile['profile_id'],json=edited)
        assert failed.status_code==503,failed.text
    assert path.read_bytes()==before
    saved=client.put('/api/profile/'+profile['profile_id'],json=edited).json()['profile']
    assert saved['revision']==profile['revision']+1
    assert client.put('/api/profile/'+profile['profile_id'],json=edited).json()['profile']==saved
    stale=copy.deepcopy(profile); stale['personal']['phone']='1111111111'
    assert client.put('/api/profile/'+profile['profile_id'],json=stale).status_code==409


def test_two_profiles_remain_independent_with_shared_email(client):
    first=confirm(client,student('integration_first'))
    body=student('integration_second');body['personal']['email']=first['personal']['email']
    second=confirm(client,body)
    complete(client,first['profile_id'])
    assert client.get('/api/profile/'+second['profile_id']).json()['profile']==second
    assert client.get('/api/profile/'+second['profile_id']+'/assessments').json()['assessments']==[]


@pytest.mark.parametrize('path,payload,status',[
    ('/api/predict',{},422),('/api/salary-predict',{},422),
    ('/api/assessment/start',{'profile_id':'absent','skill':'Python'},404),
    ('/api/assessment/start',{'profile_id':'integration_student','skill':'unknown'},404),
])
def test_request_contract_rejections(client,path,payload,status):
    confirm(client,student())
    response=client.post(path,json=payload)
    assert response.status_code==status,response.text
    assert 'detail' in response.json()


def test_cors_matches_configured_frontend_connection(client):
    from backend.app.main import create_app
    from backend.app.services.security_config import SecurityConfig
    # CORS belongs to the secured app, not the domain-only regression harness.
    with TestClient(create_app(SecurityConfig(mode='development',origins=('http://127.0.0.1:5174',))),
                    base_url='http://127.0.0.1:8765',client=('127.0.0.1',50000)) as secured:
        response=secured.options('/api/predict',headers={'Origin':'http://127.0.0.1:5174','Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'content-type'})
    assert response.status_code==200
    assert response.headers['Access-Control-Allow-Origin']=='http://127.0.0.1:5174'


@pytest.mark.live_http
def test_live_cross_module_contracts(live_server_url):
    body=student('integration_live')
    status,created=http_post_json(live_server_url+'/api/profile/verify',body)
    assert status==200,created
    profile=created['profile'];prefix=live_server_url+'/api/profile/'+profile['profile_id']
    for endpoint in ('readiness','eligibility','recommendations','performance','skills','placement-summary'):
        status,result=http_get(prefix+'/'+endpoint)
        assert status==200,result
        assert result['profile_id']==profile['profile_id'] and result['source_revision']==profile['revision']
    features=map_profile_to_ml_features(profile)
    for endpoint in ('/api/predict','/api/salary-predict'):
        status,result=http_post_json(live_server_url+endpoint,features)
        assert status==200,result
    _,current=http_get(prefix)
    assert current['profile']['prediction_history']==[] and current['profile']['assessment_evidence']==[]
