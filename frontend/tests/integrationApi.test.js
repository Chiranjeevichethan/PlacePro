import './authFixtures.js';
import test from 'node:test';
import assert from 'node:assert/strict';
import { buildSalaryPayload, predictPlacement, requestSalaryPrediction } from '../src/services/api.js';
import { buildSalaryDraftFromProfile } from '../src/services/profileConfig.js';
import { finiteNumberOrNull, percentOrNull } from '../src/services/resultDisplay.js';

const form = {
  branch: 'CSE', collegeTier: 'Tier-3', cgpa: '8.5', backlogs: '0', codingSkill: '7',
  dsaScore: '7', aptitudeScore: '80', communicationSkill: '7', mlKnowledge: '5', systemDesign: '5',
  internships: '1', projects: '1', certifications: '1', hackathons: '0',
  openSourceContributions: '0', extracurricular: '0',
};
const prediction = { placement_probability: .947732, prediction: 'PLACED', confidence: .947732, model_version: 'placepro-final-v1' };
const response = (body, status=200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

test('known profile college tier survives salary prefill and request mapping', () => {
  const draft = buildSalaryDraftFromProfile({ collegeTier: 'Tier-3', branch: 'CSE' });
  assert.equal(draft.collegeTier, 'Tier-3');
  assert.equal(buildSalaryPayload(draft).college_tier, 'Tier-3');
});
test('absent salary tier retains the existing optional backend fallback', () => {
  assert.equal('college_tier' in buildSalaryPayload({ branch: 'CSE' }), false);
});

for (const [field, value] of [
  ['placement_probability', -0.1], ['placement_probability', 1.1], ['placement_probability', '0.8'],
  ['confidence', 1.1], ['confidence', null], ['prediction', 'UNKNOWN'],
  ['prediction', null], ['model_version', null],
]) {
  test(`malformed placement ${field}=${JSON.stringify(value)} cannot become a result`, async (t) => {
    t.mock.method(globalThis, 'fetch', async () => response({ ...prediction, [field]: value }));
    await assert.rejects(predictPlacement(form), /invalid|unexpected/i);
  });
}
test('placement uses actual response fields and keeps a genuine zero probability', async (t) => {
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.ok(url.endsWith('/api/predict'));
    const body=JSON.parse(options.body);
    assert.equal(body.college_tier, 'Tier-3');
    assert.equal(body.open_source_contributions, 0);
    return response({ ...prediction, placement_probability: 0, confidence: 1, prediction: 'NOT PLACED' });
  });
  assert.deepEqual(await predictPlacement(form), { probability: 0, confidence: 100, status: 'PLACEMENT RISK', modelVersion: 'placepro-final-v1' });
});

for (const value of [null, -1, '14.8']) {
  test(`malformed salary ${JSON.stringify(value)} cannot become an estimate`, async (t) => {
    t.mock.method(globalThis, 'fetch', async () => response({ predicted_salary_lpa: value, model_version: 'placepro-salary-v2' }));
    await assert.rejects(requestSalaryPrediction({}), /unexpected/i);
  });
}
test('salary displays the backend value and model version without a fabricated range', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => response({ predicted_salary_lpa: 14.86612781395452, model_version: 'placepro-salary-v2' }));
  assert.deepEqual(await requestSalaryPrediction({}), { predictedSalaryLpa: 14.86612781395452, modelVersion: 'placepro-salary-v2' });
});
for (const status of [400,404,409,410,422,500]) {
  test(`placement HTTP ${status} remains an error instead of a result`, async (t) => {
    t.mock.method(globalThis, 'fetch', async () => response({ detail: 'Fixture rejection' }, status));
    await assert.rejects(predictPlacement(form), /rejection|failed/i);
  });
}
test('placement network failure remains visible', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => { throw new TypeError('offline'); });
  await assert.rejects(predictPlacement(form), /Cannot reach/);
});

for (const value of [null, undefined, '', '0', false, NaN, Infinity]) {
  test(`missing or unusable display number ${String(value)} stays unknown`, () => {
    assert.equal(finiteNumberOrNull(value), null);
    assert.equal(percentOrNull(value), null);
    assert.equal(percentOrNull(value, 100), null);
  });
}
test('genuine zero scores remain distinguishable from missing evidence', () => {
  assert.equal(percentOrNull(0), 0);
  assert.equal(percentOrNull(0, 100), 0);
  assert.equal(percentOrNull(.947732, 100), 95);
  assert.equal(percentOrNull(74.5), 75); // display only, backend label stays unchanged
});
test('fractional count is rejected before placement HTTP and is never rounded by salary mapping', async (t) => {
  let requests=0;
  t.mock.method(globalThis, 'fetch', async () => { requests++; return response(prediction); });
  await assert.rejects(predictPlacement({ ...form, projects: '1.5' }), /missing or invalid/);
  assert.equal(requests, 0);
  assert.ok(Number.isNaN(buildSalaryPayload({projects:'1.5'}).projects_count));
});
test('missing salary model version cannot identify an estimate', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => response({ predicted_salary_lpa: 15 }));
  await assert.rejects(requestSalaryPrediction({}), /unexpected/i);
});
