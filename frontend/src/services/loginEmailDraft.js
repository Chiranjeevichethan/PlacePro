/** A tab-scoped email draft only. Passwords and authentication proofs never belong here. */
const EMAIL_KEY = 'placepro_login_email:v1';
let memory = '';

export function readLoginEmail() {
  try {
    const storage = globalThis.sessionStorage;
    if (storage) {
      const stored = storage.getItem(EMAIL_KEY);
      memory = typeof stored === 'string' && stored.length <= 254 ? stored : '';
    }
  } catch { /* Keep the in-memory draft when browser storage is unavailable. */ }
  return memory;
}

export function rememberLoginEmail(email) {
  memory = typeof email === 'string' && email.length <= 254 ? email : '';
  try {
    const storage = globalThis.sessionStorage;
    if (memory) storage?.setItem(EMAIL_KEY, memory);
    else storage?.removeItem(EMAIL_KEY);
  } catch { /* Storage failure must not interrupt typing or authentication. */ }
}

export function clearLoginEmail() {
  rememberLoginEmail('');
}
