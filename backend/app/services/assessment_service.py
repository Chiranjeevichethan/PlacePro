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
#   - Production requires gate-issued account identity, ACTIVE profile ownership
#     and persisted account/profile/assessment binding before lifecycle work.
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

import copy
import json
import math
import os
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .score_levels import classify_percentage
from .storage_lock import StorageLockTimeout, record_transaction
from .skill_evidence import (
    ASSESSMENT_READINESS_BONUS_MAX,
    ASSESSMENT_SATISFIED_MIN_SCORE,
    assessment_evidence_status,
    latest_assessment_evidence,
    resolve_skill_evidence,
)

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

# Max completed attempts per skill/profile. Active sessions reserve quota too.
MAX_ATTEMPTS_PER_SKILL = 3

# Cooldown between attempts for the same skill (hours). 0 disables it.
COOLDOWN_HOURS = 24

# A required company skill is considered satisfied by an assessment
# only when the score is at or above this threshold (Intermediate+).
# Re-export the shared evidence threshold for existing callers.

# Questions per assessment (from the skill's bank).
QUESTIONS_PER_ASSESSMENT = 25

# The existing practice UI allows one minute per question; enforce it on the server.
MINUTES_PER_QUESTION = 1

# Documented assessment level thresholds (0-100).
ASSESSMENT_LEVELS = [
    (0, 40, "Beginner"),
    (40, 60, "Developing"),
    (60, 75, "Intermediate"),
    (75, 90, "Strong"),
    (90, 100, "Advanced"),
]

# Readiness integration: max extra points the assessment evidence can
# add to the technical_skills component (documented, capped).
# Re-export the unchanged shared bonus cap.


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


class AssessmentRetryError(AssessmentError):
    """A temporary wait for cooldown or active-session reservation expiry.

    Carries machine-readable retry timing so the API/UI can show an
    accurate remaining wait and clear the warning when it lapses:

      retry_after_seconds : whole seconds still to wait (>= 1)
      next_allowed_at     : ISO-8601 UTC instant the retry is allowed

    Cooldown's existing human-readable message is preserved.
    """

    status_code = 429

    def __init__(self, message, retry_after_seconds=None,
                 next_allowed_at=None):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds
        self.next_allowed_at = next_allowed_at


class AssessmentCooldownError(AssessmentRetryError):
    """Temporary cooldown after a completed attempt."""


class AssessmentReservationError(AssessmentRetryError):
    """Remaining quota is currently reserved by active sessions."""


class UnknownSkillError(AssessmentError):
    status_code = 404


class AssessmentCompletedError(AssessmentError):
    status_code = 409


class AssessmentExpiredError(AssessmentError):
    status_code = 410


class AssessmentStateError(AssessmentError):
    status_code = 409


class AssessmentStorageError(AssessmentError):
    status_code = 503


class InvalidSubmissionError(AssessmentError):
    status_code = 400


# ------------------------------------------------------------
# STORAGE
# ------------------------------------------------------------

_ID_PATTERN = __import__("re").compile(r"^[A-Za-z0-9\-_]+$")


def _profile_transaction(profile_id):
    from .profile_service import profile_transaction

    return profile_transaction(profile_id)


def _session_path(assessment_id: str) -> str:
    return os.path.join(ASSESSMENTS_DIR, f"{assessment_id}.json")


def _save_session(session: dict, *, access=None, creating=False) -> None:
    if (
        not isinstance(session["assessment_id"], str)
        or not _ID_PATTERN.fullmatch(session["assessment_id"])
    ):
        raise InvalidSubmissionError("Invalid assessment id.")
    path = _session_path(session["assessment_id"])
    tmp_path = f"{path}.{uuid.uuid4().hex}.tmp"
    # Always acquire the profile lock before the session lock. Initial owner
    # discovery reads release the session lock before acquiring a profile lock.
    with _profile_transaction(session["profile_id"]), record_transaction(ASSESSMENTS_DIR, session['assessment_id']):
        os.makedirs(ASSESSMENTS_DIR, exist_ok=True)
        if access is not None:
            access.validate(session)
            if creating:
                try:
                    with open(path, 'x', encoding='utf-8') as f:
                        json.dump(session, f, indent=2)
                        f.flush()
                        os.fsync(f.fileno())
                except FileExistsError:
                    raise AssessmentStateError('Assessment creation could not be completed.') from None
                return
            previous = _load_session(session['assessment_id'])
            access.validate(previous, session['assessment_id'])
            if any(previous.get(key) != session.get(key) for key in
                   ('account_id','profile_id','assessment_id','attempt','ownership_schema_version','profile_ownership_version')):
                raise AssessmentStorageError('Assessment identity is inconsistent.')
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(session, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
        if access is not None:
            access.records[session['assessment_id']] = session


def _load_session(assessment_id: str) -> dict:
    if not isinstance(assessment_id, str) or not _ID_PATTERN.fullmatch(assessment_id):
        raise AssessmentNotFoundError(
            f"Assessment '{assessment_id}' not found."
        )
    path = _session_path(assessment_id)
    if not os.path.exists(path):
        raise AssessmentNotFoundError(
            f"Assessment '{assessment_id}' not found."
        )
    try:
        with record_transaction(ASSESSMENTS_DIR, assessment_id):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except StorageLockTimeout as exc:
        raise AssessmentStorageError('Assessment storage is busy. Please retry.') from exc


def _utc_now():
    """Injectable server clock; request bodies never supply assessment timing."""
    return datetime.now(timezone.utc)


def _parse_time(value):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        moment = datetime.fromisoformat(value.strip())
    except ValueError:
        return None
    return moment.astimezone(timezone.utc) if moment.tzinfo is not None else None


def _attempt_number(entry):
    value = entry.get("attempt")
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else 0


def _sessions_for_profile(profile_id, *, access=None):
    """Read sessions under the profile transaction; never discard corrupt storage."""
    sessions = []
    for path in Path(ASSESSMENTS_DIR).glob("*.json"):
        try:
            session = _load_session(path.stem)
            if not isinstance(session, dict):
                raise ValueError("Expected a session object")
        except (ValueError, OSError) as exc:
            raise AssessmentStorageError(
                f"Cannot read assessment storage '{path.name}'."
            ) from exc
        if session.get("profile_id") == profile_id:
            if access is not None:
                if not access.matches(session, path.stem):
                    continue
                access.validate(session, path.stem)
            sessions.append(session)
    return sorted(sessions, key=lambda session: (
        _parse_time(session.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc),
        session["assessment_id"],
    ))


def _refresh_expiry(session, now, *, access=None):
    """Expire unscored sessions lazily, retaining their original timing/status."""
    if session["status"] != "IN_PROGRESS":
        return
    changed = False
    created = _parse_time(session.get("created_at"))
    if "expires_at" not in session and created is not None:
        # Legacy sessions receive a deadline from original creation, never from now.
        minutes = len(session["questions"]) * MINUTES_PER_QUESTION
        session["time_limit_minutes"] = minutes
        session["expires_at"] = (created + timedelta(minutes=minutes)).isoformat()
        changed = True
    expires = _parse_time(session.get("expires_at"))
    invalid = created is None or expires is None or expires <= created
    if invalid or now >= expires:
        session["status"] = "EXPIRED"
        session["expired_at"] = expires.isoformat() if expires else now.isoformat()
        session["status_reason"] = (
            "Session timing is missing or invalid." if invalid else "Session time limit exceeded."
        )
        changed = True
    if changed:
        _save_session(session, access=access) if access is not None else _save_session(session)


# ------------------------------------------------------------
# LEVELS / SCORING
# ------------------------------------------------------------


def assessment_level(score: float) -> str:
    """Map a 0-100 score to a documented assessment level."""
    return classify_percentage(score, ASSESSMENT_LEVELS)


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


def _save_profile(profile: dict, *, access=None) -> None:
    from .profile_service import _save

    if access is not None:
        access.profile(profile)
        access.evidence(profile)
    _save(profile)


def _finish_submission(profile, session, *, access=None):
    """Project a durable submission into evidence exactly once, then complete it.

    SUBMITTING stores accepted answers/report/time before either projection write.
    A retry or later lifecycle read can recover an interrupted write without scoring
    again. This is a recovery protocol, not a two-file database transaction.
    """
    report = session.get("score_report")
    if access is not None:
        access.validate(session)
        access.profile(profile)
        access.evidence(profile)
    if not isinstance(report, dict) or not session.get("submitted_at"):
        raise AssessmentStorageError(
            f"Assessment '{session['assessment_id']}' has an incomplete completion record."
        )
    evidence = list(profile.get("assessment_evidence") or [])
    if not any(isinstance(entry, dict) and entry.get("assessment_id") == session["assessment_id"]
               for entry in evidence):
        entry = {
            "skill": session["skill"],
            "score": report["score"],
            "level": report["level"],
            "source": "assessment",
            "verified": True,
            "assessment_id": session["assessment_id"],
            "attempt": session["attempt"],
            "timestamp": session["submitted_at"],
        }
        if access is not None:
            entry['account_id'] = access.identity.account_id
            access.validate(session)
        evidence.append(entry)
        profile["assessment_evidence"] = evidence
        _save_profile(profile, access=access) if access is not None else _save_profile(profile)
    if session["status"] != "COMPLETED":
        session["status"] = "COMPLETED"
        _save_session(session, access=access) if access is not None else _save_session(session)


def _sync_sessions(profile, now, *, access=None):
    """Recover accepted work, expire reservations and repair legacy active numbering."""
    if access is not None:
        access.profile(profile)
    sessions = _sessions_for_profile(profile["profile_id"], access=access)
    if access is not None:
        ordinals = [(s['skill'], s['attempt']) for s in sessions]
        if len(set(ordinals)) != len(ordinals):
            raise AssessmentStorageError('Assessment attempt identities are inconsistent.')
    for session in sessions:
        if session["status"] in {"SUBMITTING", "COMPLETED"}:
            _finish_submission(profile, session, access=access)
        _refresh_expiry(session, now, access=access)

    evidence = access.evidence(profile) if access is not None else profile.get("assessment_evidence") or []
    used = {}
    highest = {}
    for entry in [*evidence, *sessions]:
        if not isinstance(entry, dict) or not entry.get("skill"):
            continue
        skill, attempt = entry["skill"], _attempt_number(entry)
        highest[skill] = max(highest.get(skill, 0), attempt)
        if entry.get("status") != "IN_PROGRESS":
            used.setdefault(skill, set()).add(attempt)
    for session in sessions:
        if session["status"] != "IN_PROGRESS":
            continue
        skill = session["skill"]
        allocated = used.setdefault(skill, set())
        attempt = _attempt_number(session)
        if attempt == 0 or attempt in allocated:
            highest[skill] += 1
            session["attempt"] = highest[skill]
            _save_session(session)
        allocated.add(session["attempt"])
    return sessions


def get_assessment_evidence(profile: dict) -> list:
    """Latest score per assessed skill: [{skill, score, level,
    assessment_id, attempt, timestamp, source: "assessment",
    verified: true}]."""
    return [{**entry, "level": assessment_level(entry["score"])}
            for entry in latest_assessment_evidence(profile)]


def get_assessment_history(profile_id: str, *, access=None) -> list:
    """All assessment attempts for a profile (chronological)."""
    with _profile_transaction(profile_id):
        profile = access.load_profile() if access is not None else _load_profile(profile_id)
        _sync_sessions(profile, _utc_now(), access=access)
        return access.evidence(profile) if access is not None else list(profile.get("assessment_evidence") or [])


def _attempts_for_skill(profile: dict, skill: str, *, access=None) -> list:
    return [
        e for e in (access.evidence(profile) if access is not None else profile.get("assessment_evidence") or [])
        if isinstance(e, dict) and e.get("skill") == skill
    ]


def _last_attempt_time(attempts: list):
    """Latest recorded attempt timestamp for a skill (or None).

    Parsing is deliberately defensive. A missing, empty, malformed or
    timezone-naive timestamp is skipped instead of raising: one bad
    history entry must never crash the endpoint (HTTP 500) or lock a
    student out. The latest timestamp is used rather than the last list
    element, so the cooldown cannot depend on evidence ordering.
    """

    parsed = []

    for entry in attempts:
        if not isinstance(entry, dict):
            continue

        moment = _parse_time(entry.get("timestamp"))
        if moment is not None:
            parsed.append(moment)

    return max(parsed) if parsed else None


def _enforce_limits(profile: dict, skill: str, active_sessions=(), now=None, *, access=None) -> None:
    """Apply the documented attempt limit, then the retry cooldown.

    Order matters: exhausting MAX_ATTEMPTS_PER_SKILL is a permanent state
    (AssessmentLimitError, no retry timing), while an active cooldown is
    temporary and carries the exact remaining wait.
    """

    attempts = _attempts_for_skill(profile, skill, access=access)
    if len(attempts) >= MAX_ATTEMPTS_PER_SKILL:
        raise AssessmentLimitError(
            f"Maximum attempts reached for {skill} "
            f"({MAX_ATTEMPTS_PER_SKILL} attempts allowed)."
        )

    now = now or _utc_now()
    last = _last_attempt_time(attempts) if COOLDOWN_HOURS > 0 else None
    if last is not None:
        next_allowed = last + timedelta(hours=COOLDOWN_HOURS)
        if now < next_allowed:
            raise AssessmentCooldownError(
                f"Please wait before retrying {skill}. "
                f"Next attempt allowed after "
                f"{next_allowed.isoformat()}.",
                retry_after_seconds=max(
                    1, math.ceil((next_allowed - now).total_seconds())
                ),
                next_allowed_at=next_allowed.isoformat(),
            )

    if len(attempts) + len(active_sessions) >= MAX_ATTEMPTS_PER_SKILL:
        # This reservation limit is temporary; completed-quota exhaustion above
        # remains terminal and must never advertise a retry time.
        release_at = min(_parse_time(session["expires_at"]) for session in active_sessions)
        raise AssessmentReservationError(
            f"Maximum attempts reserved for {skill} "
            f"({MAX_ATTEMPTS_PER_SKILL} completed or active attempts allowed). "
            "Submit an active session or wait for it to expire.",
            retry_after_seconds=max(1, math.ceil((release_at - now).total_seconds())),
            next_allowed_at=release_at.isoformat(),
        )


# ------------------------------------------------------------
# ORCHESTRATION
# ------------------------------------------------------------


def start_assessment(profile_id: str, skill: str, num_questions: int = None, *, rng=None, access=None) -> dict:
    """Create an assessment session for a skill. Returns questions
    WITHOUT correct answers or explanations."""
    with _profile_transaction(profile_id):
        return _start_assessment(profile_id, skill, num_questions, rng=rng, access=access)


def _start_assessment(profile_id, skill, num_questions, *, rng, access=None):
    profile = access.load_profile() if access is not None else _load_profile(profile_id)
    if access is not None:
        access.profile(profile)

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

    now = _utc_now()
    sessions = _sync_sessions(profile, now, access=access)
    now = _utc_now()
    skill_sessions = [session for session in sessions if session["skill"] == skill]
    active = [session for session in skill_sessions if session["status"] == "IN_PROGRESS"]
    _enforce_limits(profile, skill, active, now, access=access)

    bank = get_questions(skill)
    if num_questions is not None and (
        not isinstance(num_questions, int) or isinstance(num_questions, bool)
        or not 1 <= num_questions <= QUESTIONS_PER_ASSESSMENT
    ):
        raise InvalidSubmissionError(
            f"Question count must be between 1 and {QUESTIONS_PER_ASSESSMENT}."
        )
    count = min(num_questions or QUESTIONS_PER_ASSESSMENT,
                len(bank), QUESTIONS_PER_ASSESSMENT)
    if not count:
        raise UnknownSkillError(f"No questions available for '{skill}'.")
    # SystemRandom avoids a predictable global sequence; an injected seeded RNG
    # makes selection reproducible in tests without changing the HTTP contract.
    selector = rng if rng is not None else random.SystemRandom()
    questions = copy.deepcopy(selector.sample(bank, count))
    previous = [*_attempts_for_skill(profile, skill, access=access), *skill_sessions]
    attempt = max([0, *(_attempt_number(entry) for entry in previous)]) + 1
    minutes = count * MINUTES_PER_QUESTION

    session = {
        "assessment_id": str(uuid.uuid4()),
        "profile_id": profile_id,
        "skill": skill,
        "attempt": attempt,
        "questions": questions,
        "answers": {},
        "status": "IN_PROGRESS",
        "score_report": None,
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=minutes)).isoformat(),
        "time_limit_minutes": minutes,
        "expired_at": None,
        "submitted_at": None,
    }
    if access is not None:
        access.bind(session)
        _save_session(session, access=access, creating=True)
    else:
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
        "time_limit_minutes": minutes,
        "created_at": session["created_at"],
        "expires_at": session["expires_at"],
        "server_now": _utc_now().isoformat(),
    }


def submit_assessment(assessment_id: str, profile_id: str,
                      answers: dict, *, access=None) -> dict:
    """Evaluate a submission server-side and record verified evidence."""
    session = _load_session(assessment_id)
    if access is not None:
        access.validate(session, assessment_id)
    if session["profile_id"] != profile_id:
        raise AssessmentOwnershipError(
            "This assessment belongs to a different profile."
        )
    with _profile_transaction(profile_id):
        return _submit_assessment(assessment_id, profile_id, answers, access=access)


def _submit_assessment(assessment_id, profile_id, answers, *, access=None):
    session = _load_session(assessment_id)
    if access is not None:
        access.validate(session, assessment_id)
    recovering = session["status"] == "SUBMITTING"
    accepted_answers = session.get("answers")
    profile = access.load_profile() if access is not None else _load_profile(profile_id)
    _sync_sessions(profile, _utc_now(), access=access)
    session = _load_session(assessment_id)
    if access is not None:
        access.validate(session, assessment_id)
    if session["status"] == "COMPLETED":
        if recovering and answers == accepted_answers:
            return _submission_response(session)
        raise AssessmentCompletedError(
            "This assessment has already been submitted."
        )
    if session["status"] == "EXPIRED":
        raise AssessmentExpiredError("This assessment has expired. Start a new assessment.")
    if session["status"] != "IN_PROGRESS":
        raise AssessmentStateError(
            f"This assessment cannot be submitted in state '{session['status']}'."
        )

    # Check after acquiring the lock and refreshing storage. Client timing is
    # never read; accepted_at is also the authoritative cooldown timestamp.
    accepted_at = _utc_now()
    _refresh_expiry(session, accepted_at, access=access)
    if session["status"] == "EXPIRED":
        raise AssessmentExpiredError("This assessment has expired. Start a new assessment.")
    _enforce_limits(profile, session["skill"], now=accepted_at, access=access)

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
    session["status"] = "SUBMITTING"
    session["score_report"] = report
    session["submitted_at"] = accepted_at.isoformat()
    if access is not None and getattr(access,'submission_receipt',None) is not None:
        session['submission_receipt']=access.submission_receipt
    _save_session(session, access=access) if access is not None else _save_session(session)
    _finish_submission(profile, session, access=access)
    return _submission_response(session)


def _submission_response(session):
    report = session["score_report"]
    return {
        "assessment_id": session["assessment_id"],
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


def get_assessment(assessment_id: str, profile_id: str = None, *, access=None) -> dict:
    """Optional: retrieve a session (answers never exposed).

    Production passes an authoritative access context and profile ID. The
    optional profile-only contract is retained for isolated domain regressions;
    it is never registered as the production assessment transport.
    """
    session = _load_session(assessment_id)
    if access is not None:
        access.validate(session, assessment_id)
    if profile_id is not None and session["profile_id"] != profile_id:
        raise AssessmentOwnershipError(
            "This assessment belongs to a different profile."
        )
    with _profile_transaction(session["profile_id"]):
        profile = access.load_profile() if access is not None else _load_profile(session["profile_id"])
        _sync_sessions(profile, _utc_now(), access=access)
        session = _load_session(assessment_id)
        if access is not None:
            access.validate(session, assessment_id)
        return _public_session(session)


def _public_session(session):
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
        "expires_at": session.get("expires_at"),
        "time_limit_minutes": session.get("time_limit_minutes"),
        "expired_at": session.get("expired_at"),
        "status_reason": session.get("status_reason"),
        "submitted_at": session.get("submitted_at"),
        "server_now": _utc_now().isoformat(),
        # Only the already-public aggregate report is recoverable. Stored
        # answers, correct_ids, answer keys and explanations remain private.
        "result": _submission_response(session) if session["status"] == "COMPLETED" else None,
    }


# ------------------------------------------------------------
# COMBINED SKILL VIEW (GET /api/profile/{id}/skills)
# ------------------------------------------------------------


def combined_skill_view(profile_id: str) -> dict:
    """Current claim origins and independent assessments, using shared sufficiency."""
    from .profile_service import get_profile

    profile, _ = get_profile(profile_id)
    return skills_for_profile(profile)


def skills_for_profile(profile: dict) -> dict:
    """Project skill evidence from the caller's single profile snapshot."""
    resolved = resolve_skill_evidence(profile)
    entries = []
    for skill, info in resolved["skills"].items():
        assessed = info["assessment"]
        sources = list(dict.fromkeys(e["source"] for e in info["evidence"] if e.get("source")))
        trusted = assessed and assessment_evidence_status(assessed) in {"SATISFIED", "INSUFFICIENT"}
        entries.append({
            "skill": skill,
            "resume_detected": "resume" in sources,
            "user_entered": "user" in sources,
            "assessment_score": info["score"],
            "assessment_verified": bool(trusted),
            "level": assessment_level(info["score"]) if trusted else None,
            "evidence_status": info["status"],
            "evidence_sources": sources,
            "profile_confirmed": info["profile_confirmed"],
            "assessment_timestamp": assessed.get("timestamp") if assessed else None,
        })
    return {"profile_id": profile['profile_id'], "source_revision": profile.get('revision', 0),
            "skills": entries}
