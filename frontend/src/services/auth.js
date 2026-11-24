/** Server sessions only. No password, auth flag or token is read from browser storage. */
import { API_BASE_URL, publicFetch, authenticatedFetch, setRequestIdentity, clearRequestIdentity,
  subscribeSessionInvalid } from './apiTransport.js';
import { selectedProfileKey } from './ownedProfiles.js';
import { clearLoginEmail } from './loginEmailDraft.js';

const listeners = new Set();
let state = { status: 'restoring', account: null, error: null, epoch: 0 };
let generation = 0;
const publish = (next) => { state = { ...state, ...next }; listeners.forEach((listener) => listener()); };
function clearSession(message = null) {
  const accountId = state.account?.account_id;
  if (accountId) {
    try {
      const storage = globalThis.sessionStorage;
      if (storage) {
        for (let index = storage.length - 1; index >= 0; index--) {
          const key = storage.key(index);
          if (key === selectedProfileKey(accountId) || (key?.startsWith('placepro_assessment:') && key.endsWith(':account:' + accountId))) storage.removeItem(key);
        }
      }
    } catch { /* The unmounted private UI still clears all memory. */ }
  }
  generation++;
  clearRequestIdentity();
  publish({ status: 'anonymous', account: null, error: message, epoch: state.epoch + 1 });
}
subscribeSessionInvalid(() => clearSession('Your session has expired. Sign in again.'));

function validateSession(data) {
  if (!data?.account || !/^[a-f0-9-]{36}$/.test(data.account.account_id) || typeof data.account.email !== 'string' ||
      !Number.isFinite(Date.parse(data.idle_expires_at)) || !Number.isFinite(Date.parse(data.absolute_expires_at))) {
    throw new Error('The account service returned an unexpected response. Please retry.');
  }
  return { account_id: data.account.account_id, email: data.account.email };
}
function acceptSession(data) {
  const account = validateSession(data);
  const changed = account.account_id !== state.account?.account_id;
  clearLoginEmail();
  setRequestIdentity(account.account_id);
  publish({ status: 'authenticated', account, error: null, epoch: state.epoch + Number(changed) });
}
async function jsonRequest(path, options = {}, secured = false) {
  let response;
  try { response = await (secured ? authenticatedFetch : publicFetch)(API_BASE_URL + path, options); }
  catch (cause) { throw Object.assign(new Error(cause.status ? cause.message : 'Cannot reach PlacePro. Check your connection and try again.', { cause }), { status: cause.status ?? null }); }
  let data;
  try { data = response.status === 204 ? null : await response.json(); }
  catch { throw new Error('The account service returned an unexpected response. Please retry.'); }
  if (!response.ok) {
    const messages = { 401: 'Invalid credentials or inactive account.', 403: 'Security check failed. Refresh the session and try again.',
      409: 'Active session limit reached. Sign out of another session before retrying.',
      503: path === '/api/auth/register' ? 'Registration is unavailable while email activation is being prepared. No account was activated.'
        : path === '/api/auth/google/start' ? 'Google sign-in is not configured on this server. Use your PlacePro email and password.'
        : 'Account services are temporarily unavailable. Please retry.' };
    throw Object.assign(new Error(messages[response.status] || 'Unable to process this request. Check your details and try again.'), { status: response.status });
  }
  return data;
}
export const authSession = {
  subscribe: (listener) => { listeners.add(listener); return () => listeners.delete(listener); },
  getSnapshot: () => state,
  async restore({ background = false } = {}) {
    const request = ++generation;
    if (!background) publish({ status: 'restoring', error: null });
    try {
      const data = await jsonRequest('/api/auth/session');
      if (request === generation) acceptSession(data);
    } catch (error) {
      if (request !== generation) return;
      if (error.status === 401) clearSession(state.account ? 'Your session has expired. Sign in again.' : null);
      else { clearRequestIdentity(); publish({ status: 'unavailable', account: null, error: error.message }); }
    }
  },
};

/** Obtain a bootstrap CSRF challenge and establish the real HttpOnly session. */
export async function login(username, password) {
  if (!String(username || '').trim().includes('@') || !password || [...password].length > 128) throw new Error('Enter a valid email and password.');
  const request = ++generation;
  const challenge = await jsonRequest('/api/auth/login-challenge');
  if (!/^[a-f0-9]{64}$/.test(challenge?.csrf_token)) throw new Error('The security service returned an invalid response.');
  const data = await jsonRequest('/api/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': challenge.csrf_token },
    body: JSON.stringify({ email: username.trim(), password }) });
  if (request !== generation) throw new Error('Your session changed. Please sign in again.');
  acceptSession(data);
  return true;
}

export async function register(email, password) {
  if (!email.trim().includes('@') || email.length > 254 || [...password].length < 12 || [...password].length > 128) {
    throw new Error('Use a valid email and a password of 12–128 characters.');
  }
  await jsonRequest('/api/auth/register', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email: email.trim(), password }) });
  return 'Registration received. Email activation is required before you can sign in.';
}

/**
 * Real Google OAuth 2.0 sign-in. The backend owns the client secret, the
 * authorization-code exchange, state/nonce validation and the session; this
 * module only follows the returned Google authorization URL. No Google
 * credential, token or authorization code is stored in the browser.
 */
export async function googleAuthorizationUrl() {
  const data = await jsonRequest('/api/auth/google/start');
  const value = data?.authorization_url;
  if (typeof value !== 'string' || value.length > 2048) throw new Error('The Google sign-in service returned an invalid response.');
  let target;
  try { target = new URL(value); } catch { throw new Error('The Google sign-in service returned an invalid response.'); }
  if (target.protocol !== 'https:' || target.hostname !== 'accounts.google.com' || !target.searchParams.get('state')) {
    throw new Error('The Google sign-in service returned an invalid response.');
  }
  return value;
}

export async function startGoogleLogin() {
  const url = await googleAuthorizationUrl();
  globalThis.location.assign(url);
  return true;
}

const GOOGLE_ERRORS = {
  google_denied: 'Google sign-in was cancelled.',
  google_state: 'The Google sign-in request expired. Please start again.',
  google_invalid: 'Google sign-in could not be verified. Please try again.',
  google_unverified: 'That Google account has no verified email address for PlacePro.',
  google_conflict: 'That Google account cannot be linked to this PlacePro account. Sign in with your password instead.',
  google_inactive: 'This PlacePro account is not active. Contact your placement office.',
  google_unavailable: 'Google sign-in is temporarily unavailable. Please try again.',
  google_not_configured: 'Google sign-in is not configured on this server.',
  google_session_limit: 'Active session limit reached. Sign out of another session and retry.',
};

/** Consume the one-time backend redirect result and strip it from the URL. */
let authReturn;
let authReturnRead = false;
export function consumeAuthReturn() {
  if (authReturnRead) return authReturn;
  authReturnRead = true;
  authReturn = null;
  if (typeof window === 'undefined' || !window.location) return authReturn;
  let params;
  try { params = new URLSearchParams(window.location.search); } catch { return authReturn; }
  const error = params.get('auth_error');
  const success = params.get('auth') === 'google';
  if (!error && !success) return authReturn;
  params.delete('auth_error');
  params.delete('auth');
  const query = params.toString();
  try {
    window.history.replaceState(null, '', window.location.pathname + (query ? '?' + query : '') + window.location.hash);
  } catch { /* The visible URL may retain a non-secret status flag. */ }
  authReturn = error ? { error: GOOGLE_ERRORS[error] || 'Google sign-in could not be completed.' }
    : { notice: 'Signed in with Google.' };
  return authReturn;
}

/** Clears the frontend authentication state. */
export async function logout() {
  try { await jsonRequest('/api/auth/logout', { method: 'POST' }, true); }
  catch (error) { if (error.status !== 401) throw error; }
  clearSession();
}

/**
 * Returns the current in-memory server-validated authentication state.
 */
export function isAuthenticated() {
  return state.status === 'authenticated';
}
