# ============================================================
# PLACEPRO - PHASE 10 - PROFILE TEST SUITE
# ============================================================
#
# Plain-python tests (no pytest/requests dependency):
#   python backend/tests/test_profile.py
#
# Service-level tests always run (profiles stored in a temp dir).
# HTTP tests run when a server is reachable at PLACEPRO_API_URL
# (default http://127.0.0.1:8000).
#
# Coverage (per Phase 10 spec):
#   1. Complete resume
#   2. Resume missing CGPA
#   3. Resume missing internship
#   4. Resume with multiple projects
#   5. Resume with multiple skills
#   6. Manual edits
#   7. Profile verification
#   8. Missing ML-required fields
#   9. Invalid profile
#  10. Existing /api/predict still works
#  11. Existing /api/resume/upload still works
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

# Isolate the profile store from the repo (set BEFORE importing the service)
_TMP_PROFILES = tempfile.mkdtemp(prefix="placepro_profiles_test_")
os.environ["PLACEPRO_PROFILES_DIR"] = _TMP_PROFILES

# Make backend/ (app.*) and project root (src.*) importable
BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BACKEND_ROOT)
sys.path.insert(0, BACKEND_ROOT)
sys.path.insert(0, PROJECT_ROOT)

from backend.tests.test_resume import (  # noqa: E402
    COMPLETE_RESUME,
    MISSING_INFO_RESUME,
    MULTIPLE_INTERNSHIPS_RESUME,
    MULTIPLE_PROJECTS_RESUME,
    make_docx,
    make_pdf,
)

API_URL = os.environ.get("PLACEPRO_API_URL", "http://127.0.0.1:8000")
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

# ------------------------------------------------------------
# HTTP HELPERS (same style as test_resume.py)
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


def make_profile_from_text(text, filename="resume.pdf"):
    from app.services.profile_service import build_draft_from_resume
    content = make_pdf(text.splitlines())
    profile, completion = build_draft_from_resume(filename, content, "application/pdf")
    return profile, completion


def test_complete_resume():
    print("[1] Complete resume -> draft profile")
    profile, completion = make_profile_from_text(COMPLETE_RESUME)
    check(profile["verified"] is False, "draft is not verified")
    check(profile["personal"]["name"] == "John Doe", "name extracted")
    check(profile["personal"]["email"] == "john.doe@gmail.com", "email extracted")
    check(profile["education"]["cgpa"] == 8.2, "cgpa extracted")
    check(len(profile["provenance"]["resume"]) > 0, "provenance.resume populated",
          str(len(profile["provenance"]["resume"])))
    check(profile["provenance"]["user"] == [], "provenance.user empty for draft")
    mapping = completion["ml_feature_mapping"]
    check(mapping["branch"] == "CSE", "branch mapped CSE", repr(mapping["branch"]))
    check(mapping["cgpa"] == 8.2, "cgpa mapped", repr(mapping["cgpa"]))
    check(mapping["internships"] == 1, "internships count 1", repr(mapping["internships"]))
    check(mapping["projects_count"] == 2, "projects count 2", repr(mapping["projects_count"]))
    check(mapping["certifications"] == 1, "certifications count 1")
    check(mapping["hackathons"] == 1, "hackathons count 1")
    check(mapping["aptitude_score"] is None,
          "aptitude_score NOT invented (None)", repr(mapping["aptitude_score"]))
    return profile, completion


def test_missing_cgpa():
    print("[2] Resume missing CGPA")
    profile, completion = make_profile_from_text(MISSING_INFO_RESUME)
    check(profile["education"]["cgpa"] is None, "cgpa is None (not invented)")
    check("cgpa" in completion["missing_fields"], "cgpa in missing_fields")
    check(completion["ml_feature_mapping"]["cgpa"] is None, "mapping cgpa None")


def test_missing_internship():
    print("[3] Resume missing internship")
    profile, completion = make_profile_from_text(MISSING_INFO_RESUME)
    check(profile["internships"] == [], "internships []")
    check(completion["ml_feature_mapping"]["internships"] == 0,
          "internships mapped to 0 (empty confirmed list)")
    check(profile["experience"] == [], "experience []")


def test_multiple_projects():
    print("[4] Resume with multiple projects")
    profile, completion = make_profile_from_text(MULTIPLE_PROJECTS_RESUME)
    check(len(profile["projects"]) == 3, "3 projects extracted",
          str(len(profile["projects"])))
    check(completion["ml_feature_mapping"]["projects_count"] == 3,
          "projects_count mapped to 3")


def test_multiple_skills():
    print("[5] Resume with multiple skills")
    profile, completion = make_profile_from_text(COMPLETE_RESUME)
    skills = profile["skills"]
    total = sum(len(v) for v in skills.values())
    check(total >= 8, "8+ skills across categories", str(total))
    check("Python" in skills["programming_languages"], "Python present")
    check("React" in skills["frameworks"], "React present")
    check("TensorFlow" in skills["ai_ml"], "TensorFlow present")
    # Never converted into a score
    check(completion["ml_feature_mapping"]["coding_skills"] is None,
          "skills NOT converted to coding_skill_score")


def test_manual_edits():
    print("[6] Manual edits via PUT")
    from app.services.profile_service import get_profile, update_profile
    profile, _ = make_profile_from_text(COMPLETE_RESUME)
    pid = profile["profile_id"]
    profile["personal"]["name"] = "John Updated"
    profile["education"]["cgpa"] = 9.1
    profile["ml_inputs"] = {"aptitude_score": 85.0}
    updated, completion = update_profile(pid, profile)
    check(updated["verified"] is False, "verified reset to False after edit")
    check(updated["personal"]["name"] == "John Updated", "name edit applied")
    check(updated["education"]["cgpa"] == 9.1, "cgpa edit applied")
    check("personal.name" in updated["provenance"]["user"], "name in provenance.user",
          str(updated["provenance"]["user"]))
    check("education.cgpa" in updated["provenance"]["user"], "cgpa in provenance.user")
    check("ml_inputs.aptitude_score" in updated["provenance"]["user"],
          "ml_inputs in provenance.user")
    check(completion["ml_feature_mapping"]["cgpa"] == 9.1, "mapping uses edited cgpa")
    # fetched state persists
    loaded, _ = get_profile(pid)
    check(loaded["personal"]["name"] == "John Updated", "edit persisted")
    return updated


def test_verification():
    print("[7] Profile verification")
    from app.services.profile_service import InvalidProfileError, verify_profile
    profile, _ = make_profile_from_text(COMPLETE_RESUME)
    # name/email are already there - verify should succeed
    verified, completion = verify_profile(profile)
    check(verified["verified"] is True, "verified True after confirmation")
    check(verified["profile_id"] == profile["profile_id"], "same profile_id")
    check(completion["profile_complete"] is False,
          "not complete yet (manual inputs missing)")
    # Missing email must be rejected
    bad = dict(profile)
    bad["personal"] = dict(profile["personal"])
    bad["personal"]["email"] = None
    try:
        verify_profile(bad)
        check(False, "verify without email rejected")
    except InvalidProfileError:
        check(True, "verify without email rejected (422)")
    return verified


def test_missing_ml_fields():
    print("[8] Missing ML-required fields / completion")
    profile, completion = make_profile_from_text(COMPLETE_RESUME)
    check(completion["profile_complete"] is False, "profile_complete False")
    for f in ("aptitude_score", "coding_skills", "dsa_score", "college_tier",
              "communication_skills", "ml_knowledge", "system_design",
              "open_source_contributions", "extracurriculars", "backlogs"):
        check(f in completion["missing_fields"], f"missing_fields includes {f}")
    # Fill all manual inputs -> complete
    profile["ml_inputs"] = {
        "college_tier": "Tier-1", "backlogs": 0, "coding_skills": 7.5,
        "dsa_score": 7.0, "aptitude_score": 80.0, "communication_skills": 7.0,
        "ml_knowledge": 6.0, "system_design": 5.0,
        "open_source_contributions": 2, "extracurriculars": 1,
    }
    from app.services.profile_service import verify_profile
    verified, completion2 = verify_profile(profile)
    check(completion2["profile_complete"] is True, "profile_complete True after inputs",
          str(completion2["missing_fields"]))
    check(completion2["missing_fields"] == [], "no missing fields")


def test_invalid_profile():
    print("[9] Invalid profile")
    from app.services.profile_service import (
        InvalidProfileError,
        ProfileNotFoundError,
        get_profile,
        verify_profile,
    )
    # Invalid profile_id (path traversal attempt)
    try:
        get_profile("../../etc/passwd")
        check(False, "path traversal id rejected")
    except InvalidProfileError:
        check(True, "path traversal id rejected")
    # Unknown profile
    try:
        get_profile("does-not-exist")
        check(False, "unknown id -> 404")
    except ProfileNotFoundError:
        check(True, "unknown id -> 404")
    # Structural validation: wrong type for cgpa
    from pydantic import ValidationError
    from app.schemas_profile import StudentProfile
    bad = {"education": {"cgpa": "not-a-number"}}
    try:
        StudentProfile(**bad)
        check(False, "wrong cgpa type rejected")
    except ValidationError:
        check(True, "wrong cgpa type rejected (422)")


def test_service_suite():
    print("=" * 60)
    print("SERVICE-LEVEL TESTS")
    print("=" * 60)
    test_complete_resume()
    test_missing_cgpa()
    test_missing_internship()
    test_multiple_projects()
    test_multiple_skills()
    test_manual_edits()
    test_verification()
    test_missing_ml_fields()
    test_invalid_profile()


# ------------------------------------------------------------
# HTTP-LEVEL TESTS (require a running server)
# ------------------------------------------------------------


def test_http_suite():
    print("\n" + "=" * 60)
    print("HTTP-LEVEL TESTS")
    print("=" * 60)

    # --- /health ---------------------------------------------------
    status, body = http_get(f"{API_URL}/health")
    check(status == 200 and body.get("status") == "ok", "GET /health",
          f"status={status}")

    # --- Phase 8 regression: /api/predict --------------------------
    profile_payload = {
        "branch": "CSE", "college_tier": "Tier-1", "cgpa": 8.5,
        "backlogs": 0, "coding_skills": 8.2, "dsa_score": 8.0,
        "aptitude_score": 85.0, "communication_skills": 7.5,
        "ml_knowledge": 6.5, "system_design": 5.0, "internships": 2,
        "projects_count": 4, "certifications": 2, "hackathons": 1,
        "open_source_contributions": 1, "extracurriculars": 1,
    }
    status, body = http_post_json(f"{API_URL}/api/predict", profile_payload)
    check(status == 200 and body.get("prediction") in ("PLACED", "NOT PLACED"),
          "POST /api/predict still works", f"status={status}")

    # --- Phase 9 regression: /api/resume/upload ---------------------
    pdf = make_pdf(COMPLETE_RESUME.splitlines())
    status, body = multipart_post(
        f"{API_URL}/api/resume/upload", "file", "resume.pdf", pdf,
        "application/pdf",
    )
    check(status == 200 and body.get("success") is True,
          "POST /api/resume/upload still works", f"status={status}")

    # --- POST /api/profile/from-resume ------------------------------
    status, body = multipart_post(
        f"{API_URL}/api/profile/from-resume", "file", "resume.pdf", pdf,
        "application/pdf",
    )
    check(status == 200 and body.get("profile", {}).get("profile_id"),
          "POST /api/profile/from-resume", f"status={status} {str(body)[:200]}")
    if status != 200:
        return
    profile = body["profile"]
    pid = profile["profile_id"]
    check(profile["verified"] is False, "draft not verified")
    check(profile["personal"]["email"] == "john.doe@gmail.com", "draft email")
    check(body["completion"]["profile_complete"] is False, "draft not complete")

    # --- PUT /api/profile/{id} (manual edits) ------------------------
    profile["personal"]["name"] = "John Via Http"
    profile["ml_inputs"] = {"aptitude_score": 80.0, "college_tier": "Tier-1"}
    status, body = http_put_json(f"{API_URL}/api/profile/{pid}", profile)
    check(status == 200 and body["profile"]["verified"] is False,
          "PUT edits profile + resets verified", f"status={status}")
    check(body["profile"]["personal"]["name"] == "John Via Http", "PUT name applied")
    check("personal.name" in body["profile"]["provenance"]["user"],
          "PUT provenance.user updated")

    # --- POST /api/profile/verify ------------------------------------
    edited = body["profile"]
    status, body = http_post_json(f"{API_URL}/api/profile/verify", edited)
    check(status == 200 and body["profile"]["verified"] is True,
          "POST verify confirms profile", f"status={status}")
    check("aptitude_score" not in body["completion"]["missing_fields"],
          "verify picks up ml_inputs")

    # --- GET /api/profile/{id} ---------------------------------------
    status, body = http_get(f"{API_URL}/api/profile/{pid}")
    check(status == 200 and body["profile"]["verified"] is True,
          "GET profile returns verified profile", f"status={status}")

    # --- Invalid verify (no email) -> 422 -----------------------------
    bad = json.loads(json.dumps(edited))
    bad["personal"] = dict(edited["personal"])
    bad["personal"]["email"] = None
    status, body = http_post_json(f"{API_URL}/api/profile/verify", bad)
    check(status == 422, "verify without email -> 422", f"status={status}")

    # --- Unknown profile -> 404 ----------------------------------------
    status, _ = http_get(f"{API_URL}/api/profile/no-such-profile")
    check(status == 404, "unknown profile -> 404", f"status={status}")


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
