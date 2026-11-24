# Phase 30.2 — Isolated synthetic demonstration

> Publication refresh (2026-11-24): current capabilities, 50 operations/45 paths,
> required artifacts and verification boundaries are summarized in the
> [reviewed release snapshot](../backend/DEPLOYMENT.md#reviewed-release-snapshot-2026-11-24). Earlier dated results remain historical;
> no new application tests, browser acceptance or Linux/Docker success are claimed.

`scripts/demo.py` provides a repeatable local student demonstration using the
unchanged secured FastAPI application and the existing React frontend through
an owned loopback Vite development server. Production builds still require a
non-loopback HTTPS API origin; this local harness does not exercise that bundle.
It installs nothing, creates no production secret, and adds no authentication,
activation, ownership or CSRF exception.

## Run from an interactive PowerShell terminal

Use the existing validated Python environment (or another already installed
environment satisfying requirements.txt); frontend dependencies must already exist.

```powershell
.\.venv\Scripts\python.exe -B scripts/demo.py
```

The launcher refuses occupied ports and noninteractive password input. Choose
and confirm a 15–128-character demo password at the masked prompts. It prints
the temporary workspace path, browser URL and synthetic account email addresses;
it never prints or serializes the password. Defaults: frontend 127.0.0.1:5173,
API 127.0.0.1:8765. Use `--api-port` and `--frontend-port` to choose other free
ports; both servers always bind loopback. No external hosting is supported.

Three synthetic student accounts are provisioned into a brand-new database:
demo-student-a@example.test, demo-student-b@example.test, demo-empty@example.test.
Use your chosen password. A and B each have two profiles; the third starts empty.
Names, email domains, college/projects/internships and supplied scores are explicitly
synthetic. Each primary profile has a real backend-calculated prediction history
entry using those synthetic inputs; no placement outcome or assessment score is
fabricated. Assessment history starts empty for the evaluator's own attempt.

The generated `Synthetic-Resume.docx` is a self-contained fictional fixture,
not a copy of a student's resume or an existing test document. It identifies
**Synthetic Demo Learner** with `synthetic-resume@example.test`, a fictional
college, two fictional projects, one practice internship, one volunteer experience
entry and one fictional certificate. All eight skill categories have stated
examples. No phone, home address or real social account is provided. DOCX author
and last-modified metadata explicitly identify PlacePro Synthetic Demo.

After updating the launcher/parser, stop your own previous launch with Ctrl+C
and launch again to create a fresh file and isolated Vite server. Old temporary
workspaces are retained; do not select an old file merely because its basename
also says Synthetic-Resume.docx. Use the exact path printed by the current launch.

In **Update from Resume**, compare **Current profile** with **Extracted from
uploaded file**. The editable **Profile values to save after your review** keep
current values unless an import is selected. A preserved name/email there is
not evidence that it was read from the uploaded file. Upload alone saves nothing.

## Isolation and security

Each launch creates a new `placepro_demo_*` temporary directory. There is no
option to reuse historical storage. Its marker, records, auth DB, companies DB,
resume, Vite cache and logs remain isolated and are retained after shutdown. Linked,
unmarked or historical target directories are rejected; provisioning refuses an
existing auth database. Only the three newly created pending fixture accounts are
marked ACTIVE before serving. This is explicit synthetic fixture provisioning,
not verified email delivery or an activation API for real accounts.

All profile creation/history writes use real cookie login, login challenge,
session CSRF, Origin and ownership endpoints. The server uses the already approved
development loopback policy with proxy headers disabled. Production policies and
registration (503) remain unchanged. No administrator role or fixed demo password
is added. Same-machine users with local access remain within the existing developer
trust environment; do not expose this launcher on a public host or tunnel.

Environment overrides apply only to the isolated child processes. Model files
and datasets are read unchanged. Company requirements are the existing DEMO seed,
copied by the normal company service into the new demo database. Vite uses a
new cache directory, without emptying an existing build. A run-ID response header
verifies that startup reached the owned server, not an unrelated listener.

Ctrl+C asks the owned Vite and API children to stop
gracefully. It does not terminate unrelated processes or delete any records.
If startup or shutdown fails, inspect the retained workspace/server.log; repair
or removal of records is not automatic. The interactive launcher uses no browser
credential storage, automatic login or publicly readable credential endpoint.

## Demonstration walkthrough

1. Sign in as student A and examine the labelled synthetic profile/dashboard.
2. Switch between A's two profiles; inspect completion, readiness and history.
3. Run placement and salary forms. These are stateless estimates; saving owned
   prediction history is the separate dashboard action.
4. Open skill gaps and company recommendations; requirements are sample data.
5. Start and submit a mock assessment; inspect result/history/performance. The
   server's normal deadline, quota and cooldown rules apply.
6. Edit and reconfirm a profile; run a new prediction after its revision changes.
7. Sign out. Sign in as B and verify only B's profiles appear.
8. Use demo-empty to upload `Synthetic-Resume.docx` from the printed workspace,
   review extraction and complete missing ML inputs through the profile editor.
   Resume text is not inferred into self-assessed numeric scores.

Phase30.2 focused validation: 6 passed, 0 failed/errors/skipped/deselected,
0 reported warnings (10.96 s). Tests cover fresh-only provisioning, unchanged
existing fixture accounts, Argon2 storage, invalid/historical marker rejection,
hidden-input requirements, real TCP login/CSRF/ownership/registration restriction,
stateless model calls and graceful shutdown. First focused run passed 4 tests;
two additional guards were added and all six reran. No application failure was
hidden. The final UI/build/browser rehearsal is recorded in Phase30.6 validation.

Final guards added after that initial Phase30.2 run reject in-project targets and
junctions, validate the run marker, and reserve new DB/resume/build destinations
exclusively. The expanded focused set passed **7 tests**, 0 failed/errors/skipped/
deselected, 0 reported warnings (11.86 s), and is included in the passing full
**1,125-test** backend suite. The shipped helpers seeded, built, served and shut
down the isolated demo successfully. The real HTTP rehearsal passed **54 assertions**
with no failed assertions; frontend unit/lint/build checks also pass.

The new browser/visual walkthrough could not run because automatic approval review
blocked local browser actions. The 40 prior Phase29 browser assertions do not
validate the new Phase30 UI. An interactive evaluator rehearsal remains necessary;
see [final validation](phase-30-validation.md). Demo/API test servers are stopped
and temporary records are retained. No synthetic outcome is represented as a real
student result or live email verification.
