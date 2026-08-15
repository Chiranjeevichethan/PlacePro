# ============================================================
# PLACEPRO - PHASE 15 - MODEL IMPROVEMENT TEST SUITE
# ============================================================
#
# Plain-python tests (no pytest/requests dependency):
#   python backend/tests/test_phase15_model.py
#
# Coverage (per Phase 15 spec):
#   1.  Phase 15 best model loads
#   2.  Prediction works through src.pipeline.predict_placement
#   3.  Probability is between 0 and 1
#   4.  Output format is correct (exact Phase 8 schema)
#   5-11. Existing Phase 8/9/10/11/12/13/14 regression (HTTP)
#   + GET /health
#
# NOTE: the Phase 15 best model (models/placepro_phase15_best_model.pkl)
# is an EVALUATION artifact. The production model
# (models/placepro_final_model.pkl) is NOT replaced by Phase 15.
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
_TMP_PROFILES = tempfile.mkdtemp(prefix="placepro_profiles_phase15_test_")
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

PHASE15_MODEL = os.path.join(PROJECT_ROOT, "models",
                             "placepro_phase15_best_model.pkl")
PHASE15_METADATA = os.path.join(PROJECT_ROOT, "models",
                                "placepro_phase15_metadata.json")
PROD_MODEL = os.path.join(PROJECT_ROOT, "models", "placepro_final_model.pkl")

SAMPLE_STUDENT = {
    "branch": "CSE", "college_tier": "Tier-1", "cgpa": 8.5,
    "backlogs": 0, "coding_skills": 8.2, "dsa_score": 8.0,
    "aptitude_score": 85.0, "communication_skills": 7.5,
    "ml_knowledge": 6.5, "system_design": 5.0, "internships": 2,
    "projects_count": 4, "certifications": 2, "hackathons": 1,
    "open_source_contributions": 1, "extracurriculars": 1,
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


def test_model_loads():
    print("[1] Phase 15 best model loads")
    check(os.path.exists(PHASE15_MODEL), "model file exists",
          PHASE15_MODEL)
    check(os.path.exists(PHASE15_METADATA), "metadata file exists",
          PHASE15_METADATA)
    if os.path.exists(PHASE15_MODEL):
        import joblib
        pipe = joblib.load(PHASE15_MODEL)
        check(hasattr(pipe, "predict") and hasattr(pipe, "predict_proba"),
              "pipeline has predict/predict_proba")
    if os.path.exists(PHASE15_METADATA):
        with open(PHASE15_METADATA, encoding="utf-8") as f:
            meta = json.load(f)
        check("test_metrics" in meta and "replaces_production_model" in meta,
              "metadata has test metrics + replacement flag")
        check(meta.get("replaces_production_model") is False,
              "production model NOT replaced (explicit)")
        check(os.path.exists(PROD_MODEL), "production model still exists")


def test_prediction_works():
    print("[2] Prediction works through predict_placement")
    if not os.path.exists(PHASE15_MODEL):
        check(False, "model file missing - cannot predict")
        return
    from src.pipeline import predict_placement
    result = predict_placement(SAMPLE_STUDENT,
                               model_path=PHASE15_MODEL)
    check(isinstance(result, dict), "returns a dict", repr(result))
    return result


def test_probability_range():
    print("[3] Probability between 0 and 1")
    if not os.path.exists(PHASE15_MODEL):
        check(False, "model file missing")
        return
    from src.pipeline import predict_placement
    result = predict_placement(SAMPLE_STUDENT, model_path=PHASE15_MODEL)
    p = result["placement_probability"]
    check(isinstance(p, (int, float)) and 0.0 <= p <= 1.0,
          "0 <= placement_probability <= 1", repr(p))


def test_output_format():
    print("[4] Output format is correct (Phase 8 schema)")
    if not os.path.exists(PHASE15_MODEL):
        check(False, "model file missing")
        return
    from src.pipeline import predict_placement
    result = predict_placement(SAMPLE_STUDENT, model_path=PHASE15_MODEL)
    expected_keys = {"placement_probability", "prediction", "confidence",
                     "model_version"}
    check(expected_keys <= set(result), "has all Phase 8 output keys",
          str(set(result)))
    check(result["prediction"] in ("PLACED", "NOT PLACED"),
          "prediction is PLACED/NOT PLACED", repr(result["prediction"]))
    check(0.0 <= result["confidence"] <= 1.0, "confidence in 0-1",
          repr(result["confidence"]))
    check(isinstance(result["model_version"], str), "model_version is str")
    # production model still serves the Phase 8 schema too
    from src.pipeline import predict_placement as pp
    prod = pp(SAMPLE_STUDENT)
    check(expected_keys <= set(prod), "production model schema unchanged")


def test_service_suite():
    print("=" * 60)
    print("SERVICE-LEVEL TESTS (PHASE 15 MODEL)")
    print("=" * 60)
    test_model_loads()
    test_prediction_works()
    test_probability_range()
    test_output_format()


# ------------------------------------------------------------
# HTTP-LEVEL TESTS (require a running server)
# ------------------------------------------------------------


def test_http_suite():
    print("\n" + "=" * 60)
    print("HTTP-LEVEL TESTS (PHASE 15 - REGRESSION)")
    print("=" * 60)

    status, body = http_get(f"{API_URL}/health")
    check(status == 200 and body.get("status") == "ok", "GET /health")

    # --- [5] Phase 8 prediction -----------------------------------
    status, body = http_post_json(f"{API_URL}/api/predict", SAMPLE_STUDENT)
    check(status == 200 and body.get("prediction") in ("PLACED", "NOT PLACED"),
          "[5] POST /api/predict still works", f"status={status}")

    # --- [6] Phase 9 resume extraction ------------------------------
    pdf = make_pdf(COMPLETE_RESUME.splitlines())
    status, body = multipart_post(
        f"{API_URL}/api/resume/upload", "file", "resume.pdf", pdf,
        "application/pdf",
    )
    check(status == 200 and body.get("success") is True,
          "[6] POST /api/resume/upload still works", f"status={status}")

    # --- [7] Phase 10 profile flow ----------------------------------
    status, body = multipart_post(
        f"{API_URL}/api/profile/from-resume", "file", "resume.pdf", pdf,
        "application/pdf",
    )
    check(status == 200 and body.get("profile", {}).get("profile_id"),
          "[7] from-resume still works", f"status={status}")
    profile = body["profile"]
    pid = profile["profile_id"]
    profile["ml_inputs"] = {
        "college_tier": "Tier-1", "backlogs": 0, "coding_skills": 7.5,
        "dsa_score": 7.0, "aptitude_score": 80.0,
        "communication_skills": 7.0, "ml_knowledge": 6.0,
        "system_design": 5.0, "open_source_contributions": 2,
        "extracurriculars": 1,
    }
    profile["skills"]["other_skills"] = ["Data Structures"]
    status, body = http_put_json(f"{API_URL}/api/profile/{pid}", profile)
    check(status == 200, "PUT profile still works", f"status={status}")
    status, body = http_post_json(f"{API_URL}/api/profile/verify",
                                  body["profile"])
    check(status == 200 and body["profile"]["verified"] is True,
          "verify profile still works", f"status={status}")

    # --- [8] Phase 11 prediction flow -------------------------------
    status, body = http_post_json(f"{API_URL}/api/profile/{pid}/predict", {})
    check(status == 200 and body["ready_for_prediction"] is True,
          "[8] Phase 11 prediction flow still works", f"status={status}")

    # --- [9] Phase 12 readiness -------------------------------------
    status, body = http_get(f"{API_URL}/api/profile/{pid}/readiness")
    check(status == 200 and 0 <= body["readiness_score"] <= 100,
          "[9] Phase 12 readiness still works", f"status={status}")

    # --- [10] Phase 13 eligibility -----------------------------------
    status, body = http_get(f"{API_URL}/api/profile/{pid}/eligibility")
    check(status == 200 and set(body) == {"eligible", "not_eligible",
                                          "incomplete"},
          "[10] Phase 13 eligibility still works", f"status={status}")

    # --- [11] Phase 14 recommendations --------------------------------
    status, body = http_get(f"{API_URL}/api/profile/{pid}/recommendations")
    check(status == 200 and "recommendations" in body,
          "[11] Phase 14 recommendations still work", f"status={status}")


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
