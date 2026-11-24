import test, { beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { transformWithOxc } from 'vite';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { authSession, login } from '../src/services/auth.js';
import { clearRequestIdentity, rememberCSRF } from '../src/services/apiTransport.js';
import { loadResumeReview } from '../src/services/profileReview.js';
import { createProfileController } from '../src/services/profileState.js';

// Render the real SessionApp branch logic and StudentProfile page in memory.
// Network and leaf components are probes. This tests rendered authorization /
// parent conditions, not a live browser, DOM events, or modal hook state.
const moduleURL = (code) => 'data:text/javascript;base64,' + Buffer.from(code).toString('base64');
async function jsxModule(source, filename) {
  const { code } = await transformWithOxc(source, filename, { jsx: { runtime: 'automatic' }, sourcemap: false });
  return import(moduleURL(code
    .replaceAll('"react/jsx-runtime"', JSON.stringify(import.meta.resolve('react/jsx-runtime')))
    .replaceAll('"react"', JSON.stringify(import.meta.resolve('react')))));
}
const authURL = new URL('../src/services/auth.js', import.meta.url).href;
const appSource = await readFile(new URL('../src/App.jsx', import.meta.url), 'utf8');
const sessionBody = appSource.match(/function SessionApp\(\) \{[\s\S]*?\n\}\r?\n\r?\nfunction App\(/)?.[0];
assert.ok(sessionBody, 'Locate the actual SessionApp function without changing application source');
const { SessionGate } = await jsxModule(`
  import { useEffect } from "react";
  import { authSession } from ${JSON.stringify(authURL)};
  function useAuth() { return authSession.getSnapshot(); }
  function Login() { return <div data-probe="login" />; }
  function StudentProfileProvider({ children, accountId }) {
    return <div data-probe="private-provider" data-account={accountId}>{children}</div>;
  }
  function ProfileWorkspace() { return <div data-probe="private-workspace" />; }
  ${sessionBody.slice(0, sessionBody.lastIndexOf('\nfunction App('))}
  export { SessionApp as SessionGate };
`, 'SessionGateProbe.jsx');

const contextURL = moduleURL(`
  let context;
  export function setContext(next) { context = next; }
  export function useStudentProfileContext() { return context; }
`);
const { setContext } = await import(contextURL);
const leafURL = moduleURL(`
  import { createElement } from ${JSON.stringify(import.meta.resolve('react'))};
  export default function Probe(props) {
    return createElement('div', { 'data-probe': props.preservedProfile ? 'resume-modal' : 'other-leaf' });
  }
`);
let profileSource = await readFile(new URL('../src/pages/StudentProfile.jsx', import.meta.url), 'utf8');
for (const specifier of ['../components/IconMark', '../components/EditProfileModal', '../components/ResumeUploadModal']) {
  profileSource = profileSource.replace(JSON.stringify(specifier), JSON.stringify(leafURL));
}
profileSource = profileSource
  .replace('"../hooks/useStudentProfileContext"', JSON.stringify(contextURL))
  .replace('"../services/api"', JSON.stringify(new URL('../src/services/api.js', import.meta.url).href))
  .replace("'../services/retryIntent'", JSON.stringify(new URL('../src/services/retryIntent.js', import.meta.url).href))
  .replace("'../services/profileConfig'", JSON.stringify(new URL('../src/services/profileConfig.js', import.meta.url).href));
const { default: ProfilePage } = await jsxModule(profileSource, 'StudentProfileProbe.jsx');

const accountId = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const token = 'a'.repeat(64);
const response = (body, status = 200) => new Response(JSON.stringify(body), { status });
const session = () => ({ account: { account_id: accountId, email: 'synthetic@example.test' },
  idle_expires_at: '2026-11-10T00:00:00+00:00', absolute_expires_at: '2026-11-10T01:00:00+00:00' });
const profile = () => ({ profile_id: 'synthetic-owned', revision: 5, verified: true,
  personal: { name: 'Synthetic Current Learner', email: 'current@example.test' },
  education: { branch: 'CSE', cgpa: 8.2 }, skills: {}, experience: [],
  projects: [], internships: [], certifications: [], achievements: {}, ml_inputs: {}, additional_info: {} });
const experience = { role: 'Volunteer Developer', company: 'Synthetic Community Workshop',
  duration: 'Jan 2026 - Mar 2026', technologies: ['HTML', 'CSS'] };
const gateMarkup = () => renderToStaticMarkup(createElement(SessionGate));
function deferred() {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
}
async function authenticate(t) {
  t.mock.method(globalThis, 'fetch', async () => response(session()));
  await authSession.restore();
  assert.equal(authSession.getSnapshot().status, 'authenticated');
}
beforeEach(() => { clearRequestIdentity(); });

test('two initial session 401s render login; a subsequent valid login restores the private workspace', async (t) => {
  const first = deferred(), second = deferred();
  let requests = 0;
  t.mock.method(globalThis, 'fetch', (url, options) => {
    assert.ok(url.endsWith('/api/auth/session'));
    assert.equal(options.credentials, 'include');
    return ++requests === 1 ? first.promise : second.promise;
  });
  const pending1 = authSession.restore(), pending2 = authSession.restore();
  second.resolve(response({ detail: 'Authentication is required.' }, 401));
  await pending2;
  first.resolve(response({ detail: 'Authentication is required.' }, 401));
  await pending1;
  assert.equal(requests, 2);
  assert.match(gateMarkup(), /data-probe="login"/);
  assert.doesNotMatch(gateMarkup(), /private-provider|private-workspace/);
  t.mock.method(globalThis, 'fetch', async (url) =>
    response(url.endsWith('/login-challenge') ? { csrf_token: token } : session()));
  await login('synthetic@example.test', 'Synthetic password used only by the mock');
  assert.match(gateMarkup(), /data-probe="private-workspace"/);
});

test('an initial 401 arriving after valid login cannot remove its authenticated workspace', async (t) => {
  const initial = deferred();
  t.mock.method(globalThis, 'fetch', (url) => url.endsWith('/session') ? initial.promise
    : Promise.resolve(response(url.endsWith('/login-challenge') ? { csrf_token: token } : session())));
  const restoring = authSession.restore();
  await login('synthetic@example.test', 'Synthetic password used only by the mock');
  const accepted = authSession.getSnapshot();
  initial.resolve(response({}, 401));
  await restoring;
  assert.equal(authSession.getSnapshot(), accepted);
  assert.match(gateMarkup(), /data-probe="private-workspace"/);
});

test('successful background restoration preserves authenticated identity and workspace epoch', async (t) => {
  await authenticate(t);
  const accepted = authSession.getSnapshot();
  const pending = deferred();
  t.mock.method(globalThis, 'fetch', () => pending.promise);
  const restoring = authSession.restore({ background: true });
  assert.equal(authSession.getSnapshot(), accepted);
  assert.match(gateMarkup(), /data-probe="private-workspace"/);
  pending.resolve(response(session()));
  await restoring;
  assert.equal(authSession.getSnapshot().epoch, accepted.epoch);
  assert.deepEqual(authSession.getSnapshot().account, accepted.account);
});

test('a current background session 401 removes the private parent and increments its epoch', async (t) => {
  await authenticate(t);
  const epoch = authSession.getSnapshot().epoch;
  t.mock.method(globalThis, 'fetch', async () => response({}, 401));
  await authSession.restore({ background: true });
  assert.equal(authSession.getSnapshot().account, null);
  assert.equal(authSession.getSnapshot().epoch, epoch + 1);
  assert.match(authSession.getSnapshot().error, /expired/);
  assert.match(gateMarkup(), /data-probe="login"/);
  assert.doesNotMatch(gateMarkup(), /private-provider|private-workspace/);
});

test('a superseded background 401 cannot discard a newer valid session restoration', async (t) => {
  await authenticate(t);
  const older = deferred(), newer = deferred();
  let requests = 0;
  t.mock.method(globalThis, 'fetch', () => ++requests === 1 ? older.promise : newer.promise);
  const p1 = authSession.restore({ background: true }), p2 = authSession.restore({ background: true });
  newer.resolve(response(session())); await p2;
  const accepted = authSession.getSnapshot();
  older.resolve(response({}, 401)); await p1;
  assert.equal(authSession.getSnapshot(), accepted);
  assert.match(gateMarkup(), /data-probe="private-workspace"/);
});

test('session expiry during extraction rejects a late valid preview before it can reach the review', async (t) => {
  await authenticate(t); rememberCSRF(token);
  const extraction = deferred();
  const original = profile();
  const before = structuredClone(original);
  t.mock.method(globalThis, 'fetch', (url) => url.endsWith('/resume-preview') ? extraction.promise
    : Promise.resolve(response({}, 401)));
  const uploading = loadResumeReview(new File(['synthetic'], 'Synthetic-Resume.docx'), original);
  // Attach rejection handling before the deliberately delayed response completes.
  const rejected = assert.rejects(uploading, /session changed/);
  await authSession.restore({ background: true });
  extraction.resolve(response({ profile: { ...profile(), experience: [experience] }, completion: {} }));
  await rejected;
  assert.deepEqual(original, before);
  assert.doesNotMatch(gateMarkup(), /private-workspace/);
});

test('resume-preview 401 clears the authenticated workspace and exposes no extracted values', async (t) => {
  await authenticate(t); rememberCSRF(token);
  t.mock.method(globalThis, 'fetch', async () => response({ detail: 'Authentication is required.' }, 401));
  await assert.rejects(loadResumeReview(new File(['synthetic'], 'Synthetic-Resume.docx'), profile()));
  assert.equal(authSession.getSnapshot().status, 'anonymous');
  const markup = gateMarkup();
  assert.match(markup, /data-probe="login"/);
  assert.doesNotMatch(markup, /private-workspace|Volunteer Developer|Synthetic Community Workshop/);
});

test('temporary background failure replaces private content with a visible unavailable state', async (t) => {
  await authenticate(t);
  t.mock.method(globalThis, 'fetch', async () => response({}, 503));
  await authSession.restore({ background: true });
  const markup = gateMarkup();
  assert.match(markup, /PlacePro is unavailable/);
  assert.doesNotMatch(markup, /private-workspace|private-provider/);
});

function pageContext(overrides = {}) {
  return { profileId: 'synthetic-owned', rawProfile: profile(), profile: null,
    loading: false, error: null, profileMissing: false, resumeDraft: null,
    refetch() {}, applyUpdatedProfile() {}, setPendingResumeDraft() {}, clearPendingResumeDraft() {}, ...overrides };
}
for (const [name, overrides, expected] of [
  ['normal open review', {}, true],
  ['profile loading', { loading: true }, false],
  ['profile error', { error: 'Unable to load your profile.' }, false],
  ['missing-profile onboarding', { error: 'Profile not found.', profileMissing: true }, true],
]) {
  test(`actual StudentProfile resume mount condition: ${name}`, () => {
    setContext(pageContext(overrides));
    const markup = renderToStaticMarkup(createElement(ProfilePage, { resumeOpen: true }));
    assert.equal(markup.includes('data-probe="resume-modal"'), expected);
  });
}
test('closing the parent resume request removes its modal even with an available profile', () => {
  setContext(pageContext());
  const markup = renderToStaticMarkup(createElement(ProfilePage, { resumeOpen: false }));
  assert.doesNotMatch(markup, /data-probe="resume-modal"/);
});

for (const status of [403, 404]) {
  test(`ownership denial ${status} after a valid profile clears private data and the resume modal`, async () => {
    const controller = createProfileController({ profileId: 'synthetic-owned',
      fetchProfile: async () => { throw Object.assign(new Error('Profile access denied.'), { status }); } });
    controller.apply({ profile: profile() });
    setContext(pageContext({ rawProfile: controller.getSnapshot().data.profile }));
    assert.match(renderToStaticMarkup(createElement(ProfilePage, { resumeOpen: true })), /resume-modal/);
    await controller.refresh();
    const denied = controller.getSnapshot();
    assert.equal(denied.data, null);
    assert.equal(denied.profileMissing, false);
    setContext(pageContext({ rawProfile: denied.data?.profile ?? null, error: denied.error,
      profileMissing: denied.profileMissing }));
    const markup = renderToStaticMarkup(createElement(ProfilePage, { resumeOpen: true }));
    assert.doesNotMatch(markup, /resume-modal|Synthetic Current Learner|current@example.test/);
    assert.match(markup, /Profile access denied/);
  });
}
