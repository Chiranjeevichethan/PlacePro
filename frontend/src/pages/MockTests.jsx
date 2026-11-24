/**
 * Assessment UI backed by server timing, state and scores.
 * Session references/answer drafts survive refresh; official results are reloaded.
 */
import { useEffect, useRef, useState } from "react";
import AccessibleModal from "../components/AccessibleModal";
import useTestTimer from "../hooks/useTestTimer";
import TestTimer from "../components/TestTimer";
import QuestionCard from "../components/QuestionCard";
import QuestionNavigator from "../components/QuestionNavigator";
import TestResult from "../components/TestResult";
import { API_BASE_URL } from "../services/api";
import {
  getMockQuestions,
  getAssessment,
  getAssessmentHistory,
  submitMockTest,
  formatDuration,
  SECONDS_PER_QUESTION,
} from "../services/mockTest";
import { assessmentStorageKey, createAssessmentController } from "../services/assessmentSession";
import { useStudentProfileContext } from "../hooks/useStudentProfileContext";
import { useAuth } from '../hooks/useAuth';

const SKILL_OPTIONS = [
  "Python", "Java", "C", "C++", "JavaScript", "SQL",
  "Data Structures", "Algorithms", "React", "Machine Learning", "HTML/CSS", "Git",
];
const COUNT_OPTIONS = [5, 10, 25];

function formatRemaining(seconds) {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (hours > 0) return hours + "h " + minutes + "m";
  return minutes + "m " + (seconds % 60) + "s";
}

function RequestError({ state, onRetry, retryLabel = "Try Again", disabled = false }) {
  if (!state.error) return null;
  return (
    <div className="error-banner" role="alert">
      <span>
        {state.error}
        {state.cooldownSeconds > 0 && (
          <> Time remaining: about {formatRemaining(state.cooldownSeconds)}.</>
        )}
      </span>
      {onRetry && (
        <button type="button" className="dash-btn secondary" onClick={onRetry}
          disabled={disabled || state.starting || state.submitting || state.checking ||
            state.cooldownSeconds > 0 || state.limitReached}>
          {retryLabel}
        </button>
      )}
    </div>
  );
}

function TestRunner({ state, controller, onExit, onCancelExit }) {
  const { session, answers, submitting, checking } = state;
  const questions = session.questions;
  const [currentIndex, setCurrentIndex] = useState(0);
  const [showSubmitConfirm, setShowSubmitConfirm] = useState(false);
  const [showExitConfirm, setShowExitConfirm] = useState(false);
  const queuedExitConfirm = useRef(false);
  const blocked = submitting || checking || state.locked || state.secondsLeft <= 0 ||
    state.cooldownSeconds > 0 || state.limitReached;
  const statusOnly = state.locked || state.secondsLeft <= 0 || state.errorStatus === 409;

  const closeSubmitConfirm = () => {
    setShowSubmitConfirm(false);
    if (queuedExitConfirm.current) {
      queuedExitConfirm.current = false;
      setShowExitConfirm(true);
    }
  };

  const cancelExit = () => {
    setShowExitConfirm(false);
    onCancelExit?.();
  };

  useEffect(() => {
    const requestLeave = () => {
      if (showSubmitConfirm) queuedExitConfirm.current = true;
      else setShowExitConfirm(true);
    };
    window.addEventListener("placepro:request-assessment-leave", requestLeave);
    return () => window.removeEventListener("placepro:request-assessment-leave", requestLeave);
  }, [showSubmitConfirm]);

  return (
    <div className="test-running">
      <div className="test-running-header">
        <div>
          <span className="test-running-eyebrow">Mock Test · Attempt {session.attempt}</span>
          <h1>{session.skill}</h1>
        </div>
        <div className="test-running-side">
          <TestTimer secondsLeft={state.secondsLeft} totalSeconds={state.totalSeconds} />
          <button type="button" className="dash-btn secondary test-exit-btn"
            onClick={() => setShowExitConfirm(true)}>
            Leave Test
          </button>
        </div>
      </div>

      {submitting && (
        <div className="demo-banner auto-submit-note" role="status">
          {state.autoAttempted
            ? "The deadline is approaching. Submitting your available answers..."
            : "Submitting your answers. Waiting for confirmation..."}
        </div>
      )}
      {checking && (
        <div className="demo-banner" role="status">Checking the saved assessment status...</div>
      )}
      <RequestError state={state}
        onRetry={statusOnly ? () => controller.checkStatus() : controller.retrySubmission}
        retryLabel={statusOnly ? "Check Status" : "Retry Submission"} />

      <div className="test-running-layout">
        <QuestionCard question={questions[currentIndex]} index={currentIndex}
          total={questions.length} selectedOption={answers[questions[currentIndex].question_id]}
          onSelectOption={(index) => controller.selectAnswer(questions[currentIndex].question_id, index)}
          onPrevious={() => setCurrentIndex((index) => Math.max(0, index - 1))}
          onNext={() => setCurrentIndex((index) => Math.min(questions.length - 1, index + 1))}
          onSubmit={() => setShowSubmitConfirm(true)}
          isFirst={currentIndex === 0} isLast={currentIndex === questions.length - 1}
          disabled={blocked} />
        <QuestionNavigator total={questions.length} currentIndex={currentIndex}
          answers={answers} questionIds={questions.map((q) => q.question_id)}
          onJump={setCurrentIndex} />
      </div>

      {showSubmitConfirm && (
        <AccessibleModal
          className="modal-card confirm-card"
          labelledBy="submit-confirm-title"
          describedBy="submit-confirm-description"
          closeBlocked={submitting}
          onEscape={closeSubmitConfirm}
          onBackdropClose={closeSubmitConfirm}
        >
            <div className="modal-header"><h2 id="submit-confirm-title">Submit Test</h2></div>
            <p id="submit-confirm-description" className="confirm-text" role={submitting ? "status" : undefined}>
              {submitting
                ? "Submitting your answers..."
                : "You have answered " + Object.keys(answers).length + " of " + questions.length +
                  " questions. Are you sure you want to submit?"}
            </p>
            {state.error && <p role="alert">{state.error}</p>}
            <div className="modal-actions">
              <button type="button" className="dash-btn secondary"
                onClick={closeSubmitConfirm} disabled={submitting} data-modal-initial-focus>Cancel</button>
              <button type="button" className="dash-btn primary" disabled={blocked}
                onClick={async () => { await controller.submit(); closeSubmitConfirm(); }}>
                {submitting ? "Submitting..." : "Submit Test"}
              </button>
            </div>
        </AccessibleModal>
      )}

      {showExitConfirm && (
        <AccessibleModal
          className="modal-card confirm-card"
          labelledBy="exit-confirm-title"
          describedBy="exit-confirm-description"
          onEscape={cancelExit}
          onBackdropClose={cancelExit}
        >
            <div className="modal-header"><h2 id="exit-confirm-title">Leave Test</h2></div>
            <p id="exit-confirm-description" className="confirm-text">
              Your answers are kept in this tab. The assessment deadline continues while you are away.
              Return to Mock Tests to continue.
            </p>
            <div className="modal-actions">
              <button type="button" className="dash-btn secondary"
                onClick={cancelExit} data-modal-initial-focus>Cancel</button>
              <button type="button" className="dash-btn primary"
                onClick={() => { setShowExitConfirm(false); onExit(); }}>Leave Test</button>
            </div>
        </AccessibleModal>
      )}
    </div>
  );
}

function AssessmentFlow({ profileId, accountId, onCompleted, onNavigate, onAssessmentStateChange,
  onAssessmentLeaveConfirmed, onAssessmentLeaveCancelled }) {
  const [controller] = useState(() => createAssessmentController({
    profileId,
    api: { start: getMockQuestions, submit: submitMockTest, get: getAssessment, history: getAssessmentHistory },
    storageKey: assessmentStorageKey(profileId, API_BASE_URL, accountId),
    onCompleted,
  }));
  const state = useTestTimer(controller);
  useEffect(() => {
    onAssessmentStateChange?.({
      active: state.phase === "loading" || state.phase === "running" || state.starting || state.submitting || state.checking,
      dialogAvailable: state.phase === "running" && state.session?.questions?.length > 0,
    });
  }, [onAssessmentStateChange, state.checking, state.phase, state.session?.questions?.length, state.starting, state.submitting]);
  const startDisabled = state.starting || state.submitting || state.checking ||
    state.cooldownSeconds > 0 || state.limitReached;
  const toSetup = () => controller.configure(state.skill, state.count);

  return (
    <div className="mocktests-page">
      {state.storageWarning && (
        <div className="demo-banner" role="status">{state.storageWarning}</div>
      )}

      {state.phase === "loading" && (
        <div className="prediction-card" role="status">Loading saved assessment...</div>
      )}

      {state.phase === "unavailable" && (
        <div className="prediction-card">
          <h1>Assessment unavailable</h1>
          <RequestError state={state} onRetry={controller.restore} retryLabel="Check Status" />
          <button type="button" className="dash-btn secondary" onClick={toSetup}>
            Test Configuration
          </button>
        </div>
      )}

      {state.phase === "setup" && (
        <>
          <div className="page-header">
            <h1>Mock Tests</h1>
            <p>Practice placement-focused questions, test your knowledge, and identify areas for improvement.</p>
          </div>
          <div className="prediction-card test-setup-card">
            <h2>Test Configuration</h2>
            <p className="form-description">Choose a skill and the number of questions, then start the assessment.</p>
            <div className="test-setup-grid">
              <div className="form-group">
                <label htmlFor="test-skill">Skill</label>
                <select id="test-skill" value={state.skill} disabled={state.starting}
                  onChange={(event) => controller.configure(event.target.value, state.count)}>
                  {SKILL_OPTIONS.map((option) => <option key={option} value={option}>{option}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label htmlFor="test-count">Number of Questions</label>
                <select id="test-count" value={state.count} disabled={state.starting}
                  onChange={(event) => controller.configure(state.skill, Number(event.target.value))}>
                  {COUNT_OPTIONS.map((option) => <option key={option} value={option}>{option}</option>)}
                </select>
              </div>
            </div>
            <div className="test-summary">
              <div className="test-summary-row"><span>Skill</span><strong>{state.skill}</strong></div>
              <div className="test-summary-row"><span>Number of Questions</span><strong>{state.count}</strong></div>
              <div className="test-summary-row">
                <span>Estimated Time</span><strong>{state.count * SECONDS_PER_QUESTION / 60} minutes</strong>
              </div>
            </div>
            <p className="form-description">
              The server sets the deadline. Answers are submitted automatically as that deadline approaches.
            </p>
            <RequestError state={state} onRetry={controller.startNew} />
            <button type="button" className="predict-button" onClick={controller.startNew}
              disabled={startDisabled}>
              <span>{state.starting ? "Starting Test..." : "Start Test"}</span>
            </button>
            {state.result && (
              <button type="button" className="dash-btn secondary" onClick={controller.showResult}>
                View Completed Result
              </button>
            )}
          </div>
        </>
      )}

      {state.phase === "running" && state.session?.questions?.length > 0 && (
        <TestRunner key={state.session.assessment_id} state={state} controller={controller}
          onExit={onAssessmentLeaveConfirmed} onCancelExit={onAssessmentLeaveCancelled} />
      )}

      {state.phase === "expired" && (
        <div className="prediction-card">
          <h1>Assessment Expired</h1>
          <RequestError state={state} />
          <p>No late answers were scored. Completed results remain in your assessment history.</p>
          <button type="button" className="dash-btn primary" onClick={toSetup}>Test Configuration</button>
        </div>
      )}

      {state.phase === "finished" && state.result && (
        <>
          {state.starting && (
            <div className="demo-banner" role="status">Starting a new assessment. Your previous result is saved.</div>
          )}
          {state.autoSubmitted && (
            <div className="demo-banner auto-submit-note" role="status">
              Your deadline submission has been confirmed.
            </div>
          )}
          <RequestError state={state} onRetry={controller.startNew} retryLabel="Retry Retake" />
          <TestResult result={state.result} skill={state.result.skill}
            timeTaken={state.timeTakenSeconds === null ? undefined : formatDuration(state.timeTakenSeconds)}
            onRetake={controller.startNew} retaking={state.starting} retakeDisabled={startDisabled}
            onNavigate={onNavigate} />
          <button type="button" className="dash-btn secondary" onClick={toSetup}
            disabled={state.starting}>Test Configuration</button>
        </>
      )}
    </div>
  );
}

function MockTests({ onNavigate, onAssessmentStateChange, onAssessmentLeaveConfirmed, onAssessmentLeaveCancelled }) {
  const { profileId, rawProfile, error, refetch } = useStudentProfileContext();
  const { account } = useAuth();
  if (!profileId || !rawProfile || error) return <div className="prediction-card">
    <h1>Mock Tests</h1><p>Create or select an available profile before starting an assessment.</p>
    <button type="button" className="dash-btn primary" onClick={() => onNavigate?.('profile')}>Student Profile</button>
  </div>;
  // Key by identity: another profile cannot display this student's answers or result.
  return <AssessmentFlow key={profileId} profileId={profileId} accountId={account.account_id}
    onCompleted={refetch} onNavigate={onNavigate} onAssessmentStateChange={onAssessmentStateChange}
    onAssessmentLeaveConfirmed={onAssessmentLeaveConfirmed} onAssessmentLeaveCancelled={onAssessmentLeaveCancelled} />;
}

export default MockTests;
