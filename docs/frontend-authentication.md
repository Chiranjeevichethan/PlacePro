# Frontend authentication — Phase 29.6.7

> Historical snapshot: the original phase dates, design decisions and recorded
> test results below are preserved. Statements about the then-current inventory,
> unavailable features and pre-authentication behavior are superseded by the
> [reviewed 2026-11-24 release snapshot](../backend/DEPLOYMENT.md#reviewed-release-snapshot-2026-11-24).
> This documentation change reruns no application tests and establishes no new
> Linux/Docker or browser acceptance.

The React application now uses the existing server session, CSRF and ownership
APIs. Login is real; registration has a form but the server deliberately returns
503 until approved email activation exists. No activated account or successful
registration is invented. Password recovery remains unavailable. Google OAuth was implemented later and
requires configuration and provider acceptance; GitHub/LinkedIn sign-in remain unavailable.

`apiTransport.js` sends credential cookies only to the configured API origin.
Login first obtains the bootstrap challenge. Authenticated writes and assessment
lifecycle GETs obtain a session-bound CSRF token held only in module memory.
401 clears authenticated UI; 403 clears the token and displays the rejected
request without automatically repeating a mutation. Session restoration calls
GET /api/auth/session. Background focus checks preserve active forms/assessments.
Logout clears UI only after server revocation succeeds or confirms no valid session.
Errors display safe messages; failures cannot announce successful logout.

`useAuth` subscribes to the in-memory session. Protected pages are mounted only
after restoration. Account changes remount the profile provider. Owned profile
references come from GET /api/account/profiles; every selected record is loaded
through the secured profile endpoint. SessionStorage contains account/API-scoped
selection references and assessment answer drafts, never authentication secrets.
Existing legacy localStorage caches are preserved and ignored for authentication
and owned-profile selection. Logout removes only the current account's newly
scoped UI references. No historical browser caches are deleted.

Profile switches immediately clear the previous profile and remount page state,
pending resume drafts and prediction/assessment controllers. Late responses are
discarded by request generations. Empty accounts never load the demo profile.
Dashboard, placement/salary forms, readiness/skill gaps, recommendations, profile,
mock tests and performance use the credentialed transport and backend results.
Stateless forms retain their contracts and are not saved as profile predictions.
New resume upload uses the existing owned `/api/profile/from-resume` workflow,
then review/confirmation with the returned profile ID and revision. The later owned resume-preview flow supports review and selected updates to an
existing profile. Only the two standalone processing routes remain blocked.
Existing profile corrections retain authentication, CSRF and revision protection.

Tests use Node's existing runner with explicit synthetic identity/CSRF fixtures
for domain API tests, alongside real transport/session tests. No dependencies,
manifests, lockfiles, backend architecture, environment or deployment settings
were changed in this phase.

Validation: 175 frontend tests pass (zero failed/cancelled/skipped/todo), 1,078
backend tests pass (zero failed/errors/skipped/deselected; ten existing joblib
NumPy warnings), lint exits 0 and a production build exits 0. Build output uses
fresh evidence directories; Vite warns these are outside its root and will not
be emptied. This is intentional preservation, not a suppressed warning.
Chromium verifies real login/dashboard, refresh/selection restoration, profile
switching, seven protected page navigations, two independent browser accounts,
foreign-profile 404, CSRF 403, missing-session login, restricted registration,
logout/revocation/refresh and a mobile login viewport. These are integration
checks, not full end-to-end coverage of every calculator/lifecycle; that belongs
to Phase 29.6.9. Initial browser selectors/async selection checks were corrected
without changing the application contract. Initial domain mocks lacked CSRF;
explicit fixtures correct this. A later lint run found 24 discarded causes;
wrapped errors now preserve causes without displaying private internals.

Current limits: public activation/recovery, Google provider/hosting acceptance,
production HTTPS/proxy/CORS acceptance and
complete browser lifecycle validation. Backend ownership remains authoritative;
UI controls never grant access. This integration is not public deployment readiness.
The next authorized phase is 29.6.8 account-bound retry integrity.
