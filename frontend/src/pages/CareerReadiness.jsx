import { useEffect, useRef } from 'react';
import IconMark from '../components/IconMark';
import { useProfileResource } from '../hooks/useProfileResource';
import { useStudentProfileContext } from '../hooks/useStudentProfileContext';
import { fetchCompanyRecommendations, fetchPerformance } from '../services/api';
import { buildCareerReadinessView } from '../services/careerReadiness.js';
import LearningRoadmap from '../components/LearningRoadmap.jsx';
import GoalManagement from '../components/GoalManagement.jsx';
import { buildLearningRoadmap } from '../services/learningRoadmap.js';
import { studentJourney } from '../services/studentJourney.js';
import { requireSource } from '../services/profileState.js';
import { displayPercentOrNull } from '../services/performanceDisplay.js';

async function loadCareerReadiness(profileId) {
  const [performance, recommendationResult] = await Promise.all([
    fetchPerformance(profileId),
    fetchCompanyRecommendations(profileId, 3).then(
      (recommendations) => ({ recommendations }),
      (error) => {
        if (error?.status === 401 || error?.status === 403) throw error;
        return { error: error?.message || 'Company recommendations are unavailable.' };
      }
    ),
  ]);

  const source = { profile_id: profileId, revision: performance.source_revision };
  if (recommendationResult.recommendations) {
    requireSource(recommendationResult.recommendations, source);
  }

  return {
    profile_id: performance.profile_id,
    source_revision: performance.source_revision,
    performance,
    recommendations: recommendationResult.recommendations ?? null,
    recommendationError: recommendationResult.error ?? null,
  };
}

function PageHeader() {
  return (
    <div className="page-header">
      <h1>Career Readiness</h1>
      <p>Review the preparation evidence in your confirmed profile, choose a next step, and track recorded activity.</p>
    </div>
  );
}

function PageState({ title, message, role = 'status', action }) {
  return (
    <section className="career-state-card" aria-labelledby="career-state-title">
      <h2 id="career-state-title">{title}</h2>
      <p role={role}>{message}</p>
      {action}
    </section>
  );
}

function ProfileReadinessState({ profile, completion, onNavigate, onEditProfile, onCreateProfile }) {
  const next = studentJourney(profile, completion);
  const action = next.stage === 'empty'
    ? onCreateProfile
    : next.stage === 'confirm'
      ? () => onNavigate('profile')
      : onEditProfile;

  return (
    <PageState
      title={next.title}
      message={next.detail}
      action={(
        <>
          {next.missing.length > 0 && <p className="career-missing-fields">Missing: {next.missing.join(', ')}.</p>}
          <button type="button" className="dash-btn primary" onClick={action}>
            {next.action}
          </button>
        </>
      )}
    />
  );
}

function formatRecordedDate(value) {
  if (typeof value !== 'string' || !value) return 'Date not available';
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? 'Date not available'
    : date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

function VerifiedCareerReadiness({ onNavigate, onEditProfile, active, focusGoalManagement, notificationTarget, onNotificationTargetHandled }) {
  const { data, loading, error, refetch } = useProfileResource(loadCareerReadiness);
  const wasActive = useRef(active);

  useEffect(() => {
    const returnedToPage = active && !wasActive.current;
    wasActive.current = active;
    if (returnedToPage) refetch();
  }, [active, refetch]);

  if (loading) {
    return <div className="career-readiness-page"><PageHeader />
      <PageState title="Loading your readiness information" message="Fetching verified readiness, assessment history, and company recommendations." />
    </div>;
  }

  if (error) {
    return <div className="career-readiness-page"><PageHeader />
      <PageState title="Career readiness is unavailable" message={error} role="alert"
        action={<button type="button" className="dash-btn secondary" onClick={refetch}>Retry</button>} />
    </div>;
  }

  const view = buildCareerReadinessView(data?.performance, data?.recommendations);
  if (!view) {
    return <div className="career-readiness-page"><PageHeader />
      <PageState title="Readiness information is incomplete" message="The performance service did not return a verified readiness record. No score or progress value has been substituted."
        role="alert" action={<button type="button" className="dash-btn secondary" onClick={refetch}>Retry</button>} />
    </div>;
  }

  const latestAssessmentScore = displayPercentOrNull(view.assessments.latest?.score);
  const latestPrediction = view.prediction;
  const profileCompletion = view.profileCompleteness;
  const gapCount = view.skillGaps?.length ?? null;
  const roadmap = buildLearningRoadmap(view);

  return (
    <div className="career-readiness-page">
      <PageHeader />

      <section className="career-readiness-hero" aria-labelledby="career-overview-title">
        <div className="career-score-block">
          <span className="career-eyebrow">CURRENT PREPARATION</span>
          <h2 id="career-overview-title">{view.readinessLevel || 'Readiness level unavailable'}</h2>
          <div className="career-score-row">
            <strong>{view.readinessScore === null ? 'Not available' : `${view.readinessScore}%`}</strong>
            {view.readinessScore !== null && (
              <div className="career-score-meter" role="meter" aria-label="Rule-based career readiness"
                aria-valuemin={0} aria-valuemax={100} aria-valuenow={view.readinessScore}
                aria-valuetext={`${view.readinessScore}% rule-based readiness`}>
                <span style={{ width: `${view.readinessScore}%` }} />
              </div>
            )}
          </div>
          <p>This is the backend’s rule-based preparation score. It is separate from placement probability and is not an accuracy or hiring outcome.</p>
        </div>

        <div className="career-completion-block">
          <span className="career-eyebrow">PROFILE COMPLETENESS</span>
          <strong>{profileCompletion.percentage === null ? 'Not available' : `${profileCompletion.percentage}%`}</strong>
          {profileCompletion.percentage !== null && (
            <div className="career-completion-meter" role="progressbar" aria-label="Verified profile completeness"
              aria-valuemin={0} aria-valuemax={100} aria-valuenow={profileCompletion.percentage}>
              <span style={{ width: `${profileCompletion.percentage}%` }} />
            </div>
          )}
          {profileCompletion.missingFields?.length > 0
            ? <p>{profileCompletion.missingFields.length} profile section{profileCompletion.missingFields.length === 1 ? '' : 's'} to review.</p>
            : <p>{profileCompletion.missingFields === null ? 'Missing-section details are not available.' : 'No missing sections were reported.'}</p>}
          <button type="button" className="dashboard-action-link" onClick={onEditProfile}>Review profile <span aria-hidden="true">→</span></button>
        </div>
      </section>

      <section className="career-readiness-section career-planner-section" aria-labelledby="career-actions-title">
        <div className="career-section-heading">
          <div><span className="career-eyebrow">TODAY'S FOCUS · FROM YOUR CURRENT EVIDENCE</span><h2 id="career-actions-title">Personalized action plan</h2></div>
          <button type="button" className="dashboard-action-link" onClick={() => onNavigate('skillgap')}>Open Skill Gap Analysis <span aria-hidden="true">→</span></button>
        </div>
        <p className="career-planner-intro">Actions are ordered from profile completeness, backend skill-gap priority, and recorded assessment evidence. There are no artificial scores, deadlines, or streaks.</p>
        <p className="career-plan-summary" role="status">{view.actions.length === 0
          ? 'No open actions are supported by the current response.'
          : `${view.actions.length} open action${view.actions.length === 1 ? '' : 's'} from your current verified information.`}</p>

        {view.actions.length > 0 ? (
          <ol className="career-action-list">
            {view.actions.map((item, index) => (
              <li className={`career-action-card ${index === 0 ? 'career-action-card-focus' : ''}`} key={item.id}>
                <span className={`career-priority-badge ${item.priority === 'Priority unavailable' ? 'unranked' : item.priority.toLowerCase()}`}>
                  {item.priority}
                </span>
                <div className="career-action-copy">
                  {item.skill && <span className="career-action-skill">{item.skill}</span>}
                  <h3>{item.title}</h3>
                  <p>{item.description}</p>
                  <p className="career-action-rationale"><strong>Why this is here:</strong> {item.rationale}</p>
                  <p className="career-action-follow-up"><strong>After this:</strong> {item.followUp}</p>
                </div>
                <button type="button" className="dash-btn secondary" aria-label={item.cta} onClick={() => {
                  if (item.destination === 'edit-profile') onEditProfile();
                  else onNavigate(item.destination);
                }}>{item.cta}</button>
              </li>
            ))}
          </ol>
        ) : (
          <p className="career-empty-note" role="status">The current readiness analysis returned no specific improvement actions. You can still practise, review your performance, or explore company recommendations below.</p>
        )}
        <p className="career-data-note">Action completion is not checked off when you open a page. Items update only when the existing profile, readiness, assessment, or prediction records support a change.</p>
      </section>

      <LearningRoadmap view={view} roadmap={roadmap} onNavigate={onNavigate} onEditProfile={onEditProfile} />
      <GoalManagement profileId={data.profile_id} actions={view.actions} roadmap={roadmap} active={active} focusOnHash={focusGoalManagement} onNavigate={onNavigate}
        focusTarget={notificationTarget} onFocusTargetHandled={onNotificationTargetHandled} />

      <section className="career-readiness-section" aria-labelledby="career-recorded-title">
        <div className="career-section-heading">
          <div><span className="career-eyebrow">SERVER-RECORDED EVIDENCE</span><h2 id="career-recorded-title">Progress on record</h2></div>
          <button type="button" className="dashboard-action-link" onClick={() => onNavigate('performance')}>Open Performance Analysis <span aria-hidden="true">→</span></button>
        </div>
        {view.recordedActivity.length > 0 ? (
          <ul className="career-recorded-list">
            {view.recordedActivity.map((activity) => (
              <li key={activity.id}>
                <span className="career-recorded-type">{activity.kind}</span>
                <div><strong>{activity.title}</strong><p>{activity.detail}</p></div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="career-empty-note" role="status">There are no completed assessment, profile-completeness, or saved-estimate records to show yet. Completing a supported action in its existing PLACE PRO module will update this list when the data is recorded.</p>
        )}
      </section>

      <section className="career-progress-grid" aria-label="Recorded preparation activity">
        <article className="career-progress-card">
          <div className="career-card-heading"><IconMark name="mocktest" className="dash-card-icon blue" /><h2>Assessment activity</h2></div>
          <strong className="career-progress-value">{view.assessments.count === null ? 'Not available' : view.assessments.count}</strong>
          <p>{view.assessments.averageScore === null ? 'Average score not available' : `Recorded average ${view.assessments.averageScore}%`}</p>
          {view.assessments.latest && <p className="career-data-note">Latest: {view.assessments.latest.skill || 'Skill unavailable'}{latestAssessmentScore === null ? '' : ` · ${latestAssessmentScore}%`} · {formatRecordedDate(view.assessments.latest.timestamp)}</p>}
          {!view.hasAssessmentHistory && <p className="career-data-note">No completed assessment records yet.</p>}
          <button type="button" className="dashboard-action-link" onClick={() => onNavigate('mocktests')}>{view.hasAssessmentHistory ? 'Continue practice' : 'Take your first practice assessment'} <span aria-hidden="true">→</span></button>
        </article>

        <article className="career-progress-card">
          <div className="career-card-heading"><IconMark name="performance" className="dash-card-icon purple" /><h2>Placement estimate</h2></div>
          {latestPrediction.probability === null
            ? <strong className="career-progress-value">No saved estimate</strong>
            : <strong className="career-progress-value">{latestPrediction.probability}%</strong>}
          <p>{latestPrediction.label ? `Latest model label: ${latestPrediction.label}` : 'No prediction label is available.'}</p>
          {latestPrediction.current === false
            ? <p className="career-data-note">This saved estimate used an earlier profile revision.</p>
            : latestPrediction.current === null && view.hasPredictionHistory
              ? <p className="career-data-note">The profile revision used for this estimate is not available.</p>
              : view.hasPredictionHistory
                ? <p className="career-data-note">This is a saved model estimate, not a measured placement outcome.</p>
                : <p className="career-data-note">Placement estimates remain separate from readiness scores.</p>}
          <button type="button" className="dashboard-action-link" onClick={() => onNavigate('prediction')}>{view.hasPredictionHistory ? 'Open Placement Prediction' : 'Run a placement estimate'} <span aria-hidden="true">→</span></button>
        </article>

        <article className="career-progress-card">
          <div className="career-card-heading"><IconMark name="skills" className="dash-card-icon green" /><h2>Skills on record</h2></div>
          <strong className="career-progress-value">{view.skillsTracked === null ? 'Not available' : view.skillsTracked}</strong>
          <p>{gapCount === null ? 'Skill-gap data not available' : `${gapCount} skill gap${gapCount === 1 ? '' : 's'} reported`}</p>
          {view.skillNames.length > 0
            ? <ul className="career-skill-list">{view.skillNames.slice(0, 5).map((skill) => <li key={skill}>{skill}</li>)}</ul>
            : <p className="career-data-note">No skill names were returned in the current profile evidence.</p>}
          <button type="button" className="dashboard-action-link" onClick={() => onNavigate('skillgap')}>Review skills and resources <span aria-hidden="true">→</span></button>
        </article>
      </section>

      <section className="career-readiness-section" aria-labelledby="career-companies-title">
        <div className="career-section-heading">
          <div><span className="career-eyebrow">EXISTING RECOMMENDATIONS</span><h2 id="career-companies-title">Companies to explore</h2></div>
          <button type="button" className="dashboard-action-link" onClick={() => onNavigate('companies')}>View company recommendations <span aria-hidden="true">→</span></button>
        </div>
        {data?.recommendationError && <p className="career-empty-note" role="status">Company recommendations are unavailable right now. Readiness and activity above are still available. {data.recommendationError}</p>}
        {!data?.recommendationError && view.companies.length > 0 ? (
          <ul className="career-company-list">
            {view.companies.map((company) => <li key={company.id}><strong>{company.name}</strong><span>{company.eligibility || 'Recommendation status unavailable'}</span></li>)}
          </ul>
        ) : !data?.recommendationError ? (
          <p className="career-empty-note" role="status">No company recommendations were returned for this profile.</p>
        ) : null}
        <p className="career-data-note">Company suggestions reflect the current recommendation service response and do not guarantee hiring or eligibility.</p>
      </section>

      <div className="career-footer-actions">
        <p>Assessment and prediction history are recorded by PLACE PRO. No skill-progress trend is inferred when historical snapshots are unavailable.</p>
        <button type="button" className="dash-btn primary" onClick={() => onNavigate('performance')}>Review detailed performance</button>
      </div>
    </div>
  );
}

export default function CareerReadiness({ onNavigate, onEditProfile, onCreateProfile, active = true, focusGoalManagement = false,
  notificationTarget, onNotificationTargetHandled }) {
  const { profile, rawProfile, completion, loading, error } = useStudentProfileContext();

  if (loading) return <div className="career-readiness-page"><PageHeader /><PageState title="Loading student profile" message="Fetching the selected profile before showing readiness information." /></div>;
  if (error) return <div className="career-readiness-page"><PageHeader /><PageState title="Student profile unavailable" message={error} role="alert" /></div>;
  if (!rawProfile || rawProfile.verified !== true) {
    return <div className="career-readiness-page"><PageHeader />
      <ProfileReadinessState profile={rawProfile ? { ...profile, verified: rawProfile.verified } : null}
        completion={completion} onNavigate={onNavigate} onEditProfile={onEditProfile} onCreateProfile={onCreateProfile} />
    </div>;
  }

  return <VerifiedCareerReadiness onNavigate={onNavigate} onEditProfile={onEditProfile} active={active} focusGoalManagement={focusGoalManagement}
    notificationTarget={notificationTarget} onNotificationTargetHandled={onNotificationTargetHandled} />;
}
