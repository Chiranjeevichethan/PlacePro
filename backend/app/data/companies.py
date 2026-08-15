# ============================================================
# PLACEPRO - PHASE 13 - DEMO COMPANY DATASET
# ============================================================
#
# IMPORTANT DISCLAIMER
# --------------------
# These are SAMPLE / DEMO company requirements used to exercise
# the eligibility engine. They are NOT official hiring criteria
# for any real company. Real companies' requirements must be
# supplied by an authorized placement/admin user (future phase).
#
# This module is the SINGLE configured source of company data.
# Routes never hard-code company logic - they read from here.
#
# Requirement fields (all optional; absent = not evaluated):
#   min_cgpa                 minimum CGPA (e.g. 7.5)
#   max_backlogs             maximum allowed backlogs (e.g. 0)
#   allowed_branches         list of allowed branches (dataset
#                            values: CSE, IT, ECE, EE, ME, CE, Chemical)
#   allowed_graduation_years list of allowed graduation years
#   required_skills          mandatory skills (normalized via the
#                            Phase 12 taxonomy)
#   preferred_skills         optional skills - missing ones NEVER
#                            block eligibility
#   min_internships          minimum internship count
#   min_projects             minimum project count
#   min_certifications       minimum certification count
#   min_aptitude_score       minimum aptitude score (from the
#                            profile's ml_inputs.aptitude_score)
#
# ============================================================

# A company that is not "active" is excluded from the company list
# and from all-company eligibility.
ACTIVE_COMPANIES = []

_COMPANIES = [
    {
        "company_id": "company_001",
        "company_name": "DemoTech",
        "industry": "Software (DEMO requirements)",
        "roles": ["Software Engineer"],
        "active": True,
        "requirements": {
            "min_cgpa": 7.5,
            "max_backlogs": 0,
            "allowed_branches": ["CSE", "IT", "ECE"],
            "allowed_graduation_years": [2026, 2027],
            "required_skills": ["Python", "SQL", "Data Structures"],
            "preferred_skills": ["AWS", "Docker"],
            "min_internships": 1,
            "min_projects": 2,
            "min_certifications": 0,
            "min_aptitude_score": 60,
        },
    },
    {
        "company_id": "company_002",
        "company_name": "FinTech Solutions",
        "industry": "FinTech (DEMO requirements)",
        "roles": ["Backend Developer"],
        "active": True,
        "requirements": {
            "min_cgpa": 8.0,
            "max_backlogs": 0,
            "allowed_branches": ["CSE", "IT"],
            "required_skills": ["Java", "SQL", "OOP"],
            "preferred_skills": ["Spring", "MySQL"],
            "min_internships": 1,
            "min_projects": 1,
            "min_aptitude_score": 70,
        },
    },
    {
        "company_id": "company_003",
        "company_name": "CloudWorks",
        "industry": "Cloud (DEMO requirements)",
        "roles": ["Cloud Engineer"],
        "active": True,
        "requirements": {
            "min_cgpa": 7.0,
            "max_backlogs": 2,
            "allowed_branches": ["CSE", "IT", "ECE", "EE"],
            "required_skills": ["AWS", "Linux", "Python"],
            "preferred_skills": ["Docker", "GCP"],
            "min_internships": 0,
            "min_projects": 1,
            "min_certifications": 1,
        },
    },
    {
        "company_id": "company_004",
        "company_name": "DataSystems",
        "industry": "Data (DEMO requirements)",
        "roles": ["Data Engineer"],
        "active": True,
        "requirements": {
            "min_cgpa": 7.5,
            "max_backlogs": 1,
            "allowed_branches": ["CSE", "IT"],
            "required_skills": ["Python", "SQL", "Machine Learning"],
            "preferred_skills": ["Pandas", "NumPy"],
            "min_internships": 0,
            "min_projects": 2,
        },
    },
    {
        "company_id": "company_005",
        "company_name": "WebTech",
        "industry": "Web (DEMO requirements)",
        "roles": ["Frontend Developer"],
        "active": True,
        "requirements": {
            "min_cgpa": 6.5,
            "max_backlogs": 3,
            "allowed_branches": ["CSE", "IT", "ECE", "EE", "ME", "CE", "Chemical"],
            "required_skills": ["JavaScript", "HTML", "CSS"],
            "preferred_skills": ["React", "TypeScript"],
            "min_internships": 0,
            "min_projects": 1,
        },
    },
    {
        "company_id": "company_006",
        "company_name": "AI Solutions",
        "industry": "Artificial Intelligence (DEMO requirements)",
        "roles": ["Machine Learning Engineer"],
        "active": True,
        "requirements": {
            "min_cgpa": 8.0,
            "max_backlogs": 0,
            "allowed_branches": ["CSE", "IT", "ECE"],
            "required_skills": ["Python", "Machine Learning", "Data Structures"],
            "preferred_skills": ["TensorFlow", "PyTorch"],
            "min_internships": 1,
            "min_projects": 3,
            "min_certifications": 1,
            "min_aptitude_score": 70,
        },
    },
    {
        "company_id": "company_007",
        "company_name": "InnovateLabs",
        "industry": "Product (DEMO requirements)",
        "roles": ["Product Engineer"],
        "active": True,
        "requirements": {
            "min_cgpa": 7.0,
            "max_backlogs": 1,
            "allowed_branches": ["CSE", "IT", "ECE"],
            "required_skills": ["Python", "Git", "Communication"],
            "preferred_skills": ["Docker", "React"],
            "min_internships": 1,
            "min_projects": 2,
        },
    },
    # Inactive example: demonstrates the `active` flag (excluded from
    # /api/companies and all-company eligibility).
    {
        "company_id": "company_900",
        "company_name": "ArchiveTech",
        "industry": "Software (DEMO requirements)",
        "roles": ["Software Engineer"],
        "active": False,
        "requirements": {
            "min_cgpa": 9.0,
            "max_backlogs": 0,
            "allowed_branches": ["CSE"],
        },
    },
]

ACTIVE_COMPANIES = [c for c in _COMPANIES if c.get("active", True)]


def get_company(company_id: str):
    """Return a company dict by id (active or not), or None."""
    for company in _COMPANIES:
        if company["company_id"] == company_id:
            return company
    return None


def get_active_companies():
    """Return all active companies (the ones students can be checked against)."""
    return list(ACTIVE_COMPANIES)
