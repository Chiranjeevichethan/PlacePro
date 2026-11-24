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
from datetime import datetime

MAX_RESUME_PAGES = 50
MAX_EXTRACTED_CHARACTERS = 200_000

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
        if len(reader.pages)>MAX_RESUME_PAGES:
            raise ExtractionError('Resume PDF exceeds the 50-page extraction limit.')
        page_texts = []
        text_size=0
        for page in reader.pages:
            text=page.extract_text() or ""
            text_size+=len(text)
            if text_size>MAX_EXTRACTED_CHARACTERS:
                raise ExtractionError('Resume text exceeds the extraction limit.')
            page_texts.append(text)
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
        from docx.table import Table
        from docx.text.paragraph import Paragraph

        def ordered_text(container):
            for block in container.iter_inner_content():
                if isinstance(block, Paragraph):
                    if block.text.strip():
                        yield block.text
                elif isinstance(block, Table):
                    for row in block.rows:
                        seen_cells = set()
                        for cell in row.cells:
                            # Merged cells may be exposed more than once.
                            if cell._tc not in seen_cells:
                                seen_cells.add(cell._tc)
                                yield from ordered_text(cell)

        parts = list(ordered_text(document))
    except Exception as exc:
        raise ExtractionError(
            f"Could not read the DOCX file (it may be corrupted): {exc}"
        ) from exc

    raw_text = "\n".join(parts)
    if len(raw_text)>MAX_EXTRACTED_CHARACTERS:
        raise ExtractionError('Resume text exceeds the extraction limit.')

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
        "work history", "experience", "experience and internships",
        "experience & internships", "work experience and internships",
    ],
    "internships": ["internships", "internship", "intern", "internship experience"],
    "projects": [
        "academic projects", "personal projects", "project experience",
        "projects", "project",
    ],
    "certifications": ["certifications", "certificates", "credentials", "certification"],
    # Later sections not extracted by PlacePro are still RECOGNIZED so
    # they bound the preceding section instead of bleeding into it
    # (e.g. hackathon lines becoming "certifications").
    "hackathons": [
        "hackathons and open source", "hackathons & open source",
        "hackathons",
    ],
    "open_source": [
        "open source contributions", "open-source contributions",
        "open source", "open-source",
    ],
    "extracurriculars": [
        "extracurricular activities", "extra-curricular activities",
        "extracurriculars",
    ],
    "achievements": [
        "achievements", "awards", "honors", "honours", "accomplishments",
        "achievement",
    ],
    # Boundaries only: these sections must not leak into extracted records.
    "other": [
        "summary", "professional summary", "profile", "objective",
        "career objective", "interests", "hobbies", "languages",
        "references", "publications", "coursework", "relevant coursework",
        "training", "personal details", "declaration", "student profile fields",
    ],
}


def _heading_pattern(keyword: str) -> re.Pattern:
    # Whole-line heading: optional bullets / numbers / separators,
    # then the keyword, then an optional colon. Case-insensitive.
    return re.compile(
        rf"^\s*[\#\*•·\x7f\uf0b7\u0095\-–—\d\.\)]*\s*{re.escape(keyword)}"
        rf"\s*(?::\s*)?(?:\(?\d+\)?)?\s*$",
        re.IGNORECASE,
    )


_HEADING_PATTERNS = [(section, _heading_pattern(keyword))
                     for section, keywords in SECTION_HEADINGS.items()
                     for keyword in sorted(keywords, key=len, reverse=True)]


def _section_heading(line):
    for section, pattern in _HEADING_PATTERNS:
        if pattern.match(line):
            return section
    return None


def detect_sections(lines):
    """First span per section; every known heading bounds the preceding span.

    Capitalization alone is never a boundary: uppercase certificate titles
    and project names are valid content. Repeated headings also bound spans.
    """
    heading_matches = []
    for i, line in enumerate(lines):
        section = _section_heading(line)
        if section:
            heading_matches.append((i, section))
    sections = {}
    for idx, (start, section) in enumerate(heading_matches):
        end = heading_matches[idx + 1][0] if idx + 1 < len(heading_matches) else len(lines)
        sections.setdefault(section, (start, end))
    return sections


def _section_text(lines, span):
    """Join the lines of a section, excluding its heading line."""
    start, end = span
    return "\n".join(lines[start + 1:end])


def _section_blocks(lines, section):
    """All spans of a section, still bounded by every recognized heading."""
    blocks = []
    current = None
    for line in lines:
        heading = _section_heading(line)
        if heading:
            current = [] if heading == section else None
            if current is not None:
                blocks.append(current)
        elif current is not None:
            current.append(line)
    return blocks


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

_MONTH = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
_ENTRY_DATE = rf"(?:(?:{_MONTH})\.?\s+)?20\d{{2}}|(?:0?[1-9]|1[0-2])[/.-]20\d{{2}}"
ENTRY_DATE_RANGE_RE = re.compile(
    rf"(?<!\w)(?:{_ENTRY_DATE})\s*(?:[-–—~]|to)\s*(?:{_ENTRY_DATE}|present|current|now|till\s*date)(?!\w)",
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

    Longest overlapping mention wins. Separately stated skills are retained;
    aliases normalize spellings, never imply an additional skill.
    """
    aliases = {'React': ['React.js', 'ReactJS'], 'Node.js': ['NodeJS'],
               'Vue.js': ['VueJS'], 'Express.js': ['ExpressJS'], 'Next.js': ['NextJS']}
    matches = []  # (start, end, category, canonical keyword)
    for category, keywords in SKILL_TAXONOMY.items():
        for keyword in keywords:
            for spelling in [keyword, *aliases.get(keyword, [])]:
                for match in _word_boundary_pattern(spelling).finditer(text):
                    matches.append((match.start(), match.end(), category, keyword))
    matches.sort(key=lambda item: (item[0], -(item[1] - item[0])))
    result = {category: [] for category in SKILL_TAXONOMY}
    end_of_mention = -1
    for start, end, category, keyword in matches:
        if start < end_of_mention:
            continue
        end_of_mention = end
        if keyword not in result[category]:
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
        # Restrict the fallback to education records/date lines, rather than
        # taking a scholarship expiry or other unrelated number in the block.
        years = [int(y) for line in text.splitlines()
                 if DEGREE_RE.search(line) or COLLEGE_RE.search(line)
                 or DATE_RANGE_RE.fullmatch(line.strip())
                 for y in YEAR_RE.findall(line)]
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
                if (not any(re.search(rf"\b{kw}\b", first, re.IGNORECASE) for kw in ROLE_KEYWORDS)
                        and any(re.search(rf"\b{kw}\b", second, re.IGNORECASE) for kw in ROLE_KEYWORDS)):
                    return second, first
                return first, second

    # Single token - role only (company unknown, never guessed)
    return _clean_part(rest) or None, None


def _extract_dated_entries(section_lines):
    """Split a section into dated entries: [{role, company, duration, technologies}].

    Explicit role headers start entries. A body year or statistic does not.
    Undated roles keep duration null; a following date line can supply it.
    """
    entries = []
    current = None

    for line in section_lines:
        stripped = _clean_record_text(line)
        if not stripped:
            continue

        date_m = ENTRY_DATE_RANGE_RE.search(stripped)
        single_year = None
        if not date_m:
            # single-year entry headers like "Intern, Google, 2023"
            ym = YEAR_RE.search(stripped)
            if ym and len(stripped) <= 120:
                single_year = ym.group(0)

        has_role = any(re.search(rf"\b{re.escape(kw)}\b", stripped, re.IGNORECASE)
                       for kw in ROLE_KEYWORDS) or bool(re.search(r'\binternship\b', stripped, re.IGNORECASE))
        is_body = bool(re.match(r"^(built|developed|implemented|improved|worked|"
                                r"delivered|led|managed|supported|increased|reduced|"
                                r"collaborated|assisted|analyzed|designed|created|"
                                r"maintained|conducted|participated|contributed|compared|optimized)\b",
                                stripped, re.IGNORECASE))
        is_header = has_role and not is_body and len(stripped) <= 120
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
            elif single_year:
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
                if current['duration'] is None and (ENTRY_DATE_RANGE_RE.fullmatch(stripped) or _date_year(stripped)):
                    current['duration'] = stripped
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

    def is_tech(text):
        return bool(re.match(r'^(?:technologies?|tech stack|tools|stack)\s*:', text, re.IGNORECASE))

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue

        is_bullet = bool(re.match(r"^\s*(?:[\x7f\uf0b7\u0095•\-–—*]|\d+[.)]\s)", stripped))
        body = _clean_record_text(stripped)
        is_tech_line = is_tech(body)

        # Both plain and bullet "Title — description" are explicit titles.
        m = None
        if not is_tech_line:
            m = re.split(r"\s*(?:—|–|:|\|| - )\s*", body, maxsplit=1)
            # Description bullets are part of the current project, not new
            # projects. A bare number never becomes a project title.
            if len(m) < 2 or not _looks_like_project_title(m[0]):
                m = None

        # Short titles may precede description bullets, not only a tech line.
        is_plain_title = False
        if not is_tech_line and _looks_like_project_title(body):
            # Heuristic: reasonable title length, doesn't look like a section header
            if 3 <= len(stripped) <= 80 and not re.match(
                r"^(projects?|certifications?|achievements?|education|skills?|experience|internships?)\s*:?$",
                body,
                re.IGNORECASE,
            ):
                next_idx = i + 1
                while next_idx < len(lines) and not lines[next_idx].strip():
                    next_idx += 1
                if next_idx < len(lines):
                    next_line = lines[next_idx].strip()
                    if is_tech(_clean_record_text(next_line)) or not _looks_like_project_title(
                            _clean_record_text(next_line)) and re.search(r'[A-Za-z]', next_line):
                        is_plain_title = True

        if (m and m[0].strip() and len(m[0].strip()) <= 60) or is_plain_title:
            if current is not None:
                entries.append(current)
            if is_plain_title and not m:
                title = body
                description = None
            else:
                title = m[0].strip()
                description = m[1].strip() if len(m) > 1 and m[1].strip() else None
            current = {"title": title, "descriptions": [description] if description else [], "body": [body]}
        else:
            if current is not None:
                current["body"].append(body)
                if not is_tech_line and re.search(r'[A-Za-z]', body) and not re.match(
                        r'^(?:projects?_count|total|count)\b', body, re.IGNORECASE):
                    current["descriptions"].append(body)
            # Unattributed bullets never manufacture unnamed project records.

    if current is not None:
        entries.append(current)

    result = []
    for entry in entries:
        entry_text = " ".join(entry["body"])
        tech = scan_skills(entry_text)
        technologies = [s for skills in tech.values() for s in skills]
        result.append({
            "project_name": entry["title"],
            "description": '\n'.join(entry["descriptions"]) or None,
            "technologies": technologies,
        })
    return result


def _looks_like_project_title(text):
    return bool(re.search(r"[A-Za-z]", text) and not re.match(
        r"^(built|developed|implemented|improved|worked|delivered|reduced|added|"
        r"increased|achieved|deployed|tested|projects?_count|total|count|"
        r"completed|participated|contributed|collaborated|assisted|analyzed|"
        r"designed|created|maintained|conducted|compared|optimized|https?|www)\b", text, re.IGNORECASE))


# ------------------------------------------------------------
# CERTIFICATIONS
# ------------------------------------------------------------


# "Certifications: 2" / "Certifications" with an optional stated count:
# a header, not a certification record. The stated count (if any) is
# ignored rather than used to fabricate records.
_CERTS_HEADER_RE = re.compile(
    r"^(certifications?|certificates|credentials)\s*:?\s*\d*\s*$",
    re.IGNORECASE,
)


def _looks_like_cert_record(line: str) -> bool:
    """Honest-extraction filter: is this line plausibly one certification?

    Section context supports listed course certificates, but unrelated course
    mentions, metadata, bare numbers and descriptive prose are not titles.
    """
    if len(line) > 160 or not re.search(r"[A-Za-z]", line):
        return False          # long-line prose, never a record title
    # A description clause ("..., including ...", "Participated in ...",
    # "contributed to ...") is prose, never a record.
    if re.search(r"\b(including|contributed|participated)\b",
                 line, re.IGNORECASE):
        return False
    if re.match(r"^(?:completed|studied|learned|worked|built|this|these|just|I|we|"
                r"coursework|courses?|training|testing note|description|"
                r"projects?_count|cgpa|branch|college_tier|total|count)\b",
                line, re.IGNORECASE):
        return False
    return True


# Bullet glyphs that PDF/DOCX extraction sometimes emits as text:
# DEL (\x7f), Word symbol-font bullet (\uf0b7), PUA round bullet (\u0095).
_GLYPH_BULLET_CHARS = "\x7f\uf0b7\u0095\u25fb\u25aa\u2794\u27a4"


# Ordinary bullet separators plus the glyph-only bullets.
_BULLET_STRIP_CHARS = " •·-–—*" + _GLYPH_BULLET_CHARS


def _clean_record_text(line: str) -> str:
    """Strip bullet separators AND stray glyph bullets from extraction lines."""
    return re.sub(r"^\d+[.)]\s+", "", line.strip(_BULLET_STRIP_CHARS)).strip()



_CERT_METADATA_RE = re.compile(
    r"^(?P<label>(?:certificate|certification|credential)\s*(?:id|number|no\.?|url|link)|"
    r"id|url|https?|issuer|issued by|issuing organization|provider|organization|"
    r"issued|issue date|date issued|date|completed on|completion date|"
    r"expires?|expiry(?: date)?|expiration(?: date)?|valid(?: until| through)?|status)"
    r"(?:\s*[:#=\-]\s*|\s+|$)(?P<value>.*)$", re.IGNORECASE)
_ISSUER_LABELS = {"issuer", "issued by", "issuing organization", "provider", "organization"}
_ISSUE_LABELS = {"issued", "issue date", "date issued", "date", "completed on", "completion date"}
_MONTH = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
_KNOWN_ISSUERS = {
    'amazon', 'amazon web services', 'aws', 'microsoft', 'google', 'google cloud',
    'ibm', 'oracle', 'cisco', 'meta', 'coursera', 'edx', 'udemy', 'nptel',
    'linkedin learning', 'freecodecamp', 'hackerrank', 'comptia', 'salesforce',
}


def _date_year(text):
    """Keep only the stated year of a recognizable, valid date; never guess a date."""
    value = re.sub(r'\s+', ' ', text.strip().rstrip('.'))
    value = re.sub(r'\bSept\b', 'Sep', value, flags=re.IGNORECASE)
    if not re.search(r'\b(?:19|20)\d{2}\b', value):
        return None
    for format_ in ('%Y', '%b %Y', '%B %Y', '%b %d, %Y', '%B %d, %Y',
                    '%b %d %Y', '%B %d %Y', '%d %b %Y', '%d %B %Y',
                    '%Y-%m-%d', '%Y/%m/%d', '%d/%m/%Y', '%d.%m.%Y', '%d-%m-%Y'):
        try:
            return datetime.strptime(value, format_).year
        except ValueError:
            continue
    return None


def _reliable_issuer(text):
    value = text.strip(' .').casefold()
    return value in _KNOWN_ISSUERS or bool(re.fullmatch(
        r'(?:[\w &.\-]+\s+)?(?:academy|university|institute|inc|corporation|foundation)', value))


def _cert_metadata(text):
    match = _CERT_METADATA_RE.match(text)
    if match:
        label = re.sub(r'\s+', ' ', match['label']).lower()
        value = match['value'].strip()
        if label in _ISSUER_LABELS:
            return 'issuer', value or None
        if label in _ISSUE_LABELS:
            return 'year', _date_year(value)
        return 'ignore', None
    if text.strip(' .').casefold() in _KNOWN_ISSUERS:
        return 'issuer', text.strip()
    if URL_RE.fullmatch(text.rstrip('.,;')) or _date_year(text) is not None:
        return ('year', _date_year(text)) if _date_year(text) is not None else ('ignore', None)
    return None


def _extract_certifications(section_text: str) -> list:
    """Keep titles and attach reliable metadata; preserve name/issuer/year API."""
    result = []
    current = None
    for line in section_text.splitlines():
        text = _clean_record_text(line)
        if not text:
            continue
        heading = _section_heading(text)
        if heading:
            if heading == 'certifications':
                continue
            break
        metadata = _cert_metadata(text)
        if metadata:
            for part in re.split(r'\s*\|\s*|\s+[–—]\s+', text):
                item = _cert_metadata(part)
                if item:
                    key, value = item
                    if current is not None and key != 'ignore' and value is not None and current[key] is None:
                        current[key] = value
            continue
        if not _looks_like_cert_record(text):
            current = None
            continue

        # Retain separators inside names (e.g. "Architect - Associate").
        # Split comma layouts only after recognizing metadata or an issuer.
        # A complete labelled date stays together even when it contains commas.
        pieces = re.split(r'(\s*(?:—|–|\|| - )\s*)', text)
        parts = []
        for index in range(0, len(pieces), 2):
            part = pieces[index]
            separator = pieces[index - 1] if index else ''
            if _cert_metadata(part.strip()):
                parts.append((separator, part.strip()))
            else:
                comma_parts = re.split(r'(,\s*)', part)
                for offset in range(0, len(comma_parts), 2):
                    parts.append((comma_parts[offset - 1] if offset else separator,
                                  comma_parts[offset].strip()))
        record = {'name': '', 'issuer': None, 'year': None}
        for separator, part in parts:
            meta = _cert_metadata(part)
            if meta:
                key, value = meta
                if key != 'ignore' and value is not None and record[key] is None:
                    record[key] = value
                continue
            # Existing compact layout: "Title, Amazon 2023" or "Title 2023".
            tail = re.search(rf"\s+((?:{_MONTH}\s+)?20\d{{2}})\.?$", part, re.IGNORECASE)
            if tail:
                record['year'] = record['year'] or _date_year(tail[1])
                part = part[:tail.start()].rstrip()
            if record['name'] and record['issuer'] is None and _reliable_issuer(part):
                record['issuer'] = part
            elif part:
                record['name'] += (separator if record['name'] else '') + part
        if not record['name'] or _cert_metadata(record['name']):
            current = None
            continue
        current = record
        result.append(record)

    unique = []
    def title_key(value):
        return re.sub(r"\s+", " ", value).strip(' .;').casefold()
    for record in result:
        previous = next((entry for entry in unique if title_key(entry['name']) == title_key(record['name'])
            and all(entry[key] is None or record[key] is None or
                    str(entry[key]).casefold() == str(record[key]).casefold()
                    for key in ('issuer', 'year'))), None)
        if previous is None:
            unique.append(record)
        else:
            for key in ('issuer', 'year'):
                if previous[key] is None:
                    previous[key] = record[key]
    return unique


# ------------------------------------------------------------
# ACHIEVEMENTS
# ------------------------------------------------------------


def _extract_achievements(section_text: str) -> dict:
    hackathons, awards, coding = [], [], []
    for line in section_text.splitlines():
        stripped = _clean_record_text(line)
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


def _activity_lines(section_text):
    # Retain literal reviewable descriptions, never turn a stated number
    # into that many invented records or ML scores/counts.
    return list(dict.fromkeys(text for line in section_text.splitlines()
        if (text := _clean_record_text(line)) and re.search(r"[A-Za-z]", text)
        and not _section_heading(text) and not _cert_metadata(text)
        and not re.fullmatch(r"[\w -]+:\s*\d+", text)))


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
    edu_text = _section_text(lines, sections["education"]) if "education" in sections else '\n'.join(
        line for line in header_lines if DEGREE_RE.search(line) or COLLEGE_RE.search(line)
        or CGPA_KEYWORD_RE.search(line) or GRAD_YEAR_EXPLICIT_RE.search(line))
    degree, branch, college, cgpa, grad_year, cgpa_conf, year_conf = extract_education(edu_text)

    # --- Skills ----------------------------------------------------
    skills_text = '\n'.join(line for block in _section_blocks(lines, 'skills') for line in block) if "skills" in sections else '\n'.join(
        line for line in header_lines if re.match(
            r"^\s*(?:technical skills|skills|programming languages|technologies|tech stack)\s*:",
            line, re.IGNORECASE))
    skills = scan_skills(skills_text)

    # --- Experience / Internships ----------------------------------
    experience = []
    internships = []
    for section in ('experience', 'internships'):
        for block in _section_blocks(lines, section):
            for entry in _extract_dated_entries(block):
                # An explicit internship role wins over a generic Experience heading.
                # Otherwise retain the resume's declared section; never infer employment.
                bucket = internships if section == 'internships' or re.search(
                    r'\bintern(?:ship)?\b', entry.get('role') or '', re.IGNORECASE) else experience
                if entry not in bucket:
                    bucket.append(entry)

    # --- Projects ---------------------------------------------------
    projects = []
    for block in _section_blocks(lines, 'projects'):
        projects.extend(_extract_projects('\n'.join(block)))

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

    # Hackathon / open-source sections are recognized headings; lines with
    # an explicitly stated hackathon contribution move into the
    # achievements buckets rather than silently disappearing. Never
    # invented - only lines actually present in the resume are kept.
    for extra in ("hackathons", "open_source"):
        if extra in sections:
            extra_hits = _extract_achievements(_section_text(lines, sections[extra]))
            for bucket in achievements:
                for line_ in extra_hits[bucket]:
                    if line_ not in achievements[bucket]:
                        achievements[bucket].append(line_)

    if 'hackathons' in sections:
        for text in _activity_lines(_section_text(lines, sections['hackathons'])):
            if re.search(r'open[ -]source|contribut', text, re.IGNORECASE):
                continue
            if text not in achievements['hackathons']:
                achievements['hackathons'].append(text)
    achievements['open_source_contributions'] = []
    achievements['extracurriculars'] = []
    for section, bucket in [('open_source', 'open_source_contributions'),
                            ('extracurriculars', 'extracurriculars')]:
        if section in sections:
            achievements[bucket] = _activity_lines(_section_text(lines, sections[section]))
    if 'hackathons' in sections:
        achievements['open_source_contributions'].extend(text for text in
            _activity_lines(_section_text(lines, sections['hackathons']))
            if re.search(r'open[ -]source|contribut', text, re.IGNORECASE)
            and text not in achievements['open_source_contributions'])

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
