/**
 * PlacePro mock authentication service.
 *
 * IMPORTANT: This is a TEMPORARY demo implementation. Login state is stored in
 * localStorage only - there is no real backend or OAuth yet.
 *
 * Future backend integration points (do not change the exported API):
 *  - login():     replace the body with POST <api-url>/api/login
 *  - socialLogin(): replace the mock with the real OAuth flow
 *  - logout()/isAuthenticated(): keep as the single source of auth truth
 */

const AUTH_KEY = "placepro_authenticated";

const DEMO_CREDENTIALS = {
  username: "student@placepro.com",
  password: "placepro123",
};

/**
 * Mock login. Resolves true when the demo credentials match.
 *
 * `remember` controls where the session is stored:
 *  - true  -> localStorage (persists across browser sessions)
 *  - false -> sessionStorage (cleared when the tab closes)
 *
 * Simulates network latency so the UI loading state is visible.
 */
export async function login(username, password, remember = true) {
  await new Promise((resolve) => setTimeout(resolve, 700));

  const valid =
    String(username || "").trim().toLowerCase() === DEMO_CREDENTIALS.username &&
    String(password || "") === DEMO_CREDENTIALS.password;

  if (valid) {
    const storage = remember ? localStorage : sessionStorage;
    storage.setItem(AUTH_KEY, "true");
  }

  return valid;
}

/**
 * Mock social login. No real OAuth is connected yet - this only returns the
 * message the UI should display. When the backend is ready, replace the body
 * with the real OAuth flow (e.g. redirect to the provider / POST /api/oauth).
 */
export async function socialLogin(provider) {
  await new Promise((resolve) => setTimeout(resolve, 300));

  return `${provider} login will be available when authentication is connected.`;
}

/** Clears the frontend authentication state. */
export function logout() {
  localStorage.removeItem(AUTH_KEY);
  sessionStorage.removeItem(AUTH_KEY);
}

/**
 * Returns true when the user is logged in.
 * Checks both storage locations (persisted and session-only logins).
 */
export function isAuthenticated() {
  return (
    localStorage.getItem(AUTH_KEY) === "true" ||
    sessionStorage.getItem(AUTH_KEY) === "true"
  );
}
