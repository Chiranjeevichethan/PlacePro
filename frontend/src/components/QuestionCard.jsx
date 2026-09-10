/**
 * QuestionCard - one test question with its four options and the
 * Previous / Next / Submit Test controls. Answer selection is owned by the
 * parent (MockTests page); correct answers are NEVER revealed here.
 */
function QuestionCard({
  question,
  index,
  total,
  selectedOption,
  onSelectOption,
  onPrevious,
  onNext,
  onSubmit,
  isFirst,
  isLast,
}) {
  return (
    <div className="dash-card question-card">
      <div className="question-meta">
        <span className="question-number">
          Question {index + 1} of {total}
        </span>
        <span className="question-topic">{question.topic}</span>
      </div>

      <div className="progress-track question-progress">
        <div
          className="progress-fill question-progress-fill"
          style={{ width: `${((index + 1) / total) * 100}%` }}
        ></div>
      </div>

      <h3 className="question-text">{question.question}</h3>

      <div className="question-options" role="radiogroup" aria-label="Answer options">
        {question.options.map((option, optionIndex) => {
          const selected = selectedOption === optionIndex;

          return (
            <button
              key={option}
              type="button"
              className={`question-option ${selected ? "selected" : ""}`}
              role="radio"
              aria-checked={selected}
              onClick={() => onSelectOption(optionIndex)}
            >
              <span className="option-marker" aria-hidden="true">
                {String.fromCharCode(65 + optionIndex)}
              </span>
              <span className="option-text">{option}</span>
            </button>
          );
        })}
      </div>

      <div className="question-controls">
        <button
          type="button"
          className="dash-btn secondary"
          onClick={onPrevious}
          disabled={isFirst}
        >
          Previous
        </button>

        {isLast ? (
          <button
            type="button"
            className="dash-btn primary"
            onClick={onSubmit}
          >
            Submit Test
          </button>
        ) : (
          <button
            type="button"
            className="dash-btn primary"
            onClick={onNext}
          >
            Next
          </button>
        )}
      </div>
    </div>
  );
}

export default QuestionCard;
