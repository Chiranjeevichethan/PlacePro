"""Profile confirmation is not identity authentication. All stores are isolated."""
import copy
import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from backend.tests.domain_app import app
from backend.app.services import assessment_service as assessments
from backend.app.services import profile_service as profiles
from backend.app.services import resume_intelligence
from backend.app.services.ml_feature_mapping import map_profile_to_ml_features
from backend.app.services.question_bank import get_questions
from backend.tests.test_resume import DOCX_MIME, make_docx


def upload(client, path, email='ananya@example.com', name='Ananya Rao'):
    return client.post(path, files={'file': ('resume.docx', make_docx(
        f'{name}\n{email}\nEDUCATION\nB.Tech Computer Science, Example College, 2021-2025\n'
        'CGPA: 8.4/10\nSKILLS\nPython, SQL\nCERTIFICATIONS\nAWS Certified Cloud Practitioner.\n'), DOCX_MIME)})


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def current(client):
    response = upload(client, '/api/profile/from-resume')
    assert response.status_code == 200, response.text
    draft = response.json()['profile']
    draft['personal']['phone'] = '+91 98765 43210'
    draft['education']['cgpa'] = 9.1
    draft['skills']['programming_languages'] = ['Java']
    draft['ml_inputs']['coding_skills'] = 7.5
    draft['additional_info']['attendance'] = 85
    result = client.post('/api/profile/verify', json=draft)
    assert result.status_code == 200, result.text
    return result.json()['profile']


@pytest.mark.parametrize('confirmed', [True, False])
@pytest.mark.parametrize('email,name', [
    ('ananya@example.com', 'Ananya Rao'),
    ('ANANYA@example.com', 'Ananya Rao'),
    ('another@example.com', 'Ananya Rao'),
    ('ananya@example.com', 'Different Student'),
])
def test_email_matches_never_merge_even_a_confirmed_profile(client, current, confirmed, email, name):
    current['verified'] = confirmed
    profiles._save(current)
    original_bytes = Path(profiles._profile_path(current['profile_id'])).read_bytes()
    response = upload(client, '/api/profile/from-resume', email, name)
    assert response.status_code == 200, response.text
    new = response.json()['profile']
    assert new['profile_id'] != current['profile_id']
    assert new['verified'] is False
    assert new['education']['cgpa'] == 8.4
    assert new['ml_inputs']['coding_skills'] is None
    assert new['additional_info']['attendance'] is None
    assert new['assessment_evidence'] == new['prediction_history'] == []
    assert Path(profiles._profile_path(current['profile_id'])).read_bytes() == original_bytes


@pytest.mark.parametrize('confirmed', [True, False])
@pytest.mark.parametrize('email,name', [
    ('ananya@example.com', 'Ananya Rao'), ('other@example.com', 'Other Student'),
])
def test_repeated_read_only_resume_review_preserves_profile_id_manual_values_and_store(client, current, confirmed, email, name):
    current['verified'] = confirmed
    profiles._save(current)
    before = {p.name: p.read_bytes() for p in Path(profiles.PROFILES_DIR).rglob('*') if p.is_file()}
    for _ in range(3):
        response = upload(client, '/api/resume/analyze', email, name)
        assert response.status_code == 200, response.text
        assert response.json()['extracted_profile']['email'] == email
        assert 'profile_id' not in response.json()['extracted_profile']
    after = {p.name: p.read_bytes() for p in Path(profiles.PROFILES_DIR).rglob('*') if p.is_file()}
    assert before == after


def test_repeated_direct_draft_creation_is_independent_and_does_not_overwrite(client, current):
    ids = [upload(client, '/api/profile/from-resume').json()['profile']['profile_id'] for _ in range(3)]
    assert len(set(ids + [current['profile_id']])) == 4
    assert profiles._load(current['profile_id'])['education']['cgpa'] == 9.1


@pytest.mark.parametrize('builder', [profiles.build_draft_from_resume, profiles.create_draft_with_analysis])
def test_ocr_rejection_does_not_create_a_draft_or_lock(builder, isolated_storage):
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buffer = io.BytesIO()
    writer.write(buffer)
    with pytest.raises(profiles.InvalidProfileError, match='OCR_REQUIRED'):
        builder('scanned.pdf', buffer.getvalue(), 'application/pdf')
    assert list(isolated_storage.profiles.rglob('*')) == []


def test_ocr_and_corrupt_api_rejections_preserve_existing_profile(client, current):
    original = profiles._load(current['profile_id'])
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buffer = io.BytesIO()
    writer.write(buffer)
    for content in (buffer.getvalue(), b'%PDF-corrupt'):
        result = client.post('/api/profile/from-resume', files={'file': ('scanned.pdf', content, 'application/pdf')})
        assert result.status_code == 422
    assert profiles._load(current['profile_id']) == original
    assert len(list(Path(profiles.PROFILES_DIR).glob('*.json'))) == 1


def test_analysis_failure_is_not_persisted_as_a_draft(client, monkeypatch, isolated_storage):
    def fail(*args):
        raise RuntimeError('injected analysis failure')
    monkeypatch.setattr(resume_intelligence, 'build_analysis', fail)
    result = upload(client, '/api/profile/from-resume')
    assert result.status_code == 500
    assert list(isolated_storage.profiles.rglob('*')) == []


def test_real_assessment_active_attempt_and_histories_survive_resume_review_and_correction(client, current, monkeypatch):
    profile_id = current['profile_id']
    start = assessments.start_assessment(profile_id, 'Python', 5)
    bank = {q['id']: q['correct_answer'] for q in get_questions('Python')}
    answers = {q['question_id']: bank[q['question_id']] for q in start['questions']}
    report = assessments.submit_assessment(start['assessment_id'], profile_id, answers)
    assert report['skill_score'] == 100
    active = assessments.start_assessment(profile_id, 'SQL', 5)
    # Inference is stubbed; this checks append-only history, never changes a model.
    full = profiles._load(profile_id)
    full['ml_inputs'].update(college_tier='Tier-2', backlogs=0, dsa_score=7,
        aptitude_score=80, communication_skills=7, ml_knowledge=5, system_design=5,
        open_source_contributions=0, extracurriculars=0)
    profiles.verify_profile(full)
    monkeypatch.setattr(profiles, 'predict_with_model', lambda _: {
        'placement_probability': .75, 'prediction': 'PLACED', 'confidence': .75, 'model_version': 'test-history'})
    assert profiles.predict_for_profile(profile_id)['ready_for_prediction'] is True
    before = profiles._load(profile_id)
    session_bytes = {p.name: p.read_bytes() for p in Path(assessments.ASSESSMENTS_DIR).glob('*.json')}
    for _ in range(3):
        assert upload(client, '/api/resume/analyze').status_code == 200
    assert profiles._load(profile_id) == before

    corrected = copy.deepcopy(before)
    corrected['skills']['programming_languages'] = ['C++']
    corrected['certifications'] = []
    corrected['education']['cgpa'] = 9.3
    corrected['achievements']['open_source_contributions'] = ['Documentation fix in an open-source project']
    corrected['assessment_evidence'] = []
    corrected['prediction_history'] = []
    corrected['original_resume_values'] = {}
    result = client.put(f'/api/profile/{profile_id}', json=corrected)
    assert result.status_code == 200, result.text
    edited = result.json()['profile']
    assert edited['profile_id'] == profile_id and edited['verified'] is False
    assert edited['assessment_evidence'] == before['assessment_evidence']
    assert edited['prediction_history'] == before['prediction_history']
    assert edited['original_resume_values'] == before['original_resume_values']
    assert edited['ml_inputs'] == before['ml_inputs']
    assert 'certifications' in edited['provenance']['user']
    assert 'skills.programming_languages' in edited['provenance']['user']
    assert map_profile_to_ml_features(edited)['certifications'] == 0
    assert client.get(f'/api/profile/{profile_id}/readiness').status_code == 422
    confirmed = client.post('/api/profile/verify', json=edited)
    assert confirmed.status_code == 200, confirmed.text
    performance = client.get(f'/api/profile/{profile_id}/performance')
    assert performance.status_code == 200, performance.text
    assert performance.json()['assessment_history'] == before['assessment_evidence']
    assert performance.json()['prediction_history'] == before['prediction_history']
    skills = client.get(f'/api/profile/{profile_id}/skills').json()['skills']
    py = next(s for s in skills if s['skill'] == 'Python')
    corrected_skill = next(s for s in skills if s['skill'] == 'C++')
    assert py['assessment_score'] == 100 and py['resume_detected'] is False
    assert corrected_skill['user_entered'] is True and corrected_skill['assessment_score'] is None
    assert assessments.get_assessment(active['assessment_id'])['profile_id'] == profile_id
    assert session_bytes == {p.name: p.read_bytes() for p in Path(assessments.ASSESSMENTS_DIR).glob('*.json')}


def test_new_extraction_is_unconfirmed_without_manufacturing_assessment_scores(client):
    response = upload(client, '/api/profile/from-resume')
    draft = response.json()['profile']
    assert draft['verified'] is False
    assert 'personal.email' in draft['provenance']['resume']
    assert draft['original_resume_values']['email'] == 'ananya@example.com'
    skills = client.get(f"/api/profile/{draft['profile_id']}/skills").json()['skills']
    assert all(s['profile_confirmed'] is False and s['assessment_score'] is None for s in skills)
    assert all(s['evidence_status'] == 'UNCONFIRMED' for s in skills)
