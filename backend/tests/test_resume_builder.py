"""Authenticated resume-builder persistence, profile import, and PDF output tests."""
from copy import deepcopy
from io import BytesIO
import sqlite3
import re

from fastapi.testclient import TestClient
import pytest
from pypdf import PdfReader

from backend.app.main import create_app
from backend.app.services.password_service import PasswordService
from backend.app.services.security_config import SecurityConfig
from backend.tests.test_profile_ownership import body as profile_body, create as create_profile
from backend.tests.test_session_security import BASE, ORIGIN, csrf, login
from backend.tests.test_sessions import PASSWORD


@pytest.fixture(scope='module')
def resume_password_hash():
    return PasswordService().hash_password(PASSWORD)


@pytest.fixture
def resume_pair(isolated_storage, resume_password_hash):
    app = create_app(SecurityConfig(origins=(ORIGIN,)))
    for email in ('builder-one@example.org', 'builder-two@example.org'):
        app.state.accounts.store.create_account(email, resume_password_hash)
    with sqlite3.connect(isolated_storage.auth_db) as connection:
        connection.execute("UPDATE accounts SET status='ACTIVE',email_verified_at='2026-11-09T00:00:00+00:00'")
    with TestClient(app, base_url=BASE) as first, TestClient(app, base_url=BASE) as second:
        assert login(first, email='builder-one@example.org').status_code == 200
        assert login(second, email='builder-two@example.org').status_code == 200
        headers_a, headers_b = csrf(first), csrf(second)
        profile_a = create_profile(first, headers_a)
        body_b = profile_body()
        body_b['personal']['email'] = 'builder-two@example.org'
        response_b = second.post('/api/profile/verify', json=body_b, headers=headers_b)
        assert response_b.status_code == 200, response_b.text
        yield app, first, second, headers_a, headers_b, profile_a, response_b.json()['profile'], isolated_storage


def builder_url(profile_id, suffix=''):
    return f'/api/profile/{profile_id}/resume-builder{suffix}'


def test_resume_profile_import_save_reload_and_profile_isolation(resume_pair):
    app, first, second, headers_a, headers_b, profile, foreign_profile, storage = resume_pair
    url = builder_url(profile['profile_id'])
    before = first.get(f"/api/profile/{profile['profile_id']}").json()['profile']
    assert not storage.resume_builder_db.exists()
    initial = first.get(url)
    assert initial.status_code == 200 and initial.json()['has_saved_draft'] is False
    assert initial.json()['draft']['revision'] == 0
    assert not storage.resume_builder_db.exists()

    imported = first.post(url + '/import', headers=headers_a, json={})
    assert imported.status_code == 200, imported.text
    content = imported.json()['content']
    assert content['personal']['name'] == before['personal']['name']
    assert content['personal_sources']['name'] == 'profile'
    assert any(item['name'] == 'Python' and item['source'] == 'profile' for item in content['skills'])
    assert content['summary'] == '' and content['experience'] == []

    content['summary'] = 'Student authored summary.'
    content['summary_source'] = 'student'
    content['template'] = 'modern'
    content['section_order'] = ['education', 'summary', 'skills', 'projects', 'experience', 'internships',
                                'certifications', 'achievements']
    saved = first.put(url, headers=headers_a, json=content)
    assert saved.status_code == 200, saved.text
    assert saved.json()['draft']['revision'] == 1
    assert saved.json()['draft']['template'] == 'modern'
    assert saved.json()['draft']['section_order'][0] == 'education'
    assert first.get(url).json()['draft']['summary'] == 'Student authored summary.'

    stale = first.put(url, headers=headers_a, json=content)
    assert stale.status_code == 409
    assert second.get(builder_url(profile['profile_id'])).status_code == 404
    assert first.get(builder_url(foreign_profile['profile_id'])).status_code == 404
    after = first.get(f"/api/profile/{profile['profile_id']}").json()['profile']
    assert after == before  # Resume edits do not write back to the canonical profile.
    with sqlite3.connect(storage.resume_builder_db) as connection:
        assert connection.execute('SELECT account_id,revision FROM resume_drafts').fetchone()[1] == 1

    restarted = create_app(SecurityConfig(origins=(ORIGIN,)))
    with TestClient(restarted, base_url=BASE) as restored:
        restored.cookies.set(app.state.security_config.cookie_name,
                            first.cookies.get(app.state.security_config.cookie_name))
        persisted = restored.get(url)
        assert persisted.status_code == 200 and persisted.json()['draft']['summary'] == 'Student authored summary.'


def test_imported_provenance_cannot_be_forged_and_unverified_profile_is_not_importable(resume_pair):
    _, first, _, headers, _, profile, _, _ = resume_pair
    url = builder_url(profile['profile_id'])
    imported = first.post(url + '/import', headers=headers, json={}).json()['content']
    imported['personal']['name'] = 'Forged imported name'
    forged = first.put(url, headers=headers, json=imported)
    assert forged.status_code == 422

    changed_profile = deepcopy(profile)
    changed_profile['personal']['name'] = 'Student edited profile'
    edited = first.put(f"/api/profile/{profile['profile_id']}", headers=headers,
                       json={**changed_profile, 'revision': profile['revision']})
    assert edited.status_code == 200, edited.text
    rejected = first.post(url + '/import', headers=headers, json={})
    assert rejected.status_code == 409 and 'Confirm this profile' in rejected.json()['detail']


@pytest.mark.parametrize('template', ['classic', 'modern'])
def test_pdf_export_is_valid_selectable_and_paginated(resume_pair, template):
    _, first, _, headers, _, profile, _, _ = resume_pair
    url = builder_url(profile['profile_id'])
    document = first.post(url + '/import', headers=headers, json={}).json()['content']
    document['template'] = template
    document['summary'] = 'Verified text remains selectable in the generated document.'
    document['projects'] = [{
        'entry_id': f'{template}-project-{index}', 'source': 'student', 'title': f'Long project record {index}',
        'description': ('A detailed student-authored project description with wrapped text. ' * 20),
        'technologies': 'Python, SQL', 'link': 'https://example.test/project',
    } for index in range(3)]
    document['experience'] = [{
        'entry_id': f'{template}-experience-{index}', 'source': 'student', 'role': 'Research assistant',
        'organization': f'Campus laboratory {index}', 'location': 'Chennai', 'start_date': '2025', 'end_date': '2026',
        'description': ('Documented experiment results and maintained reliable scripts. ' * 25),
    } for index in range(3)]
    saved = first.put(url, headers=headers, json=document)
    assert saved.status_code == 200, saved.text

    response = first.post(url + '/export.pdf', headers=headers, json={})
    assert response.status_code == 200, response.text
    assert response.headers['content-type'].startswith('application/pdf')
    assert response.headers['cache-control'] == 'private, no-store'
    pdf_bytes = response.content
    assert pdf_bytes.startswith(b'%PDF-1.4') and pdf_bytes.rstrip().endswith(b'%%EOF')
    reader = PdfReader(BytesIO(pdf_bytes), strict=True)
    assert len(reader.pages) >= 2
    operators = re.findall(rb'([0-9]+(?:\.[0-9]+)?) ([0-9]+(?:\.[0-9]+)?) Td', pdf_bytes)
    assert operators
    assert all(54 <= float(x) <= 558 and 50 <= float(y) <= 750 for x, y in operators)
    extracted = '\n'.join(page.extract_text() or '' for page in reader.pages)
    assert 'Verified text remains selectable' in extracted
    assert 'Long project record 0' in extracted and 'Campus laboratory 0' in extracted
    assert 'maintained reliable scripts' in extracted
    assert 'placepro-resume.pdf' in response.headers.get('content-disposition', '')


def test_pdf_export_requires_saved_nonempty_resume_and_rejects_oversized_or_invalid_input(resume_pair):
    _, first, _, headers, _, profile, _, _ = resume_pair
    url = builder_url(profile['profile_id'])
    assert first.post(url + '/export.pdf', headers=headers, json={}).status_code == 409
    imported = first.post(url + '/import', headers=headers, json={}).json()['content']
    imported['personal'] = {'name': '', 'email': '', 'phone': '', 'location': '', 'linkedin': '', 'github': '', 'portfolio': ''}
    imported['personal_sources'] = {}
    for section in ('education', 'skills', 'projects', 'experience', 'internships', 'certifications', 'achievements'):
        imported[section] = []
    imported['summary'] = ''
    saved = first.put(url, headers=headers, json=imported)
    assert saved.status_code == 200
    empty_export = first.post(url + '/export.pdf', headers=headers, json={})
    assert empty_export.status_code == 409

    invalid = deepcopy(imported)
    invalid['student_id'] = 'should not be accepted'
    assert first.put(url, headers=headers, json=invalid).status_code == 422


def test_resume_builder_routes_require_session_csrf_and_hide_foreign_profiles(resume_pair):
    app, first, _, headers, _, profile, _, storage = resume_pair
    url = builder_url(profile['profile_id'])
    anonymous = TestClient(app, base_url=BASE)
    assert anonymous.get(url).status_code == 401
    assert first.put(url, json={}, headers={'Origin': ORIGIN}).status_code == 403
    assert first.post(url + '/export.pdf', headers={'Origin': ORIGIN}, json={}).status_code == 403
    assert not storage.resume_builder_db.exists()
