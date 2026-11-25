import assert from 'node:assert/strict';
import test from 'node:test';
import config from '../vite.config.js';

const plugin = config.plugins.flat(Infinity).find(item => item.name === 'placepro-development-origin');

function request(overrides = {}, serverOptions = {}) {
  let middleware;
  plugin.configureServer({
    config: { server: { port: 5173, ...serverOptions } },
    middlewares: { use(handler) { middleware = handler; } },
  });
  const result = { next: false, ended: false };
  const response = {
    writeHead(status, headers) { Object.assign(result, { status, headers }); },
    end() { result.ended = true; },
  };
  middleware?.({ method: 'GET', url: '/experimental-v1-prediction?view=sample',
    headers: { host: 'localhost:5173', accept: 'text/html' }, ...overrides },
  response, () => { result.next = true; });
  return result;
}

test('localhost document navigations redirect to the allowed numeric origin before the app starts', () => {
  const result = request();
  assert.equal(result.status, 307);
  assert.equal(result.headers.Location, 'http://127.0.0.1:5173/experimental-v1-prediction?view=sample');
  assert.equal(result.headers['Cache-Control'], 'no-store');
  assert.equal(result.ended, true);
  assert.equal(result.next, false);
});

test('canonical documents keep their original route and receive no redirect', () => {
  assert.equal(request({ headers: { host: '127.0.0.1:5173', accept: 'text/html' } }).next, true);
});

test('API, mutation and Vite asset requests pass through without forwarding credentials to another host', () => {
  for (const overrides of [
    { method: 'POST' },
    { url: '/api/auth/session', headers: { host: 'localhost:5173', accept: 'application/json' } },
    { url: '/src/main.jsx', headers: { host: 'localhost:5173', accept: '*/*' } },
  ]) {
    const result = request(overrides);
    assert.equal(result.next, true);
    assert.equal(result.status, undefined);
  }
});

test('foreign, malformed and incorrect-port hosts stay subject to Vite host validation', () => {
  for (const host of ['foreign.example.test:5173', 'localhost:9999', 'invalid host']) {
    assert.equal(request({ headers: { host, accept: 'text/html' } }).next, true);
  }
  assert.equal(request({ url: '//foreign.example.test/path' }).next, true);
});

test('HTTPS development and production preview have no canonical HTTP redirect', () => {
  assert.deepEqual(request({}, { https: {} }), { next: false, ended: false });
  assert.equal(plugin.configurePreviewServer, undefined);
});

test('an explicitly selected development port is preserved', () => {
  const result = request({ headers: { host: 'localhost:5176', accept: 'text/html' } }, { port: 5176 });
  assert.equal(result.headers.Location, 'http://127.0.0.1:5176/experimental-v1-prediction?view=sample');
});
