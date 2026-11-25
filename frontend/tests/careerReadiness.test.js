import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { buildCareerReadinessView } from '../src/services/careerReadiness.js';
import { buildLearningRoadmap } from '../src/services/learningRoadmap.js';

const component = await readFile(new URL('../src/pages/CareerReadiness.jsx', import.meta.url), 'utf8');
const app = await readFile(new URL('../src/App.jsx', import.meta.url), 'utf8');
const sidebar = await readFile(new URL('../src/components/Sidebar.jsx', import.meta.url), 'utf8');
const search = await readFile(new URL('../src/components/SearchBar.jsx', import.meta.url), 'utf8');
const css = await readFile(new URL('../src/App.css', import.meta.url), 'utf8');
const mockTests = await readFile(new URL('../src/pages/MockTests.jsx', import.meta.url), 'utf8');
const roadmapComponent = await readFile(new URL('../src/components/LearningRoadmap.jsx', import.meta.url), 'utf8');

const performanceRecord = (overrides = {}) => ({
  profile_id: 'profile-a',
  source_revision: 4,
  verified: true,
  summary: {
    skills_tracked: 2,
    assessments: { assessments_count: 1, average_score: 72 },
    predictions: { predictions_count: 1, latest_is_current: false },
  },
  readiness: {
    readiness_score: 64.5,
    readiness_level: 'Developing',
    profile_completeness: { percentage: 75, missing_fields: ['projects'] },
    skill_gaps: [{ skill: 'SQL', priority: 'HIGH' }],
    strengths: [{ skill: 'Python' }],
    improvement_plan: [{ priority: 1, skill: 'SQL', reason: 'No evidence recorded', action: 'Practise SQL queries' }],
  },
  assessment_history: [{ assessment_id: 'assessment-1', skill: 'Python', score: 72, timestamp: '2026-01-01T00:00:00Z' }],
  prediction_history: [{ prediction: 'NOT PLACED', placement_probability: 0.41 }],
  skills: [{ skill: 'Python' }, { skill: 'SQL' }],
  ...overrides,
});

test('readiness view uses backend score, incomplete sections, and its improvement plan', () => {
  const view = buildCareerReadinessView(performanceRecord(), { recommendations: { recommended: [], eligible: [] } });

  assert.equal(view.readinessScore, 65);
  assert.equal(view.readinessLevel, 'Developing');
  assert.deepEqual(view.profileCompleteness, { percentage: 75, missingFields: ['projects'] });
  assert.equal(view.actions[0].destination, 'edit-profile');
  assert.equal(view.actions[0].priority, 'High');
  assert.equal(view.actions[1].skill, 'SQL');
  assert.equal(view.actions[1].destination, 'skillgap');
  assert.equal(view.actions[1].priority, 'High');
  assert.equal(view.assessments.count, 1);
  assert.equal(view.assessments.averageScore, 72);
});

test('placement estimates remain separate from readiness and stale estimates are identified', () => {
  const view = buildCareerReadinessView(performanceRecord(), null);

  assert.equal(view.readinessScore, 65);
  assert.equal(view.prediction.probability, 41);
  assert.equal(view.prediction.label, 'NOT PLACED');
  assert.equal(view.prediction.current, false);
  assert.notEqual(view.readinessScore, view.prediction.probability);
});

test('missing counts and missing profile completeness remain unavailable, not fabricated zeros', () => {
  const performance = performanceRecord({
    summary: { skills_tracked: null, assessments: {}, predictions: {} },
    readiness: { readiness_score: null, skill_gaps: null, improvement_plan: [] },
    assessment_history: [],
    prediction_history: [],
  });
  const view = buildCareerReadinessView(performance, null);

  assert.equal(view.readinessScore, null);
  assert.equal(view.profileCompleteness.percentage, null);
  assert.equal(view.profileCompleteness.missingFields, null);
  assert.equal(view.skillsTracked, null);
  assert.equal(view.assessments.count, null);
  assert.equal(view.skillGaps, null);
  assert.equal(view.actions.some((action) => action.id === 'first-assessment'), false);
  assert.equal(view.actions.some((action) => action.id === 'first-prediction'), false);
});

test('known empty histories produce first-use actions and real zero counts', () => {
  const performance = performanceRecord({
    summary: { skills_tracked: 0, assessments: { assessments_count: 0 }, predictions: { predictions_count: 0 } },
    readiness: { readiness_score: 0, readiness_level: 'Starting', profile_completeness: { percentage: 100, missing_fields: [] }, skill_gaps: [], strengths: [], improvement_plan: [] },
    assessment_history: [],
    prediction_history: [],
  });
  const view = buildCareerReadinessView(performance, null);

  assert.equal(view.assessments.count, 0);
  assert.equal(view.readinessScore, 0);
  assert.deepEqual(view.actions.map((action) => action.destination), ['mocktests', 'prediction']);
});

test('company recommendations are sourced from response and duplicate entries are removed', () => {
  const view = buildCareerReadinessView(performanceRecord(), {
    recommendations: {
      recommended: [{ company_id: 'c1', company_name: 'Acme', eligibility_status: 'INCOMPLETE' }],
      eligible: [{ company_id: 'c1', company_name: 'Acme' }, { company_id: 'c2', company_name: 'Northwind' }],
    },
  });

  assert.deepEqual(view.companies.map(({ id, name }) => [id, name]), [
    ['c1', 'Acme'], ['c2', 'Northwind'],
  ]);
});

test('action priorities follow backend profile completeness and skill-gap priority, without numeric scores', () => {
  const performance = performanceRecord({
    summary: { assessments: { assessments_count: 0 }, predictions: { predictions_count: 0 } },
    readiness: {
      readiness_score: 64.5,
      profile_completeness: { percentage: 75, missing_fields: ['projects'] },
      skill_gaps: [
        { skill: 'SQL', priority: 'HIGH' },
        { skill: 'Networks', priority: 'MEDIUM' },
        { skill: 'Cloud', priority: 'LOW' },
      ],
      improvement_plan: [
        { skill: 'SQL', action: 'Practise SQL', reason: 'Missing evidence', priority: 1 },
        { skill: 'Networks', action: 'Review networks', reason: 'Missing evidence', priority: 2 },
        { skill: 'Cloud', action: 'Explore cloud', reason: 'Missing evidence', priority: 3 },
      ],
    },
    assessment_history: [],
    prediction_history: [],
  });
  const view = buildCareerReadinessView(performance, { recommendations: { recommended: [{ company_id: 'acme', company_name: 'Acme' }] } });

  assert.deepEqual(view.actions.map(({ id, priority }) => [id, priority]), [
    ['complete-profile', 'High'],
    ['skill-sql-0', 'High'],
    ['skill-networks-1', 'Medium'],
    ['first-assessment', 'Medium'],
    ['skill-cloud-2', 'Optional'],
    ['first-prediction', 'Optional'],
    ['review-companies', 'Optional'],
  ]);
  assert.equal(view.actions.some((action) => typeof action.priority === 'number'), false);
  assert.match(view.actions[1].rationale, /does not prove you lack the skill/);
});

test('recent verified Beginner or Developing assessment evidence creates a skill-specific practice action', () => {
  const performance = performanceRecord({
    readiness: { readiness_score: 64, profile_completeness: { percentage: 100, missing_fields: [] }, skill_gaps: [], improvement_plan: [] },
    summary: { assessments: { assessments_count: 1 }, predictions: { predictions_count: 1 } },
    assessment_history: [{ assessment_id: 'a2', skill: 'Python', score: 38, level: 'Beginner', verified: true }],
  });
  const view = buildCareerReadinessView(performance, null);
  const practice = view.actions.find((action) => action.id === 'review-assessment-python');

  assert.equal(practice.priority, 'Medium');
  assert.equal(practice.destination, 'mocktests');
  assert.match(practice.description, /Beginner/);
  assert.match(practice.followUp, /assessment history will appear here/);
});

test('verified server history is reported as recorded progress, not as a manual completion claim', () => {
  const performance = performanceRecord({
    readiness: { readiness_score: 64, profile_completeness: { percentage: 100, missing_fields: [] }, skill_gaps: [], improvement_plan: [] },
    assessment_history: [
      { assessment_id: 'verified-1', skill: 'Python', score: 75, level: 'Strong', verified: true, timestamp: '2026-01-02' },
      { assessment_id: 'unverified-1', skill: 'SQL', score: 95, level: 'Advanced', verified: false, timestamp: '2026-01-03' },
    ],
    prediction_history: [{ prediction: 'PLACED', placement_probability: 0.9, source_revision: 3, timestamp: '2026-01-01' }],
  });
  const view = buildCareerReadinessView(performance, null);

  assert.ok(view.recordedActivity.some((item) => item.title === 'Profile sections complete'));
  assert.ok(view.recordedActivity.some((item) => item.title === 'Completed assessment: Python'));
  assert.equal(view.recordedActivity.some((item) => item.title.includes('SQL')), false);
  assert.ok(view.recordedActivity.some((item) => item.title === 'Saved placement model estimate'));
  assert.match(view.recordedActivity.find((item) => item.kind === 'Estimate').detail, /earlier profile revision/);
});

test('resolved skill-gap actions leave the active plan after fresh verified evidence arrives', () => {
  const before = performanceRecord();
  const after = performanceRecord({
    readiness: {
      readiness_score: 72,
      profile_completeness: { percentage: 100, missing_fields: [] },
      skill_gaps: [],
      strengths: [{ skill: 'SQL' }],
      improvement_plan: [],
    },
    summary: { skills_tracked: 2, assessments: { assessments_count: 2 }, predictions: { predictions_count: 1, latest_is_current: true } },
    assessment_history: [{ assessment_id: 'sql-verified', skill: 'SQL', score: 75, level: 'Strong', verified: true, timestamp: '2026-02-01' }],
  });
  const beforeView = buildCareerReadinessView(before, null);
  const afterView = buildCareerReadinessView(after, null);

  assert.ok(beforeView.actions.some((action) => action.skill === 'SQL'));
  assert.equal(afterView.actions.some((action) => action.skill === 'SQL'), false);
  assert.ok(afterView.recordedActivity.some((item) => item.title === 'Completed assessment: SQL'));
});

test('page integration uses current owned APIs and revalidates when revisited', () => {
  assert.match(component, /fetchPerformance\(profileId\)/);
  assert.match(component, /fetchCompanyRecommendations\(profileId, 3\)/);
  assert.match(component, /requireSource\(recommendationResult\.recommendations, source\)/);
  assert.match(component, /useProfileResource\(loadCareerReadiness\)/);
  assert.match(component, /if \(returnedToPage\) refetch\(\)/);
  assert.match(component, /rawProfile\.verified !== true/);
  assert.match(component, /role="alert"/);
  assert.match(component, /Loading your readiness information/);
});

test('readiness navigation is available in the sidebar and page search', () => {
  assert.match(sidebar, /page: "readiness", label: "Career Readiness"/);
  assert.match(search, /page: "readiness",\s+label: "Career Readiness"/);
  assert.match(app, /page === "readiness" \|\| page === "goals"\) setCareerReadinessVisited\(true\)/);
  assert.match(app, /<CareerReadiness[\s\S]*?focusGoalManagement=\{currentPage === "goals" && window\.location\.hash === "#goal-management"\}/);
  assert.match(app, /hidden=\{currentPage !== "readiness" && currentPage !== "goals"\}/);
});

test('existing Mock Tests remains mounted under its original hidden wrapper', () => {
  assert.match(app, /<div hidden=\{currentPage !== "mocktests"\}>\s*<MockTests onNavigate=\{handleNavigate\}[\s\S]*?onAssessmentStateChange=\{handleAssessmentStateChange\}[\s\S]*?\/>\s*<\/div>/);
  assert.match(mockTests, /Your answers are kept in this tab\. The assessment deadline continues while you are away\./);
});

test('career readiness layout has tablet and phone single-column breakpoints', () => {
  assert.match(css, /\.career-progress-grid\s*\{[^}]*grid-template-columns:\s*repeat\(3, minmax\(0, 1fr\)\)/);
  assert.match(css, /@media\s*\(max-width:\s*900px\)[\s\S]*?\.career-progress-grid\s*\{[^}]*grid-template-columns:\s*repeat\(2, minmax\(0, 1fr\)\)/);
  assert.match(css, /@media\s*\(max-width:\s*600px\)[\s\S]*?\.career-readiness-hero\s*,\s*\.career-progress-grid\s*,\s*\.career-company-list\s*\{[^}]*grid-template-columns:\s*1fr/);
  assert.match(css, /\.career-action-card\s*\{[\s\S]*?grid-template-columns:\s*minmax\(96px, auto\) minmax\(0, 1fr\) auto/);
  assert.match(css, /@media\s*\(max-width:\s*600px\)[\s\S]*?\.career-action-card\s*\{[^}]*grid-template-columns:\s*minmax\(0, 1fr\)/);
});

test('planner exposes priority, rationale, follow-up, and evidence-backed progress without local completion storage', () => {
  assert.match(component, /TODAY'S FOCUS[\s\S]*?Personalized action plan/);
  assert.match(component, /item\.priority/);
  assert.match(component, /Why this is here:/);
  assert.match(component, /After this:/);
  assert.match(component, /Progress on record/);
  assert.match(component, /Action completion is not checked off when you open a page/);
  assert.doesNotMatch(component, /localStorage|sessionStorage|type="checkbox"|Mark .*complete/i);
});

test('roadmap sequences skill gaps using backend priority and existing preparation guidance', () => {
  const roadmap = buildLearningRoadmap(buildCareerReadinessView(performanceRecord(), null));
  const sql = roadmap.days.find((day) => day.activity.title === 'SQL preparation sequence').activity;

  assert.equal(sql.priority, 'High');
  assert.deepEqual(sql.steps.map((step) => step.destination), ['skillgap', 'skillgap', 'mocktests', 'performance']);
  assert.match(sql.steps[1].title, /Practise SQL queries/);
  assert.match(sql.reason, /HIGH/);
});

test('roadmap offers mock-test practice only for a skill listed by the existing Mock Tests setup', () => {
  const view = buildCareerReadinessView(performanceRecord({
    readiness: {
      readiness_score: 50,
      profile_completeness: { percentage: 100, missing_fields: [] },
      skill_gaps: [{ skill: 'Technical Interview', priority: 'MEDIUM' }],
      improvement_plan: [{ skill: 'Technical Interview', action: 'Prepare interview examples', reason: 'No interview evidence is listed.' }],
    },
  }), null);
  const roadmap = buildLearningRoadmap(view);
  const activity = roadmap.days.find((day) => day.activity.title === 'Technical Interview preparation sequence').activity;

  assert.equal(activity.steps.some((step) => step.destination === 'mocktests'), false);
  assert.ok(activity.steps.every((step) => step.destination === 'skillgap'));
});

test('roadmap creates a deterministic seven-day overview and retains further priorities', () => {
  const actions = Array.from({ length: 9 }, (_, index) => ({
    id: `activity-${index}`,
    title: `Activity ${index}`,
    description: 'From current profile data.',
    rationale: 'Supported by the backend response.',
    priority: index === 0 ? 'High' : 'Optional',
    destination: 'performance',
    cta: 'Review performance',
  }));
  const roadmap = buildLearningRoadmap({ actions });

  assert.deepEqual(roadmap.days.map((day) => day.number), [1, 2, 3, 4, 5, 6, 7]);
  assert.equal(roadmap.days[0].activity.title, 'Activity 0');
  assert.equal(roadmap.additionalActivities.length, 2);
  assert.equal(roadmap.activityCount, 9);
});

test('roadmap handles unavailable actions without substituting zeroes or fake activities', () => {
  assert.deepEqual(buildLearningRoadmap(null), { days: [], additionalActivities: [], activityCount: 0 });
  assert.deepEqual(buildLearningRoadmap({ actions: [] }), { days: [], additionalActivities: [], activityCount: 0 });
});

test('roadmap controls navigate days and modules without claiming local completion', () => {
  assert.match(component, /<LearningRoadmap view=\{view\} roadmap=\{roadmap\} onNavigate=\{onNavigate\}/);
  assert.match(roadmapComponent, /aria-pressed=\{Boolean\(day/);
  assert.match(roadmapComponent, /onClick=\{\(\) => setSelectedDay\(index\)\}/);
  assert.match(roadmapComponent, /onNavigate\(step\.destination\)/);
  assert.match(roadmapComponent, /Opening a module does not mark work complete/);
  assert.doesNotMatch(roadmapComponent, /localStorage|sessionStorage|type="checkbox"|completed\s*=|setCompleted/i);
  assert.match(roadmapComponent, /No time estimates are shown/);
});
