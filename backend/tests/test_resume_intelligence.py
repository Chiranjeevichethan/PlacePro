# ============================================================
# PLACEPRO - PHASE 16 - RESUME INTELLIGENCE 2.0 TEST SUITE
# ============================================================
#
# Plain-python tests (no pytest/requests dependency):
#   python backend/tests/test_resume_intelligence.py
#
# Service-level tests always run. HTTP tests run when a server is
# reachable at PLACEPRO_API_URL (default http://127.0.0.1:8000).
#
# Coverage (per Phase 16 spec):
#   1.  valid PDF                 12. GitHub
#   2.  valid DOCX                13. LinkedIn
#   3.  empty document            14. branch extraction
#   4.  corrupted PDF             15. graduation year
#   5.  unsupported file          16. skill normalization (Phase 12 reuse)
#   6.  missing name              17. provenance
#   7.  missing CGPA              18. confidence
#   8.  multiple skills           19. manual override (edit -> user source)
#   9.  multiple projects         20. verification
#   10. multiple internships      21. OCR-required PDF
#   11. certifications            22. backward compatibility
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

# ------------------------------------------------------------
# SAMPLE RESUMES
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
Python, Java, SQL, Django, ReactJS, MySQL, AWS, Docker, Git, TensorFlow

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
B.E. in Electronics and Communication, NIT Trichy, CGPA: 7.8, 2020-2024

INTERNSHIPS
Software Development Intern, Amazon, 2023
- Built payment APIs
Machine Learning Intern, Flipkart, 2024
- Built a recommendation model
"""

NO_NAME_RESUME = """bob.smith@gmail.com
+91 99887 76655

EDUCATION
B.Sc in Computer Science, Mumbai University, CGPA: 7.5, 2019-2023

SKILLS
Java, MySQL
"""

# ------------------------------------------------------------
# FILE GENERATORS (same approach as Phase 9 tests)
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


def make_pdf_no_text():
    """A structurally valid PDF with NO text content (scanned-like)."""
    content = b""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R >>",
        b"<< /Length 0 >>\nstream\n\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref_pos = len(out)
    out += b"xref\n0 5\n0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (b"trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n"
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


def test_valid_pdf():
    print("[1] Valid PDF -> full intelligence analysis")
    from app.services.resume_intelligence import analyze_resume
    content = make_pdf(COMPLETE_RESUME.splitlines())
    analysis = analyze_resume("resume.pdf", content, "application/pdf")
    check(analysis["success"] is True, "success")
    check(analysis["file_type"] == "pdf", "file_type")
    check(analysis["extraction"]["page_count"] == 1, "page_count")
    check(analysis["extraction"]["ocr_required"] is False, "ocr_required False")
    p = analysis["extracted_profile"]
    check(p["name"] == "John Doe", "name", repr(p["name"]))
    check(p["email"] == "john.doe@gmail.com", "email")
    check(p["education"]["cgpa"] == 8.2, "cgpa")
    check(len(analysis["provenance"]) > 0, "provenance populated",
          str(len(analysis["provenance"])))
    check(analysis["diagnostics"]["word_count"] > 20, "word_count",
          str(analysis["diagnostics"].get("word_count")))
    check("education" in analysis["diagnostics"]["detected_sections"],
          "education section detected")
    check(analysis["diagnostics"]["ocr_required"] is False,
          "diagnostics.ocr_required False")
    return analysis


def test_valid_docx():
    print("[2] Valid DOCX -> full intelligence analysis")
    from app.services.resume_intelligence import analyze_resume
    content = make_docx(COMPLETE_RESUME)
    analysis = analyze_resume("resume.docx", content, DOCX_MIME)
    check(analysis["success"] is True, "success")
    check(analysis["file_type"] == "docx", "file_type")
    p = analysis["extracted_profile"]
    check(p["email"] == "john.doe@gmail.com", "email")
    check(p["education"]["cgpa"] == 8.2, "cgpa")
    check(analysis["extraction"]["ocr_required"] is False,
          "DOCX never OCR-flagged")
    return analysis


def test_empty_document():
    print("[3] Empty document rejected")
    from app.services.resume_intelligence import analyze_resume
    from app.services.resume_service import EmptyFileError
    try:
        analyze_resume("empty.pdf", b"", "application/pdf")
        check(False, "empty rejected")
    except EmptyFileError:
        check(True, "empty rejected (400)")


def test_corrupted_pdf():
    print("[4] Corrupted PDF rejected")
    from app.services.resume_intelligence import analyze_resume
    from app.services.resume_service import CorruptedFileError
    try:
        analyze_resume("corrupt.pdf", b"%PDF-1.4\nthis is not a real pdf",
                       "application/pdf")
        check(False, "corrupt rejected")
    except CorruptedFileError:
        check(True, "corrupt rejected (422)")


def test_unsupported_file():
    print("[5] Unsupported file rejected")
    from app.services.resume_intelligence import analyze_resume
    from app.services.resume_service import UnsupportedFileTypeError
    try:
        analyze_resume("notes.txt", b"plain text", "text/plain")
        check(False, "txt rejected")
    except UnsupportedFileTypeError:
        check(True, "txt rejected (415)")


def test_missing_name():
    print("[6] Missing name -> null (not invented)")
    from app.services.resume_parser import parse_resume
    profile, _, _ = parse_resume(NO_NAME_RESUME)
    check(profile["name"] is None, "name is None")
    check(profile["email"] == "bob.smith@gmail.com", "email still extracted")
    check(profile["education"]["cgpa"] == 7.5, "cgpa extracted")


def test_missing_cgpa():
    print("[7] Missing CGPA -> null (not invented)")
    from app.services.resume_parser import parse_resume
    profile, confidence, needs_verification = parse_resume(MISSING_INFO_RESUME)
    check(profile["education"]["cgpa"] is None, "cgpa is None")
    check("education.cgpa" in needs_verification, "cgpa flagged")
    from app.services.resume_intelligence import classify_confidence
    labels = classify_confidence(confidence)
    check(isinstance(labels, dict), "confidence labels returned")


def test_multiple_skills():
    print("[8] Multiple skills extracted")
    from app.services.resume_parser import parse_resume
    profile, _, _ = parse_resume(COMPLETE_RESUME)
    skills = profile["skills"]
    check("Python" in skills["programming_languages"], "Python")
    check("Java" in skills["programming_languages"], "Java")
    check("SQL" in skills["programming_languages"], "SQL")
    check("Django" in skills["frameworks"], "Django")
    check("AWS" in skills["cloud"], "AWS")
    check("TensorFlow" in skills["ai_ml"], "TensorFlow")


def test_multiple_projects():
    print("[9] Multiple projects extracted")
    from app.services.resume_parser import parse_resume
    profile, _, _ = parse_resume(MULTIPLE_PROJECTS_RESUME)
    check(len(profile["projects"]) == 3, "3 projects")
    check(profile["projects"][0]["project_name"] == "Weather App", "p1 name")
    check(profile["projects"][2]["project_name"] == "Portfolio Site", "p3 name")


def test_multiple_internships():
    print("[10] Multiple internships extracted")
    from app.services.resume_parser import parse_resume
    profile, _, _ = parse_resume(MULTIPLE_INTERNSHIPS_RESUME)
    check(len(profile["internships"]) == 2, "2 internships")
    check(profile["internships"][0]["company"] == "Amazon", "intern 1")
    check(profile["internships"][1]["company"] == "Flipkart", "intern 2")


def test_certifications():
    print("[11] Certifications extracted")
    from app.services.resume_parser import parse_resume
    profile, _, _ = parse_resume(COMPLETE_RESUME)
    check(len(profile["certifications"]) == 1, "1 certification")
    cert = profile["certifications"][0]
    check(cert["name"] == "AWS Certified Solutions Architect", "cert name",
          repr(cert["name"]))
    check(cert["issuer"] == "Amazon", "cert issuer")
    check(cert["year"] == 2023, "cert year")


def test_github():
    print("[12] GitHub extracted")
    from app.services.resume_parser import parse_resume
    profile, _, _ = parse_resume(COMPLETE_RESUME)
    check(profile["github"] == "github.com/johndoe", "github",
          repr(profile["github"]))
    check(profile["github"] is not None, "github not None")


def test_linkedin():
    print("[13] LinkedIn extracted")
    from app.services.resume_parser import parse_resume
    profile, _, _ = parse_resume(COMPLETE_RESUME)
    check(profile["linkedin"] == "linkedin.com/in/johndoe", "linkedin",
          repr(profile["linkedin"]))


def test_branch_extraction():
    print("[14] Branch extracted")
    from app.services.resume_parser import parse_resume
    profile, _, _ = parse_resume(COMPLETE_RESUME)
    check(profile["education"]["branch"] == "Computer Science", "branch",
          repr(profile["education"]["branch"]))


def test_graduation_year():
    print("[15] Graduation year extracted")
    from app.services.resume_parser import parse_resume
    profile, _, _ = parse_resume(COMPLETE_RESUME)
    check(profile["education"]["graduation_year"] == 2026, "grad year",
          repr(profile["education"]["graduation_year"]))


def test_skill_normalization():
    print("[16] Skill normalization reuses Phase 12 taxonomy")
    from app.services.skill_taxonomy import normalize_skill
    check(normalize_skill("js") == ["JavaScript"], "js -> JavaScript",
          str(normalize_skill("js")))
    check(normalize_skill("ReactJS") == ["React"], "ReactJS -> React",
          str(normalize_skill("ReactJS")))
    check(normalize_skill("ml") == ["Machine Learning"], "ml -> Machine Learning",
          str(normalize_skill("ml")))
    check(set(normalize_skill("DSA")) == {"Data Structures", "Algorithms"},
          "DSA -> Data Structures + Algorithms", str(normalize_skill("DSA")))
    # Unknown skills stay unmapped (never misclassified)
    check(normalize_skill("QuantumBoggle") == [], "unknown -> []")


def test_provenance():
    print("[17] Provenance (value + source + evidence)")
    from app.services.resume_intelligence import analyze_resume
    content = make_pdf(COMPLETE_RESUME.splitlines())
    analysis = analyze_resume("resume.pdf", content, "application/pdf")
    fields = {e["field"]: e for e in analysis["provenance"]}
    check("email" in fields, "email has provenance entry")
    check(fields["email"]["source"] == "resume", "email source=resume")
    check("education.cgpa" in fields, "cgpa has provenance entry")
    cgpa_entry = fields["education.cgpa"]
    check(cgpa_entry["value"] == 8.2, "cgpa value", str(cgpa_entry.get("value")))
    check(cgpa_entry["evidence"] is not None and "8.2" in cgpa_entry["evidence"],
          "cgpa evidence snippet contains the value",
          repr(cgpa_entry.get("evidence"))[:100])
    # Skills lists produce counted evidence
    skills_entry = fields.get("skills.programming_languages")
    if skills_entry:
        check(skills_entry["value"] == 3, "skills count evidence",
              str(skills_entry.get("value")))


def test_confidence():
    print("[18] Confidence labels (high/medium/low)")
    from app.services.resume_intelligence import analyze_resume
    content = make_pdf(COMPLETE_RESUME.splitlines())
    analysis = analyze_resume("resume.pdf", content, "application/pdf")
    labels = analysis["confidence"]
    check(labels.get("email") == "high", "email confidence high",
          str(labels.get("email")))
    check(labels.get("education.cgpa") == "high", "cgpa confidence high",
          str(labels.get("education.cgpa")))
    check(all(v in ("high", "medium", "low") for v in labels.values()),
          "all labels are high/medium/low")
    # Extraction confidence, never ML confidence
    check("ml_confidence" not in analysis, "no ML confidence claimed")


def test_manual_override():
    print("[19] Manual override -> user source + original preserved")
    from app.services.resume_service import process_resume_upload
    from app.services.profile_service import (
        build_draft_from_resume, update_profile, verify_profile,
    )
    content = make_pdf(COMPLETE_RESUME.splitlines())
    profile, _ = build_draft_from_resume("resume.pdf", content,
                                         "application/pdf")
    check(profile["original_resume_values"].get("education.cgpa") == 8.2,
          "original resume cgpa recorded",
          str(profile["original_resume_values"].get("education.cgpa")))
    check(profile["verified"] is False, "draft not verified")

    edited = json.loads(json.dumps(profile))
    edited["education"]["cgpa"] = 8.2  # student keeps the value
    edited["education"]["college"] = "Corrected University"
    updated, _ = update_profile(profile["profile_id"], edited)
    check(updated["verified"] is False, "edit resets verified")
    check("education.college" in updated["provenance"]["user"],
          "edited field -> provenance.user", str(updated["provenance"]["user"]))
    check(updated["original_resume_values"].get("education.cgpa") == 8.2,
          "original resume value preserved")

    # Explicit verification
    verified, _ = verify_profile(updated)
    check(verified["verified"] is True, "verify -> verified True")
    check("education.cgpa" in verified["provenance"]["resume"],
          "unchanged cgpa still provenance.resume")
    return verified


def test_verification():
    print("[20] Verification stays explicit (extracted != verified)")
    from app.services.resume_intelligence import analyze_resume
    content = make_pdf(COMPLETE_RESUME.splitlines())
    analysis = analyze_resume("resume.pdf", content, "application/pdf")
    check("verified" not in analysis["extracted_profile"],
          "analyze response has no verified flag (no profile created)")
    # Draft from resume: verified False until confirmed
    from app.services.profile_service import build_draft_from_resume
    profile, _ = build_draft_from_resume("resume.pdf", content,
                                         "application/pdf")
    check(profile["verified"] is False, "draft verified=False")


def test_ocr_required():
    print("[21] OCR-required PDF detected")
    from app.services.resume_service import _process_resume_upload_full
    pdf = make_pdf_no_text()
    response, raw_text = _process_resume_upload_full("scan.pdf", pdf,
                                                     "application/pdf")
    check(response["extraction"]["ocr_required"] is True, "ocr_required True")
    check(not raw_text.strip(), "no extractable text")
    check(response["extracted_profile"]["name"] is None,
          "no profile invented from scanned pdf")


def test_feature_availability():
    print("[21b] Feature availability classification (Phase 16 statuses)")
    from app.services.ml_feature_mapping import classify_feature_availability
    from app.services.profile_service import build_draft_from_resume
    content = make_pdf(COMPLETE_RESUME.splitlines())
    profile, _ = build_draft_from_resume("resume.pdf", content,
                                         "application/pdf")
    statuses = classify_feature_availability(profile)
    by_field = {s["field"]: s["status"] for s in statuses}
    check(len(statuses) == 16, "16 features classified", str(len(statuses)))
    check(by_field["cgpa"] == "AVAILABLE_FROM_RESUME", "cgpa available",
          by_field.get("cgpa"))
    check(by_field["internships"] == "AVAILABLE_FROM_RESUME",
          "internships available")
    check(by_field["dsa_score"] == "REQUIRES_MANUAL_INPUT",
          "dsa_score requires manual input")
    check(by_field["aptitude_score"] == "REQUIRES_MANUAL_INPUT",
          "aptitude requires manual input")
    check(by_field["coding_skills"] == "REQUIRES_MANUAL_INPUT",
          "coding_skills requires manual input (never inferred)")


def test_service_suite():
    print("=" * 60)
    print("SERVICE-LEVEL TESTS (Phase 16)")
    print("=" * 60)
    test_valid_pdf()
    test_valid_docx()
    test_empty_document()
    test_corrupted_pdf()
    test_unsupported_file()
    test_missing_name()
    test_missing_cgpa()
    test_multiple_skills()
    test_multiple_projects()
    test_multiple_internships()
    test_certifications()
    test_github()
    test_linkedin()
    test_branch_extraction()
    test_graduation_year()
    test_skill_normalization()
    test_provenance()
    test_confidence()
    test_manual_override()
    test_verification()
    test_ocr_required()
    test_feature_availability()


# ------------------------------------------------------------
# HTTP-LEVEL TESTS (require a running server)
# ------------------------------------------------------------


def test_http_suite():
    print("\n" + "=" * 60)
    print("HTTP-LEVEL TESTS (Phase 16 + regression)")
    print("=" * 60)

    # --- GET /health ------------------------------------------------
    status, body = http_get(f"{API_URL}/health")
    check(status == 200 and body.get("status") == "ok", "[22a] GET /health",
          f"status={status} body={body}")

    # --- POST /api/predict (Phase 8 regression) --------------------
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
          "[22b] POST /api/predict still works",
          f"status={status} body={body}")

    # --- POST /api/resume/upload (Phase 9 regression) --------------
    pdf = make_pdf(COMPLETE_RESUME.splitlines())
    status, body = multipart_post(
        f"{API_URL}/api/resume/upload", "file", "resume.pdf", pdf,
        "application/pdf",
    )
    check(status == 200 and body.get("success") is True,
          "[22c] POST /api/resume/upload still works",
          f"status={status} {str(body)[:200]}")
    if status == 200:
        check(body["extracted_profile"]["email"] == "john.doe@gmail.com",
              "upload email extracted")

    # --- POST /api/resume/analyze (NEW) -----------------------------
    status, body = multipart_post(
        f"{API_URL}/api/resume/analyze", "file", "resume.pdf", pdf,
        "application/pdf",
    )
    check(status == 200 and body.get("success") is True,
          "[22d] POST /api/resume/analyze works",
          f"status={status} {str(body)[:200]}")
    if status == 200:
        check(len(body["provenance"]) > 0, "analyze returns provenance")
        check("diagnostics" in body and "word_count" in body["diagnostics"],
              "analyze returns diagnostics")
        check("confidence" in body, "analyze returns confidence labels")
        check("extraction_summary" in body, "analyze returns summary")

    # --- Analyze: unsupported file -> 415 ---------------------------
    status, body = multipart_post(
        f"{API_URL}/api/resume/analyze", "file", "notes.txt",
        b"plain text", "text/plain",
    )
    check(status == 415, "[22e] analyze unsupported -> 415",
          f"status={status} {body}")

    # --- Analyze: corrupted file -> 422 -----------------------------
    status, body = multipart_post(
        f"{API_URL}/api/resume/analyze", "file", "corrupt.pdf",
        b"%PDF-1.4\nthis is not a real pdf", "application/pdf",
    )
    check(status == 422, "[22f] analyze corrupted -> 422",
          f"status={status} {body}")

    # --- Analyze: empty file -> 400 ---------------------------------
    status, body = multipart_post(
        f"{API_URL}/api/resume/analyze", "file", "empty.pdf", b"",
        "application/pdf",
    )
    check(status == 400, "[22g] analyze empty -> 400",
          f"status={status} {body}")

    # --- Analyze: OCR-required PDF -> 422 with OCR_REQUIRED ---------
    scan_pdf = make_pdf_no_text()
    status, body = multipart_post(
        f"{API_URL}/api/resume/analyze", "file", "scan.pdf", scan_pdf,
        "application/pdf",
    )
    check(status == 422 and "OCR_REQUIRED" in str(body),
          "[22h] OCR-required -> 422 OCR_REQUIRED",
          f"status={status} {str(body)[:200]}")

    # --- POST /api/profile/from-resume (enhanced, backward compat) --
    status, body = multipart_post(
        f"{API_URL}/api/profile/from-resume", "file", "resume.pdf", pdf,
        "application/pdf",
    )
    check(status == 200 and "profile" in body,
          "[22i] from-resume still works",
          f"status={status} {str(body)[:200]}")
    if status == 200:
        check(body["profile"]["verified"] is False, "draft unverified")
        check(body["profile"]["original_resume_values"].get("education.cgpa")
              == 8.2, "original_resume_values in draft",
              str(body["profile"].get("original_resume_values", {}).get(
                  "education.cgpa")))
        check(len(body.get("provenance", [])) > 0, "from-resume provenance")
        check("diagnostics" in body, "from-resume diagnostics")
        check("feature_availability" in body,
              "from-resume feature_availability")
        profile_id = body["profile"]["profile_id"]

        # --- PUT edit (manual override) ------------------------------
        edited = json.loads(json.dumps(body["profile"]))
        edited["education"]["cgpa"] = 8.9
        status, body2 = http_put_json(
            f"{API_URL}/api/profile/{profile_id}", edited)
        check(status == 200 and body2["profile"]["verified"] is False,
              "[22j] PUT edit works, verified reset",
              f"status={status} {str(body2)[:200]}")
        check("education.cgpa" in body2["profile"]["provenance"]["user"],
              "edited cgpa -> provenance.user")
        check(body2["profile"]["original_resume_values"].get("education.cgpa")
              == 8.2, "original resume cgpa 8.2 preserved",
              str(body2["profile"].get("original_resume_values", {}).get(
                  "education.cgpa")))

        # --- POST verify (explicit confirmation) ---------------------
        status, body3 = http_post_json(
            f"{API_URL}/api/profile/verify", body2["profile"])
        check(status == 200 and body3["profile"]["verified"] is True,
              "[22k] verify works", f"status={status} {str(body3)[:200]}")

        # --- Full ml_inputs + predict (Phase 11 regression) ----------
        ml = {
            "college_tier": "Tier-1", "backlogs": 0, "coding_skills": 8.2,
            "dsa_score": 8.0, "aptitude_score": 85.0,
            "communication_skills": 7.5, "ml_knowledge": 6.5,
            "system_design": 5.0, "open_source_contributions": 1,
            "extracurriculars": 1,
        }
        complete = json.loads(json.dumps(body3["profile"]))
        complete["ml_inputs"] = ml
        status, body4 = http_put_json(
            f"{API_URL}/api/profile/{profile_id}", complete)
        check(status == 200, "[22l] PUT ml_inputs",
              f"status={status} {str(body4)[:200]}")
        status, body5 = http_post_json(
            f"{API_URL}/api/profile/verify", body4["profile"])
        check(status == 200 and body5["profile"]["verified"] is True,
              "[22m] re-verify complete profile",
              f"status={status} {str(body5)[:200]}")
        status, body6 = http_post_json(
            f"{API_URL}/api/profile/{profile_id}/predict", {})
        check(status == 200 and body6.get("ready_for_prediction") is True
              and body6.get("prediction") in ("PLACED", "NOT PLACED"),
              "[22n] Phase 11 predict still works",
              f"status={status} {str(body6)[:200]}")
        if status == 200 and body6.get("ready_for_prediction"):
            check(0.0 <= body6["placement_probability"] <= 1.0,
                  "probability in [0,1]")


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
