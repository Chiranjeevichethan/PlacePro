# ============================================================
# PLACEPRO - PHASE 9 - RESUME UPLOAD TEST SUITE
# ============================================================
#
# Plain-python tests (no pytest/requests dependency):
#   python backend/tests/test_resume.py
#
# Service-level tests always run. HTTP tests run when a server is
# reachable at PLACEPRO_API_URL (default http://127.0.0.1:8000).
#
# Coverage (per Phase 9 spec):
#   1. Valid PDF          6. Resume with complete information
#   2. Valid DOCX         7. Resume with missing information
#   3. Unsupported file   8. Multiple projects
#   4. Empty file         9. Multiple internships
#   5. Corrupted file
#   + GET /health and POST /api/predict (Phase 8 regression)
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

# Make backend/ (app.*) and project root (src.*) importable
BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BACKEND_ROOT)
sys.path.insert(0, BACKEND_ROOT)
sys.path.insert(0, PROJECT_ROOT)

API_URL = os.environ.get("PLACEPRO_API_URL", "http://127.0.0.1:8000")
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

# ------------------------------------------------------------
# SAMPLE RESUMES (ASCII so they embed cleanly in the test PDF)
# ------------------------------------------------------------

COMPLETE_RESUME = """John Doe
Bengaluru, Karnataka
john.doe@gmail.com
+91 98765 43210
linkedin.com/in/johndoe
github.com/johndoe

EDUCATION
B.Tech in Computer Science, IIT Delhi, CGPA: 8.2, 2022-2026

SKILLS
Python, Java, SQL, Django, React, MySQL, AWS, Docker, Git, TensorFlow

EXPERIENCE
Software Engineer, Google, 2022-2024
- Built scalable microservices
Technologies: Python, Go, Kubernetes

INTERNSHIPS
Summer Intern, Microsoft, 2023
- Worked on Azure cloud features

PROJECTS
- Project Alpha - A web dashboard for analytics
  Technologies: React, Node.js, MongoDB
- Project Beta - An ML chatbot
  Technologies: Python, TensorFlow

CERTIFICATIONS
AWS Certified Solutions Architect, Amazon, 2023

ACHIEVEMENTS
- Winner, Smart India Hackathon 2024
- LeetCode rating 1800
"""

MISSING_INFO_RESUME = """Bob Smith
bob.smith@gmail.com
+91 99887 76655

EDUCATION
B.Sc in Computer Science, Mumbai University, 2019-2023

SKILLS
Java, Spring Boot, MySQL
"""

MULTIPLE_PROJECTS_RESUME = """Alice Johnson
alice.johnson@gmail.com

EDUCATION
B.Tech in Information Technology, VIT Vellore, CGPA: 9.0, 2023-2027

SKILLS
Python, Flask, MongoDB

PROJECTS
- Weather App - A real-time weather dashboard
  Technologies: Python, Flask
- Chat Bot - A rule-based chatbot
  Technologies: Python
- Portfolio Site - Personal website
  Technologies: HTML, CSS
"""

MULTIPLE_INTERNSHIPS_RESUME = """Jane Smith
jane.smith@gmail.com
+91 91234 56789

EDUCATION
B.E. in Electronics, NIT Trichy, CGPA: 7.8, 2020-2024

INTERNSHIPS
Software Development Intern, Amazon, 2023
- Built payment APIs
Machine Learning Intern, Flipkart, 2024
- Built a recommendation model
"""

REPORTED_PARSER_REGRESSION_RESUME = """Priya Sharma
priya.sharma@example.com
+91 90000 11111
Portfolio: Not provided

EDUCATION
B.E. in Information Science, City Engineering College, CGPA: 8.4, 2021-2025

SKILLS
Python, SQL, Power BI, Git

INTERNSHIP EXPERIENCE
Data Analytics Intern | DataMinds Analytics
May 2024 - July 2024
- Cleaned datasets and built Power BI dashboards
- Analyzed sales trends using Python and SQL

CERTIFICATIONS
Google Data Analytics Professional Certificate, Coursera, 2024
Python for Data Science, IBM, 2023

HACKATHONS
Finalist, College Data Hackathon 2024

OPEN SOURCE
Contributed bug fixes to an open-source analytics dashboard

EXTRACURRICULAR ACTIVITIES
Volunteer coordinator for college tech club
"""

COMPREHENSIVE_FAKE_RESUME_REGRESSION = """Riya Sharma
riya.sharma@example.com
Portfolio: Not provided

EDUCATION
B.E. in Computer Science, City Engineering College, CGPA: 8.4, 2022-2026

SKILLS
Python, SQL

INTERNSHIP EXPERIENCE
Role: Data Analytics Intern (fictional test entry) Duration:
January 2026 - March 2026
- Queried reports using SQL

PROJECTS
- Student Placement Dashboard - A placement analytics dashboard
- Resume Matcher - Matches resumes to jobs
- Campus Events Portal - Lists campus events

CERTIFICATIONS
SQL for Data Analysis
Python Fundamentals

HACKATHONS AND ACHIEVEMENTS
- Participated in the City Innovation Hackathon
- Dashboard project showcase achievement

EXTRACURRICULAR ACTIVITIES
- Member of the Student Technology Club
- Led peer programming activities

OPEN-SOURCE CONTRIBUTIONS
- Contributed documentation improvements to an open-source project

REFERENCES
Not provided
"""

# ------------------------------------------------------------
# FILE GENERATORS
# ------------------------------------------------------------


def make_pdf(lines):
    """Build a minimal single-page PDF containing the given text lines."""
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


def make_docx(text):
    """Build a DOCX containing the given text (one paragraph per line)."""
    import docx

    document = docx.Document()
    for line in text.splitlines():
        if line.strip():
            document.add_paragraph(line)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


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


def test_valid_pdf():
    print("[1] Valid PDF")
    from app.services.resume_service import process_resume_upload
    content = make_pdf(COMPLETE_RESUME.splitlines())
    result = process_resume_upload("resume.pdf", content, "application/pdf")
    check(result["success"] is True, "success flag", str(result)[:200])
    check(result["file_type"] == "pdf", "file_type")
    check(result["extraction"]["page_count"] == 1, "page_count == 1",
          str(result["extraction"]))
    check(result["extraction"]["extraction_success"] is True, "extraction_success")
    p = result["extracted_profile"]
    check(p["name"] == "John Doe", "name", repr(p["name"]))
    check(p["email"] == "john.doe@gmail.com", "email", repr(p["email"]))
    check(p["phone"] == "+91 98765 43210", "phone", repr(p["phone"]))
    check(p["github"] == "github.com/johndoe", "github", repr(p["github"]))
    check(p["education"]["cgpa"] == 8.2, "cgpa 8.2",
          repr(p["education"]["cgpa"]))
    check(p["education"]["degree"] == "B.Tech", "degree", repr(p["education"]["degree"]))
    check(len(p["projects"]) == 2, "2 projects", str(len(p["projects"])))
    check(len(p["internships"]) == 1, "1 internship")
    check(len(p["certifications"]) == 1, "1 certification")
    check(p["certifications"][0]["year"] == 2023, "cert year")
    return result


def test_valid_docx():
    print("[2] Valid DOCX")
    from app.services.resume_service import process_resume_upload
    content = make_docx(COMPLETE_RESUME)
    result = process_resume_upload("resume.docx", content, DOCX_MIME)
    check(result["success"] is True, "success flag", str(result)[:200])
    check(result["file_type"] == "docx", "file_type")
    check(result["extraction"]["page_count"] is None,
          "page_count is None for DOCX", str(result["extraction"]))
    p = result["extracted_profile"]
    check(p["email"] == "john.doe@gmail.com", "email", repr(p["email"]))
    check(p["education"]["cgpa"] == 8.2, "cgpa", repr(p["education"]["cgpa"]))
    check(len(p["experience"]) == 1, "1 experience entry")
    check(p["experience"][0]["company"] == "Google", "experience company",
          repr(p["experience"][0]["company"]))
    return result


def test_unsupported_file():
    print("[3] Unsupported file")
    from app.services.resume_service import (
        UnsupportedFileTypeError,
        process_resume_upload,
    )
    try:
        process_resume_upload("notes.txt", b"plain text", "text/plain")
        check(False, "txt rejected")
    except UnsupportedFileTypeError:
        check(True, "txt rejected (415)")


def test_empty_file():
    print("[4] Empty file")
    from app.services.resume_service import EmptyFileError, process_resume_upload
    try:
        process_resume_upload("empty.pdf", b"", "application/pdf")
        check(False, "empty rejected")
    except EmptyFileError:
        check(True, "empty rejected (400)")


def test_corrupted_file():
    print("[5] Corrupted file")
    from app.services.resume_service import (
        CorruptedFileError,
        process_resume_upload,
    )
    # Magic bytes look like PDF but the body is garbage -> parse failure
    try:
        process_resume_upload("corrupt.pdf", b"%PDF-1.4\nthis is not a real pdf",
                              "application/pdf")
        check(False, "corrupt pdf rejected")
    except CorruptedFileError:
        check(True, "corrupt pdf rejected (422)")
    # Random bytes with a .docx extension -> magic byte mismatch
    try:
        process_resume_upload("fake.docx", b"not a zip at all", DOCX_MIME)
        check(False, "fake docx rejected")
    except CorruptedFileError:
        check(True, "fake docx rejected (422)")


def test_complete_information():
    print("[6] Complete resume information")
    from app.services.resume_parser import parse_resume
    profile, confidence, needs_verification = parse_resume(COMPLETE_RESUME)
    check(profile["name"] == "John Doe", "name")
    check(profile["email"] == "john.doe@gmail.com", "email")
    check(profile["phone"] == "+91 98765 43210", "phone")
    check(profile["location"] == "Bengaluru, Karnataka", "location",
          repr(profile["location"]))
    check(profile["linkedin"] == "linkedin.com/in/johndoe", "linkedin")
    check(profile["github"] == "github.com/johndoe", "github")
    check(profile["education"]["branch"] == "Computer Science", "branch")
    check(profile["education"]["college"] == "IIT Delhi", "college",
          repr(profile["education"]["college"]))
    check(profile["education"]["graduation_year"] == 2026, "grad year")
    skills = profile["skills"]
    check("Python" in skills["programming_languages"], "Python skill")
    check("React" in skills["frameworks"], "React skill")
    check("MySQL" in skills["databases"], "MySQL skill")
    check("AWS" in skills["cloud"], "AWS skill")
    check("TensorFlow" in skills["ai_ml"], "TensorFlow skill")
    check(profile["experience"][0]["role"] == "Software Engineer", "exp role")
    check(profile["experience"][0]["company"] == "Google", "exp company")
    check(profile["experience"][0]["duration"] == "2022-2024", "exp duration")
    check(profile["internships"][0]["company"] == "Microsoft", "intern company")
    check(profile["projects"][0]["project_name"] == "Project Alpha", "project 1 name")
    check(profile["projects"][0]["description"] == "A web dashboard for analytics",
          "project 1 desc", repr(profile["projects"][0]["description"]))
    check(profile["certifications"][0]["name"] == "AWS Certified Solutions Architect",
          "cert name")
    check(profile["certifications"][0]["issuer"] == "Amazon", "cert issuer")
    check(profile["achievements"]["hackathons"] ==
          ["Winner, Smart India Hackathon 2024"], "hackathon achievement")
    check(profile["achievements"]["coding_achievements"] == ["LeetCode rating 1800"],
          "coding achievement")
    check(confidence["email"] > 0.9, "email confidence heuristic > 0.9",
          str(confidence["email"]))


def test_missing_information():
    print("[7] Resume with missing information")
    from app.services.resume_parser import parse_resume
    profile, confidence, needs_verification = parse_resume(MISSING_INFO_RESUME)
    check(profile["education"]["cgpa"] is None, "cgpa is None (not invented)")
    check(profile["github"] is None, "github is None (not invented)")
    check(profile["linkedin"] is None, "linkedin is None")
    check(profile["internships"] == [], "internships empty list")
    check(profile["experience"] == [], "experience empty list")
    check(profile["projects"] == [], "projects empty list")
    check("education.cgpa" in needs_verification, "cgpa flagged for verification")
    check(profile["education"]["college"] == "Mumbai University", "college")


def test_multiple_projects():
    print("[8] Resume with multiple projects")
    from app.services.resume_parser import parse_resume
    profile, _, _ = parse_resume(MULTIPLE_PROJECTS_RESUME)
    check(len(profile["projects"]) == 3, "3 projects extracted",
          str(len(profile["projects"])))
    check(profile["projects"][0]["project_name"] == "Weather App", "project 1")
    check(profile["projects"][1]["project_name"] == "Chat Bot", "project 2")
    check(profile["projects"][2]["project_name"] == "Portfolio Site", "project 3")
    check("Flask" in profile["projects"][0]["technologies"], "project 1 tech")
    check(profile["projects"][2]["technologies"] == ["HTML", "CSS"],
          "project 3 tech", str(profile["projects"][2]["technologies"]))


def test_multiple_internships():
    print("[9] Resume with multiple internships")
    from app.services.resume_parser import parse_resume
    profile, _, _ = parse_resume(MULTIPLE_INTERNSHIPS_RESUME)
    check(len(profile["internships"]) == 2, "2 internships extracted",
          str(len(profile["internships"])))
    check(profile["internships"][0]["company"] == "Amazon", "intern 1 company")
    check(profile["internships"][0]["role"] == "Software Development Intern",
          "intern 1 role", repr(profile["internships"][0]["role"]))
    check(profile["internships"][1]["company"] == "Flipkart", "intern 2 company")
    check(profile["internships"][1]["role"] == "Machine Learning Intern",
          "intern 2 role", repr(profile["internships"][1]["role"]))
    check(profile["education"]["degree"] == "B.E.", "degree", repr(profile["education"]["degree"]))


def test_reported_parser_regressions():
    print("[10] Reported resume parser regressions")
    from app.services.resume_parser import parse_resume
    profile, _, _ = parse_resume(REPORTED_PARSER_REGRESSION_RESUME)
    check(profile["portfolio"] is None, "Portfolio: Not provided stays None",
          repr(profile["portfolio"]))
    check(profile["education"]["degree"] == "B.E.", "B.E. degree still extracted",
          repr(profile["education"]["degree"]))
    check(len(profile["certifications"]) == 2, "certifications stop at next section",
          str(profile["certifications"]))
    check(profile["certifications"][0]["name"] ==
          "Google Data Analytics Professional Certificate", "cert 1 name",
          repr(profile["certifications"][0]["name"] if profile["certifications"] else None))
    check(len(profile["internships"]) == 1, "internship extracted",
          str(profile["internships"]))
    if profile["internships"]:
        check(profile["internships"][0]["role"] == "Data Analytics Intern",
              "internship role", repr(profile["internships"][0]["role"]))
        check(profile["internships"][0]["company"] == "DataMinds Analytics",
              "internship organization", repr(profile["internships"][0]["company"]))
        check(profile["internships"][0]["duration"] == "May 2024 - July 2024",
              "internship duration", repr(profile["internships"][0]["duration"]))
        check("Python" in profile["internships"][0]["technologies"],
              "internship responsibilities scanned for technologies",
              str(profile["internships"][0]["technologies"]))
    check(profile["achievements"]["hackathons"] ==
          ["Finalist, College Data Hackathon 2024"], "hackathon extracted",
          str(profile["achievements"]["hackathons"]))
    check(profile["achievements"]["coding_achievements"] ==
          ["Contributed bug fixes to an open-source analytics dashboard"],
          "open-source section mapped to coding achievements",
          str(profile["achievements"]["coding_achievements"]))
    check(profile["achievements"]["awards"] ==
          ["Volunteer coordinator for college tech club"],
          "extracurricular section preserved in supported achievements field",
          str(profile["achievements"]["awards"]))


def test_comprehensive_fake_resume_regressions():
    print("[11] Comprehensive fake resume parser regressions")
    from app.services.resume_parser import parse_resume
    profile, _, _ = parse_resume(COMPREHENSIVE_FAKE_RESUME_REGRESSION)
    check(profile["portfolio"] is None, "missing portfolio remains None")
    check(profile["education"]["degree"] == "B.E.", "education degree preserved")
    check(len(profile["projects"]) == 3, "all three projects preserved",
          str(profile["projects"]))
    check([c["name"] for c in profile["certifications"]] ==
          ["SQL for Data Analysis", "Python Fundamentals"],
          "only the two certification entries extracted",
          str(profile["certifications"]))
    check(len(profile["internships"]) == 1, "internship extracted",
          str(profile["internships"]))
    if profile["internships"]:
        internship = profile["internships"][0]
        check(internship["role"] == "Data Analytics Intern",
              "role label and parenthetical note removed", repr(internship["role"]))
        check(internship["company"] is None,
              "company left null when absent", repr(internship["company"]))
        check(internship["duration"] == "January 2026 - March 2026",
              "standalone duration extracted", repr(internship["duration"]))
    check(profile["achievements"]["hackathons"] ==
          ["Participated in the City Innovation Hackathon"],
          "hackathon entry routed to hackathons",
          str(profile["achievements"]["hackathons"]))
    check(profile["achievements"]["awards"] == [
          "Dashboard project showcase achievement",
          "Member of the Student Technology Club",
          "Led peer programming activities",
          ], "achievement and extracurricular details preserved without references",
          str(profile["achievements"]["awards"]))
    check(profile["achievements"]["coding_achievements"] == [
          "Contributed documentation improvements to an open-source project",
          ], "open-source contribution preserved in coding achievements",
          str(profile["achievements"]["coding_achievements"]))
    all_achievements = sum(profile["achievements"].values(), [])
    check("REFERENCES" not in all_achievements and
          "Not provided" not in all_achievements,
          "reference heading and missing text excluded",
          str(all_achievements))


def test_service_suite():
    print("=" * 60)
    print("SERVICE-LEVEL TESTS")
    print("=" * 60)
    test_valid_pdf()
    test_valid_docx()
    test_unsupported_file()
    test_empty_file()
    test_corrupted_file()
    test_complete_information()
    test_missing_information()
    test_multiple_projects()
    test_multiple_internships()
    test_reported_parser_regressions()
    test_comprehensive_fake_resume_regressions()


# ------------------------------------------------------------
# HTTP-LEVEL TESTS (require a running server)
# ------------------------------------------------------------


def test_http_suite():
    print("\n" + "=" * 60)
    print("HTTP-LEVEL TESTS")
    print("=" * 60)

    # --- GET /health ------------------------------------------------
    status, body = http_get(f"{API_URL}/health")
    check(status == 200 and body.get("status") == "ok", "GET /health",
          f"status={status} body={body}")

    # --- POST /api/predict (Phase 8 regression) --------------------
    profile = {
        "branch": "CSE", "college_tier": "Tier-1", "cgpa": 8.5,
        "backlogs": 0, "coding_skills": 8.2, "dsa_score": 8.0,
        "aptitude_score": 85.0, "communication_skills": 7.5,
        "ml_knowledge": 6.5, "system_design": 5.0, "internships": 2,
        "projects_count": 4, "certifications": 2, "hackathons": 1,
        "open_source_contributions": 1, "extracurriculars": 1,
    }
    status, body = http_post_json(f"{API_URL}/api/predict", profile)
    check(status == 200 and body.get("prediction") in ("PLACED", "NOT PLACED"),
          "POST /api/predict (Phase 8 regression)",
          f"status={status} body={body}")

    # --- POST /api/resume/upload: valid PDF ------------------------
    pdf = make_pdf(COMPLETE_RESUME.splitlines())
    status, body = multipart_post(
        f"{API_URL}/api/resume/upload", "file", "resume.pdf", pdf,
        "application/pdf",
    )
    check(status == 200 and body.get("success") is True, "upload valid PDF",
          f"status={status} {str(body)[:200]}")
    if status == 200:
        check(body["extracted_profile"]["email"] == "john.doe@gmail.com",
              "PDF email extracted", repr(body["extracted_profile"].get("email")))
        check(body["extracted_profile"]["education"]["cgpa"] == 8.2,
              "PDF cgpa extracted")
        check(body["extraction"]["page_count"] == 1, "PDF page_count")

    # --- POST /api/resume/upload: valid DOCX -----------------------
    docx_bytes = make_docx(COMPLETE_RESUME)
    status, body = multipart_post(
        f"{API_URL}/api/resume/upload", "file", "resume.docx", docx_bytes,
        DOCX_MIME,
    )
    check(status == 200 and body.get("success") is True, "upload valid DOCX",
          f"status={status} {str(body)[:200]}")
    if status == 200:
        check(body["file_type"] == "docx", "DOCX file_type")
        check(body["extraction"]["page_count"] is None, "DOCX page_count None")

    # --- Unsupported file -------------------------------------------
    status, body = multipart_post(
        f"{API_URL}/api/resume/upload", "file", "notes.txt",
        b"plain text", "text/plain",
    )
    check(status == 415, "unsupported file -> 415", f"status={status} {body}")

    # --- Empty file --------------------------------------------------
    status, body = multipart_post(
        f"{API_URL}/api/resume/upload", "file", "empty.pdf", b"",
        "application/pdf",
    )
    check(status == 400, "empty file -> 400", f"status={status} {body}")

    # --- Corrupted file ----------------------------------------------
    status, body = multipart_post(
        f"{API_URL}/api/resume/upload", "file", "corrupt.pdf",
        b"%PDF-1.4\nthis is not a real pdf", "application/pdf",
    )
    check(status == 422, "corrupted file -> 422", f"status={status} {body}")


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
