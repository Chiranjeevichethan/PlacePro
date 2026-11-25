"""Historical Phase 29.5 domain characterization and existing integrity.

Two clients exercise the explicit test-only domain harness with synthetic records.
Historical anonymous expectations characterize underlying unowned business logic,
not current production exposure. Production denial is covered by test_session_security.
Inference is explicitly stubbed: these tests make no model-compatibility claim.
"""
import copy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import pytest
from docx import Document
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from backend.tests.domain_app import app
from backend.app.services import assessment_service as assessments
from backend.app.services import profile_service as profiles
from backend.app.services import recommendation_service as recommendations
from backend.app.services.question_bank import get_questions


def synthetic(profile_id=None):
    return {
        "profile_id": profile_id,
        "personal": {"name": "Synthetic Audit Student", "email": "audit@example.test"},
        "education": {"degree": "B.Tech", "branch": "CSE", "cgpa": 8.0,
                      "college": "Synthetic College", "graduation_year": 2027},
        "skills": {"programming_languages": ["Python"]},
        "projects": [{"project_name": "Synthetic Project"}],
        "internships": [], "certifications": [], "achievements": {"hackathons": []},
        "ml_inputs": {"college_tier": "Tier-2", "backlogs": 0, "coding_skills": 7,
                      "dsa_score": 7, "aptitude_score": 80, "communication_skills": 7,
                      "ml_knowledge": 5, "system_design": 5,
                      "open_source_contributions": 0, "extracurriculars": 0},
    }


def confirm(client, body, **options):
    response = client.post("/api/profile/verify", json=body, **options)
    assert response.status_code == 200, response.text
    return response.json()["profile"]


def resume_file():
    document = Document()
    for line in ("Synthetic Resume Student", "resume-audit@example.test", "EDUCATION",
                 "B.Tech in Computer Science", "CGPA: 8.0", "SKILLS", "Python",
                 "CERTIFICATIONS", "AWS CERTIFIED CLOUD PRACTITIONER."):
        document.add_paragraph(line)
    stream = BytesIO()
    document.save(stream)
    return ("synthetic.docx", stream.getvalue(),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document")


@pytest.fixture
def clients(monkeypatch, isolated_storage):
    assert Path(profiles.PROFILES_DIR) == isolated_storage.profiles
    assert Path(assessments.ASSESSMENTS_DIR) == isolated_storage.assessments
    monkeypatch.setattr(assessments, "_utc_now", lambda: datetime(2026, 11, 8, tzinfo=timezone.utc))
    result = {"placement_probability": 0.75, "prediction": "PLACED", "confidence": 0.75,
              "model_version": "ownership-audit-stub"}
    monkeypatch.setattr(profiles, "predict_with_model", lambda inputs: dict(result))
    monkeypatch.setattr(recommendations, "predict_with_model", lambda inputs: dict(result))
    with TestClient(app) as creator, TestClient(app) as visitor:
        assert not creator.cookies and not visitor.cookies
        assert "authorization" not in visitor.headers
        yield creator, visitor


def start(client, profile_id, skill="Python", **options):
    response = client.post("/api/assessment/start", json={"profile_id": profile_id,
                           "skill": skill, "num_questions": 5}, **options)
    assert response.status_code == 200, response.text
    return response.json()


def answers_for(session):
    # Test-only oracle from the existing bank; public responses must omit it.
    bank = {entry["id"]: entry["correct_answer"] for entry in get_questions(session["skill"])}
    return {entry["question_id"]: bank[entry["question_id"]] for entry in session["questions"]}


def submit(client, session, profile_id):
    return client.post("/api/assessment/" + session["assessment_id"] + "/submit",
                       json={"profile_id": profile_id, "answers": answers_for(session)})


@pytest.fixture
def history_profile(clients):
    creator, _ = clients
    profile = confirm(creator, synthetic("audit-history"))
    session = start(creator, profile["profile_id"])
    assert submit(creator, session, profile["profile_id"]).status_code == 200
    response = creator.post("/api/profile/" + profile["profile_id"] + "/predict",
                            headers={"Idempotency-Key": "synthetic-history-key"})
    assert response.status_code == 200 and response.json()["ready_for_prediction"]
    return profiles._load(profile["profile_id"])


def test_current_endpoint_inventory_has_no_authenticated_dependency_or_security_scheme():
    schema = app.openapi()
    operations = [(path, method, entry) for path, methods in schema["paths"].items()
                  for method, entry in methods.items() if method in {"get", "put", "post", "delete", "patch"}]
    # The original 23 student/company/health operations still lack ownership.
    # Auth/gate is deliberately absent from this isolated domain harness.
    legacy = [(path, method, entry) for path, method, entry in operations
              if not path.startswith("/api/auth/")]
    assert len({path for path, _, _ in legacy}) == 22 and len(legacy) == 23
    assert not any(path.startswith('/api/auth/') for path, _, _ in operations)
    assert not schema.get("components", {}).get("securitySchemes")
    assert all(not entry.get("security") for _, _, entry in operations)
    assert all(not route.dependant.dependencies for route in app.routes if isinstance(route, APIRoute))


@pytest.mark.parametrize("suffix", ["", "/assessments", "/performance", "/skills", "/readiness",
                                    "/placement-summary", "/eligibility", "/eligibility/company_001",
                                    "/recommendations"])
def test_current_anonymous_client_can_read_another_synthetic_profile(clients, history_profile, suffix):
    _, visitor = clients
    response = visitor.get("/api/profile/" + history_profile["profile_id"] + suffix)
    assert response.status_code == 200
    data = response.json()
    if not suffix:
        assert data["profile"]["personal"]["email"] == "audit@example.test"
        assert len(data["profile"]["prediction_history"]) == 1
        assert len(data["profile"]["assessment_evidence"]) == 1
    elif suffix == "/performance":
        assert len(data["prediction_history"]) == len(data["assessment_history"]) == 1
        assert data["prediction_history"][0]["source_inputs"]
    elif suffix == "/assessments":
        assert len(data["assessments"]) == 1


def test_current_anonymous_update_and_confirmation_replace_claims_without_owner_proof(clients):
    creator, visitor = clients
    original = confirm(creator, synthetic("audit-modify"))
    edited = copy.deepcopy(original)
    edited["personal"]["email"] = "changed-by-anonymous@example.test"
    response = visitor.put("/api/profile/audit-modify", json=edited)
    assert response.status_code == 200
    pending = response.json()["profile"]
    assert pending["verified"] is False and pending["revision"] == original["revision"] + 1
    confirmed = confirm(visitor, pending)
    assert confirmed["verified"] is True
    assert confirmed["personal"]["email"] == edited["personal"]["email"]
    assert "user_id" not in confirmed and "owner_id" not in confirmed


def test_current_confirmation_accepts_a_client_chosen_new_id_and_claimed_email(clients):
    creator, visitor = clients
    first = confirm(creator, synthetic("audit-chosen-first"))
    second = confirm(visitor, synthetic("audit-chosen-second"))
    assert first["profile_id"] != second["profile_id"]
    assert first["personal"]["email"] == second["personal"]["email"]
    assert first["verified"] and second["verified"]
    assert not creator.cookies and not visitor.cookies


def test_current_session_get_discloses_linked_profile_and_matching_ids_allow_foreign_submit(clients):
    creator, visitor = clients
    profile = confirm(creator, synthetic("audit-session"))
    session = start(creator, profile["profile_id"])
    public = visitor.get("/api/assessment/" + session["assessment_id"])
    assert public.status_code == 200
    assert public.json()["profile_id"] == profile["profile_id"]
    result = submit(visitor, session, public.json()["profile_id"])
    assert result.status_code == 200 and result.json()["skill_score"] == 100
    assert len(profiles._load(profile["profile_id"])["assessment_evidence"]) == 1
    assert visitor.get("/api/assessment/" + session["assessment_id"]).json()["result"] == result.json()


def test_mismatching_profile_id_still_rejects_submission_and_preserves_both_profiles(clients):
    creator, visitor = clients
    first = confirm(creator, synthetic("audit-session-a"))
    second = confirm(creator, synthetic("audit-session-b"))
    session = start(creator, first["profile_id"])
    before = profiles._load(first["profile_id"])
    assert submit(visitor, session, second["profile_id"]).status_code == 403
    assert profiles._load(first["profile_id"]) == before
    assert profiles._load(second["profile_id"]) == second
    assert assessments._load_session(session["assessment_id"])["status"] == "IN_PROGRESS"


def test_current_anonymous_client_can_reserve_another_profiles_remaining_quota(clients):
    creator, visitor = clients
    profile = confirm(creator, synthetic("audit-quota"))
    sessions = [start(visitor, profile["profile_id"], headers={"Idempotency-Key": "ignored-start-key"})
                for _ in range(3)]
    assert len({session["assessment_id"] for session in sessions}) == 3
    assert [session["attempt"] for session in sessions] == [1, 2, 3]
    blocked = creator.post("/api/assessment/start", json={"profile_id": profile["profile_id"], "skill": "Python"})
    assert blocked.status_code == 429 and int(blocked.headers["Retry-After"]) > 0
    assert profiles._load(profile["profile_id"])["assessment_evidence"] == []


def test_current_anonymous_prediction_key_replay_returns_foreign_result_but_deduplicates(clients):
    creator, visitor = clients
    profile = confirm(creator, synthetic("audit-predict"))
    path = "/api/profile/" + profile["profile_id"] + "/predict"
    first = creator.post(path, headers={"Idempotency-Key": "known-request"})
    replay = visitor.post(path, headers={"Idempotency-Key": "known-request"})
    assert first.status_code == replay.status_code == 200
    assert replay.json() == first.json()
    assert len(profiles._load(profile["profile_id"])["prediction_history"]) == 1
    added = visitor.post(path, headers={"Idempotency-Key": "another-request"})
    assert added.status_code == 200
    assert len(profiles._load(profile["profile_id"])["prediction_history"]) == 2


def test_same_prediction_key_is_separate_per_profile_and_rejects_changed_revision(clients):
    creator, _ = clients
    first = confirm(creator, synthetic("audit-key-a"))
    second = confirm(creator, synthetic("audit-key-b"))
    for profile in (first, second):
        response = creator.post("/api/profile/" + profile["profile_id"] + "/predict",
                                headers={"Idempotency-Key": "shared-synthetic-key"})
        assert response.status_code == 200 and response.json()["profile_id"] == profile["profile_id"]
    changed = copy.deepcopy(first)
    changed["education"]["cgpa"] = 7.0
    saved = creator.put("/api/profile/audit-key-a", json=changed).json()["profile"]
    confirm(creator, saved)
    assert creator.post("/api/profile/audit-key-a/predict",
                        headers={"Idempotency-Key": "shared-synthetic-key"}).status_code == 409
    assert len(profiles._load(second["profile_id"])["prediction_history"]) == 1


def test_concurrent_prediction_key_retries_create_one_record(clients):
    creator, _ = clients
    confirm(creator, synthetic("audit-concurrent"))
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: creator.post("/api/profile/audit-concurrent/predict",
                            headers={"Idempotency-Key": "concurrent-key"}), range(8)))
    assert all(response.status_code == 200 for response in results)
    assert all(response.json() == results[0].json() for response in results)
    assert len(profiles._load("audit-concurrent")["prediction_history"]) == 1


def test_completed_submission_retry_returns_conflict_and_one_unchanged_evidence_record(clients):
    creator, _ = clients
    profile = confirm(creator, synthetic("audit-submit-retry"))
    session = start(creator, profile["profile_id"])
    first = submit(creator, session, profile["profile_id"])
    assert first.status_code == 200
    before = profiles._load(profile["profile_id"])
    session_bytes = Path(assessments._session_path(session["assessment_id"])).read_bytes()
    assert submit(creator, session, profile["profile_id"]).status_code == 409
    assert profiles._load(profile["profile_id"]) == before
    assert Path(assessments._session_path(session["assessment_id"])).read_bytes() == session_bytes
    assert creator.get("/api/assessment/" + session["assessment_id"]).json()["result"] == first.json()


def test_revision_guard_still_rejects_stale_changes_but_legacy_omission_does_not(clients):
    creator, visitor = clients
    original = confirm(creator, synthetic("audit-stale"))
    changed = copy.deepcopy(original)
    changed["education"]["cgpa"] = 7.0
    response = creator.put("/api/profile/audit-stale", json=changed)
    assert response.status_code == 200
    saved = response.json()["profile"]
    assert creator.put("/api/profile/audit-stale", json=changed).json()["profile"] == saved
    stale = copy.deepcopy(original)
    stale["personal"]["phone"] = "0000000000"
    assert visitor.put("/api/profile/audit-stale", json=stale).status_code == 409
    assert visitor.post("/api/profile/verify", json=original).status_code == 409
    stale.pop("revision")
    legacy = visitor.put("/api/profile/audit-stale", json=stale)
    assert legacy.status_code == 200 and legacy.json()["profile"]["education"]["cgpa"] == 8.0


def test_failed_save_does_not_advance_revision_and_retry_applies_once(clients, monkeypatch):
    creator, _ = clients
    original = confirm(creator, synthetic("audit-save-failure"))
    path = Path(profiles._profile_path(original["profile_id"]))
    before = path.read_bytes()
    edited = copy.deepcopy(original)
    edited["education"]["cgpa"] = 7.0
    replace = profiles.os.replace
    def fail(source, target):
        if Path(target) == path:
            raise OSError("Synthetic audit persistence failure")
        return replace(source, target)
    with monkeypatch.context() as patch:
        patch.setattr(profiles.os, "replace", fail)
        assert creator.put("/api/profile/audit-save-failure", json=edited).status_code == 503
    assert path.read_bytes() == before
    saved = creator.put("/api/profile/audit-save-failure", json=edited).json()["profile"]
    assert saved["revision"] == original["revision"] + 1
    assert creator.put("/api/profile/audit-save-failure", json=edited).json()["profile"] == saved


def test_protected_history_evidence_and_originals_cannot_be_forged_by_full_profile_writes(clients, history_profile):
    _, visitor = clients
    forged = copy.deepcopy(history_profile)
    forged["education"]["cgpa"] = 7.0
    forged["prediction_history"] = []
    forged["assessment_evidence"] = []
    forged["original_resume_values"] = {"email": "forged@example.test"}
    forged["provenance"] = {"ml": ["forged"]}
    saved = visitor.put("/api/profile/audit-history", json=forged).json()["profile"]
    confirmed = confirm(visitor, saved)
    for field in ("prediction_history", "assessment_evidence", "original_resume_values"):
        assert confirmed[field] == history_profile[field]
    assert confirmed["provenance"]["ml"] == history_profile["provenance"]["ml"]


def test_current_repeated_creation_without_id_is_not_idempotent_even_with_a_key(clients, isolated_storage):
    creator, _ = clients
    headers = {"Idempotency-Key": "ignored-create-key"}
    first = confirm(creator, synthetic(), headers=headers)
    second = confirm(creator, synthetic(), headers=headers)
    assert first["profile_id"] != second["profile_id"]
    assert len(list(isolated_storage.profiles.glob("*.json"))) == 2


def test_repeated_explicit_resume_creation_duplicates_but_analysis_does_not_write(clients, isolated_storage):
    creator, _ = clients
    headers = {"Idempotency-Key": "ignored-upload-key"}
    first = creator.post("/api/profile/from-resume", files={"file": resume_file()}, headers=headers)
    second = creator.post("/api/profile/from-resume", files={"file": resume_file()}, headers=headers)
    assert first.status_code == second.status_code == 200
    assert first.json()["profile"]["profile_id"] != second.json()["profile"]["profile_id"]
    assert not first.json()["profile"]["verified"] and not second.json()["profile"]["verified"]
    before = {path.name: path.read_bytes() for path in isolated_storage.profiles.glob("*.json")}
    for _ in range(2):
        assert creator.post("/api/resume/analyze", files={"file": resume_file()}).status_code == 200
    assert {path.name: path.read_bytes() for path in isolated_storage.profiles.glob("*.json")} == before


def test_current_foreign_resume_originals_are_returned_without_binary_download_route(clients):
    creator, visitor = clients
    response = creator.post("/api/profile/from-resume", files={"file": resume_file()})
    assert response.status_code == 200
    draft = response.json()["profile"]
    public = visitor.get("/api/profile/" + draft["profile_id"])
    assert public.status_code == 200
    assert public.json()["profile"]["original_resume_values"] == draft["original_resume_values"]
    assert draft["original_resume_values"]
    assert "raw_text" not in public.json()["profile"] and "resume_file" not in public.json()["profile"]
    assert not any("download" in path for path in app.openapi()["paths"])


def test_public_assessment_responses_keep_keys_answers_and_correct_ids_private(clients):
    creator, visitor = clients
    profile = confirm(creator, synthetic("audit-private-answers"))
    session = start(creator, profile["profile_id"])
    assert submit(creator, session, profile["profile_id"]).status_code == 200
    def keys(value):
        if isinstance(value, dict):
            return set(value) | set().union(*(keys(entry) for entry in value.values()))
        if isinstance(value, list):
            return set().union(*(keys(entry) for entry in value))
        return set()
    public = visitor.get("/api/assessment/" + session["assessment_id"]).json()
    forbidden = {"correct_answer", "explanation", "answers", "correct_ids", "score_report"}
    assert not forbidden.intersection(keys(session))
    assert not forbidden.intersection(keys(public))
    stored = assessments._load_session(session["assessment_id"])
    assert stored["answers"] and stored["score_report"]["correct_ids"]


def test_current_anonymous_get_can_persist_expiry_and_recover_accepted_work(clients, monkeypatch):
    creator, visitor = clients
    profile = confirm(creator, synthetic("audit-get-side-effects"))
    expiring = start(creator, profile["profile_id"], "SQL")
    accepted = start(creator, profile["profile_id"])
    with monkeypatch.context() as patch:
        patch.setattr(assessments, "_save_profile", lambda body: (_ for _ in ()).throw(OSError("Synthetic projection failure")))
        failed = submit(creator, accepted, profile["profile_id"])
        assert failed.status_code == 500
    assert assessments._load_session(accepted["assessment_id"])["status"] == "SUBMITTING"
    monkeypatch.setattr(assessments, "_utc_now", lambda: datetime(2026, 11, 9, tzinfo=timezone.utc))
    public = visitor.get("/api/assessment/" + expiring["assessment_id"])
    assert public.status_code == 200 and public.json()["status"] == "EXPIRED"
    assert assessments._load_session(accepted["assessment_id"])["status"] == "COMPLETED"
    assert len(profiles._load(profile["profile_id"])["assessment_evidence"]) == 1


@pytest.mark.parametrize("profile_id", ["../outside", "a/b", "a\\b", "a..b"])
def test_profile_path_validation_still_rejects_traversal_without_record_creation(profile_id, isolated_storage):
    with pytest.raises(profiles.InvalidProfileError):
        profiles.get_profile(profile_id)
    assert not list(isolated_storage.profiles.glob("*.json"))


def test_production_cors_rejects_untrusted_origin_and_private_response_is_not_cached(clients):
    from backend.app.main import create_app
    from backend.app.services.security_config import SecurityConfig
    creator, visitor = clients
    confirm(creator, synthetic("audit-cors"))
    headers = {"Origin": "https://untrusted.example.test", "Access-Control-Request-Method": "PUT",
               "Access-Control-Request-Headers": "content-type"}
    with TestClient(create_app(SecurityConfig()),base_url='https://testserver') as secured:
        preflight = secured.options('/api/profile/audit-cors',headers=headers)
        assert preflight.status_code == 400 and 'Access-Control-Allow-Origin' not in preflight.headers
        response = secured.get('/api/profile/audit-cors',headers={'Origin':headers['Origin']})
        assert response.status_code == 401 and 'Access-Control-Allow-Origin' not in response.headers
        assert response.headers['Cache-Control'] == 'private, no-store'


def test_current_unkeyed_prediction_calls_duplicate_and_invalid_key_is_rejected(clients):
    creator, _ = clients
    profile = confirm(creator, synthetic("audit-unkeyed"))
    path = "/api/profile/" + profile["profile_id"] + "/predict"
    invalid = creator.post(path, headers={"Idempotency-Key": "x" * 129})
    assert invalid.status_code == 422
    assert profiles._load(profile["profile_id"])["prediction_history"] == []
    for _ in range(2):
        response = creator.post(path)
        assert response.status_code == 200 and response.json()["ready_for_prediction"]
    assert len(profiles._load(profile["profile_id"])["prediction_history"]) == 2


def test_stateless_form_prediction_retries_do_not_create_profile_history(clients, monkeypatch, isolated_storage):
    creator, _ = clients
    from backend.app.routes import predict as placement_route, salary as salary_route
    from backend.app.services.ml_feature_mapping import map_profile_to_ml_features
    monkeypatch.setattr(placement_route, "predict", lambda body: {
        "placement_probability": 0.75, "prediction": "PLACED", "confidence": 0.75,
        "model_version": "ownership-audit-stub"})
    monkeypatch.setattr(salary_route, "predict_salary", lambda body: {
        "predicted_salary_lpa": 10.0, "model_version": "ownership-audit-stub"})
    profile = confirm(creator, synthetic("audit-stateless"))
    before = Path(profiles._profile_path(profile["profile_id"])).read_bytes()
    inputs = map_profile_to_ml_features(profile)
    for path in ("/api/predict", "/api/salary-predict"):
        first = creator.post(path, json=inputs)
        second = creator.post(path, json=inputs)
        assert first.status_code == second.status_code == 200 and first.json() == second.json()
    assert Path(profiles._profile_path(profile["profile_id"])).read_bytes() == before
    assert not list(isolated_storage.assessments.glob("*.json"))


def test_current_errors_echo_invalid_sensitive_inputs_and_internal_exception_details(clients, monkeypatch):
    _, visitor = clients
    invalid = visitor.post("/api/profile/verify", json={"personal": {"email": ["SYNTHETIC-PRIVATE-MARKER"]}})
    assert invalid.status_code == 422 and "SYNTHETIC-PRIVATE-MARKER" in invalid.text
    from backend.app.routes import predict as route
    def unavailable(body):
        raise FileNotFoundError("Synthetic internal model path C:/private-audit/model.pkl")
    monkeypatch.setattr(route, "predict", unavailable)
    from backend.app.services.ml_feature_mapping import map_profile_to_ml_features
    response = visitor.post("/api/predict", json=map_profile_to_ml_features(synthetic("audit-errors")))
    assert response.status_code == 503 and "C:/private-audit/model.pkl" in response.text
