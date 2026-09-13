/**
 * Mock Tests page (Phase 6B, Step 3).
 *
 * REAL assessment flow: setup -> running test (timer + navigator) ->
 * confirmation -> submitting -> result.
 *
 * The backend is authoritative: questions come from the real assessment
 * API (see src/services/mockTest.js over src/services/api.js), and the
 * official score/level/breakdowns come only from the submit response —
 * nothing is scored or reshaped here.
 *
 * State machine: "setup" | "running" | "finished".
 * - While running, <TestRunner> owns answers/index/timer state. Its `key`
 *   is the attempt id, so Start and Retake remount it fresh: no answers or
 *   timer ever leak between attempts.
 * - The countdown is a CLIENT-SIDE CONVENIENCE only; the backend does not
 *   enforce timing (time_limit_minutes is null).
 * - Leaving the page unmounts everything, so no stale test state remains.
 */
import { useCallback, useRef, useState } from "react";
import useTestTimer from "../hooks/useTestTimer";
import TestTimer from "../components/TestTimer";
import QuestionCard from "../components/QuestionCard";
import QuestionNavigator from "../components/QuestionNavigator";
import TestResult from "../components/TestResult";
import {
  getMockQuestions,
  submitMockTest,
  formatDuration,
  SECONDS_PER_QUESTION,
} from "../services/mockTest";
import { DEMO_PROFILE_ID } from "../services/profileConfig";

/**
 * Backend canonical skills (the question bank's 12 skills). There is no
 * tests-list endpoint yet, so this exact list is used for the selector.
 */
const SKILL_OPTIONS = [
  "Python",
  "Java",
  "C",
  "C++",
  "JavaScript",
  "SQL",
  "Data Structures",
  "Algorithms",
  "React",
  "Machine Learning",
  "HTML/CSS",
  "Git",
];

/** Backend num_questions allows 1-10. */
const COUNT_OPTIONS = [5, 10];

/**
 * Map a thrown service error to a user-readable message. The service
 * layer already produces readable text; this only catches unexpected
 * values so no stack trace or raw error object is ever rendered.
 */
const toReadableError = (error) =>
  error instanceof Error && error.message
    ? error.message
    : "Unable to process the assessment. Please try again.";

/**
 * Internal running-test view. Remounted for every attempt (keyed by the
 * attempt id) so the timer and answers always start clean.
 */
function TestRunner({
  skill,
  questions,
  totalSeconds,
  submitting,
  submitError,
  onRetrySubmit,
  onFinish,
  onExit,
  latestAnswersRef,
}) {
  const [answers, setAnswers] = useState({});
  const [currentIndex, setCurrentIndex] = useState(0);
  const [showSubmitConfirm, setShowSubmitConfirm] = useState(false);
  const [showExitConfirm, setShowExitConfirm] = useState(false);

  const finishRef = useCallback(
    (byTime) => onFinish({ byTime, answers }),
    [onFinish, answers]
  );

  // Client-side convenience countdown for the whole attempt; expiry
  // auto-submits the latest answers (the hook keeps the callback in a ref,
  // so this is never stale). Not server-enforced.
  const timer = useTestTimer({
    totalSeconds,
    active: true,
    onExpire: () => finishRef(true),
  });

  const handleSelectOption = (optionIndex) => {
    const question = questions[currentIndex];
    if (!question) return;
    setAnswers((prev) => {
      const next = { ...prev, [question.question_id]: optionIndex };
      latestAnswersRef.current = next; // keep retry payload in sync
      return next;
    });
  };

  const answeredCount = Object.keys(answers).length;

  return (
    <div className="test-running">
      <div className="test-running-header">
        <div>
          <span className="test-running-eyebrow">Mock Test</span>
          <h1>{skill}</h1>
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

      {submitError && (
        <div className="error-banner" role="alert">
          <span>{submitError}</span>
          <button type="button" className="dash-btn secondary" onClick={onRetrySubmit}>
            Retry
          </button>
        </div>
      )}

      <div className="test-running-layout">
        <QuestionCard
          question={questions[currentIndex]}
          index={currentIndex}
          total={questions.length}
          selectedOption={answers[questions[currentIndex].question_id]}
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
          questionIds={questions.map((q) => q.question_id)}
          onJump={(index) => setCurrentIndex(index)}
        />
      </div>

      {/* SUBMIT CONFIRMATION */}
      {showSubmitConfirm && (
        <div
          className="modal-overlay"
          onClick={() => {
            if (!submitting) setShowSubmitConfirm(false);
          }}
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
              {submitting
                ? "Submitting your answers..."
                : `You have answered ${answeredCount} of ${questions.length} questions. Are you sure you want to submit?`}
            </p>

            <div className="modal-actions">
              <button
                type="button"
                className="dash-btn secondary"
                onClick={() => setShowSubmitConfirm(false)}
                disabled={submitting}
              >
                Cancel
              </button>
              <button
                type="button"
                className="dash-btn primary"
                onClick={() => finishRef(false)}
                disabled={submitting}
              >
                {submitting ? "Submitting..." : "Submit Test"}
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
  const [skill, setSkill] = useState(SKILL_OPTIONS[0]);
  const [count, setCount] = useState(5);

  const [attemptId, setAttemptId] = useState(0);
  const [assessmentId, setAssessmentId] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [startedAt, setStartedAt] = useState(null);
  const [timeTaken, setTimeTaken] = useState(null);
  const [autoSubmitted, setAutoSubmitted] = useState(false);
  const [result, setResult] = useState(null);

  // Request lifecycle for both start and submit.
  const [starting, setStarting] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  // Synchronous guard so a timer-expiry auto-submit and a manual submit
  // click can never call submitMockTest twice for the same assessment.
  const submittingRef = useRef(false);

  // Mirrors the runner's current answers so a failed submission can be
  // retried without losing what the student has selected.
  const latestAnswersRef = useRef({});

  const totalSeconds = Math.max(60, count * SECONDS_PER_QUESTION);

  const handleStartTest = useCallback(async () => {
    setError(null);
    setStarting(true);
    setResult(null);
    setAutoSubmitted(false);

    try {
      // Starts a REAL backend assessment (also the retake path: a fresh
      // assessment is created every time, never the previous one reused).
      const assessment = await getMockQuestions(DEMO_PROFILE_ID, skill, count);

      const backendQuestions = Array.isArray(assessment?.questions)
        ? assessment.questions
        : null;

      if (
        !assessment?.assessment_id ||
        !backendQuestions ||
        backendQuestions.length === 0
      ) {
        throw new Error(
          "The assessment service returned no questions. Please try again."
        );
      }

      setAssessmentId(assessment.assessment_id);
      setQuestions(backendQuestions);
      setStartedAt(Date.now());
      setTimeTaken(null);
      setAttemptId((id) => id + 1); // remounts TestRunner: fresh timer/answers
      setPhase("running");
    } catch (startError) {
      setError(toReadableError(startError));
    } finally {
      setStarting(false);
    }
  }, [skill, count]);

  const backToSetup = () => {
    setPhase("setup");
    setAssessmentId(null);
    setQuestions([]);
    setResult(null);
    setAutoSubmitted(false);
    setError(null);
  };

  const finishTest = useCallback(
    async ({ byTime, answers }) => {
      if (submittingRef.current) return; // a submission is already in flight
      submittingRef.current = true;

      const elapsed = startedAt
        ? Math.min(totalSeconds, Math.round((Date.now() - startedAt) / 1000))
        : totalSeconds;
      setTimeTaken(byTime ? totalSeconds : elapsed);
      if (byTime) setAutoSubmitted(true);

      setSubmitting(true);
      setError(null);

      try {
        // The service converts option indexes to answer text and calls
        // the backend; the returned result is authoritative and is stored
        // as-is (no local score/percentage/breakdowns are computed).
        const backendResult = await submitMockTest(
          assessmentId,
          questions,
          answers,
          DEMO_PROFILE_ID
        );
        setResult(backendResult);
        setPhase("finished");
      } catch (submitError) {
        // Submission failed: stay in the running phase with the answers
        // intact and let the runner show the error with a Retry option.
        setError(toReadableError(submitError));
      } finally {
        submittingRef.current = false;
        setSubmitting(false);
      }
    },
    [assessmentId, questions, startedAt, totalSeconds]
  );

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

          <div className="prediction-card test-setup-card">
            <h2>Test Configuration</h2>
            <p className="form-description">
              Choose a skill and the number of questions, then start the
              assessment.
            </p>

            <div className="test-setup-grid">
              <div className="form-group">
                <label htmlFor="test-skill">Skill</label>
                <select
                  id="test-skill"
                  value={skill}
                  onChange={(event) => setSkill(event.target.value)}
                >
                  {SKILL_OPTIONS.map((option) => (
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
                <span>Skill</span>
                <strong>{skill}</strong>
              </div>
              <div className="test-summary-row">
                <span>Number of Questions</span>
                <strong>{count}</strong>
              </div>
              <div className="test-summary-row">
                <span>Estimated Time</span>
                <strong>
                  {Math.max(1, Math.round(totalSeconds / 60))} minute
                  {totalSeconds >= 90 ? "s" : ""}
                </strong>
              </div>
            </div>

            {error && (
              <div className="error-banner" role="alert">
                <span>{error}</span>
                <button
                  type="button"
                  className="dash-btn secondary"
                  onClick={handleStartTest}
                >
                  Try Again
                </button>
              </div>
            )}

            <button
              type="button"
              className="predict-button"
              onClick={handleStartTest}
              disabled={starting}
            >
              <span>{starting ? "Starting Test..." : "Start Test"}</span>
            </button>
          </div>
        </>
      )}

      {/* ===================== RUNNING PHASE ===================== */}
      {phase === "running" && assessmentId && questions.length > 0 && (
        <TestRunner
          key={attemptId}
          skill={skill}
          questions={questions}
          totalSeconds={totalSeconds}
          submitting={submitting}
          submitError={error}
          onRetrySubmit={() =>
            finishTest({ byTime: false, answers: latestAnswersRef.current })
          }
          onFinish={finishTest}
          onExit={backToSetup}
          latestAnswersRef={latestAnswersRef}
        />
      )}

      {/* ===================== RESULT PHASE ===================== */}
      {phase === "finished" && result && (
        <>
          {autoSubmitted && (
            <div className="demo-banner auto-submit-note" role="status">
              <span>Time is up. Your answers were submitted.</span>
            </div>
          )}
          <TestResult
            result={result}
            skill={skill}
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
