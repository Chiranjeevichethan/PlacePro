import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { transformWithOxc } from 'vite';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { authSession, login } from '../src/services/auth.js';

const emailKey = 'placepro_login_email:v1';
const email = 'login-regression@example.test';
const response = (body, status = 200) => new Response(JSON.stringify(body), { status });
const session = { account: { account_id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', email },
  idle_expires_at: '2026-11-23T00:00:00+00:00', absolute_expires_at: '2026-11-23T01:00:00+00:00' };
const dataModule = (source) => 'data:text/javascript;base64,' + Buffer.from(source).toString('base64');

function installStorage(t, initial = {}) {
  const values = new Map(Object.entries(initial));
  const storage = { getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, String(value)), removeItem: (key) => values.delete(key),
    key: (index) => [...values.keys()][index] ?? null, get length() { return values.size; } };
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, 'sessionStorage');
  Object.defineProperty(globalThis, 'sessionStorage', { configurable: true, value: storage });
  t.after(() => descriptor ? Object.defineProperty(globalThis, 'sessionStorage', descriptor) : delete globalThis.sessionStorage);
  return storage;
}

// Execute the actual transport with Vite environment values and a browser URL.
// Production and non-loopback destinations must keep the explicitly configured origin.
const transportSource = await readFile(new URL('../src/services/apiTransport.js', import.meta.url), 'utf8');
async function transportBase(configured, pageURL, development = true) {
  const environment = { DEV: development, PROD: !development, VITE_API_BASE_URL: configured };
  const source = `const globalThis = ${JSON.stringify({ location: pageURL ? { href: pageURL } : undefined })};\n`
    + transportSource.replaceAll('import.meta.env', `(${JSON.stringify(environment)})`);
  return (await import(dataModule(source))).API_BASE_URL;
}

for (const [name, configured, pageURL, expected, development] of [
  ['localhost page and IPv4 API', 'http://127.0.0.1:8000', 'http://localhost:5173/dashboard', 'http://localhost:8000', true],
  ['IPv4 page and localhost API', 'http://localhost:8000', 'http://127.0.0.1:5173/', 'http://127.0.0.1:8000', true],
  ['existing matching hosts', 'http://127.0.0.1:8765/', 'http://127.0.0.1:5173/', 'http://127.0.0.1:8765', true],
  ['configured port and base path', 'http://127.0.0.1:8123/service/', 'http://localhost:5173/', 'http://localhost:8123/service', true],
  ['production', 'https://api.example.test/', 'https://app.example.test/', 'https://api.example.test', false],
  ['HTTPS development', 'https://127.0.0.1:8000', 'https://localhost:5173/', 'https://127.0.0.1:8000', true],
  ['external API', 'https://api.example.test', 'http://localhost:5173/', 'https://api.example.test', true],
  ['external frontend', 'http://127.0.0.1:8000', 'http://frontend.example.test/', 'http://127.0.0.1:8000', true],
  ['no browser URL', 'http://127.0.0.1:8000', undefined, 'http://127.0.0.1:8000', true],
]) {
  test('API cookie host policy: ' + name, async () => {
    assert.equal(await transportBase(configured, pageURL, development), expected);
  });
}

// Render the real Login form on independent mounts. Only decorative leaves are replaced.
let loginSource = await readFile(new URL('../src/pages/Login.jsx', import.meta.url), 'utf8');
const leaf = dataModule('export default function DecorativeLeaf() { return null; }');
loginSource = loginSource.replace('"../components/Logo"', JSON.stringify(leaf))
  .replace('"../components/DemoCredentials"', JSON.stringify(leaf))
  .replace('"../services/auth"', JSON.stringify(new URL('../src/services/auth.js', import.meta.url).href))
  .replace('"../services/loginEmailDraft.js"', JSON.stringify(new URL('../src/services/loginEmailDraft.js', import.meta.url).href));
const transformed = await transformWithOxc(loginSource, 'LoginRecoveryProbe.jsx', { jsx: { runtime: 'automatic' }, sourcemap: false });
const { default: Login } = await import(dataModule(transformed.code
  .replaceAll('"react/jsx-runtime"', JSON.stringify(import.meta.resolve('react/jsx-runtime')))
  .replaceAll('"react"', JSON.stringify(import.meta.resolve('react')))));
const loginMarkup = () => renderToStaticMarkup(createElement(Login));

test('anonymous background restoration keeps Login mounted while the request is pending', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => response({}, 401));
  await authSession.restore();
  const anonymous = authSession.getSnapshot();
  let finish;
  t.mock.method(globalThis, 'fetch', () => new Promise((resolve) => { finish = resolve; }));
  const pending = authSession.restore({ background: true });
  try {
    assert.equal(authSession.getSnapshot(), anonymous);
    assert.equal(authSession.getSnapshot().status, 'anonymous');
  } finally {
    finish(response({}, 401));
    await pending;
  }
  assert.equal(authSession.getSnapshot().status, 'anonymous');
});

test('independent Login mounts restore only the tab email draft', (t) => {
  installStorage(t, { [emailKey]: email });
  for (let mount = 0; mount < 2; mount++) {
    const input = loginMarkup().match(/<input\b[^>]*id="login-username"[^>]*>/)?.[0];
    assert.match(input, /value="login-regression@example\.test"/);
  }
});

test('Login never restores a password from browser storage', (t) => {
  const password = 'Password storage must never be consumed';
  const storage = installStorage(t, { [emailKey]: email, password, placepro_login_password: password });
  const markup = loginMarkup();
  const input = markup.match(/<input\b[^>]*id="login-password"[^>]*>/)?.[0];
  assert.match(input, /value=""/);
  assert.ok(!markup.includes(password));
  assert.equal(storage.getItem('password'), password, 'Unrelated existing storage is left intact.');
});

test('successful server login clears the tab email draft', async (t) => {
  const storage = installStorage(t, { [emailKey]: email });
  t.mock.method(globalThis, 'fetch', async (url) =>
    response(url.endsWith('/login-challenge') ? { csrf_token: 'a'.repeat(64) } : session));
  await login(email, 'Synthetic fixture password used only by this mocked request');
  assert.equal(storage.getItem(emailKey), null);
});

test('successful session restoration clears a pending email draft', async (t) => {
  const storage = installStorage(t, { [emailKey]: email });
  t.mock.method(globalThis, 'fetch', async () => response(session));
  await authSession.restore();
  assert.equal(authSession.getSnapshot().status, 'authenticated');
  assert.equal(storage.getItem(emailKey), null);
});

test('invalid credentials leave the email draft and authentication state intact', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => response({}, 401));
  await authSession.restore();
  const storage = installStorage(t, { [emailKey]: email });
  const anonymous = authSession.getSnapshot();
  t.mock.method(globalThis, 'fetch', async (url) => url.endsWith('/login-challenge')
    ? response({ csrf_token: 'a'.repeat(64) }) : response({ detail: 'Invalid credentials.' }, 401));
  await assert.rejects(login(email, 'Incorrect synthetic fixture password'), (error) => error.status === 401);
  assert.equal(authSession.getSnapshot(), anonymous);
  assert.equal(storage.getItem(emailKey), email);
});
