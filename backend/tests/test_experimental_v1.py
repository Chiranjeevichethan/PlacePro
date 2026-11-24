"""V1 form alignment, real isolated security and model regression contracts."""
import json
from pathlib import Path
import secrets
import sqlite3
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pandas as pd
from pydantic import ValidationError
import pytest

from backend.app.main import create_app
from backend.app.schemas_experimental_v1 import ExperimentalV1Request, ExperimentalV1Response
from backend.app.services import experimental_v1_service as service
from backend.app.services.security_config import SecurityConfig
from backend.tests.test_session_security import BASE, ORIGIN, login, csrf
from experimental.v1.feature_schema import (
    INPUT_COLUMNS, MODEL_FEATURES, IGNORED_INPUTS, MODEL_VERSION, project_training_features,
)

PAYLOAD = {
    "branch": "CSE", "college_tier": "Tier-2", "cgpa": 8.5, "backlogs": 0,
    "coding_skills": 8, "dsa_score": 7, "ml_knowledge": 6, "system_design": 5,
    "projects_count": 2, "certifications": 1, "aptitude_score": 80, "communication_skills": 7,
    "internships": 1, "hackathons": 1, "open_source_contributions": 0, "extracurriculars": 2,
}
PATH = "/api/experimental/v1/predict"


class RedactedHeaders(dict):
    def __repr__(self):
        return "<isolated authentication headers redacted>"


@pytest.fixture
def signed_in(isolated_storage):
    application = create_app(SecurityConfig(origins=(ORIGIN,)))
    password = secrets.token_urlsafe(32)
    application.state.accounts.register("v1-alignment@example.test", password)
    with sqlite3.connect(isolated_storage.auth_db) as connection:
        connection.execute("UPDATE accounts SET status='ACTIVE',email_verified_at='2026-11-23T00:00:00+00:00'")
    with TestClient(application, base_url=BASE) as client:
        assert login(client, email="v1-alignment@example.test", password=password).status_code == 200
        password = None
        yield client, RedactedHeaders(csrf(client))


def test_request_schema_has_exactly_the_16_production_form_inputs():
    assert list(ExperimentalV1Request.model_fields) == INPUT_COLUMNS
    assert ExperimentalV1Request.model_validate(PAYLOAD).model_dump() == PAYLOAD
    assert len(MODEL_FEATURES) == 11 and len(IGNORED_INPUTS) == 5


@pytest.mark.parametrize("field,minimum,maximum", [
    ("cgpa", 4, 10), ("coding_skills", 1, 10), ("dsa_score", 1, 10),
    ("ml_knowledge", 0, 10), ("system_design", 0, 10), ("aptitude_score", 20, 100),
    ("communication_skills", 1, 10),
])
def test_scores_match_form_bounds(field, minimum, maximum):
    for value in (minimum, maximum):
        assert getattr(ExperimentalV1Request(**(PAYLOAD | {field: value})), field) == value
    for value in (minimum - 0.1, maximum + 0.1, None, "", float("inf"), float("nan")):
        with pytest.raises(ValidationError):
            ExperimentalV1Request(**(PAYLOAD | {field: value}))


@pytest.mark.parametrize("field", ["backlogs", "projects_count", "certifications", "internships",
                                  "hackathons", "open_source_contributions", "extracurriculars"])
def test_counts_require_unbounded_nonnegative_integers(field):
    for value in (0, 1000):
        assert getattr(ExperimentalV1Request(**(PAYLOAD | {field: value})), field) == value
    for value in (-1, 1.5, None, ""):
        with pytest.raises(ValidationError):
            ExperimentalV1Request(**(PAYLOAD | {field: value}))


@pytest.mark.parametrize("branch", ["CSE", "ISE", "IT", "ECE", "EE", "ME", "CE", "Chemical"])
def test_all_reference_branch_options_are_accepted(branch):
    assert ExperimentalV1Request(**(PAYLOAD | {"branch": branch})).branch == branch


@pytest.mark.parametrize("field", INPUT_COLUMNS)
def test_missing_values_are_never_defaulted(field):
    missing = {key: value for key, value in PAYLOAD.items() if key != field}
    with pytest.raises(ValidationError):
        service.predict_experimental_v1(missing)


@pytest.mark.parametrize("field", ["salary_package_lpa", "placement_status", "age", "github_repos"])
def test_removed_and_forbidden_features_are_rejected(field):
    with pytest.raises(ValidationError):
        service.predict_experimental_v1(PAYLOAD | {field: 12})


def test_training_projection_preserves_labels_and_uses_only_matching_sources():
    data = pd.DataFrame([{
        "branch": "EEE", "college_tier": "Tier 2", "cgpa": 8.5, "backlogs": 0,
        "coding_skill_score": 80, "communication_skill_score": 70, "aptitude_score": 85,
        "projects_count": 3, "certifications_count": 2, "internships_count": 1,
        "hackathons_participated": 2, "logical_reasoning_score": 99, "github_repos": 12,
        "extracurricular_score": 88, "placement_status": "Placed", "salary_package_lpa": 45,
    }])
    before = data.copy(deep=True)
    projected = project_training_features(data)
    assert list(projected.columns) == MODEL_FEATURES
    assert projected.iloc[0].to_dict() == {
        "branch": "EE", "college_tier": "Tier-2", "cgpa": 8.5, "backlogs": 0,
        "coding_skills": 8, "projects_count": 3, "certifications": 2, "aptitude_score": 85,
        "communication_skills": 7, "internships": 1, "hackathons": 2,
    }
    pd.testing.assert_frame_equal(data, before)
    # Changing labels, salary and related-but-different scores cannot change X.
    changed = data.assign(placement_status="Not Placed", salary_package_lpa=0,
                          logical_reasoning_score=0, github_repos=0, extracurricular_score=0)
    pd.testing.assert_frame_equal(project_training_features(changed), projected)


def test_retrained_artifact_metadata_and_real_prediction_match_the_supported_contract():
    model = service._load_model()
    assert list(model.feature_names_in_) == MODEL_FEATURES
    metadata = json.loads(Path(service.MODEL_PATH).with_name("placepro_v1_production_fields_metadata.json").read_text())
    assert metadata["target"] == "placement_status" and metadata["synthetic_data"] is True
    assert metadata["api_inputs"] == INPUT_COLUMNS and metadata["features"] == MODEL_FEATURES
    assert metadata["ignored_api_inputs"] == IGNORED_INPUTS
    result = service.predict_experimental_v1(PAYLOAD)
    assert ExperimentalV1Response.model_validate(result).experimental is True
    assert result["model_version"] == MODEL_VERSION and "not a validated" in result["synthetic_data_notice"]
    assert service.predict_experimental_v1(PAYLOAD | {"coding_skills": 1})["placement_probability"] != result["placement_probability"]
    ignored = {field: 10 if field in ("dsa_score", "ml_knowledge", "system_design") else 1000 for field in IGNORED_INPUTS}
    assert service.predict_experimental_v1(PAYLOAD | ignored) == result


@pytest.mark.parametrize("branch", ["ISE", "Chemical"])
def test_unseen_branches_are_not_renamed_and_report_the_training_gap(branch):
    result = service.predict_experimental_v1(PAYLOAD | {"branch": branch})
    assert branch + " has no synthetic training rows" in result["synthetic_data_notice"]
    encoder = service._load_model().named_steps["pre"].named_transformers_["cat"]
    encoded = encoder.transform(pd.DataFrame([{"branch": branch, "college_tier": "Tier-2"}])).toarray()[0]
    assert encoded[:len(encoder.categories_[0])].sum() == 0


def test_v1_and_production_inference_remain_separate_with_real_authentication(signed_in):
    client, headers = signed_in
    before = client.post("/api/predict", json=PAYLOAD, headers=headers)
    experimental = client.post(PATH, json=PAYLOAD, headers=headers)
    after = client.post("/api/predict", json=PAYLOAD, headers=headers)
    assert before.status_code == experimental.status_code == after.status_code == 200
    assert before.json() == after.json()
    assert before.json()["model_version"] == "placepro-final-v1"
    assert experimental.json()["model_version"] == MODEL_VERSION
    assert client.get("/api/auth/session", headers={"Origin": ORIGIN}).status_code == 200


def test_v1_denies_invalid_session_csrf_and_origin_before_inference(signed_in, monkeypatch):
    client, headers = signed_in
    def forbidden(*args, **kwargs):
        pytest.fail("Unauthorized request reached inference")
    monkeypatch.setattr(service, "_load_model", forbidden)
    assert client.post(PATH, json=PAYLOAD, headers={"Origin": ORIGIN}).status_code == 403
    assert client.post(PATH, json=PAYLOAD, headers=headers | {"X-CSRF-Token": "invalid"}).status_code == 403
    assert client.post(PATH, json=PAYLOAD, headers=headers | {"Origin": "https://untrusted.example.test"}).status_code == 403
    assert client.post("/api/auth/logout", headers=headers).status_code == 204
    assert client.post(PATH, json=PAYLOAD, headers=headers).status_code == 401


def test_v1_validates_unsupported_fields_and_does_not_fill_missing_scores(signed_in):
    client, headers = signed_in
    for bad in (PAYLOAD | {"dsa_score": 0}, PAYLOAD | {"extracurriculars": 1.5},
                {key: value for key, value in PAYLOAD.items() if key != "coding_skills"}):
        assert client.post(PATH, json=bad, headers=headers).status_code == 422


def test_old_23_feature_artifact_is_never_silently_used(monkeypatch):
    service._load_model.cache_clear()
    incompatible = SimpleNamespace(feature_names_in_=[f"legacy_feature_{i}" for i in range(23)])
    monkeypatch.setattr(service.joblib, "load", lambda path: incompatible)
    try:
        with pytest.raises(ValueError, match="feature schema mismatch"):
            service._load_model()
    finally:
        service._load_model.cache_clear()
