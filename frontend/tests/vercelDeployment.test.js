import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import config from '../vite.config.js';
import { APP_ROUTES } from '../src/services/appRoutes.js';

const vercel = JSON.parse(await readFile(new URL('../vercel.json', import.meta.url), 'utf8'));
const guard = config.plugins.flat(Infinity).find(plugin => plugin.name === 'placepro-production-api');
const validate = (base, overrides = {}) => guard.configResolved({ command: 'build',
  env: { PROD: true, VITE_API_BASE_URL: base }, ...overrides });

test('Vercel serves every application deep link, including V1 and trailing slashes, through the SPA', () => {
  assert.equal(vercel.framework, 'vite');
  assert.equal(vercel.buildCommand, 'npm run build');
  assert.equal(vercel.outputDirectory, 'dist');
  const fallback = vercel.rewrites.find(rule => rule.destination === '/index.html');
  const matches = new RegExp('^' + fallback.source + '$');
  for (const path of ['/', '/login', ...Object.values(APP_ROUTES).map(route => route.path)]) {
    assert.ok(matches.test(path), path);
    if (path !== '/') assert.ok(matches.test(path + '/'), path + '/');
  }
  assert.ok(matches.test('/experimental-v1-prediction'));
  for (const path of ['/api', '/api/auth/session', '/api/predict', '/api/salary-predict',
    '/api/experimental/v1/predict', '/health', '/health/']) {
    assert.equal(matches.test(path), false, 'Backend requests must not become HTML: ' + path);
  }
});

test('Vercel API responses are marked non-cacheable for browsers and CDN layers', () => {
  const api = vercel.headers.find(rule => rule.source === '/api/:path*');
  const headers = Object.fromEntries(api.headers.map(header => [header.key, header.value]));
  assert.equal(headers['Cache-Control'], 'private, no-store');
  assert.equal(headers['CDN-Cache-Control'], 'no-store');
  assert.equal(headers['Vercel-CDN-Cache-Control'], 'no-store');
});

for (const base of ['https://api.example.test', 'https://api.example.test/',
  ' https://api.example.test/ ', 'https://api.example.test:8443']) {
  test('production build accepts an explicit HTTPS API origin: ' + base.trim(), () => {
    assert.doesNotThrow(() => validate(base));
  });
}

for (const [name, base] of [
  ['missing', undefined], ['empty', ''], ['blank', '   '], ['relative origin', '/'],
  ['relative API path', '/api'], ['HTTP', 'http://api.example.test'],
  ['localhost', 'https://localhost:8765'], ['localhost subdomain', 'https://api.localhost'],
  ['IPv4 loopback', 'https://127.0.0.1:8765'], ['other IPv4 loopback', 'https://127.0.0.2'],
  ['short IPv4 loopback', 'https://127.1'], ['IPv6 loopback', 'https://[::1]:8765'],
  ['unspecified IPv4', 'https://0.0.0.0'], ['unspecified IPv6', 'https://[::]'],
  ['API suffix', 'https://api.example.test/api'], ['base path', 'https://api.example.test/service/'],
  ['query', 'https://api.example.test/?setting=example'], ['fragment', 'https://api.example.test/#example'],
  ['userinfo', 'https://example-user:example-value@api.example.test'],
]) {
  test('production build rejects unsafe or incompatible API configuration: ' + name, () => {
    assert.throws(() => validate(base), error => /VITE_API_BASE_URL/.test(error.message)
      && !error.message.includes('example-value'));
  });
}

test('build mode cannot publish development-only environment code', () => {
  assert.throws(() => validate('https://api.example.test', {
    env: { PROD: false, VITE_API_BASE_URL: 'https://api.example.test' },
  }), /NODE_ENV=production/);
});

test('development keeps existing local API configuration and requires no production environment', () => {
  assert.doesNotThrow(() => validate(undefined, { command: 'serve', env: { PROD: false } }));
});

const transportSource = await readFile(new URL('../src/services/apiTransport.js', import.meta.url), 'utf8');
async function transport(environment) {
  const source = transportSource.replaceAll('import.meta.env', '(' + JSON.stringify(environment) + ')');
  return import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
}

test('development transport retains the existing loopback fallback', async () => {
  const api = await transport({ DEV: true, PROD: false });
  assert.equal(api.API_BASE_URL, 'http://127.0.0.1:8765');
});

test('production transport uses the configured origin and unchanged API paths, credentials and no-store policy', async t => {
  const api = await transport({ DEV: false, PROD: true, VITE_API_BASE_URL: ' https://api.example.test/ ' });
  assert.equal(api.API_BASE_URL, 'https://api.example.test');
  api.setRequestIdentity('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa');
  api.rememberCSRF('a'.repeat(64));
  const calls = [];
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    calls.push({ url, options });
    return new Response('{}', { headers: { 'Cache-Control': 'private, no-store' } });
  });
  for (const path of ['/api/auth/session', '/api/profile/owned-profile', '/api/predict',
    '/api/salary-predict', '/api/experimental/v1/predict']) {
    const response = await api.authenticatedFetch(api.API_BASE_URL + path, {
      method: path.includes('predict') ? 'POST' : 'GET',
    });
    assert.equal(response.headers.get('Cache-Control'), 'private, no-store');
    assert.equal(calls.at(-1).url, 'https://api.example.test' + path);
    assert.equal(calls.at(-1).options.credentials, 'include');
    assert.equal(calls.at(-1).options.cache, 'no-store');
    if (path.includes('predict')) assert.equal(calls.at(-1).options.headers['x-csrf-token'], 'a'.repeat(64));
  }
  await assert.rejects(api.authenticatedFetch('http://127.0.0.1:8765/api/auth/session'), /Untrusted API destination/);
  assert.equal(calls.length, 5);
});
