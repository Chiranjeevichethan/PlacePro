"""Real API contracts over isolated storage and unchanged DEMO companies."""
import copy

import pytest
from fastapi.testclient import TestClient

from backend.tests.domain_app import app
from backend.app.schemas_readiness import ReadinessResponse
from backend.app.services import assessment_service as assessments
from backend.app.services import company_store
from backend.app.services import profile_service as profiles
from backend.app.services import readiness_service as readiness
from backend.app.services.question_bank import get_questions
from backend.tests.test_skill_evidence import evidence, student


@pytest.fixture
def client():
    return TestClient(app)


def recommendation_for(body, company_id='company_001'):
    return next(item for group in body['recommendations'].values() for item in group
                if item['company_id'] == company_id)


@pytest.mark.parametrize('score,expected', [(74.5, 'SATISFIED'), (59.5, 'INSUFFICIENT'), (0, 'INSUFFICIENT')])
def test_fractional_scores_and_evidence_metadata_across_api_contracts(client, score, expected):
    profile = student(assessed=[evidence(score)])
    profiles._save(profile)
    before = copy.deepcopy(profiles._load(profile['profile_id']))
    analysis = readiness.get_readiness(profile['profile_id'])
    base = f"/api/profile/{profile['profile_id']}"
    for path in ('readiness', 'placement-summary', 'performance', 'recommendations',
                 'eligibility', 'eligibility/company_001', 'skills'):
        response = client.get(f'{base}/{path}')
        assert response.status_code == 200, (path, response.text)
        body = response.json()
        if path in ('readiness', 'placement-summary'):
            assert body['readiness_score'] == analysis['readiness_score']
            assert body['readiness_score'] == sum(body['readiness_breakdown'].values())
            assert body['readiness_level'] == analysis['readiness_level']
        elif path == 'performance':
            assert body['summary']['readiness_score'] == analysis['readiness_score']
            assert body['readiness'] == ReadinessResponse.model_validate(analysis).model_dump()
        elif path == 'recommendations':
            item = recommendation_for(body)
            assert item['readiness_score'] == analysis['readiness_score']
            assert ('Python' in item['skill_match']['required_matched']) == (expected == 'SATISFIED')
            assert item['eligibility_status'] == ('ELIGIBLE' if expected == 'SATISFIED' else 'INCOMPLETE')
        elif path == 'eligibility/company_001':
            groups = body['requirements']
            py = next(r for group in groups.values() for r in group if r['requirement'] == 'Required skill: Python')
            assert py['evidence_status'] == expected
            assert py['student_value'] == ('Python' if expected == 'SATISFIED' else score)
            assert 'Python' not in body['missing_information']
        elif path == 'skills':
            py = next(s for s in body['skills'] if s['skill'] == 'Python')
            assert py['assessment_score'] == score
            assert py['assessment_verified'] is True
            assert py['evidence_status'] == expected
            assert py['assessment_timestamp'] == evidence()['timestamp']
            assert py['evidence_sources'] == ['assessment']
            assert py['profile_confirmed'] is False
    assert profiles._load(profile['profile_id']) == before  # incomplete ML summary cannot append history
    assert company_store.get_company('company_001')['requirement_set']['verification_status'] == 'DEMO'


@pytest.mark.parametrize('path', ['readiness', 'placement-summary', 'performance', 'recommendations',
                                 'eligibility', 'eligibility/company_001'])
def test_unverified_profile_does_not_bypass_domain_gates_with_assessment(client, path):
    profile = student(assessed=[evidence()])
    profile['verified'] = False
    profiles._save(profile)
    response = client.get(f"/api/profile/{profile['profile_id']}/{path}")
    assert response.status_code == 422
    assert 'verified' in response.json()['detail']


def test_inspection_retains_unconfirmed_claims_without_creating_assessment_scores(client):
    profile = student(['Python'])
    profile['verified'] = False
    profiles._save(profile)
    response = client.get(f"/api/profile/{profile['profile_id']}/skills")
    assert response.status_code == 200
    py = next(s for s in response.json()['skills'] if s['skill'] == 'Python')
    assert py['resume_detected'] is True and py['profile_confirmed'] is False
    assert py['assessment_score'] is None and py['assessment_verified'] is False
    assert py['evidence_status'] == 'UNCONFIRMED'


@pytest.mark.parametrize('score', [None, '100', 101])
def test_bad_stored_assessment_cannot_create_readiness_or_matching_credit(client, score):
    profile = student(assessed=[evidence(score)])
    profiles._save(profile)
    base = f"/api/profile/{profile['profile_id']}"
    analysis = client.get(base + '/readiness')
    assert analysis.status_code == 200
    gap = next(g for g in analysis.json()['skill_gaps'] if g['skill'] == 'Python OR Java OR C++')
    assert gap['evidence_status'] == 'INVALID'
    eligibility = client.get(base + '/eligibility/company_001')
    assert eligibility.status_code == 200 and eligibility.json()['status'] == 'INCOMPLETE'
    recommendation = client.get(base + '/recommendations')
    assert recommendation.status_code == 200
    assert 'Python' in recommendation_for(recommendation.json())['skill_match']['required_missing']
    skills = client.get(base + '/skills')
    assert skills.status_code == 200
    py = next(s for s in skills.json()['skills'] if s['skill'] == 'Python')
    assert py['assessment_score'] is None and py['evidence_status'] == 'INVALID'


def test_real_fractional_assessment_persistence_and_all_downstream_services(client):
    profile = student()
    profiles._save(profile)
    start = client.post('/api/assessment/start', json={'profile_id': profile['profile_id'],
                        'skill': 'Python', 'num_questions': 25})
    assert start.status_code == 200
    session = start.json()
    bank = get_questions('Python')
    # Find a real 41/55-point answer subset rather than supplying a client score.
    subsets = {0: []}
    for q in bank:
        for total, selected in list(subsets.items()):
            subsets.setdefault(total + q['points'], selected + [q])
    answers = {q['id']: q['correct_answer'] for q in subsets[41]}
    submit = client.post(f"/api/assessment/{session['assessment_id']}/submit",
                         json={'profile_id': profile['profile_id'], 'answers': answers})
    assert submit.status_code == 200
    assert submit.json()['skill_score'] == 74.5
    assert submit.json()['level'] == 'Intermediate'
    stored = profiles._load(profile['profile_id'])
    assert stored['skills'] == profile['skills'] and stored['ml_inputs'] == profile['ml_inputs']
    assert len(stored['assessment_evidence']) == 1
    assert stored['assessment_evidence'][0]['score'] == 74.5
    base = f"/api/profile/{profile['profile_id']}"
    assert client.get(base + '/eligibility/company_001').json()['status'] == 'ELIGIBLE'
    assert 'Python' in recommendation_for(client.get(base + '/recommendations').json())['skill_match']['required_matched']
    analysis = client.get(base + '/readiness').json()
    assert not any(g['skill'] == 'Python OR Java OR C++' for g in analysis['skill_gaps'])
    assert client.get(base + '/performance').json()['readiness'] == analysis
    assert client.get(base + '/assessments').json()['assessments'] == stored['assessment_evidence']


def test_edit_api_reconfirmation_keeps_measurement_and_rejects_client_forgery(client):
    profile = student(assessed=[evidence(20)])
    profiles._save(profile)
    submitted = copy.deepcopy(profile)
    submitted['skills']['other_skills'].append('Python')
    submitted['ml_inputs']['coding_skills'] = 10
    submitted['assessment_evidence'] = [evidence(100, assessment_id='forged')]
    response = client.put(f"/api/profile/{profile['profile_id']}", json=submitted)
    assert response.status_code == 200
    edited = response.json()['profile']
    assert edited['verified'] is False
    assert edited['assessment_evidence'] == profile['assessment_evidence']
    verified = client.post('/api/profile/verify', json=edited)
    assert verified.status_code == 200
    result = client.get(f"/api/profile/{profile['profile_id']}/eligibility/company_001")
    assert result.json()['status'] == 'INCOMPLETE'
    py = next(r for r in result.json()['requirements']['unknown'] if r['required_value'] == 'Python')
    assert py['evidence_status'] == 'INSUFFICIENT' and py['student_value'] == 20


def test_recommendations_use_one_profile_snapshot(monkeypatch):
    from backend.app.services import recommendation_service
    profile = student(assessed=[evidence(74.5)])
    calls = []
    monkeypatch.setattr(recommendation_service, 'get_profile', lambda profile_id: (calls.append(profile_id) or profile, {}))
    result = recommendation_service.get_recommendations(profile['profile_id'])
    assert calls == [profile['profile_id']]
    assert recommendation_for(result)['readiness_score'] == readiness.readiness_for_profile(profile)['readiness_score']
