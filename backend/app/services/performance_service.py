# ============================================================
# PLACEPRO - PHASE 27 - PERFORMANCE ANALYTICS SERVICE
# ============================================================
#
# Consolidated performance view for a verified profile:
#
#   profile (data/profiles/{id}.json)
#       |-- prediction_history   (Phase 11, server-recorded)
#       |-- assessment_evidence  (Phase 17, server-recorded)
#       |-- skills               (Phase 12 collection + Phase 17 view)
#
#   + Phase 12 readiness (recomputed live - never cached)
#
# HONESTY RULES
#   - Every value is computed from data that already exists.
#   - Empty history -> count 0 and None (never a default guess).
#   - No skill-progress-over-time is reported: per-attempt
#     assessment evidence exists, historical skill snapshots do not.
#   - The readiness score is NOT re-implemented here - it is
#     delegated to readiness_service.get_readiness().
#   - Assessment scores are 0-100 question-bank percentages only;
#     resume skill mentions are never turned into scores.
#
# Cross-service imports are done lazily inside the function, the
# same defensive pattern used by readiness_service and
# assessment_service.
#
# ============================================================


class PerformanceServiceError(Exception):
    status_code = 422


def get_performance(profile_id: str) -> dict:
    """Consolidated performance analytics for a VERIFIED profile.

    Raises ProfileNotFoundError (404) / InvalidProfileError (422)
    via the existing profile service, and PerformanceServiceError
    (422) when the profile is not verified - matching the Phase
    12-17 endpoint convention.
    """
    from .assessment_service import combined_skill_view
    from .profile_service import (
        ProfileNotFoundError,
        ProfileServiceError,
        get_profile,
    )
    from .readiness_service import get_readiness

    # 404 / invalid-id behavior comes from the existing store.
    profile, _ = get_profile(profile_id)

    if not profile.get("verified"):
        raise PerformanceServiceError(
            "Student profile must be verified first."
        )

    # --- Phase 12 readiness (delegated, recomputed live) ----------
    readiness = get_readiness(profile_id)

    # --- Phase 17 combined skill view (delegated) -----------------
    skills_view = combined_skill_view(profile_id)

    # --- Phase 11 prediction history summary ----------------------
    history = profile.get("prediction_history") or []
    probabilities = [e["placement_probability"] for e in history]
    prediction_summary = {
        "predictions_count": len(history),
        "latest_prediction": history[-1]["prediction"] if history else None,
        "latest_probability": probabilities[-1] if history else None,
        "latest_timestamp": history[-1]["timestamp"] if history else None,
        "highest_probability": max(probabilities) if history else None,
        "lowest_probability": min(probabilities) if history else None,
    }

    # --- Phase 17 assessment history summary ----------------------
    evidence = profile.get("assessment_evidence") or []
    scores = [e["score"] for e in evidence]
    assessment_summary = {
        "assessments_count": len(evidence),
        "skills_assessed": len({e["skill"] for e in evidence}),
        "average_score": (
            round(sum(scores) / len(scores), 1) if evidence else None
        ),
        "latest_skill": evidence[-1]["skill"] if evidence else None,
        "latest_score": scores[-1] if evidence else None,
        "latest_level": evidence[-1]["level"] if evidence else None,
        "latest_timestamp": evidence[-1]["timestamp"] if evidence else None,
    }

    return {
        "profile_id": profile["profile_id"],
        "verified": bool(profile.get("verified")),
        "summary": {
            "predictions": prediction_summary,
            "assessments": assessment_summary,
            "readiness_score": readiness["readiness_score"],
            "readiness_level": readiness["readiness_level"],
            "skills_tracked": len(skills_view["skills"]),
        },
        "prediction_history": history,
        "assessment_history": evidence,
        "readiness": readiness,
        "skills": skills_view["skills"],
    }
