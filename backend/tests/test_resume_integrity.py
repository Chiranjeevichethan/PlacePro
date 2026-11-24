"""Real text/PDF regressions for section boundaries and honest extraction."""
from pathlib import Path

import pytest

from backend.app.services.resume_parser import _extract_certifications, parse_resume
from backend.app.services.resume_intelligence import analyze_resume
from backend.app.services.resume_service import process_resume_upload
from backend.tests.test_resume import DOCX_MIME, make_docx, make_pdf

FIXTURE = Path(__file__).parent / 'fixtures' / 'resume_integrity_fictional.txt'


@pytest.mark.parametrize('title', [
    'AWS CERTIFIED CLOUD PRACTITIONER', 'AWS Certified Cloud Practitioner.',
    'Microsoft Certified: Azure Fundamentals.', 'SQL for Data Analysis.',
    'Python Programming Fundamentals;',
])
def test_certification_titles_keep_capitals_and_punctuation(title):
    profile, _, _ = parse_resume(f'CERTIFICATIONS\n{title}\nIssuer: Example Academy\nIssued: May 2024\nPROJECTS\n')
    assert profile['certifications'] == [{'name': title, 'issuer': 'Example Academy', 'year': 2024}]


@pytest.mark.parametrize('metadata', [
    'Certificate ID: ABC123', 'Credential ID: 20249876', 'Certification Number: 12345',
    'Credential URL: https://credentials.example.com/2025/123', 'https://example.com/credential',
    'www.example.com/123', 'Status: Completed', 'Expires: 2028', 'Valid until: 2028',
    'Expiry date: 2028-05-01', 'Issuer: Example Academy', '2024', 'May 2024',
])
def test_metadata_never_becomes_a_certification(metadata):
    result = _extract_certifications('AWS Certified Cloud Practitioner\n' + metadata)
    assert len(result) == 1
    assert result[0]['name'] == 'AWS Certified Cloud Practitioner'
    if metadata.startswith(('Expires', 'Valid', 'Expiry', 'Credential')):
        assert result[0]['year'] is None


def test_inline_metadata_and_separate_issue_date_preserve_reliable_values():
    result = _extract_certifications(
        'AWS Certified Cloud Practitioner | Issuer: Amazon | Credential ID: ABC123 | Issued: 2024-05-01\n'
        'Python Fundamentals.\nIssued by: Example Academy\nDate issued: 10/06/2023\n'
        'SQL for Data Analysis\n')
    assert result == [
        {'name': 'AWS Certified Cloud Practitioner', 'issuer': 'Amazon', 'year': 2024},
        {'name': 'Python Fundamentals.', 'issuer': 'Example Academy', 'year': 2023},
        {'name': 'SQL for Data Analysis', 'issuer': None, 'year': None},
    ]


def test_duplicate_certifications_coalesce_but_conflicting_metadata_remains():
    result = _extract_certifications('Python Fundamentals.\nIssuer: Academy\nIssued: 2023\n'
        'PYTHON FUNDAMENTALS | Academy | 2023\nPython Fundamentals | Academy | 2024\n')
    assert len(result) == 2
    assert [entry['year'] for entry in result] == [2023, 2024]


@pytest.mark.parametrize('text', [
    'Completed a Python course to learn programming.', 'Coursework: Python, SQL.',
    'Participated in a hackathon.', '8.2', '200', 'projects_count | 3',
])
def test_course_prose_and_unrelated_numbers_are_not_certifications(text):
    assert _extract_certifications(text) == []


@pytest.mark.parametrize('format_', ['text', 'pdf', 'docx'])
def test_realistic_fixture_survives_text_and_document_extraction(format_):
    text = FIXTURE.read_text(encoding='utf-8')
    if format_ == 'text':
        profile = parse_resume(text)[0]
    else:
        content = make_pdf(text.splitlines()) if format_ == 'pdf' else make_docx(text)
        result = process_resume_upload(f'resume.{format_}', content, 'application/pdf' if format_ == 'pdf' else DOCX_MIME)
        assert result['success'] is True
        profile = result['extracted_profile']
    assert len(profile['certifications']) == 2
    assert profile['certifications'][0] == {'name': 'AWS CERTIFIED CLOUD PRACTITIONER.',
        'issuer': 'Amazon Web Services', 'year': 2024}
    assert profile['education']['graduation_year'] == 2025
    assert len(profile['projects']) == len(profile['internships']) == 1
    assert profile['projects'][0]['project_name'] == 'Weather Dashboard'
    assert profile['skills']['programming_languages'] == ['Python', 'SQL']
    assert profile['achievements']['hackathons'] == ['CodeFest 2024 - Finalist, weather prototype']
    assert len(profile['achievements']['open_source_contributions']) == 1
    assert profile['achievements']['extracurriculars'] == ['Volunteer, college technical festival']


@pytest.mark.parametrize('heading', ['HACKATHONS', 'OPEN-SOURCE CONTRIBUTIONS',
    'EXTRACURRICULAR ACTIVITIES', 'REFERENCES', 'STUDENT PROFILE FIELDS', 'RELEVANT COURSEWORK'])
def test_adjacent_headings_bound_certifications_and_skills(heading):
    profile = parse_resume('SKILLS\nSQL\nCERTIFICATIONS\nAWS Certified Cloud Practitioner\n'
        + heading + '\nPython\nprojects_count | 2024\n')[0]
    assert len(profile['certifications']) == 1
    assert profile['skills']['programming_languages'] == ['SQL']


def test_missing_headings_do_not_promote_technology_prose_or_unrelated_years():
    profile = parse_resume('Ananya Rao\nananya@example.com\n'
        'I hope to study Python next year.\nWinner of a competition in 2028\n')[0]
    assert not any(profile['skills'].values())
    assert profile['education']['graduation_year'] is None
    assert profile['certifications'] == profile['projects'] == profile['internships'] == []


def test_explicit_inline_skill_and_education_evidence_without_headings():
    profile = parse_resume('Ananya Rao\nSkills: Python, SQL\n'
        'B.Tech Computer Science, Example College, 2021-2025\nCGPA: 8.4/10\n')[0]
    assert profile['skills']['programming_languages'] == ['Python', 'SQL']
    assert profile['education']['graduation_year'] == 2025


def test_repeated_heading_keeps_later_skills_without_leaking_sections():
    profile = parse_resume('SKILLS\nSQL\nPROJECTS\nWeather App\nTechnologies: Flask\n'
        'SKILLS\nJava\nCERTIFICATIONS\nAWS Certified Cloud Practitioner\n')[0]
    assert profile['skills']['programming_languages'] == ['SQL', 'Java']
    assert profile['projects'][0]['technologies'] == ['Flask']


def test_undated_internship_and_body_year_are_not_invented_attempts():
    profile = parse_resume('INTERNSHIPS\nSoftware Intern at Example Labs\n'
        '- Built a report with 2024 observations using SQL.\nSKILLS\nPython\n')[0]
    assert profile['internships'] == [{'role': 'Software Intern', 'company': 'Example Labs',
        'duration': None, 'technologies': ['SQL']}]


def test_project_bullets_and_numeric_lines_do_not_inflate_counts():
    profile = parse_resume('PROJECTS\n- Weather App - Live weather dashboard\n'
        '- Built 12 API endpoints\n- Improved latency by 25 percent\n'
        'Technologies: Flask\n2\nprojects_count | 2024\n')[0]
    assert len(profile['projects']) == 1
    assert profile['projects'][0]['technologies'] == ['Flask']


def test_analysis_uses_parser_headings_and_retains_text_and_counts():
    analysis = analyze_resume('resume.pdf', make_pdf(FIXTURE.read_text().splitlines()), 'application/pdf')
    assert analysis['diagnostics']['detected_sections'] == ['education', 'skills', 'projects',
        'internships', 'certifications', 'hackathons', 'open_source', 'extracurriculars']
    assert analysis['extraction_summary']['counts']['certifications'] == 2
    assert any(item['source'] == 'resume' and item['field'] == 'certifications' for item in analysis['provenance'])
    assert all(item['status'] == 'REQUIRES_MANUAL_INPUT' for item in
        analysis['completeness']['feature_availability'] if item['field'] in ['open_source_contributions', 'extracurriculars'])


def test_diagnostics_do_not_invent_sections_from_prose_keywords():
    analysis = analyze_resume('resume.docx', make_docx('Ananya Rao\n'
        'I wish to learn skills for future projects and internships.'), DOCX_MIME)
    assert analysis['diagnostics']['detected_sections'] == []


@pytest.mark.parametrize('title', [
    'AWS Certified Solutions Architect - Associate',
    'AWS Certified Solutions Architect – Associate',
    'Cloud, Security and Networking Certificate.',
])
def test_separators_inside_genuine_title_do_not_fabricate_an_issuer(title):
    assert _extract_certifications(title) == [{'name': title, 'issuer': None, 'year': None}]


@pytest.mark.parametrize('metadata', [
    'Issued: May 10, 2024', 'Issued: 10 May 2024', 'Issue date: May 2024',
    'Issued May 2024', 'Date issued: 2024/05/10',
])
def test_common_certification_issue_dates(metadata):
    assert _extract_certifications('AWS Certified Cloud Practitioner\n' + metadata) == [
        {'name': 'AWS Certified Cloud Practitioner', 'issuer': None, 'year': 2024}]


@pytest.mark.parametrize('metadata', [
    'Certificate ID ABC123', 'Credential URL https://example.com/ABC123',
    'Issued: February 31, 2024', 'Expires May 2028',
    'Status Completed', 'https://example.com/credential.',
])
def test_additional_metadata_and_invalid_dates_do_not_create_records(metadata):
    assert _extract_certifications('AWS Certified Cloud Practitioner\n' + metadata) == [
        {'name': 'AWS Certified Cloud Practitioner', 'issuer': None, 'year': None}]


def test_separate_known_issuer_is_metadata_not_another_certification():
    assert _extract_certifications('AWS Certified Cloud Practitioner\nAmazon Web Services\n2024\n'
        'Microsoft Certified: Azure Fundamentals\nMicrosoft\n2023\n') == [
        {'name': 'AWS Certified Cloud Practitioner', 'issuer': 'Amazon Web Services', 'year': 2024},
        {'name': 'Microsoft Certified: Azure Fundamentals', 'issuer': 'Microsoft', 'year': 2023}]


def test_internship_date_range_in_description_is_not_a_duration():
    result = parse_resume('INTERNSHIPS\nSoftware Intern at Example Labs\n'
        '- Compared data from 2021-2024 using SQL.\nSKILLS\nPython\n')[0]
    assert len(result['internships']) == 1
    assert result['internships'][0]['duration'] is None


@pytest.mark.parametrize('line', [
    'Issuer: Amazon | Issue date: May 2024',
    'Credential ID: ABC123 | Issuer: Amazon | Issued: 2024-05-10',
])
def test_combined_metadata_line_keeps_issuer_and_issue_year(line):
    assert _extract_certifications('AWS Certified Cloud Practitioner\n' + line) == [
        {'name': 'AWS Certified Cloud Practitioner', 'issuer': 'Amazon', 'year': 2024}]


def test_unrelated_year_in_education_does_not_replace_degree_end_year():
    result = parse_resume('EDUCATION\nB.Tech Computer Science, Example College, 2021-2025\n'
        'Scholarship valid until 2028\nCGPA: 8.4/10\n')[0]
    assert result['education']['graduation_year'] == 2025


def test_experience_description_with_role_word_does_not_create_another_internship():
    result = parse_resume('INTERNSHIPS\nSoftware Intern at Example Labs, 2024\n'
        '- Collaborated with the Software Engineer on SQL reports\n')[0]
    assert len(result['internships']) == 1
    assert result['internships'][0]['company'] == 'Example Labs'
