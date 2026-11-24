/**
 * TestTimer - displays the countdown (M:SS). Turns amber under 60s and red
 * under 10s. The interval itself lives in the useTestTimer hook.
 */
function TestTimer({ secondsLeft, totalSeconds }) {
  const safe = Math.max(0, Number(secondsLeft) || 0);
  const minutes = Math.floor(safe / 60);
  const seconds = safe % 60;
  const label = `${minutes}:${String(seconds).padStart(2, "0")}`;

  const urgency =
    safe <= 10 ? "critical" : safe <= 60 ? "warning" : "normal";

  return (
    <div className={`test-timer ${urgency}`} role="timer" aria-live="off">
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <circle cx="12" cy="13" r="8" />
        <path d="M12 9v4l2.5 2.5" />
        <path d="M9 2h6" />
      </svg>
      <span className="test-timer-label">Time Left</span>
      <strong>{label}</strong>
      <span className="visually-hidden">
        {Math.floor(totalSeconds / 60)} minute test
      </span>
    </div>
  );
}

export default TestTimer;
