import IconMark from "./IconMark";

/**
 * StatsCard - dashboard statistic tile.
 *
 * `chip` is an optional badge (e.g. "REAL DATA"); when omitted no badge is
 * rendered — never a fake "DEMO" marker on real backend values.
 */
function StatsCard({ title, value, description, icon, accent = "blue", chip = null }) {
  return (
    <div className="stats-card">
      <div className="stats-card-top">
        <IconMark name={icon} className={`stats-card-icon ${accent}`} />
        {chip && <span className="demo-chip">{chip}</span>}
      </div>

      <div className="stats-card-title">{title}</div>

      <div className="stats-card-value">{value}</div>

      <div className="stats-card-description">{description}</div>
    </div>
  );
}

export default StatsCard;
