# ============================================================
# PLACEPRO - PHASE 17 - SKILL ASSESSMENT ENGINE
# ============================================================
#
# A real, evidence-based skill assessment system. A resume mention
# is NOT a skill score - a numerical score comes ONLY from an
# actual assessment, evaluated server-side.
#
# FLOW
#   POST /api/assessment/start            -> session (questions, no answers)
#   POST /api/assessment/{id}/submit      -> server-side scoring
#   GET  /api/profile/{id}/assessments    -> attempt history
#   GET  /api/profile/{id}/skills         -> combined skill view
#
# SECURITY / INTEGRITY
#   - Answer keys NEVER leave the server (start responses strip
#     correct_answer/explanation).
#   - Scoring is 100% server-side from the stored bank answers.
#   - Sessions are validated by ID + ownership (profile_id).
#   - Duplicate submission / unknown questions / answers for
#     questions outside the session are rejected.
#   - Attempt limits + cooldown are enforced (configurable).
#   - Assessment evidence is stored ON the profile (source
#     "assessment", verified=true) and NEVER overwrites the
#     resume evidence (which stays source "resume").
#
# HONESTY
#   The score reflects performance on the PlacePro assessment
#   question bank - NOT a professionally validated psychometric
#   test and NOT a guarantee of real-world expertise.
#
# ============================================================

import json
import os
import sys
import threading
import uuid
from datetime import datetime, timedelta, timezone

from .question_bank import (
    DIFFICULTY_POINTS,
    EASY,
    HARD,
    MEDIUM,
    SUPPORTED_SKILLS,
    get_questions,
)

# Project root on sys.path
_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Storage for assessment sessions (profiles stay in data/profiles/)
DEFAULT_ASSESSMENTS_DIR = os.path.join(_PROJECT_ROOT, "data", "assessments")
ASSESSMENTS_DIR = os.environ.get("PLACEPRO_ASSESSMENTS_DIR") or DEFAULT_ASSESSMENTS_DIR

# ------------------------------------------------------------
# CONFIGURABLE POLICIES (attempt limits / cooldown)
# ------------------------------------------------------------

# Max attempts allowed per skill per profile.
MAX_ATTEMPTS_PER_SKILL = 3

# Cooldown between attempts for the same skill (hours). 0 disables it.
COOLDOWN_HOURS = 24

# A required company skill is considered satisfied by an assessment
# only when the score is at or above this threshold (Intermediate+).
ASSESSMENT_SATISFIED_MIN_SCORE = 60

# Questions per assessment (from the skill's bank).
QUESTIONS_PER_ASSESSMENT = 10

# Documented assessment level thresholds (0-100).
ASSESSMENT_LEVELS = [
    (0, 39, "Beginner"),
    (40, 59, "Developing"),
    (60, 74, "Intermediate"),
    (75, 89, "Strong"),
    (90, 100, "Advanced"),
]

# Readiness integration: max extra points the assessment evidence can
# add to the technical_skills component (documented, capped).
ASSESSMENT_READINESS_BONUS_MAX = 5


# ------------------------------------------------------------
# ERRORS
# ------------------------------------------------------------


class AssessmentError(Exception):
    status_code = 422


class AssessmentNotFoundError(AssessmentError):
    status_code = 404


class AssessmentOwnershipError(AssessmentError):
    status_code = 403


class AssessmentLimitError(AssessmentError):
    status_code = 429


class AssessmentCooldownError(AssessmentError):
    status_code = 429


class UnknownSkillError(AssessmentError):
    status_code = 404


class AssessmentCompletedError(AssessmentError):
    status_code = 409


class InvalidSubmissionError(AssessmentError):
    status_code = 400


# ------------------------------------------------------------
# STORAGE
# ------------------------------------------------------------

_ID_PATTERN = __import__("re").compile(r"^[A-Za-z0-9\-_]+$")
_lock = threading.Lock()


def _session_path(assessment_id: str) -> str:
    return os.path.join(ASSESSMENTS_DIR, f"{assessment_id}.json")


def _save_session(session: dict) -> None:
    os.makedirs(ASSESSMENTS_DIR, exist_ok=True)
    if not _ID_PATTERN.match(session["assessment_id"]):
        raise InvalidSubmissionError("Invalid assessment id.")
    path = _session_path(session["assessment_id"])
    tmp_path = f"{path}.tmp"
    with _lock:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(session, f, indent=2)
        os.replace(tmp_path, path)


def _load_session(assessment_id: str) -> dict:
    if not assessment_id or not _ID_PATTERN.match(assessment_id):
        raise AssessmentNotFoundError(
            f"Assessment '{assessment_id}' not found."
        )
    path = _session_path(assessment_id)
    if not os.path.exists(path):
        raise AssessmentNotFoundError(
            f"Assessment '{assessment_id}' not found."
        )
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ------------------------------------------------------------
# LEVELS / SCORING
# ------------------------------------------------------------


def assessment_level(score: float) -> str:
    """Map a 0-100 score to a documented assessment level."""
    for low, high, label in ASSESSMENT_LEVELS:
        if low <= score <= high:
            return label
    return "Beginner"  # defensive fallback


def compute_score(session: dict, answers: dict) -> dict:
    """Evaluate answers server-side and return the full score report.

    answers: {question_id: submitted_answer}. Only questions in the
    session are evaluated; anything else is rejected by the caller.
    """
    earned = 0
    total = 0
    correct_ids = []
    per_difficulty = {EASY: [0, 0], MEDIUM: [0, 0], HARD: [0, 0]}
    per_topic = {}

    for question in session["questions"]:
        qid = question["id"]
        points = question.get("points", DIFFICULTY_POINTS[question["difficulty"]])
        total += points
        diff = question["difficulty"]
        per_difficulty[diff][1] += points

        submitted = answers.get(qid)
        correct = _answer_matches(submitted, question["correct_answer"])
        if correct:
            earned += points
            correct_ids.append(qid)
            per_difficulty[diff][0] += points

        topic = question["topic"]
        bucket = per_topic.setdefault(topic, [0, 0])
        bucket[1] += 1
        if correct:
            bucket[0] += 1

    score = round(earned / total * 100, 1) if total else 0.0

    difficulty_breakdown = {
        diff: round(earned_pts / total_pts * 100, 1)
        for diff, (earned_pts, total_pts) in per_difficulty.items()
        if total_pts > 0
    }
    topic_breakdown = {
        topic: round(correct_count / count * 100, 1)
        for topic, (correct_count, count) in per_topic.items()
    }
    return {
        "score": score,
        "level": assessment_level(score),
        "correct": len(correct_ids),
        "total": len(session["questions"]),
        "correct_ids": correct_ids,
        "difficulty_breakdown": difficulty_breakdown,
        "topic_breakdown": topic_breakdown,
    }


def _answer_matches(submitted, correct) -> bool:
    """Server-side answer comparison (normalized, exact).

    For mcq answers the submitted text is compared to the stored
    correct option text; numeric answers (not currently used) would
    be compared with tolerance. Nothing client-side is trusted.
    """
    if submitted is None:
        return False
    try:
        sub_num = float(str(submitted).strip())
        cor_num = float(str(correct).strip())
        return abs(sub_num - cor_num) < 1e-6
    except (ValueError, TypeError):
        return str(submitted).strip().lower() == str(correct).strip().lower()


# ------------------------------------------------------------
# PROFILE HELPERS (evidence + history, additive only)
# ------------------------------------------------------------


def _profile_path(profile_id: str) -> str:
    from .profile_service import _profile_path as pp

    return pp(profile_id)


def _load_profile(profile_id: str) -> dict:
    from .profile_service import _load

    return _load(profile_id)


def _save_profile(profile: dict) -> None:
    from .profile_service import _save

    _save(profile)


def get_assessment_evidence(profile: dict) -> list:
    """Latest score per assessed skill: [{skill, score, level,
    assessment_id, attempt, timestamp, source: "assessment",
    verified: true}]."""
    evidence = profile.get("assessment_evidence") or []
    latest = {}
    for entry in evidence:
        if entry["skill"] not in latest or entry["attempt"] > latest[entry["skill"]]["attempt"]:
            latest[entry["skill"]] = entry
    return list(latest.values())


def get_assessment_history(profile_id: str) -> list:
    """All assessment attempts for a profile (chronological)."""
    profile = _load_profile(profile_id)
    return list(profile.get("assessment_evidence") or [])


def _attempts_for_skill(profile: dict, skill: str) -> list:
    return [
        e for e in (profile.get("assessment_evidence") or [])
        if e["skill"] == skill
    ]


def _enforce_limits(profile: dict, skill: str) -> None:
    attempts = _attempts_for_skill(profile, skill)
    if len(attempts) >= MAX_ATTEMPTS_PER_SKILL:
        raise AssessmentLimitError(
            f"Maximum attempts reached for {skill} "
            f"({MAX_ATTEMPTS_PER_SKILL} attempts allowed)."
        )
    if attempts and COOLDOWN_HOURS > 0:
        last = datetime.fromisoformat(attempts[-1]["timestamp"])
        next_allowed = last + timedelta(hours=COOLDOWN_HOURS)
        if datetime.now(timezone.utc) < next_allowed:
            raise AssessmentCooldownError(
                f"Please wait before retrying {skill}. "
                f"Next attempt allowed after "
                f"{next_allowed.isoformat()}."
            )


# ------------------------------------------------------------
# ORCHESTRATION
# ------------------------------------------------------------


def start_assessment(profile_id: str, skill: str, num_questions: int = None) -> dict:
    """Create an assessment session for a skill. Returns questions
    WITHOUT correct answers or explanations."""
    profile = _load_profile(profile_id)  # raises ProfileNotFoundError

    if not profile.get("verified"):
        from .profile_service import ProfileServiceError

        raise ProfileServiceError(
            "Student profile must be verified before taking an assessment."
        )

    if skill not in SUPPORTED_SKILLS:
        raise UnknownSkillError(
            f"Unknown skill '{skill}'. Supported skills: "
            f"{', '.join(SUPPORTED_SKILLS)}"
        )

    _enforce_limits(profile, skill)

    bank = get_questions(skill)
    count = min(num_questions or QUESTIONS_PER_ASSESSMENT,
                len(bank), QUESTIONS_PER_ASSESSMENT)
    questions = bank[:count]

    session = {
        "assessment_id": str(uuid.uuid4()),
        "profile_id": profile_id,
        "skill": skill,
        "attempt": len(_attempts_for_skill(profile, skill)) + 1,
        "questions": questions,
        "answers": {},
        "status": "IN_PROGRESS",
        "score_report": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "submitted_at": None,
    }
    _save_session(session)

    public_questions = [
        {
            "question_id": q["id"],
            "skill": q["skill"],
            "topic": q["topic"],
            "difficulty": q["difficulty"],
            "question_type": q["question_type"],
            "question": q["question"],
            "options": q.get("options") or [],
        }
        for q in questions
    ]
    return {
        "assessment_id": session["assessment_id"],
        "skill": skill,
        "attempt": session["attempt"],
        "total_questions": len(public_questions),
        "questions": public_questions,
        "time_limit_minutes": None,
    }


def submit_assessment(assessment_id: str, profile_id: str,
                      answers: dict) -> dict:
    """Evaluate a submission server-side and record verified evidence."""
    session = _load_session(assessment_id)

    if session["profile_id"] != profile_id:
        raise AssessmentOwnershipError(
            "This assessment belongs to a different profile."
        )

    if session["status"] == "COMPLETED":
        raise AssessmentCompletedError(
            "This assessment has already been submitted."
        )

    if not answers:
        raise InvalidSubmissionError("No answers were provided.")

    question_ids = {q["id"] for q in session["questions"]}
    submitted_ids = set(answers.keys())
    unknown = submitted_ids - question_ids
    if unknown:
        raise InvalidSubmissionError(
            "Answers contain question ids that are not part of this "
            f"assessment: {', '.join(sorted(unknown))}"
        )

    report = compute_score(session, answers)

    session["answers"] = answers
    session["status"] = "COMPLETED"
    session["score_report"] = report
    session["submitted_at"] = datetime.now(timezone.utc).isoformat()
    _save_session(session)

    # Record verified evidence on the profile (NEVER overwrites the
    # resume evidence - it lives alongside it with its own source).
    profile = _load_profile(profile_id)
    evidence = profile.get("assessment_evidence") or []
    evidence.append({
        "skill": session["skill"],
        "score": report["score"],
        "level": report["level"],
        "source": "assessment",
        "verified": True,
        "assessment_id": assessment_id,
        "attempt": session["attempt"],
        "timestamp": session["submitted_at"],
    })
    profile["assessment_evidence"] = evidence
    _save_profile(profile)

    return {
        "assessment_id": assessment_id,
        "skill": session["skill"],
        "attempt": session["attempt"],
        "skill_score": report["score"],
        "level": report["level"],
        "correct": report["correct"],
        "total": report["total"],
        "difficulty_breakdown": report["difficulty_breakdown"],
        "topic_breakdown": report["topic_breakdown"],
        "message": (
            "Assessment score represents performance on the PlacePro "
            "assessment question bank and is not a guaranteed measure "
            "of real-world expertise."
        ),
    }


def get_assessment(assessment_id: str, profile_id: str = None) -> dict:
    """Optional: retrieve a session (answers never exposed).

    When `profile_id` is provided it must own the session (ownership
    check); when None (public GET route) ownership is enforced on the
    mutating submit operation instead.
    """
    session = _load_session(assessment_id)
    if profile_id is not None and session["profile_id"] != profile_id:
        raise AssessmentOwnershipError(
            "This assessment belongs to a different profile."
        )
    public_questions = [
        {
            "question_id": q["id"],
            "skill": q["skill"],
            "topic": q["topic"],
            "difficulty": q["difficulty"],
            "question_type": q["question_type"],
            "question": q["question"],
            "options": q.get("options") or [],
        }
        for q in session["questions"]
    ]
    return {
        "assessment_id": session["assessment_id"],
        "profile_id": session["profile_id"],
        "skill": session["skill"],
        "attempt": session["attempt"],
        "status": session["status"],
        "total_questions": len(public_questions),
        "questions": public_questions,
        "created_at": session.get("created_at"),
        "submitted_at": session.get("submitted_at"),
    }


# ------------------------------------------------------------
# COMBINED SKILL VIEW (GET /api/profile/{id}/skills)
# ------------------------------------------------------------


def combined_skill_view(profile_id: str) -> dict:
    """Resume-detected + user-entered + assessed skills in one view.

    Each entry:
      {skill, resume_detected, user_entered, assessment_score,
       assessment_verified, level}
    Resume provenance is preserved (a mention is not a score).
    """
    from .profile_service import get_profile
    from .readiness_service import collect_verified_skills

    profile, _ = get_profile(profile_id)
    evidence = get_assessment_evidence(profile)
    assessed = {e["skill"]: e for e in evidence}

    # Which skills came from the resume / user (Phase 12 collection
    # already resolves provenance via the profile's provenance map).
    entries = {}
    for entry in collect_verified_skills(profile):
        skill = entry["skill"]
        info = entries.setdefault(skill, {
            "skill": skill,
            "resume_detected": False,
            "user_entered": False,
            "assessment_score": None,
            "assessment_verified": False,
            "level": None,
        })
        if entry["source"] == "resume":
            info["resume_detected"] = True
        elif entry["source"] == "user":
            info["user_entered"] = True

    for skill, entry in assessed.items():
        info = entries.setdefault(skill, {
            "skill": skill,
            "resume_detected": False,
            "user_entered": False,
            "assessment_score": None,
            "assessment_verified": False,
            "level": None,
        })
        info["assessment_score"] = entry["score"]
        info["assessment_verified"] = entry["verified"]
        info["level"] = entry["level"]

    return {"profile_id": profile_id, "skills": list(entries.values())}
