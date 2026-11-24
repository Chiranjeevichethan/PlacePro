/**
 * MatchProgress - progress bar with a percentage label, reusing the existing
 * .progress-track / .progress-fill design-system classes. The fill color
 * follows the existing rating classes used by PerformanceAnalysis.
 */
function MatchProgress({ percent, label = "Skill Match" }) {
  const value = Math.max(0, Math.min(100, Number(percent) || 0));

  const ratingClass =
    value >= 85
      ? "rating-excellent"
      : value >= 70
        ? "rating-good"
        : value >= 50
          ? "rating-average"
          : "rating-low";

  return (
    <div className="match-progress">
      <div className="match-progress-header">
        <span>{label}</span>
        <strong>{value}%</strong>
      </div>

      <div className="progress-track">
        <div
          className={`progress-fill ${ratingClass}`}
          style={{ width: `${value}%` }}
        ></div>
      </div>
    </div>
  );
}

export default MatchProgress;
