import { useMemo } from 'react';
import IconMark from './IconMark';
import { usePredictionResult } from '../hooks/usePredictionResult';
import { buildSalaryDraftFromProfile } from '../services/profileConfig.js';
import { predictSalary, formatLpa } from '../services/salaryPrediction';
import { validateDashboardSalaryDraft } from '../services/dashboardSalary.js';

function DashboardSalaryEstimate({ profile, profileKey, profileLoading, profileError, onNavigate }) {
  const draft = useMemo(() => buildSalaryDraftFromProfile(profile), [profile]);
  const issues = validateDashboardSalaryDraft(draft);
  // The controller calls the stable service with submitted values, never a
  // callback closed over the profile from the component's first render.
  const { result, busy, error, run } = usePredictionResult(profileKey, draft, predictSalary);
  const canEstimate = Boolean(profile) && !profileLoading && !profileError && issues.length === 0;

  const handleEstimate = () => {
    if (canEstimate && !busy) run({ ...draft });
  };

  return (
    <section className="dash-card dashboard-estimate-card" aria-labelledby="dashboard-salary-title" aria-busy={busy}>
      <div className="dash-card-header">
        <IconMark name="salary" className="dash-card-icon blue" />
        <h2 id="dashboard-salary-title">Salary Estimate</h2>
        <span className="dashboard-model-chip">MODEL ESTIMATE</span>
      </div>

      <div className="dashboard-salary-status" aria-live="polite" role="status">
        {busy ? <p className="dashboard-estimate-empty">Estimating from your current profile…</p>
          : result ? <>
            <p className="dashboard-estimate-value">{formatLpa(result.predictedSalaryLpa)}</p>
            <p className="dashboard-estimate-caption">Estimated annual salary · lakhs per annum</p>
          </> : <p className="dashboard-estimate-empty">No salary estimate requested yet.</p>}
      </div>

      <p className="dashboard-estimate-qualification" id="dashboard-salary-note">
        Conditional on placement. This model estimate is not a guaranteed offer.
      </p>
      {result?.modelVersion && <p className="dashboard-estimate-caption">Model: {result.modelVersion}</p>}

      {profileLoading ? <p className="dashboard-estimate-caption">Loading your profile inputs…</p>
        : profileError ? <p className="error-banner" role="alert">{profileError}</p>
        : issues.length > 0 ? <div className="dashboard-estimate-inputs">
          <p>Complete or correct these profile inputs to estimate salary:</p>
          <ul>{issues.map(({ field, message }) => <li key={field}>{message}</li>)}</ul>
          <button type="button" className="dashboard-action-link" onClick={() => onNavigate('profile')}>
            Review Student Profile <span aria-hidden="true">→</span>
          </button>
        </div> : <p className="dashboard-estimate-caption">
          Uses your current profile inputs. {draft.collegeTier
            ? `College tier: ${draft.collegeTier}.`
            : 'College tier is missing; the existing backend default applies.'}
        </p>}

      {error && <div className="error-banner" role="alert">{error}</div>}
      <div className="dashboard-estimate-actions">
        <button type="button" className="dash-btn primary" disabled={!canEstimate || busy}
          aria-describedby="dashboard-salary-note" onClick={handleEstimate}>
          {busy ? 'Estimating salary…' : error ? 'Retry salary estimate' : 'Estimate salary'}
        </button>
        <button type="button" className="dashboard-action-link" onClick={() => onNavigate('salary')}>
          Edit salary inputs independently <span aria-hidden="true">→</span>
        </button>
      </div>
      <p className="dashboard-estimate-caption">Salary previews do not save prediction history.</p>
    </section>
  );
}

export default DashboardSalaryEstimate;
