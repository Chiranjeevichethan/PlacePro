# PlacePro skill evidence policy — Phase 29.3.4

> Historical snapshot: the original phase dates, design decisions and recorded
> test results below are preserved. Statements about the then-current inventory,
> unavailable features and pre-authentication behavior are superseded by the
> [reviewed 2026-11-24 release snapshot](../backend/DEPLOYMENT.md#reviewed-release-snapshot-2026-11-24).
> This documentation change reruns no application tests and establishes no new
> Linux/Docker or browser acceptance.

Decided on 2026-11-07 after inspecting profile storage, assessment persistence,
readiness, eligibility, recommendations, skills view and their schemas/callers.
This policy governs skill evidence, not company requirements or ML inputs.

## Authority and conflict resolution

1. The current profile is authoritative for student claims. Resume originals are
   audit records, not active claims: a student edit/removal replaces the extracted
   value. Confirmation makes current resume/user/project/internship/experience/
   certification mentions usable evidence, but does not establish tested proficiency.
   Provenance is resolved per field, not for the entire skills section.
2. A server-recorded assessment with `source: assessment`, `verified: true` and a
   finite numeric score in [0, 100] is independent evidence of performance on that
   named PlacePro assessment. The latest completion timestamp wins per canonical
   skill; attempt ordinal breaks ties, then assessment ID makes ties deterministic.
   Missing/malformed/naive timestamps sort before usable UTC timestamps. No timestamp
   is invented. Stored attempt history remains intact.
3. A valid latest assessment takes precedence for skill sufficiency, even when its
   score conflicts with a confirmed mention. The existing PlacePro threshold is 60:
   scores >=60 satisfy evidence matching; scores <60 are **insufficient evidence**.
   This threshold is an evidence policy, not a new company cutoff. Insufficient
   evidence leaves skill eligibility UNKNOWN/INCOMPLETE, rather than asserting the
   student fails an unstated company assessment requirement.
4. Invalid/unverified latest assessment records cannot grant skill credit or numeric
   bonus and cannot override confirmed claims. An older passing attempt is not
   resurrected in place of an unusable newer record. With no confirmed claim, expose
   INVALID/UNCONFIRMED evidence. Missing evidence has score `null`, never zero.
5. Manual `ml_inputs` scores remain student-provided numeric features. Coding is not
   a Python score; DSA, communication, aptitude, ML knowledge and system design have
   their own existing scales. They neither manufacture named skill mentions nor
   overwrite assessment scores. Explicit company numeric requirements continue to
   use the existing feature mapping. No assessment verifies other profile fields.

## Verification, age and edits

- Readiness, eligibility and recommendation APIs require profile confirmation;
  unverified/edited profiles retain the existing 422 contract. The shared resolver
  retains unconfirmed claims and independently verified assessments for inspection.
- Profile editing preserves server assessment evidence/history and resets profile
  verification. Reconfirmation activates current claims again. Editing or removing
  a claim does not erase an independent assessment or turn a low score into a pass.
- Assessment evidence has completion timestamps. Profile claims have provenance
  paths, but no persisted per-field confirmation/edit timestamps. Represent absent
  claim timestamps as null; do not infer them from assessment completion.
- There is no assessment evidence expiry policy. Old assessments remain evidence;
  session deadlines and the 24-hour retake cooldown do not expire completed evidence.
  No arbitrary age limit is introduced. Age and historical proficiency remain limits.

## Shared projections and counting

Normalize all skills through the taxonomy (including the bank's HTML/CSS pair).
Keep source, original mention, field/record path, verification and available timestamp.
Deduplicate aliases/repeats within a single record; distinct project records remain
distinct support. Readiness coverage and matching count each canonical skill once.
Only the latest trusted assessment per skill contributes the existing qualifying
average/5-point bonus, capped within the unchanged 30-point technical component.
Coverage and bonus are existing separate signals, never repeated-attempt credits.

Readiness gaps distinguish MISSING, INSUFFICIENT, UNCONFIRMED and INVALID evidence.
Eligibility and recommendations use the same sufficiency result. The skills view
shows current claim origins separately from assessment score/verification and adds
evidence status, sources and the available assessment timestamp. Stored originals
and assessment history are preserved; rejected evidence is not silently rewritten.

## Levels and API compatibility

Both readiness and assessment scales use [0,40), [40,60), [60,75), [75,90),
[90,100]. Existing labels and weights are preserved. Classification uses the
provided score without rounding; invalid/nonfinite/out-of-range scores raise a
controlled ValueError instead of receiving a misleading level.

Readiness totals/technical components are JSON numbers and may contain fractions.
Readiness, placement-summary, recommendation and performance response schemas must
accept those fractions. The historical integer-only declarations rejected valid
bonuses; the approved schema correction now permits fractional numeric results.
Existing field names, labels, endpoints and request bodies remain. Evidence metadata
is additive. Existing frontend numeric consumers accept fractions; UI formatting
may round presentation without changing backend classification.

Company requirement data and its existing DEMO status remain unchanged.
