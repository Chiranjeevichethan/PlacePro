import { useEffect, useState } from "react";
import IconMark from "../components/IconMark";
import SkillChip from "../components/SkillChip";
import { fetchPerformance, fetchStudentProfile } from "../services/api";
import {
  DEMO_PROFILE_ID,
  flattenBackendProfile,
} from "../services/profileConfig";

/* ------------------------------------------------------------------ */
/* Defensive readers (backend fields may be missing/null/empty).       */
/* ------------------------------------------------------------------ */

/** 0-1 probability -> rounded percentage for display only. Null-safe. */
const probToPercent = (value) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Math.round(parsed * 100) : null;
};

/** Already-percentage value -> rounded, null-safe. */
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

const asArray = (value) => (Array.isArray(value) ? value : []);

/* Backend breakdown component keys -> readable labels. Only these six
   components exist in the backend schema; nothing else is invented. */
const BREAKDOWN_LABELS = {
  technical_skills: "Technical Skills",
  projects: "Projects",
  internships: "Internships",
  certifications: "Certifications",
  communication: "Communication",
  profile_completeness: "Profile Completeness",
};

/* ------------------------------------------------------------------ */
/* Charts: real history only. 0 points -> empty state, 1 point ->      */
/* single real dot, multiple -> real line. No points are fabricated.   */
/* ------------------------------------------------------------------ */

function HistoryChart({ points, ariaLabel, unit = "%" }) {
  const width = 340;
  const height = 150;
  const padX = 26;
  const padY = 18;

  if (points.length === 0) {
    return null;
  }

  const values = points.map((p) => p.value);
  const minV = Math.min(...values) - 5;
  const maxV = Math.max(...values) + 5;

  const x = (i) =>
    padX + (i * (width - padX * 2)) / Math.max(points.length - 1, 1);
  const y = (v) =>
    height - padY - ((v - minV) / (maxV - minV)) * (height - padY * 2);

  const linePoints = points.map((p, i) => `${x(i)},${y(p.value)}`).join(" ");

  return (
    <svg
      className="trend-chart"
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={ariaLabel}
    >
      <defs>
        <linearGradient id="analysisTrendArea" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#2563eb" stopOpacity="0.28" />
          <stop offset="100%" stopColor="#7c3aed" stopOpacity="0" />
        </linearGradient>
      </defs>

      <line
        x1={padX}
        y1={height - padY}
        x2={width - padX}
        y2={height - padY}
        className="chart-grid-line"
      />

      {points.length > 1 && (
        <>
          <polygon
            points={`${padX},${height - padY} ${linePoints} ${width - padX},${
              height - padY
            }`}
            fill="url(#analysisTrendArea)"
          />
          <polyline points={linePoints} className="chart-line" fill="none" />
        </>
      )}

      {points.map((point, i) => (
        <g key={`${point.label}-${i}`}>
          <circle cx={x(i)} cy={y(point.value)} r="4" className="chart-dot" />
          <text x={x(i)} y={height - 5} textAnchor="middle" className="chart-label">
            {point.label}
          </text>
          <text
            x={x(i)}
            y={y(point.value) - 9}
            textAnchor="middle"
            className="chart-value"
          >
            {point.value}
            {unit}
          </text>
        </g>
      ))}
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/* Small building blocks                                               */
/* ------------------------------------------------------------------ */

function LoadingState() {
  return (
    <div className="analysis-card">
      <h2>Loading performance analysis…</h2>
      <p className="skills-empty">
        Fetching your real readiness, prediction and assessment data.
      </p>
    </div>
  );
}

function ErrorState({ message, onRetry }) {
  return (
    <div className="analysis-card">
      <h2>Performance Analysis unavailable</h2>
      <div className="error-banner" role="alert">
        {message}
      </div>
      <button type="button" className="dash-btn secondary" onClick={onRetry}>
        Retry
      </button>
    </div>
  );
}

/* ------------------------------------------------------------------ */

function PerformanceAnalysis() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  /* Performance covers readiness + histories + skills. The profile is
     fetched once for the real activity counts (internships/projects/
     certifications/hackathons/backlogs), which the performance response
     does not contain (its breakdown values are points, not counts). */
  const fetchAll = () =>
    Promise.all([
      fetchPerformance(DEMO_PROFILE_ID),
      fetchStudentProfile(DEMO_PROFILE_ID),
    ]);

  useEffect(() => {
    let active = true;

    fetchAll()
      .then(([performance, profileRes]) => {
        if (!active) return;
        setData({ performance, profileRes });
        setError(null);
        setLoading(false);
      })
      .catch((err) => {
        if (!active) return;
        setError(
          err?.message ?? "Unable to load performance data. Please try again."
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
      .then(([performance, profileRes]) => {
        setData({ performance, profileRes });
        setError(null);
        setLoading(false);
      })
      .catch((err) => {
        setError(
          err?.message ?? "Unable to load performance data. Please try again."
        );
        setLoading(false);
      });
  };

  if (loading) {
    return (
      <div className="analysis-page">
        <div className="page-header">
          <h1>Performance Analysis</h1>
          <p>
            A breakdown of your placement readiness, predictions, and
            assessment performance from the backend.
          </p>
        </div>
        <LoadingState />
      </div>
    );
  }

  if (error) {
    return (
      <div className="analysis-page">
        <div className="page-header">
          <h1>Performance Analysis</h1>
          <p>
            A breakdown of your placement readiness, predictions, and
            assessment performance from the backend.
          </p>
        </div>
        <ErrorState message={error} onRetry={handleRetry} />
      </div>
    );
  }

  const performance = data.performance ?? {};
  const profile = flattenBackendProfile(data.profileRes?.profile);

  /* Live backend nests the summary: summary.predictions / summary.assessments.
     Merged defensively so a flat shape would also work. */
  const rawSummary = performance.summary ?? {};
  const summary = {
    ...(rawSummary.predictions ?? {}),
    ...(rawSummary.assessments ?? {}),
    ...rawSummary,
  };

  const readiness = performance.readiness ?? {};
  const predictionHistory = asArray(performance.prediction_history);
  const assessmentHistory = asArray(performance.assessment_history);
  const skills = asArray(performance.skills);

  const readinessScore = pctValue(readiness.readiness_score);
  const readinessLevel = readiness.readiness_level ?? null;
  const breakdown = readiness.readiness_breakdown ?? {};
  const strengths = asArray(readiness.strengths);
  const skillGaps = asArray(readiness.skill_gaps);
  const improvementPlan = asArray(readiness.improvement_plan);

  /* --- Prediction performance (real values; nulls stay null) --- */
  const predictionsCount = Number.isFinite(Number(summary.predictions_count))
    ? Number(summary.predictions_count)
    : 0;
  const latestProbability = probToPercent(summary.latest_probability);
  const highestProbability = probToPercent(summary.highest_probability);
  const lowestProbability = probToPercent(summary.lowest_probability);
  const latestPredictionTimestamp = formatDate(summary.latest_timestamp);
  const latestModelVersion =
    predictionHistory.length > 0
      ? predictionHistory[predictionHistory.length - 1]?.model_version ?? null
      : null;

  const predictionPoints = predictionHistory
    .map((entry) => ({
      value: probToPercent(entry?.placement_probability),
      label: formatDate(entry?.timestamp),
    }))
    .filter((point) => point.value !== null)
    .slice(-6);

  /* --- Assessment performance (real values; nulls stay null) --- */
  const assessmentsCount = Number.isFinite(Number(summary.assessments_count))
    ? Number(summary.assessments_count)
    : 0;
  const averageScore = pctValue(summary.average_score);
  const skillsAssessed = Number.isFinite(Number(summary.skills_assessed))
    ? Number(summary.skills_assessed)
    : 0;
  const latestSkill = summary.latest_skill ?? null;
  const latestScore = pctValue(summary.latest_score);
  const latestLevel = summary.latest_level ?? null;
  const latestAssessmentTimestamp = formatDate(summary.latest_timestamp);

  const assessmentPoints = assessmentHistory
    .map((entry) => ({
      value: pctValue(entry?.score),
      label: formatDate(entry?.timestamp),
    }))
    .filter((point) => point.value !== null)
    .slice(-6);

  /* --- Skills provenance --- */
  const skillEntries = skills
    .map((entry) => ({
      skill: typeof entry?.skill === "string" ? entry.skill : null,
      resumeDetected: Boolean(entry?.resume_detected),
      userEntered: Boolean(entry?.user_entered),
      assessmentScore: pctValue(entry?.assessment_score),
      assessmentVerified: Boolean(entry?.assessment_verified),
      level: typeof entry?.level === "string" ? entry.level : null,
    }))
    .filter((entry) => entry.skill !== null);

  const activityCards = [
    {
      label: "Internships",
      value: String(profile.internshipsCount),
      note: "From your verified profile",
    },
    {
      label: "Projects",
      value: String(profile.projectsCount),
      note: "From your verified profile",
    },
    {
      label: "Certifications",
      value: String(profile.certificationsCount),
      note: "From your verified profile",
    },
    {
      label: "Hackathons",
      value: String(profile.hackathonsCount),
      note: "From your verified profile",
    },
    {
      label: "Backlogs",
      value:
        profile.backlogs === ""
          ? "Not available"
          : String(profile.backlogs),
      note: "From your verified profile",
    },
  ];

  /* Real ML inputs from the profile, shown at their true scales. */
  const modelInputCards = [
    {
      label: "Aptitude",
      value:
        profile.aptitudeScore === "" ? null : `${profile.aptitudeScore} / 100`,
    },
    {
      label: "Coding Skill",
      value:
        profile.codingSkills === "" ? null : `${profile.codingSkills} / 10`,
    },
    {
      label: "Communication",
      value:
        profile.communicationSkills === ""
          ? null
          : `${profile.communicationSkills} / 10`,
    },
    {
      label: "DSA Score",
      value: profile.dsaScore === "" ? null : `${profile.dsaScore} / 10`,
    },
  ].filter((card) => card.value !== null);

  return (
    <div className="analysis-page">
      <div className="page-header">
        <h1>Performance Analysis</h1>
        <p>
          A breakdown of your placement readiness, predictions, and assessment
          performance from the backend.
        </p>
      </div>

      <div className="analysis-summary">
        <div className="analysis-overall">
          <span className="analysis-overall-label">Placement Readiness</span>
          <span className="analysis-overall-value">
            {readinessScore === null ? "Not available" : readinessScore}
            <small>/100</small>
          </span>
          <span className="analysis-overall-note">
            {readinessLevel ?? "Level not available"}
          </span>
        </div>

        <div className="analysis-summary-note">
          <strong>Rule-based readiness:</strong> this score is a transparent
          backend calculation from your verified profile and assessments — it
          is not an ML accuracy value.
        </div>
      </div>

      {/* Readiness breakdown — backend point components, no new weighting */}
      <div className="analysis-section">
        <h2>
          <IconMark name="performance" className="section-title-icon" />
          <span>Readiness Breakdown</span>
        </h2>

        <div className="bar-list">
          {Object.entries(BREAKDOWN_LABELS).map(([key, label]) => {
            const points = Number.isFinite(Number(breakdown[key]))
              ? Number(breakdown[key])
              : null;
            return (
              <div key={key} className="bar-row-header">
                <span>{label}</span>
                <strong>
                  {points === null ? "Not available" : `${points} pts`}
                </strong>
              </div>
            );
          })}
        </div>
      </div>

      {/* Model inputs — real profile ml_inputs at their true scales */}
      {modelInputCards.length > 0 && (
        <div className="analysis-section">
          <h2>
            <IconMark name="academic" className="section-title-icon" />
            <span>Model Inputs (from your profile)</span>
          </h2>

          <div className="activity-grid">
            {modelInputCards.map((card) => (
              <div key={card.label} className="activity-card">
                <span className="activity-value">{card.value}</span>
                <span className="activity-label">{card.label}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Experience & Activities — real profile counts */}
      <div className="analysis-section">
        <h2>
          <IconMark name="experience" className="section-title-icon" />
          <span>Experience &amp; Activities</span>
        </h2>

        <div className="activity-grid">
          {activityCards.map((item) => (
            <div key={item.label} className="activity-card">
              <span className="activity-value">{item.value}</span>
              <span className="activity-label">{item.label}</span>
              <span className="activity-note">{item.note}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Prediction performance */}
      <div className="analysis-section">
        <h2>
          <IconMark name="prediction" className="section-title-icon" />
          <span>Prediction Performance</span>
        </h2>

        <div className="activity-grid">
          <div className="activity-card">
            <span className="activity-value">{predictionsCount}</span>
            <span className="activity-label">Predictions made</span>
          </div>
          <div className="activity-card">
            <span className="activity-value">
              {latestProbability === null ? "—" : `${latestProbability}%`}
            </span>
            <span className="activity-label">Latest probability</span>
            <span className="activity-note">
              {latestPredictionTimestamp || "No prediction yet"}
            </span>
          </div>
          <div className="activity-card">
            <span className="activity-value">
              {highestProbability === null ? "—" : `${highestProbability}%`}
            </span>
            <span className="activity-label">Highest probability</span>
          </div>
          <div className="activity-card">
            <span className="activity-value">
              {lowestProbability === null ? "—" : `${lowestProbability}%`}
            </span>
            <span className="activity-label">Lowest probability</span>
          </div>
        </div>

        {latestModelVersion && (
          <p className="dash-card-note">
            Model version: <strong>{latestModelVersion}</strong>
          </p>
        )}

        <div className="analysis-card">
          <h3>Prediction history</h3>
          {predictionHistory.length > 0 ? (
            <>
              <HistoryChart
                points={predictionPoints}
                ariaLabel="Placement probability across your predictions"
              />
              {predictionHistory.length === 1 && (
                <p className="skills-empty">
                  One real prediction recorded — the trend line will appear as
                  you make more predictions.
                </p>
              )}
              <ul className="analysis-list">
                {predictionHistory
                  .slice()
                  .reverse()
                  .map((entry, index) => {
                    const probability = probToPercent(
                      entry?.placement_probability
                    );
                    return (
                      <li
                        key={entry?.timestamp ?? `prediction-${index}`}
                      >
                        <strong>
                          {probability === null
                            ? "Probability not available"
                            : `${probability}%`}
                        </strong>
                        <span className="analysis-priority-chip">
                          {entry?.prediction ?? "Unknown result"}
                        </span>
                        <span className="skills-empty">
                          {formatDate(entry?.timestamp) || "Timestamp not available"}
                          {entry?.model_version ? ` · ${entry.model_version}` : ""}
                        </span>
                      </li>
                    );
                  })}
              </ul>
            </>
          ) : (
            <p className="skills-empty">
              Prediction history will appear after you make predictions.
            </p>
          )}
        </div>
      </div>

      {/* Assessment performance */}
      <div className="analysis-section">
        <h2>
          <IconMark name="mocktest" className="section-title-icon" />
          <span>Assessment Performance</span>
        </h2>

        <div className="activity-grid">
          <div className="activity-card">
            <span className="activity-value">{assessmentsCount}</span>
            <span className="activity-label">Assessments taken</span>
          </div>
          <div className="activity-card">
            <span className="activity-value">
              {averageScore === null ? "—" : `${averageScore}%`}
            </span>
            <span className="activity-label">Average score</span>
          </div>
          <div className="activity-card">
            <span className="activity-value">{skillsAssessed}</span>
            <span className="activity-label">Skills assessed</span>
          </div>
          <div className="activity-card">
            <span className="activity-value">
              {latestScore === null ? "—" : `${latestScore}%`}
            </span>
            <span className="activity-label">
              Latest: {latestSkill ?? "No assessment yet"}
            </span>
            <span className="activity-note">
              {latestLevel ? `${latestLevel} · ` : ""}
              {latestAssessmentTimestamp || "No assessment yet"}
            </span>
          </div>
        </div>

        <div className="analysis-card">
          <h3>Recent assessments</h3>
          {assessmentHistory.length > 0 ? (
            <>
              {assessmentPoints.length >= 2 ? (
                <HistoryChart
                  points={assessmentPoints}
                  ariaLabel="Assessment scores over time"
                />
              ) : (
                <p className="skills-empty">
                  A score trend needs at least two assessments — take another
                  mock test to see one.
                </p>
              )}
              <ul className="analysis-list">
                {assessmentHistory
                  .slice()
                  .reverse()
                  .map((entry, index) => {
                    const score = pctValue(entry?.score);
                    return (
                      <li
                        key={
                          entry?.assessment_id ??
                          `${entry?.skill}-${entry?.timestamp}-${index}`
                        }
                      >
                        <strong>{entry?.skill ?? "Unknown skill"}</strong>
                        <span className="analysis-priority-chip">
                          {entry?.level ?? "Level not available"}
                        </span>
                        <span className="skills-empty">
                          {score === null
                            ? "Score not available"
                            : `Score ${score}%`}
                          {Number.isFinite(Number(entry?.attempt))
                            ? ` · attempt ${entry.attempt}`
                            : ""}
                          {entry?.verified ? " · verified" : ""}
                          {entry?.timestamp
                            ? ` · ${formatDate(entry.timestamp)}`
                            : ""}
                        </span>
                      </li>
                    );
                  })}
              </ul>
            </>
          ) : (
            <p className="skills-empty">
              No assessments yet — take a mock test to see real results here.
            </p>
          )}
        </div>
      </div>

      {/* Strengths & skill gaps (split layout preserved) */}
      <div className="analysis-split">
        <div className="analysis-card strengths-card">
          <h2>
            <IconMark name="strengths" className="section-title-icon" />
            <span>Strengths</span>
          </h2>

          {strengths.length > 0 ? (
            <ul>
              {strengths.map((entry, index) => (
                <li key={`${entry?.skill ?? "strength"}-${index}`}>
                  <strong>{entry?.skill ?? "Unknown skill"}</strong>
                  {entry?.category ? ` — ${entry.category}` : ""}
                  {Array.isArray(entry?.evidence) && entry.evidence.length > 0 && (
                    <div className="skills-empty">{entry.evidence.join(" · ")}</div>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p className="skills-empty">No strengths reported yet.</p>
          )}
        </div>

        <div className="analysis-card improvements-card">
          <h2>
            <IconMark name="improve" className="section-title-icon" />
            <span>Skill Gaps</span>
          </h2>

          {skillGaps.length > 0 ? (
            <ul className="analysis-gap-list">
              {skillGaps.map((entry, index) => (
                <li key={entry?.skill ?? `gap-${index}`}>
                  <strong>{entry?.skill ?? "Unknown skill"}</strong>
                  {entry?.priority && (
                    <span className="analysis-priority-chip">
                      {entry.priority}
                    </span>
                  )}
                  {entry?.category && (
                    <div className="skills-empty">{entry.category}</div>
                  )}
                  {entry?.reason && <p>{entry.reason}</p>}
                </li>
              ))}
            </ul>
          ) : (
            <p className="skills-empty">No skill gaps reported yet.</p>
          )}
        </div>
      </div>

      {/* Improvement plan — backend actions */}
      <div className="analysis-section">
        <h2>
          <IconMark name="learning" className="section-title-icon" />
          <span>Improvement Plan</span>
        </h2>

        {improvementPlan.length > 0 ? (
          <ul className="analysis-gap-list">
            {improvementPlan.map((entry, index) => (
              <li key={`${entry?.skill}-${index}`}>
                <strong>{entry?.skill ?? "Unknown skill"}</strong>
                {Number.isFinite(Number(entry?.priority)) && (
                  <span className="analysis-priority-chip">
                    Priority {entry.priority}
                  </span>
                )}
                {entry?.action && <p>{entry.action}</p>}
                {entry?.reason && (
                  <p className="skills-empty">{entry.reason}</p>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p className="skills-empty">
            No improvement plan available yet.
          </p>
        )}
      </div>

      {/* Skills — real combined view with provenance */}
      <div className="analysis-section">
        <h2>
          <IconMark name="skills" className="section-title-icon" />
          <span>Skills</span>
        </h2>

        {skillEntries.length > 0 ? (
          <ul className="analysis-list">
            {skillEntries.map((entry) => (
              <li key={entry.skill}>
                <SkillChip skill={entry.skill} variant="matched" />
                <span className="skills-empty">
                  {entry.resumeDetected ? "from resume" : ""}
                  {entry.resumeDetected && entry.userEntered ? " + " : ""}
                  {entry.userEntered ? "self-added" : ""}
                  {!entry.resumeDetected && !entry.userEntered
                    ? "source not recorded"
                    : ""}
                </span>
                <span className="skills-empty">
                  {entry.assessmentVerified
                    ? `Assessed ${entry.assessmentScore ?? "—"}%${
                        entry.level ? ` · ${entry.level}` : ""
                      }`
                    : "No assessment yet"}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="skills-empty">No skills recorded in your profile yet.</p>
        )}
      </div>
    </div>
  );
}

export default PerformanceAnalysis;
