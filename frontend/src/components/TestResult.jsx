/**
 * TestResult - the post-submission view for the REAL backend assessment
 * result (Phase 6B, Step 4).
 *
 * Everything displayed comes from the backend submit response — nothing is
 * calculated, reshaped, or substituted here:
 *   { skill_score, level, correct, total,
 *     difficulty_breakdown, topic_breakdown, message }
 *
 * The backend does NOT return answer keys or explanations, so the old
 * per-question review (correct answers / explanations) is removed entirely.
 * `timeTaken` is UI timing information only.
 */
import IconMark from "./IconMark";

/** True when a value is a plain object (not null, not an array). */
const isPlainObject = (value) =>
  value !== null && typeof value === "object" && !Array.isArray(value);

/** True when the value can be shown without displaying NaN/undefined. */
const isDisplayable = (value) =>
  typeof value === "number"
    ? Number.isFinite(value)
    : value !== null && value !== undefined && value !== "";

/**
 * Normalize a breakdown entry to a displayable shape. The backend
 * breakdown schema is not assumed: entries may be objects with any
 * label/value fields, or plain strings/numbers. Only values that are
 * actually present are rendered — nothing is invented.
 */
function toBreakdownEntry(key, value) {
  if (typeof value === "string" || typeof value === "number") {
    return { label: key, values: [value] };
  }

  if (Array.isArray(value)) {
    return { label: key, values: value.filter(isDisplayable) };
  }

  if (isPlainObject(value)) {
    const label =
      value.label ??
      value.name ??
      value.topic ??
      value.difficulty ??
      value.skill ??
      key;

    const values = Object.entries(value)
      .filter(
        ([field, val]) =>
          field !== "label" &&
          field !== "name" &&
          field !== "topic" &&
          field !== "difficulty" &&
          field !== "skill" &&
          isDisplayable(val) &&
          !isPlainObject(val) &&
          !Array.isArray(val)
      )
      .map(([, val]) => val);

    return { label, values };
  }

  return null;
}

/**
 * Flatten any breakdown (object keyed by label, or array of entries)
 * into [{ label, values }] in backend order. Returns [] when empty.
 */
function toBreakdownList(breakdown) {
  if (Array.isArray(breakdown)) {
    return breakdown
      .map((entry, index) =>
        isPlainObject(entry)
          ? toBreakdownEntry(
              entry.label ?? entry.name ?? entry.topic ?? entry.difficulty ?? `#${index + 1}`,
              entry
            )
          : toBreakdownEntry(`#${index + 1}`, entry)
      )
      .filter(Boolean);
  }

  if (isPlainObject(breakdown)) {
    return Object.entries(breakdown)
      .map(([key, value]) => toBreakdownEntry(key, value))
      .filter(Boolean);
  }

  return [];
}

function TestResult({ result, skill, timeTaken, onRetake, onNavigate }) {
  const scoreValue = Number(result?.skill_score);
  const hasScore = Number.isFinite(scoreValue);
  const level = isDisplayable(result?.level) ? result.level : null;
  const message = isDisplayable(result?.message) ? result.message : null;

  const hasCounts =
    Number.isFinite(Number(result?.correct)) &&
    Number.isFinite(Number(result?.total));

  const difficultyList = toBreakdownList(result?.difficulty_breakdown);
  const topicList = toBreakdownList(result?.topic_breakdown);

  return (
    <div className="test-result">
      {/* ---------- SCORE SUMMARY ---------- */}
      <div className="prediction-result test-result-card">
        <h2>Test Completed</h2>

        {hasScore ? (
          <div className="result-body">
            <div className="salary-result-top">
              <div className="salary-estimate">
                <div className="prediction-percentage">{scoreValue}%</div>
                <div className="prediction-probability-label">
                  {level ?? "Assessment Result"}
                </div>
              </div>

              <div className="salary-meta">
                <div className="salary-meta-row">
                  <span>Skill</span>
                  <strong>{skill ?? "—"}</strong>
                </div>
                <div className="salary-meta-row">
                  <span>Level</span>
                  <strong>{level ?? "—"}</strong>
                </div>
                <div className="salary-meta-row">
                  <span>Correct / Total</span>
                  <strong>
                    {hasCounts ? `${Number(result.correct)} / ${Number(result.total)}` : "—"}
                  </strong>
                </div>
                <div className="salary-meta-row">
                  <span>Time Taken</span>
                  <strong>{timeTaken ?? "—"}</strong>
                </div>
              </div>
            </div>

            <div className="confidence-track">
              <div
                className={`confidence-fill ${
                  scoreValue >= 50 ? "confidence-placed" : "confidence-risk"
                }`}
                style={{ width: `${scoreValue}%` }}
              ></div>
            </div>

            {message && <p className="prediction-data-note">{message}</p>}

            <div className="test-result-actions">
              <button
                type="button"
                className="dash-btn primary"
                onClick={onRetake}
              >
                Retake Test
              </button>
            </div>
          </div>
        ) : (
          <div className="result-body">
            <p className="prediction-data-note">
              Assessment result is unavailable.
            </p>
            <div className="test-result-actions">
              <button
                type="button"
                className="dash-btn primary"
                onClick={onRetake}
              >
                Retake Test
              </button>
            </div>
          </div>
        )}
      </div>

      {/* ---------- IMPROVE YOUR SKILLS (pathway) ---------- */}
      <div className="dash-card improve-skills-card">
        <div className="dash-card-header">
          <IconMark name="skills" className="dash-card-icon purple" />
          <h2>Improve Your Skills</h2>
        </div>

        <p>
          Use your result to target practice where it matters before taking
          another assessment.
        </p>

        <div className="improve-skills-actions">
          <button
            type="button"
            className="dash-btn primary"
            onClick={() => onNavigate?.("skillgap")}
          >
            View Skill Gap
          </button>
          <button
            type="button"
            className="dash-btn secondary"
            onClick={() => onNavigate?.("companies")}
          >
            View Company Recommendations
          </button>
        </div>
      </div>

      {/* ---------- DIFFICULTY BREAKDOWN (backend data) ---------- */}
      <div className="dash-card topic-performance-card">
        <div className="dash-card-header">
          <IconMark name="overview" className="dash-card-icon blue" />
          <h2>Difficulty Breakdown</h2>
        </div>

        {difficultyList.length > 0 ? (
          <div className="bar-list">
            {difficultyList.map((entry, index) => (
              <div key={`${entry.label}-${index}`} className="bar-row">
                <div className="bar-row-header">
                  <span>{entry.label}</span>
                  <strong>
                    {entry.values
                      .map((value) => (typeof value === "number" ? String(value) : value))
                      .join(" · ")}
                  </strong>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="prediction-data-note">
            No difficulty breakdown available.
          </p>
        )}
      </div>

      {/* ---------- TOPIC BREAKDOWN (backend data) ---------- */}
      <div className="dash-card topic-performance-card">
        <div className="dash-card-header">
          <IconMark name="academic" className="dash-card-icon green" />
          <h2>Topic Breakdown</h2>
        </div>

        {topicList.length > 0 ? (
          <div className="bar-list">
            {topicList.map((entry, index) => (
              <div key={`${entry.label}-${index}`} className="bar-row">
                <div className="bar-row-header">
                  <span>{entry.label}</span>
                  <strong>
                    {entry.values
                      .map((value) => (typeof value === "number" ? String(value) : value))
                      .join(" · ")}
                  </strong>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="prediction-data-note">
            No topic breakdown available.
          </p>
        )}
      </div>

      {/* ---------- ANSWER REVIEW (removed: no answer keys from backend) ---------- */}
      <div className="dash-card answer-review-card">
        <div className="dash-card-header">
          <IconMark name="academic" className="dash-card-icon green" />
          <h2>Answer Review</h2>
        </div>

        <p className="prediction-data-note">
          Answer review is unavailable because answers are securely evaluated
          by the server.
        </p>
      </div>
    </div>
  );
}

export default TestResult;
