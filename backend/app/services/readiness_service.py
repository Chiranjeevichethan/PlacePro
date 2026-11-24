# ============================================================
# PLACEPRO - PHASE 12 - PLACEMENT READINESS & SKILL GAP ENGINE
# ============================================================
#
# Transparent, rule-based analysis. It answers:
#   1. What skills does the student already have?
#   2. What are the student's strengths?
#   3. What skills are missing or weak?
#   4. What should the student improve first?
#   5. How ready is the student for placements?
#
# CONCEPTUAL SEPARATION (never merged):
#   A. ML placement probability  -> ONLY from the Phase 8 model
#                                   (src/pipeline.py, via Phase 11).
#   B. Placement readiness score -> this module: transparent,
#                                   rule-based, 0-100, explained by
#                                   a documented breakdown.
#   C. Skill gap                 -> comparison of VERIFIED profile
#                                   skills against PLACEMENT_REQUIREMENTS.
#   D. Recommendations           -> derived from the skill-gap analysis.
#
# HONESTY RULES:
#   - Only VERIFIED profile information is used.
#   - A missing skill is reported as "not found in verified profile" -
#     never as "the student does not know X".
#   - Skill presence is NEVER converted into an artificial numeric
#     skill score.
#   - The readiness score is NOT ML accuracy and is never presented
#     as such.
#
# ============================================================

from .profile_service import get_profile
from .score_levels import classify_percentage
from .skill_evidence import (
    assessment_readiness_bonus,
    resolve_skill_evidence,
    skill_status,
)
from .skill_taxonomy import (
    PLACEMENT_REQUIREMENTS,
    skill_category,
)

# ------------------------------------------------------------
# ERRORS
# ------------------------------------------------------------


class ReadinessServiceError(Exception):
    status_code = 422


# ------------------------------------------------------------
# READINESS LEVELS (documented, transparent)
# ------------------------------------------------------------
READINESS_LEVELS = [
    (0, 40, "Needs Improvement"),
    (40, 60, "Developing"),
    (60, 75, "Placement Ready"),
    (75, 90, "Strong"),
    (90, 100, "Highly Ready"),
]

# ------------------------------------------------------------
# READINESS SCORE WEIGHTS (documented, sum to 100)
# ------------------------------------------------------------
#   technical_skills     30  share of core+programming placement
#                            requirements met (7 slots: 6 core CS +
#                            1 programming language OR-group)
#   projects             20  evidence of applied work
#                            (0->0, 1->10, 2->16, >=3->20)
#   internships          15  industry exposure
#                            (0->0, 1->10, >=2->15)
#   certifications        8  (0->0, 1->4, >=2->8)
#   communication         7  Communication skill present -> 7
#   profile_completeness 20  fraction of the 8 canonical profile
#                            sections that are filled
#                            (personal, education, skills, experience,
#                             internships, projects, certifications,
#                             achievements)
#
# Rationale: foundational technical skills and demonstrated
# experience (projects/internships) dominate; listing many skills
# alone cannot produce a high score (a student with 20 listed
# skills but no projects or internships stays capped well below
# the top). Every component is explainable - there are no
# arbitrary hidden "AI" scores.
READINESS_WEIGHTS = {
    "technical_skills": 30,
    "projects": 20,
    "internships": 15,
    "certifications": 8,
    "communication": 7,
    "profile_completeness": 20,
}

_CANONICAL_SECTIONS = (
    "personal", "education", "skills", "experience",
    "internships", "projects", "certifications", "achievements",
)

_PROJECT_LEVELS = [(0, 0), (1, 10), (2, 16), (3, 20)]  # count -> points
_INTERNSHIP_LEVELS = [(0, 0), (1, 10), (2, 15)]
_CERTIFICATION_LEVELS = [(0, 0), (1, 4), (2, 8)]


# ------------------------------------------------------------
# 1. SKILL COLLECTION (verified profile -> skill entries)
# ------------------------------------------------------------


def collect_verified_skills(profile: dict) -> list:
    """Compatibility wrapper returning evidence that satisfies the shared policy."""
    return resolve_skill_evidence(profile)["accepted_entries"]


# ------------------------------------------------------------
# 2. STRENGTHS (evidence-based)
# ------------------------------------------------------------
# A strength is a skill with evidence from at least 2 DISTINCT
# sources (e.g. 3 projects + 1 internship). Evidence is factual
# profile information - never fabricated.


def compute_strengths(skill_entries: list, limit: int = 5) -> list:
    by_skill = {}
    for entry in skill_entries:
        by_skill.setdefault(entry["skill"], []).append(entry)

    strengths = []
    for skill, entries in by_skill.items():
        sources = {}
        for entry in entries:
            sources[entry["source"]] = sources.get(entry["source"], 0) + 1
        if len(sources) < 2:
            continue  # single source is not enough evidence of strength
        evidence = []
        for source, count in sorted(sources.items(), key=lambda kv: -kv[1]):
            if source == "projects":
                evidence.append(f"{count} project{'s' if count != 1 else ''}")
            elif source == "internships":
                evidence.append(f"{count} internship{'s' if count != 1 else ''}")
            elif source == "experience":
                evidence.append(f"{count} experience role{'s' if count != 1 else ''}")
            elif source == "certifications":
                evidence.append("certification")
            elif source == "assessment":
                evidence.append("qualifying PlacePro assessment")
            else:
                evidence.append(f"listed in {source} skills")
        strengths.append(
            {
                "skill": skill,
                "category": skill_category(skill),
                "evidence": evidence,
                "_total": sum(sources.values()),
            }
        )

    strengths.sort(key=lambda s: -s["_total"])
    for strength in strengths:
        strength.pop("_total", None)
    return strengths[:limit]


# ------------------------------------------------------------
# 3. SKILL GAPS (verified skills vs PLACEMENT_REQUIREMENTS)
# ------------------------------------------------------------
# A missing skill is reported as a gap ONLY because it is a
# defined placement requirement and was not found in the verified
# profile - not because the student is presumed not to know it.


def compute_skill_gaps(skill_entries: list, evidence=None) -> list:
    present = {entry["skill"] for entry in skill_entries}
    gaps = []
    for req in PLACEMENT_REQUIREMENTS:
        if req.get("skills_any"):
            if not any(s in present for s in req["skills_any"]):
                gaps.append(
                    {
                        "skill": req["skill"],
                        "category": req["category"],
                        "priority": req["priority"],
                        "reason": req["reason"],
                        "action": req["action"],
                    }
                )
        elif req["skill"] not in present:
            gaps.append(
                {
                    "skill": req["skill"],
                    "category": req["category"],
                    "priority": req["priority"],
                    "reason": req["reason"],
                    "action": req["action"],
                }
            )
    for gap in gaps:
        requirement = next(req for req in PLACEMENT_REQUIREMENTS if req["skill"] == gap["skill"])
        names = requirement.get("skills_any") or [gap["skill"]]
        statuses = [skill_status(evidence, name) for name in names] if evidence else ['MISSING']
        status = next((s for s in ('INSUFFICIENT', 'INVALID', 'UNCONFIRMED') if s in statuses), 'MISSING')
        gap["evidence_status"] = status
        if status == 'INSUFFICIENT':
            gap["reason"] = "Latest verified PlacePro assessment evidence is below the qualifying score of 60"
        elif status == 'INVALID':
            gap["reason"] = "Recorded assessment evidence has an invalid score or source; skill evidence cannot be confirmed"
        elif status == 'UNCONFIRMED':
            gap["reason"] = "Recorded skill evidence has not been confirmed"
    return gaps


# ------------------------------------------------------------
# 4. PLACEMENT READINESS SCORE (transparent, 0-100)
# ------------------------------------------------------------


def _profile_completeness(profile: dict) -> dict:
    """Fraction of the 8 canonical sections that are filled."""
    missing = []
    for section in _CANONICAL_SECTIONS:
        value = profile.get(section)
        if not value:
            missing.append(section)
            continue
        if isinstance(value, dict) and not any(
            v for v in value.values()
        ):
            missing.append(section)
        elif isinstance(value, list) and not value:
            missing.append(section)
    filled = len(_CANONICAL_SECTIONS) - len(missing)
    percentage = round(filled / len(_CANONICAL_SECTIONS) * 100)
    return {"percentage": percentage, "missing_fields": missing}


def _points_for(count: int, levels) -> int:
    """Map a count to points using a documented threshold table."""
    points = 0
    for threshold, pts in levels:
        if count >= threshold:
            points = pts
    return points


def compute_readiness_score(profile: dict, skill_entries: list, evidence=None) -> dict:
    """Compute the 0-100 readiness score + documented breakdown.

    Returns {readiness_score, breakdown:{...}} where breakdown sums
    to <= 100 and every component is explained by READINESS_WEIGHTS.
    """
    present = {entry["skill"] for entry in skill_entries}

    # technical_skills: 6 core requirements + 1 language OR-group
    core_reqs = [
        req for req in PLACEMENT_REQUIREMENTS
        if req["priority"] == "HIGH" and not req.get("skills_any")
    ]
    lang_req = next(
        (req for req in PLACEMENT_REQUIREMENTS if req.get("skills_any")), None
    )
    total_slots = len(core_reqs) + (1 if lang_req else 0)
    met = sum(1 for req in core_reqs if req["skill"] in present)
    if lang_req and any(s in present for s in lang_req["skills_any"]):
        met += 1
    technical = round(met / total_slots * READINESS_WEIGHTS["technical_skills"])

    projects = _points_for(
        len(profile.get("projects") or []), _PROJECT_LEVELS
    )
    internships = _points_for(
        len(profile.get("internships") or []), _INTERNSHIP_LEVELS
    )
    certifications = _points_for(
        len(profile.get("certifications") or []), _CERTIFICATION_LEVELS
    )
    communication = (
        READINESS_WEIGHTS["communication"]
        if "Communication" in present
        else 0
    )
    completeness = _profile_completeness(profile)
    profile_points = round(
        completeness["percentage"] / 100 * READINESS_WEIGHTS["profile_completeness"]
    )

    # PHASE 17 - assessment evidence bonus (documented, capped).
    # Verified assessment scores strengthen the technical component:
    #   bonus = ASSESSMENT_READINESS_BONUS_MAX * (avg latest score / 100)
    # Only the LATEST score per skill counts (repeated attempts can
    # not inflate the bonus - a student who retries and scores lower
    # gets the lower latest score, and the bonus is capped at 5 pts).
    assessment_bonus = assessment_readiness_bonus(evidence or resolve_skill_evidence(profile))
    technical = min(technical + assessment_bonus,
                    READINESS_WEIGHTS["technical_skills"])

    breakdown = {
        "technical_skills": technical,
        "projects": projects,
        "internships": internships,
        "certifications": certifications,
        "communication": communication,
        "profile_completeness": profile_points,
    }
    score = round(min(100, sum(breakdown.values())), 1)
    return {"readiness_score": score, "breakdown": breakdown}


def _assessment_bonus(profile: dict) -> float:
    """Capped readiness bonus from verified assessment evidence.

    Uses the LATEST score per assessed skill only; scores below 60
    (Developing/Beginner) contribute no bonus. See docs/skill-evidence-policy.md.
    """
    return assessment_readiness_bonus(resolve_skill_evidence(profile))


def readiness_level(score: float) -> str:
    """Map a readiness score to a documented level."""
    return classify_percentage(score, READINESS_LEVELS)


# ------------------------------------------------------------
# 5. IMPROVEMENT PLAN (from skill gaps)
# ------------------------------------------------------------


def build_improvement_plan(gaps: list) -> list:
    """Prioritized plan: HIGH first, then MEDIUM, then LOW.

    Entries are generic and educational - never a placement
    guarantee.
    """
    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    ordered = sorted(
        gaps, key=lambda g: (priority_order.get(g["priority"], 9), g["skill"])
    )
    return [
        {
            "priority": index,
            "skill": gap["skill"],
            "reason": gap["reason"],
            "action": gap["action"],
        }
        for index, gap in enumerate(ordered, start=1)
    ]


# ------------------------------------------------------------
# 6. ORCHESTRATION
# ------------------------------------------------------------


def _require_verified(profile: dict) -> None:
    if not profile.get("verified"):
        raise ReadinessServiceError(
            "Student profile must be verified first."
        )


def get_readiness(profile_id: str) -> dict:
    """Full readiness analysis for a profile.

    Only verified profiles are analyzed. Returns:
      {profile_id, readiness_score, readiness_level, strengths,
       skill_gaps, improvement_plan, profile_completeness}
    """
    profile, _ = get_profile(profile_id)
    return readiness_for_profile(profile)


def readiness_for_profile(profile: dict, evidence=None) -> dict:
    """Analyze one loaded snapshot, shared with recommendation orchestration."""
    _require_verified(profile)

    evidence = evidence or resolve_skill_evidence(profile)
    skill_entries = evidence["accepted_entries"]
    strengths = compute_strengths(skill_entries)
    gaps = compute_skill_gaps(skill_entries, evidence)
    score_result = compute_readiness_score(profile, skill_entries, evidence)
    completeness = _profile_completeness(profile)

    return {
        "profile_id": profile["profile_id"],
        "source_revision": profile.get('revision', 0),
        "readiness_score": score_result["readiness_score"],
        "readiness_level": readiness_level(score_result["readiness_score"]),
        "readiness_breakdown": score_result["breakdown"],
        "strengths": strengths,
        "skill_gaps": gaps,
        "improvement_plan": build_improvement_plan(gaps),
        "profile_completeness": completeness,
    }


def get_placement_summary(profile_id: str, *, snapshot=None) -> dict:
    """Combined view: Phase 11 ML prediction + Phase 12 readiness.

    The two scores are NEVER merged - they measure different
    things and are reported side by side. The prediction goes
    through the verified/complete model gate on the same snapshot.
    This GET does not append prediction history.
    """
    profile = snapshot if snapshot is not None else get_profile(profile_id)[0]
    readiness = readiness_for_profile(profile)

    from .profile_service import prediction_for_snapshot

    prediction = prediction_for_snapshot(profile)

    return {
        "profile_id": profile_id,
        "source_revision": profile.get('revision', 0),
        "ready_for_prediction": prediction["ready_for_prediction"],
        "prediction": prediction.get("prediction"),
        "placement_probability": prediction.get("placement_probability"),
        "confidence": prediction.get("confidence"),
        "model_version": prediction.get("model_version"),
        "missing_fields": prediction.get("missing_fields", []),
        "reason": prediction.get("reason"),
        "readiness_score": readiness["readiness_score"],
        "readiness_level": readiness["readiness_level"],
        "readiness_breakdown": readiness["readiness_breakdown"],
        "strengths": readiness["strengths"],
        "skill_gaps": readiness["skill_gaps"],
        "improvement_plan": readiness["improvement_plan"],
    }
