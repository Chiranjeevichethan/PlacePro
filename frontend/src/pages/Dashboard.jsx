import { useEffect, useState } from "react";
import StatsCard from "../components/StatsCard";
import SkillChip from "../components/SkillChip";
import IconMark from "../components/IconMark";
import {
  fetchStudentProfile,
  fetchPlacementSummary,
  fetchPerformance,
  fetchCompanyRecommendations,
} from "../services/api";
import { DEMO_PROFILE_ID } from "../services/profileConfig";

/* ------------------------------------------------------------------ */
/* Defensive readers (backend fields may be missing/null/empty)        */
/* ------------------------------------------------------------------ */

const pctOrNull = (value) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Math.round(parsed * 100) : null;
};

const pctValue = (value) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Math.round(parsed) : null;
};

const formatDate = (timestamp) => {
  if (typeof timestamp !== "string" || timestamp.length === 0) return "";
  const date = new Date(timestamp);
  return Number.isNaN(date.getTime())
    ? ""
    : date.toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
  });
};

function readProfileName() {
  try {
    const raw = localStorage.getItem("placepro_profile");
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed?.name) return parsed.name;
    }
  } catch {
    // Fall back to the backend profile name below.
  }
  return null;
}

/* ------------------------------------------------------------------ */
/* Static welcome art (decorative only — carries no data)              */
/* ------------------------------------------------------------------ */

function WelcomeArt() {
  return (
    <svg
      className="welcome-art"
      viewBox="0 0 300 190"
      role="presentation"
      aria-hidden="true"
      focusable="false"
    >
      <path
        className="art-area"
        d="M20 150 L75 118 L130 128 L185 88 L240 100 L285 42 L285 150 Z"
      />
      <polyline
        className="art-line"
        points="20,150 75,118 130,128 185,88 240,100 285,42"
      />
      <rect className="art-bar" x="196" y="118" width="16" height="32" rx="4" />
      <rect className="art-bar" x="222" y="100" width="16" height="50" rx="4" />
      <rect className="art-bar" x="248" y="82" width="16" height="68" rx="4" />
      <g className="art-cap">
        <polygon points="196,44 226,34 256,44 226,54" />
        <path d="M206 52 h40 v8 h-40 z" />
        <line x1="244" y1="58" x2="256" y2="66" />
        <circle cx="258" cy="68" r="3" />
      </g>
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
      <circle className="art-node" cx="75" cy="118" r="4" />
      <circle className="art-node" cx="185" cy="88" r="4" />
      <circle className="art-node" cx="285" cy="42" r="4" />
      <circle className="art-dot" cx="40" cy="90" r="2" />
      <circle className="art-dot" cx="160" cy="150" r="2" />
      <circle className="art-dot" cx="252" cy="140" r="2" />
      <circle className="art-dot" cx="216" cy="60" r="2" />
      <path className="art-sparkle" d="M96 40 l1.6 4.4 4.4 1.6 -4.4 1.6 -1.6 4.4 -1.6 -4.4 -4.4 -1.6 4.4 -1.6 Z" />
      <path className="art-sparkle" d="M268 20 l1.4 3.6 3.6 1.4 -3.6 1.4 -1.4 3.6 -1.4 -3.6 -3.6 -1.4 3.6 -1.4 Z" />
      <path className="art-sparkle" d="M46 130 l1.1 3 3 1.1 -3 1.1 -1.1 3 -1.1 -3 -3 -1.1 3 -1.1 Z" />
      <path className="art-sparkle" d="M212 150 l1 2.8 2.8 1 -2.8 1 -1 2.8 -1 -2.8 -2.8 -1 2.8 -1 Z" />
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/* Trend chart: real prediction history only. Empty -> no chart.       */
/* ------------------------------------------------------------------ */

function TrendChart({ history }) {
  const width = 340;
  const height = 150;
  const padX = 26;
  const padY = 18;

  const points = (Array.isArray(history) ? history : [])
    .map((entry) => ({
      probability: pctOrNull(entry?.placement_probability),
      label: formatDate(entry?.timestamp),
    }))
    .filter((point) => point.probability !== null)
    .slice(-6);

  if (points.length === 0) {
    return (
      <p className="skills-empty dashboard-empty-state">
        Prediction trend will appear after you make predictions.
      </p>
    );
  }

  const values = points.map((p) => p.probability);
  const minV = Math.min(...values) - 5;
  const maxV = Math.max(...values) + 5;

  const x = (i) =>
    padX + (i * (width - padX * 2)) / Math.max(points.length - 1, 1);
  const y = (v) =>
    height - padY - ((v - minV) / (maxV - minV)) * (height - padY * 2);

  const linePoints = points.map((p, i) => `${x(i)},${y(p.probability)}`).join(" ");
  const areaPoints = `${padX},${height - padY} ${linePoints} ${
    width - padX
  },${height - padY}`;

  return (
    <svg
      className="trend-chart"
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label="Placement probability trend across your predictions"
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

      <line
        x1={padX}
        y1={height - padY}
        x2={width - padX}
        y2={height - padY}
        className="chart-grid-line"
      />

      <polygon points={areaPoints} fill="url(#trendArea)" />
      <polyline points={linePoints} className="chart-line" fill="none" />

      {points.map((point, i) => (
        <g key={`${point.label}-${i}`}>
          <circle cx={x(i)} cy={y(point.probability)} r="4" className="chart-dot" />
          <text x={x(i)} y={height - 5} textAnchor="middle" className="chart-label">
            {point.label}
          </text>
          <text
            x={x(i)}
            y={y(point.probability) - 9}
            textAnchor="middle"
            className="chart-value"
          >
            {point.probability}%
          </text>
        </g>
      ))}
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/* Small building blocks                                               */
/* ------------------------------------------------------------------ */

function LoadingCard() {
  return (
    <div className="dash-card">
      <div className="dash-card-header">
        <IconMark name="overview" className="dash-card-icon blue" />
        <h2>Loading dashboard…</h2>
      </div>
      <p className="skills-empty">
        Fetching your real profile, readiness and assessment data.
      </p>
    </div>
  );
}

function ErrorState({ message, onRetry }) {
  return (
    <div className="dash-card">
      <div className="dash-card-header">
        <IconMark name="improve" className="dash-card-icon orange" />
        <h2>Dashboard unavailable</h2>
      </div>
      <div className="error-banner" role="alert">
        {message}
      </div>
      <button type="button" className="dash-btn secondary" onClick={onRetry}>
        Retry
      </button>
    </div>
  );
}

function Dashboard({ onNavigate }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchAll = () =>
    Promise.all([
      fetchStudentProfile(DEMO_PROFILE_ID),
      fetchPlacementSummary(DEMO_PROFILE_ID),
      fetchPerformance(DEMO_PROFILE_ID),
      fetchCompanyRecommendations(DEMO_PROFILE_ID, 3),
    ]);

  /* Codebase convention: .then/.catch with state updates ONLY in async
     callbacks — the effect body never calls setState synchronously.
     Initial state is already loading=true. */
  useEffect(() => {
    let active = true;

    fetchAll()
      .then(([profileRes, placementSummary, performance, recommendations]) => {
        if (!active) return;
        setData({ profileRes, placementSummary, performance, recommendations });
        setError(null);
        setLoading(false);
      })
      .catch((err) => {
        if (!active) return;
        setError(
          err?.message ?? "Unable to load the dashboard. Please try again."
        );
        setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  const handleRetry = () => {
    setLoading(true);
    setError(null);

    fetchAll()
      .then(([profileRes, placementSummary, performance, recommendations]) => {
        setData({ profileRes, placementSummary, performance, recommendations });
        setError(null);
        setLoading(false);
      })
      .catch((err) => {
        setError(
          err?.message ?? "Unable to load the dashboard. Please try again."
        );
        setLoading(false);
      });
  };

  const userName = readProfileName() ?? "Student";

  if (loading) {
    return (
      <div className="dashboard">
        <div className="dashboard-welcome">
          <div className="welcome-content">
            <h1>Welcome back, {userName}! 👋</h1>
            <p>Track your placement readiness and get AI-powered insights.</p>
            <span className="welcome-badge">AI-Powered Intelligence</span>
          </div>
          <WelcomeArt />
        </div>
        <LoadingCard />
      </div>
    );
  }

  if (error) {
    return (
      <div className="dashboard">
        <div className="dashboard-welcome">
          <div className="welcome-content">
            <h1>Welcome back, {userName}! 👋</h1>
            <p>Track your placement readiness and get AI-powered insights.</p>
            <span className="welcome-badge">AI-Powered Intelligence</span>
          </div>
          <WelcomeArt />
        </div>
        <ErrorState message={error} onRetry={handleRetry} />
      </div>
    );
  }

  const backendProfile = data.profileRes?.profile ?? {};
  const completion = data.profileRes?.completion ?? {};
  const readiness = data.performance?.readiness ?? {};
  /* Live backend nests summary under `predictions` and `assessments`.
     Support both the nested shape and a flat shape defensively. */
  const rawSummary = data.performance?.summary ?? {};
  const summary = {
    ...(rawSummary.predictions ?? {}),
    ...(rawSummary.assessments ?? {}),
    ...rawSummary,
  };
  const predictionHistory = data.performance?.prediction_history ?? [];
  const assessmentHistory = data.performance?.assessment_history ?? [];

  const profileName =
    typeof backendProfile.personal?.name === "string" &&
    backendProfile.personal.name.length > 0
      ? backendProfile.personal.name
      : userName;

  const predictionProbability = pctOrNull(
    data.placementSummary?.placement_probability
  );
  const predictionLabel = data.placementSummary?.prediction;
  const predictionConfidence = pctOrNull(data.placementSummary?.confidence);
  const modelVersion = data.placementSummary?.model_version;
  const readyForPrediction = Boolean(data.placementSummary?.ready_for_prediction);

  const readinessScore = pctValue(readiness.readiness_score);
  const readinessLevel = readiness.readiness_level ?? null;
  const strengths = Array.isArray(readiness.strengths) ? readiness.strengths : [];
  const skillGaps = Array.isArray(readiness.skill_gaps) ? readiness.skill_gaps : [];

  const completionPercentage = pctValue(
    completion?.percentage ?? readiness.profile_completeness?.percentage
  );

  const assessmentsCount = Number.isFinite(Number(summary.assessments_count))
    ? Number(summary.assessments_count)
    : null;
  const skillsAssessed = Number.isFinite(Number(summary.skills_assessed))
    ? Number(summary.skills_assessed)
    : null;
  const averageScore = pctValue(summary.average_score);

  const skillsTracked = Number.isFinite(Number(summary.skills_tracked))
    ? Number(summary.skills_tracked)
    : null;

  const recommendedCompanies = [
    ...(Array.isArray(data.recommendations?.recommendations?.recommended)
      ? data.recommendations.recommendations.recommended
      : []),
    ...(Array.isArray(data.recommendations?.recommendations?.eligible)
      ? data.recommendations.recommendations.eligible
      : []),
  ].slice(0, 3);

  const strengthNames = strengths
    .map((entry) => entry?.skill)
    .filter((skill) => typeof skill === "string" && skill.length > 0);

  const gapEntries = skillGaps
    .map((entry) => ({
      skill: entry?.skill,
      priority: typeof entry?.priority === "string" ? entry.priority : null,
      reason: typeof entry?.reason === "string" ? entry.reason : null,
    }))
    .filter((entry) => typeof entry.skill === "string" && entry.skill.length > 0);

  const donutPercent = readinessScore ?? 0;
  const predictionDisplay =
    predictionLabel === "PLACED" ? "LIKELY PLACED" : "PLACEMENT RISK";

  return (
    <div className="dashboard">
      <div className="dashboard-welcome">
        <div className="welcome-content">
          <h1>Welcome back, {profileName}! 👋</h1>
          <p>Track your placement readiness and get AI-powered insights.</p>
          <span className="welcome-badge">AI-Powered Intelligence</span>
        </div>
        <WelcomeArt />
      </div>

      <div className="stats-grid">
        <StatsCard
          title="Readiness Score"
          value={readinessScore === null ? "Not available" : `${readinessScore}%`}
          description={readinessLevel ?? "Backend readiness analysis"}
          icon="placement"
          accent="green"
        />
        <StatsCard
          title="Placement Prediction"
          value={
            predictionProbability === null
              ? "No prediction yet"
              : `${predictionProbability}%`
          }
          description={
            predictionProbability === null
              ? readyForPrediction
                ? "Run your first prediction"
                : "Complete your profile to enable prediction"
              : predictionDisplay
          }
          icon="prediction"
          accent="blue"
          chip={predictionProbability === null ? null : "REAL DATA"}
        />
        <StatsCard
          title="Profile Completion"
          value={
            completionPercentage === null ? "Not available" : `${completionPercentage}%`
          }
          description="Verified profile completeness"
          icon="profile"
          accent="purple"
        />
        <StatsCard
          title="Assessments Taken"
          value={assessmentsCount === null ? "Not available" : String(assessmentsCount)}
          description={
            averageScore === null
              ? "Take a mock test to see scores"
              : `Avg score ${averageScore}% across ${skillsAssessed ?? "—"} skills${
                  skillsTracked !== null ? `, ${skillsTracked} tracked` : ""
                }`
          }
          icon="mocktest"
          accent="orange"
        />
      </div>

      <div className="dashboard-grid">
        <div className="dash-card">
          <div className="dash-card-header">
            <IconMark name="overview" className="dash-card-icon blue" />
            <h2>Readiness Overview</h2>
          </div>

          <div className="overview-body">
            <div
              className="donut"
              style={{
                background: `conic-gradient(#2563eb 0deg, #7c3aed ${
                  donutPercent * 3.6
                }deg, #eef2ff ${donutPercent * 3.6}deg 360deg)`,
              }}
            >
              <div className="donut-center">
                <span className="donut-value">
                  {readinessScore === null ? "—" : `${readinessScore}%`}
                </span>
                <span className="donut-label">Readiness</span>
              </div>
            </div>

            <div className="overview-legend">
              <div className="legend-row">
                <span className="legend-dot placed"></span>
                <span>Readiness level</span>
                <strong>{readinessLevel ?? "Not available"}</strong>
              </div>
              <div className="legend-row">
                <span className="legend-dot not-placed"></span>
                <span>Profile completion</span>
                <strong>
                  {completionPercentage === null ? "—" : `${completionPercentage}%`}
                </strong>
              </div>
              {modelVersion && (
                <div className="legend-row">
                  <span className="legend-dot placed"></span>
                  <span>Model</span>
                  <strong>{modelVersion}</strong>
                </div>
              )}
              {predictionConfidence !== null && (
                <div className="legend-row">
                  <span className="legend-dot not-placed"></span>
                  <span>Prediction confidence</span>
                  <strong>{predictionConfidence}%</strong>
                </div>
              )}
            </div>
          </div>

          <p className="dash-card-note">
            Rule-based readiness from your verified profile — not an ML accuracy value.
          </p>
        </div>

        <div className="dash-card">
          <div className="dash-card-header">
            <IconMark name="trend" className="dash-card-icon purple" />
            <h2>Prediction Trend</h2>
          </div>

          <TrendChart history={predictionHistory} />

          <p className="dash-card-note">
            {predictionHistory.length > 0
              ? "Each point is one real backend prediction."
              : "No predictions recorded yet — the chart is intentionally empty."}
          </p>
        </div>
      </div>

      <div className="dashboard-grid">
        <div className="dash-card">
          <div className="dash-card-header">
            <IconMark name="strengths" className="dash-card-icon green" />
            <h2>Top Strength Areas</h2>
          </div>

          {strengthNames.length > 0 ? (
            <div className="skill-chip-row">
              {strengthNames.slice(0, 6).map((skill) => (
                <SkillChip key={skill} skill={skill} variant="matched" />
              ))}
            </div>
            ) : (
            <p className="skills-empty">No strengths reported yet.</p>
          )}

          <p className="dash-card-note">From the backend readiness analysis.</p>
        </div>

        <div className="dash-card">
          <div className="dash-card-header">
            <IconMark name="improve" className="dash-card-icon orange" />
            <h2>Areas to Improve</h2>
          </div>

          {gapEntries.length > 0 ? (
            <ul className="dashboard-gap-list">
              {gapEntries.slice(0, 4).map((entry) => (
                <li key={entry.skill}>
                  <strong>{entry.skill}</strong>
                  {entry.priority && (
                    <span className="dashboard-priority-chip">{entry.priority}</span>
                  )}
                  {entry.reason && <p>{entry.reason}</p>}
                </li>
              ))}
            </ul>
          ) : (
            <p className="skills-empty">No skill gaps reported yet.</p>
          )}

          <p className="dash-card-note">From the backend readiness analysis.</p>
        </div>
      </div>

      <div className="dashboard-grid">
        <div className="dash-card">
          <div className="dash-card-header">
            <IconMark name="mocktest" className="dash-card-icon blue" />
            <h2>Recent Assessments</h2>
          </div>

          {assessmentHistory.length > 0 ? (
            <ul className="dashboard-assessment-list">
              {assessmentHistory.slice(-3).reverse().map((entry) => {
                const score = pctValue(entry?.score);
                return (
                  <li key={entry?.assessment_id ?? `${entry?.skill}-${entry?.timestamp}`}>
                    <strong>{entry?.skill ?? "Unknown skill"}</strong>
                    <span className="dashboard-priority-chip">
                      {entry?.level ?? "Level not available"}
                    </span>
                    <span className="skills-empty">
                      {score === null ? "Score not available" : `Score ${score}%`}
                      {entry?.timestamp ? ` · ${formatDate(entry.timestamp)}` : ""}
                    </span>
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="skills-empty">
              No assessments yet — take a mock test to see real results here.
            </p>
          )}

          <p className="dash-card-note">Verified backend assessment evidence.</p>
        </div>

        <div className="dash-card">
          <div className="dash-card-header">
            <IconMark name="company" className="dash-card-icon purple" />
            <h2>Top Recommended Companies</h2>
          </div>

          {recommendedCompanies.length > 0 ? (
            <ul className="dashboard-assessment-list">
              {recommendedCompanies.map((item) => {
                const score = pctValue(item?.recommendation_score);
                return (
                  <li key={item?.company_id ?? item?.company_name}>
                    <strong>{item?.company_name ?? "Unknown company"}</strong>
                    <span className="dashboard-priority-chip">
                      {item?.eligibility_status ?? "Status not available"}
                    </span>
                    <span className="skills-empty">
                      {score === null
                        ? "Score not available"
                        : `Match score ${score}%`}
                    </span>
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="skills-empty">No recommendations available yet.</p>
          )}

          <p className="dash-card-note">
            Company requirements are sample/demo data — not real hiring criteria.
          </p>
        </div>
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
          <strong>Sample company data:</strong> Company requirements shown in
          recommendations are sample data for the eligibility engine — not real
          hiring criteria. All readiness, prediction and assessment values come
          from your verified backend profile.
        </span>
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
          onClick={() => onNavigate("companies")}
        >
          View Recommendations
        </button>
        <button
          type="button"
          className="dash-btn secondary"
          onClick={() => onNavigate("prediction")}
        >
          Run New Prediction
        </button>
      </div>
    </div>
  );
}

export default Dashboard;
