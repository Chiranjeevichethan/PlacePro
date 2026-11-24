# Profile revision and downstream integrity — Phase 29.3.6

> Historical snapshot: the original phase dates, design decisions and recorded
> test results below are preserved. Statements about the then-current inventory,
> unavailable features and pre-authentication behavior are superseded by the
> [reviewed 2026-11-24 release snapshot](../backend/DEPLOYMENT.md#reviewed-release-snapshot-2026-11-24).
> This documentation change reruns no application tests and establishes no new
> Linux/Docker or browser acceptance.

Decided 2026-11-07 after the mandatory journal/policy and current-source audit.

The existing JSON profile is the authority. Add one server-controlled `revision`
integer: new profiles start at 1; legacy profiles read as 0 without a write.
Changes to editable claims, confirmation, provenance or assessment evidence advance
it once, only after atomic replacement succeeds. Identical edits/confirmation and
history-only writes do not advance it. No public content hash or student data is
encoded in this metadata. Confirmation remains claim review, not authentication.

PUT/verify may send the revision they read. Under the existing cooperating local
profile lock, conflicting stale edits return 409. An exact repeat of the already
applied operation is safe; an old confirmation cannot confirm changed claims.
Legacy clients omitting revision retain compatibility and cannot receive full stale
edit protection. No records are merged, deleted or migrated.

Audit ambiguities: `verified` is a profile-wide confirmation gate, not per-field
verification; PUT saves pending claims and reconfirmation activates them. There is
no last-confirmed snapshot to serve while corrections are pending. Preserve this
workflow and its 422 domain gate. Failed updates leave the last persisted profile;
failure is request/UI state, not a persisted revision. Salary/direct placement use
independent form inputs, not a stored-profile prediction endpoint. Associate their
UI results with the actual submitted inputs and active identity; do not invent
profile-linked salary history.

## Dependency inventory

| Output | Influential profile fields | Calculation/storage | Refresh/freshness |
| --- | --- | --- | --- |
| Readiness, gaps, progress | Confirmation; named skills and role/project/certification support; assessment evidence; project/internship/certification lists; communication; personal/education completeness | readiness service, on demand | Response source revision; UI reload on shared revision |
| Eligibility | Confirmation; branch, CGPA, graduation year, backlogs; actual project/internship/certification counts; shared skill sufficiency | eligibility service, on demand, current company requirements | Response source revision; no profile-derived persisted cache |
| Company recommendations | Eligibility fields; readiness; skill evidence; all 16 mapped placement inputs | recommendation service, one snapshot, on demand | Response source revision; no history append |
| Skills and assessment suggestions | Current confirmed skills/support, provenance and latest trusted assessment | shared resolver, skills view, on demand | Response source revision; assessment completion refreshes profile |
| Placement summary/dashboard | Readiness plus 16 mapped inputs; performance histories | summary is read-only inference; dashboard joins independent GETs | Require matching source revisions; retry mixed snapshots |
| Profile placement prediction | Confirmation; 16 mapped inputs | explicit POST, append-only profile history | New entries retain source revision and mapped inputs; retries with the same optional Idempotency-Key do not duplicate history; unkeyed explicit POSTs retain their existing history behavior |
| Direct placement form | Actual submitted 16 inputs, prefilled from current profile | stateless inference; component result | Identity/revision + submitted input stamp; changed inputs require rerun |
| Salary form | Actual submitted request; model uses 12 fields, existing tier fallback/conversions | stateless inference, no stored history | Identity/revision + submitted input stamp; changed inputs require rerun |
| Performance | Original assessment/prediction history plus current readiness/skills | on demand, one loaded profile snapshot | Revision metadata on current projections; old predictions remain historical |
| Profile overview | Current claims, confirmation, completion, evidence | canonical GET + frontend flattening | Guard late responses and profile switches; retain same-profile data on refresh failure with explicit error |
| Browser mirrors/drafts | Active profile, editable prefills | local/sessionStorage UI convenience only | Never bootstrap authoritative state from mirror; identity/revision stamps isolate drafts/results |

## History and failure boundaries

Existing history without source revision stays unknown (`null` in response), never
backfilled. New source metadata describes only new predictions. Assessment scores,
timestamps, attempts and provenance remain unchanged by edits. Session/evidence
recovery remains the existing durable SUBMITTING protocol; one recovered evidence
projection advances revision once. JSON still cannot atomically commit both files.
Profile reads share the existing profile writer lock. Session reads and writes
also share a per-session lock: the profile lock is acquired before the session
lock, and initial owner-discovery reads release the session lock before acquiring
a profile lock. Session inventory reads use the same protected reader. This avoids
Windows replacement failures caused by another request holding a JSON file open.
Two deterministic open-reader regressions cover profile and session replacement.

Per-profile locks and atomic replacements cover cooperating local writers, not
multi-host storage or manual edits. No new database, authentication, model change,
historical migration or rollback rewrite is introduced.

## Validation and limits

Final isolated validation on 2026-11-07: focused revision/identity 43 passed;
relevant lifecycle/evidence/readiness/performance/API 171 passed; full backend
520 passed (10 existing joblib/NumPy warnings). Node frontend 121 passed;
lint/build succeeded. Chromium 156.0.8078.80 at 1440x1000: 14 passed, no page
errors. No final failures, errors, skips or deselections. All 530 protected
phase-start files retain their hashes. Exact commands, earlier failed executions,
changed files and complete Git inventory are in the Phase 29.3.6 historical phase report.

The frontend refreshes on successful mutations, assessment completion, focus,
storage events and explicit Retry; it does not continuously poll external changes.
Mixed revisions are refused with a refresh instruction. Same-profile data remains
in memory after refresh failure; dependent views show a failure rather than an
empty successful result. Profile Retry explicitly reloads the selected ID; a
DOM click event cannot become a request for the default demo profile.

One revision conservatively invalidates all profile-dependent consumers, including
when only non-model context or assessment evidence changes. Source revision is
not an owner identity, model-version guarantee or per-field confirmation timestamp.
Legacy revision-less clients remain susceptible to stale full-profile writes.
Pending edits retain the existing profile-wide confirmation gate; there is no
separate last-confirmed snapshot. Legacy prediction source revisions remain unknown.
Unkeyed explicit prediction POSTs remain repeatable records; callers requiring
retry deduplication must reuse an Idempotency-Key. At this historical checkpoint, no lost-start discovery or start idempotency
was added; later account-bound retry work added scoped start/creation receipts. JSON multi-file crash,
POSIX, multi-host and non-cooperating-reader guarantees remain unvalidated. No
historical migration, per-field confirmation, authentication or model/dataset change.
