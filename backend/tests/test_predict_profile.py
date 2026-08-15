# ============================================================
# PLACEPRO - PHASE 11 - PROFILE PREDICTION TEST SUITE
# ============================================================
#
# Plain-python tests (no pytest/requests dependency):
#   python backend/tests/test_predict_profile.py
#
# Service-level tests always run (profiles in a temp dir).
# HTTP tests run when a server is reachable at PLACEPRO_API_URL.
#
# Coverage (per Phase 11 spec):
#   1.  Unverified profile -> prediction rejected
#   2.  Verified incomplete profile -> missing fields returned
#   3.  Verified complete profile -> prediction succeeds
#   4.  Probability between 0 and 1
#   5.  Prediction is PLACED or NOT PLACED
#   6.  Model version returned
#   7.  Prediction history recorded
#   8.  Multiple predictions -> multiple history entries
#   9.  Invalid profile ID
#  10.  Existing /api/predict still works
#  11.  Existing /api/resume/upload still works
#  12.  Existing Phase 10 profile endpoints still work
#   + GET /health
#
# ============================================================

import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
import uuid

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Isolate the profile store (set BEFORE importing the service)
_TMP_PROFILES = tempfile.mkdtemp(prefix="placepro_profiles_predict_test_")
os.environ["PLACEPRO_PROFILES_DIR"] = _TMP_PROFILES

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BACKEND_ROOT)
sys.path.insert(0, BACKEND_ROOT)
sys.path.insert(0, PROJECT_ROOT)

from backend.tests.test_resume import (  # noqa: E402
    COMPLETE_RESUME,
    make_pdf,
)

API_URL = os.environ.get("PLACEPRO_API_URL", "http://127.0.0.1:8000")
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

COMPLETE_ML_INPUTS = {
    "college_tier": "Tier-1", "backlogs": 0, "coding_skills": 7.5,
    "dsa_score": 7.0, "aptitude_score": 80.0, "communication_skills": 7.0,
    "ml_knowledge": 6.0, "system_design": 5.0,
    "open_source_contributions": 2, "extracurriculars": 1,
}

# ------------------------------------------------------------
# HTTP HELPERS
# ------------------------------------------------------------


def multipart_post(url, field_name, filename, content, content_type):
    boundary = "----PlaceProBoundary" + uuid.uuid4().hex
    body = b""
    body += f"--{boundary}\r\n".encode()
    body += (f'Content-Disposition: form-data; name="{field_name}"; '
             f'filename="{filename}"\r\n').encode()
    body += f"Content-Type: {content_type}\r\n\r\n".encode()
    body += content + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def http_get(url):
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise AssertionError(f"Server not reachable: {exc.reason}")


def http_post_json(url, payload):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def http_put_json(url, payload):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="PUT",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


# ------------------------------------------------------------
# SERVICE-LEVEL TESTS
# ------------------------------------------------------------

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


def _draft():
    from app.services.profile_service import build_draft_from_resume
    pdf = make_pdf(COMPLETE_RESUME.splitlines())
    profile, _ = build_draft_from_resume("resume.pdf", pdf, "application/pdf")
    return profile


def _verified_complete():
    from app.services.profile_service import verify_profile
    profile = _draft()
    profile["ml_inputs"] = dict(COMPLETE_ML_INPUTS)
    verified, completion = verify_profile(profile)
    assert completion["profile_complete"], "setup: profile should be complete"
    return verified


def test_unverified_rejected():
    print("[1] Unverified profile -> prediction rejected")
    from app.services.profile_service import predict_for_profile
    draft = _draft()
    result = predict_for_profile(draft["profile_id"])
    check(result["ready_for_prediction"] is False, "ready_for_prediction False")
    check("verified" in (result.get("reason") or "").lower(),
          "reason mentions verification", repr(result.get("reason")))


def test_verified_incomplete():
    print("[2] Verified incomplete profile -> missing fields returned")
    from app.services.profile_service import predict_for_profile, verify_profile
    profile = verify_profile(_draft())[0]
    result = predict_for_profile(profile["profile_id"])
    check(result["ready_for_prediction"] is False, "ready_for_prediction False")
    check("aptitude_score" in result["missing_fields"],
          "missing aptitude_score", str(result["missing_fields"]))
    check("coding_skills" in result["missing_fields"], "missing coding_skills")
    check("dsa_score" in result["missing_fields"], "missing dsa_score")
    check(result["prediction"] is None, "no prediction returned")


def test_verified_complete():
    print("[3] Verified complete profile -> prediction succeeds")
    from app.services.profile_service import predict_for_profile
    profile = _verified_complete()
    result = predict_for_profile(profile["profile_id"])
    check(result["ready_for_prediction"] is True, "ready_for_prediction True")
    check(result["prediction"] in ("PLACED", "NOT PLACED"),
          "prediction label", repr(result["prediction"]))
    return result


def test_probability_range():
    print("[4] Probability between 0 and 1")
    from app.services.profile_service import predict_for_profile
    result = predict_for_profile(_verified_complete()["profile_id"])
    p = result["placement_probability"]
    check(isinstance(p, (int, float)) and 0.0 <= p <= 1.0,
          "0 <= placement_probability <= 1", repr(p))


def test_prediction_label():
    print("[5] Prediction is PLACED or NOT PLACED")
    from app.services.profile_service import predict_for_profile
    result = predict_for_profile(_verified_complete()["profile_id"])
    check(result["prediction"] in ("PLACED", "NOT PLACED"), "valid label",
          repr(result["prediction"]))


def test_model_version():
    print("[6] Model version returned")
    from app.services.profile_service import predict_for_profile
    result = predict_for_profile(_verified_complete()["profile_id"])
    check(result.get("model_version") == "placepro-final-v1",
          "model_version returned", repr(result.get("model_version")))


def test_history_recorded():
    print("[7] Prediction history recorded")
    from app.services.profile_service import get_profile, predict_for_profile
    pid = _verified_complete()["profile_id"]
    result = predict_for_profile(pid)
    check(len(result["prediction_history"]) == 1, "1 history entry")
    entry = result["prediction_history"][0]
    for key in ("timestamp", "model_version", "placement_probability", "prediction"):
        check(key in entry, f"entry has {key}", str(entry))
    check(entry["model_version"] == "placepro-final-v1", "entry model_version")
    check(entry["prediction"] == result["prediction"], "entry prediction matches")
    # persisted on the profile
    stored, _ = get_profile(pid)
    check(len(stored["prediction_history"]) == 1, "history persisted on profile")


def test_multiple_predictions():
    print("[8] Multiple predictions -> multiple history entries")
    from app.services.profile_service import get_profile, predict_for_profile
    pid = _verified_complete()["profile_id"]
    predict_for_profile(pid)
    predict_for_profile(pid)
    stored, _ = get_profile(pid)
    check(len(stored["prediction_history"]) == 2, "2 history entries",
          str(len(stored["prediction_history"])))
    # timestamps differ (entries are appended, not replaced)
    check(stored["prediction_history"][0]["timestamp"] !=
          stored["prediction_history"][1]["timestamp"], "distinct timestamps")


def test_invalid_profile_id():
    print("[9] Invalid profile ID")
    from app.services.profile_service import (
        InvalidProfileError,
        ProfileNotFoundError,
        predict_for_profile,
    )
    try:
        predict_for_profile("no-such-profile")
        check(False, "unknown id rejected")
    except ProfileNotFoundError:
        check(True, "unknown id -> 404")
    try:
        predict_for_profile("../../etc/passwd")
        check(False, "path traversal rejected")
    except InvalidProfileError:
        check(True, "path traversal rejected")


def test_service_suite():
    print("=" * 60)
    print("SERVICE-LEVEL TESTS")
    print("=" * 60)
    test_unverified_rejected()
    test_verified_incomplete()
    test_verified_complete()
    test_probability_range()
    test_prediction_label()
    test_model_version()
    test_history_recorded()
    test_multiple_predictions()
    test_invalid_profile_id()


# ------------------------------------------------------------
# HTTP-LEVEL TESTS (require a running server)
# ------------------------------------------------------------


def test_http_suite():
    print("\n" + "=" * 60)
    print("HTTP-LEVEL TESTS")
    print("=" * 60)

    # --- /health ---------------------------------------------------
    status, body = http_get(f"{API_URL}/health")
    check(status == 200 and body.get("status") == "ok", "GET /health")

    # --- [10] /api/predict still works ------------------------------
    payload = {
        "branch": "CSE", "college_tier": "Tier-1", "cgpa": 8.5,
        "backlogs": 0, "coding_skills": 8.2, "dsa_score": 8.0,
        "aptitude_score": 85.0, "communication_skills": 7.5,
        "ml_knowledge": 6.5, "system_design": 5.0, "internships": 2,
        "projects_count": 4, "certifications": 2, "hackathons": 1,
        "open_source_contributions": 1, "extracurriculars": 1,
    }
    status, body = http_post_json(f"{API_URL}/api/predict", payload)
    check(status == 200 and body.get("prediction") in ("PLACED", "NOT PLACED"),
          "[10] POST /api/predict still works", f"status={status}")

    # --- [11] /api/resume/upload still works -------------------------
    pdf = make_pdf(COMPLETE_RESUME.splitlines())
    status, body = multipart_post(
        f"{API_URL}/api/resume/upload", "file", "resume.pdf", pdf,
        "application/pdf",
    )
    check(status == 200 and body.get("success") is True,
          "[11] POST /api/resume/upload still works", f"status={status}")

    # --- [12] Phase 10 profile endpoints still work ------------------
    status, body = multipart_post(
        f"{API_URL}/api/profile/from-resume", "file", "resume.pdf", pdf,
        "application/pdf",
    )
    check(status == 200 and body.get("profile", {}).get("profile_id"),
          "[12] from-resume still works", f"status={status}")
    if status != 200:
        return
    profile = body["profile"]
    pid = profile["profile_id"]
    profile["ml_inputs"] = dict(COMPLETE_ML_INPUTS)
    status, body = http_put_json(f"{API_URL}/api/profile/{pid}", profile)
    check(status == 200, "PUT profile still works", f"status={status}")
    status, body = http_post_json(f"{API_URL}/api/profile/verify", body["profile"])
    check(status == 200 and body["profile"]["verified"] is True,
          "verify profile still works", f"status={status}")
    status, body = http_get(f"{API_URL}/api/profile/{pid}")
    check(status == 200, "GET profile still works", f"status={status}")

    # --- New endpoint: unverified -> rejected -------------------------
    status2, body2 = multipart_post(
        f"{API_URL}/api/profile/from-resume", "file", "resume.pdf", pdf,
        "application/pdf",
    )
    pid2 = body2["profile"]["profile_id"]
    status2, body2 = http_post_json(f"{API_URL}/api/profile/{pid2}/predict", {})
    check(status2 == 200 and body2["ready_for_prediction"] is False and
          "verified" in body2.get("reason", ""),
          "unverified profile rejected via HTTP", f"status={status2} {body2}")

    # --- New endpoint: verified complete -> prediction -----------------
    status, body = http_post_json(f"{API_URL}/api/profile/{pid}/predict", {})
    check(status == 200 and body["ready_for_prediction"] is True,
          "verified complete profile predicts via HTTP", f"status={status}")
    if status == 200:
        check(0.0 <= body["placement_probability"] <= 1.0, "probability in range")
        check(body["prediction"] in ("PLACED", "NOT PLACED"), "valid label")
        check(body["model_version"] == "placepro-final-v1", "model version")
        check(len(body["prediction_history"]) >= 1, "history returned")

    # --- New endpoint: unknown id -> 404 --------------------------------
    status, _ = http_post_json(f"{API_URL}/api/profile/nope/predict", {})
    check(status == 404, "unknown profile id -> 404", f"status={status}")


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
