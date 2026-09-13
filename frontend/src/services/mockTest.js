/**
 * PlacePro mock test service (Phase 6B, Step 2).
 *
 * Thin service layer over the REAL assessment endpoints exposed by
 * src/services/api.js:
 *
 *   startAssessment(profileId, skill, numQuestions) -> POST /api/assessment/start
 *   submitAssessment(assessmentId, answers)         -> POST /api/assessment/{id}/submit
 *   fetchAssessment(assessmentId)                   -> GET  /api/assessment/{id}
 *   fetchAssessmentHistory(profileId)               -> GET  /api/profile/{id}/assessments
 *   fetchSkillsView(profileId)                      -> GET  /api/profile/{id}/skills
 *
 * The backend is authoritative: questions, answers, score, level, correct,
 * total, difficulty breakdown, and topic breakdown all come from the
 * backend response and are passed through as-is. Nothing is generated,
 * shuffled, scored, or recomputed here, and correct answers are never
 * exposed or invented.
 */

import {
  startAssessment,
  submitAssessment,
  fetchAssessment,
  fetchAssessmentHistory,
  fetchSkillsView,
} from "./api";

/** Demo timing rule kept for the existing UI: about 1 minute per question. */
export const SECONDS_PER_QUESTION = 60;

/* ================================================================
   SETUP OPTIONS
   ================================================================ */

/**
 * Skill options for the test setup form.
 *
 * The demo subject list is gone; skill names come from the backend's
 * profile skills view (see getProfileSkills). Provided as an empty array
 * default so the not-yet-updated MockTests.jsx can fill this in Step 3.
 */
export function getSubjects() {
  return [];
}

/**
 * Difficulty options for the test setup form.
 * Kept as a minimal constant; the backend validates the actual values.
 */
export function getDifficulties() {
  return ["Easy", "Medium", "Hard"];
}

/* ================================================================
   STARTING AN ASSESSMENT
   ================================================================ */

/**
 * Start a REAL backend assessment.
 *
 * Replaces the Phase 3 demo question generation. The backend selects the
 * questions and returns the created assessment; that response is
 * authoritative and is returned as-is.
 *
 * Signature change vs the demo: (profileId, skill, count) — MockTests.jsx
 * still needs Step 3 to pass the profile id and skill name.
 */
export async function getMockQuestions(profileId, skill, count) {
  return startAssessment(profileId, skill, count);
}

/* ================================================================
   SUBMITTING AN ASSESSMENT
   ================================================================ */

/**
 * Build the backend answers payload from the frontend selection state.
 *
 * The UI stores answers as { questionId: selectedOptionIndex }. The
 * backend expects { "<question_id>": "<answer_text>" }, so each selected
 * option index is converted into question.options[index] BEFORE submitting:
 *
 *   selected option index -> question.options[selectedIndex] -> answer text
 *
 * Unanswered questions (missing id, non-integer index, or out-of-range
 * index) are OMITTED — no answers are invented. Returns an object shaped
 * { answers: { "<question_id>": answerText } } ready for submitAssessment().
 */
export function buildAnswerPayload(questions, answers) {
  const payload = {};

  (questions ?? []).forEach((question) => {
    if (!question || question.question_id === undefined || question.question_id === null) {
      return;
    }

    const selectedIndex = answers?.[question.question_id];
    if (!Number.isInteger(selectedIndex)) {
      return; // Unanswered: omit, never invent.
    }

    const options = Array.isArray(question.options) ? question.options : [];
    const answerText = options[selectedIndex];
    if (typeof answerText !== "string" || answerText.trim() === "") {
      return; // Out-of-range or invalid option: omit rather than guess.
    }

    payload[question.question_id] = answerText;
  });

  return { answers: payload };
}

/**
 * Submit a student's answers for grading.
 *
 * Converts frontend option indexes into answer text (see
 * buildAnswerPayload), then delegates grading entirely to the backend via
 * submitAssessment(). No score, level, or breakdown is computed here —
 * the backend response is returned as-is.
 */
export async function submitMockTest(assessmentId, questions, answers, profileId) {
  const answerPayload = buildAnswerPayload(questions, answers);
  return submitAssessment(assessmentId, profileId, answerPayload.answers);
}

/* ================================================================
   READ WRAPPERS
   ================================================================ */

/** Fetch a previously started assessment (questions + state). */
export async function getAssessment(assessmentId) {
  return fetchAssessment(assessmentId);
}

/** Fetch a profile's past assessment attempts. */
export async function getAssessmentHistory(profileId) {
  return fetchAssessmentHistory(profileId);
}

/** Fetch a profile's per-skill proficiency view. */
export async function getProfileSkills(profileId) {
  return fetchSkillsView(profileId);
}

/* ================================================================
   PURE FORMATTING HELPERS (unchanged from Phase 3)
   ================================================================ */

/** Formats seconds as "M:SS". */
export function formatTime(totalSeconds) {
  const safe = Math.max(0, Number(totalSeconds) || 0);
  const minutes = Math.floor(safe / 60);
  const seconds = safe % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

/** Formats seconds as "5m 20s" for the result page "Time Taken". */
export function formatDuration(totalSeconds) {
  const safe = Math.max(0, Number(totalSeconds) || 0);
  const minutes = Math.floor(safe / 60);
  const seconds = safe % 60;
  if (minutes === 0) return `${seconds}s`;
  return `${minutes}m ${seconds}s`;
}
