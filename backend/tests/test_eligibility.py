# ============================================================
# PLACEPRO - PHASE 13 - COMPANY ELIGIBILITY TEST SUITE
# ============================================================
#
# Plain-python tests (no pytest/requests dependency):
#   python backend/tests/test_eligibility.py
#
# Service-level tests always run (profiles in a temp dir).
# HTTP tests run when a server is reachable at PLACEPRO_API_URL.
#
# Coverage (per Phase 13 spec):
#   1.  Eligible student
#   2.  CGPA failure
#   3.  Backlog failure
#   4.  Branch failure
#   5.  Missing CGPA
#   6.  Missing branch
#   7.  Missing skill
#   8.  Required skill failure (honest UNKNOWN, blocks eligibility)
#   9.  Preferred skill missing (does NOT block)
#  10.  Multiple failures
#  11.  Multiple unknowns
#  12.  Unknown company
#  13.  Unknown profile
#  14.  Unverified profile
#  15.  All-company eligibility
#  16.  Skill normalization (Phase 12 taxonomy reused)
#  17-21. Existing Phase 8/9/10/11/12 regression (HTTP)
#   + GET /health and the new eligibility endpoints
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
_TMP_PROFILES = tempfile.mkdtemp(prefix="placepro_profiles_eligibility_test_")
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

COMPLETE_ML_INPUTS = {
    "college_tier": "Tier-1", "backlogs": 0, "coding_skills": 7.5,
    "dsa_score": 7.0, "aptitude_score": 80.0, "communication_skills": 7.0,
    "ml_knowledge": 6.0, "system_design": 5.0,
    "open_source_contributions": 2, "extracurriculars": 1,
}

DEMOTECH = "company_001"      # min_cgpa 7.5, max_backlogs 0, [CSE,IT,ECE],
                              # required [Python, SQL, Data Structures],
                              # preferred [AWS, Docker], min_internships 1,
                              # min_projects 2, aptitude 60
WEBTECH = "company_005"       # required [JavaScript, HTML, CSS],
                              # preferred [React, TypeScript]

# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------

_CLEAR = object()  # sentinel: pass to explicitly CLEAR a value (incl. None)


def _draft():
    from app.services.profile_service import build_draft_from_resume
    pdf = make_pdf(COMPLETE_RESUME.splitlines())
    profile, _ = build_draft_from_resume("resume.pdf", pdf, "application/pdf")
    return profile


def _profile(cgpa=_CLEAR, branch=_CLEAR, backlogs=_CLEAR, aptitude=_CLEAR,
             skills=_CLEAR, verified=True):
    """Verified profile built from the COMPLETE_RESUME draft.

    Baseline (from the resume): cgpa 8.2, branch CSE (mapped),
    graduation 2026, 1 internship, 2 projects, 1 certification.

    Pass _CLEAR-sentinel params to leave the resume value; pass an
    explicit value (including None) to override or clear it.
    `skills` replaces ALL skill lists with the given names - use it
    for deterministic skill tests (the resume's own skill list is
    otherwise present).
    """
    from app.services.profile_service import verify_profile
    profile = _draft()
    if cgpa is not _CLEAR:
        profile["education"]["cgpa"] = cgpa
    if branch is not _CLEAR:
        profile["education"]["branch"] = branch
    ml_inputs = {}
    if backlogs is not _CLEAR:
        ml_inputs["backlogs"] = backlogs
    if aptitude is not _CLEAR:
        ml_inputs["aptitude_score"] = aptitude
    profile["ml_inputs"] = ml_inputs
    if skills is not _CLEAR:
        empty = {key: [] for key in (
            "programming_languages", "frameworks", "databases", "cloud",
            "ai_ml", "web_technologies", "tools", "other_skills",
        )}
        empty["other_skills"] = list(skills or [])
        profile["skills"] = empty
    if verified:
        profile, _ = verify_profile(profile)
    return profile


DEMOTECH_SKILLS = ["Python", "SQL", "Data Structures", "AWS", "Docker"]


def _demo_tech_eligible():
    """A profile that meets every DemoTech requirement (incl. preferred)."""
    return _profile(
        backlogs=0, aptitude=80.0, skills=DEMOTECH_SKILLS,
    )


def _eligibility(profile, company_id):
    from app.services.eligibility_service import evaluate_company_eligibility
    from app.services.eligibility_service import get_company
    return evaluate_company_eligibility(profile, get_company(company_id))


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


def test_eligible():
    print("[1] Eligible student")
    r = _eligibility(_demo_tech_eligible(), DEMOTECH)
    check(r["status"] == "ELIGIBLE", "status ELIGIBLE", repr(r["status"]))
    check(r["requirements"]["failed"] == [], "no failed requirements")
    check(r["requirements"]["unknown"] == [], "no unknown requirements")
    check(r["explanation"], "explanation present")
    check("placement_probability" not in r,
          "eligibility never uses ML probability")


def test_cgpa_failure():
    print("[2] CGPA failure")
    r = _eligibility(_profile(cgpa=6.5, backlogs=0, aptitude=80.0,
                              skills=DEMOTECH_SKILLS), DEMOTECH)
    check(r["status"] == "NOT_ELIGIBLE", "status NOT_ELIGIBLE")
    failed = r["requirements"]["failed"]
    cgpa = next((f for f in failed if f["requirement"] == "Minimum CGPA"), None)
    check(cgpa is not None, "CGPA requirement failed")
    if cgpa:
        check(cgpa["student_value"] == 6.5 and cgpa["required_value"] == 7.5,
              "student/required values reported")
        check("6.5" in cgpa["explanation"] and "7.5" in cgpa["explanation"],
              "explanation states both values", cgpa["explanation"])


def test_backlog_failure():
    print("[3] Backlog failure")
    r = _eligibility(_profile(backlogs=2, aptitude=80.0,
                              skills=DEMOTECH_SKILLS), DEMOTECH)
    check(r["status"] == "NOT_ELIGIBLE", "status NOT_ELIGIBLE")
    failed = [f["requirement"] for f in r["requirements"]["failed"]]
    check("Maximum Backlogs" in failed, "backlog requirement failed",
          str(failed))


def test_branch_failure():
    print("[4] Branch failure")
    # "Mechanical" maps to ME, which is not allowed by DemoTech
    r = _eligibility(_profile(branch="Mechanical", backlogs=0, aptitude=80.0,
                              skills=DEMOTECH_SKILLS), DEMOTECH)
    check(r["status"] == "NOT_ELIGIBLE", "status NOT_ELIGIBLE")
    failed = [f["requirement"] for f in r["requirements"]["failed"]]
    check("Allowed Branch" in failed, "branch requirement failed",
          str(failed))


def test_missing_cgpa():
    print("[5] Missing CGPA")
    r = _eligibility(_profile(cgpa=None, backlogs=0, aptitude=80.0,
                              skills=DEMOTECH_SKILLS), DEMOTECH)
    check(r["status"] == "INCOMPLETE", "status INCOMPLETE (not NOT_ELIGIBLE)",
          repr(r["status"]))
    check("cgpa" in r["missing_information"], "cgpa listed as missing",
          str(r["missing_information"]))
    unknown = [u["requirement"] for u in r["requirements"]["unknown"]]
    check("Minimum CGPA" in unknown, "CGPA requirement UNKNOWN", str(unknown))
    check(any("cannot be confirmed" in e for e in r["explanation"]),
          "explanation says cannot be confirmed", str(r["explanation"]))


def test_missing_branch():
    print("[6] Missing branch")
    r = _eligibility(_profile(branch=None, backlogs=0, aptitude=80.0,
                              skills=DEMOTECH_SKILLS), DEMOTECH)
    check(r["status"] == "INCOMPLETE", "status INCOMPLETE")
    check("branch" in r["missing_information"], "branch listed as missing",
          str(r["missing_information"]))


def test_missing_skill():
    print("[7] Missing skill")
    # Data Structures not added -> required skill unknown
    r = _eligibility(_profile(backlogs=0, aptitude=80.0), DEMOTECH)
    unknown = {u["requirement"]: u for u in r["requirements"]["unknown"]}
    check("Required skill: Data Structures" in unknown,
          "Data Structures requirement UNKNOWN", str(list(unknown)))
    if "Required skill: Data Structures" in unknown:
        check("not found in the verified profile" in
              unknown["Required skill: Data Structures"]["explanation"],
              "honest explanation (not found in profile)")
        check("Add verified evidence" in
              (unknown["Required skill: Data Structures"].get("action") or ""),
              "action suggests verified evidence")


def test_required_skill_blocks():
    print("[8] Required skill failure (honest UNKNOWN blocks eligibility)")
    r = _eligibility(_profile(backlogs=0, aptitude=80.0), DEMOTECH)
    check(r["status"] == "INCOMPLETE",
          "missing required skill -> INCOMPLETE, not ELIGIBLE",
          repr(r["status"]))
    check(r["status"] != "NOT_ELIGIBLE",
          "never classified as NOT_ELIGIBLE for a missing skill")


def test_preferred_skill_missing():
    print("[9] Preferred skill missing (does NOT block)")
    # AWS and Docker are preferred; leave them out but keep required skills
    r = _eligibility(
        _profile(backlogs=0, aptitude=80.0,
                 skills=["Python", "SQL", "Data Structures"]),
        DEMOTECH,
    )
    check(r["status"] == "ELIGIBLE", "still ELIGIBLE", repr(r["status"]))
    unknown = [u for u in r["requirements"]["unknown"]]
    preferred_unknown = [u for u in unknown if not u["mandatory"]]
    check(len(preferred_unknown) >= 1, "preferred skills reported as unknown",
          str([u["requirement"] for u in preferred_unknown]))
    check(all(u["mandatory"] is False for u in preferred_unknown),
          "preferred items flagged non-mandatory")


def test_multiple_failures():
    print("[10] Multiple failures")
    r = _eligibility(_profile(cgpa=6.0, branch="Mechanical", backlogs=3,
                              aptitude=40.0,
                              skills=DEMOTECH_SKILLS), DEMOTECH)
    check(r["status"] == "NOT_ELIGIBLE", "status NOT_ELIGIBLE")
    failed_names = [f["requirement"] for f in r["requirements"]["failed"]]
    check(len(failed_names) >= 3, "multiple failed requirements",
          str(failed_names))
    for name in ("Minimum CGPA", "Maximum Backlogs", "Allowed Branch",
                 "Minimum Aptitude Score"):
        check(name in failed_names, f"{name} among failures", str(failed_names))


def test_multiple_unknowns():
    print("[11] Multiple unknowns")
    r = _eligibility(_profile(cgpa=None, branch=None, backlogs=0,
                              aptitude=80.0), DEMOTECH)
    check(r["status"] == "INCOMPLETE", "status INCOMPLETE")
    unknown_names = [u["requirement"] for u in r["requirements"]["unknown"]]
    check("Minimum CGPA" in unknown_names and "Allowed Branch" in unknown_names,
          "cgpa and branch both unknown", str(unknown_names))
    check(len(r["missing_information"]) >= 2, "multiple missing items",
          str(r["missing_information"]))


def test_unknown_company():
    print("[12] Unknown company")
    from app.services.eligibility_service import (
        CompanyNotFoundError,
        get_eligibility,
    )
    pid = _demo_tech_eligible()["profile_id"]
    try:
        get_eligibility(pid, "company_999")
        check(False, "unknown company rejected")
    except CompanyNotFoundError:
        check(True, "unknown company -> 404")


def test_unknown_profile():
    print("[13] Unknown profile")
    from app.services.eligibility_service import get_eligibility
    from app.services.profile_service import ProfileNotFoundError
    try:
        get_eligibility("no-such-profile", DEMOTECH)
        check(False, "unknown profile rejected")
    except ProfileNotFoundError:
        check(True, "unknown profile -> 404")


def test_unverified_profile():
    print("[14] Unverified profile")
    from app.services.eligibility_service import (
        EligibilityServiceError,
        get_eligibility,
    )
    draft = _profile(verified=False)
    try:
        get_eligibility(draft["profile_id"], DEMOTECH)
        check(False, "unverified profile rejected")
    except EligibilityServiceError:
        check(True, "unverified profile -> error")


def test_all_companies():
    print("[15] All-company eligibility")
    from app.services.eligibility_service import get_all_eligibility
    pid = _demo_tech_eligible()["profile_id"]
    result = get_all_eligibility(pid)
    check(set(result) == {"eligible", "not_eligible", "incomplete"},
          "grouped into 3 buckets", str(sorted(result)))
    check(len(result["eligible"]) >= 1, "at least one eligible company",
          str([c["company"]["company_name"] for c in result["eligible"]]))
    for bucket in ("eligible", "not_eligible", "incomplete"):
        for item in result[bucket]:
            check("company" in item and "status" in item and
                  "passed_count" in item and "failed_count" in item and
                  "unknown_count" in item and "major_reasons" in item,
                  f"{bucket} item has full summary")
    all_ids = [c["company"]["company_id"] for b in result.values()
               for c in b]
    check("company_900" not in all_ids,
          "inactive company excluded from all-company eligibility")


def test_skill_normalization():
    print("[16] Skill normalization (Phase 12 taxonomy reused)")
    # "js" -> JavaScript, "reactjs" -> React (WebTech requires JS/HTML/CSS)
    profile = _profile(backlogs=0, skills=["js", "html", "css", "reactjs"])
    r = _eligibility(profile, WEBTECH)
    check(r["status"] == "ELIGIBLE", "status ELIGIBLE", repr(r["status"]))
    passed = {p["requirement"]: p for p in r["requirements"]["passed"]}
    check("Required skill: JavaScript" in passed,
          "js normalized to JavaScript -> PASS", str(list(passed)))
    check("Required skill: HTML" in passed, "HTML -> PASS")
    check("Required skill: CSS" in passed, "CSS -> PASS")
    check("Preferred skill: React" in passed,
          "reactjs normalized to React -> PASS")


def test_service_suite():
    print("=" * 60)
    print("SERVICE-LEVEL TESTS (PHASE 13)")
    print("=" * 60)
    test_eligible()
    test_cgpa_failure()
    test_backlog_failure()
    test_branch_failure()
    test_missing_cgpa()
    test_missing_branch()
    test_missing_skill()
    test_required_skill_blocks()
    test_preferred_skill_missing()
    test_multiple_failures()
    test_multiple_unknowns()
    test_unknown_company()
    test_unknown_profile()
    test_unverified_profile()
    test_all_companies()
    test_skill_normalization()


# ------------------------------------------------------------
# HTTP-LEVEL TESTS (require a running server)
# ------------------------------------------------------------


def _http_verified_profile():
    """Create a verified profile via the API (DemoTech-eligible)."""
    pdf = make_pdf(COMPLETE_RESUME.splitlines())
    status, body = multipart_post(
        f"{API_URL}/api/profile/from-resume", "file", "resume.pdf", pdf,
        "application/pdf",
    )
    assert status == 200, f"from-resume failed: {status} {body}"
    profile = body["profile"]
    pid = profile["profile_id"]
    profile["ml_inputs"] = dict(COMPLETE_ML_INPUTS)
    profile["skills"]["other_skills"] = ["Data Structures"]
    status, body = http_put_json(f"{API_URL}/api/profile/{pid}", profile)
    assert status == 200, f"PUT failed: {status} {body}"
    status, body = http_post_json(f"{API_URL}/api/profile/verify",
                                  body["profile"])
    assert status == 200 and body["profile"]["verified"], "verify failed"
    return pid


def test_http_suite():
    print("\n" + "=" * 60)
    print("HTTP-LEVEL TESTS (PHASE 13)")
    print("=" * 60)

    # --- /health ---------------------------------------------------
    status, body = http_get(f"{API_URL}/health")
    check(status == 200 and body.get("status") == "ok", "GET /health")

    # --- [17] Phase 8 prediction still works ------------------------
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
          "[17] POST /api/predict still works", f"status={status}")

    # --- [18] Phase 9 resume extraction still works ------------------
    pdf = make_pdf(COMPLETE_RESUME.splitlines())
    status, body = multipart_post(
        f"{API_URL}/api/resume/upload", "file", "resume.pdf", pdf,
        "application/pdf",
    )
    check(status == 200 and body.get("success") is True,
          "[18] POST /api/resume/upload still works", f"status={status}")

    # --- [19] Phase 10 profile flow still works ----------------------
    pid = _http_verified_profile()
    status, body = http_get(f"{API_URL}/api/profile/{pid}")
    check(status == 200 and body["profile"]["verified"] is True,
          "[19] Phase 10 profile flow still works", f"status={status}")

    # --- [20] Phase 11 prediction flow still works -------------------
    status, body = http_post_json(f"{API_URL}/api/profile/{pid}/predict", {})
    check(status == 200, "[20] Phase 11 prediction flow still works",
          f"status={status}")
    if status == 200:
        check(body["ready_for_prediction"] is True, "ready for prediction")

    # --- [21] Phase 12 readiness still works -------------------------
    status, body = http_get(f"{API_URL}/api/profile/{pid}/readiness")
    check(status == 200 and 0 <= body["readiness_score"] <= 100,
          "[21] Phase 12 readiness still works", f"status={status}")

    # --- New: GET /api/companies --------------------------------------
    status, body = http_get(f"{API_URL}/api/companies")
    check(status == 200 and isinstance(body, list), "GET /api/companies")
    if status == 200:
        ids = [c["company_id"] for c in body]
        check("company_001" in ids, "demo companies listed")
        check("company_900" not in ids, "inactive company excluded")
        check(all("company_id" in c and "company_name" in c and
                  "roles" in c for c in body), "summary fields present")

    # --- New: GET /api/companies/{id} ---------------------------------
    status, body = http_get(f"{API_URL}/api/companies/{DEMOTECH}")
    check(status == 200 and body.get("company_id") == DEMOTECH,
          "GET /api/companies/company_001")
    if status == 200:
        check("requirements" in body and "min_cgpa" in body["requirements"],
              "requirements returned")
    status, body = http_get(f"{API_URL}/api/companies/company_999")
    check(status == 404, "unknown company -> 404", f"status={status}")

    # --- New: GET /api/profile/{id}/eligibility/{company_id} -----------
    status, body = http_get(
        f"{API_URL}/api/profile/{pid}/eligibility/{DEMOTECH}")
    check(status == 200 and body.get("status") == "ELIGIBLE",
          "eligibility for one company", f"status={status} {body.get('status')}")
    if status == 200:
        check(body["requirements"]["passed"] and
              body["requirements"]["failed"] == [] and
              body["requirements"]["unknown"] == [],
              "PASS/FAIL/UNKNOWN grouped correctly")
        check(body["explanation"], "explanation present")

    # --- New: GET /api/profile/{id}/eligibility ------------------------
    status, body = http_get(f"{API_URL}/api/profile/{pid}/eligibility")
    check(status == 200 and set(body) == {"eligible", "not_eligible",
                                          "incomplete"},
          "all-company eligibility", f"status={status}")

    # --- New: unverified profile -> 422 --------------------------------
    status2, body2 = multipart_post(
        f"{API_URL}/api/profile/from-resume", "file", "resume.pdf", pdf,
        "application/pdf",
    )
    pid2 = body2["profile"]["profile_id"]
    status2, _ = http_get(f"{API_URL}/api/profile/{pid2}/eligibility/{DEMOTECH}")
    check(status2 == 422, "unverified eligibility -> 422",
          f"status={status2}")

    # --- New: unknown profile -> 404 ------------------------------------
    status2, _ = http_get(f"{API_URL}/api/profile/nope/eligibility/{DEMOTECH}")
    check(status2 == 404, "unknown profile eligibility -> 404",
          f"status={status2}")


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
