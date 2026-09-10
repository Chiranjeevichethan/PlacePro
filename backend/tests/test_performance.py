# ============================================================
# PLACEPRO - PHASE 27 - PERFORMANCE ANALYTICS TEST SUITE
# ============================================================
#
# Plain-python tests (no pytest/requests dependency):
#   python backend/tests/test_performance.py
#
# Service-level tests always run (profiles in a temp dir).
# HTTP tests run when a server is reachable at PLACEPRO_API_URL.
#
# Coverage (per Phase 27 spec):
#   1.  Performance endpoint with valid (verified) profile
#   2.  Unknown profile -> 404
#   3.  Invalid profile id -> 422
#   4.  Profile with no history (explicit None/0 summaries)
#   5.  Profile with prediction history (summary math)
#   6.  Profile with assessment history (summary math)
#   7.  Profile with both histories
#   8.  Readiness included correctly (delegated, not duplicated)
#   9.  Skills view included correctly
#  10.  Unverified profile -> 422
#  11.  No fabricated values (no invented progress/trend fields)
#  12.  Response schema validation (Pydantic)
#   + GET /health, GET /api/profile/{id}/performance
#
# NOTE ON SHARED TEMP STORES: the HTTP helpers are imported from
# test_readiness, whose module body also (re)points the store env
# vars at its own temp dir. That is the existing suite-wide
# behavior (all service tests share one isolated temp store); it
# keeps every run isolated from real data in data/profiles/.
#
# ============================================================

import os
import sys
import tempfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Isolate the stores (set BEFORE importing the services). The
# test_readiness import below re-points these to ITS temp dir -
# same isolation guarantee, one shared suite store.
_TMP_PROFILES = tempfile.mkdtemp(prefix="placepro_profiles_performance_test_")
_TMP_ASSESSMENTS = tempfile.mkdtemp(prefix="placepro_assessments_performance_test_")
os.environ["PLACEPRO_PROFILES_DIR"] = _TMP_PROFILES
os.environ["PLACEPRO_ASSESSMENTS_DIR"] = _TMP_ASSESSMENTS

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BACKEND_ROOT)
sys.path.insert(0, BACKEND_ROOT)
sys.path.insert(0, PROJECT_ROOT)

from backend.tests.test_resume import (  # noqa: E402
    COMPLETE_RESUME,
    make_pdf,
)
from backend.tests.test_readiness import (  # noqa: E402
    http_get,
    http_post_json,
    http_put_json,
    multipart_post,
)

API_URL = os.environ.get("PLACEPRO_API_URL", "http://127.0.0.1:8000")

COMPLETE_ML_INPUTS = {
    "college_tier": "Tier-1", "backlogs": 0, "coding_skills": 7.5,
    "dsa_score": 7.0, "aptitude_score": 80.0, "communication_skills": 7.0,
    "ml_knowledge": 6.0, "system_design": 5.0,
    "open_source_contributions": 2, "extracurriculars": 1,
}

ALL_CORE_SKILLS = [
    "Data Structures", "Algorithms", "DBMS", "Operating Systems",
    "Computer Networks", "OOP",
]


# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------


def _draft():
    """Draft profile from the COMPLETE_RESUME fixture (unverified)."""
    from app.services.profile_service import build_draft_from_resume

    pdf = make_pdf(COMPLETE_RESUME.splitlines())
    profile, _ = build_draft_from_resume("resume.pdf", pdf, "application/pdf")
    return profile


def _profile(verified=True, ml_inputs=None):
    """Verified profile with deterministic skills (same fixture
    approach as test_readiness)."""
    from app.services.profile_service import verify_profile

    profile = _draft()
    profile["skills"] = {
        "programming_languages": [], "frameworks": [], "databases": [],
        "cloud": [], "ai_ml": [], "web_technologies": [],
        "tools": [], "other_skills": [],
    }
    profile["skills"]["other_skills"] = (
        ALL_CORE_SKILLS + ["Python", "Git", "SQL", "Communication"]
    )
    if ml_inputs:
        profile["ml_inputs"] = dict(ml_inputs)
    if verified:
        profile, _ = verify_profile(profile)
    return profile


def _record_prediction(profile_id):
    """Append one prediction-history entry via the REAL service path.

    verify_profile/update_profile strip client-submitted history, so
    predict_for_profile() is the only honest way to create history.
    Requires a complete ml_inputs set.
    """
    from app.services.profile_service import predict_for_profile

    return predict_for_profile(profile_id)


def _run_assessment(profile_id, skill, correct_count):
    """Run one real assessment to completion with a controlled score.

    Scoring is difficulty-weighted (EASY 1 / MEDIUM 2 / HARD 3), so
    the expected score is computed from the served questions rather
    than assumed.
    """
    from app.services.assessment_service import (
        get_questions,
        start_assessment,
        submit_assessment,
    )
    from app.services.question_bank import DIFFICULTY_POINTS

    session = start_assessment(profile_id, skill)
    bank = {q["id"]: q["correct_answer"] for q in get_questions(skill)}
    answers = {}
    for i, q in enumerate(session["questions"]):
        answers[q["question_id"]] = (
            bank[q["question_id"]] if i < correct_count else "DEFINITELY WRONG"
        )

    total_pts = sum(
        DIFFICULTY_POINTS[q["difficulty"]] for q in session["questions"]
    )
    earned_pts = sum(
        DIFFICULTY_POINTS[q["difficulty"]]
        for q in session["questions"][:correct_count]
    )
    expected = round(earned_pts / total_pts * 100, 1)

    result = submit_assessment(session["assessment_id"], profile_id, answers)
    return result, expected


PASS = 0
FAIL = 0


def check(condition, label, extra=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {label}")
    else:
        FAIL += 1
        print(f"  ❌ {label} {extra}")


# ------------------------------------------------------------
# SERVICE-LEVEL TESTS
# ------------------------------------------------------------


def test_verified_profile_with_no_history():
    print("[1] Verified profile, no history at all")
    from app.services.performance_service import get_performance

    profile = _profile(ml_inputs=COMPLETE_ML_INPUTS)
    r = get_performance(profile["profile_id"])

    check(r["profile_id"] == profile["profile_id"], "profile_id echoed")
    check(r["verified"] is True, "verified is True")
    check(r["summary"]["predictions"]["predictions_count"] == 0,
          "predictions_count 0", str(r["summary"]["predictions"]))
    check(r["summary"]["predictions"]["latest_probability"] is None,
          "latest_probability None (not 0, not fabricated)")
    check(r["summary"]["predictions"]["highest_probability"] is None,
          "highest_probability None")
    check(r["summary"]["assessments"]["assessments_count"] == 0,
          "assessments_count 0")
    check(r["summary"]["assessments"]["average_score"] is None,
          "average_score None")
    check(r["prediction_history"] == [], "prediction_history empty list")
    check(r["assessment_history"] == [], "assessment_history empty list")
    # Raw service value may be float (Phase 17 bonus arithmetic);
    # the API schema (ReadinessResponse/PerformanceResponse) declares
    # int and coerces - assert the contract, not the internal dtype.
    check(0 <= r["summary"]["readiness_score"] <= 100, "readiness in 0-100",
          str(r["summary"]["readiness_score"]))
    from app.schemas_performance import PerformanceResponse as _PR
    _m = _PR(**r)
    check(isinstance(_m.summary.readiness_score, int),
          "schema-validated readiness_score is int",
          str(type(_m.summary.readiness_score)))
    check(len(r["skills"]) > 0, "skills view populated",
          str(len(r["skills"])))
    check(r["summary"]["skills_tracked"] == len(r["skills"]),
          "skills_tracked matches skills list")


def test_unknown_profile():
    print("[2] Unknown profile")
    from app.services.performance_service import get_performance
    from app.services.profile_service import ProfileNotFoundError

    try:
        get_performance("no-such-profile-id")
        check(False, "unknown profile rejected")
    except ProfileNotFoundError:
        check(True, "unknown profile -> ProfileNotFoundError (404)")


def test_invalid_profile_id():
    print("[3] Invalid profile id characters")
    from app.services.performance_service import get_performance
    from app.services.profile_service import InvalidProfileError

    try:
        get_performance("bad id!")
        check(False, "invalid id rejected")
    except InvalidProfileError:
        check(True, "invalid id -> InvalidProfileError (422)")


def test_unverified_profile():
    print("[4] Unverified profile -> 422 convention")
    from app.services.performance_service import (
        PerformanceServiceError,
        get_performance,
    )

    profile = _profile(verified=False)
    try:
        get_performance(profile["profile_id"])
        check(False, "unverified profile rejected")
    except PerformanceServiceError:
        check(True, "unverified profile -> PerformanceServiceError (422)")


def test_prediction_history_summary():
    print("[5] Prediction history summarized (real service path)")
    from app.services.performance_service import get_performance

    profile = _profile(ml_inputs=COMPLETE_ML_INPUTS)
    pid = profile["profile_id"]

    r1 = _record_prediction(pid)
    check(r1["ready_for_prediction"] is True, "prediction 1 recorded")
    r2 = _record_prediction(pid)
    check(r2["ready_for_prediction"] is True, "prediction 2 recorded")

    r = get_performance(pid)
    p = r["summary"]["predictions"]
    check(p["predictions_count"] == 2, "predictions_count == 2",
          str(p["predictions_count"]))
    check(p["latest_probability"] == r2["placement_probability"],
          "latest_probability == latest prediction")
    check(p["latest_prediction"] == r2["prediction"],
          "latest_prediction == latest prediction")
    check(p["highest_probability"] == max(
        r1["placement_probability"], r2["placement_probability"]),
        "highest_probability correct")
    check(p["lowest_probability"] == min(
        r1["placement_probability"], r2["placement_probability"]),
        "lowest_probability correct")
    check(len(r["prediction_history"]) == 2, "history has 2 entries")
    check(all(set(e) == {"timestamp", "model_version",
                         "placement_probability", "prediction"}
              for e in r["prediction_history"]),
          "history entries match PredictionHistoryEntry fields")


def test_assessment_history_summary():
    print("[6] Assessment history summarized (real service path)")
    from app.services.performance_service import get_performance

    profile = _profile(ml_inputs=COMPLETE_ML_INPUTS)
    pid = profile["profile_id"]

    sub, expected = _run_assessment(pid, "Python", correct_count=7)
    check(sub["skill_score"] == expected,
          f"weighted score == computed expectation ({expected})",
          str(sub["skill_score"]))

    r = get_performance(pid)
    a = r["summary"]["assessments"]
    check(a["assessments_count"] == 1, "assessments_count == 1",
          str(a["assessments_count"]))
    check(a["skills_assessed"] == 1, "skills_assessed == 1")
    check(a["average_score"] == expected,
          "average_score == the single attempt score",
          str(a["average_score"]))
    check(a["latest_skill"] == "Python", "latest_skill Python")
    check(a["latest_score"] == expected, "latest_score matches")
    check(a["latest_level"] == sub["level"], "latest_level matches report")
    check(len(r["assessment_history"]) == 1, "history has 1 entry")
    entry = r["assessment_history"][0]
    check(entry["verified"] is True and entry["source"] == "assessment",
          "evidence marked verified/assessment")
    check(a["latest_timestamp"] == entry["timestamp"],
          "latest_timestamp matches evidence")


def test_combined_histories_and_readiness():
    print("[7] Both histories + readiness delegation")
    from app.services.performance_service import get_performance
    from app.services.readiness_service import get_readiness

    profile = _profile(ml_inputs=COMPLETE_ML_INPUTS)
    pid = profile["profile_id"]

    _record_prediction(pid)
    _run_assessment(pid, "SQL", correct_count=10)

    r = get_performance(pid)
    check(r["summary"]["predictions"]["predictions_count"] == 1,
          "1 prediction")
    check(r["summary"]["assessments"]["assessments_count"] == 1,
          "1 assessment")

    # Readiness is delegated, not recomputed: identical to the
    # dedicated Phase 12 endpoint's output.
    standalone = get_readiness(pid)
    check(r["readiness"] == standalone,
          "readiness section == get_readiness() output")
    check(r["summary"]["readiness_score"] == standalone["readiness_score"],
          "summary readiness_score matches readiness section")
    check(r["summary"]["readiness_level"] == standalone["readiness_level"],
          "summary readiness_level matches readiness section")
    # Fixture meets every core requirement -> technical component is
    # at its cap; assessment evidence must not corrupt it.
    check(standalone["readiness_breakdown"]["technical_skills"] == 30,
          "technical_skills at documented cap (30)",
          str(standalone["readiness_breakdown"]))


def test_no_fabricated_progress():
    print("[8] No fabricated skill progress")
    from app.services.performance_service import get_performance

    profile = _profile(ml_inputs=COMPLETE_ML_INPUTS)
    r = get_performance(profile["profile_id"])

    # Skills view carries only real flags/scores: a skill with no
    # assessment must not claim a verified score.
    for entry in r["skills"]:
        if entry["assessment_score"] is None:
            check(entry["assessment_verified"] is False,
                  f"{entry['skill']}: no score -> not 'verified'")
    # No time-series skill fields exist anywhere in the response.
    keys = set(r.keys()) | set(r["summary"].keys())
    check(not any("progress" in k or "trend" in k for k in keys),
          "no invented progress/trend fields", str(sorted(keys)))


def test_schema_validation():
    print("[9] Pydantic response schema validation")
    from app.schemas_performance import PerformanceResponse
    from app.services.performance_service import get_performance

    profile = _profile(ml_inputs=COMPLETE_ML_INPUTS)
    pid = profile["profile_id"]
    _record_prediction(pid)
    _run_assessment(pid, "Python", correct_count=5)

    raw = get_performance(pid)
    model = PerformanceResponse(**raw)
    check(model.profile_id == pid, "PerformanceResponse validates")
    check(len(model.prediction_history) == 1, "typed history list")
    check(len(model.assessment_history) == 1, "typed evidence list")
    check(model.summary.predictions.predictions_count == 1,
          "typed summary nesting")
    check(model.readiness.profile_id == pid, "nested ReadinessResponse")
    check(model.skills[0].skill and isinstance(model.skills[0].skill, str),
          "typed SkillViewEntry list")


def test_service_suite():
    print("=" * 60)
    print("SERVICE-LEVEL TESTS (PHASE 27)")
    print("=" * 60)
    test_verified_profile_with_no_history()
    test_unknown_profile()
    test_invalid_profile_id()
    test_unverified_profile()
    test_prediction_history_summary()
    test_assessment_history_summary()
    test_combined_histories_and_readiness()
    test_no_fabricated_progress()
    test_schema_validation()


# ------------------------------------------------------------
# HTTP-LEVEL TESTS (require a running server)
# ------------------------------------------------------------


def _http_verified_complete_profile():
    """Create a verified complete profile via the API."""
    pdf = make_pdf(COMPLETE_RESUME.splitlines())
    status, body = multipart_post(
        f"{API_URL}/api/profile/from-resume", "file", "resume.pdf", pdf,
        "application/pdf",
    )
    assert status == 200, f"from-resume failed: {status} {body}"
    profile = body["profile"]
    pid = profile["profile_id"]
    profile["ml_inputs"] = dict(COMPLETE_ML_INPUTS)
    status, body = http_put_json(f"{API_URL}/api/profile/{pid}", profile)
    assert status == 200, f"PUT failed: {status} {body}"
    status, body = http_post_json(f"{API_URL}/api/profile/verify",
                                  body["profile"])
    assert status == 200 and body["profile"]["verified"], "verify failed"
    return pid


def test_http_suite():
    print("\n" + "=" * 60)
    print("HTTP-LEVEL TESTS (PHASE 27)")
    print("=" * 60)

    # --- /health ---------------------------------------------------
    status, body = http_get(f"{API_URL}/health")
    check(status == 200 and body.get("status") == "ok", "GET /health")

    # --- [10] valid profile, no history yet ------------------------
    pid = _http_verified_complete_profile()
    status, body = http_get(f"{API_URL}/api/profile/{pid}/performance")
    check(status == 200, "GET performance (valid profile)",
          f"status={status}")
    check(body.get("profile_id") == pid, "profile_id echoed")
    check(body["summary"]["predictions"]["predictions_count"] == 0,
          "no predictions yet -> count 0")
    check(body["summary"]["predictions"]["latest_probability"] is None,
          "no predictions yet -> latest None")

    # --- [11] prediction history flows into the endpoint -----------
    status, body2 = http_post_json(
        f"{API_URL}/api/profile/{pid}/predict", {})
    check(status == 200 and body2.get("ready_for_prediction") is True,
          "profile predict recorded", f"status={status}")
    status, body = http_get(f"{API_URL}/api/profile/{pid}/performance")
    check(body["summary"]["predictions"]["predictions_count"] == 1,
          "prediction reflected in performance")
    check(body["summary"]["predictions"]["latest_probability"]
          == body2["placement_probability"],
          "latest_probability matches the prediction")

    # --- [12] unverified -> 422 ------------------------------------
    pdf = make_pdf(COMPLETE_RESUME.splitlines())
    status, body3 = multipart_post(
        f"{API_URL}/api/profile/from-resume", "file", "resume.pdf", pdf,
        "application/pdf",
    )
    draft_pid = body3["profile"]["profile_id"]
    status, _ = http_get(f"{API_URL}/api/profile/{draft_pid}/performance")
    check(status == 422, "unverified -> 422", f"status={status}")

    # --- [13] unknown -> 404, invalid -> 422 -----------------------
    status, _ = http_get(f"{API_URL}/api/profile/no-such-id/performance")
    check(status == 404, "unknown profile -> 404", f"status={status}")
    status, _ = http_get(
        f"{API_URL}/api/profile/invalid%20id%21/performance")
    check(status == 422, "invalid id -> 422", f"status={status}")


# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------

if __name__ == "__main__":
    test_service_suite()

    server_up = False
    try:
        status, _ = http_get(f"{API_URL}/health")
        server_up = status == 200
    except AssertionError:
        server_up = False

    if server_up:
        test_http_suite()
    else:
        print(f"\n⚠️  Server not reachable at {API_URL} - skipping HTTP tests.")
        print("   Start it with:  uvicorn backend.app.main:app --reload")

    print(f"\n{'=' * 60}")
    print(f"RESULT: {PASS} passed, {FAIL} failed")
    print("=" * 60)
    sys.exit(1 if FAIL else 0)
