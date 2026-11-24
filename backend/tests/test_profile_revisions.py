"""Revision, source freshness and history regressions; autouse stores are isolated."""
import copy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from threading import Barrier, Event, Thread

import pytest
from fastapi.testclient import TestClient

from backend.tests.domain_app import app
from backend.app.services import assessment_service as assessments
from backend.app.services import profile_service as profiles
from backend.app.services import performance_service, readiness_service, recommendation_service
from backend.app.services.question_bank import get_questions


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def current(client, monkeypatch):
    response = client.post('/api/profile/verify', json={
        'profile_id': 'revision-student', 'personal': {'name': 'Ananya Rao', 'email': 'fixture@example.com'},
        'education': {'cgpa': 8.5, 'branch': 'CSE', 'graduation_year': 2027},
        'skills': {'programming_languages': ['Python', 'Java'], 'databases': ['SQL']},
        'projects': [{'project_name': 'Placement Portal', 'technologies': ['React']}],
        'internships': [{'role': 'Developer', 'company': 'Example'}],
        'certifications': [{'name': 'AWS Certified Cloud Practitioner', 'issuer': 'AWS'}],
        'ml_inputs': {'college_tier': 'Tier-2', 'backlogs': 0, 'coding_skills': 7,
            'dsa_score': 7, 'aptitude_score': 80, 'communication_skills': 7,
            'ml_knowledge': 5, 'system_design': 5, 'open_source_contributions': 0, 'extracurriculars': 0},
    })
    assert response.status_code == 200, response.text
    def infer(inputs):
        probability = .8 if inputs['cgpa'] >= 8 else .4
        return {'placement_probability': probability, 'prediction': 'PLACED' if probability >= .5 else 'NOT PLACED',
                'confidence': max(probability, 1 - probability), 'model_version': 'revision-fixture'}
    monkeypatch.setattr(profiles, 'predict_with_model', infer)
    monkeypatch.setattr(recommendation_service, 'predict_with_model', infer)
    return response.json()['profile']


def put(client, profile):
    return client.put(f"/api/profile/{profile['profile_id']}", json=profile)


def test_creation_changed_identical_and_confirmation_revision(client, current):
    assert current['revision'] == 1 and current['verified']
    path = Path(profiles._profile_path(current['profile_id']))
    before = path.read_bytes()
    assert put(client, current).json()['profile']['revision'] == 1
    assert path.read_bytes() == before
    edited = copy.deepcopy(current)
    edited['education']['cgpa'] = 7
    changed = put(client, edited).json()['profile']
    assert changed['revision'] == 2 and changed['verified'] is False
    assert put(client, edited).json()['profile']['revision'] == 2  # lost response replay
    confirmed = client.post('/api/profile/verify', json=changed).json()['profile']
    assert confirmed['revision'] == 3 and confirmed['verified']
    assert client.post('/api/profile/verify', json=changed).json()['profile']['revision'] == 3


def test_legacy_get_does_not_write_and_first_change_advances(client, current):
    path = Path(profiles._profile_path(current['profile_id']))
    legacy = copy.deepcopy(current)
    legacy.pop('revision')
    path.write_text(json.dumps(legacy), encoding='utf-8')
    before = path.read_bytes()
    read = client.get(f"/api/profile/{current['profile_id']}").json()['profile']
    assert read['revision'] == 0 and path.read_bytes() == before
    assert put(client, read).json()['profile']['revision'] == 0
    assert path.read_bytes() == before
    read['personal']['phone'] = '9876543210'
    updated = put(client, read).json()['profile']
    assert updated['revision'] == 1 and not updated['verified']


@pytest.mark.parametrize('operation', ['edit', 'verify'])
def test_stale_full_profile_and_confirmation_cannot_overwrite(client, current, operation):
    newer = copy.deepcopy(current)
    newer['personal']['phone'] = '9876543210'
    saved = put(client, newer).json()['profile']
    stale = copy.deepcopy(current)
    stale['skills']['programming_languages'] = ['C++']
    response = put(client, stale) if operation == 'edit' else client.post('/api/profile/verify', json=stale)
    assert response.status_code == 409
    assert profiles._load(current['profile_id'])['revision'] == saved['revision']
    assert profiles._load(current['profile_id'])['personal']['phone'] == '9876543210'
    assert not profiles._load(current['profile_id'])['verified']


def test_omitted_revision_keeps_legacy_update_contract(client, current):
    current.pop('revision')
    current['education']['cgpa'] = 7
    response = put(client, current)
    assert response.status_code == 200 and response.json()['profile']['revision'] == 2


@pytest.mark.parametrize('path,value', [('education.cgpa', -1), ('education.cgpa', 12),
    ('ml_inputs.coding_skills', 100), ('ml_inputs.backlogs', -1), ('ml_inputs.backlogs', .5)])
def test_invalid_update_preserves_bytes_and_revision(client, current, path, value):
    original = Path(profiles._profile_path(current['profile_id'])).read_bytes()
    section, field = path.split('.')
    current[section][field] = value
    response = put(client, current)
    assert response.status_code == 422, response.text
    assert Path(profiles._profile_path(current['profile_id'])).read_bytes() == original


@pytest.mark.parametrize('operation', ['edit', 'verify'])
def test_persistence_failure_preserves_last_valid_profile(client, current, monkeypatch, operation):
    path = Path(profiles._profile_path(current['profile_id']))
    before = path.read_bytes()
    current['education']['cgpa'] = 7
    def fail(*args):
        raise OSError('injected replace failure')
    monkeypatch.setattr(profiles.os, 'replace', fail)
    response = put(client, current) if operation == 'edit' else client.post('/api/profile/verify', json=current)
    assert response.status_code == 503
    assert path.read_bytes() == before
    assert current['revision'] == 1


def test_completion_validation_precedes_persistence(client, current, monkeypatch):
    before = Path(profiles._profile_path(current['profile_id'])).read_bytes()
    def fail(*args):
        raise profiles.InvalidProfileError('injected completion failure')
    monkeypatch.setattr(profiles, 'check_profile_completion', fail)
    current['education']['cgpa'] = 7
    assert put(client, current).status_code == 422
    assert Path(profiles._profile_path(current['profile_id'])).read_bytes() == before


@pytest.mark.parametrize('identical', [True, False])
def test_concurrent_revision_edits_are_serialized_without_lost_updates(current, identical):
    barrier = Barrier(6)
    def update(index):
        submitted = copy.deepcopy(current)
        submitted['personal']['phone'] = 'same' if identical else str(index)
        barrier.wait(timeout=10)
        try:
            return profiles.update_profile(current['profile_id'], submitted)[0]['revision']
        except profiles.ProfileConflictError:
            return 'conflict'
    with ThreadPoolExecutor(max_workers=6) as executor:
        outcomes = list(executor.map(update, range(6)))
    assert outcomes.count(2) == (6 if identical else 1)
    assert outcomes.count('conflict') == (0 if identical else 5)
    assert profiles._load(current['profile_id'])['revision'] == 2


def test_revision_and_source_metadata_cannot_be_forged(client, current):
    current['revision'] = 999
    current['assessment_evidence'] = [{'skill': 'Python', 'score': 100}]
    assert put(client, current).status_code == 200  # identical claims do not mutate
    saved = profiles._load(current['profile_id'])
    assert saved['revision'] == 1 and saved['assessment_evidence'] == []
    current['education']['cgpa'] = 7
    assert put(client, current).status_code == 409


def test_summary_is_read_only_and_predictions_have_explicit_source(client, current):
    profile_id = current['profile_id']
    before = Path(profiles._profile_path(profile_id)).read_bytes()
    for _ in range(3):
        response = client.get(f'/api/profile/{profile_id}/placement-summary')
        assert response.status_code == 200, response.text
        assert response.json()['source_revision'] == 1
        assert response.json()['placement_probability'] == .8
    assert Path(profiles._profile_path(profile_id)).read_bytes() == before
    for _ in range(3):
        response = client.post(f'/api/profile/{profile_id}/predict', headers={'Idempotency-Key': 'fixture-request'})
        assert response.status_code == 200
    stored = profiles._load(profile_id)
    assert stored['revision'] == 1 and len(stored['prediction_history']) == 1
    entry = stored['prediction_history'][0]
    assert entry['source_revision'] == 1 and entry['source_inputs']['cgpa'] == 8.5
    current['education']['cgpa'] = 7
    changed = put(client, current).json()['profile']
    assert stored['prediction_history'] == profiles._load(profile_id)['prediction_history']
    assert client.post(f'/api/profile/{profile_id}/predict', headers={'Idempotency-Key': 'fixture-request'}).status_code == 409
    confirmed = client.post('/api/profile/verify', json=changed).json()['profile']
    performance = client.get(f'/api/profile/{profile_id}/performance').json()
    assert performance['source_revision'] == confirmed['revision']
    assert performance['summary']['predictions']['latest_is_current'] is False
    assert performance['prediction_history'] == stored['prediction_history']
    assert client.get(f'/api/profile/{profile_id}/placement-summary').json()['placement_probability'] == .4


def test_legacy_history_revision_is_unknown_and_never_backfilled(client, current):
    current['prediction_history'] = [{'timestamp': '2025-01-01T00:00:00+00:00', 'model_version': 'legacy',
        'placement_probability': .6, 'prediction': 'PLACED'}]
    profiles._save(current)
    before = Path(profiles._profile_path(current['profile_id'])).read_bytes()
    performance = client.get(f"/api/profile/{current['profile_id']}/performance").json()
    summary = performance['summary']['predictions']
    assert summary['latest_source_revision'] is None and summary['latest_is_current'] is None
    assert performance['prediction_history'][0]['source_revision'] is None
    assert Path(profiles._profile_path(current['profile_id'])).read_bytes() == before


def test_downstream_outputs_refresh_after_confirmed_corrections(client, current):
    profile_id = current['profile_id']
    paths = ['readiness', 'eligibility', 'eligibility/company_001', 'recommendations', 'skills', 'performance']
    before = {path: client.get(f'/api/profile/{profile_id}/{path}').json() for path in paths}
    assert all(value['source_revision'] == 1 for value in before.values())
    current['education']['cgpa'] = 4
    current['skills']['programming_languages'] = []
    current['certifications'] = []
    updated = put(client, current).json()['profile']
    for path in paths[:-2]:
        assert client.get(f'/api/profile/{profile_id}/{path}').status_code == 422
    confirmed = client.post('/api/profile/verify', json=updated).json()['profile']
    after = {path: client.get(f'/api/profile/{profile_id}/{path}').json() for path in paths}
    assert all(value['source_revision'] == confirmed['revision'] for value in after.values())
    assert after['readiness']['readiness_score'] < before['readiness']['readiness_score']
    assert after['eligibility/company_001']['status'] == 'NOT_ELIGIBLE'
    assert 'Python' not in [entry['skill'] for entry in after['skills']['skills']]
    assert after['recommendations'] != before['recommendations']


def test_assessment_partial_recovery_advances_once_and_edits_preserve_history(client, current, monkeypatch):
    profile_id = current['profile_id']
    session = assessments.start_assessment(profile_id, 'Python', 5)
    bank = {question['id']: question['correct_answer'] for question in get_questions('Python')}
    answers = {question['question_id']: bank[question['question_id']] for question in session['questions']}
    real_save = assessments._save_session
    def fail_completion(value):
        if value['status'] == 'COMPLETED':
            raise OSError('injected session completion failure')
        real_save(value)
    monkeypatch.setattr(assessments, '_save_session', fail_completion)
    with pytest.raises(OSError):
        assessments.submit_assessment(session['assessment_id'], profile_id, answers)
    projected = profiles._load(profile_id)
    assert projected['revision'] == 2 and len(projected['assessment_evidence']) == 1
    monkeypatch.setattr(assessments, '_save_session', real_save)
    recovered = assessments.get_assessment(session['assessment_id'])
    assert recovered['status'] == 'COMPLETED'
    assert profiles._load(profile_id)['revision'] == 2
    evidence = copy.deepcopy(profiles._load(profile_id)['assessment_evidence'])
    session_bytes = Path(assessments._session_path(session['assessment_id'])).read_bytes()
    projected['skills']['programming_languages'] = []
    changed = put(client, projected).json()['profile']
    confirmed = client.post('/api/profile/verify', json=changed).json()['profile']
    assert confirmed['assessment_evidence'] == evidence
    assert Path(assessments._session_path(session['assessment_id'])).read_bytes() == session_bytes
    skills = client.get(f'/api/profile/{profile_id}/skills').json()['skills']
    python = next(entry for entry in skills if entry['skill'] == 'Python')
    assert python['assessment_score'] == 100 and python['assessment_verified']


def test_performance_uses_one_profile_snapshot(current, monkeypatch):
    calls = []
    original = profiles.get_profile
    def once(profile_id):
        calls.append(profile_id)
        assert len(calls) == 1
        return original(profile_id)
    monkeypatch.setattr(profiles, 'get_profile', once)
    result = performance_service.get_performance(current['profile_id'])
    assert result['source_revision'] == result['readiness']['source_revision'] == 1


def test_summary_uses_one_snapshot(current, monkeypatch):
    calls = []
    original = readiness_service.get_profile
    def once(profile_id):
        calls.append(profile_id)
        assert len(calls) == 1
        return original(profile_id)
    monkeypatch.setattr(readiness_service, 'get_profile', once)
    assert readiness_service.get_placement_summary(current['profile_id'])['source_revision'] == 1


@pytest.mark.parametrize('record_kind', ['profile', 'assessment'])
def test_open_reader_serializes_with_atomic_record_replacement(current, monkeypatch, record_kind):
    """An open JSON reader must not cause Windows replacement to fail."""
    if record_kind == 'profile':
        load = lambda: profiles._load(current['profile_id'])
        replacement = copy.deepcopy(current)
        replacement['personal']['phone'] = 'new phone'
        save = lambda: profiles._save(replacement)
    else:
        public = assessments.start_assessment(current['profile_id'], 'Python', 5)
        replacement = assessments._load_session(public['assessment_id'])
        replacement['status_reason'] = 'replacement fixture'
        load = lambda: assessments._load_session(public['assessment_id'])
        save = lambda: assessments._save_session(replacement)

    reader_open, release_reader, writer_started, writer_finished = (Event() for _ in range(4))
    real_load = json.load
    failures = []

    def hold_reader(handle, *args, **kwargs):
        from threading import current_thread
        if current_thread().name == 'integrity-reader':
            reader_open.set()
            assert release_reader.wait(timeout=10)
        return real_load(handle, *args, **kwargs)

    def read():
        try:
            load()
        except Exception as exc:
            failures.append(exc)

    def write():
        writer_started.set()
        try:
            save()
        except Exception as exc:
            failures.append(exc)
        finally:
            writer_finished.set()

    monkeypatch.setattr(json, 'load', hold_reader)
    reader = Thread(target=read, name='integrity-reader')
    writer = Thread(target=write, name='integrity-writer')
    reader.start()
    try:
        assert reader_open.wait(timeout=10)
        writer.start()
        assert writer_started.wait(timeout=10)
        assert not writer_finished.wait(timeout=.3), f'Writer finished with an open reader: {failures!r}'
    finally:
        release_reader.set()
        reader.join(timeout=10)
        if writer.ident is not None:
            writer.join(timeout=10)
    assert not reader.is_alive() and not writer.is_alive()
    assert failures == []
    assert load() == replacement
