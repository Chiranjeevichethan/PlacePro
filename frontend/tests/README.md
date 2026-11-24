# Assessment regression tests

> Publication refresh (2026-11-24): current capabilities, 50 operations/45 paths,
> required artifacts and verification boundaries are summarized in the
> [reviewed release snapshot](../../backend/DEPLOYMENT.md#reviewed-release-snapshot-2026-11-24). Earlier dated results remain historical;
> no new application tests, browser acceptance or Linux/Docker success are claimed.

From `frontend/` run `npm run test` and `npm run lint`. Tests use Node's built-in
runner, fake network responses, injected monotonic clocks and in-memory storage;
they install no dependencies and never contact project runtime storage.

`assessmentSession.test.js` covers server deadlines, automatic delivery, duplicate
guards, HTTP expiry/conflict handling, uncertain submission recovery, refresh,
retakes, cooldowns, result preservation and detached-controller writes.
`assessmentApi.test.js` verifies request bodies, answer conversion, status/retry
metadata and malformed/network responses. These tests exercise the controller/API;
they do not mount React or establish browser rendering behavior.

Active assessments require the backend's `created_at`, `expires_at` and `server_now`.
Completed session GETs return the public aggregate `result`; answer keys remain private.
Only a session reference and answer draft are saved in per-tab storage, scoped by
backend URL and profile. Official results must be confirmed by the backend.

For production validation set `NODE_ENV=production` and `VITE_API_BASE_URL` to
a reviewed non-loopback HTTPS origin, then use
`npm run build -- --outDir <new-artifact-directory>`
so existing output is preserved. Phase 29.3.3 additionally executes real Chromium
flows against that build and an owned temporary backend. The browser fixture keeps
the normal three-completion/24-hour policies and advances an injected server clock;
network failures are injected only in isolated browser contexts.

Never point browser tests at a development server with real profiles or assessment
records. Use the existing fixture-owned authentication, profile, assessment, company,
goals and resume-builder stores before importing the app; the existing
backend HTTP wrapper verifies those paths and its unique response identity.
