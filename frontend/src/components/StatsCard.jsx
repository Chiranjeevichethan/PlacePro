import IconMark from "./IconMark";

function StatsCard({ title, value, description, icon, accent = "blue" }) {
  return (
    <div className="stats-card">
      <div className="stats-card-top">
        <IconMark name={icon} className={`stats-card-icon ${accent}`} />
        <span className="demo-chip">DEMO</span>
      </div>

      <div className="stats-card-title">{title}</div>

      <div className="stats-card-value">{value}</div>

      <div className="stats-card-description">{description}</div>
    </div>
  );
}

export default StatsCard;
