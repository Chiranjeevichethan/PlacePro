import math

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.salary_prediction_service import (
    _convert_extracurricular_score,
    _convert_skill_score,
    normalize_branch,
    normalize_college_tier,
    predict_salary,
)

client = TestClient(app)


VALID_PAYLOAD = {
    "branch": "CSE",
    "college_tier": "Tier-2",
    "cgpa": 8.5,
    "backlogs": 0,
    "coding_skills": 8.0,
    "dsa_score": 8.0,
    "aptitude_score": 80.0,
    "communication_skills": 8.0,
    "ml_knowledge": 7.0,
    "system_design": 7.0,
    "internships": 2,
    "projects_count": 3,
    "certifications": 2,
    "hackathons": 2,
    "open_source_contributions": 1,
    "extracurriculars": 2,
}


def test_salary_prediction_success():
    response = client.post("/api/salary-predict", json=VALID_PAYLOAD)

    assert response.status_code == 200

    body = response.json()

    assert "predicted_salary_lpa" in body
    assert "model_version" in body

    assert isinstance(body["predicted_salary_lpa"], float)
    assert body["predicted_salary_lpa"] > 0
    assert body["model_version"] == "placepro-salary-v2"


def test_salary_prediction_uses_frontend_compatible_16_field_payload():
    response = client.post("/api/salary-predict", json=VALID_PAYLOAD)

    assert response.status_code == 200


def test_salary_prediction_rejects_invalid_cgpa():
    payload = VALID_PAYLOAD.copy()
    payload["cgpa"] = 11.0

    response = client.post("/api/salary-predict", json=payload)

    assert response.status_code == 422


def test_salary_prediction_rejects_missing_required_field():
    payload = VALID_PAYLOAD.copy()
    del payload["cgpa"]

    response = client.post("/api/salary-predict", json=payload)

    assert response.status_code == 422


# ------------------------------------------------------------------
# Category normalization (salary dataset uses "Tier 1" / "CSE" etc.)
# ------------------------------------------------------------------


@pytest.mark.parametrize(
    "spelling,expected",
    [
        ("Tier 1", "Tier 1"),
        ("Tier-1", "Tier 1"),
        (1, "Tier 1"),
        ("Tier 2", "Tier 2"),
        ("Tier-2", "Tier 2"),
        ("Tier 3", "Tier 3"),
        ("Tier-3", "Tier 3"),
        (3, "Tier 3"),
    ],
)
def test_normalize_college_tier(spelling, expected):
    assert normalize_college_tier(spelling) == expected


@pytest.mark.parametrize(
    "spelling,expected",
    [
        ("Computer Science & Engineering", "CSE"),
        ("Mechanical Engineering", "Mechanical"),
        ("ME", "Mechanical"),
        ("EE", "EEE"),
        ("CE", "Civil"),
        ("CSE", "CSE"),
    ],
)
def test_normalize_branch(spelling, expected):
    assert normalize_branch(spelling) == expected


@pytest.mark.parametrize(
    "tier_spelling",
    ["Tier 2", "Tier-2", "2"],
)
def test_api_tier_spellings_are_equivalent(tier_spelling):
    """All accepted tier spellings must hit the same one-hot category."""

    baseline = client.post("/api/salary-predict", json=VALID_PAYLOAD)

    payload = VALID_PAYLOAD.copy()
    payload["college_tier"] = tier_spelling
    response = client.post("/api/salary-predict", json=payload)

    assert baseline.status_code == 200
    assert response.status_code == 200
    assert (
        response.json()["predicted_salary_lpa"]
        == pytest.approx(baseline.json()["predicted_salary_lpa"])
    )


# ------------------------------------------------------------------
# Input scale conversion (frontend 0-10 -> dataset 20-100)
# ------------------------------------------------------------------


def test_convert_skill_score_scales_and_clamps():
    assert _convert_skill_score(8.0) == 80.0
    assert _convert_skill_score(10.0) == 100.0
    # Dataset range starts at 20; low inputs clamp to that floor.
    assert _convert_skill_score(0.0) == 20.0
    assert _convert_skill_score(1.5) == 20.0
    assert _convert_skill_score(12.0) == 100.0


def test_convert_extracurricular_score_scales_count_to_0_100():
    assert _convert_extracurricular_score(0) == 0.0
    assert _convert_extracurricular_score(3) == 100.0
    assert _convert_extracurricular_score(2) == pytest.approx(66.67, abs=0.01)


# ------------------------------------------------------------------
# Prediction sanity across representative profiles
# ------------------------------------------------------------------


def _profile(**overrides):
    profile = {
        "branch": "CSE",
        "college_tier": "Tier-2",
        "cgpa": 8.0,
        "backlogs": 0,
        "coding_skills": 7.0,
        "dsa_score": 7.0,
        "aptitude_score": 70.0,
        "communication_skills": 7.0,
        "ml_knowledge": 6.0,
        "system_design": 6.0,
        "internships": 1,
        "projects_count": 3,
        "certifications": 2,
        "hackathons": 1,
        "open_source_contributions": 1,
        "extracurriculars": 2,
    }
    profile.update(overrides)
    return profile


@pytest.mark.parametrize(
    "profile",
    [
        _profile(),
        _profile(cgpa=9.5, coding_skills=9.5, internships=4, backlogs=0),
        _profile(cgpa=5.0, coding_skills=2.0, backlogs=3, internships=0),
        _profile(college_tier="Tier 1", branch="IT"),
        _profile(college_tier="Tier 3", branch="Civil"),
    ],
)
def test_predictions_are_finite_and_positive(profile):
    result = predict_salary(profile)

    value = result["predicted_salary_lpa"]
    assert math.isfinite(value)
    assert value > 0
    assert result["model_version"] == "placepro-salary-v2"


def test_stronger_numeric_profile_predicts_higher_than_weak_profile():
    weak = predict_salary(
        _profile(cgpa=5.0, coding_skills=2.0, internships=0, backlogs=3)
    )
    strong = predict_salary(
        _profile(cgpa=9.5, coding_skills=9.5, internships=4, backlogs=0)
    )

    assert (
        strong["predicted_salary_lpa"] > weak["predicted_salary_lpa"]
    )


def test_higher_coding_score_predicts_higher_salary():
    """coding_skill_score has a positive learned Ridge coefficient."""

    low = predict_salary(_profile(coding_skills=3.0))
    high = predict_salary(_profile(coding_skills=9.0))

    assert high["predicted_salary_lpa"] > low["predicted_salary_lpa"]


def test_unknown_branch_passes_through_without_crashing():
    """handle_unknown="ignore" must keep odd branch strings working."""

    result = predict_salary(_profile(branch="Chemical Engineering"))

    assert math.isfinite(result["predicted_salary_lpa"])
    assert result["predicted_salary_lpa"] > 0
