# ============================================================
# PLACEPRO - PHASE 9 - RESUME PARSER
# ============================================================
#
# Two responsibilities:
#   1. extract_text()  - pull raw text out of PDF (pypdf) and
#                        DOCX (python-docx) bytes.
#   2. parse_resume()  - detect sections and extract structured
#                        information from the raw text.
#
# HONESTY RULES
#   - A field is returned ONLY when evidence exists in the text.
#     Missing values are None (scalars) or [] (lists). Nothing is
#     inferred, guessed, or converted into scores.
#   - Extraction confidence is a HEURISTIC (0..1), not a calibrated
#     probability. Uncertain fields are flagged via needs_verification.
#
# ============================================================

import io
import re

# ------------------------------------------------------------
# EXTRACTION ERRORS
# ------------------------------------------------------------


class ExtractionError(Exception):
    """Raised when text cannot be extracted or parsed."""


class NoTextExtractionError(ExtractionError):
    """The file is structurally valid but contains NO extractable text
    (e.g. a scanned/image-only PDF). Callers surface this as an
    OCR_REQUIRED diagnostic instead of a corruption error."""


# ------------------------------------------------------------
# TEXT EXTRACTION
# ------------------------------------------------------------


def extract_text_from_pdf(content: bytes) -> dict:
    """Return {"raw_text", "page_count", "extraction_success"} for PDF bytes."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise ExtractionError("pypdf is not installed - cannot parse PDFs") from exc

    try:
        reader = PdfReader(io.BytesIO(content))
        page_texts = []
        for page in reader.pages:
            page_texts.append(page.extract_text() or "")
        raw_text = "\n".join(page_texts)
        page_count = len(reader.pages)
    except ExtractionError:
        raise
    except Exception as exc:
        raise ExtractionError(
            f"Could not read the PDF file (it may be corrupted): {exc}"
        ) from exc

    if not raw_text.strip():
        raise NoTextExtractionError(
            "No extractable text found in the PDF. "
            "Scanned/image-only PDFs are not supported yet."
        )

    return {
        "raw_text": raw_text,
        "page_count": page_count,
        "extraction_success": True,
    }


def extract_text_from_docx(content: bytes) -> dict:
    """Return {"raw_text", "page_count": None, "extraction_success"} for DOCX bytes."""
    try:
        import docx  # python-docx
    except ImportError as exc:  # pragma: no cover
        raise ExtractionError("python-docx is not installed - cannot parse DOCX") from exc

    try:
        document = docx.Document(io.BytesIO(content))
        parts = [p.text for p in document.paragraphs if p.text.strip()]
        for table in document.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        parts.append(cell.text)
    except Exception as exc:
        raise ExtractionError(
            f"Could not read the DOCX file (it may be corrupted): {exc}"
        ) from exc

    raw_text = "\n".join(parts)

    if not raw_text.strip():
        raise NoTextExtractionError(
            "No extractable text found in the DOCX file."
        )

    # DOCX has no reliable page count without rendering - report None honestly.
    return {
        "raw_text": raw_text,
        "page_count": None,
        "extraction_success": True,
    }


def extract_text(content: bytes, file_type: str) -> dict:
    """Dispatch text extraction by file type."""
    if file_type == "pdf":
        return extract_text_from_pdf(content)
    if file_type == "docx":
        return extract_text_from_docx(content)
    raise ExtractionError(f"Unsupported file type for extraction: {file_type}")


# ------------------------------------------------------------
# SECTION DETECTION
# ------------------------------------------------------------

SECTION_HEADINGS = {
    "education": [
        "education", "academic qualifications", "educational qualification",
        "academics", "qualifications",
    ],
    "skills": [
        "technical skills", "skills", "technologies", "tech stack",
        "areas of expertise", "core competencies",
    ],
    "experience": [
        "work experience", "professional experience", "employment history",
        "work history", "experience",
    ],
    "internships": ["internships", "internship", "intern"],
    "projects": [
        "academic projects", "personal projects", "project experience",
        "projects",
    ],
    "certifications": ["certifications", "certificates", "credentials", "certification"],
    "achievements": [
        "achievements", "awards", "honors", "honours", "accomplishments",
        "achievement",
    ],
}


def _heading_pattern(keyword: str) -> re.Pattern:
    # Whole-line heading: optional bullets / numbers / separators,
    # then the keyword, then an optional colon. Case-insensitive.
    return re.compile(
        rf"^\s*[\#\*•·\-–—\d\.\)]*\s*{re.escape(keyword)}\s*:?\s*$",
        re.IGNORECASE,
    )


def detect_sections(lines):
    """Map section name -> (start_line, end_line) for the detected headings."""
    # (line_index, section, keyword) for the first match of each keyword
    heading_matches = []
    for section, keywords in SECTION_HEADINGS.items():
        for keyword in keywords:
            pattern = _heading_pattern(keyword)
            for i, line in enumerate(lines):
                if pattern.match(line):
                    heading_matches.append((i, section, keyword))
                    break

    # Keep the earliest heading per section; longest keyword on ties.
    best = {}
    for i, section, keyword in heading_matches:
        current = best.get(section)
        if current is None or i < current[0] or (
            i == current[0] and len(keyword) > len(current[1])
        ):
            best[section] = (i, keyword)

    ordered = sorted(best.items(), key=lambda kv: kv[1][0])
    sections = {}
    for idx, (section, (start, _)) in enumerate(ordered):
        end = ordered[idx + 1][1][0] if idx + 1 < len(ordered) else len(lines)
        sections[section] = (start, end)
    return sections


def _section_text(lines, span):
    """Join the lines of a section, excluding its heading line."""
    start, end = span
    return "\n".join(lines[start + 1:end])


# ------------------------------------------------------------
# REGEX BUILDING BLOCKS
# ------------------------------------------------------------

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

# A phone-like token (digits + separators). Length + digit-count
# validation happens in extract_phone().
PHONE_TOKEN_RE = re.compile(r"(?:\+?\d[\d\s\-().]{7,}\d)")

URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?([a-zA-Z0-9\-]+(?:\.[a-zA-Z0-9\-]+)+)(?:/[^\s)]*)?"
)

YEAR_RE = re.compile(r"\b20\d{2}\b")

DATE_RANGE_RE = re.compile(
    r"\b(20\d{2})\s*(?:[-–—~]|to)\s*(20\d{2}|present|current|now|till\s*date)?\b",
    re.IGNORECASE,
)

DEGREE_RE = re.compile(
    r"\b(?:Bachelor(?:'s)? of (?:Technology|Engineering|Science|Arts|Business Administration|Computer Applications|Commerce)|"
    r"Master(?:'s)? of (?:Technology|Engineering|Science|Arts|Business Administration|Computer Applications|Commerce)|"
    r"B\.?Tech|B\.?E|M\.?Tech|M\.?E|B\.?Sc|M\.?Sc|B\.?A|M\.?A|MBA|PGDM|PhD|"
    r"BCA|MCA|BBA|B\.?Com|M\.?Com|B\.?Arch|M\.?Arch|B\.?Pharm|M\.?Pharm|Diploma)\b",
    re.IGNORECASE,
)

BRANCH_KEYWORDS = [
    "Information Science and Engineering",
    "Electronics and Communication",
    "Artificial Intelligence",
    "Data Science",
    "Machine Learning",
    "Cyber Security",
    "Computer Engineering",
    "Software Engineering",
    "Computer Science",
    "Information Technology",
    "Information Science",
    "Electronics",
    "Electrical",
    "Mechanical",
    "Civil",
    "Chemical",
    "Instrumentation",
    "Biotechnology",
    "Automobile",
    "Aerospace",
    "ECE",
    "CSE",
    "EEE",
    "IT",
    "AIML",
    "AI & ML",
]

COLLEGE_RE = re.compile(
    r"\b((?:Indian Institute of Technology|National Institute of Technology|"
    r"Indian Institute of Information Technology|Indian Institute of Science|"
    r"IIT|NIT|IIIT|IISc)\s+[A-Z][A-Za-z]*|"
    r"[A-Z][A-Za-z&.\- ]{1,60}?(?:University|Institute of Technology|Institute|"
    r"College|School|Academy|Polytechnic))\b"
)

CGPA_KEYWORD_RE = re.compile(
    r"(?:CGPA|GPA)\s*[:=\-–—]?\s*(\d+(?:\.\d+)?)\s*(?:/\s*(10|4))?",
    re.IGNORECASE,
)
CGPA_SLASH_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*/\s*10\b")

GRAD_YEAR_EXPLICIT_RE = re.compile(
    r"(?:graduat\w*\s*(?:in|year|:)|expected\s+graduation|class\s+of|passing\s+year)\s*"
    r"(20\d{2})",
    re.IGNORECASE,
)

ROLE_KEYWORDS = [
    "engineer", "developer", "intern", "analyst", "scientist", "manager",
    "lead", "architect", "specialist", "consultant", "designer", "tester",
    "researcher", "trainee", "associate", "coordinator", "executive",
    "director", "head", "freelancer",
]

CITY_NAMES = [
    "Mumbai", "Delhi", "Bengaluru", "Bangalore", "Hyderabad", "Chennai",
    "Pune", "Kolkata", "Ahmedabad", "Jaipur", "Lucknow", "Kochi", "Indore",
    "Nagpur", "Surat", "Gurgaon", "Gurugram", "Noida", "Chandigarh",
    "Bhopal", "Patna", "Bhubaneswar", "Coimbatore", "Visakhapatnam",
    "Guwahati", "Thiruvananthapuram", "Mysore", "Vellore", "Madurai",
    "Vijayawada", "Warangal", "Kanpur", "Agra", "Varanasi", "Dehradun",
    "Raipur", "Ranchi", "Jamshedpur", "Amritsar", "Ludhiana", "Jodhpur",
    "Udaipur", "Manipal", "Kharagpur", "Roorkee", "Tiruchirappalli",
]

ACHIEVEMENT_AWARD_WORDS = [
    "winner", "award", "prize", "rank", "medal", "trophy", "first place",
    "secured", "top 10", "top 5", "distinction", "scholarship",
]
ACHIEVEMENT_CODING_WORDS = [
    "leetcode", "codechef", "codeforces", "hackerrank", "hackerearth",
    "geeksforgeeks", "coding", "rating", "competitive programming",
]

# ------------------------------------------------------------
# SKILL TAXONOMY (keyword -> category; presence-based, no inference)
# ------------------------------------------------------------

SKILL_TAXONOMY = {
    "programming_languages": [
        "Python", "Java", "JavaScript", "TypeScript", "C++", "C#", "Go",
        "Rust", "Kotlin", "Swift", "Ruby", "PHP", "Scala", "Dart", "SQL",
        "MATLAB", "Bash", "Shell Scripting", "Perl", "Haskell",
        "Objective-C", "Groovy", "Elixir", "Julia", "VB.NET",
    ],
    "frameworks": [
        "Django", "Flask", "FastAPI", "Spring Boot", "Spring", "React",
        "React Native", "Angular", "Vue.js", "Node.js", "Express.js",
        "Next.js", ".NET", "ASP.NET", "Laravel", "Ruby on Rails", "Flutter",
        "Bootstrap", "Tailwind", "jQuery", "Redux", "Hibernate", "Selenium",
        "JUnit", "pytest", "Cypress", "Playwright", "Apache Spark", "Hadoop",
        "Kafka",
    ],
    "databases": [
        "MySQL", "PostgreSQL", "MongoDB", "SQLite", "Oracle", "SQL Server",
        "Redis", "Cassandra", "DynamoDB", "Firebase", "Elasticsearch",
        "Neo4j", "MariaDB", "Snowflake", "BigQuery", "CouchDB", "InfluxDB",
        "Hive",
    ],
    "cloud": [
        "AWS", "Amazon Web Services", "Azure", "Google Cloud", "GCP", "S3",
        "EC2", "Lambda", "Docker", "Kubernetes", "Terraform", "Heroku",
        "Vercel", "Netlify", "Cloudflare", "OpenStack", "DigitalOcean",
        "Azure DevOps", "GitHub Actions", "CI/CD",
    ],
    "ai_ml": [
        "Machine Learning", "Deep Learning", "Natural Language Processing",
        "NLP", "Computer Vision", "LLM", "Large Language Model",
        "Generative AI", "Reinforcement Learning", "TensorFlow", "PyTorch",
        "Keras", "Scikit-learn", "XGBoost", "OpenCV", "NLTK", "spaCy",
        "Transformers", "LangChain", "Hugging Face", "pandas", "NumPy",
        "Matplotlib", "Seaborn", "Data Analysis", "Statistics", "CNN",
        "RNN", "LSTM", "RAG",
    ],
    "web_technologies": [
        "HTML", "CSS", "REST API", "RESTful", "GraphQL", "WebSockets",
        "JSON", "XML", "AJAX", "Responsive Design", "DOM",
    ],
    "tools": [
        "Git", "GitLab", "Bitbucket", "VS Code", "Visual Studio Code",
        "IntelliJ", "Eclipse", "Jupyter", "Postman", "Figma", "Adobe XD",
        "Photoshop", "Jenkins", "Jira", "Confluence", "Linux", "Unix",
        "Tableau", "Power BI", "Excel", "Google Analytics", "Notion",
        "Slack", "Trello",
    ],
    "other_skills": [
        "Communication", "Teamwork", "Leadership", "Problem Solving",
        "Time Management", "Agile", "Scrum", "MS Office", "PowerPoint",
        "Word", "Documentation", "Presentation", "Adaptability",
        "Critical Thinking", "Project Management",
    ],
}


def _word_boundary_pattern(keyword: str) -> re.Pattern:
    """Match a keyword as a standalone word/phrase (handles C#, C++, .NET)."""
    return re.compile(rf"(?<!\w){re.escape(keyword)}(?!\w)", re.IGNORECASE)


def scan_skills(text: str) -> dict:
    """Return {category: [skill, ...]} for skills actually present in text.

    Order of appearance is preserved; subsumed keywords are dropped
    (e.g. 'Spring' is removed when 'Spring Boot' is also present).
    """
    matches = []  # (position, category, keyword)
    for category, keywords in SKILL_TAXONOMY.items():
        for keyword in keywords:
            m = _word_boundary_pattern(keyword).search(text)
            if m:
                matches.append((m.start(), category, keyword))

    matches.sort(key=lambda t: t[0])

    # Drop keywords subsumed by a longer matched keyword (e.g. Spring in Spring Boot)
    kept = []
    for pos, category, keyword in matches:
        subsumed = any(
            keyword.lower() in other.lower()
            for _, _, other in kept
            if len(other) > len(keyword)
        )
        if not subsumed:
            kept.append((pos, category, keyword))

    result = {category: [] for category in SKILL_TAXONOMY}
    for _, category, keyword in kept:
        result[category].append(keyword)
    return result


# ------------------------------------------------------------
# PERSONAL INFORMATION
# ------------------------------------------------------------


def _is_contact_line(line: str) -> bool:
    return bool(
        EMAIL_RE.search(line)
        or PHONE_TOKEN_RE.search(line)
        or URL_RE.search(line)
    )


def extract_name(header_lines):
    for line in header_lines:
        candidate = line.strip(" •·-–—|#*")
        if not candidate:
            continue
        if _is_contact_line(candidate):
            continue
        words = re.split(r"\s+", candidate)
        if not (2 <= len(words) <= 5):
            continue
        if not all(re.fullmatch(r"[A-Za-z][A-Za-z.'\-]*", w) for w in words):
            continue
        if sum(1 for w in words if w[:1].isupper()) >= 2:
            return candidate
    return None


def extract_email(text: str):
    m = EMAIL_RE.search(text)
    return m.group(0).strip(".,;") if m else None


def extract_phone(header_lines):
    best = None
    for line in header_lines:
        for m in PHONE_TOKEN_RE.finditer(line):
            candidate = m.group(0).strip(" \t.,;()")
            digits = re.sub(r"\D", "", candidate)
            if 10 <= len(digits) <= 15:
                if best is None or len(digits) > len(re.sub(r"\D", "", best)):
                    best = candidate
    return best


def _url_host(url: str) -> str:
    m = re.match(r"(?:https?://)?(?:www\.)?([a-zA-Z0-9\-]+(?:\.[a-zA-Z0-9\-]+)+)", url)
    return m.group(1).lower() if m else ""


def extract_links(text: str):
    """Return (linkedin, github, portfolio) - each None when not found."""
    linkedin = github = portfolio = None
    for m in URL_RE.finditer(text):
        # Skip matches that are part of an email address
        before = text[max(0, m.start() - 1):m.start()]
        after = text[m.end():m.end() + 1]
        if before == "@" or after == "@":
            continue
        url = m.group(0).strip(".,;")
        host = _url_host(url)
        if not host:
            continue
        if "linkedin.com" in host and linkedin is None:
            linkedin = url
        elif "github.com" in host and github is None:
            github = url
        elif linkedin is None and github is None and portfolio is None:
            portfolio = url
    return linkedin, github, portfolio


def extract_location(header_lines):
    # Pattern 1: "City, State" or "City, District, State"
    for line in header_lines:
        stripped = line.strip(" •·-–—|#*")
        if not stripped or len(stripped) > 60:
            continue
        if _is_contact_line(stripped):
            continue
        if re.fullmatch(
            r"[A-Z][a-zA-Z]+(?:[\s\-][A-Z][a-zA-Z]+)*(?:,\s*[A-Z][a-zA-Z]+(?:\s*[A-Z]{2})?)+",
            stripped,
        ):
            return stripped
    # Pattern 2: known city name on a short line
    for line in header_lines:
        stripped = line.strip(" •·-–—|#*")
        if not stripped or len(stripped) > 60 or _is_contact_line(stripped):
            continue
        for city in CITY_NAMES:
            if re.search(rf"\b{re.escape(city)}\b", stripped, re.IGNORECASE):
                if len(stripped) <= 30:
                    return stripped
                return re.search(rf"\b{re.escape(city)}\b", stripped,
                                 re.IGNORECASE).group(0)
    return None


# ------------------------------------------------------------
# EDUCATION
# ------------------------------------------------------------


def extract_education(text: str) -> tuple:
    """Return (degree, branch, college, cgpa, graduation_year, cgpa_conf, year_conf)."""
    degree = None
    m = DEGREE_RE.search(text)
    if m:
        # Include a trailing period so "B.E." stays "B.E." (not "B.E")
        end = m.end()
        if end < len(text) and text[end] == ".":
            end += 1
        degree = re.sub(r"\s+", " ", text[m.start():end]).strip()

    branch = None
    for keyword in BRANCH_KEYWORDS:
        m2 = re.search(rf"\b{re.escape(keyword)}\b", text, re.IGNORECASE)
        if m2:
            branch = m2.group(0)
            break
    if branch is None:
        # "B.Tech (CSE)" style
        m2 = re.search(r"\(([A-Za-z &]{2,20})\)", text)
        if m2:
            branch = m2.group(1).strip()

    college = None
    m3 = COLLEGE_RE.search(text)
    if m3:
        college = re.sub(r"\s+", " ", m3.group(0)).strip().strip(".,;")

    cgpa = None
    cgpa_conf = 0.0
    m4 = CGPA_KEYWORD_RE.search(text)
    if m4:
        value = float(m4.group(1))
        scale = m4.group(2)
        if 0 <= value <= 10:
            cgpa = value
            if scale == "10" or (scale is None and value > 4):
                cgpa_conf = 0.90
            else:
                cgpa_conf = 0.50  # scale ambiguous (e.g. /4 GPA)
    if cgpa is None:
        m5 = CGPA_SLASH_RE.search(text)
        if m5:
            value = float(m5.group(1))
            if 0 <= value <= 10:
                cgpa = value
                cgpa_conf = 0.90

    graduation_year = None
    year_conf = 0.0
    m6 = GRAD_YEAR_EXPLICIT_RE.search(text)
    if m6:
        graduation_year = int(m6.group(1))
        year_conf = 0.80
    else:
        years = [int(y) for y in YEAR_RE.findall(text)]
        if years:
            # Heuristic: latest year in the education block.
            graduation_year = max(years)
            year_conf = 0.60

    return degree, branch, college, cgpa, graduation_year, cgpa_conf, year_conf


# ------------------------------------------------------------
# EXPERIENCE / INTERNSHIPS
# ------------------------------------------------------------


def _clean_part(part: str) -> str:
    part = re.sub(r"^[\s•·\-–—|,]+|[\s•·\-–—|,]+$", "", part)
    return part.strip(" .")


def _entry_role_company(header_rest: str):
    """Split a header line (minus dates) into (role, company) heuristically."""
    rest = header_rest.strip(" ,|•·-–—")

    # "Role at Company" / "Role @ Company"
    m = re.search(r"\s(?:at|@)\s", rest, re.IGNORECASE)
    if m:
        role = _clean_part(rest[: m.start()])
        company = _clean_part(rest[m.end():])
        return role or None, company or None

    # Split on the strongest separator present
    for sep in ["|", " – ", " — ", " - ", ", "]:
        if sep in rest:
            parts = [p for p in rest.split(sep) if p.strip()]
            if len(parts) >= 2:
                first, second = _clean_part(parts[0]), _clean_part(parts[1])
                # If the second part looks like a role, it is the role
                if any(kw in second.lower() for kw in ROLE_KEYWORDS):
                    return second, first
                return first, second

    # Single token - role only (company unknown, never guessed)
    return _clean_part(rest) or None, None


def _extract_dated_entries(section_lines):
    """Split a section into dated entries: [{role, company, duration, technologies}].

    Only lines carrying a date range / year start a new entry - we never
    fabricate entries without evidence of dates.
    """
    entries = []
    current = None

    for line in section_lines:
        stripped = line.strip()
        if not stripped:
            continue

        date_m = DATE_RANGE_RE.search(stripped)
        single_year = None
        if not date_m:
            # single-year entry headers like "Intern, Google, 2023"
            ym = YEAR_RE.search(stripped)
            if ym and len(stripped) <= 120:
                single_year = ym.group(0)

        is_header = date_m is not None or single_year is not None
        # A "Technologies:" body line must not start a new entry
        if is_header and re.match(r"^(technologies?|skills?|tools?)\s*[:]",
                                  stripped, re.IGNORECASE):
            is_header = False

        if is_header:
            if current is not None:
                entries.append(current)
            duration = None
            rest = stripped
            if date_m:
                duration = date_m.group(0)
                rest = stripped[: date_m.start()] + " " + stripped[date_m.end():]
            else:
                duration = single_year
                rest = stripped.replace(single_year, "", 1)
            role, company = _entry_role_company(rest)
            current = {
                "role": role,
                "company": company,
                "duration": duration,
                "body": [stripped],
            }
        else:
            if current is not None:
                current["body"].append(stripped)

    if current is not None:
        entries.append(current)

    result = []
    for entry in entries:
        entry_text = " ".join(entry["body"])
        tech = scan_skills(entry_text)
        technologies = [s for skills in tech.values() for s in skills]
        result.append({
            "company": entry["company"],
            "role": entry["role"],
            "duration": entry["duration"],
            "technologies": technologies,
        })
    return result


# ------------------------------------------------------------
# PROJECTS
# ------------------------------------------------------------


def _extract_projects(section_text: str) -> list:
    entries = []
    current = None
    lines = section_text.splitlines()

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue

        is_bullet = bool(re.match(r"^\s*[•\-–—*]", stripped))
        is_tech_line = stripped.lower().startswith(
            ("technologies:", "tech stack:", "tools:")
        )

        # Bullet with "Title — description" / "Title : description"
        m = None
        if is_bullet:
            body = re.sub(r"^\s*[•\-–—*]\s*", "", stripped)
            m = re.split(r"\s*(?:—|–|:|\|| - )\s*", body, maxsplit=1)

        # Also detect plain-line project titles: short line followed by a
        # technologies line (or another title / end of section)
        is_plain_title = False
        if not is_bullet and not is_tech_line:
            # Heuristic: reasonable title length, doesn't look like a section header
            if 3 <= len(stripped) <= 80 and not re.match(
                r"^(projects?|certifications?|achievements?|education|skills?|experience|internships?)\s*:?$",
                stripped,
                re.IGNORECASE,
            ):
                # Look ahead: if next non-empty line is a technologies line, this is likely a title
                next_idx = i + 1
                while next_idx < len(lines) and not lines[next_idx].strip():
                    next_idx += 1
                if next_idx < len(lines):
                    next_line = lines[next_idx].strip()
                    if next_line.lower().startswith(
                        ("technologies:", "tech stack:", "tools:")
                    ):
                        is_plain_title = True

        if (m and m[0].strip() and len(m[0].strip()) <= 60) or is_plain_title:
            if current is not None:
                entries.append(current)
            if is_plain_title:
                title = stripped
                description = None
            else:
                title = m[0].strip()
                description = m[1].strip() if len(m) > 1 and m[1].strip() else None
            current = {"title": title, "description": description, "body": [stripped]}
        else:
            if current is not None:
                current["body"].append(stripped)
                if current["description"] is None and not is_tech_line:
                    current["description"] = stripped
            elif is_bullet and not is_tech_line:
                # A bullet without a title marker - start an unnamed entry
                current = {"title": None, "description": stripped, "body": [stripped]}

    if current is not None:
        entries.append(current)

    result = []
    for entry in entries:
        entry_text = " ".join(entry["body"])
        tech = scan_skills(entry_text)
        technologies = [s for skills in tech.values() for s in skills]
        result.append({
            "project_name": entry["title"],
            "description": entry["description"],
            "technologies": technologies,
        })
    return result


# ------------------------------------------------------------
# CERTIFICATIONS
# ------------------------------------------------------------


def _extract_certifications(section_text: str) -> list:
    result = []
    for line in section_text.splitlines():
        stripped = line.strip(" •·-–—*")
        if not stripped:
            continue
        if re.match(r"^(certifications?|certificates|credentials)\s*:?$",
                    stripped, re.IGNORECASE):
            continue
        year = None
        ym = YEAR_RE.search(stripped)
        if ym:
            year = int(ym.group(0))
        rest = re.sub(r"\b20\d{2}\b", " ", stripped)
        rest = re.sub(r"\s+", " ", rest).strip(" ,|•·-–—")
        if not rest:
            continue
        parts = [p.strip() for p in re.split(r"\s*(?:—|–|\||,)\s*", rest) if p.strip()]
        name = parts[0]
        issuer = parts[1] if len(parts) > 1 else None
        result.append({"name": name, "issuer": issuer, "year": year})
    return result


# ------------------------------------------------------------
# ACHIEVEMENTS
# ------------------------------------------------------------


def _extract_achievements(section_text: str) -> dict:
    hackathons, awards, coding = [], [], []
    for line in section_text.splitlines():
        stripped = line.strip(" •·-–—*")
        if not stripped:
            continue
        lowered = stripped.lower()
        if "hackathon" in lowered:
            hackathons.append(stripped)
        elif any(w in lowered for w in ACHIEVEMENT_CODING_WORDS):
            coding.append(stripped)
        elif any(w in lowered for w in ACHIEVEMENT_AWARD_WORDS):
            awards.append(stripped)
    return {
        "hackathons": hackathons,
        "awards": awards,
        "coding_achievements": coding,
    }


# ------------------------------------------------------------
# TOP-LEVEL PARSE
# ------------------------------------------------------------


def parse_resume(raw_text: str):
    """Parse raw resume text into (profile_dict, confidence_dict, needs_verification).

    profile_dict matches schemas_resume.ExtractedProfile.
    confidence_dict maps each field path to a 0..1 heuristic score
    (0 = not found). NOT calibrated - for review guidance only.
    """
    lines = [l.rstrip() for l in raw_text.splitlines()]
    sections = detect_sections(lines)

    first_heading = min((s[0] for s in sections.values()), default=None)
    header_end = first_heading if first_heading is not None else min(40, len(lines))
    header_lines = lines[:header_end]

    # --- Personal -------------------------------------------------
    name = extract_name(header_lines)
    email = extract_email(raw_text)
    phone = extract_phone(header_lines)
    location = extract_location(header_lines)
    linkedin, github, portfolio = extract_links(raw_text)

    # --- Education -------------------------------------------------
    edu_text = _section_text(lines, sections["education"]) if "education" in sections else raw_text
    degree, branch, college, cgpa, grad_year, cgpa_conf, year_conf = extract_education(edu_text)

    # --- Skills ----------------------------------------------------
    skills_text = _section_text(lines, sections["skills"]) if "skills" in sections else raw_text
    skills = scan_skills(skills_text)

    # --- Experience / Internships ----------------------------------
    experience = []
    if "experience" in sections:
        sec_lines = lines[sections["experience"][0] + 1: sections["experience"][1]]
        experience = _extract_dated_entries(sec_lines)

    internships = []
    if "internships" in sections:
        sec_lines = lines[sections["internships"][0] + 1: sections["internships"][1]]
        internships = _extract_dated_entries(sec_lines)

    # --- Projects ---------------------------------------------------
    projects = []
    if "projects" in sections:
        projects = _extract_projects(_section_text(lines, sections["projects"]))

    # --- Certifications ---------------------------------------------
    certifications = []
    if "certifications" in sections:
        certifications = _extract_certifications(
            _section_text(lines, sections["certifications"])
        )

    # --- Achievements -----------------------------------------------
    achievements = {"hackathons": [], "awards": [], "coding_achievements": []}
    if "achievements" in sections:
        achievements = _extract_achievements(
            _section_text(lines, sections["achievements"])
        )

    profile = {
        "name": name,
        "email": email,
        "phone": phone,
        "location": location,
        "linkedin": linkedin,
        "github": github,
        "portfolio": portfolio,
        "education": {
            "degree": degree,
            "branch": branch,
            "college": college,
            "cgpa": cgpa,
            "graduation_year": grad_year,
        },
        "skills": skills,
        "experience": experience,
        "internships": internships,
        "projects": projects,
        "certifications": certifications,
        "achievements": achievements,
    }

    # --- Heuristic confidence ---------------------------------------
    confidence = {
        "name": 0.50 if name else 0.0,
        "email": 0.97 if email else 0.0,
        "phone": 0.90 if phone else 0.0,
        "location": 0.40 if location else 0.0,
        "linkedin": 0.95 if linkedin else 0.0,
        "github": 0.95 if github else 0.0,
        "portfolio": 0.60 if portfolio else 0.0,
        "education.degree": 0.70 if degree else 0.0,
        "education.branch": 0.70 if branch else 0.0,
        "education.college": 0.60 if college else 0.0,
        "education.cgpa": cgpa_conf if cgpa is not None else 0.0,
        "education.graduation_year": year_conf if grad_year else 0.0,
        "skills": 0.80 if any(skills.values()) else 0.0,
        "experience": 0.75 if experience else 0.0,
        "internships": 0.75 if internships else 0.0,
        "projects": 0.75 if projects else 0.0,
        "certifications": 0.75 if certifications else 0.0,
        "achievements": 0.75 if any(achievements.values()) else 0.0,
    }
    needs_verification = [
        field for field, conf in confidence.items() if conf < 0.70
    ]

    return profile, confidence, needs_verification
