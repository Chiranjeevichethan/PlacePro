"""Assessment reservations, deadlines, durable completion and concurrency regressions."""

import copy
import json
import os
import random
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from backend.tests.domain_app import app
from backend.app.services import assessment_service as assessments
from backend.app.services import profile_service as profiles
from backend.app.services.question_bank import get_questions
from backend.tests.support import PROJECT_ROOT, http_get, http_post_json


class Clock:
    def __init__(self):
        self.now = datetime(2026, 11, 6, 12, tzinfo=timezone.utc)

    def __call__(self):
        return self.now

    def advance(self, **kwargs):
        self.now += timedelta(**kwargs)


@pytest.fixture
def clock(monkeypatch):
    value = Clock()
    monkeypatch.setattr(assessments, "_utc_now", value, raising=False)
    return value


@pytest.fixture
def client():
    with TestClient(app) as value:
        yield value


def _profile(profile_id="lifecycle_student"):
    profile = {
        "profile_id": profile_id,
        "verified": True,
        "personal": {"name": "Lifecycle Student", "email": "lifecycle@example.test"},
        "education": {"branch": "CSE"},
        "skills": {"programming_languages": ["Python"]},
        "provenance": {"resume": ["skills.programming_languages"], "user": [], "ml": []},
        "original_resume_values": {"skills.programming_languages": ["Python"]},
        "ml_inputs": {},
        "prediction_history": [],
        "assessment_evidence": [],
    }
    profiles._save(profile)
    return profile


def _start(client, profile_id="lifecycle_student", skill="Python", count=5):
    return client.post("/api/assessment/start", json={
        "profile_id": profile_id, "skill": skill, "num_questions": count,
    })


def _answers(session, correct=True):
    bank = {question["id"]: question["correct_answer"]
            for question in get_questions(session["skill"])}
    return {question["question_id"]: (
        bank[question["question_id"]] if correct else "deliberately wrong"
    ) for question in session["questions"]}


def _submit(client, session, correct=True, profile_id="lifecycle_student", **extra):
    return client.post(f"/api/assessment/{session['assessment_id']}/submit", json={
        "profile_id": profile_id, "answers": _answers(session, correct), **extra,
    })


def _history(profile_id="lifecycle_student"):
    return profiles._load(profile_id)["assessment_evidence"]


def _assert_no_keys(value):
    for question in value["questions"]:
        assert "correct_answer" not in question
        assert "explanation" not in question


def test_ui_session_responses_supply_a_fresh_server_clock(client, clock):
    _profile()
    started = _start(client)
    assert started.status_code == 200, started.text
    session = started.json()
    assert session["server_now"] == clock.now.isoformat()
    assert datetime.fromisoformat(session["expires_at"]) - datetime.fromisoformat(session["created_at"]) == timedelta(minutes=5)
    clock.advance(seconds=30)
    loaded = client.get(f"/api/assessment/{session['assessment_id']}")
    assert loaded.status_code == 200, loaded.text
    assert loaded.json()["server_now"] == clock.now.isoformat()
    assert loaded.json()["expires_at"] == session["expires_at"]
    assert loaded.json()["result"] is None


def test_ui_completed_result_can_be_reloaded_without_private_answers(client, clock):
    _profile()
    session = _start(client).json()
    clock.advance(seconds=20)
    submitted = _submit(client, session)
    assert submitted.status_code == 200, submitted.text
    loaded = client.get(f"/api/assessment/{session['assessment_id']}")
    assert loaded.status_code == 200, loaded.text
    body = loaded.json()
    assert body["status"] == "COMPLETED"
    assert body["result"] == submitted.json()
    assert body["submitted_at"] == clock.now.isoformat()
    _assert_no_keys(body)
    for forbidden in ("answers", "correct_answer", "correct_ids", "explanation", "score_report"):
        assert f'"{forbidden}"' not in loaded.text
    duplicate = _submit(client, session)
    assert duplicate.status_code == 409
    assert client.get(f"/api/assessment/{session['assessment_id']}").json()["result"] == submitted.json()
    assert len(_history()) == 1


def test_ui_expired_session_has_no_public_result_or_evidence(client, clock):
    _profile()
    session = _start(client).json()
    clock.advance(minutes=5)
    loaded = client.get(f"/api/assessment/{session['assessment_id']}")
    assert loaded.status_code == 200, loaded.text
    body = loaded.json()
    assert body["status"] == "EXPIRED" and body["result"] is None
    _assert_no_keys(body)
    assert _submit(client, session).status_code == 410
    assert _history() == []


def test_ui_profile_skills_and_performance_use_persisted_assessment_evidence(client, clock):
    initial = _profile()
    session = _start(client).json()
    clock.advance(seconds=15)
    result = _submit(client, session).json()
    assert result["skill_score"] == 100
    loaded = profiles._load("lifecycle_student")
    assert loaded["ml_inputs"] == initial["ml_inputs"]
    assert loaded["skills"] == initial["skills"]
    history = client.get("/api/profile/lifecycle_student/assessments")
    assert history.status_code == 200, history.text
    entry, = history.json()["assessments"]
    assert entry["assessment_id"] == session["assessment_id"]
    assert entry["source"] == "assessment" and entry["verified"] is True
    skills = client.get("/api/profile/lifecycle_student/skills")
    assert skills.status_code == 200, skills.text
    python, = [value for value in skills.json()["skills"] if value["skill"] == "Python"]
    assert python["assessment_score"] == 100 and python["assessment_verified"] is True
    performance = client.get("/api/profile/lifecycle_student/performance")
    assert performance.status_code == 200, performance.text
    assert performance.json()["assessment_history"] == history.json()["assessments"]
    assert performance.json()["summary"]["assessments"]["assessments_count"] == 1


def test_outstanding_sessions_reserve_unique_attempts_and_limit_fourth_start(client):
    _profile()
    responses = [_start(client) for _ in range(3)]
    assert [response.status_code for response in responses] == [200, 200, 200]
    sessions = [response.json() for response in responses]
    assert [session["attempt"] for session in sessions] == [1, 2, 3]
    assert len({session["assessment_id"] for session in sessions}) == 3
    fourth = _start(client)
    assert fourth.status_code == 429, fourth.text
    assert "active" in fourth.json()["detail"].lower()
    assert _history() == []


def test_completed_and_outstanding_sessions_share_the_quota(client, monkeypatch):
    monkeypatch.setattr(assessments, "COOLDOWN_HOURS", 0)
    _profile()
    first = _start(client).json()
    assert _submit(client, first).status_code == 200
    second, third = _start(client), _start(client)
    assert second.status_code == third.status_code == 200
    assert [second.json()["attempt"], third.json()["attempt"]] == [2, 3]
    assert _start(client).status_code == 429
    assert len(_history()) == 1


def test_expired_reservations_free_capacity_and_preserve_records(client, clock, isolated_storage):
    _profile()
    sessions = [_start(client).json() for _ in range(3)]
    clock.advance(minutes=5)
    next_response = _start(client)
    assert next_response.status_code == 200, next_response.text
    assert next_response.json()["attempt"] == 4  # expired reservation ordinals are retained
    for session in sessions:
        stored = assessments._load_session(session["assessment_id"])
        assert stored["status"] == "EXPIRED"
        assert stored["score_report"] is None and stored["answers"] == {}
        assert stored["submitted_at"] is None
    assert len(list(isolated_storage.assessments.glob("*.json"))) == 4
    assert _history() == []


def test_outstanding_submission_cannot_bypass_cooldown(client, clock):
    _profile()
    first, second, third = [_start(client).json() for _ in range(3)]
    clock.advance(minutes=1)
    assert _submit(client, first).status_code == 200
    for session in (second, third):
        blocked = _submit(client, session)
        assert blocked.status_code == 429, blocked.text
        body = blocked.json()
        assert body["retry_after_seconds"] == 24 * 3600
        assert body["next_allowed_at"] == (clock.now + timedelta(hours=24)).isoformat()
        assert blocked.headers["Retry-After"] == str(body["retry_after_seconds"])
        stored = assessments._load_session(session["assessment_id"])
        assert stored["status"] == "IN_PROGRESS" and stored["score_report"] is None
    blocked_start = _start(client)
    assert blocked_start.status_code == 429
    assert blocked_start.json()["next_allowed_at"] == blocked.json()["next_allowed_at"]
    assert len(_history()) == 1
    clock.advance(hours=24)
    assert _submit(client, second).status_code == 410
    retake = _start(client)
    assert retake.status_code == 200 and retake.json()["attempt"] == 4


def test_legacy_outstanding_sessions_cannot_exceed_completed_quota(client, clock, monkeypatch):
    monkeypatch.setattr(assessments, "COOLDOWN_HOURS", 0)
    _profile()
    first = _start(client).json()
    stored = assessments._load_session(first["assessment_id"])
    sessions = [first]
    for index in range(3):
        legacy = copy.deepcopy(stored)
        legacy["assessment_id"] = f"legacy_outstanding_{index}"
        legacy["attempt"] = 1
        legacy.pop("expires_at", None)
        legacy.pop("time_limit_minutes", None)
        assessments._save_session(legacy)
        sessions.append({**first, "assessment_id": legacy["assessment_id"]})
    assert _start(client).status_code == 429
    results = [_submit(client, session) for session in sessions]
    assert [result.status_code for result in results] == [200, 200, 200, 429]
    assert len(_history()) == 3
    assert len({entry["attempt"] for entry in _history()}) == 3
    assert "retry_after_seconds" not in results[-1].json()


@pytest.mark.parametrize("offset_microseconds,expected_status", [(-1, 200), (0, 410), (1, 410)])
def test_submission_expires_at_authoritative_deadline(client, clock, offset_microseconds, expected_status):
    _profile()
    session = _start(client).json()
    assert session["created_at"] == clock.now.isoformat()
    assert session["time_limit_minutes"] == 5
    assert datetime.fromisoformat(session["expires_at"]) == clock.now + timedelta(minutes=5)
    clock.advance(minutes=5, microseconds=offset_microseconds)
    result = _submit(client, session)
    assert result.status_code == expected_status, result.text
    stored = assessments._load_session(session["assessment_id"])
    if expected_status == 410:
        assert stored["status"] == "EXPIRED"
        assert stored["score_report"] is None and stored["submitted_at"] is None
        assert _history() == []
    else:
        assert stored["status"] == "COMPLETED" and len(_history()) == 1


def test_session_get_persists_expiry_without_scoring_or_leaking_keys(client, clock):
    _profile()
    session = _start(client).json()
    _assert_no_keys(session)
    active = client.get(f"/api/assessment/{session['assessment_id']}")
    assert active.status_code == 200 and active.json()["status"] == "IN_PROGRESS"
    clock.advance(minutes=6)
    expired = client.get(f"/api/assessment/{session['assessment_id']}")
    assert expired.status_code == 200
    body = expired.json()
    assert body["status"] == "EXPIRED" and body["expires_at"] == session["expires_at"]
    assert body["expired_at"] == session["expires_at"]
    _assert_no_keys(body)
    assert assessments._load_session(session["assessment_id"])["status"] == "EXPIRED"
    assert _submit(client, session).status_code == 410 and _history() == []


@pytest.mark.parametrize("creation", [None, "", "bad timestamp", "2026-11-06T12:00:00"])
def test_legacy_sessions_with_unusable_timing_expire_closed(client, clock, creation):
    _profile()
    session = _start(client).json()
    stored = assessments._load_session(session["assessment_id"])
    stored["created_at"] = creation
    stored.pop("expires_at", None)
    stored.pop("time_limit_minutes", None)
    assessments._save_session(stored)
    result = _submit(client, session)
    assert result.status_code == 410, result.text
    assert assessments._load_session(session["assessment_id"])["status"] == "EXPIRED"
    assert _history() == []


def test_legacy_expiry_is_derived_from_original_creation_and_does_not_reset(client, clock):
    _profile()
    session = _start(client).json()
    stored = assessments._load_session(session["assessment_id"])
    stored["created_at"] = clock.now.astimezone(timezone(timedelta(hours=5, minutes=30))).isoformat()
    stored.pop("expires_at", None)
    stored.pop("time_limit_minutes", None)
    assessments._save_session(stored)
    clock.advance(minutes=6)
    first = client.get(f"/api/assessment/{session['assessment_id']}").json()
    clock.advance(minutes=2)
    second = client.get(f"/api/assessment/{session['assessment_id']}").json()
    assert first["status"] == second["status"] == "EXPIRED"
    assert first["expires_at"] == second["expires_at"] == session["expires_at"]
    assert _history() == []


def test_client_timing_and_score_fields_cannot_rescue_an_expired_submission(client, clock):
    _profile()
    session = _start(client).json()
    clock.advance(minutes=6)
    result = _submit(client, session, created_at=clock.now.isoformat(),
                     expires_at=(clock.now + timedelta(days=1)).isoformat(),
                     time_spent_seconds=0, skill_score=100, status="COMPLETED")
    assert result.status_code == 410, result.text
    assert _history() == []


def test_duplicate_submission_preserves_one_completion(client, clock):
    original = _profile()
    session = _start(client).json()
    first = _submit(client, session)
    assert first.status_code == 200 and first.json()["skill_score"] == 100
    clock.advance(seconds=1)
    duplicate = _submit(client, session, correct=False)
    assert duplicate.status_code == 409
    assert len(_history()) == 1 and _history()[0]["score"] == 100
    stored = profiles._load(original["profile_id"])
    assert stored["skills"] == original["skills"]
    assert stored["original_resume_values"] == original["original_resume_values"]
    assert stored["provenance"] == original["provenance"]


@pytest.mark.parametrize("passed", [True, False], ids=["passing-score", "failing-score"])
def test_legitimate_retake_after_cooldown_for_any_completed_score(client, clock, passed):
    _profile()
    session = _start(client).json()
    result = _submit(client, session, correct=passed)
    assert result.status_code == 200
    assert result.json()["skill_score"] == (100 if passed else 0)
    assert _start(client).status_code == 429
    clock.advance(hours=24)
    retake = _start(client)
    assert retake.status_code == 200 and retake.json()["attempt"] == 2
    assert _submit(client, retake.json()).status_code == 200
    assert [entry["attempt"] for entry in _history()] == [1, 2]


@pytest.mark.parametrize("assessment_id", ["", "../profile", "../../data", "bad/id", "unknown-session"])
def test_invalid_session_ids_are_rejected(assessment_id):
    _profile()
    with pytest.raises(assessments.AssessmentNotFoundError):
        assessments.submit_assessment(assessment_id, "lifecycle_student", {"q": "a"})
    with pytest.raises(assessments.AssessmentNotFoundError):
        assessments.get_assessment(assessment_id)
    assert _history() == []


def test_wrong_owner_cannot_submit_or_change_session_state(client, clock):
    _profile()
    session = _start(client).json()
    clock.advance(minutes=6)
    result = _submit(client, session, profile_id="someone_else")
    assert result.status_code == 403
    assert assessments._load_session(session["assessment_id"])["status"] == "IN_PROGRESS"
    assert _history() == []
    assert _submit(client, session).status_code == 410


@pytest.mark.parametrize("bad_answers", [{}, {"unknown-question": "answer"}])
def test_invalid_answers_leave_a_retryable_active_reservation(client, bad_answers):
    _profile()
    session = _start(client).json()
    result = client.post(f"/api/assessment/{session['assessment_id']}/submit",
                         json={"profile_id": "lifecycle_student", "answers": bad_answers})
    assert result.status_code == 400
    assert assessments._load_session(session["assessment_id"])["status"] == "IN_PROGRESS"
    assert _history() == []
    assert _submit(client, session).status_code == 200
    assert len(_history()) == 1


def test_latest_evidence_uses_completion_time_when_reservations_finish_out_of_order(client, clock, monkeypatch):
    monkeypatch.setattr(assessments, "COOLDOWN_HOURS", 0)
    _profile()
    first, second = _start(client).json(), _start(client).json()
    assert _submit(client, second, correct=False).status_code == 200
    clock.advance(seconds=1)
    assert _submit(client, first).status_code == 200
    assert [entry["attempt"] for entry in _history()] == [2, 1]
    latest = assessments.get_assessment_evidence(profiles._load("lifecycle_student"))
    assert latest[0]["assessment_id"] == first["assessment_id"]
    assert latest[0]["score"] == 100
    assert _start(client).json()["attempt"] == 3


def test_seeded_question_selection_is_reproducible_and_does_not_modify_bank():
    _profile()
    bank = copy.deepcopy(get_questions("Python"))
    first = assessments.start_assessment("lifecycle_student", "Python", 5, rng=random.Random(7))
    second = assessments.start_assessment("lifecycle_student", "Python", 5, rng=random.Random(7))
    third = assessments.start_assessment("lifecycle_student", "Python", 5, rng=random.Random(8))
    assert first["questions"] == second["questions"]
    assert first["questions"] != third["questions"]
    assert [q["question_id"] for q in first["questions"]] != [q["id"] for q in bank[:5]]
    assert len({q["question_id"] for q in first["questions"]}) == 5
    assert get_questions("Python") == bank
    _assert_no_keys(first)


def test_full_bank_selection_shuffles_without_repetition_or_answer_exposure():
    _profile()
    first = assessments.start_assessment("lifecycle_student", "Python", 25, rng=random.Random(42))
    second = assessments.start_assessment("lifecycle_student", "Python", 25, rng=random.Random(43))
    expected = {q["id"] for q in get_questions("Python")}
    assert {q["question_id"] for q in first["questions"]} == expected
    assert {q["question_id"] for q in second["questions"]} == expected
    assert first["questions"] != second["questions"]
    assert first["time_limit_minutes"] == 25
    _assert_no_keys(first)
    _assert_no_keys(second)


def _fail_once(monkeypatch, name, predicate=lambda value: True):
    real = getattr(assessments, name)
    failed = False

    def fail(value):
        nonlocal failed
        if not failed and predicate(value):
            failed = True
            raise OSError(f"injected {name} write failure")
        return real(value)

    monkeypatch.setattr(assessments, name, fail)
    return real


@pytest.mark.parametrize("write_step", ["profile", "completed-session"])
def test_interrupted_submission_is_recoverable_without_duplicate_scoring(monkeypatch, clock, write_step):
    _profile()
    session = assessments.start_assessment("lifecycle_student", "Python", 5)
    name = "_save_profile" if write_step == "profile" else "_save_session"
    real = _fail_once(monkeypatch, name, lambda value: (
        write_step == "profile" or value["status"] == "COMPLETED"
    ))
    accepted_at = clock.now.isoformat()
    with pytest.raises(OSError, match="injected"):
        assessments.submit_assessment(session["assessment_id"], "lifecycle_student", _answers(session))
    assert assessments._load_session(session["assessment_id"])["status"] == "SUBMITTING"
    assert len(_history()) == (0 if write_step == "profile" else 1)
    monkeypatch.setattr(assessments, name, real)
    monkeypatch.setattr(assessments, "compute_score", lambda *args: pytest.fail("Recovery must not rescore"))
    clock.advance(hours=1)  # acceptance was timely; recovery uses the stored submission
    result = assessments.submit_assessment(session["assessment_id"], "lifecycle_student", _answers(session))
    assert result["skill_score"] == 100
    assert len(_history()) == 1 and _history()[0]["timestamp"] == accepted_at
    assert assessments._load_session(session["assessment_id"])["status"] == "COMPLETED"
    with pytest.raises(assessments.AssessmentCompletedError):
        assessments.submit_assessment(session["assessment_id"], "lifecycle_student", _answers(session))


def test_start_recovers_pending_evidence_and_enforces_its_cooldown(monkeypatch, clock, client):
    _profile()
    session = _start(client).json()
    real = _fail_once(monkeypatch, "_save_profile")
    failed = _submit(client, session)
    assert failed.status_code == 500
    assert assessments._load_session(session["assessment_id"])["status"] == "SUBMITTING"
    monkeypatch.setattr(assessments, "_save_profile", real)
    blocked = _start(client)
    assert blocked.status_code == 429 and blocked.json()["retry_after_seconds"] == 86400
    assert len(_history()) == 1
    assert assessments._load_session(session["assessment_id"])["status"] == "COMPLETED"


def test_completed_legacy_session_without_evidence_is_recovered_and_counted(client, clock):
    _profile()
    session = _start(client).json()
    legacy = assessments._load_session(session["assessment_id"])
    legacy.update(status="COMPLETED", answers=_answers(session),
                  submitted_at=clock.now.isoformat(),
                  score_report=assessments.compute_score(legacy, _answers(session)))
    assessments._save_session(legacy)
    blocked = _start(client)
    assert blocked.status_code == 429
    assert len(_history()) == 1 and _history()[0]["assessment_id"] == session["assessment_id"]
    assert _submit(client, session).status_code == 409
    assert len(_history()) == 1


def _thread_race(action, workers=12):
    gate = threading.Barrier(workers)

    def run(index):
        gate.wait(timeout=10)
        return action(index)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(run, range(workers)))


def test_concurrent_start_requests_reserve_only_three_attempts(client, isolated_storage):
    _profile()
    results = _thread_race(lambda index: _start(client))
    successes = [result.json() for result in results if result.status_code == 200]
    assert sorted(result.status_code for result in results) == [200] * 3 + [429] * 9
    assert sorted(session["attempt"] for session in successes) == [1, 2, 3]
    assert len({session["assessment_id"] for session in successes}) == 3
    assert len(list(isolated_storage.assessments.glob("*.json"))) == 3
    assert _history() == []


def test_concurrent_duplicate_submissions_record_exactly_one_attempt(client):
    _profile()
    session = _start(client).json()
    results = _thread_race(lambda index: _submit(client, session))
    assert sorted(result.status_code for result in results) == [200] + [409] * 11
    assert len(_history()) == 1 and _history()[0]["score"] == 100
    assert assessments._load_session(session["assessment_id"])["status"] == "COMPLETED"


def test_concurrent_different_skill_submissions_preserve_all_evidence(client):
    _profile()
    skills = ["Python", "C", "Java", "SQL"]
    sessions = [_start(client, skill=skill).json() for skill in skills]
    results = _thread_race(lambda index: _submit(client, sessions[index]), workers=4)
    assert all(result.status_code == 200 for result in results)
    assert {entry["skill"] for entry in _history()} == set(skills)
    assert len(_history()) == 4


@pytest.mark.parametrize("mutation", ["update", "verify", "prediction"])
def test_profile_mutations_cannot_overwrite_concurrent_assessment_evidence(monkeypatch, mutation):
    original = _profile()
    session = assessments.start_assessment(original["profile_id"], "Python", 5)
    snapshot_read, continue_mutation = threading.Event(), threading.Event()
    real_load = profiles._load
    errors = []

    def paused_load(profile_id):
        snapshot = real_load(profile_id)
        if threading.current_thread().name == "profile_mutator":
            snapshot_read.set()
            assert continue_mutation.wait(timeout=10)
        return snapshot

    monkeypatch.setattr(profiles, "_load", paused_load)
    monkeypatch.setattr(profiles, "check_profile_completion", lambda profile: {
        "profile_complete": True, "ml_feature_mapping": {},
    })
    monkeypatch.setattr(profiles, "predict_with_model", lambda inputs: {
        "placement_probability": 0.8, "prediction": "PLACED",
        "confidence": 0.8, "model_version": "test-only",
    })

    def mutate():
        try:
            if mutation == "update":
                profiles.update_profile(original["profile_id"], original)
            elif mutation == "verify":
                profiles.verify_profile(original)
            else:
                profiles.predict_for_profile(original["profile_id"])
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=mutate, name="profile_mutator")
    thread.start()
    try:
        assert snapshot_read.wait(timeout=10)
        with ThreadPoolExecutor(max_workers=1) as pool:
            submission = pool.submit(assessments.submit_assessment, session["assessment_id"],
                                     original["profile_id"], _answers(session))
            try:
                submission.result(timeout=0.1)
            except TimeoutError:
                pass  # the profile transaction may hold the assessment until it saves
            finally:
                continue_mutation.set()
            assert submission.result(timeout=10)["skill_score"] == 100
    finally:
        continue_mutation.set()
        thread.join(timeout=10)
    assert not thread.is_alive() and errors == []
    assert len(_history()) == 1
    if mutation == "prediction":
        assert len(profiles._load(original["profile_id"])["prediction_history"]) == 1


_PROCESS_SCRIPT = r"""
import json, os, sys, time
from pathlib import Path
from backend.app.services import assessment_service as service
from backend.app.services import profile_service
gate = Path(sys.argv[1])
action, profile_id, assessment_id = sys.argv[2:5]
service.COOLDOWN_HOURS = 0
save = service._save_session
def slow_save(session):
    time.sleep(0.03)
    save(session)
service._save_session = slow_save
gate.with_name(str(os.getpid()) + ".ready").write_text("ready")
deadline = time.monotonic() + 20
while not gate.exists():
    if time.monotonic() >= deadline:
        raise RuntimeError("Concurrency gate was not released")
    time.sleep(0.01)
results = []
for index in range(3):
    try:
        if action == "start":
            result = service.start_assessment(profile_id, "Python", 5)
        else:
            session = service._load_session(assessment_id)
            answers = {q["id"]: q["correct_answer"] for q in session["questions"]}
            result = service.submit_assessment(assessment_id, profile_id, answers)
        results.append({"status": 200, "attempt": result["attempt"], "id": result["assessment_id"]})
    except service.AssessmentError as exc:
        results.append({"status": exc.status_code, "detail": str(exc)})
print(json.dumps({"pid": os.getpid(), "results": results}))
"""


def _process_race(storage, action, assessment_id=""):
    gate = storage.root / "process_gate"
    environment = os.environ.copy()
    environment.update(storage.environment())
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    processes = []
    try:
        for _ in range(4):
            processes.append(subprocess.Popen(
                [sys.executable, "-B", "-c", _PROCESS_SCRIPT, str(gate),
                 action, "lifecycle_student", assessment_id],
                cwd=PROJECT_ROOT, env=environment, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True,
                creationflags=(subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0),
            ))
        deadline = time.monotonic() + 20
        while len(list(storage.root.glob("*.ready"))) < 4 and time.monotonic() < deadline:
            assert all(process.poll() is None for process in processes), "A worker exited before the race"
            time.sleep(0.02)
        assert len(list(storage.root.glob("*.ready"))) == 4, "Workers were not ready within 20s"
        gate.write_text("go", encoding="utf-8")
        workers = []
        for process in processes:
            stdout, stderr = process.communicate(timeout=30)
            assert process.returncode == 0, f"Worker failed: {stdout}\n{stderr}"
            workers.append(json.loads(stdout))
        assert len({worker["pid"] for worker in workers}) == 4
        return [result for worker in workers for result in worker["results"]]
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)


def test_multiple_processes_cannot_overreserve_json_attempts(isolated_storage):
    _profile()
    results = _process_race(isolated_storage, "start")
    assert sorted(result["status"] for result in results) == [200] * 3 + [429] * 9
    successes = [result for result in results if result["status"] == 200]
    assert sorted(result["attempt"] for result in successes) == [1, 2, 3]
    assert len({result["id"] for result in successes}) == 3
    assert len(list(isolated_storage.assessments.glob("*.json"))) == 3
    assert _history() == []


def test_multiple_processes_cannot_duplicate_json_completion(isolated_storage):
    _profile()
    session = assessments.start_assessment("lifecycle_student", "Python", 5)
    results = _process_race(isolated_storage, "submit", session["assessment_id"])
    assert sorted(result["status"] for result in results) == [200] + [409] * 11
    assert len(_history()) == 1
    assert assessments._load_session(session["assessment_id"])["status"] == "COMPLETED"


@pytest.mark.live_http
def test_live_http_concurrent_lifecycle_uses_isolated_server(live_server_url):
    profile_id = f"lifecycle_http_{uuid.uuid4().hex}"
    status, body = http_post_json(f"{live_server_url}/api/profile/verify", {
        "profile_id": profile_id,
        "personal": {"name": "HTTP Lifecycle Student", "email": "http@example.test"},
        "education": {"branch": "CSE"},
    })
    assert status == 200, body

    def start(index):
        return http_post_json(f"{live_server_url}/api/assessment/start", {
            "profile_id": profile_id, "skill": "Python", "num_questions": 5,
        })

    starts = _thread_race(start)
    assert sorted(status for status, body in starts) == [200] * 3 + [429] * 9
    sessions = [body for status, body in starts if status == 200]
    assert sorted(session["attempt"] for session in sessions) == [1, 2, 3]
    session = sessions[0]
    _assert_no_keys(session)

    def submit(index):
        return http_post_json(f"{live_server_url}/api/assessment/{session['assessment_id']}/submit", {
            "profile_id": profile_id, "answers": _answers(session),
        })

    submissions = _thread_race(submit)
    assert sorted(status for status, body in submissions) == [200] + [409] * 11, submissions
    other = sessions[1]
    status, body = http_post_json(f"{live_server_url}/api/assessment/{other['assessment_id']}/submit", {
        "profile_id": profile_id, "answers": _answers(other),
    })
    assert status == 429 and body["retry_after_seconds"] > 0
    status, body = http_get(f"{live_server_url}/api/profile/{profile_id}/assessments")
    assert status == 200 and len(body["assessments"]) == 1
    status, body = http_get(f"{live_server_url}/api/assessment/{session['assessment_id']}")
    assert status == 200 and body["status"] == "COMPLETED"
    _assert_no_keys(body)
