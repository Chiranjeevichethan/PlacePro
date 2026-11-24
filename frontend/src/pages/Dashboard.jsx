import StatsCard from "../components/StatsCard";
import { useEffect, useState } from 'react';
import { usePredictionResult } from '../hooks/usePredictionResult';
import { createRetryIntent } from '../services/retryIntent';
import { saveProfilePrediction } from '../services/ownedProfiles';
import SkillChip from "../components/SkillChip";
import IconMark from "../components/IconMark";
import DashboardSalaryEstimate from '../components/DashboardSalaryEstimate';
import {
  fetchPlacementSummary,
  fetchPerformance,
  fetchCompanyRecommendations,
} from "../services/api";
import { useStudentProfileContext } from "../hooks/useStudentProfileContext";
import { useProfileResource } from '../hooks/useProfileResource';
import { requireSource } from '../services/profileState.js';
import { finiteNumberOrNull, percentOrNull } from '../services/resultDisplay.js';

async function loadDashboard(profileId) {
  const [placementSummary, performance, recommendations] = await Promise.all([
    fetchPlacementSummary(profileId), fetchPerformance(profileId), fetchCompanyRecommendations(profileId, 3),
  ]);
  const source = { profile_id: profileId, revision: performance.source_revision };
  requireSource(placementSummary, source);
  requireSource(recommendations, source);
  return { profile_id: profileId, source_revision: performance.source_revision,
    placementSummary, performance, recommendations };
}

/* ------------------------------------------------------------------ */
/* Defensive readers (backend fields may be missing/null/empty)        */
/* ------------------------------------------------------------------ */

const pctOrNull = (value) => percentOrNull(value, 100);
const pctValue = percentOrNull;

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
    <div
      className="trend-chart-scroll"
      role="region"
      aria-label="Scrollable placement probability trend chart"
      tabIndex={0}
    >
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
    </div>
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
  /* The canonical profile (and its id) comes from the shared context — the
     dashboard never reads the name from localStorage or from a fixed demo
     profile. */
  const { profile,profileId,profileKey,rawProfile,error: profileError,loading: profileLoading } = useStudentProfileContext();
  const [retryIntent] = useState(createRetryIntent);
  const inputs = { profileId, revision: rawProfile?.revision };
  const savedPrediction = usePredictionResult(profileKey,inputs,
    (input) => saveProfilePrediction(input.profileId,input.revision,retryIntent(input)));

  /* Data is tagged with the profile it belongs to: if the student changes
     (e.g. a resume is verified), the previous student's numbers are never
     rendered while the new ones load. */
  const { data, loading, error: pageError, refetch: handleRetry } = useProfileResource(loadDashboard);
  useEffect(() => { if (savedPrediction.result) handleRetry(); },[savedPrediction.result,handleRetry]);

  /* Fallback name only when the profile has no usable name. */
  const userName = profile?.name?.trim() || "Student";

  if (!rawProfile && !profileError && !profileLoading) return <div className="dashboard">
    <div className="dash-card"><h1>Your placement dashboard</h1>
      <p>Create your first profile to see readiness, skill gaps and recommendations here.</p>
      <p>After reviewing your profile, explore model estimates and take a practice assessment to build your performance history.</p>
      <button type="button" className="dash-btn secondary" onClick={() => onNavigate('profile')}>Explore Student Profile</button>
    </div>
  </div>;

  /* Derived states (no setState in the effect body): loading until this
     profile's own data arrives, and the profile error always wins. */
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

  if (pageError) {
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
        <ErrorState message={pageError} onRetry={handleRetry} />
      </div>
    );
  }

  const readiness = data?.performance?.readiness ?? {};
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

  const profileName = userName;

  const rawProbability = finiteNumberOrNull(data.placementSummary?.placement_probability);
  const predictionProbability = rawProbability !== null && rawProbability >= 0 && rawProbability <= 1
    ? pctOrNull(rawProbability) : null;
  const predictionLabel = data.placementSummary?.prediction;
  const predictionConfidence = pctOrNull(data.placementSummary?.confidence);
  const modelVersion = data.placementSummary?.model_version;
  const readyForPrediction = Boolean(data.placementSummary?.ready_for_prediction);

  const readinessScore = pctValue(readiness.readiness_score);
  const readinessLevel = readiness.readiness_level ?? null;
  const strengths = Array.isArray(readiness.strengths) ? readiness.strengths : [];
  const skillGaps = Array.isArray(readiness.skill_gaps) ? readiness.skill_gaps : [];

  const completionPercentage = pctValue(
    readiness.profile_completeness?.percentage
  );

  const assessmentsCount = finiteNumberOrNull(summary.assessments_count);
  const skillsAssessed = finiteNumberOrNull(summary.skills_assessed);
  const averageScore = pctValue(summary.average_score);

  const skillsTracked = finiteNumberOrNull(summary.skills_tracked);

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
  const predictionDisplay = predictionLabel === "PLACED" ? "LIKELY PLACED"
    : predictionLabel === "NOT PLACED" ? "PLACEMENT RISK" : "Prediction label unavailable";

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
          chip={predictionProbability === null ? null : "MODEL ESTIMATE"}
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

      <div className="dashboard-grid dashboard-estimates">
        <section className="dash-card dashboard-estimate-card" aria-labelledby="dashboard-probability-title">
          <div className="dash-card-header">
            <IconMark name="prediction" className="dash-card-icon blue" />
            <h2 id="dashboard-probability-title">Placement Probability</h2>
            <span className="dashboard-model-chip">MODEL ESTIMATE</span>
          </div>
          {predictionProbability === null ? <>
            <p className="dashboard-estimate-empty">Placement estimate unavailable.</p>
            <p className="dashboard-estimate-inputs">
              {readyForPrediction ? 'Run a placement prediction to view a model estimate.'
                : 'Complete and confirm your profile inputs to enable a placement estimate.'}
            </p>
          </> : <>
            <p className="dashboard-estimate-value">{predictionProbability}%</p>
            <p className="dashboard-estimate-caption">{predictionDisplay}</p>
            <div className="dashboard-probability-meter" role="meter"
              aria-labelledby="dashboard-probability-title" aria-describedby="dashboard-probability-note"
              aria-valuemin={0} aria-valuemax={100} aria-valuenow={predictionProbability}
              aria-valuetext={`${predictionProbability}% estimated placement probability`}>
              <span aria-hidden="true" style={{ width: `${predictionProbability}%` }} />
            </div>
            <div className="dashboard-meter-scale" aria-hidden="true"><span>0%</span><span>100%</span></div>
          </>}
          <p className="dashboard-estimate-qualification" id="dashboard-probability-note">
            A model estimate from your profile, not a measured placement outcome or a guaranteed offer.
          </p>
          <button type="button" className="dashboard-action-link" onClick={() => onNavigate('prediction')}>
            Open Placement Prediction <span aria-hidden="true">→</span>
          </button>
          <p className="dashboard-estimate-caption">Save a profile prediction below to add it to your history.</p>
        </section>
        <DashboardSalaryEstimate profile={profile} profileKey={profileKey}
          profileLoading={profileLoading} profileError={profileError} onNavigate={onNavigate} />
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
          <button type="button" className="dashboard-action-link" onClick={() => onNavigate('skillgap')}>
            Explore skill gaps and learning resources <span aria-hidden="true">→</span>
          </button>
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
          <button type="button" className="dashboard-action-link" onClick={() => onNavigate('mocktests')}>
            Take a practice assessment <span aria-hidden="true">→</span>
          </button>
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
          <button type="button" className="dashboard-action-link" onClick={() => onNavigate('companies')}>
            Explore company matches <span aria-hidden="true">→</span>
          </button>
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
        <button type="button" className="dash-btn primary"
          disabled={!readyForPrediction || savedPrediction.busy || Boolean(savedPrediction.result)}
          onClick={() => savedPrediction.run(inputs)}>
          {savedPrediction.busy ? 'Saving prediction…' : savedPrediction.result ? 'Profile prediction saved' : 'Save profile prediction'}
        </button>
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
      {savedPrediction.error && <p className="error-banner" role="alert">{savedPrediction.error}</p>}
    </div>
  );
}

export default Dashboard;
