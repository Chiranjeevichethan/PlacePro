/** Cookie transport. CSRF and account identity live only in this module's memory. */
function apiBaseURL() {
  const configured = (import.meta.env?.VITE_API_BASE_URL || 'http://127.0.0.1:8765').replace(/\/$/, '');
  if (import.meta.env?.DEV !== true || !globalThis.location?.href) return configured;
  try {
    const api = new URL(configured);
    const page = new URL(globalThis.location.href);
    const localHosts = ['localhost', '127.0.0.1'];
    if (api.protocol === 'http:' && page.protocol === 'http:'
        && localHosts.includes(api.hostname) && localHosts.includes(page.hostname)
        && !api.username && !api.password) {
      // SameSite=Lax cookies require the same site, even for two loopback names.
      api.hostname = page.hostname;
      return api.href.replace(/\/$/, '');
    }
  } catch { /* trustedURL rejects invalid API configuration before any request. */ }
  return configured;
}
// Vite removes the development fallback from production bundles.
// The build config requires this public HTTPS origin before emitting assets.
export const API_BASE_URL = import.meta.env?.PROD === true
  ? import.meta.env.VITE_API_BASE_URL.trim().replace(/\/$/, '')
  : apiBaseURL();
let accountId = null;
let epoch = 0;
let csrf = null;
let tokenRequest = null;
const listeners = new Set();

export function setRequestIdentity(id) {
  if (id !== accountId) { accountId = id; epoch++; csrf = null; tokenRequest = null; }
}
export function clearRequestIdentity() { accountId = null; epoch++; csrf = null; tokenRequest = null; }
export function subscribeSessionInvalid(listener) { listeners.add(listener); return () => listeners.delete(listener); }
export function rememberCSRF(token) {
  if (typeof token !== 'string' || !/^[a-f0-9]{64}$/.test(token)) throw new Error('The security service returned an invalid response.');
  csrf = token;
}
const errorWithStatus = (message, status) => Object.assign(new Error(message), { status });
function trustedURL(url) {
  const target = new URL(url, API_BASE_URL);
  if (target.origin !== new URL(API_BASE_URL).origin) throw new Error('Untrusted API destination.');
  return target;
}
export async function publicFetch(url, options = {}) {
  trustedURL(url);
  return fetch(url, { ...options, credentials: 'include', cache: 'no-store' });
}
function invalidSession(captured) {
  if (captured !== epoch) return;
  clearRequestIdentity();
  listeners.forEach((listener) => listener());
}
async function getCSRF(captured) {
  if (csrf) return csrf;
  if (!tokenRequest) {
    const pending = (async () => {
      const response = await publicFetch(API_BASE_URL + '/api/auth/csrf');
      if (captured !== epoch) throw errorWithStatus('Your account session changed. Please try again.', 401);
      if (!response.ok) {
        if (response.status === 401) invalidSession(captured);
        throw errorWithStatus(response.status === 401 ? 'Your session has expired. Sign in again.' : 'Security check failed. Refresh the session and try again.', response.status);
      }
      const data = await response.json();
      rememberCSRF(data?.csrf_token);
      return csrf;
    })();
    tokenRequest = pending;
    pending.finally(() => { if (tokenRequest === pending) tokenRequest = null; }).catch(() => {});
  }
  return tokenRequest;
}
export async function authenticatedFetch(url, options = {}) {
  const captured = epoch;
  const target = trustedURL(url);
  const method = (options.method || 'GET').toUpperCase();
  const lifecycleGET = /^\/api\/assessment\/[^/]+$/.test(target.pathname) || /^\/api\/profile\/[^/]+\/assessments$/.test(target.pathname);
  const headers = Object.fromEntries(new Headers(options.headers || {}).entries());
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method) || lifecycleGET) headers['x-csrf-token'] = await getCSRF(captured);
  if (captured !== epoch) throw errorWithStatus('Your account session changed. Please try again.', 401);
  const response = await publicFetch(url, { ...options, headers });
  if (captured !== epoch) throw errorWithStatus('Your account session changed. Please try again.', 401);
  if (response.status === 401) invalidSession(captured);
  if (response.status === 403) csrf = null;
  // Rejected mutations are never silently resubmitted.
  return response;
}
