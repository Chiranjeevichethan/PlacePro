# Account authentication foundation — Phase 29.6.2

> Historical snapshot: the original phase dates, design decisions and recorded
> test results below are preserved. Statements about the then-current inventory,
> unavailable features and pre-authentication behavior are superseded by the
> [reviewed 2026-11-24 release snapshot](../backend/DEPLOYMENT.md#reviewed-release-snapshot-2026-11-24).
> This documentation change reruns no application tests and establishes no new
> Linux/Docker or browser acceptance.

Implemented 2026-11-08 against the existing working tree. This is the account and
credential foundation for the [approved architecture](authentication-architecture.md),
not an authenticated student application. No frontend, ownership association,
session, CSRF, JWT, legacy migration or model change is included.

## Implemented boundary

The services can register accounts and verify credentials. The production router
registers `/api/auth/register` and `/api/auth/login` but **always returns HTTP 503
before parsing the request**. There is no environment flag, API switch or temporary
token that enables it. Importing the app does not initialize an account database.

Isolated endpoint tests construct `create_auth_router(service)` with a temporary
AccountService. This is explicit application construction, not a browser security
flag or a bypass on existing student endpoints. Its contract is:

| Request | Isolated foundation behavior |
| --- | --- |
| POST `/api/auth/register` with email/password | 202, same minimal `accepted` response for a new or duplicate normalized email; no account ID/hash/status/cookie returned. The message explicitly says verification delivery is unavailable. |
| POST `/api/auth/login`, unknown/wrong/pending/disabled/deactivated/unverified/corrupt credentials | 401, `Invalid credentials.`; no indication which check failed. |
| POST `/api/auth/login`, correct ACTIVE and verified credentials | 503, secure sessions/CSRF unavailable; never a successful application login. The internal service result is not serialized. |
| Invalid body, missing/extra fields or malformed JSON | 422 with a fixed safe message; no FastAPI input/validation-context echo. |
| Storage/hash/processing-cap failure | 503 with generic details, no exception/path/credential disclosure; Retry-After 1 where processing can be retried. |

Every response uses `Cache-Control: private, no-store`. Password request fields use
SecretStr and reject unknown fields including client account IDs and activation
claims. Registration never creates, loads or associates student profiles.

Existing student endpoints remain unprotected as documented in the
[ownership audit](ownership-access-control-audit.md). Adding these disabled routes
does not secure them; public deployment with real student data remains unsafe.

## Account storage

`AccountStore` uses a separate configurable `PLACEPRO_AUTH_DB`; its lazy default is
`data/auth/accounts.sqlite3`. Backend configuration reads process environment, not
dotenv. Do not point it at company/student storage. The store refuses the known
company paths, unsupported extensions and existing unrelated/version-incompatible
SQLite databases. Only a new/empty database is initialized; no migration is run.

Schema version 1 and an application ID distinguish this metadata store. The sole
table is `accounts`: immutable server UUID, unique normalized email, encoded Argon2id
hash, PENDING_EMAIL/ACTIVE/DISABLED/DEACTIVATED status, nullable email_verified_at,
auth_version (initially 1), created_at, updated_at and password_changed_at (UTC).
ACTIVE requires non-null verification metadata at the database and service boundaries.

Database UNIQUE and CHECK constraints, parameterized SQL, short transactions,
per-operation connections and a five-second SQLite busy timeout protect concurrent
registration. Duplicate insertion leaves every existing field unchanged, including
disabled accounts. Failed insert commit rolls back; a retry can safely encounter an
existing registration without replacing its password. There is no account ID supplied
by the client, account listing, activation or ownership-transfer API.

`auth_version` and password_changed_at are reserved inputs for future session
invalidation, not implemented revocation. Session, challenge, owner and retry tables
are not created. Database files contain sensitive hashes and require restricted
filesystem/backup access before deployment; ACL/encryption/lifecycle automation is
not implemented here. Existing databases and records are not rewritten.

## Email and status policy

Use the maintained Python `email.headerregistry.Address` parser plus existing
`idna==3.18` and an explicit ASCII dot-atom policy. Strip surrounding whitespace,
reject internal controls/whitespace, comments, display names, quoted or non-ASCII
local parts, malformed dot atoms and invalid domain labels. Local parts are limited
to 64 characters; the complete normalized address to 254 ASCII characters. Domains
require a dot and strict IDNA validation, with no trailing dot. Normalize supported
domains to lowercase ASCII IDNA and local parts to lowercase under the documented
case-insensitive account policy. Preserve dots, plus suffixes and provider aliases.

Both registration and credential lookup use the same function. No DNS/deliverability
query occurs and syntactic acceptance proves neither mailbox control nor profile
ownership. This narrower policy is deliberate; it is not arbitrary RFC mailbox support.
Email-validator/dnspython were not cached and direct registry access was blocked, so
no new validation dependency or ad-hoc broad RFC parser was added.

All registrations start PENDING_EMAIL with email_verified_at NULL. No approved
delivery provider is configured: verification challenges, delivery, activation,
recovery and resend flows are deferred. Only synthetic test SQL creates verified
ACTIVE/disabled fixtures, outside production modules. No activation shortcut exists.

## Password and credential processing

`argon2-cffi==25.1.0` provides supported Argon2id hashing/verification. Parameters:
64 MiB (65536 KiB), three iterations, parallelism one, 32-byte hash, 16-byte random
library salt, version 19. Different salts produce different hashes for identical
passwords. Passwords are never stored, logged, stripped, normalized or truncated.

Registration accepts 15–128 characters, at most 512 UTF-8 bytes; login bounds inputs
to 1–128 characters/512 bytes for verification compatibility. Invalid Unicode fails
safely. Two concurrent hash/verification operations per process are allowed, with a
five-second wait before a generic unavailable response. This bounds work, not login
attempt frequency or distributed abuse.

Unknown accounts use a random non-account Argon2 dummy hash. Malformed, unsupported
or excessive-cost stored encodings fail safely; allowable verification work is bounded
to 8–128 MiB, one to six iterations and at most four workers, with bounded salt/hash
lengths. Library mismatch/verification exceptions do not reach responses.

Successful verified credentials may upgrade older bounded parameters using
`check_needs_rehash` plus a no-downgrade guard and compare-and-swap on the old hash,
version and active/verified status. Rehash preserves account ID/auth_version and
password_changed_at. Conflicts and status changes during verification fail closed.
Future session creation must recheck status/version transactionally; the internal
credential result is not a session, bearer token or student permission.

The retained five-run benchmark measured median hashing 0.188782 s and verification
0.169941 s on this Windows development machine under concurrent test load. An earlier
unretained sample was about 0.127/0.125 s. These are development observations, not
production capacity/security calibration. Rate limiting, common/compromised-password
checks, distributed work budgets and real recovery remain release prerequisites.

## Dependencies and isolated validation

Four new runtime pins: argon2-cffi 25.1.0, argon2-cffi-bindings 25.1.0, cffi 2.1.1,
pycparser 3.0. Existing ML/runtime pins are unchanged. Required Windows wheels are
compatible with CPython 3.14.6 x64, including cp39-abi3 bindings and cp314 CFFI.
Cached official PyPI index hashes, wheel metadata, platform tags and ZIP integrity
were checked before copying them into a new phase wheelhouse.

Fresh installation used the unchanged 36-package runtime/test wheelhouse from
29.3.7-R plus the four verified wheels. Current manifests therefore have 32 runtime
and 40 runtime/test pins. `requirements-dev.txt` and the optional analysis file
inherit them; neither was regenerated. The existing environments were preserved.

```powershell
# Use the new validated environment, or install current manifests into a new venv.
$authPython = 'python'
& $authPython -B -m pip check
& $authPython -B -m pytest backend/tests/test_account_store.py backend/tests/test_authentication.py -q -p no:cacheprovider
& $authPython -B -m pytest backend/tests/ -q -p no:cacheprovider
```

The existing fixture now binds PLACEPRO_AUTH_DB before collection and for each
test. HTTP wrappers verify all four stores are temporary. Windows venv launchers
can use a different server PID; the test-only run-ID-verified wrapper reports its
actual PID. Shutdown uses only that verified process and its owned Popen handle,
without process-tree discovery, unrelated process termination or security changes.
A synthetic regression verifies the server closes and a separate listener remains.

No frontend files, environments, .env files,
student/history/company records, datasets or trained artifacts were modified.

Next assignment: **Phase 29.6.3 — Server-Side Session Management, CSRF Protection
& Default-Private Request Gate**. No work on that phase is included here.
