# ============================================================
# PLACEPRO - ISSUE C REGRESSION TESTS
# ============================================================
#
# The demo pipeline previously stored 48 "certifications" for one
# student: the certifications extractor treated every line of the
# section (and content that belonged to later, undetected sections)
# as a certification record, and header lines such as
# "Certifications: 2" became records of their own.
#
# These tests pin the fix: resume extraction must be HONEST.
#   * heading-like lines never become records;
#   * sentences/prose lines never become records;
#   * a stated count in the heading must never fabricate records;
#   * content after an unrecognized heading does NOT bleed into the
#     certifications section;
#   * genuinely listed certifications are still extracted;
#   * projects are never silently dropped (3 clear projects -> 3).
# ============================================================

import pytest

from backend.app.services.resume_parser import (  # noqa: E402
    detect_sections,
    parse_resume,
    _extract_certifications,
)


# ------------------------------------------------------------------
# Plain-line extractor: never a heading, never prose
# ------------------------------------------------------------------


def test_heading_lines_are_not_certifications():
    lines = [
        "Certifications:",
        "AWS Certified Solutions Architect — Amazon",
    ]
    result = _extract_certifications("\n".join(lines))

    assert len(result) == 1
    assert result[0]["name"] == "AWS Certified Solutions Architect"


def test_header_line_with_a_count_does_not_become_or_create_records():
    """'Certifications: 2' is a header, not a record — and must not
    invent two records either."""
    lines = [
        "Certifications: 2",
        "AWS Certified Solutions Architect — Amazon 2023",
    ]
    result = _extract_certifications("\n".join(lines))

    # No fabricated records; the real listed certification stays.
    assert len(result) == 1
    assert result[0]["name"] == "AWS Certified Solutions Architect"


def test_prose_sentence_is_not_a_certification():
    lines = [
        "Certifications:",
        "Certifications: 2",
        "AWS Certified Solutions Architect — Amazon 2023",
        "Open-source contributions: 4 sample contributions, including "
        "documentation fixes and small bug fixes in demo repositories.",
    ]
    result = _extract_certifications("\n".join(lines))

    assert len(result) == 1
    names = [c["name"] for c in result]
    assert all("Open-source" not in n for n in names)


def test_content_after_an_unrecognized_heading_does_not_bleed_in():
    """'HACKATHONS AND OPEN SOURCE' was not in the heading list, so its
    content used to become certifications. The section must stop there."""
    lines = [
        "Certifications:",
        "AWS Certified Solutions Architect — Amazon 2023",
        "HACKATHONS AND OPEN SOURCE",
        "Hackathons: Participated in 2 student hackathons; contributed to a team prototype and final demo.",
    ]
    result = _extract_certifications("\n".join(lines))

    assert len(result) == 1
    assert result[0]["name"] == "AWS Certified Solutions Architect"


def test_no_certifications_section_extracts_nothing():
    result = _extract_certifications("Just some text about programming.")
    assert result == []


def test_extracurricular_section_after_certifications_does_not_bleed_in():
    """'EXTRACURRICULAR ACTIVITIES' followed by activity bullets and a
    count line must not become certification records."""
    lines = [
        "Certifications:",
        "AWS Certified Solutions Architect — Amazon 2023",
        "EXTRACURRICULAR ACTIVITIES",
        "• Volunteer, college technical fest",
        "• Member, coding club",
        "Extracurricular activities: 2",
    ]
    result = _extract_certifications("\n".join(lines))

    names = [c["name"] for c in result]
    assert names == ["AWS Certified Solutions Architect"]
    assert not any(
        any(word in n.lower() for word in ("volunteer", "member",
                                           "extracurricular"))
        for n in names
    )


def test_numbers_in_unrelated_sections_do_not_fabricate_records():
    """Sample field-value tables (field labels, bare numbers like '8.2',
    '3', '2') must never become certification records."""
    lines = [
        "Certifications:",
        "AWS Certified Solutions Architect — Amazon 2023",
        "STUDENT PROFILE FIELDS",
        "branch | CSE (Computer Science and Engineering)",
        "college_tier | Tier-2",
        "cgpa | 8.2",
        "projects_count | 3",
        "2",
        "Testing note: all candidate details are fictional; not used for applications.",
    ]
    result = _extract_certifications("\n".join(lines))

    names = [c["name"] for c in result]
    assert names == ["AWS Certified Solutions Architect"]


def test_multiple_genuine_certifications_are_all_kept():
    lines = [
        "Certifications:",
        "• AWS Certified Solutions Architect — Amazon 2022",
        "• SQL for Data Analysis — Demo Learning Academy",
        "• Python Programming Fundamentals — Demo Learning Academy",
    ]
    result = _extract_certifications("\n".join(lines))

    names = [c["name"] for c in result]
    assert names == [
        "AWS Certified Solutions Architect",
        "SQL for Data Analysis",
        "Python Programming Fundamentals",
    ]


@pytest.mark.parametrize("heading", [
    "CERTIFICATIONS",
    "Certifications",
    "certifications:",
    "# Certifications",
    "• Certifications",
    "1. Certifications",
])
def test_heading_capitalization_and_formatting_variants(heading):
    """Section-start handling goes through detect_sections (headings may be
    bulleted/numbered); the extractor itself receives only section text."""
    resume = (
        "ARJUN SHARMA\n"
        "arjun@example.com | +91 98765 43210\n"
        "\n"
        f"{heading}\n"
        "AWS Certified Solutions Architect — Amazon 2022\n"
    )
    profile, _, _ = parse_resume(resume)

    assert [c["name"] for c in profile["certifications"]] == (
        ["AWS Certified Solutions Architect"]
    )


def test_stray_pdf_bullet_glyph_is_removed_from_names():
    """PDF extraction sometimes leaves a control-character bullet before a
    record; it must not end up inside the certification name."""
    lines = ["Certifications:", "\x7f SQL for Data Analysis — Academy"]
    result = _extract_certifications("\n".join(lines))

    assert [c["name"] for c in result] == ["SQL for Data Analysis"]


def test_hackathon_lines_reach_achievements_not_certifications():
    """A HACKATHONS AND OPEN SOURCE section is recognized: its explicit
    hackathon lines flow into achievements, never into certifications."""
    # 'HACKATHONS AND OPEN SOURCE' is a recognized heading in the parser.
    profile, _, _ = parse_resume(RESUME_WITH_CLEAR_SECTIONS)

    assert len(profile["certifications"]) == 1
    assert profile["achievements"]["hackathons"], (
        "explicit hackathon line should be captured in achievements"
    )


# ------------------------------------------------------------------
# Full-resume parse: counts stay defensible end-to-end
# ------------------------------------------------------------------

RESUME_WITH_CLEAR_SECTIONS = """ARJUN SHARMA
Bangalore | arjun@example.com | +91 98765 43210

EDUCATION
B.Tech Computer Science and Engineering, 2021 - 2025
XYZ College, Bangalore
CGPA: 8.4

SKILLS
Python, Java, SQL, AWS, Docker

PROJECTS
Weather App
Technologies: Python, Flask
A web dashboard for live weather analytics.

Chat Bot
Technologies: NLTK
A rule-based chat assistant for FAQs.

Portfolio Site
Technologies: HTML, CSS
A personal portfolio page.

CERTIFICATIONS
AWS Certified Solutions Architect — Amazon 2023

HACKATHONS AND OPEN SOURCE
Participated in 2 student hackathons.
Open-source contributions in demo repositories.
"""


def test_full_resume_yields_the_listed_certification_only():
    profile, confidence, needs_verification = parse_resume(RESUME_WITH_CLEAR_SECTIONS)

    certs = profile["certifications"]
    assert len(certs) == 1
    assert certs[0]["name"].strip() == "AWS Certified Solutions Architect"

    # The three clearly separated projects are all found.
    names = [p["project_name"] for p in profile["projects"]]
    assert names == ["Weather App", "Chat Bot", "Portfolio Site"]


def test_full_resume_with_no_certifications_lists_none():
    resume = RESUME_WITH_CLEAR_SECTIONS.replace(
        "AWS Certified Solutions Architect — Amazon 2023\n",
        "",
    )

    profile, _, _ = parse_resume(resume)

    assert profile["certifications"] == []


def test_three_projects_count_is_stable_across_pages():
    """The count songs every page reads derive from the structured list;
    three clear projects must yield exactly three."""
    profile, _, _ = parse_resume(RESUME_WITH_CLEAR_SECTIONS)
    assert len(profile["projects"]) == 3
    assert len(profile["certifications"]) == 1


def test_certifications_section_text_via_detect_sections_is_bounded():
    """A recognized later heading still bounds the certifications span."""
    extended = RESUME_WITH_CLEAR_SECTIONS.replace(
        "HACKATHONS AND OPEN SOURCE", "ACHIEVEMENTS"
    )
    lines = extended.splitlines()
    sections = detect_sections(lines)

    assert "certifications" in sections
    start, end = sections["certifications"]
    section_text = "\n".join(lines[start + 1 : end])

    assert "Hackathon" not in section_text
    assert "Open-source" not in section_text
