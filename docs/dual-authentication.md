# Dual authentication: student email/password and Google OAuth 2.0

> Publication refresh (2026-11-24): current capabilities, 50 operations/45 paths,
> required artifacts and verification boundaries are summarized in the
> [reviewed release snapshot](../backend/DEPLOYMENT.md#reviewed-release-snapshot-2026-11-24). Earlier dated results remain historical;
> no new application tests, browser acceptance or Linux/Docker success are claimed.

Both sign-in methods resolve to the same immutable account row, the same
authoritative profile ownership records and the same opaque HttpOnly server
session. There is no separate Google user table or parallel student system.

## Account and session foundation (unchanged)

- Accounts live in `PLACEPRO_AUTH_DB` (default `data/auth/accounts.sqlite3`),
  schema version 1, Argon2id password hashes only.
- Sessions are opaque server records; the cookie carries a 256-bit secret and
  only its SHA-256 digest is stored. Idle/absolute expiry, rotation, CSRF and
  revocation are unchanged by this work.
- The existing fail-closed ASGI gate still protects every private operation;
  authenticated accounts resolve student profiles through the ownership store.

The local account database on this checkout contained **zero accounts**. Local
registration intentionally returns `503` until an approved email-verification
workflow exists, so no account could be created through the UI. That is why the
previous student credentials stopped working; it was not a password change.

## Local development student account

Created only by backend code, never by frontend code:

1. At API startup in explicit development mode, when both
   `PLACEPRO_DEV_STUDENT_EMAIL` and `PLACEPRO_DEV_STUDENT_PASSWORD` are set.
2. Or explicitly with hidden password input: `python scripts/seed_dev_student.py --password`.

The default local development email is `student@placepro.com`. Choose a password
privately using the existing hidden prompts:

```powershell
$env:PLACEPRO_SECURITY_MODE = 'development'
$env:PLACEPRO_ALLOWED_ORIGINS = 'http://127.0.0.1:5173'
python scripts/seed_dev_student.py --password
```

Do not commit the password or put it in `VITE_` variables. Existing accounts keep
their existing password; provisioning is not a password reset.

Properties:

| Property | Behaviour |
| --- | --- |
| Hashing | Existing Argon2id service (64 MiB, t=3, p=1); plaintext is never stored or logged. |
| Password policy | Development provisioning accepts 8–128 characters; prefer at least 15 characters for operator-chosen passwords. Student registration keeps the 15-character minimum. |
| Duplicates | `email_normalized` UNIQUE plus `ON CONFLICT DO NOTHING`; repeated provisioning creates no second row. |
| Existing account | An existing account's password, status and hash are never overwritten. |
| Activation | Only `PENDING_EMAIL` rows are activated; disabled accounts stay disabled. |
| Production | Refused. Setting these variables outside `PLACEPRO_SECURITY_MODE=development` fails startup. |
| Identification | Provenance is recorded as `LOCAL_DEVELOPMENT` in the additive `account_origins` table. |

## Google OAuth 2.0

Authorization-code flow with PKCE, a single-use server-side state challenge
stored as a digest, an HttpOnly state cookie and an ID-token nonce:

```
GET /api/auth/google/start      exact Origin required -> { authorization_url } + state cookie
GET /api/auth/google/callback   state cookie + state -> code exchange -> session cookie -> 303
```

Verification steps on the callback:

1. `state` must be a 43-character URL-safe secret equal to the state cookie
   value (constant-time compare) and must match an unexpired, unconsumed
   challenge row for this security context. Challenge lifetime is 300 s and a
   state is consumed atomically, so replay fails.
2. The authorization code is exchanged with Google over TLS using the client
   secret and the PKCE verifier.
3. The returned ID token is verified with Google's `tokeninfo` endpoint, then
   locally for `iss`, `aud`/`azp`, `exp`/`iat`, `nonce`, `sub` and
   `email_verified`.
4. Only `email_verified: true` is accepted. Unverified email addresses never
   create or link an account.
5. The verified Google `sub` is the durable identity: it is linked once to one
   account. A second Google identity can never attach to the same account; an
   account may not hold two Google identities.
6. First Google sign-in creates an `ACTIVE`, email-verified account whose local
   password hash is derived from a random secret that is immediately discarded,
   so password sign-in to a Google-only account is impossible. Returning users
   reuse the same account. A local account is linked only when it is `ACTIVE`
   with a verified email; pending or disabled accounts are refused.

Google passwords are never requested or stored. Application authentication
secrets are not persisted in browser storage. The production container launcher
disables access logging; any other Uvicorn launcher, host or proxy must separately
omit callback query strings and sensitive headers/bodies from logs. Do not infer
log redaction from application code alone.

### Configuration

Set these in the shell before starting the API (the application does not load
`.env` files itself):

```
GOOGLE_CLIENT_ID=<client-id>.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=<client-secret>
GOOGLE_REDIRECT_URI=http://127.0.0.1:8765/api/auth/google/callback
PLACEPRO_APP_URL=http://127.0.0.1:5173
```

Google Cloud Console: create an OAuth 2.0 Client ID of type "Web application",
add the exact `GOOGLE_REDIRECT_URI` as an authorised redirect URI, and consent
scope `openid email profile`. Development redirect URIs must be loopback HTTP;
production configuration requires HTTPS. `PLACEPRO_APP_URL` must exactly match
one of `PLACEPRO_ALLOWED_ORIGINS`, which keeps the post-login redirect from
becoming an open redirect.

If the client ID and secret are absent, the API returns a clear `503` from
`/api/auth/google/start` and the login page reports that Google sign-in is not
configured. No credentials are invented. A partially configured pair (only one
value) fails startup rather than silently redirecting.

### Failure behaviour

Callback failures redirect to `PLACEPRO_APP_URL` with a non-secret code
(`auth_error=google_state|google_invalid|google_unverified|google_conflict|
google_inactive|google_unavailable|google_session_limit`) and never set a
session cookie. The login page shows a safe message and clears the flag.

## Remaining limitations

- Registration and password recovery still wait for an approved email
  activation/recovery workflow; the student registration link says so.
- Google ID-token signature verification relies on Google's `tokeninfo`
  endpoint (stdlib HTTPS) because the pinned environment has no JWT/crypto
  library. Local JWKS signature checking is a documented future hardening step.
- URL navigation and SPA deep-link configuration are implemented. Production
  HTTPS/proxy and Google callback acceptance, public onboarding and complete
  current browser verification remain pending; see the deployment guide.


### Historical development-login regression (2026-11-10)

The regression covers the shared runtime/provisioner store, duplicate-safe
provisioning, preservation of existing credentials, production-mode refusal,
valid/invalid login, session restoration, CSRF-protected logout and rejection of
revoked cookies. A provisioning already-exists result does not validate a newly
supplied password and must never silently replace an existing credential.

The original reported failed request was not captured sufficiently to establish
its exact cause. Do not attribute it to a typo, cache or password reset without
evidence. Operator-specific account state, password-verification results, live
database correlation and private browser/process history are omitted.

Historical recorded automated results are retained below. The initial missing
Origin fixture was corrected without weakening CSRF or authentication. These are
dated records; no current browser acceptance or public onboarding success is claimed.

| Historical check (2026-11-10) | Recorded result |
| --- | --- |
| Initial focused fixture, before the required Origin was supplied | 1 failed; 8.20 s |
| Corrected focused regression | 1 passed; no failures/errors/skips; 6.15 s |
| Relevant backend authentication suites | 249 passed; no failures/errors/skips; 81.58 s |
| Frontend authentication suite | 23 passed; 0 failed/cancelled/skipped/todo; 190.1713 ms |
Use `backend/tests/test_dev_student_login.py` and the public release verification
commands to reproduce the current regression coverage with isolated test stores.

