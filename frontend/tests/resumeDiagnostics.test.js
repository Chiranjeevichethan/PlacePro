import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { safeResumeDiagnostic, traceResume } from '../src/services/resumeDiagnostics.js';

test('resume diagnostics retain lifecycle metadata and exclude credentials and resume contents', () => {
  const metadata = { source: 'ResumeUploadModal.handleKey', reason: 'escape', previous: true, next: false,
    profileId: 'synthetic-profile-id', uploading: false, verifying: false };
  assert.deepEqual(safeResumeDiagnostic({ ...metadata, password: 'private', cookie: 'private',
    csrfToken: 'private', authToken: 'private', resume: { contents: 'private' },
    file: { name: 'private' }, draft: {}, error: { message: 'private' } }), metadata);
});

test('ordinary production and Node diagnostics stay disabled and require no browser globals', () => {
  assert.doesNotThrow(() => traceResume('modal.close', { password: 'private' }));
});

// Execute the actual module with build environments injected only in memory.
// Production variants deliberately have no window/performance/console objects.
test('only explicitly opted-in development logs metadata; all production variants stay silent', async () => {
  const source = await readFile(new URL('../src/services/resumeDiagnostics.js', import.meta.url), 'utf8');
  for (const environment of [undefined, { DEV: true },
    { DEV: false, VITE_RESUME_DIAGNOSTICS: '1' },
    { DEV: false, VITE_RESUME_DIAGNOSTICS: '1', VITE_DEMO_MODE: 'synthetic' },
    { DEV: true, VITE_RESUME_DIAGNOSTICS: '1' }]) {
    const records = [];
    const sandboxWindow = {};
    const optedIn = environment?.DEV === true && environment?.VITE_RESUME_DIAGNOSTICS === '1';
    const factory = new Function('buildEnvironment', 'authSession', 'window', 'performance', 'console', source
      .replace(/^import .*;\r?\n/, '')
      .replaceAll('import.meta.env', 'buildEnvironment')
      .replaceAll('export function ', 'function ') + '\nreturn { traceResume, resumeDiagnosticInstance };');
    const diagnostic = factory(environment, { getSnapshot: () => ({ status: 'authenticated', epoch: 3 }) },
      optedIn ? sandboxWindow : undefined, optedIn ? { now: () => 1 } : undefined,
      optedIn ? { debug: (...args) => records.push(args) } : undefined);
    const instance = diagnostic.resumeDiagnosticInstance();
    diagnostic.traceResume('modal.state', { instance, phase: 'review', selectedExperience: true,
      resume: 'private-resume', cookie: 'private-cookie', token: 'private-token', password: 'private-password' });
    if (!optedIn) {
      assert.equal(instance, null);
      assert.equal(records.length, 0);
      assert.deepEqual(sandboxWindow, {});
    } else {
      assert.equal(records.length, 1);
      assert.deepEqual(sandboxWindow.__placeproResumeDiagnostics[0], {
        sequence: 1, timeMs: 1, event: 'modal.state', instance: 1, phase: 'review', selectedExperience: true,
        authStatus: 'authenticated', authEpoch: 3,
      });
      assert.doesNotMatch(JSON.stringify(records), /private-/);
      for (let index = 0; index < 1001; index++) diagnostic.traceResume('modal.state', { instance, phase: 'review' });
      assert.equal(sandboxWindow.__placeproResumeDiagnostics.length, 1000);
    }
  }
});
