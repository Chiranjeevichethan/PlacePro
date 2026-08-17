import StatsCard from "../components/StatsCard";
import IconMark from "../components/IconMark";

function readProfileName() {
  try {
    const raw = localStorage.getItem("placepro_profile");
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed?.name) return parsed.name;
    }
  } catch {
    // Fall back to default.
  }
  return "Bhargav";
}

const PLACED_RATE = 54.46;
const NOT_PLACED_RATE = 100 - PLACED_RATE;

const strengthData = [
  { label: "Academic Performance", value: 82 },
  { label: "Aptitude", value: 80 },
  { label: "Logical Reasoning", value: 78 },
];

const improvementData = [
  { label: "Coding Skill", value: 75 },
  { label: "Communication", value: 75 },
  { label: "Mock Interview", value: 70 },
];

const trendData = [
  { month: "Jan", value: 48 },
  { month: "Feb", value: 51 },
  { month: "Mar", value: 53 },
  { month: "Apr", value: 52 },
  { month: "May", value: 55 },
  { month: "Jun", value: 54 },
];

function TrendChart() {
  const width = 340;
  const height = 150;
  const padX = 26;
  const padY = 18;
  const minV = 40;
  const maxV = 60;

  const x = (i) => padX + (i * (width - padX * 2)) / (trendData.length - 1);
  const y = (v) =>
    height - padY - ((v - minV) / (maxV - minV)) * (height - padY * 2);

  const linePoints = trendData
    .map((d, i) => `${x(i)},${y(d.value)}`)
    .join(" ");

  const areaPoints = `${padX},${height - padY} ${linePoints} ${
    width - padX
  },${height - padY}`;

  return (
    <svg
      className="trend-chart"
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label="Placement trend over the last six months"
    >
      <defs>
        <linearGradient id="trendArea" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#2563eb" stopOpacity="0.28" />
          <stop offset="100%" stopColor="#7c3aed" stopOpacity="0" />
        </linearGradient>
        <linearGradient id="trendLine" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#2563eb" />
          <stop offset="100%" stopColor="#7c3aed" />
        </linearGradient>
      </defs>

      {[45, 50, 55, 60].map((v) => (
        <line
          key={v}
          x1={padX}
          y1={y(v)}
          x2={width - padX}
          y2={y(v)}
          className="chart-grid-line"
        />
      ))}

      <polygon points={areaPoints} fill="url(#trendArea)" />
      <polyline points={linePoints} className="chart-line" fill="none" />

      {trendData.map((d, i) => (
        <g key={d.month}>
          <circle cx={x(i)} cy={y(d.value)} r="4" className="chart-dot" />
          <text x={x(i)} y={height - 5} textAnchor="middle" className="chart-label">
            {d.month}
          </text>
          <text
            x={x(i)}
            y={y(d.value) - 9}
            textAnchor="middle"
            className="chart-value"
          >
            {d.value}%
          </text>
        </g>
      ))}
    </svg>
  );
}

function WelcomeArt() {
  return (
    <svg
      className="welcome-art"
      viewBox="0 0 300 190"
      role="presentation"
      aria-hidden="true"
      focusable="false"
    >
      {/* rising trend area + line */}
      <path
        className="art-area"
        d="M20 150 L75 118 L130 128 L185 88 L240 100 L285 42 L285 150 Z"
      />
      <polyline
        className="art-line"
        points="20,150 75,118 130,128 185,88 240,100 285,42"
      />

      {/* rising bars */}
      <rect className="art-bar" x="196" y="118" width="16" height="32" rx="4" />
      <rect className="art-bar" x="222" y="100" width="16" height="50" rx="4" />
      <rect className="art-bar" x="248" y="82" width="16" height="68" rx="4" />

      {/* graduation cap above the charts */}
      <g className="art-cap">
        <polygon points="196,44 226,34 256,44 226,54" />
        <path d="M206 52 h40 v8 h-40 z" />
        <line x1="244" y1="58" x2="256" y2="66" />
        <circle cx="258" cy="68" r="3" />
      </g>

      {/* transparent geometric shapes */}
      <circle
        cx="34"
        cy="66"
        r="22"
        fill="none"
        stroke="rgba(255,255,255,0.12)"
        strokeWidth="1.5"
      />
      <circle
        cx="120"
        cy="28"
        r="9"
        fill="none"
        stroke="rgba(255,255,255,0.14)"
        strokeWidth="1.5"
      />
      <line
        x1="0"
        y1="182"
        x2="96"
        y2="118"
        stroke="rgba(255,255,255,0.1)"
        strokeWidth="1.5"
      />

      {/* neural data nodes along the trend */}
      <circle className="art-node" cx="75" cy="118" r="4" />
      <circle className="art-node" cx="185" cy="88" r="4" />
      <circle className="art-node" cx="285" cy="42" r="4" />
      <circle className="art-dot" cx="40" cy="90" r="2" />
      <circle className="art-dot" cx="160" cy="150" r="2" />
      <circle className="art-dot" cx="252" cy="140" r="2" />
      <circle className="art-dot" cx="216" cy="60" r="2" />

      {/* sparkles / tiny stars */}
      <path className="art-sparkle" d="M96 40 l1.6 4.4 4.4 1.6 -4.4 1.6 -1.6 4.4 -1.6 -4.4 -4.4 -1.6 4.4 -1.6 Z" />
      <path className="art-sparkle" d="M268 20 l1.4 3.6 3.6 1.4 -3.6 1.4 -1.4 3.6 -1.4 -3.6 -3.6 -1.4 3.6 -1.4 Z" />
      <path className="art-sparkle" d="M46 130 l1.1 3 3 1.1 -3 1.1 -1.1 3 -1.1 -3 -3 -1.1 3 -1.1 Z" />
      <path className="art-sparkle" d="M212 150 l1 2.8 2.8 1 -2.8 1 -1 2.8 -1 -2.8 -2.8 -1 2.8 -1 Z" />
    </svg>
  );
}

function Dashboard({ onNavigate }) {
  const userName = readProfileName();

  return (
    <div className="dashboard">
      <div className="dashboard-welcome">
        <div className="welcome-content">
          <h1>Welcome back, {userName}! 👋</h1>
          <p>Track your placement readiness and get AI-powered insights.</p>

          <span className="welcome-badge">
            <svg
              className="badge-sparkle"
              viewBox="0 0 24 24"
              fill="currentColor"
              aria-hidden="true"
              focusable="false"
            >
              <path d="M12 2l2.4 7.6L22 12l-7.6 2.4L12 22l-2.4-7.6L2 12l7.6-2.4z" />
            </svg>
            AI-Powered Intelligence
          </span>
        </div>

        <WelcomeArt />
      </div>

      <div className="stats-grid">
        <StatsCard
          title="Total Students"
          value="100,000"
          description="Total students"
          icon="students"
          accent="blue"
        />

        <StatsCard
          title="Placement Rate"
          value="54.46%"
          description="Overall placement rate"
          icon="placement"
          accent="green"
        />

        <StatsCard
          title="Best Model"
          value="Random Forest"
          description="Best-performing model (initial run)"
          icon="model"
          accent="purple"
        />

        <StatsCard
          title="Model Accuracy"
          value="55.19%"
          description="Accuracy of the best model"
          icon="accuracy"
          accent="orange"
        />
      </div>

      <div className="info-note">
        <svg
          className="info-note-icon"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="16" x2="12" y2="12" />
          <line x1="12" y1="8" x2="12.01" y2="8" />
        </svg>
        <span>
          <strong>Demo application:</strong> This is a demo application. For
          real predictions, connect your backend server.
        </span>
      </div>

      <div className="dashboard-grid">
        <div className="dash-card">
          <div className="dash-card-header">
            <IconMark name="overview" className="dash-card-icon blue" />
            <h2>Placement Overview</h2>
          </div>

          <div className="overview-body">
            <div
              className="donut"
              style={{
                background: `conic-gradient(#2563eb 0deg, #7c3aed ${
                  PLACED_RATE * 3.6
                }deg, #eef2ff ${PLACED_RATE * 3.6}deg 360deg)`,
              }}
            >
              <div className="donut-center">
                <span className="donut-value">{PLACED_RATE}%</span>
                <span className="donut-label">Placed</span>
              </div>
            </div>

            <div className="overview-legend">
              <div className="legend-row">
                <span className="legend-dot placed"></span>
                <span>Placed</span>
                <strong>{PLACED_RATE}%</strong>
              </div>
              <div className="legend-row">
                <span className="legend-dot not-placed"></span>
                <span>Not Placed</span>
                <strong>{NOT_PLACED_RATE}%</strong>
              </div>
            </div>
          </div>

          <p className="dash-card-note">Based on the demo dataset split.</p>
        </div>

        <div className="dash-card">
          <div className="dash-card-header">
            <IconMark name="trend" className="dash-card-icon purple" />
            <h2>Placement Trend</h2>
          </div>

          <TrendChart />

          <p className="dash-card-note">
            Six-month trend - sample/demo values, not ML output.
          </p>
        </div>
      </div>

      <div className="dashboard-grid">
        <div className="dash-card">
          <div className="dash-card-header">
            <IconMark name="strengths" className="dash-card-icon green" />
            <h2>Top Strength Areas</h2>
          </div>

          <div className="bar-list">
            {strengthData.map((item) => (
              <div key={item.label} className="bar-row">
                <div className="bar-row-header">
                  <span>{item.label}</span>
                  <strong>{item.value}%</strong>
                </div>
                <div className="progress-track">
                  <div
                    className="progress-fill rating-excellent"
                    style={{ width: `${item.value}%` }}
                  ></div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="dash-card">
          <div className="dash-card-header">
            <IconMark name="improve" className="dash-card-icon orange" />
            <h2>Areas to Improve</h2>
          </div>

          <div className="bar-list">
            {improvementData.map((item) => (
              <div key={item.label} className="bar-row">
                <div className="bar-row-header">
                  <span>{item.label}</span>
                  <strong>{item.value}%</strong>
                </div>
                <div className="progress-track">
                  <div
                    className="progress-fill rating-average"
                    style={{ width: `${item.value}%` }}
                  ></div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="dashboard-actions">
        <button
          type="button"
          className="dash-btn primary"
          onClick={() => onNavigate("performance")}
        >
          View Full Analysis
        </button>
        <button
          type="button"
          className="dash-btn secondary"
          onClick={() => onNavigate("prediction")}
        >
          View Recommendations
        </button>
      </div>
    </div>
  );
}

export default Dashboard;
