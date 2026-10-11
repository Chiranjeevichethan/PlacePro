import pytest
from fastapi.testclient import TestClient

from backend.app.main import app

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