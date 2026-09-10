/**
 * TestResult - the post-submission view: demo score summary, retake button,
 * skill-gap pathway ("Improve Your Skills"), demo topic performance, weak
 * areas, and the full answer review with explanations. Everything shown is
 * computed from the demo test and labeled as demo.
 */
import IconMark from "./IconMark";

function TestResult({ result, subject, difficulty, timeTaken, onRetake, onNavigate }) {
  const reviewEntries = result.perQuestion;

  return (
    <div className="test-result">
      {/* ---------- SCORE SUMMARY ---------- */}
      <div className="prediction-result test-result-card">
        <h2>Test Completed</h2>

        <div className="result-body">
          <div className="salary-result-top">
            <div className="salary-estimate">
              <div className="prediction-percentage">{result.percentage}%</div>
              <div className="prediction-probability-label">
                Demo Test Result
              </div>
            </div>

            <div className="salary-meta">
              <div className="salary-meta-row">
                <span>Score</span>
                <strong>
                  {result.score} / {result.total}
                </strong>
              </div>
              <div className="salary-meta-row">
                <span>Correct Answers</span>
                <strong>{result.score}</strong>
              </div>
              <div className="salary-meta-row">
                <span>Wrong Answers</span>
                <strong>{result.wrong}</strong>
              </div>
              <div className="salary-meta-row">
                <span>Unanswered</span>
                <strong>{result.unanswered}</strong>
              </div>
              <div className="salary-meta-row">
                <span>Subject</span>
                <strong>{subject}</strong>
              </div>
              <div className="salary-meta-row">
                <span>Difficulty</span>
                <strong>{difficulty}</strong>
              </div>
              <div className="salary-meta-row">
                <span>Time Taken</span>
                <strong>{timeTaken}</strong>
              </div>
            </div>
          </div>

          <div className="confidence-track">
            <div
              className={`confidence-fill ${
                result.percentage >= 50
                  ? "confidence-placed"
                  : "confidence-risk"
              }`}
              style={{ width: `${result.percentage}%` }}
            ></div>
          </div>

          <div className="test-result-actions">
            <button
              type="button"
              className="dash-btn primary"
              onClick={onRetake}
            >
              Retake Test
            </button>
          </div>

          <p className="prediction-data-note">
            Demo Test Result - scored locally in the browser, not by an ML
            model.
          </p>
        </div>
      </div>

      {/* ---------- IMPROVE YOUR SKILLS (pathway to Skill Gap) ---------- */}
      <div className="dash-card improve-skills-card">
        <div className="dash-card-header">
          <IconMark name="skills" className="dash-card-icon purple" />
          <h2>Improve Your Skills</h2>
        </div>

        <p>
          {result.weakTopics.length > 0
            ? "Consider revising these topics before taking another test."
            : "Strong result! Keep practicing other subjects to stay sharp."}
        </p>

        <div className="improve-skills-actions">
          <button
            type="button"
            className="dash-btn primary"
            onClick={() => onNavigate("skillgap")}
          >
            View Skill Gap
          </button>
          <button
            type="button"
            className="dash-btn secondary"
            onClick={() => onNavigate("companies")}
          >
            View Company Recommendations
          </button>
        </div>
      </div>

      {/* ---------- TOPIC PERFORMANCE ---------- */}
      <div className="dash-card topic-performance-card">
        <div className="dash-card-header">
          <IconMark name="overview" className="dash-card-icon blue" />
          <h2>Topic Performance (Demo)</h2>
        </div>

        <div className="bar-list">
          {result.topicPerformance.map((topic) => (
            <div key={topic.topic} className="bar-row">
              <div className="bar-row-header">
                <span>{topic.topic}</span>
                <strong>
                  {topic.correct}/{topic.total} - {topic.percentage}%
                </strong>
              </div>
              <div className="progress-track">
                <div
                  className={`progress-fill ${
                    topic.percentage >= 60
                      ? "rating-good"
                      : "rating-low"
                  }`}
                  style={{ width: `${topic.percentage}%` }}
                ></div>
              </div>
            </div>
          ))}
        </div>

        {result.weakTopics.length > 0 && (
          <div className="weak-topics">
            <h3>Weak Areas</h3>
            <div className="skill-chip-row">
              {result.weakTopics.map((topic) => (
                <span key={topic} className="skill-chip missing">
                  {topic}
                </span>
              ))}
            </div>
            <p className="weak-topics-note">
              Consider revising these topics before taking another test.
            </p>
          </div>
        )}
      </div>

      {/* ---------- ANSWER REVIEW ---------- */}
      <div className="dash-card answer-review-card">
        <div className="dash-card-header">
          <IconMark name="academic" className="dash-card-icon green" />
          <h2>Answer Review</h2>
        </div>

        <div className="review-list">
          {reviewEntries.map(({ question, selectedIndex, status }, index) => (
            <div key={question.id} className={`review-item ${status}`}>
              <div className="review-item-header">
                <span className="review-status">
                  {status === "correct" && "✓ Correct"}
                  {status === "wrong" && "✗ Incorrect"}
                  {status === "unanswered" && "— Not answered"}
                </span>
                <span className="review-topic">{question.topic}</span>
              </div>

              <p className="review-question">
                {index + 1}. {question.question}
              </p>

              <div className="review-answers">
                <div className="review-answer-row">
                  <span>Your Answer</span>
                  <strong
                    className={status === "wrong" ? "review-wrong" : ""}
                  >
                    {selectedIndex !== null
                      ? question.options[selectedIndex]
                      : "Not answered"}
                  </strong>
                </div>
                <div className="review-answer-row">
                  <span>Correct Answer</span>
                  <strong>{question.options[question.correctAnswer]}</strong>
                </div>
              </div>

              <p className="review-explanation">{question.explanation}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default TestResult;
