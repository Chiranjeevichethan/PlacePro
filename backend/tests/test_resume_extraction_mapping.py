"""Known fictional content through PDF/DOCX, canonical mapping and owned review."""
from copy import deepcopy
from io import BytesIO

import pytest
from docx import Document

from scripts.demo import create_resume, new_workspace
from backend.app.services.resume_parser import extract_text_from_docx, parse_resume, scan_skills
from backend.app.services.resume_service import process_resume_upload
from backend.tests.test_resume import DOCX_MIME, make_docx, make_pdf
from backend.tests.test_profile_ownership import pair, encoded_password, create, snapshot


SAMPLE = """Synthetic Demo Learner
synthetic-resume@example.test
SYNTHETIC DEMONSTRATION DATA - every person and organisation is fictional
EDUCATION
B.Tech Computer Science and Engineering
Synthetic Demonstration College | Graduation: 2027 | CGPA: 8.2
SKILLS
Python, JavaScript, SQL
React.js, NodeJS, Spring Boot
PostgreSQL, SQLite
Docker, AWS
Machine Learning, pandas, NumPy
HTML, CSS, REST API
Git, VS Code
Teamwork, Problem Solving
PROJECTS
Synthetic Library Planner - Fictional book-loan tracking practice application
Technologies: Python, FastAPI, SQLite
- Built a loan tracker using entirely fictional library records.
- Added input validation and search.
Synthetic Study Board
- Built a fictional study planner for practice.
Technologies: React.js, NodeJS, PostgreSQL
INTERNSHIPS
Software Intern at Synthetic Practice Lab | Jun 2025 - Aug 2025
- Built practice endpoints using Python and FastAPI.
EXPERIENCE
Volunteer Developer at Synthetic Community Workshop | Jan 2026 - Mar 2026
- Maintained a fictional website using HTML and CSS.
CERTIFICATIONS
Synthetic Python Practice Certificate | Synthetic Learning Academy | 2025
REFERENCES
No real student information is included.
"""


@pytest.mark.parametrize('kind', ['pdf', 'docx'])
def test_known_sample_preserves_projects_roles_dates_and_all_skill_categories(kind):
    content = make_pdf(SAMPLE.splitlines()) if kind == 'pdf' else make_docx(SAMPLE)
    result = process_resume_upload('fictional.' + kind, content,
                                  'application/pdf' if kind == 'pdf' else DOCX_MIME)
    profile = result['extracted_profile']
    assert profile['name'] == 'Synthetic Demo Learner'
    assert profile['email'] == 'synthetic-resume@example.test'
    assert profile['phone'] is None and profile['location'] is None
    assert profile['education']['cgpa'] == 8.2
    assert profile['education']['graduation_year'] == 2027
    assert [item['project_name'] for item in profile['projects']] == [
        'Synthetic Library Planner', 'Synthetic Study Board']
    assert 'input validation' in profile['projects'][0]['description']
    assert set(profile['projects'][0]['technologies']) == {'Python', 'FastAPI', 'SQLite'}
    assert set(profile['projects'][1]['technologies']) == {'React', 'Node.js', 'PostgreSQL'}
    assert profile['internships'] == [{'role': 'Software Intern', 'company': 'Synthetic Practice Lab',
        'duration': 'Jun 2025 - Aug 2025', 'technologies': ['Python', 'FastAPI']}]
    assert profile['experience'] == [{'role': 'Volunteer Developer', 'company': 'Synthetic Community Workshop',
        'duration': 'Jan 2026 - Mar 2026', 'technologies': ['HTML', 'CSS']}]
    assert all(profile['skills'].values())
    assert profile['skills']['programming_languages'] == ['Python', 'JavaScript', 'SQL']
    assert profile['skills']['frameworks'] == ['React', 'Node.js', 'Spring Boot']
    assert profile['skills']['databases'] == ['PostgreSQL', 'SQLite']


def test_demo_resume_is_fictional_body_metadata_and_complete_known_sample(isolated_storage):
    root = new_workspace(isolated_storage.root)
    path = create_resume(root)
    text = extract_text_from_docx(path.read_bytes())['raw_text']
    assert text.splitlines() == SAMPLE.splitlines()
    document = Document(BytesIO(path.read_bytes()))
    assert document.core_properties.author == 'PlacePro Synthetic Demo'
    assert document.core_properties.last_modified_by == 'PlacePro Synthetic Demo'
    assert document.core_properties.subject == 'Entirely fictional demonstration data'
    assert not document.inline_shapes and not document.tables
    assert document.part.rels
    assert not any(rel.is_external for rel in document.part.rels.values())


def test_old_demo_inline_project_is_not_silently_dropped():
    profile = parse_resume('PROJECTS\nSynthetic Campus Portal — Python and SQL practice project')[0]
    assert profile['projects'] == [{'project_name': 'Synthetic Campus Portal',
        'description': 'Python and SQL practice project', 'technologies': ['Python', 'SQL']}]


def test_docx_tables_stay_between_their_headings_and_do_not_leak_sections():
    document = Document()
    document.add_paragraph('SKILLS')
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = 'Python, SQL'
    table.cell(0, 1).text = 'Git, Teamwork'
    document.add_paragraph('PROJECTS')
    document.add_paragraph('Synthetic Table Reader')
    document.add_paragraph('Technologies: Flask')
    document.add_paragraph('INTERNSHIPS')
    table = document.add_table(rows=1, cols=1)
    table.cell(0, 0).text = 'Software Intern at Synthetic Table Lab\n2025\nBuilt a practice API with FastAPI.'
    document.add_paragraph('REFERENCES')
    document.add_paragraph('No real references')
    output = BytesIO()
    document.save(output)
    extracted = process_resume_upload('table.docx', output.getvalue(), DOCX_MIME)['extracted_profile']
    assert extracted['skills']['programming_languages'] == ['Python', 'SQL']
    assert extracted['skills']['tools'] == ['Git']
    assert extracted['projects'][0]['technologies'] == ['Flask']
    assert extracted['internships'][0]['company'] == 'Synthetic Table Lab'
    assert extracted['internships'][0]['technologies'] == ['FastAPI']


@pytest.mark.parametrize('heading', ['EXPERIENCE', 'WORK EXPERIENCE', 'INTERNSHIP EXPERIENCE',
                                    'EXPERIENCE AND INTERNSHIPS'])
def test_explicit_intern_roles_are_internships_without_duplicate_experience(heading):
    text = heading + '\nSoftware Intern at Synthetic Lab | 2025\nBuilt an API using Python.\n'
    if heading != 'INTERNSHIP EXPERIENCE':
        text += 'Software Developer at Synthetic Workshop | 2026\nMaintained a site using HTML.'
    profile = parse_resume(text)[0]
    assert len(profile['internships']) == 1 and not any(
        'Intern' in entry['role'] for entry in profile['experience'])
    assert profile['internships'][0]['company'] == 'Synthetic Lab'
    if heading != 'INTERNSHIP EXPERIENCE':
        assert profile['experience'][0]['role'] == 'Software Developer'


def test_later_skills_and_projects_are_extracted_without_section_leakage():
    profile = parse_resume('SKILLS\nSQL\nPROJECTS\nSynthetic First - Practice tracker\n'
        'Technologies: Flask\nTECHNICAL SKILLS\nJava, NodeJS\nPROJECTS\n'
        'Synthetic Second - Practice board\nTechnologies: React.js\nREFERENCES\nPython')[0]
    assert profile['skills']['programming_languages'] == ['SQL', 'Java']
    assert profile['skills']['frameworks'] == ['Node.js']
    assert [entry['project_name'] for entry in profile['projects']] == ['Synthetic First', 'Synthetic Second']
    assert profile['projects'][0]['technologies'] == ['Flask']


@pytest.mark.parametrize('text,expected', [
    ('Spring Boot, Spring', ['Spring Boot', 'Spring']),
    ('Spring, Spring Boot', ['Spring', 'Spring Boot']),
    ('React Native', ['React Native']),
    ('React.js, NodeJS, VueJS, ExpressJS, NextJS', ['React', 'Node.js', 'Vue.js', 'Express.js', 'Next.js']),
])
def test_skill_aliases_and_specific_mentions_are_preserved_without_substring_claims(text, expected):
    assert scan_skills(text)['frameworks'] == expected
    assert 'Java' not in scan_skills('JavaScript')['programming_languages']


@pytest.mark.parametrize('text', ['PROJECTS\n2\nprojects_count | 4',
    'PROJECTS\n- Built a tracker in 2025.\n- Improved search by 25 percent.',
    'EXPERIENCE\nBuilt a tutorial with 2024 records.\nTECHNICAL SKILLS\nUnavailableSkillName'])
def test_ambiguous_prose_counts_and_unknown_skills_do_not_fabricate_records(text):
    profile = parse_resume(text)[0]
    assert profile['projects'] == profile['internships'] == profile['experience'] == []
    assert all(not values for values in profile['skills'].values())


@pytest.mark.parametrize('kind', ['pdf', 'docx'])
def test_owned_known_sample_mapping_confirmation_correction_revision_and_denial(pair, isolated_storage, kind):
    _, a, b, ha, hb = pair
    original = create(a, ha)
    before = snapshot(isolated_storage)
    content = make_pdf(SAMPLE.splitlines()) if kind == 'pdf' else make_docx(SAMPLE)
    target = '/api/profile/' + original['profile_id'] + '/resume-preview'
    form = {'revision': str(original['revision'])}
    files = {'file': ('synthetic.' + kind, content, 'application/pdf' if kind == 'pdf' else DOCX_MIME)}
    assert b.post(target, files=files, data=form, headers=hb).status_code == 404
    response = a.post(target, files=files, data=form, headers=ha)
    assert response.status_code == 200, response.text
    preview = response.json()['profile']
    assert snapshot(isolated_storage) == before
    assert preview['personal']['name'] == 'Synthetic Demo Learner'
    assert len(preview['projects']) == 2
    assert len(preview['internships']) == len(preview['experience']) == 1
    assert preview['skills']['frameworks'] == ['React', 'Node.js', 'Spring Boot']
    assert all(value is None for value in preview['ml_inputs'].values())
    corrected = deepcopy(original)
    for key in ['skills', 'projects', 'internships', 'experience']:
        corrected[key] = preview[key]
    corrected['projects'][0]['description'] = 'Student-reviewed fictional project description'
    result = a.post('/api/profile/verify', json=corrected, headers=ha | {'Idempotency-Key': 'known-mapping-confirm'})
    assert result.status_code == 200, result.text
    saved = result.json()['profile']
    assert saved['personal'] == original['personal']
    assert saved['projects'][0]['description'] == corrected['projects'][0]['description']
    assert saved['experience'] == preview['experience']
    assert saved['additional_info']['volunteer_experience'] == original['additional_info']['volunteer_experience']
    retrieved = a.get('/api/profile/' + saved['profile_id'])
    assert retrieved.status_code == 200
    assert retrieved.json()['profile']['experience'] == preview['experience']
    assert retrieved.json()['profile']['additional_info']['volunteer_experience'] == original['additional_info']['volunteer_experience']
    assert saved['revision'] == original['revision'] + 1
    assert b.get('/api/profile/' + saved['profile_id']).status_code == 404
    assert a.post(target, files=files, data=form, headers=ha).status_code == 409
