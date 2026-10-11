# ============================================================
# PLACEPRO - PHASE 12 - SKILL TAXONOMY & PLACEMENT REQUIREMENTS
# ============================================================
#
# SINGLE source of truth for:
#   1. The skill taxonomy (categories + canonical skill names).
#   2. Skill-name normalization (aliases -> canonical names).
#   3. Placement skill requirements (what a generic software
#      placement profile is expected to have).
#
# Everything here is plain, configurable data - the readiness
# engine (readiness_service.py) contains NO hard-coded skill
# logic. To change the taxonomy or requirements, edit this file.
#
# ============================================================

# ------------------------------------------------------------
# 1. SKILL TAXONOMY
# ------------------------------------------------------------
# Each category: key (machine), label (display), skills (canonical names).
SKILL_TAXONOMY = [
    {
        "key": "PROGRAMMING",
        "label": "Programming",
        "skills": ["Python", "Java", "C", "C++", "JavaScript", "TypeScript"],
    },
    {
        "key": "WEB",
        "label": "Web",
        "skills": ["HTML", "CSS", "React", "Node.js", "Express", "REST API"],
    },
    {
        "key": "DATABASE",
        "label": "Database",
        "skills": ["MySQL", "PostgreSQL", "MongoDB", "SQL"],
    },
    {
        "key": "DATA_AI",
        "label": "Data / AI",
        "skills": [
            "Machine Learning", "Deep Learning", "NLP", "Pandas", "NumPy",
            "Scikit-learn", "TensorFlow", "PyTorch",
        ],
    },
    {
        "key": "CORE_CS",
        "label": "Core CS",
        "skills": [
            "Data Structures", "Algorithms", "DBMS", "Operating Systems",
            "Computer Networks", "OOP", "Software Engineering",
        ],
    },
    {
        "key": "TOOLS",
        "label": "Tools",
        "skills": ["Git", "GitHub", "Docker", "Linux"],
    },
    {
        "key": "CLOUD",
        "label": "Cloud",
        "skills": ["AWS", "Azure", "GCP"],
    },
    {
        "key": "INTERVIEW",
        "label": "Interview",
        "skills": ["Aptitude", "Communication", "Technical Interview", "Problem Solving"],
    },
]

# Canonical name -> category label (lookup built from SKILL_TAXONOMY)
SKILL_CATEGORY = {}
for _cat in SKILL_TAXONOMY:
    for _skill in _cat["skills"]:
        SKILL_CATEGORY[_skill] = _cat["label"]

# Lower-cased canonical name -> canonical casing (for exact matches)
_CANONICAL_BY_LOWER = {name.lower(): name for name in SKILL_CATEGORY}

# ------------------------------------------------------------
# 2. SKILL NORMALIZATION (aliases -> canonical taxonomy names)
# ------------------------------------------------------------
# Keys are lower-cased raw skill names. Values are one canonical
# name, or a LIST when the alias genuinely spans multiple skills
# (e.g. "DSA" == Data Structures AND Algorithms).
#
# Matching is EXACT on the normalized (lowercased, whitespace-
# stripped) raw name - there is no fuzzy/contains matching, so
# unrelated skills are never falsely classified.
SKILL_ALIASES = {
    # Programming
    "python": "Python",
    "java": "Java",
    "c": "C",
    "c++": "C++",
    "cpp": "C++",
    "javascript": "JavaScript",
    "js": "JavaScript",
    "java script": "JavaScript",
    "ecmascript": "JavaScript",
    "typescript": "TypeScript",
    "ts": "TypeScript",
    # Web
    "html": "HTML",
    "html5": "HTML",
    "css": "CSS",
    "css3": "CSS",
    "react": "React",
    "reactjs": "React",
    "react.js": "React",
    "node": "Node.js",
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "express": "Express",
    "expressjs": "Express",
    "express.js": "Express",
    "rest": "REST API",
    "rest api": "REST API",
    "restapi": "REST API",
    "restful api": "REST API",
    # Database
    "mysql": "MySQL",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "mongo": "MongoDB",
    "mongodb": "MongoDB",
    "sql": "SQL",
    # Data / AI
    "ml": "Machine Learning",
    "machinelearning": "Machine Learning",
    "machine learning": "Machine Learning",
    "deeplearning": "Deep Learning",
    "deep learning": "Deep Learning",
    "nlp": "NLP",
    "natural language processing": "NLP",
    "pandas": "Pandas",
    "numpy": "NumPy",
    "scikit learn": "Scikit-learn",
    "scikit-learn": "Scikit-learn",
    "sklearn": "Scikit-learn",
    "tensorflow": "TensorFlow",
    "pytorch": "PyTorch",
    "torch": "PyTorch",
    # Core CS
    "ds": "Data Structures",
    "datastructures": "Data Structures",
    "data structures": "Data Structures",
    "dsa": ["Data Structures", "Algorithms"],
    "data structures and algorithms": ["Data Structures", "Algorithms"],
    "algorithms": "Algorithms",
    "algo": "Algorithms",
    "dbms": "DBMS",
    "os": "Operating Systems",
    "operating system": "Operating Systems",
    "operating systems": "Operating Systems",
    "cn": "Computer Networks",
    "computer network": "Computer Networks",
    "computer networks": "Computer Networks",
    "oop": "OOP",
    "object oriented": "OOP",
    "object oriented programming": "OOP",
    "object-oriented programming": "OOP",
    "software engineering": "Software Engineering",
    # Tools
    "git": "Git",
    "github": "GitHub",
    "docker": "Docker",
    "linux": "Linux",
    # Cloud
    "aws": "AWS",
    "amazon web services": "AWS",
    "azure": "Azure",
    "gcp": "GCP",
    "google cloud": "GCP",
    "google cloud platform": "GCP",
    # Interview
    "aptitude": "Aptitude",
    "communication": "Communication",
    "communication skills": "Communication",
    "technical interview": "Technical Interview",
    "problem solving": "Problem Solving",
}

# ------------------------------------------------------------
# 3. PLACEMENT REQUIREMENTS
# ------------------------------------------------------------
# A generic software-placement requirement set. Each entry:
#   skill      - canonical skill name (or display name for an OR-group)
#   skills_any - optional OR-group: satisfied if ANY of these is present
#   category   - display category (must exist in SKILL_TAXONOMY labels)
#   priority   - HIGH / MEDIUM / LOW (see PRIORITY_RULES)
#   reason     - shown when the requirement is missing
#   action     - generic, educational improvement suggestion
#
# PRIORITY RULES (transparent, documented):
#   HIGH   - core CS fundamentals + at least one programming language.
#            Foundational: standard placement filters, and they unlock
#            most other skills (interviews, projects, internships).
#   MEDIUM - development essentials (Git, SQL) + communication.
#            Important, but often evaluated later or only for some roles.
#   LOW    - reserved for optional / nice-to-have requirements
#            (none configured today).
PLACEMENT_REQUIREMENTS = [
    # --- Core CS (each individually required) ---
    {
        "skill": "Data Structures",
        "category": "Core CS",
        "priority": "HIGH",
        "reason": "Required placement skill not found in verified profile",
        "action": "Practice arrays, strings, linked lists, stacks, queues, trees and graphs",
    },
    {
        "skill": "Algorithms",
        "category": "Core CS",
        "priority": "HIGH",
        "reason": "Required placement skill not found in verified profile",
        "action": "Practice sorting, searching, recursion, dynamic programming and greedy techniques",
    },
    {
        "skill": "OOP",
        "category": "Core CS",
        "priority": "HIGH",
        "reason": "Required placement skill not found in verified profile",
        "action": "Practice class design, inheritance, polymorphism and encapsulation",
    },
    {
        "skill": "DBMS",
        "category": "Core CS",
        "priority": "HIGH",
        "reason": "Required placement skill not found in verified profile",
        "action": "Study the relational model, normalization, transactions and indexing",
    },
    {
        "skill": "Operating Systems",
        "category": "Core CS",
        "priority": "HIGH",
        "reason": "Required placement skill not found in verified profile",
        "action": "Study processes, threads, scheduling, memory management and file systems",
    },
    {
        "skill": "Computer Networks",
        "category": "Core CS",
        "priority": "HIGH",
        "reason": "Required placement skill not found in verified profile",
        "action": "Study TCP/IP, HTTP, DNS and core networking concepts",
    },
    # --- Programming (ANY of these satisfies the requirement) ---
    {
        "skill": "Python OR Java OR C++",
        "skills_any": ["Python", "Java", "C++"],
        "category": "Programming",
        "priority": "HIGH",
        "reason": "At least one programming language (Python, Java or C++) is required",
        "action": "Learn one language deeply and practice problem solving with it",
    },
    # --- Development essentials ---
    {
        "skill": "Git",
        "category": "Tools",
        "priority": "MEDIUM",
        "reason": "Required placement skill not found in verified profile",
        "action": "Learn version control workflows: commit, branch, merge and pull requests",
    },
    {
        "skill": "SQL",
        "category": "Database",
        "priority": "MEDIUM",
        "reason": "Required placement skill not found in verified profile",
        "action": "Practice joins, aggregation and subqueries",
    },
    # --- Communication ---
    {
        "skill": "Communication",
        "category": "Interview",
        "priority": "MEDIUM",
        "reason": "Required placement skill not found in verified profile",
        "action": "Practice explaining technical concepts clearly and prepare for HR interviews",
    },
]


def normalize_skill(raw_skill) -> list:
    """Normalize one raw skill name to canonical taxonomy names.

    Returns a list of canonical names (0, 1 or more - "DSA" yields
    two). Never invents skills: unknown names return [].
    """
    if not raw_skill:
        return []
    name = str(raw_skill).strip()
    if not name:
        return []

    # Defensive: a single string may contain comma-separated skills
    if "," in name:
        results = []
        for part in name.split(","):
            results.extend(normalize_skill(part))
        return results

    key = name.lower()
    # Exact alias lookup first
    if key in SKILL_ALIASES:
        alias = SKILL_ALIASES[key]
        return list(alias) if isinstance(alias, list) else [alias]

    # Punctuation / whitespace-insensitive lookup (e.g. "React.js")
    compact = "".join(ch for ch in key if ch.isalnum())
    if compact in SKILL_ALIASES:
        alias = SKILL_ALIASES[compact]
        return list(alias) if isinstance(alias, list) else [alias]

    # Exact canonical name match (case-insensitive)
    if key in _CANONICAL_BY_LOWER:
        return [_CANONICAL_BY_LOWER[key]]

    return []


def skill_category(skill: str):
    """Category label for a canonical skill, or None if unknown."""
    return SKILL_CATEGORY.get(skill)
