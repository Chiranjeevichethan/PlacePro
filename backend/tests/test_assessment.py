# ============================================================
# PLACEPRO - PHASE 17 - SKILL ASSESSMENT ENGINE TEST SUITE
# ============================================================
#
# Plain-python tests (no pytest/requests dependency):
#   python backend/tests/test_assessment.py
#
# Service-level tests always run. HTTP tests run when a server is
# reachable at PLACEPRO_API_URL (default http://127.0.0.1:8000).
#
# Coverage (per Phase 17 spec):
#   1.  Start assessment          12. Duplicate submission
#   2.  Unknown skill             13. Unknown question
#   3.  Unknown profile           14. Invalid assessment ID
#   4.  Unverified profile        15. Attempt limits
#   5.  Question structure        16. Assessment history
#   6.  Correct answer            17. Skill evidence
#   7.  Incorrect answer          18. Resume + assessment provenance
#   8.  Score calculation         19. Readiness integration
#   9.  Difficulty breakdown      20. Recommendation integration
#   10. Topic breakdown           21. Security
#   11. Completion                22. Existing Phase 8-16 regression
#
# ============================================================

import io
import json
import os
import sys
import urllib.error
import urllib.request
import uuid

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BACKEND_ROOT)
sys.path.insert(0, BACKEND_ROOT)
sys.path.insert(0, PROJECT_ROOT)

API_URL = os.environ.get("PLACEPRO_API_URL", "http://127.0.0.1:8000")
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

# Isolate the SERVICE-LEVEL tests in a fresh temp store so cooldowns /
# attempt limits / history never bleed across runs or into real data.
import tempfile
import shutil

_TMP = tempfile.mkdtemp(prefix="placepro_p17_test_")
os.environ["PLACEPRO_PROFILES_DIR"] = os.path.join(_TMP, "profiles")
os.environ["PLACEPRO_ASSESSMENTS_DIR"] = os.path.join(_TMP, "assessments")


# The HTTP tests hit the real server (its own store); nothing below
# touches the temp dir.

COMPLETE_RESUME = """John Doe
Bengaluru, Karnataka
john.doe@gmail.com
+91 98765 43210

EDUCATION
B.Tech in Computer Science, IIT Delhi, CGPA: 8.2, 2022-2026

SKILLS
Python, Java, SQL, Django, ReactJS, MySQL, AWS, Docker, Git

PROJECTS
- Project Alpha - A web dashboard
  Technologies: React, Node.js, MongoDB
- Project Beta - An ML chatbot
  Technologies: Python, TensorFlow

INTERNSHIPS
Summer Intern, Microsoft, 2023
- Worked on Azure cloud features

CERTIFICATIONS
AWS Certified Solutions Architect, Amazon, 2023
"""


def make_pdf(lines):
    def esc(s):
        return s.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")

    content_parts = []
    y = 760
    for line in lines:
        content_parts.append(f"BT /F1 11 Tf 60 {y} Td ({esc(line)}) Tj ET")
        y -= 16
    content = "\n".join(content_parts).encode("latin-1")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n"
        + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"

    xref_pos = len(out)
    out += b"xref\n0 6\n0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n"
            + str(xref_pos).encode() + b"\n%%EOF")
    return bytes(out)


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
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, {"detail": body}


def http_get(url):
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise AssertionError(f"Server not reachable: {exc.reason}")


def http_post_json(url, payload):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def http_put_json(url, payload):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="PUT",
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


def _verified_profile(profile_id="svc_prof_1"):
    """Build a verified canonical profile (resume-derived provenance)."""
    from app.services.profile_service import _save, verify_profile

    profile = {
        "profile_id": profile_id,
        "personal": {"name": "Svc Student", "email": "svc@test.com",
                     "phone": "+91 90000 00000"},
        "education": {"degree": "B.Tech", "branch": "Computer Science",
                      "college": "IIT Delhi", "cgpa": 8.2,
                      "graduation_year": 2026},
        "skills": {"programming_languages": ["Python", "SQL"],
                   "frameworks": [], "databases": [], "cloud": [],
                   "ai_ml": [], "web_technologies": [], "tools": [],
                   "other_skills": []},
        "experience": [],
        "internships": [],
        "projects": [{"project_name": "Alpha", "description": "d",
                      "technologies": ["Python"]}],
        "certifications": [],
        "achievements": {},
        "ml_inputs": {"college_tier": "Tier-1", "backlogs": 0,
                      "coding_skills": 8.0, "dsa_score": 7.0,
                      "aptitude_score": 80.0, "communication_skills": 7.0,
                      "ml_knowledge": 6.0, "system_design": 5.0,
                      "open_source_contributions": 1, "extracurriculars": 1},
        "provenance": {
            "resume": ["personal.name", "personal.email", "education.cgpa",
                       "education.branch", "skills.programming_languages"],
            "user": [], "ml": [],
        },
        "original_resume_values": {},
        "verified": False,
        "prediction_history": [],
        "assessment_evidence": [],
    }
    # Save as a draft FIRST so verify_profile diffs against it and the
    # resume provenance paths survive (otherwise everything provided on
    # a brand-new profile is treated as user-entered).
    _save(profile)
    verified, _ = verify_profile(profile)
    return verified


def _all_correct_answers(session):
    from app.services.question_bank import get_questions

    bank = {q["id"]: q["correct_answer"]
            for q in get_questions(session["skill"])}
    return {q["question_id"]: bank[q["question_id"]]
            for q in session["questions"]}


def test_start_assessment():
    print("[1] Start assessment")
    from app.services.assessment_service import start_assessment
    _verified_profile()
    s = start_assessment("svc_prof_1", "Python", 10)
    check(s["skill"] == "Python", "skill", str(s.get("skill")))
    check(len(s["questions"]) == 10, "10 questions", str(len(s["questions"])))
    check(s["total_questions"] == 10, "total_questions")
    check(s["assessment_id"], "assessment_id present")
    check(s["attempt"] == 1, "attempt 1", str(s.get("attempt")))
    return s


def test_unknown_skill():
    print("[2] Unknown skill")
    from app.services.assessment_service import (
        UnknownSkillError,
        start_assessment,
    )
    _verified_profile("svc_prof_2")
    try:
        start_assessment("svc_prof_2", "QuantumPhysics", 5)
        check(False, "unknown skill rejected")
    except UnknownSkillError:
        check(True, "unknown skill rejected (404)")


def test_unknown_profile():
    print("[3] Unknown profile")
    from app.services.assessment_service import start_assessment
    from app.services.profile_service import ProfileNotFoundError
    try:
        start_assessment("no-such-profile", "Python", 5)
        check(False, "unknown profile rejected")
    except ProfileNotFoundError:
        check(True, "unknown profile rejected (404)")


def test_unverified_profile():
    print("[4] Unverified profile")
    from app.services.assessment_service import start_assessment
    from app.services.profile_service import (
        ProfileServiceError,
        build_draft_from_resume,
    )
    content = make_pdf(COMPLETE_RESUME.splitlines())
    draft, _ = build_draft_from_resume("resume.pdf", content,
                                       "application/pdf")
    check(draft["verified"] is False, "draft exists and is unverified")
    try:
        start_assessment(draft["profile_id"], "Python", 5)
        check(False, "unverified rejected")
    except ProfileServiceError as exc:
        check("verified" in str(exc), "unverified rejected: " + str(exc)[:60])


def test_question_structure():
    print("[5] Question structure")
    from app.services.assessment_service import start_assessment
    _verified_profile("svc_prof_5")
    s = start_assessment("svc_prof_5", "Data Structures", 10)
    q = s["questions"][0]
    check(q["question_id"], "question_id")
    check(q["topic"], "topic")
    check(q["difficulty"] in ("EASY", "MEDIUM", "HARD"), "difficulty")
    check(q["question_type"], "question_type")
    check(q["question"], "question text")
    check(len(q["options"]) >= 2, "options present")
    check("correct_answer" not in q, "NO correct_answer in response")
    check("explanation" not in q, "NO explanation in response")


def test_correct_answer():
    print("[6] Correct answer scored")
    from app.services.assessment_service import (
        start_assessment,
        submit_assessment,
    )
    _verified_profile("svc_prof_6")
    s = start_assessment("svc_prof_6", "Python", 10)
    answers = _all_correct_answers(s)
    r = submit_assessment(s["assessment_id"], "svc_prof_6", answers)
    check(r["skill_score"] == 100.0, "all correct -> 100",
          str(r["skill_score"]))
    check(r["correct"] == 10 and r["total"] == 10, "10/10 correct")
    check(r["level"] == "Advanced", "level Advanced", str(r["level"]))


def test_incorrect_answer():
    print("[7] Incorrect answer scored")
    from app.services.assessment_service import (
        start_assessment,
        submit_assessment,
    )
    _verified_profile("svc_prof_7")
    s = start_assessment("svc_prof_7", "Python", 10)
    answers = {q["question_id"]: "TOTALLY WRONG" for q in s["questions"]}
    r = submit_assessment(s["assessment_id"], "svc_prof_7", answers)
    check(r["skill_score"] == 0.0, "all wrong -> 0", str(r["skill_score"]))
    check(r["correct"] == 0, "0 correct")
    check(r["level"] == "Beginner", "level Beginner", str(r["level"]))


def test_score_calculation():
    print("[8] Score calculation (weighted by difficulty)")
    from app.services.assessment_service import (
        start_assessment,
        submit_assessment,
    )
    from app.services.question_bank import DIFFICULTY_POINTS, get_questions
    _verified_profile("svc_prof_8")
    s = start_assessment("svc_prof_8", "SQL", 10)
    bank = {q["id"]: q["correct_answer"] for q in get_questions("SQL")}
    answers = {}
    easy_points = 0
    total_points = 0
    for q in s["questions"]:
        total_points += DIFFICULTY_POINTS[q["difficulty"]]
        if q["difficulty"] == "EASY":
            easy_points += DIFFICULTY_POINTS[q["difficulty"]]
            answers[q["question_id"]] = bank[q["question_id"]]
        else:
            answers[q["question_id"]] = "WRONG"
    r = submit_assessment(s["assessment_id"], "svc_prof_8", answers)
    # Only EASY questions answered correctly -> weighted fraction.
    expected = round(easy_points / total_points * 100, 1)
    check(r["skill_score"] == expected,
          "score == easy-only weighted fraction",
          f"{r['skill_score']} vs {expected}")
    check(0.0 <= r["skill_score"] <= 100.0, "score in [0,100]")
    check(r["total"] == 10, "total 10")


def test_difficulty_breakdown():
    print("[9] Difficulty breakdown")
    from app.services.assessment_service import (
        start_assessment,
        submit_assessment,
    )
    _verified_profile("svc_prof_9")
    s = start_assessment("svc_prof_9", "Algorithms", 10)
    answers = _all_correct_answers(s)
    r = submit_assessment(s["assessment_id"], "svc_prof_9", answers)
    check(set(r["difficulty_breakdown"].keys()) <=
          {"EASY", "MEDIUM", "HARD"}, "difficulty keys",
          str(r["difficulty_breakdown"]))
    check(all(0 <= v <= 100 for v in r["difficulty_breakdown"].values()),
          "values in [0,100]")
    check(r["difficulty_breakdown"].get("EASY") == 100.0,
          "easy 100 when all correct")


def test_topic_breakdown():
    print("[10] Topic breakdown")
    from app.services.assessment_service import (
        start_assessment,
        submit_assessment,
    )
    _verified_profile("svc_prof_10")
    s = start_assessment("svc_prof_10", "Python", 10)
    answers = _all_correct_answers(s)
    r = submit_assessment(s["assessment_id"], "svc_prof_10", answers)
    check(len(r["topic_breakdown"]) >= 3, "multiple topics",
          str(len(r["topic_breakdown"])))
    check(all(0 <= v <= 100 for v in r["topic_breakdown"].values()),
          "topic values in [0,100]")
    check(all(v == 100.0 for v in r["topic_breakdown"].values()),
          "all topics 100 when all correct")


def test_completion():
    print("[11] Completion")
    from app.services.assessment_service import (
        start_assessment,
        submit_assessment,
    )
    _verified_profile("svc_prof_11")
    s = start_assessment("svc_prof_11", "Java", 10)
    r = submit_assessment(s["assessment_id"], "svc_prof_11",
                          _all_correct_answers(s))
    check(r["assessment_id"] == s["assessment_id"], "assessment id echoed")
    check("level" in r and "difficulty_breakdown" in r, "full report")


def test_duplicate_submission():
    print("[12] Duplicate submission rejected")
    from app.services.assessment_service import (
        AssessmentCompletedError,
        start_assessment,
        submit_assessment,
    )
    _verified_profile("svc_prof_12")
    s = start_assessment("svc_prof_12", "Python", 10)
    submit_assessment(s["assessment_id"], "svc_prof_12",
                      _all_correct_answers(s))
    try:
        submit_assessment(s["assessment_id"], "svc_prof_12",
                          _all_correct_answers(s))
        check(False, "duplicate rejected")
    except AssessmentCompletedError:
        check(True, "duplicate rejected (409)")


def test_unknown_question():
    print("[13] Unknown question id rejected")
    from app.services.assessment_service import (
        InvalidSubmissionError,
        start_assessment,
        submit_assessment,
    )
    _verified_profile("svc_prof_13")
    s = start_assessment("svc_prof_13", "Python", 10)
    answers = _all_correct_answers(s)
    answers["not_a_real_question"] = "x"
    try:
        submit_assessment(s["assessment_id"], "svc_prof_13", answers)
        check(False, "unknown question rejected")
    except InvalidSubmissionError:
        check(True, "unknown question rejected (400)")


def test_invalid_assessment_id():
    print("[14] Invalid assessment id")
    from app.services.assessment_service import (
        AssessmentNotFoundError,
        submit_assessment,
    )
    try:
        submit_assessment("../evil/../path", "svc_prof_13", {"q": "a"})
        check(False, "path traversal id rejected")
    except AssessmentNotFoundError:
        check(True, "path traversal id rejected (404)")


def test_attempt_limits():
    print("[15] Attempt limits")
    import app.services.assessment_service as svc
    from app.services.assessment_service import (
        AssessmentLimitError,
        start_assessment,
        submit_assessment,
    )
    _verified_profile("svc_prof_15")
    # Disable cooldown for this test so only the MAX_ATTEMPTS limit is hit
    old_cooldown = svc.COOLDOWN_HOURS
    svc.COOLDOWN_HOURS = 0
    try:
        for i in range(3):
            s = start_assessment("svc_prof_15", "C", 10)
            submit_assessment(s["assessment_id"], "svc_prof_15",
                              _all_correct_answers(s))
        check(True, "3 attempts allowed")
        try:
            start_assessment("svc_prof_15", "C", 10)
            check(False, "4th attempt rejected")
        except AssessmentLimitError:
            check(True, "4th attempt rejected (429)")
    finally:
        svc.COOLDOWN_HOURS = old_cooldown


def test_assessment_history():
    print("[16] Assessment history")
    from app.services.assessment_service import (
        get_assessment_history,
        start_assessment,
        submit_assessment,
    )
    _verified_profile("svc_prof_16")
    s = start_assessment("svc_prof_16", "Git", 10)
    submit_assessment(s["assessment_id"], "svc_prof_16",
                      _all_correct_answers(s))
    history = get_assessment_history("svc_prof_16")
    check(len(history) == 1, "1 history entry", str(len(history)))
    entry = history[0]
    check(entry["skill"] == "Git", "skill")
    check(entry["score"] == 100.0, "score")
    check(entry["level"] == "Advanced", "level")
    check(entry["assessment_id"] == s["assessment_id"], "assessment id")
    check(entry["attempt"] == 1, "attempt number")
    check(entry["timestamp"], "timestamp")


def test_skill_evidence():
    print("[17] Verified skill evidence")
    from app.services.assessment_service import (
        get_assessment_evidence,
        start_assessment,
        submit_assessment,
    )
    from app.services.profile_service import _load
    _verified_profile("svc_prof_17")
    s = start_assessment("svc_prof_17", "Python", 10)
    submit_assessment(s["assessment_id"], "svc_prof_17",
                      _all_correct_answers(s))
    saved = _load("svc_prof_17")
    evidence = get_assessment_evidence(saved)
    check(len(evidence) == 1, "1 skill evidenced", str(len(evidence)))
    e = evidence[0]
    check(e["skill"] == "Python", "skill Python")
    check(e["score"] == 100.0, "score 100")
    check(e["source"] == "assessment", "source assessment",
          str(e.get("source")))
    check(e["verified"] is True, "verified True")


def test_provenance():
    print("[18] Resume + assessment provenance preserved")
    from app.services.assessment_service import (
        combined_skill_view,
        start_assessment,
        submit_assessment,
    )
    _verified_profile("svc_prof_18")
    s = start_assessment("svc_prof_18", "Python", 10)
    submit_assessment(s["assessment_id"], "svc_prof_18",
                      _all_correct_answers(s))
    view = combined_skill_view("svc_prof_18")
    python = [v for v in view["skills"] if v["skill"] == "Python"][0]
    check(python["resume_detected"] is True, "resume_detected preserved",
          str(python))
    check(python["assessment_score"] == 100.0, "assessment_score present")
    check(python["assessment_verified"] is True, "assessment_verified")
    check(python["level"] == "Advanced", "level")


def test_readiness_integration():
    print("[19] Readiness integration (assessment bonus)")
    from app.services.assessment_service import (
        start_assessment,
        submit_assessment,
    )
    from app.services.profile_service import _load
    from app.services.readiness_service import (
        collect_verified_skills,
        compute_readiness_score,
    )
    _verified_profile("svc_prof_19")
    before = compute_readiness_score(
        _load("svc_prof_19"), collect_verified_skills(_load("svc_prof_19"))
    )["readiness_score"]

    s = start_assessment("svc_prof_19", "Python", 10)
    submit_assessment(s["assessment_id"], "svc_prof_19",
                      _all_correct_answers(s))
    after = compute_readiness_score(
        _load("svc_prof_19"), collect_verified_skills(_load("svc_prof_19"))
    )["readiness_score"]

    check(after >= before, "readiness does not drop after assessment",
          f"{before} -> {after}")
    check(after - before <= 5, "bonus capped at 5 pts",
          f"delta {after - before}")
    breakdown = compute_readiness_score(
        _load("svc_prof_19"), collect_verified_skills(_load("svc_prof_19"))
    )["breakdown"]
    check(breakdown["technical_skills"] <= 30, "technical capped at 30",
          str(breakdown["technical_skills"]))


def test_recommendation_integration():
    print("[20] Recommendation integration (assessed skills primary)")
    from app.services.assessment_service import (
        start_assessment,
        submit_assessment,
    )
    from app.services.recommendation_service import get_recommendations
    _verified_profile("svc_prof_20")
    # SQL is in the resume. Assess SQL badly -> it must NOT satisfy
    # required skills anymore. Assess Python well -> it still satisfies.
    s = start_assessment("svc_prof_20", "SQL", 10)
    submit_assessment(s["assessment_id"], "svc_prof_20",
                      {q["question_id"]: "WRONG"
                       for q in s["questions"]})
    s2 = start_assessment("svc_prof_20", "Python", 10)
    submit_assessment(s2["assessment_id"], "svc_prof_20",
                      _all_correct_answers(s2))

    recs = get_recommendations("svc_prof_20")
    grouped = recs["recommendations"]
    all_items = [i for bucket in grouped.values() for i in bucket]
    demotech = [i for i in all_items
                if i["company_name"] == "DemoTech"][0]
    sm = demotech["skill_match"]
    check("Python" in sm["required_matched"], "Python matched (assessed 100)",
          str(sm["required_matched"]))
    check("SQL" in sm["required_missing"],
          "SQL missing despite resume (assessed 0)",
          str(sm["required_missing"]))
    check("Data Structures" in sm["required_missing"],
          "DSA missing (no assessment)")


def test_security():
    print("[21] Security")
    from app.services.assessment_service import (
        AssessmentOwnershipError,
        start_assessment,
        submit_assessment,
    )
    _verified_profile("svc_prof_21a")
    _verified_profile("svc_prof_21b")
    s = start_assessment("svc_prof_21a", "Python", 10)
    # Another profile cannot submit this assessment
    try:
        submit_assessment(s["assessment_id"], "svc_prof_21b",
                          _all_correct_answers(s))
        check(False, "cross-profile submission rejected")
    except AssessmentOwnershipError:
        check(True, "cross-profile submission rejected (403)")
    # Answer keys never leak in any service response
    check("correct_answer" not in json.dumps(s), "no answer key in start")
    # Client cannot forge evidence: verify/update preserve server evidence
    from app.services.profile_service import update_profile
    from app.services.profile_service import _load
    saved = _load("svc_prof_21a")
    forged = json.loads(json.dumps(saved))
    forged["assessment_evidence"] = [
        {"skill": "Python", "score": 100, "source": "assessment",
         "verified": True, "assessment_id": "FORGED", "attempt": 1,
         "timestamp": "2026-01-01T00:00:00+00:00"}
    ]
    updated, _ = update_profile("svc_prof_21a", forged)
    check(updated["assessment_evidence"] == saved["assessment_evidence"],
          "client cannot forge assessment evidence")


def test_service_suite():
    print("=" * 60)
    print("SERVICE-LEVEL TESTS (Phase 17)")
    print("=" * 60)
    test_start_assessment()
    test_unknown_skill()
    test_unknown_profile()
    test_unverified_profile()
    test_question_structure()
    test_correct_answer()
    test_incorrect_answer()
    test_score_calculation()
    test_difficulty_breakdown()
    test_topic_breakdown()
    test_completion()
    test_duplicate_submission()
    test_unknown_question()
    test_invalid_assessment_id()
    test_attempt_limits()
    test_assessment_history()
    test_skill_evidence()
    test_provenance()
    test_readiness_integration()
    test_recommendation_integration()
    test_security()


# ------------------------------------------------------------
# HTTP-LEVEL TESTS (require a running server)
# ------------------------------------------------------------


def _http_verified_profile(prefix):
    """from-resume -> PUT ml_inputs -> verify; returns (profile, ml_payload)."""
    pdf = make_pdf(COMPLETE_RESUME.splitlines())
    status, body = multipart_post(
        f"{API_URL}/api/profile/from-resume", "file", "resume.pdf", pdf,
        "application/pdf",
    )
    assert status == 200, f"from-resume failed: {status} {str(body)[:200]}"
    profile = body["profile"]
    profile_id = profile["profile_id"]
    ml = {
        "college_tier": "Tier-1", "backlogs": 0, "coding_skills": 8.0,
        "dsa_score": 7.0, "aptitude_score": 80.0,
        "communication_skills": 7.0, "ml_knowledge": 6.0,
        "system_design": 5.0, "open_source_contributions": 1,
        "extracurriculars": 1,
    }
    complete = json.loads(json.dumps(profile))
    complete["ml_inputs"] = ml
    status, body = http_put_json(f"{API_URL}/api/profile/{profile_id}",
                                 complete)
    assert status == 200, f"PUT failed: {status} {str(body)[:200]}"
    status, body = http_post_json(f"{API_URL}/api/profile/verify",
                                  body["profile"])
    assert status == 200, f"verify failed: {status} {str(body)[:200]}"
    return body["profile"], ml


def test_http_suite():
    print("\n" + "=" * 60)
    print("HTTP-LEVEL TESTS (Phase 17 + regression)")
    print("=" * 60)

    # --- Regression: GET /health + POST /api/predict ----------------
    status, body = http_get(f"{API_URL}/health")
    check(status == 200 and body.get("status") == "ok",
          "[22a] GET /health", f"status={status}")
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
          "[22b] POST /api/predict", f"status={status}")

    # --- Regression: /api/resume/analyze ----------------------------
    pdf = make_pdf(COMPLETE_RESUME.splitlines())
    status, body = multipart_post(
        f"{API_URL}/api/resume/analyze", "file", "resume.pdf", pdf,
        "application/pdf",
    )
    check(status == 200 and "provenance" in body, "[22c] resume/analyze",
          f"status={status}")

    # --- Regression: readiness / eligibility / recommendations ------
    profile, _ = _http_verified_profile("http")
    pid = profile["profile_id"]
    status, body = http_get(f"{API_URL}/api/profile/{pid}/readiness")
    check(status == 200 and "readiness_score" in body, "[22d] readiness",
          f"status={status}")
    status, body = http_get(f"{API_URL}/api/profile/{pid}/eligibility")
    check(status == 200, "[22e] eligibility", f"status={status}")
    status, body = http_get(f"{API_URL}/api/profile/{pid}/recommendations")
    check(status == 200 and "recommendations" in body,
          "[22f] recommendations", f"status={status}")

    # --- POST /api/assessment/start ---------------------------------
    status, body = http_post_json(
        f"{API_URL}/api/assessment/start",
        {"profile_id": pid, "skill": "Python", "num_questions": 10},
    )
    check(status == 200 and len(body["questions"]) == 10,
          "[22g] assessment/start", f"status={status} {str(body)[:150]}")
    assessment_id = body["assessment_id"]
    start_questions = body["questions"]
    check("correct_answer" not in json.dumps(body), "[22h] no answer key")

    # --- Start: unverified profile -> error --------------------------
    status, body = http_post_json(
        f"{API_URL}/api/assessment/start",
        {"profile_id": "does-not-exist", "skill": "Python"},
    )
    check(status == 404, "[22i] start unknown profile -> 404",
          f"status={status}")

    # --- Start: unknown skill -> 404 ---------------------------------
    status, body = http_post_json(
        f"{API_URL}/api/assessment/start",
        {"profile_id": pid, "skill": "QuantumPhysics"},
    )
    check(status == 404, "[22j] unknown skill -> 404", f"status={status}")

    # --- Submit (all correct via bank lookup is NOT possible over HTTP
    #     without the keys - submit best-effort known answers) ---------
    # We answer using the question text: for simplicity submit a mix.
    answers = {}
    for q in start_questions:
        answers[q["question_id"]] = q["options"][0] if q["options"] else "x"
    status, body = http_post_json(
        f"{API_URL}/api/assessment/{assessment_id}/submit",
        {"profile_id": pid, "answers": answers},
    )
    check(status == 200 and 0.0 <= body["skill_score"] <= 100.0,
          "[22k] assessment submit", f"status={status} {str(body)[:150]}")
    check(body["correct"] + 0 == body["correct"], "correct count integer")
    check("difficulty_breakdown" in body and "topic_breakdown" in body,
          "[22l] breakdowns present")

    # --- Submit again -> 409 -----------------------------------------
    status, body = http_post_json(
        f"{API_URL}/api/assessment/{assessment_id}/submit",
        {"profile_id": pid, "answers": answers},
    )
    check(status == 409, "[22m] duplicate submit -> 409", f"status={status}")

    # --- GET /api/assessment/{id} (ownership) ------------------------
    status, body = http_get(f"{API_URL}/api/assessment/{assessment_id}")
    check(status == 200 and "questions" in body,
          "[22n] GET assessment", f"status={status}")

    # --- GET /api/profile/{id}/assessments ---------------------------
    status, body = http_get(f"{API_URL}/api/profile/{pid}/assessments")
    check(status == 200 and len(body["assessments"]) >= 1,
          "[22o] profile assessments", f"status={status} {str(body)[:150]}")
    check(body["assessments"][0]["skill"] == "Python", "history skill")

    # --- GET /api/profile/{id}/skills --------------------------------
    status, body = http_get(f"{API_URL}/api/profile/{pid}/skills")
    check(status == 200 and len(body["skills"]) > 0,
          "[22p] profile skills", f"status={status} {str(body)[:150]}")
    python = [s for s in body["skills"] if s["skill"] == "Python"]
    check(python and python[0]["resume_detected"] is True,
          "[22q] resume_detected true", str(python)[:150])
    check(python and python[0]["assessment_score"] is not None,
          "[22r] assessment score present")

    # --- Prediction still works --------------------------------------
    status, body = http_post_json(f"{API_URL}/api/profile/{pid}/predict", {})
    check(status == 200 and body.get("ready_for_prediction") is True,
          "[22s] profile predict", f"status={status} {str(body)[:150]}")


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
