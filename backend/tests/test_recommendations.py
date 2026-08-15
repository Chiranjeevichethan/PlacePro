# ============================================================
# PLACEPRO - PHASE 14 - RECOMMENDATION TEST SUITE
# ============================================================
#
# Plain-python tests (no pytest/requests dependency):
#   python backend/tests/test_recommendations.py
#
# Service-level tests always run (profiles in a temp dir).
# HTTP tests run when a server is reachable at PLACEPRO_API_URL.
#
# Coverage (per Phase 14 spec):
#   1.  Strong eligible student
#   2.  Weak student
#   3.  Incomplete profile
#   4.  Unverified profile
#   5.  Unknown profile
#   6.  Skill matching
#   7.  Required skill missing
#   8.  Preferred skill missing
#   9.  Eligibility failure
#  10.  Recommendation ranking
#  11.  Recommendation score range
#  12.  Readiness integration
#  13.  ML probability integration
#  14.  Required eligibility override
#  15.  Top-N limit
#  16.  Empty recommendation scenario
#  17.  Explanation generation
#  18.  Improvement actions
#  19.  Skill normalization reuse
#  20-25. Existing Phase 8/9/10/11/12/13 regression (HTTP)
#   + GET /health and the new recommendations endpoint
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
_TMP_PROFILES = tempfile.mkdtemp(prefix="placepro_profiles_rec_test_")
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

DEMOTECH = "company_001"
WEBTECH = "company_005"
DEMOTECH_SKILLS = ["Python", "SQL", "Data Structures", "AWS", "Docker"]

# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------

_CLEAR = object()


def _draft():
    from app.services.profile_service import build_draft_from_resume
    pdf = make_pdf(COMPLETE_RESUME.splitlines())
    profile, _ = build_draft_from_resume("resume.pdf", pdf, "application/pdf")
    return profile


def _profile(cgpa=_CLEAR, branch=_CLEAR, backlogs=_CLEAR, aptitude=_CLEAR,
             skills=_CLEAR, ml_inputs=_CLEAR, verified=True):
    """Verified profile from the COMPLETE_RESUME draft.

    Baseline (from the resume): cgpa 8.2, branch CSE (mapped),
    graduation 2026, 1 internship, 2 projects, 1 certification.
    """
    from app.services.profile_service import verify_profile
    profile = _draft()
    if cgpa is not _CLEAR:
        profile["education"]["cgpa"] = cgpa
    if branch is not _CLEAR:
        profile["education"]["branch"] = branch
    if backlogs is not _CLEAR or aptitude is not _CLEAR:
        profile["ml_inputs"] = dict(profile.get("ml_inputs") or {})
        if backlogs is not _CLEAR:
            profile["ml_inputs"]["backlogs"] = backlogs
        if aptitude is not _CLEAR:
            profile["ml_inputs"]["aptitude_score"] = aptitude
    if ml_inputs is not _CLEAR:
        profile["ml_inputs"] = dict(ml_inputs)
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


def _strong_profile():
    """Meets DemoTech fully and has all ML inputs."""
    return _profile(
        skills=DEMOTECH_SKILLS, ml_inputs=dict(COMPLETE_ML_INPUTS),
    )


def _weak_profile():
    """Fails most companies (low CGPA, backlogs, few skills)."""
    return _profile(
        cgpa=6.5, backlogs=3, aptitude=40.0, skills=["Java"],
        ml_inputs=dict(COMPLETE_ML_INPUTS),
    )


def _recs(profile, limit=None):
    from app.services.recommendation_service import get_recommendations
    return get_recommendations(profile["profile_id"], limit=limit)


def _all_items(result):
    groups = result["recommendations"]
    return (groups["recommended"] + groups["eligible"] +
            groups["incomplete"] + groups["not_recommended"])


def _item(result, company_id):
    for item in _all_items(result):
        if item["company_id"] == company_id:
            return item
    return None


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


def test_strong_eligible():
    print("[1] Strong eligible student")
    result = _recs(_strong_profile())
    groups = result["recommendations"]
    check(groups["recommended"], "recommended bucket non-empty")
    demotech = _item(result, DEMOTECH)
    check(demotech is not None and demotech["status"] == "RECOMMENDED",
          "DemoTech RECOMMENDED", repr(demotech and demotech["status"]))
    check(demotech["recommendation_score"] >= 75,
          "score >= threshold", str(demotech["recommendation_score"]))


def test_weak_student():
    print("[2] Weak student")
    result = _recs(_weak_profile())
    groups = result["recommendations"]
    check(groups["recommended"] == [], "no recommended companies")
    check(groups["eligible"] == [], "no merely-eligible companies")
    check(len(groups["not_recommended"]) >= 1, "not_recommended non-empty",
          str(len(groups["not_recommended"])))


def test_incomplete_profile():
    print("[3] Incomplete profile (verified, missing CGPA)")
    profile = _profile(cgpa=None, ml_inputs=dict(COMPLETE_ML_INPUTS))
    result = _recs(profile)
    groups = result["recommendations"]
    check(groups["incomplete"], "incomplete bucket non-empty")
    check(groups["recommended"] == [], "nothing recommended")
    for item in groups["incomplete"]:
        check(item["status"] == "INCOMPLETE", "status INCOMPLETE")
        check(item["missing_information"], "missing information listed")


def test_unverified():
    print("[4] Unverified profile")
    from app.services.recommendation_service import (
        RecommendationServiceError,
        get_recommendations,
    )
    draft = _profile(verified=False)
    try:
        get_recommendations(draft["profile_id"])
        check(False, "unverified profile rejected")
    except RecommendationServiceError:
        check(True, "unverified profile -> error")


def test_unknown_profile():
    print("[5] Unknown profile")
    from app.services.profile_service import ProfileNotFoundError
    from app.services.recommendation_service import get_recommendations
    try:
        get_recommendations("no-such-profile")
        check(False, "unknown profile rejected")
    except ProfileNotFoundError:
        check(True, "unknown profile -> 404")


def test_skill_matching():
    print("[6] Skill matching")
    result = _recs(_strong_profile())
    demotech = _item(result, DEMOTECH)
    sm = demotech["skill_match"]
    check(sm["required_matched"] == ["Python", "SQL", "Data Structures"],
          "required skills matched", str(sm["required_matched"]))
    check(sm["required_missing"] == [], "no required skills missing")
    check(sorted(sm["preferred_matched"]) == ["AWS", "Docker"],
          "preferred skills matched", str(sm["preferred_matched"]))
    check(sm["preferred_missing"] == [], "no preferred skills missing")
    check(sm["score"] == 100.0, "skill match 100%", str(sm["score"]))


def test_required_skill_missing():
    print("[7] Required skill missing")
    profile = _profile(skills=["Python", "SQL", "AWS", "Docker"],
                       ml_inputs=dict(COMPLETE_ML_INPUTS))
    result = _recs(profile)
    demotech = _item(result, DEMOTECH)
    check(demotech["skill_match"]["required_missing"] == ["Data Structures"],
          "Data Structures listed as missing",
          str(demotech["skill_match"]["required_missing"]))
    check("Strengthen Data Structures knowledge" in
          demotech["improvement_actions"],
          "improvement action for missing skill",
          str(demotech["improvement_actions"]))
    check(demotech["status"] == "INCOMPLETE",
          "missing required skill -> INCOMPLETE (not recommended)")


def test_preferred_skill_missing():
    print("[8] Preferred skill missing (does NOT block)")
    profile = _profile(skills=["Python", "SQL", "Data Structures"],
                       ml_inputs=dict(COMPLETE_ML_INPUTS))
    result = _recs(profile)
    demotech = _item(result, DEMOTECH)
    # AWS is matched via the resume's AWS certification (Phase 12
    # certification-name scan); Docker is genuinely absent.
    check("Docker" in demotech["skill_match"]["preferred_missing"],
          "Docker listed as missing preferred",
          str(demotech["skill_match"]["preferred_missing"]))
    check("AWS" in demotech["skill_match"]["preferred_matched"],
          "AWS matched via certification",
          str(demotech["skill_match"]["preferred_matched"]))
    check(demotech["status"] in ("RECOMMENDED", "ELIGIBLE"),
          "still eligible-status based", repr(demotech["status"]))


def test_eligibility_failure():
    print("[9] Eligibility failure -> NOT_RECOMMENDED")
    profile = _profile(cgpa=6.0, ml_inputs=dict(COMPLETE_ML_INPUTS),
                       skills=DEMOTECH_SKILLS)
    result = _recs(profile)
    demotech = _item(result, DEMOTECH)
    check(demotech["status"] == "NOT_RECOMMENDED", "status NOT_RECOMMENDED",
          repr(demotech["status"]))
    check(demotech["eligibility_status"] == "NOT_ELIGIBLE",
          "eligibility status NOT_ELIGIBLE")


def test_ranking():
    print("[10] Recommendation ranking (score desc within bucket)")
    result = _recs(_strong_profile())
    groups = result["recommendations"]
    for bucket in ("recommended", "eligible", "incomplete",
                   "not_recommended"):
        scores = [i["recommendation_score"] for i in groups[bucket]]
        check(scores == sorted(scores, reverse=True),
              f"{bucket} sorted by score desc", str(scores))


def test_score_range():
    print("[11] Recommendation score range 0-100")
    for profile in (_strong_profile(), _weak_profile(),
                    _profile(cgpa=None, ml_inputs=dict(COMPLETE_ML_INPUTS))):
        for item in _all_items(_recs(profile)):
            check(0.0 <= item["recommendation_score"] <= 100.0,
                  "score in 0-100", str(item["recommendation_score"]))


def test_readiness_integration():
    print("[12] Readiness integration")
    from app.services.readiness_service import get_readiness
    profile = _strong_profile()
    readiness = get_readiness(profile["profile_id"])
    result = _recs(profile)
    for item in _all_items(result):
        check(item["readiness_score"] == readiness["readiness_score"],
              "readiness score matches Phase 12",
              f"{item['readiness_score']} vs {readiness['readiness_score']}")
        check(item["readiness_level"] == readiness["readiness_level"],
              "readiness level matches Phase 12")
        break  # one item is enough; all use the same readiness


def test_ml_probability_integration():
    print("[13] ML probability integration")
    # Complete ML profile -> probability present, 0-1
    result = _recs(_strong_profile())
    demotech = _item(result, DEMOTECH)
    p = demotech["placement_probability"]
    check(p is not None and 0.0 <= p <= 1.0, "probability present, 0-1",
          repr(p))
    # Incomplete ML profile -> probability None (never invented)
    incomplete_ml = _profile(skills=DEMOTECH_SKILLS)  # no ml_inputs
    result2 = _recs(incomplete_ml)
    demotech2 = _item(result2, DEMOTECH)
    check(demotech2["placement_probability"] is None,
          "probability None when ML features missing")


def test_eligibility_override():
    print("[14] Required eligibility override")
    # A near-perfect student (every taxonomy skill + full ML inputs)
    # whose branch (ME) is NOT allowed by DemoTech.
    perfect_skills = [
        "Data Structures", "Algorithms", "DBMS", "Operating Systems",
        "Computer Networks", "OOP", "Python", "Git", "SQL",
        "Communication", "AWS", "Docker", "Machine Learning",
        "JavaScript", "HTML", "CSS",
    ]
    profile = _profile(branch="Mechanical", skills=perfect_skills,
                       ml_inputs=dict(COMPLETE_ML_INPUTS))
    result = _recs(profile)
    demotech = _item(result, DEMOTECH)
    check(demotech["status"] == "NOT_RECOMMENDED",
          "NOT_RECOMMENDED despite strong skills/readiness",
          f"score={demotech['recommendation_score']} "
          f"skills={demotech['skill_match']['score']}%")
    check(demotech["eligibility_status"] == "NOT_ELIGIBLE",
          "eligibility status NOT_ELIGIBLE")
    # The numerical score is still meaningful (eligibility=0 caps it,
    # but the other signals are strong) - the override is what
    # keeps it out of the recommended/eligible buckets.
    check(demotech["recommendation_score"] >= 50,
          "other signals score high (override demonstrated)",
          str(demotech["recommendation_score"]))
    check(any("branch" in reason.lower() for reason in demotech["reasons"]),
          "reason explains the branch failure",
          str(demotech["reasons"])[:120])
    # Same student with an allowed branch -> DemoTech is no longer
    # NOT_RECOMMENDED.
    profile2 = _profile(branch="CSE", skills=perfect_skills,
                        ml_inputs=dict(COMPLETE_ML_INPUTS))
    demotech2 = _item(_recs(profile2), DEMOTECH)
    check(demotech2["status"] != "NOT_RECOMMENDED",
          "allowed branch -> not NOT_RECOMMENDED",
          repr(demotech2["status"]))


def test_top_n_limit():
    print("[15] Top-N limit")
    profile = _strong_profile()
    result = _recs(profile, limit=2)
    total = len(_all_items(result))
    check(total <= 2, "limit=2 caps total items", str(total))
    # Priority order: the recommended bucket is preserved first.
    groups = result["recommendations"]
    check(len(groups["recommended"]) == 1,
          "recommended bucket fully preserved under limit",
          str(len(groups["recommended"])))
    check(total == 2, "total capped at limit", str(total))
    # A larger limit returns everything
    result_all = _recs(profile, limit=50)
    check(len(_all_items(result_all)) == 7, "limit=50 returns all 7",
          str(len(_all_items(result_all))))


def test_empty_recommendation():
    print("[16] Empty recommendation scenario")
    result = _recs(_weak_profile())
    groups = result["recommendations"]
    check(groups["recommended"] == [] and groups["eligible"] == [],
          "recommended and eligible empty for weak student")
    check(len(_all_items(result)) == 7, "all 7 companies still analyzed")


def test_explanations():
    print("[17] Explanation generation")
    strong = _recs(_strong_profile())
    weak = _recs(_weak_profile())
    incomplete = _recs(_profile(cgpa=None, ml_inputs=dict(COMPLETE_ML_INPUTS)))

    demotech = _item(strong, DEMOTECH)
    check(demotech["reasons"], "recommended item has reasons")
    check(any("All mandatory eligibility requirements satisfied" in r
              for r in demotech["reasons"]), "recommended reason present")
    check(any("Model-estimated placement probability" in r
              for r in demotech["reasons"]),
          "probability labeled as model-estimated",
          str(demotech["reasons"]))

    for item in weak["recommendations"]["not_recommended"]:
        check(item["reasons"] and any(
            r.startswith("Not recommended because") for r in item["reasons"]),
            "not-recommended reason explains why",
            str(item["reasons"])[:100])
        break

    for item in incomplete["recommendations"]["incomplete"]:
        check(any("not enough information" in r.lower()
                  or "cannot be confirmed" in r.lower()
                  for r in item["reasons"]),
              "incomplete reason says eligibility unconfirmed",
              str(item["reasons"])[:100])
        break


def test_improvement_actions():
    print("[18] Improvement actions")
    profile = _profile(skills=["Python", "SQL", "AWS", "Docker"],
                       ml_inputs=dict(COMPLETE_ML_INPUTS))
    demotech = _item(_recs(profile), DEMOTECH)
    check(demotech["improvement_actions"] ==
          ["Strengthen Data Structures knowledge"],
          "action for each missing required skill",
          str(demotech["improvement_actions"]))
    # No missing required skills -> no actions
    strong = _item(_recs(_strong_profile()), DEMOTECH)
    check(strong["improvement_actions"] == [], "no actions when complete")


def test_normalization_reuse():
    print("[19] Skill normalization reuse (Phase 12 taxonomy)")
    # "js" -> JavaScript (WebTech requires it)
    profile = _profile(skills=["js", "html", "css", "reactjs"],
                       ml_inputs=dict(COMPLETE_ML_INPUTS))
    result = _recs(profile)
    webtech = _item(result, WEBTECH)
    check("JavaScript" in webtech["skill_match"]["required_matched"],
          "js normalized to JavaScript -> matched",
          str(webtech["skill_match"]["required_matched"]))
    check("React" in webtech["skill_match"]["preferred_matched"],
          "reactjs normalized to React -> matched")


def test_service_suite():
    print("=" * 60)
    print("SERVICE-LEVEL TESTS (PHASE 14)")
    print("=" * 60)
    test_strong_eligible()
    test_weak_student()
    test_incomplete_profile()
    test_unverified()
    test_unknown_profile()
    test_skill_matching()
    test_required_skill_missing()
    test_preferred_skill_missing()
    test_eligibility_failure()
    test_ranking()
    test_score_range()
    test_readiness_integration()
    test_ml_probability_integration()
    test_eligibility_override()
    test_top_n_limit()
    test_empty_recommendation()
    test_explanations()
    test_improvement_actions()
    test_normalization_reuse()


# ------------------------------------------------------------
# HTTP-LEVEL TESTS (require a running server)
# ------------------------------------------------------------


def _http_verified_profile():
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
    print("HTTP-LEVEL TESTS (PHASE 14)")
    print("=" * 60)

    status, body = http_get(f"{API_URL}/health")
    check(status == 200 and body.get("status") == "ok", "GET /health")

    # --- [20] Phase 8 prediction -----------------------------------
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
          "[20] POST /api/predict still works", f"status={status}")

    # --- [21] Phase 9 resume extraction -----------------------------
    pdf = make_pdf(COMPLETE_RESUME.splitlines())
    status, body = multipart_post(
        f"{API_URL}/api/resume/upload", "file", "resume.pdf", pdf,
        "application/pdf",
    )
    check(status == 200 and body.get("success") is True,
          "[21] POST /api/resume/upload still works", f"status={status}")

    # --- [22] Phase 10 profile flow ----------------------------------
    pid = _http_verified_profile()
    status, body = http_get(f"{API_URL}/api/profile/{pid}")
    check(status == 200 and body["profile"]["verified"] is True,
          "[22] Phase 10 profile flow still works", f"status={status}")

    # --- [23] Phase 11 prediction flow -------------------------------
    status, body = http_post_json(f"{API_URL}/api/profile/{pid}/predict", {})
    check(status == 200 and body["ready_for_prediction"] is True,
          "[23] Phase 11 prediction flow still works", f"status={status}")

    # --- [24] Phase 12 readiness -------------------------------------
    status, body = http_get(f"{API_URL}/api/profile/{pid}/readiness")
    check(status == 200 and 0 <= body["readiness_score"] <= 100,
          "[24] Phase 12 readiness still works", f"status={status}")

    # --- [25] Phase 13 eligibility -----------------------------------
    status, body = http_get(f"{API_URL}/api/profile/{pid}/eligibility")
    check(status == 200 and set(body) == {"eligible", "not_eligible",
                                          "incomplete"},
          "[25] Phase 13 eligibility still works", f"status={status}")

    # --- New: recommendations ----------------------------------------
    status, body = http_get(f"{API_URL}/api/profile/{pid}/recommendations")
    check(status == 200 and "recommendations" in body,
          "GET /api/profile/{id}/recommendations", f"status={status}")
    if status == 200:
        groups = body["recommendations"]
        check(set(groups) == {"recommended", "eligible", "incomplete",
                              "not_recommended"}, "4 buckets present")
        check(groups["recommended"], "recommended non-empty for strong profile")
        demotech = next((i for i in groups["recommended"]
                         if i["company_id"] == "company_001"), None)
        check(demotech is not None and demotech["status"] == "RECOMMENDED",
              "DemoTech recommended")
        check(0.0 <= demotech["recommendation_score"] <= 100.0,
              "score in range")
        check(demotech["placement_probability"] is not None,
              "ML probability present")
        check(demotech["reasons"], "reasons present")
        check("skill_match" in demotech, "skill match present")

    # --- New: ?limit=3 ------------------------------------------------
    status, body = http_get(
        f"{API_URL}/api/profile/{pid}/recommendations?limit=3")
    check(status == 200, "recommendations?limit=3 works", f"status={status}")
    if status == 200:
        total = sum(len(body["recommendations"][k])
                    for k in ("recommended", "eligible", "incomplete",
                              "not_recommended"))
        check(total <= 3, "limit=3 caps total", str(total))

    # --- New: invalid limits -> 422 ------------------------------------
    status, _ = http_get(f"{API_URL}/api/profile/{pid}/recommendations?limit=0")
    check(status == 422, "limit=0 -> 422", f"status={status}")
    status, _ = http_get(
        f"{API_URL}/api/profile/{pid}/recommendations?limit=999")
    check(status == 422, "limit=999 -> 422", f"status={status}")

    # --- New: unverified profile -> 422 --------------------------------
    status2, body2 = multipart_post(
        f"{API_URL}/api/profile/from-resume", "file", "resume.pdf", pdf,
        "application/pdf",
    )
    pid2 = body2["profile"]["profile_id"]
    status2, _ = http_get(f"{API_URL}/api/profile/{pid2}/recommendations")
    check(status2 == 422, "unverified recommendations -> 422",
          f"status={status2}")

    # --- New: unknown profile -> 404 -----------------------------------
    status2, _ = http_get(f"{API_URL}/api/profile/nope/recommendations")
    check(status2 == 404, "unknown profile recommendations -> 404",
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
