"""Evidence regressions use isolated stores and the existing DEMO requirements."""
import copy
import math

import pytest

from backend.app.services import assessment_service as assessments
from backend.app.services import company_store
from backend.app.services import eligibility_service as eligibility
from backend.app.services import profile_service as profiles
from backend.app.services import readiness_service as readiness
from backend.app.services import recommendation_service as recommendations
from backend.app.services.skill_evidence import resolve_skill_evidence, skill_status


def evidence(score=100, skill='Python', timestamp='2026-11-07T00:00:00+00:00',
             attempt=1, assessment_id='evidence-one', **extra):
    return {'skill': skill, 'score': score, 'level': 'Advanced', 'source': 'assessment',
            'verified': True, 'timestamp': timestamp, 'attempt': attempt,
            'assessment_id': assessment_id, **extra}


def student(python=None, assessed=()):
    # Meets the existing company_001 DEMO requirements except for variable Python.
    return {'profile_id': 'evidence-student', 'verified': True,
        'personal': {'name': 'Evidence Student', 'email': 'evidence@example.com'},
        'education': {'cgpa': 8.2, 'branch': 'CSE', 'graduation_year': 2026},
        'skills': {'other_skills': ['SQL', 'Data Structures', 'AWS', 'Docker'] + (python or [])},
        'projects': [{'project_name': 'One'}, {'project_name': 'Two'}],
        'internships': [{'company': 'Fixture'}], 'experience': [],
        'certifications': [], 'achievements': {},
        'ml_inputs': {'backlogs': 0, 'aptitude_score': 80},
        'provenance': {'resume': ['skills.other_skills'], 'user': [], 'ml': []},
        'assessment_evidence': list(assessed), 'prediction_history': []}


def test_assessment_only_coverage():
    profile = student(assessed=[evidence()])
    entries = readiness.collect_verified_skills(profile)
    assert 'Python' in {e['skill'] for e in entries}
    assert not any(g['skill'] == 'Python OR Java OR C++' for g in readiness.compute_skill_gaps(entries))
    # Data Structures + language = round(2/7*30) + existing 5-point bonus.
    assert readiness.compute_readiness_score(profile, entries)['breakdown']['technical_skills'] == 14


def test_assessment_only_eligibility():
    profile = student(assessed=[evidence()])
    company = company_store.get_company('company_001')
    assert eligibility.evaluate_company_eligibility(profile, company)['status'] == 'ELIGIBLE'


def test_low_assessment_overrides_resume_consistently():
    profile = student(python=['Python'], assessed=[evidence(20)])
    company = company_store.get_company('company_001')
    entries = readiness.collect_verified_skills(profile)
    assert 'Python' not in {e['skill'] for e in entries}
    result = eligibility.evaluate_company_eligibility(profile, company)
    assert result['status'] == 'INCOMPLETE'
    py = next(r for r in result['requirements']['unknown'] if r['required_value'] == 'Python')
    assert py['student_value'] == 20
    assert 'Python' not in result['missing_information']


def test_fractional_readiness_api():
    from fastapi.testclient import TestClient
    from backend.tests.domain_app import app
    profile = student(assessed=[evidence(74.5)])
    profiles._save(profile)
    response = TestClient(app).get('/api/profile/evidence-student/readiness')
    assert response.status_code == 200
    body = response.json()
    assert body['readiness_score'] == sum(body['readiness_breakdown'].values())
    assert body['readiness_breakdown']['technical_skills'] == 12.7


@pytest.mark.parametrize('python,records,expected', [
    (['Python'], [], 'SATISFIED'),
    ([], [evidence()], 'SATISFIED'),
    (['Python'], [evidence(100)], 'SATISFIED'),
    (['Python'], [evidence(59.5)], 'INSUFFICIENT'),
    ([], [evidence(60)], 'SATISFIED'),
    (['Python'], [evidence(0)], 'INSUFFICIENT'),
    ([], [], 'MISSING'),
    ([], [evidence(100, timestamp='2000-01-01T00:00:00+00:00')], 'SATISFIED'),
    ([], [evidence(None)], 'INVALID'),
    ([], [evidence(100, verified=False)], 'UNCONFIRMED'),
    (['Python'], [evidence(100, verified=False)], 'SATISFIED'),
    (['Python'], [evidence(None)], 'SATISFIED'),
], ids=['resume', 'assessment', 'multiple', 'conflict', 'threshold', 'measured-zero',
        'missing', 'old-no-expiry', 'invalid', 'unconfirmed', 'unconfirmed-with-claim', 'invalid-with-claim'])
def test_equivalent_evidence_across_services(python, records, expected):
    profile = student(python, copy.deepcopy(records))
    original = copy.deepcopy(profile)
    resolved = resolve_skill_evidence(profile)
    assert skill_status(resolved, 'Python') == expected
    entries = readiness.collect_verified_skills(profile)
    has_python = 'Python' in {e['skill'] for e in entries}
    assert has_python == (expected == 'SATISFIED')
    analysis = readiness.readiness_for_profile(profile)
    language_gap = next((g for g in analysis['skill_gaps'] if g['skill'] == 'Python OR Java OR C++'), None)
    assert (language_gap is None) == has_python
    if language_gap:
        assert language_gap['evidence_status'] == expected
    company = company_store.get_company('company_001')
    result = eligibility.evaluate_company_eligibility(profile, company)
    assert result['status'] == ('ELIGIBLE' if has_python else 'INCOMPLETE')
    all_checks = result['requirements']['passed'] + result['requirements']['unknown']
    py = next(r for r in all_checks if r['requirement'] == 'Required skill: Python')
    assert py['evidence_status'] == expected
    match = recommendations.compute_skill_match(company, set(), evidence=resolved)
    assert ('Python' in match['required_matched']) == has_python
    rec = recommendations.build_recommendation(profile, company, analysis, None, set())
    assert rec['skill_match'] == match
    assert rec['eligibility_status'] == result['status']
    assert rec['readiness_score'] == analysis['readiness_score']
    if expected == 'INSUFFICIENT':
        assert any('below PlacePro' in reason for reason in rec['reasons'])
    assert profile == original  # projections never rewrite storage/history


@pytest.mark.parametrize('score', [None, '100', True, math.nan, math.inf, -1, 101])
def test_invalid_assessment_never_becomes_zero_or_a_bonus(score):
    profile = student(assessed=[evidence(score)])
    resolved = resolve_skill_evidence(profile)
    assert resolved['skills']['Python']['score'] is None
    assert skill_status(resolved, 'Python') == 'INVALID'
    assert readiness._assessment_bonus(profile) == 0
    assert assessments.get_assessment_evidence(profile) == []


def test_wrong_source_cannot_grant_assessment_credit():
    profile = student(assessed=[evidence(source='user')])
    assert skill_status(resolve_skill_evidence(profile), 'Python') == 'INVALID'
    assert readiness._assessment_bonus(profile) == 0


def test_manually_entered_scores_are_not_named_skill_evidence():
    profile = student()
    profile['ml_inputs'].update(coding_skills=10, dsa_score=10, communication_skills=10,
                               ml_knowledge=10, system_design=10)
    resolved = resolve_skill_evidence(profile)
    assert skill_status(resolved, 'Python') == 'MISSING'
    assert skill_status(resolved, 'Communication') == 'MISSING'
    assert skill_status(resolved, 'Algorithms') == 'MISSING'
    company = company_store.get_company('company_001')
    result = eligibility.evaluate_company_eligibility(profile, company)
    assert result['status'] == 'INCOMPLETE'
    assert any(r['requirement'] == 'Minimum Aptitude Score' for r in result['requirements']['passed'])


def test_provenance_is_per_field_and_does_not_confirm_other_fields():
    profile = student()
    profile['skills'] = {'programming_languages': ['Python'], 'frameworks': ['React']}
    profile['provenance'] = {'resume': ['skills.programming_languages'], 'user': ['skills.frameworks']}
    resolved = resolve_skill_evidence(profile)
    py = resolved['skills']['Python']['evidence'][0]
    react = resolved['skills']['React']['evidence'][0]
    assert py['source'] == 'resume' and react['source'] == 'user'
    assert py['path'] == 'skills.programming_languages'
    assert py['timestamp'] is None
    profile['verified'] = False
    assert skill_status(resolve_skill_evidence(profile), 'Python') == 'UNCONFIRMED'
    profile['assessment_evidence'] = [evidence()]
    # Independent assessment verification never verifies the manual/resume claim.
    py = resolve_skill_evidence(profile)['skills']['Python']
    assert py['status'] == 'SATISFIED' and not py['profile_confirmed']


@pytest.mark.parametrize('reverse', [False, True])
def test_latest_completion_not_best_score_or_largest_attempt(reverse):
    records = [evidence(100, attempt=3, timestamp='2026-11-06T00:00:00Z', assessment_id='older'),
               evidence(20, attempt=1, timestamp='2026-11-07T01:00:00+01:00', assessment_id='newer')]
    if reverse:
        records.reverse()
    profile = student(['Python'], records)
    latest = assessments.get_assessment_evidence(profile)
    assert latest[0]['assessment_id'] == 'newer'
    assert skill_status(resolve_skill_evidence(profile), 'Python') == 'INSUFFICIENT'
    assert readiness._assessment_bonus(profile) == 0


@pytest.mark.parametrize('stamp', [None, '', 'malformed', '2026-11-08T00:00:00'])
def test_unusable_timestamps_are_preserved_and_sort_before_usable(stamp):
    profile = student(assessed=[evidence(0, timestamp=stamp, attempt=10),
        evidence(60, timestamp='2026-11-06T00:00:00Z', assessment_id='aware')])
    original = copy.deepcopy(profile)
    assert assessments.get_assessment_evidence(profile)[0]['assessment_id'] == 'aware'
    assert profile == original


def test_same_timestamp_ordinal_and_id_ties_are_deterministic():
    records = [evidence(100, attempt=1, assessment_id='a'), evidence(0, attempt=2, assessment_id='b')]
    for items in (records, list(reversed(records))):
        assert assessments.get_assessment_evidence(student(assessed=items))[0]['assessment_id'] == 'b'


def test_new_invalid_record_does_not_resurrect_old_passing_attempt():
    profile = student(assessed=[evidence(), evidence(None, timestamp='2026-11-08T00:00:00Z',
                                                  assessment_id='new-invalid')])
    assert skill_status(resolve_skill_evidence(profile), 'Python') == 'INVALID'
    assert assessments.get_assessment_evidence(profile) == []
    assert readiness._assessment_bonus(profile) == 0


def test_duplicate_aliases_and_attempts_do_not_inflate_strength_or_bonus():
    profile = student(['Python', 'python', 'Python,python'], [evidence(80), evidence(80)])
    profile['projects'] = [{'technologies': ['Python', 'python']}, {'technologies': ['Python']}]
    entries = readiness.collect_verified_skills(profile)
    py_entries = [e for e in entries if e['skill'] == 'Python']
    assert len(py_entries) == 4  # one mention, two projects, one latest assessment
    strength = next(s for s in readiness.compute_strengths(entries) if s['skill'] == 'Python')
    assert '2 projects' in strength['evidence']
    assert readiness._assessment_bonus(profile) == 4
    assert readiness.compute_readiness_score(profile, entries)['breakdown']['technical_skills'] == 13


def test_combined_assessment_normalizes_without_double_bonus_credit():
    profile = student(assessed=[evidence(100, skill='HTML/CSS'),
                               evidence(60, skill='Python', assessment_id='python')])
    resolved = resolve_skill_evidence(profile)
    assert {'HTML', 'CSS', 'Python'} <= resolved['satisfied_skills']
    assert readiness._assessment_bonus(profile) == 4  # avg(100,60), not avg(100,100,60)
    profile['skills']['other_skills'].append('js')
    profile['projects'] = [{'project_name': 'Web'}]
    company = company_store.get_company('company_005')
    assert eligibility.evaluate_company_eligibility(profile, company)['status'] == 'ELIGIBLE'
    assert recommendations.compute_skill_match(company, set(), evidence=resolve_skill_evidence(profile))['required_missing'] == []


@pytest.mark.parametrize('score,expected', [(None, 'MISSING'), (100, 'SATISFIED'), (20, 'INSUFFICIENT')])
def test_profile_edit_removal_reconfirmation_preserves_independent_evidence(score, expected):
    records = [] if score is None else [evidence(score)]
    profile = student(['Python'], records)
    profile['original_resume_values'] = {'skills.other_skills': list(profile['skills']['other_skills'])}
    profiles._save(profile)
    submitted = copy.deepcopy(profile)
    submitted['skills']['other_skills'].remove('Python')
    submitted['assessment_evidence'] = [evidence(100, assessment_id='forged')]
    edited, _ = profiles.update_profile(profile['profile_id'], submitted)
    assert edited['verified'] is False
    assert edited['assessment_evidence'] == records
    for service, error in [(readiness.get_readiness, readiness.ReadinessServiceError),
                           (recommendations.get_recommendations, recommendations.RecommendationServiceError)]:
        with pytest.raises(error):
            service(profile['profile_id'])
    with pytest.raises(eligibility.EligibilityServiceError):
        eligibility.get_eligibility(profile['profile_id'], 'company_001')
    confirmed, _ = profiles.verify_profile(edited)
    assert confirmed['assessment_evidence'] == records
    assert confirmed['original_resume_values'] == profile['original_resume_values']
    assert skill_status(resolve_skill_evidence(confirmed), 'Python') == expected
    assert ('Python' in {e['skill'] for e in readiness.collect_verified_skills(confirmed)}) == (expected == 'SATISFIED')
    result = eligibility.get_eligibility(profile['profile_id'], 'company_001')
    assert result['status'] == ('ELIGIBLE' if expected == 'SATISFIED' else 'INCOMPLETE')


def test_new_profile_cannot_forge_assessment_evidence_on_confirmation():
    profile, _ = profiles.verify_profile(student(assessed=[evidence()]))
    assert profile['assessment_evidence'] == []
    assert skill_status(resolve_skill_evidence(profile), 'Python') == 'MISSING'


def test_manually_confirmed_skill_matches_without_claiming_an_assessment():
    profile = student(['Python'])
    profile['provenance'] = {'resume': [], 'user': ['skills.other_skills'], 'ml': []}
    profiles._save(profile)
    company = company_store.get_company('company_001')
    assert eligibility.get_eligibility(profile['profile_id'], 'company_001')['status'] == 'ELIGIBLE'
    resolved = resolve_skill_evidence(profile)
    assert 'Python' in recommendations.compute_skill_match(company, set(), evidence=resolved)['required_matched']
    assert not any(g['skill'] == 'Python OR Java OR C++' for g in readiness.get_readiness(profile['profile_id'])['skill_gaps'])
    py = next(e for e in assessments.combined_skill_view(profile['profile_id'])['skills'] if e['skill'] == 'Python')
    assert py['user_entered'] is True and py['resume_detected'] is False
    assert py['profile_confirmed'] is True and py['assessment_verified'] is False
    assert py['assessment_score'] is None and py['assessment_timestamp'] is None


def test_insufficient_preferred_evidence_does_not_block_eligibility():
    profile = student(['Python'], [evidence(20, skill='AWS')])
    company = company_store.get_company('company_001')
    resolved = resolve_skill_evidence(profile)
    result = eligibility.evaluate_company_eligibility(profile, company)
    assert result['status'] == 'ELIGIBLE'
    aws = next(r for r in result['requirements']['unknown'] if r['required_value'] == 'AWS')
    assert aws['evidence_status'] == 'INSUFFICIENT' and aws['mandatory'] is False
    match = recommendations.compute_skill_match(company, set(), evidence=resolved)
    assert 'AWS' in match['preferred_missing'] and match['required_missing'] == []
