# ============================================================
# PLACEPRO - PHASE 13 - COMPANY ELIGIBILITY ENGINE
# ============================================================
#
# Answers: "Is this VERIFIED student eligible for this company?"
# and - more importantly - "WHY?"
#
# HONESTY RULES
# -------------
#   - Missing information is NEVER treated as failure automatically.
#     Every requirement is PASS / FAIL / UNKNOWN:
#         CGPA 8.2 vs >= 7.5  -> PASS
#         CGPA 6.5 vs >= 7.5  -> FAIL
#         CGPA null           -> UNKNOWN
#   - A missing required skill is UNKNOWN ("not found in the verified
#     profile"), never "the student does not know it". The suggested
#     action is to add verified evidence / complete an assessment.
#   - Preferred skills NEVER block eligibility.
#   - ML placement probability is NOT used anywhere here: eligibility
#     is driven purely by the configured company requirements.
#
# ELIGIBILITY STATUS
# ------------------
#   ELIGIBLE      all mandatory requirements PASS
#   NOT_ELIGIBLE  one or more mandatory requirements FAIL
#   INCOMPLETE    no mandatory FAIL, but >=1 mandatory UNKNOWN
#
# REUSE (no duplicate implementations):
#   - Skill normalization + verified skills come from Phase 12
#     (readiness_service.collect_verified_skills + skill_taxonomy).
#   - cgpa / branch / counts / backlogs / aptitude come from the
#     Phase 10 ML-feature mapping (ml_feature_mapping).
#
# ============================================================

import re

from .company_store import get_active_companies, get_company  # Phase 28C store
from .ml_feature_mapping import map_profile_to_ml_features
from .profile_service import ProfileNotFoundError, get_profile
from .readiness_service import collect_verified_skills

# ------------------------------------------------------------
# ERRORS
# ------------------------------------------------------------


class EligibilityServiceError(Exception):
    status_code = 422


class CompanyNotFoundError(EligibilityServiceError):
    status_code = 404


# ------------------------------------------------------------
# REQUIREMENT CHECKERS (each returns a RequirementResult dict)
# ------------------------------------------------------------


def _result(requirement, student_value, required_value, status,
            explanation, mandatory=True, action=None):
    return {
        "requirement": requirement,
        "student_value": student_value,
        "required_value": required_value,
        "status": status,          # PASS / FAIL / UNKNOWN
        "mandatory": mandatory,
        "explanation": explanation,
        "action": action,
    }


def _check_cgpa(req, value):
    minimum = req.get("min_cgpa")
    if minimum is None:
        return None
    if value is None:
        return _result(
            "Minimum CGPA", None, minimum, "UNKNOWN",
            "Your CGPA has not been provided; this requirement "
            "cannot be confirmed.",
        )
    status = "PASS" if value >= minimum else "FAIL"
    explanation = (
        "CGPA meets the minimum requirement."
        if status == "PASS"
        else f"Your CGPA is {value}, while the minimum requirement is {minimum}."
    )
    return _result("Minimum CGPA", value, minimum, status, explanation)


def _check_backlogs(req, value):
    maximum = req.get("max_backlogs")
    if maximum is None:
        return None
    if value is None:
        return _result(
            "Maximum Backlogs", None, maximum, "UNKNOWN",
            "Your backlog count has not been provided; this "
            "requirement cannot be confirmed.",
        )
    status = "PASS" if value <= maximum else "FAIL"
    explanation = (
        "Backlog count is within the allowed limit."
        if status == "PASS"
        else f"You have {value} backlog(s), while the maximum allowed is {maximum}."
    )
    return _result("Maximum Backlogs", value, maximum, status, explanation)


def _check_branch(req, value):
    allowed = req.get("allowed_branches")
    if not allowed:
        return None
    if value is None:
        return _result(
            "Allowed Branch", None, allowed, "UNKNOWN",
            "Your branch has not been provided; this requirement "
            "cannot be confirmed.",
        )
    status = "PASS" if value in allowed else "FAIL"
    explanation = (
        f"Your branch ({value}) is in the allowed list."
        if status == "PASS"
        else f"Your branch ({value}) is not in the allowed list {allowed}."
    )
    return _result("Allowed Branch", value, allowed, status, explanation)


def _check_graduation_year(req, value):
    allowed = req.get("allowed_graduation_years")
    if not allowed:
        return None
    if value is None:
        return _result(
            "Graduation Year", None, allowed, "UNKNOWN",
            "Your graduation year has not been provided; this "
            "requirement cannot be confirmed.",
        )
    status = "PASS" if value in allowed else "FAIL"
    explanation = (
        f"Your graduation year ({value}) is in the allowed list."
        if status == "PASS"
        else f"Your graduation year ({value}) is not in the allowed list {allowed}."
    )
    return _result("Graduation Year", value, allowed, status, explanation)


def _check_count(req, key, label, value):
    minimum = req.get(key)
    if minimum is None:
        return None
    # Counts always come from the profile's verified lists (never null)
    status = "PASS" if value >= minimum else "FAIL"
    explanation = (
        f"{label} count meets the minimum requirement."
        if status == "PASS"
        else f"You have {value} {label.lower()}(s), while the minimum required is {minimum}."
    )
    return _result(f"Minimum {label}s", value, minimum, status, explanation)


_SKILL_ACTION = (
    "Add verified evidence of {skill} knowledge or complete the "
    "relevant assessment."
)


def _check_required_skills(req, present_skills):
    required = req.get("required_skills") or []
    results = []
    for skill in required:
        if skill in present_skills:
            results.append(_result(
                f"Required skill: {skill}", skill, skill, "PASS",
                f"Required skill '{skill}' is present in the verified profile.",
            ))
        else:
            results.append(_result(
                f"Required skill: {skill}", None, skill, "UNKNOWN",
                f"Required skill '{skill}' was not found in the verified "
                "profile.",
                action=_SKILL_ACTION.format(skill=skill),
            ))
    return results


def _check_preferred_skills(req, present_skills):
    preferred = req.get("preferred_skills") or []
    results = []
    for skill in preferred:
        if skill in present_skills:
            results.append(_result(
                f"Preferred skill: {skill}", skill, skill, "PASS",
                f"Preferred skill '{skill}' is present in the verified profile.",
                mandatory=False,
            ))
        else:
            results.append(_result(
                f"Preferred skill: {skill}", None, skill, "UNKNOWN",
                f"Preferred skill '{skill}' was not found in the verified "
                "profile (not mandatory).",
                mandatory=False,
            ))
    return results


# ------------------------------------------------------------
# ORCHESTRATION
# ------------------------------------------------------------


def _student_data(profile):
    """Gather the student values used by eligibility checks.

    Reuses the Phase 10 ML-feature mapping (single source of truth
    for cgpa / branch / counts / backlogs / aptitude) and Phase 12
    skill normalization for verified skills.
    """
    mapping = map_profile_to_ml_features(profile)
    education = profile.get("education") or {}
    return {
        "cgpa": mapping.get("cgpa"),
        "branch": mapping.get("branch"),          # already normalized
        "backlogs": mapping.get("backlogs"),
        "internships": mapping.get("internships"),
        "projects": mapping.get("projects_count"),
        "certifications": mapping.get("certifications"),
        "aptitude": mapping.get("aptitude_score"),
        "graduation_year": education.get("graduation_year"),
        "skills": {e["skill"] for e in collect_verified_skills(profile)},
    }


def evaluate_company_eligibility(profile: dict, company: dict) -> dict:
    """Evaluate one student profile against one company.

    Returns the full transparent eligibility result (never uses ML
    placement probability).
    """
    data = _student_data(profile)
    req = company.get("requirements") or {}

    results = []
    for checker in (
        lambda: _check_cgpa(req, data["cgpa"]),
        lambda: _check_backlogs(req, data["backlogs"]),
        lambda: _check_branch(req, data["branch"]),
        lambda: _check_graduation_year(req, data["graduation_year"]),
        lambda: _check_count(req, "min_internships", "Internship",
                             data["internships"]),
        lambda: _check_count(req, "min_projects", "Project",
                             data["projects"]),
        lambda: _check_count(req, "min_certifications", "Certification",
                             data["certifications"]),
    ):
        result = checker()
        if result is not None:
            results.append(result)

    if req.get("min_aptitude_score") is not None:
        minimum = req["min_aptitude_score"]
        if data["aptitude"] is None:
            results.append(_result(
                "Minimum Aptitude Score", None, minimum, "UNKNOWN",
                "Your aptitude score has not been provided; this "
                "requirement cannot be confirmed.",
            ))
        else:
            status = "PASS" if data["aptitude"] >= minimum else "FAIL"
            explanation = (
                "Aptitude score meets the minimum requirement."
                if status == "PASS"
                else f"Your aptitude score is {data['aptitude']}, while the "
                f"minimum requirement is {minimum}."
            )
            results.append(_result(
                "Minimum Aptitude Score", data["aptitude"], minimum,
                status, explanation,
            ))

    results.extend(_check_required_skills(req, data["skills"]))
    results.extend(_check_preferred_skills(req, data["skills"]))

    mandatory_failed = [
        r for r in results
        if r["mandatory"] and r["status"] == "FAIL"
    ]
    mandatory_unknown = [
        r for r in results
        if r["mandatory"] and r["status"] == "UNKNOWN"
    ]

    if mandatory_failed:
        status = "NOT_ELIGIBLE"
    elif mandatory_unknown:
        status = "INCOMPLETE"
    else:
        status = "ELIGIBLE"

    missing_information = []
    for r in results:
        if r["status"] == "UNKNOWN" and r["mandatory"] and \
                r["student_value"] is None:
            missing_information.append(_info_label(r))

    explanation = _build_explanation(status, company["company_name"],
                                     results, mandatory_failed,
                                     mandatory_unknown)

    return {
        "company_id": company["company_id"],
        "company_name": company["company_name"],
        "status": status,
        "requirements": {
            "passed": [r for r in results if r["status"] == "PASS"],
            "failed": [r for r in results if r["status"] == "FAIL"],
            "unknown": [r for r in results if r["status"] == "UNKNOWN"],
        },
        "missing_information": missing_information,
        "explanation": explanation,
    }


_INFO_LABELS = {
    "Minimum CGPA": "cgpa",
    "Maximum Backlogs": "backlogs",
    "Allowed Branch": "branch",
    "Graduation Year": "graduation_year",
    "Minimum Aptitude Score": "aptitude_score",
    "Minimum Internships": "internships",
    "Minimum Projects": "projects",
    "Minimum Certifications": "certifications",
}


def _info_label(result) -> str:
    """Clean human label for a missing piece of information."""
    requirement = result["requirement"]
    if requirement.startswith(("Required skill:", "Preferred skill:")):
        return requirement.split(": ", 1)[1]
    return _INFO_LABELS.get(requirement, requirement.lower())


def _build_explanation(status, company_name, results, failed, unknown):
    lines = []
    if status == "ELIGIBLE":
        lines.append(
            f"Your CGPA, branch, internship count, project count and "
            f"required skills satisfy all mandatory {company_name} "
            "requirements."
        )
    elif status == "NOT_ELIGIBLE":
        lines.append(
            "Not eligible because: "
            + ", ".join(sorted({r["requirement"] for r in failed}))
            + "."
        )
    else:  # INCOMPLETE
        unknown_labels = sorted(
            {r["requirement"] for r in unknown}
        )
        lines.append(
            "Eligibility cannot be confirmed because the following "
            "required information is missing: "
            + ", ".join(unknown_labels)
            + "."
        )

    for r in failed:
        lines.append(r["explanation"])
    for r in unknown:
        if r["mandatory"]:
            lines.append(r["explanation"])
    return lines


# ------------------------------------------------------------
# API ENTRY POINTS
# ------------------------------------------------------------


def list_companies():
    """Active companies as public summaries (no internal paths)."""
    return [
        {
            "company_id": c["company_id"],
            "company_name": c["company_name"],
            "industry": c.get("industry"),
            "roles": c.get("roles") or [],
        }
        for c in get_active_companies()
    ]


def get_company_detail(company_id: str) -> dict:
    """Public detail for one company (id validated against config)."""
    company = get_company(company_id)
    if company is None:
        raise CompanyNotFoundError(f"Company '{company_id}' not found.")
    return {
        "company_id": company["company_id"],
        "company_name": company["company_name"],
        "industry": company.get("industry"),
        "roles": company.get("roles") or [],
        "active": company.get("active", True),
        "requirements": company.get("requirements") or {},
    }


def _require_verified(profile) -> None:
    if not profile.get("verified"):
        raise EligibilityServiceError(
            "Student profile must be verified first."
        )


def get_eligibility(profile_id: str, company_id: str) -> dict:
    """Eligibility of a verified profile against one company."""
    profile, _ = get_profile(profile_id)  # raises ProfileNotFoundError
    _require_verified(profile)
    company = get_company(company_id)
    if company is None:
        raise CompanyNotFoundError(f"Company '{company_id}' not found.")
    return evaluate_company_eligibility(profile, company)


def get_all_eligibility(profile_id: str) -> dict:
    """Eligibility of a verified profile against ALL active companies."""
    profile, _ = get_profile(profile_id)
    _require_verified(profile)

    grouped = {"eligible": [], "not_eligible": [], "incomplete": []}
    for company in get_active_companies():
        result = evaluate_company_eligibility(profile, company)
        summary = {
            "company": {
                "company_id": company["company_id"],
                "company_name": company["company_name"],
                "industry": company.get("industry"),
                "roles": company.get("roles") or [],
            },
            "status": result["status"],
            "passed_count": len(result["requirements"]["passed"]),
            "failed_count": len(result["requirements"]["failed"]),
            "unknown_count": len(result["requirements"]["unknown"]),
            "major_reasons": result["explanation"][:3],
        }
        key = result["status"].lower()
        grouped[key].append(summary)

    return grouped
