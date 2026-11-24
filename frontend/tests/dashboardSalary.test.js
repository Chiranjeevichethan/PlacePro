import test from 'node:test';
import assert from 'node:assert/strict';
import { validateDashboardSalaryDraft } from '../src/services/dashboardSalary.js';
import { buildSalaryDraftFromProfile } from '../src/services/profileConfig.js';
import { buildSalaryPayload } from '../src/services/api.js';
import { createPredictionController, predictionStamp, profileStamp } from '../src/services/profileState.js';

// Synthetic input fixture only; no model result or student record is created.
const profile = {
  branch: 'CSE', collegeTier: 'Tier-3', cgpa: '0', backlogs: '0',
  codingSkills: '0', dsaScore: '0', aptitudeScore: '0', communicationSkills: '0',
  mlKnowledge: '0', systemDesign: '0', internshipsCount: 0, projectsCount: 0,
  certificationsCount: 0, hackathonsCount: 0, openSourceContributions: '0', extracurriculars: '0',
};
const draft = () => buildSalaryDraftFromProfile(profile);

test('salary preview accepts genuine zero inputs and preserves the profile tier', () => {
  const values = draft();
  assert.deepEqual(validateDashboardSalaryDraft(values), []);
  const payload = buildSalaryPayload(values);
  assert.equal(payload.college_tier, 'Tier-3');
  assert.equal(payload.cgpa, 0);
  assert.equal(payload.projects_count, 0);
});

test('missing required salary inputs remain missing and are named for the student', () => {
  const issues = validateDashboardSalaryDraft(buildSalaryDraftFromProfile(null));
  assert.equal(issues.length, 15);
  assert.ok(issues.some(({ field, message }) => field === 'codingSkills' && message === 'Coding skill is missing.'));
  for (const value of [undefined, null, '', '   ']) {
    assert.deepEqual(validateDashboardSalaryDraft({ ...draft(), cgpa: value }),
      [{ field: 'cgpa', message: 'CGPA is missing.' }]);
  }
});

test('optional absent college tier preserves the existing backend fallback', () => {
  const values = draft();
  delete values.collegeTier;
  assert.deepEqual(validateDashboardSalaryDraft(values), []);
  assert.equal('college_tier' in buildSalaryPayload(values), false);
});

test('salary preview keeps existing branch mapping and rejects unsupported categories', () => {
  for (const branch of ['ISE', 'Information Science', 'Information Science and Engineering']) {
    const values = { ...draft(), branch };
    assert.deepEqual(validateDashboardSalaryDraft(values), []);
    assert.equal(buildSalaryPayload(values).branch, 'CSE');
  }
  assert.equal(validateDashboardSalaryDraft({ ...draft(), branch: 'Unmapped branch' })[0].field, 'branch');
  assert.equal(validateDashboardSalaryDraft({ ...draft(), collegeTier: 'Tier-4' })[0].field, 'collegeTier');
});

test('invalid numeric types cannot enable the dashboard salary request', () => {
  for (const value of [NaN, Infinity, 'no score', true, [], {}]) {
    assert.ok(validateDashboardSalaryDraft({ ...draft(), codingSkills: value })
      .some(({ field }) => field === 'codingSkills'));
  }
});

test('dashboard salary input limits and whole counts match the existing salary page', () => {
  for (const [field, value] of [['cgpa', 10.1], ['codingSkills', 10.1], ['aptitudeScore', 101],
    ['openSourceContributions', 3], ['extracurriculars', 4], ['backlogs', -1],
    ['internships', 1.5], ['projects', .5], ['certifications', .1], ['hackathons', .1]]) {
    assert.ok(validateDashboardSalaryDraft({ ...draft(), [field]: value })
      .some((issue) => issue.field === field), `${field}=${value} must be rejected`);
  }
  assert.deepEqual(validateDashboardSalaryDraft({ ...draft(), cgpa: 10, codingSkills: 10,
    aptitudeScore: 100, openSourceContributions: 2, extracurriculars: 3 }), []);
});

test('the salary request captures every current draft value and does not reuse the initial profile', async () => {
  const submitted = [];
  const controller = createPredictionController(async (values) => { submitted.push(values); return null; });
  const first = draft();
  await controller.run(predictionStamp('profile-a', first), first);
  const current = { ...first, cgpa: '9', collegeTier: 'Tier-1', projects: '2' };
  await controller.run(predictionStamp('profile-a', current), current);
  current.cgpa = '5';
  assert.equal(submitted[0].cgpa, '0');
  assert.deepEqual(submitted[1], { ...first, cgpa: '9', collegeTier: 'Tier-1', projects: '2' });
});

test('equal salary inputs on a new profile or revision discard a delayed result', async () => {
  for (const replacement of [{ profile_id: 'b', revision: 1 }, { profile_id: 'a', revision: 2 }]) {
    let finish;
    const delayed = new Promise((resolve) => { finish = resolve; });
    const controller = createPredictionController(() => delayed);
    const initialKey = profileStamp('a', { revision: 1, verified: true });
    const request = controller.run(predictionStamp(initialKey, draft()), draft());
    const nextKey = profileStamp(replacement.profile_id, { ...replacement, verified: true });
    controller.select(predictionStamp(nextKey, draft()));
    finish({ fixture: 'synthetic late result' });
    await request;
    assert.equal(controller.getSnapshot().result, null);
    assert.equal(controller.getSnapshot().busy, false);
  }
});
