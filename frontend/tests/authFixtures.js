/** Explicit synthetic authenticated transport for unchanged domain API assertions. */
import { beforeEach } from 'node:test';
import { clearRequestIdentity, setRequestIdentity, rememberCSRF } from '../src/services/apiTransport.js';
beforeEach(() => {
  clearRequestIdentity();
  setRequestIdentity('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa');
  rememberCSRF('a'.repeat(64));
});
