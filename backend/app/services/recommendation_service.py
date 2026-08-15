# ============================================================
# PLACEPRO - PHASE 14 - COMPANY RECOMMENDATION ENGINE
# ============================================================
#
# Answers: "Which companies are the best matches for this
# VERIFIED student?" - and WHY, transparently.
#
# The engine ranks every active demo company using FIVE signals:
#
#   1. Company eligibility   (Phase 13 result)
#   2. Skill match           (verified skills vs company
#                             required/preferred skills)
#   3. Readiness score       (Phase 12 result)
#   4. Placement probability (Phase 8 model, via the Phase 11
#                             mapping - model-estimated only)
#   5. Profile completeness  (Phase 12 profile_completeness)
#
# RECOMMENDATION SCORE (transparent weighted formula, 0-100)
# -----------------------------------------------------------
#   eligibility component     30 pts  ELIGIBLE -> 30; INCOMPLETE ->
#                                     30 * (mandatory passed / total);
#                                     NOT_ELIGIBLE -> 0
#   skill match component     25 pts  25 * (0.75 * required matched
#                                     fraction + 0.25 * preferred
#                                     matched fraction)
#   readiness component       20 pts  readiness_score / 100 * 20
#   placement probability     15 pts  probability * 15 (0 when the
#                                     model cannot run - missing ML
#                                     features are never invented)
#   profile completeness      10 pts  completeness % / 100 * 10
#
# ELIGIBILITY OVERRIDE (critical)
# ------------------------------
# Mandatory eligibility failures override the score:
#   NOT_ELIGIBLE  -> status NOT_RECOMMENDED (score shown but
#                    informational)
#   INCOMPLETE    -> status INCOMPLETE (eligibility cannot be
#                    confirmed - score is provisional)
#   ELIGIBLE      -> RECOMMENDED if score >= RECOMMENDED_THRESHOLD
#                    else ELIGIBLE
#
# The score is a transparent heuristic - it is NOT a machine-
# learning probability. The ML probability is only the Phase 8
# model's estimate of the placement target in the training data
# and is always labeled "Model-estimated placement probability".
#
# REUSE (no duplicate implementations):
#   - eligibility   : Phase 13 evaluate_company_eligibility
#   - skills        : Phase 12 skill_taxonomy + collect_verified_skills
#   - readiness     : Phase 12 get_readiness
#   - ML probability: Phase 8 model via ml_feature_mapping + the
#                     Phase 8 prediction wrapper (read-only - this
#                     view does NOT write prediction history)
#
# ============================================================

from ..data.companies import get_active_companies
from .eligibility_service import evaluate_company_eligibility
from .ml_feature_mapping import check_profile_completion
from .prediction_service import predict as predict_with_model
from .profile_service import get_profile
from .readiness_service import collect_verified_skills, get_readiness

# ------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------

# A verified-eligible company is RECOMMENDED when its score is at
# or above this documented threshold.
RECOMMENDED_THRESHOLD = 75.0

# Documented weights (sum to 100).
SCORE_WEIGHTS = {
    "eligibility": 30,
    "skill_match": 25,
    "readiness": 20,
    "placement_probability": 15,
    "profile_completeness": 10,
}

# Bucket priority used by the optional ?limit= (recommended first).
_BUCKET_PRIORITY = ("recommended", "eligible", "incomplete", "not_recommended")


class RecommendationServiceError(Exception):
    status_code = 422


# ------------------------------------------------------------
# SKILL MATCH
# ------------------------------------------------------------


def compute_skill_match(company: dict, present_skills: set) -> dict:
    """Required/preferred skill match for one company.

    Returns {score, required_matched, required_missing,
             preferred_matched, preferred_missing}. Score is
      round((0.75 * required_fraction + 0.25 * preferred_fraction) * 100, 1)
    with a fraction of 1.0 when a category has no skills configured.
    """
    requirements = company.get("requirements") or {}
    required = list(requirements.get("required_skills") or [])
    preferred = list(requirements.get("preferred_skills") or [])

    required_matched = [s for s in required if s in present_skills]
    required_missing = [s for s in required if s not in present_skills]
    preferred_matched = [s for s in preferred if s in present_skills]
    preferred_missing = [s for s in preferred if s not in present_skills]

    required_fraction = (
        len(required_matched) / len(required) if required else 1.0
    )
    preferred_fraction = (
        len(preferred_matched) / len(preferred) if preferred else 1.0
    )
    score = round(
        (0.75 * required_fraction + 0.25 * preferred_fraction) * 100, 1
    )
    return {
        "score": score,
        "required_matched": required_matched,
        "required_missing": required_missing,
        "preferred_matched": preferred_matched,
        "preferred_missing": preferred_missing,
    }


# ------------------------------------------------------------
# SCORING
# ------------------------------------------------------------


def _eligibility_component(eligibility: dict) -> float:
    status = eligibility["status"]
    if status == "ELIGIBLE":
        return float(SCORE_WEIGHTS["eligibility"])
    if status == "NOT_ELIGIBLE":
        return 0.0
    # INCOMPLETE: credit the mandatory requirements that DID pass
    mandatory = [
        r for group in ("passed", "failed", "unknown")
        for r in eligibility["requirements"][group] if r["mandatory"]
    ]
    if not mandatory:
        return 0.0
    passed = sum(1 for r in mandatory if r["status"] == "PASS")
    return round(
        SCORE_WEIGHTS["eligibility"] * (passed / len(mandatory)), 1
    )


def _recommendation_score(eligibility, skill_match, readiness_score,
                          placement_probability, completeness_pct) -> float:
    components = {
        "eligibility": _eligibility_component(eligibility),
        "skill_match": round(skill_match["score"] / 100 * SCORE_WEIGHTS["skill_match"], 1),
        "readiness": round(readiness_score / 100 * SCORE_WEIGHTS["readiness"], 1),
        "placement_probability": (
            round(placement_probability * SCORE_WEIGHTS["placement_probability"], 1)
            if placement_probability is not None else 0.0
        ),
        "profile_completeness": round(
            completeness_pct / 100 * SCORE_WEIGHTS["profile_completeness"], 1
        ),
    }
    return round(min(100.0, sum(components.values())), 1)


# ------------------------------------------------------------
# REASONS / ACTIONS (explainability + honesty)
# ------------------------------------------------------------


def _build_reasons(item_ctx) -> list:
    status = item_ctx["status"]
    eligibility = item_ctx["eligibility"]
    skill_match = item_ctx["skill_match"]
    readiness_score = item_ctx["readiness_score"]
    readiness_level = item_ctx["readiness_level"]
    probability = item_ctx["placement_probability"]
    required = item_ctx["required_total"]

    if status in ("RECOMMENDED", "ELIGIBLE"):
        reasons = ["All mandatory eligibility requirements satisfied"]
        reasons.append(
            f"Skill match: {skill_match['score']}% "
            f"({len(skill_match['required_matched'])}/{required} "
            "required skills matched)"
        )
        reasons.append(
            f"Readiness score: {readiness_score} ({readiness_level})"
        )
        if probability is not None:
            reasons.append(
                f"Model-estimated placement probability: "
                f"{probability * 100:.0f}%"
            )
        if status == "RECOMMENDED":
            reasons.append("Strong overall fit - top recommendation")
        return reasons

    if status == "INCOMPLETE":
        missing = eligibility.get("missing_information") or []
        if missing:
            return [
                "Not enough information to confirm eligibility because: "
                + ", ".join(missing) + "."
            ]
        return ["Eligibility cannot be confirmed because required "
                "information is missing."]

    # NOT_RECOMMENDED
    failed = [r["explanation"] for r in eligibility["requirements"]["failed"]]
    if failed:
        return ["Not recommended because " + " ".join(failed)]
    return ["Not recommended because mandatory eligibility "
            "requirements are not satisfied."]


def _build_improvement_actions(skill_match: dict) -> list:
    return [f"Strengthen {skill} knowledge"
            for skill in skill_match["required_missing"]]


# ------------------------------------------------------------
# ORCHESTRATION
# ------------------------------------------------------------


def _require_verified(profile) -> None:
    if not profile.get("verified"):
        raise RecommendationServiceError(
            "Student profile must be verified first."
        )


def build_recommendation(profile, company, readiness, placement_probability,
                         present_skills) -> dict:
    """One company's recommendation for a verified profile."""
    eligibility = evaluate_company_eligibility(profile, company)
    skill_match = compute_skill_match(company, present_skills)

    readiness_score = readiness["readiness_score"]
    completeness_pct = readiness["profile_completeness"]["percentage"]
    score = _recommendation_score(
        eligibility, skill_match, readiness_score,
        placement_probability, completeness_pct,
    )

    # Eligibility semantics override the numerical score.
    if eligibility["status"] == "NOT_ELIGIBLE":
        status = "NOT_RECOMMENDED"
    elif eligibility["status"] == "INCOMPLETE":
        status = "INCOMPLETE"
    else:
        status = "RECOMMENDED" if score >= RECOMMENDED_THRESHOLD else "ELIGIBLE"

    context = {
        "status": status,
        "eligibility": eligibility,
        "skill_match": skill_match,
        "readiness_score": readiness_score,
        "readiness_level": readiness["readiness_level"],
        "placement_probability": placement_probability,
        "required_total": len(company.get("requirements", {}).get(
            "required_skills") or []),
    }

    return {
        "company_id": company["company_id"],
        "company_name": company["company_name"],
        "status": status,
        "recommendation_score": score,
        "eligibility_status": eligibility["status"],
        "skill_match": skill_match,
        "readiness_score": readiness_score,
        "readiness_level": readiness["readiness_level"],
        "placement_probability": placement_probability,
        "reasons": _build_reasons(context),
        "improvement_actions": _build_improvement_actions(skill_match),
        "missing_information": eligibility.get("missing_information") or [],
    }


def _placement_probability(profile):
    """Model-estimated placement probability (read-only, no history).

    Uses the SAME Phase 10 feature mapping and Phase 8 model as the
    Phase 11 prediction flow, but does NOT write prediction history:
    recommendations are a read-only view. Returns None when ML
    features are incomplete (missing features are never invented).
    """
    completion = check_profile_completion(profile)
    if not completion["profile_complete"]:
        return None
    result = predict_with_model(completion["ml_feature_mapping"])
    return result["placement_probability"]


def get_recommendations(profile_id: str, limit=None) -> dict:
    """Rank every active company for a verified profile.

    Grouped into recommended / eligible / incomplete /
    not_recommended, each sorted by recommendation_score descending.
    `limit` (optional, validated by the route) caps the TOTAL number
    of items, filling buckets in priority order so semantics are
    preserved.
    """
    profile, _ = get_profile(profile_id)  # raises ProfileNotFoundError
    _require_verified(profile)

    readiness = get_readiness(profile_id)  # Phase 12 (verified enforced)
    placement_probability = _placement_probability(profile)
    present_skills = {e["skill"] for e in collect_verified_skills(profile)}

    grouped = {"recommended": [], "eligible": [],
               "incomplete": [], "not_recommended": []}
    for company in get_active_companies():
        item = build_recommendation(
            profile, company, readiness, placement_probability,
            present_skills,
        )
        grouped[item["status"].lower()].append(item)

    for bucket in grouped.values():
        bucket.sort(key=lambda i: -i["recommendation_score"])

    if limit is not None:
        # Cap the total across buckets, respecting bucket priority.
        remaining = int(limit)
        for bucket in _BUCKET_PRIORITY:
            if remaining <= 0:
                grouped[bucket] = []
                continue
            if len(grouped[bucket]) > remaining:
                grouped[bucket] = grouped[bucket][:remaining]
            remaining -= len(grouped[bucket])

    return {"profile_id": profile["profile_id"], "recommendations": grouped}
