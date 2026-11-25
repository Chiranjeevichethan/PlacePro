import test from 'node:test';
import assert from 'node:assert/strict';
import { readLoginEmail, rememberLoginEmail, clearLoginEmail } from '../src/services/loginEmailDraft.js';

function storageFor(t, values = new Map()) {
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, 'sessionStorage');
  const storage = { getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value), removeItem: (key) => values.delete(key) };
  Object.defineProperty(globalThis, 'sessionStorage', { configurable: true, value: storage });
  t.after(() => descriptor ? Object.defineProperty(globalThis, 'sessionStorage', descriptor) : delete globalThis.sessionStorage);
  clearLoginEmail();
  return storage;
}

test('partial email text survives a remount without normalizing the input', (t) => {
  const storage = storageFor(t);
  rememberLoginEmail(' student@');
  assert.equal(readLoginEmail(), ' student@');
  assert.equal(storage.getItem('placepro_login_email:v1'), ' student@');
});

test('clearing the email removes both persisted and in-memory drafts', (t) => {
  const storage = storageFor(t);
  rememberLoginEmail('synthetic@example.test');
  clearLoginEmail();
  assert.equal(storage.getItem('placepro_login_email:v1'), null);
  assert.equal(readLoginEmail(), '');
});

test('overlong persisted email data is ignored', (t) => {
  const storage = storageFor(t);
  storage.setItem('placepro_login_email:v1', 'e'.repeat(255));
  assert.equal(readLoginEmail(), '');
});

test('storage denial preserves the email in memory and cannot interrupt authentication clearing', (t) => {
  storageFor(t);
  Object.defineProperty(globalThis, 'sessionStorage', { configurable: true, get() { throw new Error('Storage denied'); } });
  rememberLoginEmail('synthetic@example.test');
  assert.equal(readLoginEmail(), 'synthetic@example.test');
  assert.doesNotThrow(clearLoginEmail);
  assert.equal(readLoginEmail(), '');
});
