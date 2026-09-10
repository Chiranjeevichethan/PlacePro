/**
 * Mock Tests page (Phase 3).
 *
 * Flow: setup -> running test (timer + navigator) -> confirmation -> result.
 *
 * DEMO FEATURE: questions come from src/data/mockTestData.js and scoring
 * happens locally (src/services/mockTest.js). A real question database/API
 * will be connected later - the service is shaped for a 1:1 swap.
 *
 * State machine: "setup" | "running" | "finished".
 * - While running, <TestRunner> owns answers/index/timer state. Its `key`
 *   is the attempt id, so Start and Retake remount it fresh: no answers or
 *   timer ever leak between attempts.
 * - Leaving the page unmounts everything, so no stale test state remains.
 */
import { useCallback, useMemo, useState } from "react";
import useTestTimer from "../hooks/useTestTimer";
import TestTimer from "../components/TestTimer";
import QuestionCard from "../components/QuestionCard";
import QuestionNavigator from "../components/QuestionNavigator";
import TestResult from "../components/TestResult";
import {
  getMockQuestions,
  getSubjects,
  getDifficulties,
  scoreTest,
  formatDuration,
  SECONDS_PER_QUESTION,
} from "../services/mockTest";
import { COUNT_OPTIONS } from "../data/mockTestData";

const SUBJECT_OPTIONS = getSubjects();
const DIFFICULTY_OPTIONS = getDifficulties();

/**
 * Internal running-test view. Remounted for every attempt (keyed by the
 * attempt id) so the timer and answers always start clean.
 */
function TestRunner({ subject, difficulty, questions, totalSeconds, onFinish, onExit }) {
  const [answers, setAnswers] = useState({});
  const [currentIndex, setCurrentIndex] = useState(0);
  const [showSubmitConfirm, setShowSubmitConfirm] = useState(false);
  const [showExitConfirm, setShowExitConfirm] = useState(false);

  const finishRef = useCallback(
    (byTime) => onFinish({ byTime, answers }),
    [onFinish, answers]
  );

  // Timer runs for the whole attempt; expiry auto-submits with the latest
  // answers (the hook keeps the callback in a ref, so this is never stale).
  const timer = useTestTimer({
    totalSeconds,
    active: true,
    onExpire: () => finishRef(true),
  });

  const handleSelectOption = (optionIndex) => {
    const question = questions[currentIndex];
    if (!question) return;
    setAnswers((prev) => ({ ...prev, [question.id]: optionIndex }));
  };

  const answeredCount = Object.keys(answers).length;

  return (
    <div className="test-running">
      <div className="test-running-header">
        <div>
          <span className="test-running-eyebrow">Demo Test</span>
          <h1>
            {subject} - {difficulty}
          </h1>
        </div>
        <div className="test-running-side">
          <TestTimer secondsLeft={timer.secondsLeft} totalSeconds={totalSeconds} />
          <button
            type="button"
            className="dash-btn secondary test-exit-btn"
            onClick={() => setShowExitConfirm(true)}
          >
            Exit Test
          </button>
        </div>
      </div>

      <div className="test-running-layout">
        <QuestionCard
          question={questions[currentIndex]}
          index={currentIndex}
          total={questions.length}
          selectedOption={answers[questions[currentIndex].id]}
          onSelectOption={handleSelectOption}
          onPrevious={() => setCurrentIndex((index) => Math.max(0, index - 1))}
          onNext={() =>
            setCurrentIndex((index) => Math.min(questions.length - 1, index + 1))
          }
          onSubmit={() => setShowSubmitConfirm(true)}
          isFirst={currentIndex === 0}
          isLast={currentIndex === questions.length - 1}
        />

        <QuestionNavigator
          total={questions.length}
          currentIndex={currentIndex}
          answers={answers}
          questionIds={questions.map((q) => q.id)}
          onJump={(index) => setCurrentIndex(index)}
        />
      </div>

      {/* SUBMIT CONFIRMATION */}
      {showSubmitConfirm && (
        <div
          className="modal-overlay"
          onClick={() => setShowSubmitConfirm(false)}
          role="presentation"
        >
          <div
            className="modal-card confirm-card"
            role="dialog"
            aria-modal="true"
            aria-labelledby="submit-confirm-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="modal-header">
              <h2 id="submit-confirm-title">Submit Test</h2>
            </div>

            <p className="confirm-text">
              You have answered {answeredCount} of {questions.length} questions.
              Are you sure you want to submit?
            </p>

            <div className="modal-actions">
              <button
                type="button"
                className="dash-btn secondary"
                onClick={() => setShowSubmitConfirm(false)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="dash-btn primary"
                onClick={() => finishRef(false)}
              >
                Submit Test
              </button>
            </div>
          </div>
        </div>
      )}

      {/* EXIT CONFIRMATION */}
      {showExitConfirm && (
        <div
          className="modal-overlay"
          onClick={() => setShowExitConfirm(false)}
          role="presentation"
        >
          <div
            className="modal-card confirm-card"
            role="dialog"
            aria-modal="true"
            aria-labelledby="exit-confirm-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="modal-header">
              <h2 id="exit-confirm-title">Exit Test</h2>
            </div>

            <p className="confirm-text">
              Your current answers and timer will be lost. Do you want to exit
              this test?
            </p>

            <div className="modal-actions">
              <button
                type="button"
                className="dash-btn secondary"
                onClick={() => setShowExitConfirm(false)}
              >
                Cancel
              </button>
              <button type="button" className="dash-btn primary" onClick={onExit}>
                Exit Test
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function MockTests() {
  const [phase, setPhase] = useState("setup");
  const [subject, setSubject] = useState(SUBJECT_OPTIONS[0]);
  const [difficulty, setDifficulty] = useState("Easy");
  const [count, setCount] = useState(5);

  const [attemptId, setAttemptId] = useState(0);
  const [questions, setQuestions] = useState([]);
  const [startedAt, setStartedAt] = useState(null);
  const [timeTaken, setTimeTaken] = useState(null);
  const [autoSubmitted, setAutoSubmitted] = useState(false);
  const [result, setResult] = useState(null);

  const availableCount = useMemo(
    () => getMockQuestions(subject, difficulty, Number.MAX_SAFE_INTEGER).length,
    [subject, difficulty]
  );

  const effectiveCount = Math.min(count, availableCount);
  const totalSeconds = Math.max(60, effectiveCount * SECONDS_PER_QUESTION);

  const finishTest = useCallback(
    ({ byTime, answers }) => {
      const elapsed = startedAt
        ? Math.min(totalSeconds, Math.round((Date.now() - startedAt) / 1000))
        : totalSeconds;
      setTimeTaken(byTime ? totalSeconds : elapsed);
      setResult(scoreTest(questions, answers));
      setPhase("finished");
    },
    [questions, startedAt, totalSeconds]
  );

  const handleStartTest = () => {
    setQuestions(getMockQuestions(subject, difficulty, effectiveCount));
    setAutoSubmitted(false);
    setStartedAt(Date.now());
    setTimeTaken(null);
    setResult(null);
    setAttemptId((id) => id + 1); // remounts TestRunner: fresh timer/answers
    setPhase("running");
  };

  const backToSetup = () => {
    setPhase("setup");
    setQuestions([]);
    setResult(null);
    setAutoSubmitted(false);
  };

  return (
    <div className="mocktests-page">
      {/* ===================== SETUP PHASE ===================== */}
      {phase === "setup" && (
        <>
          <div className="page-header">
            <h1>Mock Tests</h1>
            <p>
              Practice placement-focused questions, test your knowledge, and
              identify areas for improvement.
            </p>
          </div>

          <div className="demo-banner">
            <span className="demo-chip">Demo Test</span>
            <span>
              These questions are frontend demo content. A real question
              database/API will be connected later.
            </span>
          </div>

          <div className="prediction-card test-setup-card">
            <h2>Test Configuration</h2>
            <p className="form-description">
              Choose a subject, difficulty, and the number of questions.
            </p>

            <div className="test-setup-grid">
              <div className="form-group">
                <label htmlFor="test-subject">Subject</label>
                <select
                  id="test-subject"
                  value={subject}
                  onChange={(event) => setSubject(event.target.value)}
                >
                  {SUBJECT_OPTIONS.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label htmlFor="test-difficulty">Difficulty</label>
                <select
                  id="test-difficulty"
                  value={difficulty}
                  onChange={(event) => setDifficulty(event.target.value)}
                >
                  {DIFFICULTY_OPTIONS.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label htmlFor="test-count">Number of Questions</label>
                <select
                  id="test-count"
                  value={count}
                  onChange={(event) => setCount(Number(event.target.value))}
                >
                  {COUNT_OPTIONS.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="test-summary">
              <div className="test-summary-row">
                <span>Subject</span>
                <strong>{subject}</strong>
              </div>
              <div className="test-summary-row">
                <span>Difficulty</span>
                <strong>{difficulty}</strong>
              </div>
              <div className="test-summary-row">
                <span>Number of Questions</span>
                <strong>
                  {effectiveCount}
                  {effectiveCount < count
                    ? ` (only ${availableCount} demo question${
                        availableCount === 1 ? "" : "s"
                      } available)`
                    : ""}
                </strong>
              </div>
              <div className="test-summary-row">
                <span>Estimated Time</span>
                <strong>
                  {Math.max(1, Math.round(totalSeconds / 60))} minute
                  {totalSeconds >= 90 ? "s" : ""}
                </strong>
              </div>
            </div>

            <button
              type="button"
              className="predict-button"
              onClick={handleStartTest}
              disabled={effectiveCount === 0}
            >
              <span>Start Test</span>
            </button>
          </div>
        </>
      )}

      {/* ===================== RUNNING PHASE ===================== */}
      {phase === "running" && questions.length > 0 && (
        <TestRunner
          key={attemptId}
          subject={subject}
          difficulty={difficulty}
          questions={questions}
          totalSeconds={totalSeconds}
          onFinish={finishTest}
          onExit={backToSetup}
        />
      )}

      {/* ===================== RESULT PHASE ===================== */}
      {phase === "finished" && result && (
        <>
          {autoSubmitted && (
            <div className="demo-banner auto-submit-note" role="status">
              <span>Time is up - the test was submitted automatically.</span>
            </div>
          )}
          <TestResult
            result={result}
            subject={subject}
            difficulty={difficulty}
            timeTaken={formatDuration(timeTaken)}
            onRetake={handleStartTest}
            onNavigate={backToSetup}
          />
        </>
      )}
    </div>
  );
}

export default MockTests;
