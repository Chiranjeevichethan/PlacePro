# ============================================================
# PLACEPRO - MOCK TEST START / RETRY COOLDOWN TESTS
# ============================================================
#
# The Mock Tests page reported "Please wait before retrying Python. Next
# attempt allowed after ..." and could not start a test. The backend
# cooldown was correct; the defect was that the retry state was neither
# machine-readable (so the UI could not show an accurate remaining wait)
# nor self-clearing (so the warning outlived the wait and described a
# skill the student had already switched away from).
#
# These tests pin BOTH halves of the fix and the preserved policy:
#   * the retry cooldown still blocks a start while it is active;
#   * it reports an accurate, machine-readable remaining wait;
#   * it stops blocking the moment it lapses;
#   * UTC timestamps are compared correctly and bad ones never crash;
#   * the permanent attempt limit stays distinct from the cooldown;
#   * technical failures never record a completed attempt; active sessions reserve quota;
#   * cooldowns stay isolated per profile and per skill;
#   * the rest of the mock test flow still works.
#
# Stores are isolated from the real data/ directory (see the fixture).
# ============================================================

import json
import os
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from backend.tests.domain_app import app  # noqa: E402
from backend.app.services import assessment_service, profile_service  # noqa: E402
from backend.app.services.assessment_service import (  # noqa: E402
    COOLDOWN_HOURS,
    MAX_ATTEMPTS_PER_SKILL,
    _last_attempt_time,
)

client = TestClient(app)

SKILL = "Python"
OTHER_SKILL = "C"


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _iso(moment):
    return moment.isoformat()


def _evidence(skill=SKILL, timestamp=None, attempt=1, score=50.0):
    return {
        "skill": skill,
        "score": score,
        "level": "Developing",
        "source": "assessment",
        "verified": True,
        "assessment_id": "seed-assessment-0001",
        "attempt": attempt,
        "timestamp": timestamp,
    }


def _make_profile(profile_id, verified=True, evidence=None):
    profile = {
        "profile_id": profile_id,
        "verified": verified,
        "personal": {"name": "Assessment Test Student"},
        "education": {"branch": "CSE"},
        "ml_inputs": {},
        "assessment_evidence": list(evidence or []),
    }
    profile_service._save(profile)
    return profile


def _completed_ago(profile_id, hours_ago, skill=SKILL):
    """A profile whose only recorded attempt was submitted `hours_ago`."""

    stamp = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    _make_profile(profile_id, evidence=[_evidence(skill=skill, timestamp=_iso(stamp))])
    return stamp


def _start(profile_id, skill=SKILL, num_questions=5):
    return client.post(
        "/api/assessment/start",
        json={
            "profile_id": profile_id,
            "skill": skill,
            "num_questions": num_questions,
        },
    )


def _correct_answers(session):
    from backend.app.services.question_bank import get_questions

    bank = {q["id"]: q["correct_answer"] for q in get_questions(session["skill"])}
    return {
        q["question_id"]: bank[q["question_id"]]
        for q in session["questions"]
    }


def _stored_evidence(profile_id):
    return profile_service._load(profile_id).get("assessment_evidence") or []


# ------------------------------------------------------------------
# Policy is preserved (the audit found no evidence to change it)
# ------------------------------------------------------------------


def test_retry_policy_values_are_unchanged():
    assert COOLDOWN_HOURS == 24
    assert MAX_ATTEMPTS_PER_SKILL == 3


# ------------------------------------------------------------------
# 1. No previous attempt -> can start
# ------------------------------------------------------------------


def test_profile_with_no_attempt_can_start_a_test():
    _make_profile("retry_fresh")

    response = _start("retry_fresh")

    assert response.status_code == 200

    body = response.json()

    assert body["skill"] == SKILL
    assert body["attempt"] == 1
    assert body["total_questions"] == 5
    assert len(body["questions"]) == 5


# ------------------------------------------------------------------
# 2. Active cooldown -> blocked, with an accurate machine-readable wait
# ------------------------------------------------------------------


def test_active_cooldown_blocks_and_reports_the_remaining_wait():
    submitted = _completed_ago("retry_cooling", hours_ago=1)

    response = _start("retry_cooling")

    assert response.status_code == 429

    body = response.json()
    expected_next = submitted + timedelta(hours=COOLDOWN_HOURS)

    # The human-readable detail string is unchanged (existing contract).
    assert body["detail"] == (
        f"Please wait before retrying {SKILL}. "
        f"Next attempt allowed after {expected_next.isoformat()}."
    )

    # ...and the retry timing is now machine-readable.
    assert body["next_allowed_at"] == expected_next.isoformat()

    remaining = (expected_next - datetime.now(timezone.utc)).total_seconds()
    assert body["retry_after_seconds"] == pytest.approx(remaining, abs=5)
    # ~23h left of the 24h cooldown (the attempt was stamped 1h ago).
    assert 23 * 3600 - 5 <= body["retry_after_seconds"] <= 23 * 3600 + 5

    # Standard HTTP retry signalling.
    assert response.headers["Retry-After"] == str(body["retry_after_seconds"])


def test_repeated_blocked_attempts_report_a_decreasing_wait():
    _completed_ago("retry_decreasing", hours_ago=2)

    first = _start("retry_decreasing").json()["retry_after_seconds"]
    second = _start("retry_decreasing").json()["retry_after_seconds"]

    assert 0 < second <= first
    assert first - second <= 5


def test_blocked_start_creates_no_assessment_session(isolated_storage):
    _completed_ago("retry_no_session", hours_ago=1)

    before = set(os.listdir(isolated_storage.assessments))

    assert _start("retry_no_session").status_code == 429

    assert set(os.listdir(isolated_storage.assessments)) == before


# ------------------------------------------------------------------
# 3. Expired cooldown -> no longer blocks (no refresh, no wait)
# ------------------------------------------------------------------


def test_expired_cooldown_no_longer_blocks_a_test():
    _completed_ago("retry_expired", hours_ago=COOLDOWN_HOURS + 1)

    response = _start("retry_expired")

    assert response.status_code == 200

    body = response.json()

    assert body["attempt"] == 2  # the earlier completed attempt still counts
    assert len(body["questions"]) == 5


def test_cooldown_boundary_just_after_expiry_is_allowed():
    _completed_ago("retry_boundary", hours_ago=COOLDOWN_HOURS)

    assert _start("retry_boundary").status_code == 200


def test_cooldown_disabled_allows_back_to_back_starts(monkeypatch):
    """COOLDOWN_HOURS = 0 is the documented off switch."""

    monkeypatch.setattr(assessment_service, "COOLDOWN_HOURS", 0)
    _completed_ago("retry_disabled", hours_ago=0)

    assert _start("retry_disabled").status_code == 200


# ------------------------------------------------------------------
# 4 + 5. UTC / timestamp handling and remaining-time accuracy
# ------------------------------------------------------------------


def test_last_attempt_time_uses_the_latest_aware_timestamp():
    now = datetime.now(timezone.utc)
    older = _evidence(timestamp=_iso(now - timedelta(hours=5)))
    newer = _evidence(timestamp=_iso(now - timedelta(hours=1)))

    expected = datetime.fromisoformat(newer["timestamp"])

    # Order-independent: the latest instant wins, not the last list entry.
    assert _last_attempt_time([older, newer]) == expected
    assert _last_attempt_time([newer, older]) == expected
    assert _last_attempt_time([older, older]) == datetime.fromisoformat(
        older["timestamp"]
    )


@pytest.mark.parametrize(
    "bad_value",
    [None, "", "   ", "not-a-timestamp", 12345, "2026-10-11T08:17:31.733482"],
)
def test_unusable_timestamps_are_ignored_instead_of_blocking_or_crashing(bad_value):
    """A missing/malformed/naive stamp must never block or 500 a start."""

    _make_profile(
        "retry_bad_stamp",
        evidence=[_evidence(timestamp=bad_value)],
    )

    assert _last_attempt_time([_evidence(timestamp=bad_value)]) is None

    response = _start("retry_bad_stamp")

    assert response.status_code == 200  # not 429, and not 500


def test_cooldown_uses_utc_consistently():
    """A stamp 1h old in UTC blocks; 25h old does not - no local-time drift."""

    _completed_ago("retry_utc_blocked", hours_ago=1)
    _completed_ago("retry_utc_clear", hours_ago=25)

    assert _start("retry_utc_blocked").status_code == 429
    assert _start("retry_utc_clear").status_code == 200


# ------------------------------------------------------------------
# 6 + 7. Technical failures must not consume an attempt
# ------------------------------------------------------------------


def test_failed_submission_does_not_record_an_attempt():
    _make_profile("retry_failed_submit")

    session = _start("retry_failed_submit").json()

    # A technical failure: unknown assessment id and empty answers.
    bad = client.post(
        "/api/assessment/00000000-0000-0000-0000-000000000000/submit",
        json={"profile_id": "retry_failed_submit", "answers": {"q": "a"}},
    )
    assert bad.status_code == 404

    empty = client.post(
        f"/api/assessment/{session['assessment_id']}/submit",
        json={"profile_id": "retry_failed_submit", "answers": {}},
    )
    assert empty.status_code == 400

    # No completed attempt consumed and no cooldown created. The original
    # reservation remains retryable; an additional start reserves another slot.
    assert _stored_evidence("retry_failed_submit") == []
    assert assessment_service._load_session(session["assessment_id"])["status"] == "IN_PROGRESS"

    retry = _start("retry_failed_submit")

    assert retry.status_code == 200
    assert retry.json()["attempt"] == 2
    completed = client.post(
        f"/api/assessment/{session['assessment_id']}/submit",
        json={"profile_id": "retry_failed_submit", "answers": _correct_answers(session)},
    )
    assert completed.status_code == 200, completed.text
    assert len(_stored_evidence("retry_failed_submit")) == 1
    assert _stored_evidence("retry_failed_submit")[0]["attempt"] == 1


def test_unverified_profile_is_rejected_without_recording_an_attempt():
    """ProfileServiceError is HTTP 400 on this endpoint (existing behaviour)."""

    _make_profile("retry_unverified", verified=False)

    response = _start("retry_unverified")

    assert response.status_code == 400
    assert "verified" in response.json()["detail"]
    assert _stored_evidence("retry_unverified") == []


# ------------------------------------------------------------------
# 8. Start Test initializes a real assessment
# ------------------------------------------------------------------


def test_start_initializes_an_in_progress_session_without_answer_keys(isolated_storage):
    _make_profile("retry_session")

    body = _start("retry_session").json()
    session_path = isolated_storage.assessments / f"{body['assessment_id']}.json"

    assert os.path.exists(session_path)

    with open(session_path, encoding="utf-8") as session_file:
        session = json.load(session_file)

    assert session["status"] == "IN_PROGRESS"
    assert session["submitted_at"] is None
    assert session["profile_id"] == "retry_session"
    assert len(session["questions"]) == 5

    for question in body["questions"]:
        assert question["options"]
        assert "correct_answer" not in question
        assert "explanation" not in question

    assert datetime.fromisoformat(session["created_at"]).tzinfo is not None


# ------------------------------------------------------------------
# 9. Repeated starts do not create duplicate/repeated attempts
# ------------------------------------------------------------------


def test_repeated_starts_reserve_unique_attempts_without_recording_evidence():
    _make_profile("retry_repeat")

    first = _start("retry_repeat").json()
    second = _start("retry_repeat").json()
    third = _start("retry_repeat").json()

    # Each start is a fresh session with its own reserved ordinal.
    assert len({first["assessment_id"], second["assessment_id"], third["assessment_id"]}) == 3

    # Starting alone never records a completed score, but reserves limited quota.
    assert [first["attempt"], second["attempt"], third["attempt"]] == [1, 2, 3]
    assert _stored_evidence("retry_repeat") == []
    fourth = _start("retry_repeat")
    assert fourth.status_code == 429, fourth.text
    assert "active" in fourth.json()["detail"].lower()


def test_only_a_completed_attempt_counts_and_starts_the_cooldown():
    _make_profile("retry_complete_once")

    session = _start("retry_complete_once").json()
    result = client.post(
        f"/api/assessment/{session['assessment_id']}/submit",
        json={
            "profile_id": "retry_complete_once",
            "answers": _correct_answers(session),
        },
    )

    assert result.status_code == 200
    assert result.json()["skill_score"] == 100.0

    evidence = _stored_evidence("retry_complete_once")

    assert len(evidence) == 1
    assert evidence[0]["attempt"] == 1

    # Only now does the cooldown apply.
    blocked = _start("retry_complete_once")

    assert blocked.status_code == 429
    assert blocked.json()["retry_after_seconds"] > 0


# ------------------------------------------------------------------
# 10. Isolation: per profile and per skill
# ------------------------------------------------------------------


def test_cooldown_is_isolated_per_profile():
    _completed_ago("retry_student_a", hours_ago=1)
    _make_profile("retry_student_b")

    assert _start("retry_student_a").status_code == 429
    assert _start("retry_student_b").status_code == 200


def test_cooldown_is_isolated_per_skill():
    _completed_ago("retry_per_skill", hours_ago=1, skill=SKILL)

    assert _start("retry_per_skill", skill=SKILL).status_code == 429
    assert _start("retry_per_skill", skill=OTHER_SKILL).status_code == 200


# ------------------------------------------------------------------
# Permanent attempt limit stays distinct from the temporary cooldown
# ------------------------------------------------------------------


def test_attempt_limit_is_terminal_and_carries_no_retry_timing(monkeypatch):
    """The limit is permanent, so it must not advertise a retry time.

    The original Phase 17 suite disabled the cooldown to reach the limit;
    the same approach is used here.
    """

    monkeypatch.setattr(assessment_service, "COOLDOWN_HOURS", 0)
    _make_profile("retry_limit")

    for _ in range(MAX_ATTEMPTS_PER_SKILL):
        session = _start("retry_limit").json()
        assert session["skill"] == SKILL
        result = client.post(
            f"/api/assessment/{session['assessment_id']}/submit",
            json={"profile_id": "retry_limit", "answers": _correct_answers(session)},
        )
        assert result.status_code == 200, result.text

    response = _start("retry_limit")

    assert response.status_code == 429

    body = response.json()

    assert body["detail"] == (
        f"Maximum attempts reached for {SKILL} "
        f"({MAX_ATTEMPTS_PER_SKILL} attempts allowed)."
    )
    # No retry timing: the UI must not render a countdown for a terminal state.
    assert "retry_after_seconds" not in body
    assert "next_allowed_at" not in body
    assert "Retry-After" not in response.headers


# ------------------------------------------------------------------
# 11. Existing mock test functionality still works
# ------------------------------------------------------------------


def test_full_mock_test_flow_still_works():
    _make_profile("retry_full_flow")

    session = _start("retry_full_flow", num_questions=5).json()
    answers = _correct_answers(session)

    result = client.post(
        f"/api/assessment/{session['assessment_id']}/submit",
        json={"profile_id": "retry_full_flow", "answers": answers},
    ).json()

    assert result["total"] == 5
    assert result["correct"] == 5
    assert result["skill_score"] == 100.0
    assert result["level"] == "Advanced"
    assert result["difficulty_breakdown"]

    history = client.get("/api/profile/retry_full_flow/assessments")

    assert history.status_code == 200
    assert len(history.json()["assessments"]) == 1
    assert history.json()["assessments"][0]["score"] == 100.0

    skills = client.get("/api/profile/retry_full_flow/skills")

    assert skills.status_code == 200
    assert any(
        entry["skill"] == SKILL and entry["assessment_score"] == 100.0
        for entry in skills.json()["skills"]
    )


def test_unknown_skill_is_still_rejected():
    _make_profile("retry_unknown_skill")

    assert _start("retry_unknown_skill", skill="Underwater Basket Weaving").status_code == 404
