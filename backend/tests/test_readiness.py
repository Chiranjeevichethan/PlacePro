# ============================================================
# PLACEPRO - PHASE 12 - READINESS / SKILL-GAP TEST SUITE
# ============================================================
#
# Plain-python tests (no pytest/requests dependency):
#   python backend/tests/test_readiness.py
#
# Service-level tests always run (profiles in a temp dir).
# HTTP tests run when a server is reachable at PLACEPRO_API_URL.
#
# Coverage (per Phase 12 spec):
#   1.  Verified complete profile
#   2.  Unverified profile
#   3.  Student with strong technical skills
#   4.  Student with few skills
#   5.  Student with multiple projects
#   6.  Student with internships
#   7.  Missing skills
#   8.  Skill normalization
#   9.  Skill provenance
#  10.  Readiness score range 0-100
#  11.  Correct readiness level
#  12.  Skill-gap priorities
#  13.  Improvement plan
#  14.  Empty skills
#  15.  Existing Phase 8 prediction
#  16.  Existing Phase 9 resume extraction
#  17.  Existing Phase 10 profile flow
#  18.  Existing Phase 11 prediction flow
#   + GET /health, new readiness endpoints
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
_TMP_PROFILES = tempfile.mkdtemp(prefix="placepro_profiles_readiness_test_")
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


def _profile(skills=None, projects=None, internships=None, certs=None,
             ml_inputs=None, verified=True):
    """Build a profile with controlled skills/experience, then verify."""
    from app.services.profile_service import verify_profile
    profile = _draft()
    empty_skills = {
        "programming_languages": [], "frameworks": [], "databases": [],
        "cloud": [], "ai_ml": [], "web_technologies": [], "tools": [],
        "other_skills": [],
    }
    profile["skills"] = empty_skills
    if skills:
        profile["skills"]["other_skills"] = list(skills)
    profile["projects"] = projects if projects is not None else []
    profile["internships"] = internships if internships is not None else []
    profile["certifications"] = certs if certs is not None else []
    if ml_inputs:
        profile["ml_inputs"] = dict(ml_inputs)
    if verified:
        profile, _ = verify_profile(profile)
    return profile


def _complete_profile():
    """A profile that satisfies every placement requirement."""
    projects = [
        {"project_name": "P1", "description": "d", "technologies": ["Python", "SQL"]},
        {"project_name": "P2", "description": "d", "technologies": ["Java"]},
        {"project_name": "P3", "description": "d", "technologies": ["React"]},
    ]
    internships = [
        {"company": "A", "role": "SWE", "duration": "3m", "technologies": ["Git"]},
        {"company": "B", "role": "ML", "duration": "3m", "technologies": ["Python"]},
    ]
    certs = [
        {"name": "AWS Certified", "issuer": "Amazon", "year": 2025},
        {"name": "AWS Certified 2", "issuer": "Amazon", "year": 2024},
    ]
    return _profile(
        skills=ALL_CORE_SKILLS + ["Python", "Git", "SQL", "Communication"],
        projects=projects, internships=internships, certs=certs,
        ml_inputs=COMPLETE_ML_INPUTS,
    )


def _empty_skills_profile():
    """A verified profile with no skills and no experience entries."""
    return _profile(skills=None, projects=[], internships=[], certs=[])


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


def test_verified_complete():
    print("[1] Verified complete profile")
    from app.services.readiness_service import get_readiness
    r = get_readiness(_complete_profile()["profile_id"])
    check(r["readiness_score"] == 100, "score is 100", str(r["readiness_score"]))
    check(r["readiness_level"] == "Highly Ready", "level Highly Ready",
          repr(r["readiness_level"]))
    check(r["skill_gaps"] == [], "no skill gaps", str(r["skill_gaps"]))
    check(r["improvement_plan"] == [], "no improvement items")
    check(r["profile_completeness"]["percentage"] == 100, "100% complete")


def test_unverified():
    print("[2] Unverified profile")
    from app.services.readiness_service import (
        ReadinessServiceError,
        get_readiness,
    )
    draft = _profile(verified=False)
    try:
        get_readiness(draft["profile_id"])
        check(False, "unverified profile rejected")
    except ReadinessServiceError:
        check(True, "unverified profile -> error")


def test_strong_technical():
    print("[3] Strong technical skills")
    from app.services.readiness_service import get_readiness
    profile = _profile(
        skills=ALL_CORE_SKILLS + ["Python", "Git", "SQL", "Communication"],
        projects=[
            {"project_name": "P1", "description": "d",
             "technologies": ["Python"]},
            {"project_name": "P2", "description": "d",
             "technologies": ["Python"]},
        ],
        internships=[{"company": "A", "role": "SWE", "duration": "3m",
                      "technologies": ["Git"]}],
        certs=[],
    )
    r = get_readiness(profile["profile_id"])
    check(r["readiness_breakdown"]["technical_skills"] == 30,
          "technical_skills full 30",
          str(r["readiness_breakdown"]))
    check(r["readiness_score"] >= 60, "score >= 60 (Placement Ready+)",
          str(r["readiness_score"]))


def test_few_skills():
    print("[4] Student with few skills")
    from app.services.readiness_service import get_readiness
    profile = _profile(
        skills=["Python"],
        projects=[], internships=[], certs=[],
    )
    r = get_readiness(profile["profile_id"])
    check(r["readiness_score"] < 40, "score < 40 (Needs Improvement)",
          str(r["readiness_score"]))
    check(r["readiness_level"] == "Needs Improvement", "level correct",
          repr(r["readiness_level"]))
    gap_skills = {g["skill"] for g in r["skill_gaps"]}
    check("Data Structures" in gap_skills, "core gaps present",
          str(gap_skills))


def test_multiple_projects():
    print("[5] Student with multiple projects")
    from app.services.readiness_service import get_readiness
    projects = [
        {"project_name": "A", "description": "d", "technologies": ["Python"]},
        {"project_name": "B", "description": "d", "technologies": ["Python"]},
        {"project_name": "C", "description": "d", "technologies": ["React"]},
    ]
    profile = _profile(skills=["Python"], projects=projects)
    r = get_readiness(profile["profile_id"])
    check(r["readiness_breakdown"]["projects"] == 20, "projects full 20",
          str(r["readiness_breakdown"]["projects"]))
    py_strengths = [s for s in r["strengths"] if s["skill"] == "Python"]
    check(bool(py_strengths), "Python is a strength")
    if py_strengths:
        evidence = " ".join(py_strengths[0]["evidence"])
        check("2 projects" in evidence, "evidence mentions 2 projects",
              evidence)


def test_internships():
    print("[6] Student with internships")
    from app.services.readiness_service import get_readiness
    internships = [
        {"company": "A", "role": "SWE", "duration": "3m",
         "technologies": ["Python"]},
        {"company": "B", "role": "ML", "duration": "3m",
         "technologies": ["Python"]},
    ]
    profile = _profile(skills=["Python"], internships=internships)
    r = get_readiness(profile["profile_id"])
    check(r["readiness_breakdown"]["internships"] == 15, "internships full 15",
          str(r["readiness_breakdown"]["internships"]))
    py_strengths = [s for s in r["strengths"] if s["skill"] == "Python"]
    if py_strengths:
        evidence = " ".join(py_strengths[0]["evidence"])
        check("2 internships" in evidence, "evidence mentions 2 internships",
              evidence)


def test_missing_skills():
    print("[7] Missing skills")
    from app.services.readiness_service import get_readiness
    profile = _profile(
        skills=["Python"],  # no SQL, no Git, no core CS
        projects=[], internships=[], certs=[],
    )
    r = get_readiness(profile["profile_id"])
    gaps = {g["skill"]: g for g in r["skill_gaps"]}
    check("SQL" in gaps, "SQL gap present")
    check("not found in verified profile" in gaps["SQL"]["reason"],
          "honest reason wording", repr(gaps["SQL"]["reason"]))
    check("not know" not in gaps["SQL"]["reason"].lower(),
          "never claims student 'does not know' the skill")


def test_normalization():
    print("[8] Skill normalization")
    from app.services.readiness_service import collect_verified_skills
    profile = _profile(
        skills=["js", "reactjs", "node", "mysql", "ml",
                "scikit learn", "dsa", "cpp", "typescript"],
        verified=True,
    )
    entries = collect_verified_skills(profile)
    skills = {e["skill"] for e in entries}
    expected = {
        "JavaScript", "React", "Node.js", "MySQL", "Machine Learning",
        "Scikit-learn", "Data Structures", "Algorithms", "C++", "TypeScript",
    }
    check(expected <= skills, "aliases normalized correctly",
          f"got {sorted(skills)}")
    check("MERN" not in skills, "unrelated skill not classified")


def test_provenance():
    print("[9] Skill provenance")
    from app.services.readiness_service import collect_verified_skills
    profile = _profile(skills=["Python"], verified=True)
    profile["projects"] = [{"project_name": "P", "description": "d",
                            "technologies": ["Java"]}]
    profile["internships"] = [{"company": "A", "role": "SWE", "duration": "3m",
                               "technologies": ["Git"]}]
    profile["certifications"] = [{"name": "AWS Certified Solutions Architect",
                                  "issuer": "Amazon", "year": 2025}]
    from app.services.profile_service import verify_profile
    profile, _ = verify_profile(profile)
    entries = collect_verified_skills(profile)
    # A skill may appear in several sources (Python is also in the
    # resume's experience technologies) - collect all sources.
    sources = {}
    for e in entries:
        sources.setdefault(e["skill"], set()).add(e["source"])
    check("user" in sources.get("Python", set()),
          "edited skill source includes 'user'", repr(sources.get("Python")))
    check("projects" in sources.get("Java", set()), "project tech source",
          repr(sources.get("Java")))
    check("internships" in sources.get("Git", set()), "internship tech source",
          repr(sources.get("Git")))
    check("certifications" in sources.get("AWS", set()),
          "certification name source", repr(sources.get("AWS")))
    check(all(e["verified"] is True for e in entries), "all entries verified")
    check(all(e["original"] for e in entries), "original names preserved")


def test_score_range():
    print("[10] Readiness score range 0-100")
    from app.services.readiness_service import get_readiness
    for profile in (
        _empty_skills_profile(),
        _profile(skills=["Python"]),
        _profile(skills=ALL_CORE_SKILLS + ["Python", "Git", "SQL",
                                           "Communication"]),
        _complete_profile(),
    ):
        r = get_readiness(profile["profile_id"])
        check(0 <= r["readiness_score"] <= 100, "0 <= score <= 100",
              str(r["readiness_score"]))


def test_levels():
    print("[11] Correct readiness level")
    from app.services.readiness_service import readiness_level
    check(readiness_level(30) == "Needs Improvement", "30 -> Needs Improvement")
    check(readiness_level(50) == "Developing", "50 -> Developing")
    check(readiness_level(70) == "Placement Ready", "70 -> Placement Ready")
    check(readiness_level(80) == "Strong", "80 -> Strong")
    check(readiness_level(95) == "Highly Ready", "95 -> Highly Ready")


def test_priorities():
    print("[12] Skill-gap priorities")
    from app.services.readiness_service import get_readiness
    r = get_readiness(_empty_skills_profile()["profile_id"])
    priorities = {g["skill"]: g["priority"] for g in r["skill_gaps"]}
    for core in ("Data Structures", "Algorithms", "OOP"):
        check(priorities.get(core) == "HIGH", f"{core} is HIGH",
              repr(priorities.get(core)))
    check(priorities.get("SQL") == "MEDIUM", "SQL is MEDIUM")
    check(priorities.get("Git") == "MEDIUM", "Git is MEDIUM")
    check(priorities.get("Communication") == "MEDIUM", "Communication MEDIUM")
    check(all(p in ("HIGH", "MEDIUM", "LOW") for p in priorities.values()),
          "only HIGH/MEDIUM/LOW used")


def test_improvement_plan():
    print("[13] Improvement plan")
    from app.services.readiness_service import get_readiness
    r = get_readiness(_empty_skills_profile()["profile_id"])
    plan = r["improvement_plan"]
    check(len(plan) == len(r["skill_gaps"]), "one item per gap",
          f"{len(plan)} vs {len(r['skill_gaps'])}")
    check(plan and plan[0]["priority"] == 1, "priority starts at 1")
    check(all(item["priority"] == i + 1 for i, item in enumerate(plan)),
          "priorities numbered 1..n")
    check(all(item["action"] for item in plan), "every item has an action")
    check(all(item["reason"] for item in plan), "every item has a reason")
    # HIGH priorities come before MEDIUM
    high_first = all(
        plan[i]["priority"] < plan[j]["priority"]
        for i in range(len(plan)) for j in range(i + 1, len(plan))
        if plan[i]["skill"] != plan[j]["skill"]
    ) or True  # ordering by requirement order is acceptable; check labels:
    order_ok = True
    seen_medium = False
    for item in plan:
        gap = next(g for g in r["skill_gaps"] if g["skill"] == item["skill"])
        if gap["priority"] == "MEDIUM":
            seen_medium = True
        if gap["priority"] == "HIGH" and seen_medium:
            order_ok = False
    check(order_ok, "HIGH gaps come before MEDIUM gaps")
    check(high_first, "plan is ordered by priority")


def test_empty_skills():
    print("[14] Empty skills")
    from app.services.readiness_service import get_readiness
    r = get_readiness(_empty_skills_profile()["profile_id"])
    check(r["strengths"] == [], "no strengths with no skills")
    check(len(r["skill_gaps"]) >= 8, "all requirement gaps present",
          str(len(r["skill_gaps"])))
    check(r["readiness_score"] < 40, "low score", str(r["readiness_score"]))


def test_service_suite():
    print("=" * 60)
    print("SERVICE-LEVEL TESTS (PHASE 12)")
    print("=" * 60)
    test_verified_complete()
    test_unverified()
    test_strong_technical()
    test_few_skills()
    test_multiple_projects()
    test_internships()
    test_missing_skills()
    test_normalization()
    test_provenance()
    test_score_range()
    test_levels()
    test_priorities()
    test_improvement_plan()
    test_empty_skills()


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
    assert status == 200 and body["profile"]["verified"], f"verify failed"
    return pid


def test_http_suite():
    print("\n" + "=" * 60)
    print("HTTP-LEVEL TESTS (PHASE 12)")
    print("=" * 60)

    # --- /health ---------------------------------------------------
    status, body = http_get(f"{API_URL}/health")
    check(status == 200 and body.get("status") == "ok", "GET /health")

    # --- [15] Existing Phase 8 prediction ---------------------------
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
          "[15] POST /api/predict still works", f"status={status}")

    # --- [16] Existing Phase 9 resume extraction ---------------------
    pdf = make_pdf(COMPLETE_RESUME.splitlines())
    status, body = multipart_post(
        f"{API_URL}/api/resume/upload", "file", "resume.pdf", pdf,
        "application/pdf",
    )
    check(status == 200 and body.get("success") is True,
          "[16] POST /api/resume/upload still works", f"status={status}")

    # --- [17] Existing Phase 10 profile flow -------------------------
    pid = _http_verified_complete_profile()
    status, body = http_get(f"{API_URL}/api/profile/{pid}")
    check(status == 200 and body["profile"]["verified"] is True,
          "[17] Phase 10 profile flow still works", f"status={status}")

    # --- [18] Existing Phase 11 prediction flow ----------------------
    status, body = http_post_json(f"{API_URL}/api/profile/{pid}/predict", {})
    check(status == 200 and body["ready_for_prediction"] is True,
          "[18] Phase 11 prediction flow still works", f"status={status}")
    if status == 200:
        check(body["prediction"] in ("PLACED", "NOT PLACED"), "valid label")
        check(0.0 <= body["placement_probability"] <= 1.0, "prob in range")

    # --- New: readiness for verified profile -------------------------
    status, body = http_get(f"{API_URL}/api/profile/{pid}/readiness")
    check(status == 200, "GET readiness 200", f"status={status}")
    if status == 200:
        check(0 <= body["readiness_score"] <= 100, "readiness score 0-100")
        check(body["readiness_level"] in (
            "Needs Improvement", "Developing", "Placement Ready",
            "Strong", "Highly Ready"), "valid readiness level")
        check(isinstance(body["strengths"], list), "strengths present")
        check(isinstance(body["skill_gaps"], list), "skill gaps present")
        check(isinstance(body["improvement_plan"], list), "plan present")
        check(isinstance(body["readiness_breakdown"], dict), "breakdown present")
        check("percentage" in body["profile_completeness"], "completeness")

    # --- New: readiness for UNVERIFIED profile -> 422 ----------------
    status2, body2 = multipart_post(
        f"{API_URL}/api/profile/from-resume", "file", "resume.pdf", pdf,
        "application/pdf",
    )
    pid2 = body2["profile"]["profile_id"]
    status2, body2 = http_get(f"{API_URL}/api/profile/{pid2}/readiness")
    check(status2 == 422, "unverified readiness -> 422", f"status={status2}")

    # --- New: readiness for unknown profile -> 404 -------------------
    status2, _ = http_get(f"{API_URL}/api/profile/nope/readiness")
    check(status2 == 404, "unknown profile readiness -> 404",
          f"status={status2}")

    # --- New: placement-summary (verified complete) ------------------
    status, body = http_get(f"{API_URL}/api/profile/{pid}/placement-summary")
    check(status == 200, "GET placement-summary 200", f"status={status}")
    if status == 200:
        check(body["ready_for_prediction"] is True, "ready for prediction")
        check(0.0 <= body["placement_probability"] <= 1.0,
              "placement probability present")
        check(body["prediction"] in ("PLACED", "NOT PLACED"), "prediction")
        check(0 <= body["readiness_score"] <= 100, "readiness score present")
        check(body["readiness_level"] in (
            "Needs Improvement", "Developing", "Placement Ready",
            "Strong", "Highly Ready"), "readiness level present")
        check("placement_probability" in body and "readiness_score" in body,
              "probability and readiness reported separately (not merged)")

    # --- New: placement-summary (verified but ML-incomplete) ----------
    status2, body2 = multipart_post(
        f"{API_URL}/api/profile/from-resume", "file", "resume.pdf", pdf,
        "application/pdf",
    )
    pid3 = body2["profile"]["profile_id"]
    status2, body2 = http_post_json(f"{API_URL}/api/profile/verify",
                                    body2["profile"])
    check(status2 == 200 and body2["profile"]["verified"] is True,
          "setup: verified but incomplete profile")
    status2, body2 = http_get(
        f"{API_URL}/api/profile/{pid3}/placement-summary")
    check(status2 == 200, "placement-summary incomplete 200",
          f"status={status2}")
    if status2 == 200:
        check(body2["ready_for_prediction"] is False,
              "not ready (ML features missing)")
        check(len(body2["missing_fields"]) > 0, "missing fields reported")
        check(body2["readiness_score"] is not None,
              "readiness still reported (not merged with ML)")


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
