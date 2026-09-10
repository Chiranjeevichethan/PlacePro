/**
 * PlacePro mock test service (Phase 3).
 *
 * IMPORTANT: This is a TEMPORARY DEMO implementation serving questions from
 * src/data/mockTestData.js. Scoring happens locally in the browser.
 *
 * FUTURE BACKEND INTEGRATION (do not change the exported API):
 *   - getMockQuestions() -> replace with
 *       GET /api/tests?subject=SQL&difficulty=medium
 *   - Test submission    -> replace local scoring with
 *       POST /api/tests/submit  { test_id, answers }
 *       -> { score, total, percentage, weak_topics }
 *
 * The demo path must keep the "Demo Test" labeling used by MockTests.jsx.
 */
import { QUESTIONS, SUBJECTS, DIFFICULTIES } from "../data/mockTestData";

/** Demo timing rule: about 1 minute per question. */
export const SECONDS_PER_QUESTION = 60;

export function getSubjects() {
  return SUBJECTS;
}

export function getDifficulties() {
  return DIFFICULTIES;
}

/** Normalizes a subject key for comparisons ("Computer Networks" etc.). */
const sameText = (a, b) =>
  String(a || "").trim().toLowerCase() === String(b || "").trim().toLowerCase();

/**
 * Demo question retrieval. Shuffles deterministically per attempt so retakes
 * feel fresh, then slices to the requested count. If fewer questions exist
 * than requested, all available ones are returned (UI shows the real count).
 *
 * Returns a NEW array of NEW question objects (options copied) so component
 * state can never mutate the shared demo bank.
 */
export function getMockQuestions(subject, difficulty, count) {
  const pool = QUESTIONS.filter(
    (q) => sameText(q.subject, subject) && sameText(q.difficulty, difficulty)
  );

  // Fisher-Yates shuffle on a copy.
  const shuffled = [...pool];
  for (let i = shuffled.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
  }

  const requested = Number(count) || pool.length;
  return shuffled.slice(0, Math.min(requested, shuffled.length)).map((q) => ({
    ...q,
    options: [...q.options],
  }));
}

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

/**
 * Local demo scoring. Produces the same shape the future
 * POST /api/tests/submit response is expected to have.
 */
export function scoreTest(questions, answers) {
  const perQuestion = questions.map((question) => {
    const selectedIndex = answers[question.id];
    const answered = Number.isInteger(selectedIndex);
    const correct = answered && selectedIndex === question.correctAnswer;

    return {
      question,
      selectedIndex: answered ? selectedIndex : null,
      status: !answered ? "unanswered" : correct ? "correct" : "wrong",
    };
  });

  const correctCount = perQuestion.filter((r) => r.status === "correct").length;
  const wrongCount = perQuestion.filter((r) => r.status === "wrong").length;
  const unansweredCount = perQuestion.filter(
    (r) => r.status === "unanswered"
  ).length;
  const total = questions.length;
  const percentage = total ? Math.round((correctCount / total) * 100) : 0;

  // Topic-wise demo performance: { topic: { correct, total } }.
  const topicMap = new Map();
  perQuestion.forEach(({ question, status }) => {
    const entry = topicMap.get(question.topic) || { correct: 0, total: 0 };
    entry.total += 1;
    if (status === "correct") entry.correct += 1;
    topicMap.set(question.topic, entry);
  });

  const topicPerformance = [...topicMap.entries()]
    .map(([topic, { correct, total: topicTotal }]) => ({
      topic,
      correct,
      total: topicTotal,
      percentage: Math.round((correct / topicTotal) * 100),
    }))
    .sort((a, b) => a.percentage - b.percentage);

  // Weak areas: any topic below 60% correct in this attempt.
  const weakTopics = topicPerformance
    .filter((t) => t.percentage < 60)
    .map((t) => t.topic);

  return {
    perQuestion,
    score: correctCount,
    wrong: wrongCount,
    unanswered: unansweredCount,
    total,
    percentage,
    topicPerformance,
    weakTopics,
    demo: true,
  };
}
