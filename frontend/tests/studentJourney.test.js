import test from 'node:test';
import assert from 'node:assert/strict';
import { isSyntheticDemo, studentJourney } from '../src/services/studentJourney.js';

test('empty accounts receive creation guidance without a demo profile', () => {
  assert.equal(studentJourney(null, null).stage, 'empty');
});
test('unknown completion never announces prediction readiness', () => {
  assert.equal(studentJourney({ verified: true }, null).stage, 'incomplete');
});
test('resume missing inputs take precedence over a confirmation badge', () => {
  const state = studentJourney({ verified: true }, { profile_complete: false, missing_fields: ['coding_skills', 'dsa_score'] });
  assert.equal(state.stage, 'incomplete');
  assert.deepEqual(state.missing, ['Coding skill', 'DSA score']);
});
test('saved edits require confirmation even when model inputs are complete', () => {
  assert.equal(studentJourney({ verified: false }, { profile_complete: true }).stage, 'confirm');
});
test('ready guidance requires both server completion and explicit confirmation', () => {
  assert.equal(studentJourney({ verified: true }, { profile_complete: true }).stage, 'ready');
});
test('synthetic flag labels the bundle only and cannot imply authentication', () => {
  assert.equal(isSyntheticDemo('synthetic'), true);
  for (const value of ['production', 'true', true, null, '']) assert.equal(isSyntheticDemo(value), false);
});
