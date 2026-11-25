/**
 * QuestionNavigator - numbered grid (1..N) with three visual states:
 * current, answered, unanswered. Clicking a number jumps to that question.
 * Answers live in the parent's state, so nothing is lost when jumping.
 */
function QuestionNavigator({
  total,
  currentIndex,
  answers,
  questionIds,
  onJump,
}) {
  return (
    <div className="dash-card question-navigator">
      <h3 className="navigator-title">Questions</h3>

      <div className="navigator-grid">
        {Array.from({ length: total }, (_, index) => {
          const questionId = questionIds[index];
          const answered = Number.isInteger(answers[questionId]);
          const isCurrent = index === currentIndex;
          const stateClass = isCurrent
            ? "current"
            : answered
              ? "answered"
              : "unanswered";

          return (
            <button
              key={questionId}
              type="button"
              className={`navigator-item ${stateClass}`}
              aria-label={`Question ${index + 1}${
                answered ? " (answered)" : " (not answered)"
              }`}
              aria-current={isCurrent ? "step" : undefined}
              onClick={() => onJump(index)}
            >
              {index + 1}
            </button>
          );
        })}
      </div>

      <div className="navigator-legend">
        <span className="legend-item">
          <span className="legend-dot answered" aria-hidden="true"></span>
          Answered
        </span>
        <span className="legend-item">
          <span className="legend-dot unanswered" aria-hidden="true"></span>
          Unanswered
        </span>
      </div>
    </div>
  );
}

export default QuestionNavigator;
