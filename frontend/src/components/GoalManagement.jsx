import { useCallback, useEffect, useRef, useState } from 'react';
import AccessibleModal from './AccessibleModal.jsx';
import {
  createGoalMilestone,
  createStudentGoal,
  deleteStudentGoal,
  fetchStudentGoals,
  updateGoalMilestone,
  updateStudentGoal,
} from '../services/goalsApi.js';
import { goalDeadlineLabel, goalDraftFromAction, goalDraftFromRoadmap, goalProgressLabel,
  milestoneDeadlineLabel } from '../services/goalPresentation.js';

const CATEGORIES = [
  ['skill', 'Skill development'], ['preparation', 'Preparation sequence'], ['mock_test', 'Mock-test practice'],
  ['profile', 'Profile completion'], ['opportunity', 'Placement opportunity'],
  ['weekly_target', 'Weekly preparation target'], ['other', 'Other'],
];
const MODULES = [
  ['readiness', 'Career Readiness'], ['skillgap', 'Skill Gap Analysis'], ['mocktests', 'Mock Tests'],
  ['performance', 'Performance Analysis'], ['profile', 'Student Profile'],
  ['companies', 'Company Recommendations'], ['prediction', 'Placement Prediction'],
];
const EMPTY_GOAL = { title: '', description: '', category: 'preparation', target_date: '', priority: 'medium', related_module: '' };
const EMPTY_MILESTONE = { title: '', description: '', target_date: '' };

function formatDate(value) {
  if (!value) return null;
  const date = new Date(`${value}T00:00:00Z`);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString(undefined,
    { year: 'numeric', month: 'short', day: 'numeric', timeZone: 'UTC' });
}

function destinationFor(module) {
  return module === 'readiness' ? 'readiness' : module === 'skillgap' ? 'skillgap'
    : module === 'mocktests' ? 'mocktests' : module === 'performance' ? 'performance'
      : module === 'profile' ? 'profile' : module === 'companies' ? 'companies' : 'prediction';
}

function GoalFormModal({ draft, setDraft, busy, error, onClose, onSubmit }) {
  const editing = Boolean(draft.goal_id);
  return (
    <AccessibleModal labelledBy="goal-form-title" describedBy="goal-form-help" closeBlocked={busy}
      onEscape={onClose} onBackdropClose={onClose} className="modal-card goal-form-modal">
      <form onSubmit={onSubmit}>
        <div className="modal-header"><h2 id="goal-form-title">{editing ? 'Edit goal' : 'Create a goal'}</h2></div>
        <p id="goal-form-help" className="form-description">Set a personal target. Opening a related module never completes a goal automatically.</p>
        {error && <p className="error-banner" role="alert">{error}</p>}
        <div className="goal-form-grid">
          <div className="form-group goal-form-wide">
            <label htmlFor="goal-title">Goal title</label>
            <input id="goal-title" data-modal-initial-focus required maxLength={120} value={draft.title}
              onChange={(event) => setDraft((current) => ({ ...current, title: event.target.value }))} />
          </div>
          <div className="form-group">
            <label htmlFor="goal-category">Category</label>
            <select id="goal-category" value={draft.category}
              onChange={(event) => setDraft((current) => ({ ...current, category: event.target.value }))}>
              {CATEGORIES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label htmlFor="goal-priority">Priority</label>
            <select id="goal-priority" value={draft.priority}
              onChange={(event) => setDraft((current) => ({ ...current, priority: event.target.value }))}>
              <option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option>
            </select>
          </div>
          <div className="form-group">
            <label htmlFor="goal-target-date">Target date (optional)</label>
            <input id="goal-target-date" type="date" value={draft.target_date}
              onChange={(event) => setDraft((current) => ({ ...current, target_date: event.target.value }))} />
            <span className="goal-field-hint">Past target dates are allowed and shown as overdue.</span>
          </div>
          <div className="form-group">
            <label htmlFor="goal-module">Related PLACE PRO module (optional)</label>
            <select id="goal-module" value={draft.related_module}
              onChange={(event) => setDraft((current) => ({ ...current, related_module: event.target.value }))}>
              <option value="">None selected</option>
              {MODULES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </div>
          <div className="form-group goal-form-wide">
            <label htmlFor="goal-description">Description (optional)</label>
            <textarea id="goal-description" rows={3} maxLength={2000} value={draft.description}
              onChange={(event) => setDraft((current) => ({ ...current, description: event.target.value }))} />
          </div>
        </div>
        <div className="modal-actions">
          <button type="button" className="dash-btn secondary" onClick={onClose} disabled={busy}>Cancel</button>
          <button type="submit" className="dash-btn primary" disabled={busy}>{busy ? 'Saving…' : editing ? 'Save changes' : 'Create goal'}</button>
        </div>
      </form>
    </AccessibleModal>
  );
}

function MilestoneFormModal({ draft, setDraft, busy, error, onClose, onSubmit }) {
  const editing = Boolean(draft.milestone_id);
  return (
    <AccessibleModal labelledBy="milestone-form-title" describedBy="milestone-form-help" closeBlocked={busy}
      onEscape={onClose} onBackdropClose={onClose} className="modal-card goal-form-modal">
      <form onSubmit={onSubmit}>
        <div className="modal-header"><h2 id="milestone-form-title">{editing ? 'Edit milestone' : 'Add a milestone'}</h2></div>
        <p id="milestone-form-help" className="form-description">Milestones are personal records. Complete them only after you have done the work.</p>
        {error && <p className="error-banner" role="alert">{error}</p>}
        <div className="goal-form-grid">
          <div className="form-group goal-form-wide">
            <label htmlFor="milestone-title">Milestone title</label>
            <input id="milestone-title" data-modal-initial-focus required maxLength={120} value={draft.title}
              onChange={(event) => setDraft((current) => ({ ...current, title: event.target.value }))} />
          </div>
          <div className="form-group goal-form-wide">
            <label htmlFor="milestone-description">Description (optional)</label>
            <textarea id="milestone-description" rows={3} maxLength={1000} value={draft.description}
              onChange={(event) => setDraft((current) => ({ ...current, description: event.target.value }))} />
          </div>
          <div className="form-group">
            <label htmlFor="milestone-date">Target date (optional)</label>
            <input id="milestone-date" type="date" value={draft.target_date}
              onChange={(event) => setDraft((current) => ({ ...current, target_date: event.target.value }))} />
          </div>
        </div>
        <div className="modal-actions">
          <button type="button" className="dash-btn secondary" onClick={onClose} disabled={busy}>Cancel</button>
          <button type="submit" className="dash-btn primary" disabled={busy}>{busy ? 'Saving…' : editing ? 'Save milestone' : 'Add milestone'}</button>
        </div>
      </form>
    </AccessibleModal>
  );
}

function DeleteGoalModal({ goal, busy, error, onClose, onConfirm }) {
  return (
    <AccessibleModal labelledBy="delete-goal-title" describedBy="delete-goal-description" closeBlocked={busy}
      onEscape={onClose} onBackdropClose={onClose} className="modal-card confirm-card">
      <div className="modal-header"><h2 id="delete-goal-title">Delete this goal?</h2></div>
      <p id="delete-goal-description" className="confirm-text">“{goal.title}” and all its milestones will be permanently removed.</p>
      {error && <p role="alert" className="error-banner">{error}</p>}
      <div className="modal-actions">
        <button type="button" className="dash-btn secondary" onClick={onClose} disabled={busy}>Keep goal</button>
        <button type="button" className="dash-btn primary danger" data-modal-initial-focus onClick={onConfirm} disabled={busy}>
          {busy ? 'Deleting…' : 'Delete goal'}
        </button>
      </div>
    </AccessibleModal>
  );
}

function GoalCard({ goal, onEdit, onDelete, onStatus, onAddMilestone, onEditMilestone, onMilestoneStatus, onNavigate, busy }) {
  return (
    <article id={`goal-${goal.goal_id}`} className={`student-goal-card ${goal.is_overdue ? 'student-goal-overdue' : ''}`}>
      <div className="student-goal-heading">
        <div>
          <span className={`student-goal-status status-${goal.status}`}>{goal.status}</span>
          <span className={`career-priority-badge ${goal.priority}`}>{goal.priority} priority</span>
            <h3 tabIndex={-1}>{goal.title}</h3>
        </div>
        <p className={goal.is_overdue ? 'goal-overdue-label' : 'career-data-note'}>{goalDeadlineLabel(goal)}</p>
      </div>
      {goal.description && <p className="student-goal-description">{goal.description}</p>}
      <div className="student-goal-progress">
        <div><strong>{goalProgressLabel(goal)}</strong><span>{goal.milestone_count} milestone{goal.milestone_count === 1 ? '' : 's'}</span></div>
        {goal.progress_percentage !== null && (
          <div className="student-goal-meter" role="progressbar" aria-label={`Milestone progress for ${goal.title}`}
            aria-valuemin={0} aria-valuemax={100} aria-valuenow={goal.progress_percentage}>
            <span style={{ width: `${goal.progress_percentage}%` }} />
          </div>
        )}
      </div>
      {goal.related_module && <button type="button" className="dashboard-action-link student-goal-module-link"
        onClick={() => onNavigate(destinationFor(goal.related_module))}>
        Open {MODULES.find(([value]) => value === goal.related_module)?.[1] || 'related module'} <span aria-hidden="true">→</span>
      </button>}
      <div className="student-milestones">
        <div className="student-milestones-heading"><h4>Milestones</h4>
          {goal.status !== 'completed' && <button type="button" className="dashboard-action-link" onClick={() => onAddMilestone(goal)}>Add milestone</button>}
        </div>
        {goal.milestones.length ? <ul>
          {goal.milestones.map((milestone) => (
            <li id={`milestone-${milestone.milestone_id}`} key={milestone.milestone_id} className={milestone.is_overdue ? 'milestone-overdue' : ''}>
              <span className={`milestone-status milestone-${milestone.status} milestone-${milestone.deadline_state || 'no-deadline'}`}>{milestoneDeadlineLabel(milestone)}</span>
              <div className="milestone-copy"><strong tabIndex={-1}>{milestone.title}</strong>
                {milestone.description && <p>{milestone.description}</p>}
                {milestone.target_date && <span className="career-data-note">Target {formatDate(milestone.target_date)}</span>}
                {milestone.completed_at && <span className="career-data-note">Saved {new Date(milestone.completed_at).toLocaleString()}</span>}
              </div>
              <div className="milestone-actions">
                <button type="button" className="dashboard-action-link" onClick={() => onEditMilestone(goal, milestone)}>Edit</button>
                {goal.status !== 'completed' && <button type="button" className="dashboard-action-link"
                  aria-label={`${milestone.status === 'completed' ? 'Reopen' : 'Mark complete'} milestone: ${milestone.title}`}
                  disabled={busy} onClick={() => onMilestoneStatus(goal, milestone)}>
                  {milestone.status === 'completed' ? 'Reopen' : 'Mark complete'}
                </button>}
              </div>
            </li>
          ))}
        </ul> : <p className="career-data-note">No milestones added. Progress is not calculated until a milestone exists.</p>}
      </div>
      <div className="student-goal-actions">
        <button type="button" className="dash-btn secondary" onClick={() => onEdit(goal)}>Edit goal</button>
        {goal.status === 'active' && <button type="button" className="dash-btn secondary" disabled={busy} onClick={() => onStatus(goal, 'paused')}>Pause</button>}
        {goal.status === 'paused' && <button type="button" className="dash-btn secondary" disabled={busy} onClick={() => onStatus(goal, 'active')}>Resume</button>}
        {goal.status !== 'completed' && <button type="button" className="dash-btn secondary" disabled={busy}
          onClick={() => onStatus(goal, 'completed')}>Mark goal complete</button>}
        {goal.status === 'completed' && <button type="button" className="dash-btn secondary" disabled={busy}
          onClick={() => onStatus(goal, 'active')}>Reopen goal</button>}
        <button type="button" className="dashboard-action-link student-goal-delete" onClick={() => onDelete(goal)}>Delete</button>
      </div>
      {goal.status !== 'completed' && <p className="goal-completion-guidance">Complete every milestone before completing this goal. If no milestones exist, you may mark the goal complete explicitly.</p>}
    </article>
  );
}

export default function GoalManagement({ profileId, actions = [], roadmap, active = true, focusOnHash = false, onNavigate,
  focusTarget, onFocusTargetHandled }) {
  const [loaded, setLoaded] = useState(null);
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState(null);
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [mutationError, setMutationError] = useState(null);
  const [goalDraft, setGoalDraft] = useState(null);
  const [milestoneDraft, setMilestoneDraft] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const requestVersion = useRef(0);
  const loadedProfileId = useRef(null);

  const load = useCallback(async (showLoading = false) => {
    if (!profileId) return;
    const version = ++requestVersion.current;
    if (showLoading) setLoading(true);
    setPageError(null);
    try {
      const data = await fetchStudentGoals(profileId);
      if (requestVersion.current === version) {
        loadedProfileId.current = profileId;
        setLoaded({ profileId, data });
      }
    } catch (error) {
      if (requestVersion.current === version) setPageError(error.message);
    } finally {
      if (requestVersion.current === version) setLoading(false);
    }
  }, [profileId]);

  useEffect(() => {
    if (!active) return undefined;
    const profileChanged = loadedProfileId.current !== null && loadedProfileId.current !== profileId;
    if (profileChanged) setLoaded(null);
    void load(loadedProfileId.current !== profileId || profileChanged);
    return () => { requestVersion.current += 1; };
  }, [active, load, profileId]);

  const current = loaded?.profileId === profileId ? loaded.data : null;
  const goals = current?.goals ?? [];
  const summary = current?.summary ?? { active_goals: 0, completed_goals: 0, upcoming_milestones: 0, overdue_milestones: 0 };

  useEffect(() => {
    if (!active || !current || !focusTarget?.goalId) return;
    const target = focusTarget.milestoneId
      ? document.getElementById(`milestone-${focusTarget.milestoneId}`)
      : document.getElementById(`goal-${focusTarget.goalId}`);
    const heading = focusTarget.milestoneId ? target?.querySelector('strong') : target?.querySelector('h3');
    if (target) {
      target.scrollIntoView({ behavior: 'smooth', block: 'center' });
      heading?.focus({ preventScroll: true });
    }
    onFocusTargetHandled?.();
  }, [active, current, focusTarget, onFocusTargetHandled]);

  useEffect(() => {
    if (!active || !current || !focusOnHash || window.location.hash !== '#goal-management') return;
    const heading = document.getElementById('goal-management-title');
    if (!heading) return;
    heading.focus({ preventScroll: true });
    heading.scrollIntoView({ block: 'start' });
  }, [active, current, focusOnHash]);

  const refreshAfterMutation = async (successMessage) => {
    requestVersion.current += 1;
    const data = await fetchStudentGoals(profileId);
    loadedProfileId.current = profileId;
    setLoaded({ profileId, data });
    setPageError(null);
    setNotice(successMessage);
    setMutationError(null);
    window.dispatchEvent(new Event('placepro-goals-changed'));
  };

  const createFromAction = (action) => {
    setMutationError(null);
    setNotice('');
    setGoalDraft({ ...goalDraftFromAction(action), goal_id: null });
  };

  const createFromRoadmap = (activity) => {
    setMutationError(null);
    setNotice('');
    setGoalDraft({ ...goalDraftFromRoadmap(activity), goal_id: null });
  };

  const saveGoal = async (event) => {
    event.preventDefault();
    if (!goalDraft || busy) return;
    setBusy(true); setMutationError(null); setNotice('');
    const payload = {
      title: goalDraft.title,
      description: goalDraft.description,
      category: goalDraft.category,
      target_date: goalDraft.target_date || null,
      priority: goalDraft.priority,
      related_module: goalDraft.related_module || null,
    };
    try {
      if (goalDraft.goal_id) await updateStudentGoal(profileId, goalDraft.goal_id, payload);
      else await createStudentGoal(profileId, payload);
      setGoalDraft(null);
      await refreshAfterMutation(goalDraft.goal_id ? 'Goal changes saved.' : 'Goal created and saved to your account.');
    } catch (error) { setMutationError(error.message); }
    finally { setBusy(false); }
  };

  const saveMilestone = async (event) => {
    event.preventDefault();
    if (!milestoneDraft || busy) return;
    setBusy(true); setMutationError(null); setNotice('');
    const payload = { ...milestoneDraft, target_date: milestoneDraft.target_date || null };
    delete payload.goal_id; delete payload.milestone_id;
    try {
      if (milestoneDraft.milestone_id) {
        await updateGoalMilestone(profileId, milestoneDraft.goal_id, milestoneDraft.milestone_id, payload);
      } else {
        await createGoalMilestone(profileId, milestoneDraft.goal_id, payload);
      }
      setMilestoneDraft(null);
      await refreshAfterMutation(milestoneDraft.milestone_id ? 'Milestone changes saved.' : 'Milestone added.');
    } catch (error) { setMutationError(error.message); }
    finally { setBusy(false); }
  };

  const runMutation = async (operation, successMessage) => {
    if (busy) return;
    setBusy(true); setMutationError(null); setNotice('');
    try { await operation(); await refreshAfterMutation(successMessage); }
    catch (error) { setMutationError(error.message); }
    finally { setBusy(false); }
  };

  const openGoal = (goal = null) => {
    setMutationError(null); setNotice('');
    setGoalDraft(goal ? { ...goal, target_date: goal.target_date || '', related_module: goal.related_module || '' } : { ...EMPTY_GOAL, goal_id: null });
  };

  const openMilestone = (goal, milestone = null) => {
    setMutationError(null); setNotice('');
    setMilestoneDraft(milestone
      ? { goal_id: goal.goal_id, milestone_id: milestone.milestone_id, title: milestone.title, description: milestone.description || '', target_date: milestone.target_date || '' }
      : { goal_id: goal.goal_id, milestone_id: null, ...EMPTY_MILESTONE });
  };

  const visibleActions = actions.filter((action) => action.title && action.priority !== 'Priority unavailable').slice(0, 4);

  return (
    <section id="goal-management" className="career-readiness-section goal-management" aria-labelledby="goal-management-title">
      <div className="career-section-heading">
        <div><span className="career-eyebrow">YOUR TARGETS · SAVED TO YOUR ACCOUNT</span><h2 id="goal-management-title" tabIndex={-1}>Goals and milestones</h2></div>
        <button type="button" className="dash-btn primary" onClick={() => openGoal()}>Create a goal</button>
      </div>
      <p className="career-planner-intro">Set your own targets from your current preparation needs. Completing goals and milestones requires your explicit action; visiting a module never changes their status.</p>
      {notice && <p className="goal-success-message" role="status">{notice}</p>}
      {pageError && <div className="goal-error-state" role="alert"><p>{pageError}</p>
        <button type="button" className="dash-btn secondary" onClick={() => load(true)}>Retry</button></div>}
      {mutationError && !goalDraft && !milestoneDraft && !deleteTarget &&
        <p className="goal-inline-error" role="alert">{mutationError}</p>}
      {loading && !current ? <p className="career-empty-note" role="status">Loading saved goals…</p> : current && (
        <>
          <div className="goal-summary-grid" aria-label="Goal and milestone summary">
            <article><span>Active goals</span><strong>{summary.active_goals}</strong></article>
            <article><span>Completed goals</span><strong>{summary.completed_goals}</strong></article>
            <article><span>Upcoming milestones</span><strong>{summary.upcoming_milestones}</strong></article>
            <article className={summary.overdue_milestones ? 'has-overdue' : ''}><span>Overdue milestones</span><strong>{summary.overdue_milestones}</strong></article>
          </div>
          {pageError && <p className="goal-inline-error" role="alert">The latest refresh failed; showing the last saved response. {pageError}</p>}
          {goals.length ? <div className="student-goal-list">
            {goals.map((goal) => <GoalCard key={goal.goal_id} goal={goal} busy={busy} onNavigate={onNavigate}
              onEdit={openGoal} onDelete={setDeleteTarget} onAddMilestone={(item) => openMilestone(item)}
              onEditMilestone={openMilestone}
              onStatus={(item, status) => runMutation(() => updateStudentGoal(profileId, item.goal_id, { status }),
                status === 'completed' ? 'Goal marked complete.' : status === 'paused' ? 'Goal paused.' : 'Goal is active again.')}
              onMilestoneStatus={(item, milestone) => runMutation(
                () => updateGoalMilestone(profileId, item.goal_id, milestone.milestone_id,
                  { status: milestone.status === 'completed' ? 'pending' : 'completed' }),
                milestone.status === 'completed' ? 'Milestone reopened.' : 'Milestone completion saved.')}
            />)}
          </div> : <div className="goal-empty-state" role="status"><h3>No goals yet</h3>
            <p>Create a goal you choose, or start from one of the current verified preparation recommendations below.</p>
            <button type="button" className="dash-btn primary" onClick={() => openGoal()}>Create your first goal</button>
          </div>}
          {visibleActions.length > 0 && <div className="goal-recommendation-start">
            <div><h3>Start from a current recommendation</h3><p>These are existing Career Readiness actions. Choose one to prefill a draft; it is not saved until you create it.</p></div>
            <ul>{visibleActions.map((action) => <li key={action.id}>
              <div><span className={`career-priority-badge ${action.priority.toLowerCase()}`}>{action.priority}</span><strong>{action.title}</strong></div>
              <button type="button" className="dashboard-action-link" onClick={() => createFromAction(action)}>Use as a goal draft</button>
            </li>)}</ul>
          </div>}
          {roadmap?.activityCount > 0 && <div className="goal-recommendation-start">
            <div><h3>Turn a Learning Roadmap sequence into a goal</h3><p>Choose an existing sequence to prefill a draft with its current priority and related module. Nothing is saved until you submit the goal form.</p></div>
            <ul>{roadmap.days.slice(0, 4).map(({ activity }) => <li key={activity.id}>
              <div><span className={`career-priority-badge ${activity.priority === 'Priority unavailable' ? 'unranked' : activity.priority.toLowerCase()}`}>{activity.priority}</span><strong>{activity.title}</strong></div>
              <button type="button" className="dashboard-action-link" onClick={() => createFromRoadmap(activity)}>Use roadmap sequence</button>
            </li>)}</ul>
          </div>}
        </>
      )}
      {goalDraft && <GoalFormModal draft={goalDraft} setDraft={setGoalDraft} busy={busy} error={mutationError}
        onClose={() => { if (!busy) { setGoalDraft(null); setMutationError(null); } }} onSubmit={saveGoal} />}
      {milestoneDraft && <MilestoneFormModal draft={milestoneDraft} setDraft={setMilestoneDraft} busy={busy} error={mutationError}
        onClose={() => { if (!busy) { setMilestoneDraft(null); setMutationError(null); } }} onSubmit={saveMilestone} />}
      {deleteTarget && <DeleteGoalModal goal={deleteTarget} busy={busy} error={mutationError}
        onClose={() => { if (!busy) { setDeleteTarget(null); setMutationError(null); } }}
        onConfirm={() => runMutation(async () => {
          await deleteStudentGoal(profileId, deleteTarget.goal_id);
          setDeleteTarget(null);
        }, 'Goal and its milestones were deleted.')} />}
    </section>
  );
}
