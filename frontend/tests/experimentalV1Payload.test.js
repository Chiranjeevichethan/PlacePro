import assert from 'node:assert/strict';
import test from 'node:test';
import { buildExperimentalV1Payload } from '../src/services/experimentalV1Payload.js';
import { buildPredictionPayload } from '../src/services/api.js';

const draft = { branch: 'CSE', collegeTier: 'Tier-2', cgpa: '8', backlogs: '0', codingSkill: '8',
  dsaScore: '7', aptitudeScore: '80', communicationSkill: '7', mlKnowledge: '6', systemDesign: '5',
  internships: '1', projects: '2', certifications: '1', hackathons: '1', openSourceContributions: '0', extracurricular: '2' };

test('V1 keeps exactly the production numeric units and 16 payload keys', () => {
  assert.deepEqual(buildExperimentalV1Payload(draft), buildPredictionPayload(draft));
  const payload = buildExperimentalV1Payload({ ...draft, salary_package_lpa: 12, placement_status: 'Placed', age: 22 });
  assert.equal(Object.keys(payload).length, 16);
  assert.equal(payload.coding_skills, 8);
  assert.equal('salary_package_lpa' in payload, false);
});

test('V1 preserves unseen department identities while production retains its existing ISE mapping', () => {
  assert.equal(buildExperimentalV1Payload({ ...draft, branch: 'ISE' }).branch, 'ISE');
  assert.equal(buildPredictionPayload({ ...draft, branch: 'ISE' }).branch, 'CSE');
  assert.equal(buildExperimentalV1Payload({ ...draft, branch: 'Chemical' }).branch, 'Chemical');
});

for (const [field, min, max] of [['cgpa', 4, 10], ['codingSkill', 1, 10], ['dsaScore', 1, 10],
  ['mlKnowledge', 0, 10], ['systemDesign', 0, 10], ['aptitudeScore', 20, 100], ['communicationSkill', 1, 10]]) {
  test(`V1 matches production score bounds for ${field}`, () => {
    for (const value of [min, max]) assert.doesNotThrow(() => buildExperimentalV1Payload({ ...draft, [field]: value }));
    for (const value of [min - 0.1, max + 0.1, null, '', ' ', false, Infinity, NaN]) {
      assert.throws(() => buildExperimentalV1Payload({ ...draft, [field]: value }), /missing or invalid/);
    }
  });
}

for (const field of ['backlogs', 'projects', 'certifications', 'internships', 'hackathons', 'openSourceContributions', 'extracurricular']) {
  test(`V1 validates ${field} as a nonnegative unbounded integer without rounding`, () => {
    for (const value of [0, 1000]) assert.doesNotThrow(() => buildExperimentalV1Payload({ ...draft, [field]: value }));
    for (const value of [-1, 1.5, '', null]) assert.throws(() => buildExperimentalV1Payload({ ...draft, [field]: value }));
  });
}

test('unknown/missing dropdown values and missing draft fail before inference', () => {
  for (const invalid of [null, {}, { ...draft, branch: 'EEE' }, { ...draft, collegeTier: 'Tier 2' }]) {
    assert.throws(() => buildExperimentalV1Payload(invalid), /missing or invalid/);
  }
});
