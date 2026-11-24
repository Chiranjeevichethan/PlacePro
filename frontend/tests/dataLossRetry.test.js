import './authFixtures.js';
import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile } from 'node:fs/promises';
import { transformWithOxc } from 'vite';
import { createOwnedProfilesController } from '../src/services/ownedProfiles.js';
import { fetchStudentProfile } from '../src/services/api.js';
import { authSession } from '../src/services/auth.js';
import { rememberCSRF } from '../src/services/apiTransport.js';
import { DEFAULT_RESUME_DOCUMENT } from '../src/services/resumeBuilder.js';

// Exercise the real component handlers/state and authenticated API transport.
// Hooks run in a small in-memory driver; these are not DOM/browser assertions.
const moduleURL = (source) => 'data:text/javascript;base64,' + Buffer.from(source).toString('base64');
const hooksURL = moduleURL(`
  let active;
  export function useState(initial) {
    const driver = active, index = driver.cursor++;
    if (!(index in driver.state)) driver.state[index] = typeof initial === 'function' ? initial() : initial;
    return [driver.state[index], value => {
      driver.state[index] = typeof value === 'function' ? value(driver.state[index]) : value;
    }];
  }
  export function useMemo(callback) { return callback(); }
  export function useEffect(callback, dependencies) {
    const driver = active, index = driver.cursor++;
    const old = driver.dependencies[index];
    if (!old || dependencies.some((value, i) => value !== old[i])) {
      driver.dependencies[index] = dependencies;
      driver.effects.push(() => {
        driver.cleanup[index]?.();
        driver.cleanup[index] = callback();
      });
    }
  }
  export function createDriver(Component) {
    const driver = { state: [], dependencies: [], cleanup: [] };
    return {
      render(props = {}) {
        active = driver; driver.cursor = 0; driver.effects = [];
        const tree = Component(props);
        active = null;
        driver.effects.forEach(effect => effect());
        return tree;
      },
      dispose() { driver.cleanup.forEach(cleanup => cleanup?.()); },
    };
  }
`);
const { createDriver } = await import(hooksURL);
const contextURL = moduleURL(`export function useStudentProfileContext() { return { profileId: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa' }; }`);
const leafURL = moduleURL('export default function StudentForm() { return null; }');
async function component(relativePath) {
  const url = new URL(relativePath, import.meta.url);
  let source = await readFile(url, 'utf8');
  for (const match of [...source.matchAll(/from\s+(['"])([^'"]+)\1/g)]) {
    const specifier = match[2];
    const resolved = specifier === 'react' ? hooksURL
      : specifier.includes('useStudentProfileContext') ? contextURL
        : specifier === './StudentForm' ? leafURL
          : new URL(specifier, url).href;
    source = source.replace(match[0], 'from ' + JSON.stringify(resolved));
  }
  const { code } = await transformWithOxc(source, url.pathname, { jsx: { runtime: 'automatic' }, sourcemap: false });
  return (await import(moduleURL(code.replaceAll('"react/jsx-runtime"', JSON.stringify(import.meta.resolve('react/jsx-runtime')))))).default;
}
const V1 = await component('../src/components/ExperimentalV1Form.jsx');
const ResumeBuilder = await component('../src/pages/StudentResumeBuilder.jsx');
const response = (body, status = 200) => new Response(JSON.stringify(body), { status });
const id = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const otherId = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
const profile = (profileId = id, revision = 1) => ({ profile: { profile_id: profileId, revision,
  verified: true, education: { cgpa: 8.1 }, ml_inputs: { coding_skills: 8, aptitude_score: 80 } }, completion: {} });
const session = { account: { account_id: id, email: 'synthetic@example.test' },
  idle_expires_at: '2026-11-24T00:00:00Z', absolute_expires_at: '2026-11-24T12:00:00Z' };
const settle = () => new Promise(resolve => setImmediate(resolve));
function find(tree, predicate) {
  if (!tree || typeof tree !== 'object') return null;
  if (predicate(tree)) return tree;
  for (const child of [tree.props?.children].flat(Infinity)) {
    const found = find(child, predicate);
    if (found) return found;
  }
  return null;
}
const button = (tree, label) => find(tree, node => node.type === 'button' && node.props.children === label);
const click = async (tree, label) => { await button(tree, label).props.onClick(); await settle(); };
const field = (tree, name) => find(tree, node => node.props?.id === name);
const hasNotice = (tree, text) => Boolean(find(tree, node => node.type === 'p' && node.props.children === text));

for (const failure of ['503', 'network']) {
  test(`V1 retains its workspace, manual edits and blanks through repeated ${failure} list failures and retry`, async t => {
    let failing = false, latest = profile(), profileReads = 0;
    t.mock.method(globalThis, 'fetch', async url => {
      if (url.endsWith('/api/account/profiles')) {
        if (failing && failure === 'network') throw new TypeError('offline');
        return failing ? response({}, 503) : response({ profiles: [{ profile_id: id }] });
      }
      profileReads++;
      return response(latest);
    });
    const selected = [];
    const controller = createOwnedProfilesController({ fetchProfile: fetchStudentProfile, onSelected: value => selected.push(value) });
    await controller.reload();
    let driver, key, mounts = 0;
    const render = () => {
      const state = controller.getSnapshot();
      // Mirror the actual workspace/form keys, without changing their production code.
      if (key !== state.profileId) { driver = createDriver(V1); key = state.profileId; mounts++; }
      return driver.render({ profile: state.data?.profile }).props.children.props;
    };
    const originalData = controller.getSnapshot().data;
    let form = render();
    form.onDraftChange({ ...form.draft, cgpa: '9.9', aptitudeScore: '' });
    failing = true;
    for (let attempt = 0; attempt < 2; attempt++) {
      await controller.reload(id); // Same reload used by window focus and Retry.
      form = render();
      assert.equal(controller.getSnapshot().profileId, id);
      assert.equal(controller.getSnapshot().data, originalData);
      assert.deepEqual(controller.getSnapshot().ids, [id]);
      assert.equal(controller.getSnapshot().listLoading, false);
      assert.match(controller.getSnapshot().listError, /retry/i);
      assert.equal(form.draft.cgpa, '9.9');
      assert.equal(form.draft.aptitudeScore, '');
      assert.equal(mounts, 1);
    }
    assert.equal(profileReads, 1, 'A failed list must not fetch or select a different profile.');
    latest = profile(id, 2);
    latest.profile.ml_inputs.coding_skills = 9;
    latest.profile.ml_inputs.aptitude_score = 72;
    failing = false;
    await controller.reload(id);
    form = render();
    assert.equal(form.draft.cgpa, '9.9');
    assert.equal(form.draft.aptitudeScore, '');
    assert.equal(form.draft.codingSkill, '9');
    assert.equal(controller.getSnapshot().listError, null);
    assert.equal(mounts, 1);
    assert.ok(selected.every(value => value === id));
  });
}

for (const status of [401, 403]) {
  test(`actual profile-list ${status} clears private profile selection instead of treating denial as an outage`, async t => {
    let denied = false;
    t.mock.method(globalThis, 'fetch', async url => url.endsWith('/api/auth/session') ? response(session)
      : url.endsWith('/api/account/profiles') ? denied ? response({}, status) : response({ profiles: [{ profile_id: id }] })
        : response(profile()));
    await authSession.restore();
    const controller = createOwnedProfilesController({ fetchProfile: fetchStudentProfile });
    await controller.reload();
    denied = true;
    await controller.reload();
    assert.equal(controller.getSnapshot().profileId, null);
    assert.equal(controller.getSnapshot().data, null);
    assert.deepEqual(controller.getSnapshot().ids, []);
    assert.equal(authSession.getSnapshot().status, status === 401 ? 'anonymous' : 'authenticated');
  });
}

test('successful ownership refresh still removes unavailable selections and clears an empty account', async t => {
  let ids = [id];
  const reads = [];
  t.mock.method(globalThis, 'fetch', async url => {
    if (url.endsWith('/api/account/profiles')) return response({ profiles: ids.map(profile_id => ({ profile_id })) });
    const requested = url.split('/').at(-1); reads.push(requested); return response(profile(requested));
  });
  const controller = createOwnedProfilesController({ fetchProfile: fetchStudentProfile });
  await controller.reload();
  ids = [otherId];
  await controller.reload();
  assert.equal(controller.getSnapshot().profileId, otherId);
  assert.deepEqual(reads, [id, otherId]);
  ids = [];
  await controller.reload();
  assert.equal(controller.getSnapshot().profileId, null);
  assert.equal(controller.getSnapshot().data, null);
});

async function resume(t, saveResponse) {
  const saved = { ...structuredClone(DEFAULT_RESUME_DOCUMENT), revision: 4, summary: 'Saved summary' };
  saved.personal.name = 'Saved Name';
  const calls = [];
  t.mock.method(globalThis, 'fetch', async (url, init) => {
    const call = { url, method: init?.method || 'GET', headers: init?.headers,
      body: init?.body ? JSON.parse(init.body) : null };
    calls.push(call);
    if (url.endsWith('/api/auth/session')) return response(session);
    if (url.endsWith('/api/auth/csrf')) return response({ csrf_token: 'b'.repeat(64) });
    if (call.method === 'GET') return response({ draft: structuredClone(saved), has_saved_draft: true });
    return saveResponse(call, calls);
  });
  globalThis.window = { addEventListener() {}, removeEventListener() {} };
  const driver = createDriver(ResumeBuilder);
  t.after(() => { driver.dispose(); delete globalThis.window; });
  driver.render();
  await settle();
  return { driver, calls, saved };
}

for (const failure of ['503', 'network']) {
  test(`resume Retry saves the latest edits and blanks after repeated ${failure} failures, without reloading`, async t => {
    let attempts = 0, confirm;
    const pending = new Promise(resolve => { confirm = resolve; });
    const { driver, calls } = await resume(t, () => {
      attempts++;
      if (attempts === 3) return pending;
      if (failure === 'network') throw new TypeError('offline');
      return response({ detail: 'Temporary outage.' }, 503);
    });
    let tree = driver.render();
    field(tree, 'resume-personal-name').props.onChange('Unsaved Name');
    field(tree, 'resume-summary').props.onChange('');
    await click(driver.render(), 'Save draft');
    tree = driver.render();
    assert.equal(field(tree, 'resume-personal-name').props.value, 'Unsaved Name');
    assert.equal(field(tree, 'resume-summary').props.value, '');
    assert.ok(hasNotice(tree, 'Unsaved changes. Save your draft before closing this page.'));
    field(tree, 'resume-personal-name').props.onChange('Latest Edited Name');
    await button(driver.render(), 'Retry').props.onClick();
    tree = driver.render();
    assert.equal(field(tree, 'resume-personal-name').props.value, 'Latest Edited Name');
    assert.equal(field(tree, 'resume-summary').props.value, '');
    assert.ok(hasNotice(tree, 'Unsaved changes. Save your draft before closing this page.'));
    const retry = button(tree, 'Retry').props.onClick();
    await settle();
    tree = driver.render();
    assert.ok(hasNotice(tree, 'Unsaved changes. Save your draft before closing this page.'), 'Pending persistence must not mark the document saved.');
    assert.ok(!hasNotice(tree, 'Resume draft saved to your account.'));
    confirm(response({ draft: { ...calls.at(-1).body, revision: 5 }, has_saved_draft: true }));
    await retry;
    tree = driver.render();
    assert.equal(field(tree, 'resume-personal-name').props.value, 'Latest Edited Name');
    assert.equal(field(tree, 'resume-summary').props.value, '');
    assert.ok(hasNotice(tree, 'Resume draft saved to your account.'));
    assert.ok(!hasNotice(tree, 'Unsaved changes. Save your draft before closing this page.'));
    assert.deepEqual(calls.map(call => call.method), ['GET', 'PUT', 'PUT', 'PUT']);
    assert.deepEqual(calls.slice(1).map(call => call.body.revision), [4, 4, 4]);
    assert.deepEqual(calls.slice(1).map(call => call.body.personal.name), ['Unsaved Name', 'Latest Edited Name', 'Latest Edited Name']);
    assert.ok(calls.slice(1).every(call => call.body.summary === '' && call.headers['x-csrf-token'] === 'a'.repeat(64)));
  });
}

test('resume 401 invalidates authentication and never retries a denied save', async t => {
  const { driver, calls } = await resume(t, () => response({ detail: 'Authentication is required.' }, 401));
  await authSession.restore(); rememberCSRF('a'.repeat(64));
  field(driver.render(), 'resume-personal-name').props.onChange('Unsaved Name');
  await click(driver.render(), 'Save draft');
  const retry = button(driver.render(), 'Retry');
  assert.equal(authSession.getSnapshot().status, 'anonymous');
  assert.equal(retry.props.disabled, true);
  const count = calls.length;
  await retry.props.onClick();
  assert.equal(calls.length, count);
  assert.ok(!hasNotice(driver.render(), 'Resume draft saved to your account.'));
});

test('resume repeated 403 denies persistence; explicit Retry obtains fresh CSRF without losing edits', async t => {
  let attempts = 0;
  const { driver, calls } = await resume(t, call => ++attempts < 3
    ? response({ detail: 'CSRF validation failed.' }, 403)
    : response({ draft: { ...call.body, revision: 5 }, has_saved_draft: true }));
  field(driver.render(), 'resume-personal-name').props.onChange('Unsaved Name');
  field(driver.render(), 'resume-summary').props.onChange('');
  await click(driver.render(), 'Save draft');
  assert.equal(attempts, 1, 'Transport must not silently replay a rejected mutation.');
  assert.ok(!hasNotice(driver.render(), 'Resume draft saved to your account.'));
  await button(driver.render(), 'Retry').props.onClick();
  assert.equal(attempts, 2);
  assert.equal(field(driver.render(), 'resume-personal-name').props.value, 'Unsaved Name');
  assert.equal(field(driver.render(), 'resume-summary').props.value, '');
  assert.ok(!hasNotice(driver.render(), 'Resume draft saved to your account.'));
  await button(driver.render(), 'Retry').props.onClick();
  assert.equal(attempts, 3);
  assert.ok(hasNotice(driver.render(), 'Resume draft saved to your account.'));
  assert.equal(calls.filter(call => call.method === 'GET' && !call.url.endsWith('/csrf')).length, 1);
  assert.equal(calls.filter(call => call.url.endsWith('/csrf')).length, 2);
  assert.deepEqual(calls.filter(call => call.method === 'PUT').map(call => call.headers['x-csrf-token']),
    ['a'.repeat(64), 'b'.repeat(64), 'b'.repeat(64)]);
});

test('resume conflict retries preserve the current document and original revision without loading stale data', async t => {
  const { driver, calls } = await resume(t, () => response({ detail: 'The resume changed. Reload and review it before continuing.' }, 409));
  field(driver.render(), 'resume-personal-name').props.onChange('Unsaved Name');
  await click(driver.render(), 'Save draft');
  await button(driver.render(), 'Retry').props.onClick();
  assert.deepEqual(calls.map(call => call.method), ['GET', 'PUT', 'PUT']);
  assert.ok(calls.slice(1).every(call => call.body.revision === 4));
  assert.equal(field(driver.render(), 'resume-personal-name').props.value, 'Unsaved Name');
  assert.ok(!hasNotice(driver.render(), 'Resume draft saved to your account.'));
});
