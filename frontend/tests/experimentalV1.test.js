import './authFixtures.js';
import assert from 'node:assert/strict';
import test from 'node:test';
import { predictExperimentalV1 } from '../src/services/api.js';
import { clearRequestIdentity, setRequestIdentity } from '../src/services/apiTransport.js';

const draft = {
  branch: 'EE', collegeTier: 'Tier-2', cgpa: '8.5', backlogs: '0',
  codingSkill: '7.5', dsaScore: '8', mlKnowledge: '6', systemDesign: '5',
  projects: '2', certifications: '1', aptitudeScore: '80', communicationSkill: '7',
  internships: '1', hackathons: '0', openSourceContributions: '1', extracurricular: '2',
};
const payload = {
  branch: 'EE', college_tier: 'Tier-2', cgpa: 8.5, backlogs: 0,
  coding_skills: 7.5, dsa_score: 8, ml_knowledge: 6, system_design: 5,
  projects_count: 2, certifications: 1, aptitude_score: 80, communication_skills: 7,
  internships: 1, hackathons: 0, open_source_contributions: 1, extracurriculars: 2,
};
const prediction = {
  placement_probability: 0.8123, prediction: 'Placed', confidence: 0.8123,
  model_version: 'placepro-experimental-v1-16-inputs', experimental: true,
  synthetic_data_notice: 'Trained entirely on synthetic data; not validated for real-world outcomes.',
};
const response = (body, status = 200) => new Response(JSON.stringify(body), { status });

test('V1 sends exactly its 16 production-equivalent fields and vocabulary through cookie and CSRF transport', async (t) => {
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.ok(url.endsWith('/api/experimental/v1/predict'));
    assert.equal(options.method, 'POST');
    assert.equal(options.credentials, 'include');
    assert.equal(options.cache, 'no-store');
    assert.equal(options.headers['x-csrf-token'], 'a'.repeat(64));
    assert.equal(options.headers['content-type'], 'application/json');
    assert.deepEqual(JSON.parse(options.body), payload);
    assert.equal(Object.keys(JSON.parse(options.body)).length, 16);
    return response(prediction);
  });
  assert.deepEqual(await predictExperimentalV1(draft), {
    probability: 81, status: 'LIKELY PLACED', confidence: 81,
    modelVersion: prediction.model_version, experimental: true,
    syntheticDataNotice: prediction.synthetic_data_notice,
  });
});

test('V1 preserves a zero score and the backend negative class and confidence', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => response({
    ...prediction, placement_probability: 0, prediction: 'Not Placed', confidence: 1,
  }));
  const result = await predictExperimentalV1(draft);
  assert.equal(result.probability, 0);
  assert.equal(result.status, 'PLACEMENT RISK');
  assert.equal(result.confidence, 100);
});

for (const [field, value] of [
  ['placement_probability', -0.1], ['placement_probability', 1.1],
  ['placement_probability', '0.8'], ['confidence', null], ['confidence', 1.1],
  ['prediction', 'PLACED'], ['model_version', ''], ['experimental', false],
  ['synthetic_data_notice', null], ['synthetic_data_notice', '   '],
]) {
  test(`V1 rejects malformed ${field}=${JSON.stringify(value)}`, async (t) => {
    t.mock.method(globalThis, 'fetch', async () => response({ ...prediction, [field]: value }));
    await assert.rejects(predictExperimentalV1(draft), /invalid response/);
  });
}

test('V1 rejects missing and non-finite inputs before requesting inference', async (t) => {
  t.mock.method(globalThis, 'fetch', () => assert.fail('Invalid payload reached network'));
  const missing = { ...draft };
  delete missing.codingSkill;
  for (const invalid of [null, missing, { ...draft, cgpa: Infinity }, { ...draft, dsaScore: NaN }]) {
    await assert.rejects(predictExperimentalV1(invalid), /missing or invalid/);
  }
});

for (const status of [401, 403]) {
  test(`V1 retains HTTP ${status} security errors without replaying inference`, async (t) => {
    let requests = 0;
    t.mock.method(globalThis, 'fetch', async () => { requests++; return response({}, status); });
    await assert.rejects(predictExperimentalV1(draft), (error) =>
      error.status === status && /session has expired|Security check failed/.test(error.message));
    assert.equal(requests, 1);
  });
}

test('V1 retains CSRF retrieval rejection before sending the prediction', async (t) => {
  clearRequestIdentity();
  setRequestIdentity('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa');
  t.mock.method(globalThis, 'fetch', async (url) => {
    assert.ok(url.endsWith('/api/auth/csrf'));
    return response({}, 403);
  });
  await assert.rejects(predictExperimentalV1(draft), (error) => error.status === 403);
});

test('V1 rejects a delayed response after the active account changes', async (t) => {
  let finish;
  const started = new Promise((resolve) => {
    t.mock.method(globalThis, 'fetch', () => new Promise((complete) => {
      finish = complete;
      resolve();
    }));
  });
  const pending = predictExperimentalV1(draft);
  await started;
  setRequestIdentity('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb');
  finish(response(prediction));
  await assert.rejects(pending, (error) => error.status === 401 && /session changed/.test(error.message));
});

test('V1 exposes backend field validation without manufacturing a prediction', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => response({
    detail: [{ loc: ['body', 'coding_skills'], msg: 'Input should be a valid integer' }],
  }, 422));
  await assert.rejects(predictExperimentalV1(draft), /Coding.*valid integer/i);
});

test('V1 model unavailability remains an error', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => response({ detail: 'Model unavailable' }, 503));
  await assert.rejects(predictExperimentalV1(draft), /HTTP 503/);
});

test('V1 network failure remains visible', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => { throw new TypeError('offline'); });
  await assert.rejects(predictExperimentalV1(draft), /Cannot reach/);
});
