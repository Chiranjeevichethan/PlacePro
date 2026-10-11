# ============================================================
# PLACEPRO - PHASE 8 - PREDICTION API SMOKE TEST
# ============================================================
#
# Plain-python test (no pytest / httpx required):
#   python backend/tests/test_predict.py
#
# 1. Service-level: predict a sample student, validate schema.
# 2. HTTP-level: POST to a running server (skips gracefully if
#    the server is not up) and validate the JSON contract.
#
# ============================================================

import json
import os
import sys
import urllib.error
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Make backend/ (for `app.*`) and project root (for `src.*`) importable
BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BACKEND_ROOT)
sys.path.insert(0, BACKEND_ROOT)
sys.path.insert(0, PROJECT_ROOT)

SAMPLE_STUDENT = {
    "branch": "CSE",
    "college_tier": "Tier-1",
    "cgpa": 8.5,
    "backlogs": 0,
    "coding_skills": 8.2,
    "dsa_score": 8.0,
    "aptitude_score": 85.0,
    "communication_skills": 7.5,
    "ml_knowledge": 6.5,
    "system_design": 5.0,
    "internships": 2,
    "projects_count": 4,
    "certifications": 2,
    "hackathons": 1,
    "open_source_contributions": 1,
    "extracurriculars": 1,
}

API_URL = os.environ.get("PLACEPRO_API_URL", "http://127.0.0.1:8000")


def validate_response(result, label):
    """Assert the Phase 8 output contract."""
    assert isinstance(result, dict), f"{label}: expected dict"
    for key in ("placement_probability", "prediction", "confidence"):
        assert key in result, f"{label}: missing key {key!r} -> {result}"
    p = result["placement_probability"]
    conf = result["confidence"]
    assert isinstance(p, (int, float)) and 0.0 <= p <= 1.0, \
        f"{label}: placement_probability out of range -> {p}"
    assert result["prediction"] in ("PLACED", "NOT PLACED"), \
        f"{label}: bad prediction -> {result['prediction']}"
    assert isinstance(conf, (int, float)) and 0.0 <= conf <= 1.0, \
        f"{label}: confidence out of range -> {conf}"
    # Consistency: prediction label must agree with the 0.50 threshold
    expected = "PLACED" if p >= 0.50 else "NOT PLACED"
    assert result["prediction"] == expected, \
        f"{label}: prediction {result['prediction']} inconsistent with p={p}"
    print(f"  ✅ {label}: {result['prediction']} "
          f"(p={p:.4f}, confidence={conf:.4f})")


def test_service():
    print("[1/2] Service-level prediction...")
    from app.services.prediction_service import predict
    result = predict(dict(SAMPLE_STUDENT))
    validate_response(result, "service")
    return result


def test_http():
    print(f"[2/2] HTTP POST {API_URL}/api/predict ...")
    body = json.dumps(SAMPLE_STUDENT).encode("utf-8")
    req = urllib.request.Request(
        f"{API_URL}/api/predict",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        print(f"  ⚠️  Server not reachable ({exc.reason}) - "
              "skipping HTTP test. Start it with:")
        print("     uvicorn backend.app.main:app --reload")
        return None
    validate_response(payload, "http")
    return payload


if __name__ == "__main__":
    failures = 0
    try:
        test_service()
    except Exception as exc:
        failures += 1
        print(f"  ❌ service test failed: {exc}")
    try:
        test_http()
    except Exception as exc:
        failures += 1
        print(f"  ❌ http test failed: {exc}")

    if failures:
        print(f"\n{failures} test(s) FAILED")
        sys.exit(1)
    print("\nAll smoke tests passed ✅")
