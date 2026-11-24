import './authFixtures.js';
import test from 'node:test';
import assert from 'node:assert/strict';
import { createProfileController, createProfileRefreshHandlers, createPredictionController, predictionStamp, profileStamp, requireSource } from '../src/services/profileState.js';
import { buildProfileCorrection } from '../src/services/profileReview.js';
import { updateStudentProfile, verifyStudentProfile } from '../src/services/api.js';

const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; };
const response = (id = 'student-a', revision = 1) => ({ profile: { profile_id: id, revision, verified: true, personal: { name: id } }, completion: {} });

const handlersFor = (controller, readProfileId) => createProfileRefreshHandlers({
  refresh: (id) => controller.refresh(id), readProfileId,
  profileIdKey: 'placepro_profile_id', profileKey: 'placepro_profile',
});

test('another tab clearing the old mirror selects the active ID and rejects an older GET', async () => {
  const old = deferred();
  const mirrors = [];
  const controller = createProfileController({ profileId: 'student-a',
    fetchProfile: (id) => id === 'student-a' ? old.promise : Promise.resolve(response(id)),
    mirror: (id) => mirrors.push(id),
  });
  controller.apply(response());
  const pending = controller.refresh();
  const handlers = handlersFor(controller, () => 'student-b');
  await handlers.onStorage({ key: 'placepro_profile', newValue: null });
  old.resolve(response('student-a', 9));
  await pending;
  assert.equal(controller.getSnapshot().data.profile.profile_id, 'student-b');
  assert.equal(mirrors.at(-1), 'student-b');
});

test('a queued ID event cannot restore an ID superseded in shared storage', async () => {
  const controller = createProfileController({ profileId: 'student-a', fetchProfile: async (id) => response(id) });
  controller.apply(response());
  await handlersFor(controller, () => 'student-b').onStorage({ key: 'placepro_profile_id', newValue: 'student-a' });
  assert.equal(controller.getSnapshot().profileId, 'student-b');
  assert.equal(controller.getSnapshot().data.profile.profile_id, 'student-b');
});

test('focus follows the shared active ID; unrelated storage events do not refresh', async () => {
  const requested = [];
  const controller = createProfileController({ profileId: 'student-a', fetchProfile: async (id) => {
    requested.push(id); throw new Error('new profile unavailable');
  } });
  controller.apply(response());
  const handlers = handlersFor(controller, () => 'student-b');
  handlers.onStorage({ key: 'unrelated' });
  assert.deepEqual(requested, []);
  await handlers.onFocus();
  assert.deepEqual(requested, ['student-b']);
  assert.equal(controller.getSnapshot().profileId, 'student-b');
  assert.equal(controller.getSnapshot().data, null);
  assert.equal(controller.getSnapshot().profileMissing, false);
});

test('initial profile and same-profile refresh preserve data on network failure', async () => {
  let failing = false;
  const controller = createProfileController({ profileId: 'student-a', fetchProfile: async () => {
    if (failing) throw new Error('offline'); return response();
  } });
  await controller.refresh();
  const saved = controller.getSnapshot().data;
  failing = true;
  await controller.refresh();
  assert.equal(controller.getSnapshot().data, saved);
  assert.equal(controller.getSnapshot().error, 'offline');
  assert.equal(controller.getSnapshot().status, 'error');
});

test('switch clears prior profile and mirror immediately, then ignores late response', async () => {
  const first = deferred(), second = deferred();
  const mirrors = [];
  const controller = createProfileController({ profileId: 'student-a', fetchProfile: (id) => id === 'student-a' ? first.promise : second.promise,
    mirror: (id, data) => mirrors.push([id, data]) });
  controller.apply(response());
  const old = controller.refresh();
  const latest = controller.refresh('student-b');
  assert.equal(controller.getSnapshot().data, null);
  assert.deepEqual(mirrors.at(-1), ['student-b', null]);
  second.resolve(response('student-b'));
  await latest;
  first.resolve(response('student-a', 8));
  await old;
  assert.equal(controller.getSnapshot().data.profile.profile_id, 'student-b');
});

test('failed switch cannot display previous profile or enable false 404 creation', async () => {
  const controller = createProfileController({ profileId: 'student-a', fetchProfile: async () => { throw new Error('503'); } });
  controller.apply(response());
  await controller.refresh('student-b');
  assert.equal(controller.getSnapshot().data, null);
  assert.equal(controller.getSnapshot().profileMissing, false);
});

test('real initial 404 retains explicit missing state', async () => {
  const controller = createProfileController({ profileId: 'student-a', fetchProfile: async () => {
    throw Object.assign(new Error('missing'), { code: 'PROFILE_NOT_FOUND' });
  } });
  await controller.refresh();
  assert.equal(controller.getSnapshot().profileMissing, true);
});

test('successful save suppresses earlier GET and preserves new revision', async () => {
  const pending = deferred();
  const controller = createProfileController({ profileId: 'student-a', fetchProfile: () => pending.promise });
  const request = controller.refresh();
  controller.apply(response('student-a', 2));
  pending.resolve(response());
  await request;
  assert.equal(controller.getSnapshot().data.profile.revision, 2);
});

test('older mutation response and foreign identity cannot replace selection', () => {
  const controller = createProfileController({ profileId: 'student-a', fetchProfile: async () => response() });
  controller.apply(response('student-a', 3));
  assert.equal(controller.apply(response('student-a', 2)), false);
  assert.throws(() => controller.apply(response('student-b', 4)), /unexpected profile/);
  assert.equal(controller.getSnapshot().data.profile.revision, 3);
});

test('malformed/foreign GET is rejected without corrupting last valid state', async () => {
  const controller = createProfileController({ profileId: 'student-a', fetchProfile: async () => response('student-b') });
  controller.apply(response());
  await controller.refresh();
  assert.equal(controller.getSnapshot().data.profile.profile_id, 'student-a');
  assert.match(controller.getSnapshot().error, /unexpected profile/);
});

test('cancellation prevents detached GET from mirroring state', async () => {
  const pending = deferred();
  let writes = 0;
  const controller = createProfileController({ profileId: 'student-a', fetchProfile: () => pending.promise, mirror: () => writes++ });
  const request = controller.refresh();
  controller.cancel();
  pending.resolve(response());
  await request;
  assert.equal(writes, 0);
});

test('identity/revision/confirmation stamps isolate equal input profiles', () => {
  const a = profileStamp('student-a', response().profile);
  const b = profileStamp('student-b', response('student-b').profile);
  assert.notEqual(a, b);
  assert.notEqual(a, profileStamp('student-a', response('student-a', 2).profile));
  assert.notEqual(a, profileStamp('student-a', { ...response().profile, verified: false }));
  assert.notEqual(predictionStamp(a, { cgpa: 8 }), predictionStamp(b, { cgpa: 8 }));
});

test('correction retains the revision of the reviewed baseline', () => {
  const profile = { ...response('student-a', 3).profile, education: { cgpa: 8 } };
  const payload = buildProfileCorrection(profile, { cgpa: '9' });
  assert.equal(payload.revision, 3);
  assert.equal(payload.education.cgpa, 9);
  assert.equal(profile.education.cgpa, 8);
});

test('derived responses must match both source identity and revision', () => {
  const profile = response().profile;
  assert.equal(requireSource({ profile_id: 'student-a', source_revision: 1 }, profile).source_revision, 1);
  for (const value of [{ profile_id: 'student-b', source_revision: 1 }, { profile_id: 'student-a', source_revision: 2 }, {}]) {
    assert.throws(() => requireSource(value, profile), /Profile changed/);
  }
});

test('repeated prediction clicks deliver once and retain submitted values', async () => {
  const pending = deferred();
  const inputs = { cgpa: 8 };
  let calls = 0, used;
  const controller = createPredictionController(async (value) => { calls++; used = value; return pending.promise; });
  const request = controller.run('first', inputs);
  await controller.run('first', inputs);
  inputs.cgpa = 9;
  pending.resolve({ probability: 80 });
  await request;
  assert.equal(calls, 1);
  assert.equal(used.cgpa, 8);
  assert.equal(controller.getSnapshot().result.probability, 80);
});

test('placement/salary input change hides prior result and ignores delayed response', async () => {
  const pending = deferred();
  const controller = createPredictionController(() => pending.promise);
  const request = controller.run('old-inputs', { cgpa: 8 });
  controller.select('new-inputs');
  pending.resolve({ salary: 15 });
  await request;
  assert.equal(controller.getSnapshot().result, null);
  assert.equal(controller.getSnapshot().busy, false);
});

test('prediction profile switch ignores late response and permits a new request', async () => {
  const pending = deferred();
  const controller = createPredictionController((value) => value.profile === 'a' ? pending.promise : Promise.resolve({ probability: 20 }));
  const old = controller.run('profile-a', { profile: 'a' });
  await controller.run('profile-b', { profile: 'b' });
  pending.resolve({ probability: 90 });
  await old;
  assert.equal(controller.getSnapshot().result.probability, 20);
});

test('failed prediction retry retains a valid result for unchanged inputs', async () => {
  let failed = false;
  const controller = createPredictionController(async () => { if (failed) throw new Error('503'); return { salary: 12 }; });
  await controller.run('same', {});
  failed = true;
  await controller.run('same', {});
  assert.deepEqual(controller.getSnapshot().result, { salary: 12 });
  assert.equal(controller.getSnapshot().error, '503');
});

test('detached prediction never accepts its response', async () => {
  const pending = deferred();
  const controller = createPredictionController(() => pending.promise);
  const request = controller.run('old', {});
  controller.cancel();
  pending.resolve({ salary: 12 });
  await request;
  assert.equal(controller.getSnapshot().result, null);
});

test('PUT conflict exposes reload instruction and sends revision', async (context) => {
  let body;
  context.mock.method(globalThis, 'fetch', async (_, options) => {
    body = JSON.parse(options.body);
    return { ok: false, status: 409 };
  });
  await assert.rejects(updateStudentProfile('student-a', response().profile), (error) => error.status === 409 && /Reload/.test(error.message));
  assert.equal(body.revision, 1);
});

test('confirmation conflict cannot be mistaken for success', async (context) => {
  context.mock.method(globalThis, 'fetch', async () => ({ ok: false, status: 409, json: async () => ({ detail: 'conflict' }) }));
  await assert.rejects(verifyStudentProfile(response().profile), (error) => error.status === 409 && /latest values/.test(error.message));
});
