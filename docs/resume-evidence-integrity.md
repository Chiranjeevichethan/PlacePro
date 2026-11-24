# Resume extraction and profile integrity — Phase 29.3.5

> Historical snapshot: the original phase dates, design decisions and recorded
> test results below are preserved. Statements about the then-current inventory,
> unavailable features and pre-authentication behavior are superseded by the
> [reviewed 2026-11-24 release snapshot](../backend/DEPLOYMENT.md#reviewed-release-snapshot-2026-11-24).
> This documentation change reruns no application tests and establishes no new
> Linux/Docker or browser acceptance.

Decided 2026-11-07 after reading the complete historical phase report, the Phase
29.3.4 skill evidence policy and current parser, routes, storage and UI.

## Identity decision (before implementation)

There is no authenticated identity or verified email ownership in this app.
`verified` means the student confirmed profile claims. An email, name, phone,
locally stored profile ID or client-supplied verification flag does not establish
ownership. Never look up and merge profiles by email, even when claims are confirmed.

The minimal workflow is read-only resume analysis when a current profile is loaded.
It creates no draft, changes no active ID and copies no previous values into another
profile. The student compares extraction with their current information, then makes
explicit corrections through Edit Profile and reconfirms. Conflicting names/emails
remain independent extraction claims; there is no automatic application. New-profile
creation still issues an independent UUID and requires confirmation. Direct repeated
calls to from-resume can therefore create separate drafts; deduplication requires
real ownership verification and is deferred. Do not present this as verified email
reuse or an authentication solution.

A real selected-profile GET 404 offers explicit new-profile creation. Network/503
failures offer Retry and cannot enter creation. A draft is selected only after the
student confirms it; extraction alone cannot switch the active ID.

## Evidence and extraction decisions

The [skill evidence policy](skill-evidence-policy.md) remains authoritative. Current
confirmed claims replace original extraction; assessments remain independent. Edits
reset confirmation and cannot write assessment evidence or prediction history.
Preserve original extracted values and available provenance; do not attach assessment
timestamps to claims or infer skill scores from technology mentions.

Sections are identified by whole-line known headings, including common boundary-only
headings. Capitalization alone cannot identify a boundary. Stated heading counts are
ignored. Missing headings require explicit field labels/context rather than scanning
unrelated prose for skills or using every year as a graduation date. Unknown templates
remain a review limitation. Repeated section headings bound the first section; the
existing single-span output retains the first occurrence.

Certification titles can be uppercase or punctuated. Labeled credential IDs, URLs,
status, issuer and date metadata are not titles. Reliable issuer and issue-year data
can attach to the preceding title; expiry dates do not become issue years. Duplicate
compatible titles coalesce; contradictory issuer/year records stay separate for review.
The existing name/issuer/year contract cannot represent full issue dates or IDs.

Structural corrections use actual records and skill lists, never synthetic entries
created from counts. Open-source and extracurricular text can be retained as additive
achievement lists; their ML count inputs still require manual input.

## History findings and migration recommendation

Assessment sessions reference their original profile_id; profile assessment evidence
and placement prediction history are stored on that profile. Performance projects
these histories. Salary prediction is a stateless request and has no stored profile
history; direct placement requests likewise do not append profile history. A previous
re-upload created a new UUID and could switch the UI to it, leaving original records
accessible through the older ID. No records were transferred or deleted by that flow.

No historical migration is performed. A future migration must first establish owner
identity, inventory every affected ID/session/history, obtain explicit approval of a
mapping and backup/rollback plan, then reconcile records transactionally with duplicate
and reference checks. Email-only bulk merging is not an acceptable migration.

## Audit of the eight earlier findings

Partial 29.3.5 changes were already present at
continuation start and were inspected/preserved as a historical baseline.

| Finding | Verification and final behavior |
| --- | --- |
| Uppercase title terminates extraction | Original CAPS_HEADING_RE stops on AWS CERTIFIED CLOUD PRACTITIONER and loses the next title; reproduced from retained source in memory. Known whole-line headings now bound extraction. |
| Period-ending title dropped | Original record filter rejects every final period; reproduced in memory. Genuine punctuation survives. |
| Certificate ID becomes record | Original emits Certificate ID: ABC123; reproduced in memory. IDs, links, status, issuer and date lines are now metadata. |
| Same-email upload generates new ID | Backend always uses uuid4 and has no ownership lookup. Explicit creation still produces a distinct draft; loaded-profile uploads now use read-only analysis. |
| Inconsistent carry-forward | Original UI fills missing education, ML inputs and additional info on an email match, including prior resume-derived education. This merge is removed; explicit current-profile edits retain untouched values. |
| Assessment history stays on older ID | Sessions reference profile_id; evidence/history live on that profile. Original confirmation selects a new ID without transferring history. Read-only review retains current selection/history. |
| Structural records cannot be corrected | Original modals expose counts/read-only structures. Current editors support skills, projects, internships, experience, certifications, activities and personal/education details. |
| Confirmed claims precede originals | The 29.3.4 shared resolver already implements this. Corrections preserve originals/assessments, reset confirmation and replace active claims after reconfirmation. |

## Section and storage behavior

pypdf extracts page text; python-docx extracts paragraphs, then table cells. No OCR
or layout reconstruction exists. Known whole-line headings allow bullets, numbering,
colons and stated counts. Boundary-only headings include summary, interests, languages,
references, publications, coursework and personal details. Capitalization alone is not
a boundary. The existing single-span contract retains the first occurrence per section.

Personal fields use header/contact heuristics; email and links still scan the full
text. Education uses its section or explicit header education lines. Graduation-year
fallback now reads degree/college/date-range lines, excluding unrelated scholarship
expiry years. Skills scan only their section or explicit inline header labels. Named
technologies stay on relevant project/role records; mentions never become numeric
scores. Undated roles keep null duration; body verbs/dates do not create roles or
durations. Explicit bullet project titles take precedence over plain-title detection.

Certifications retain name/issuer/year. Explicit metadata and recognized compact
issuer layouts can supply issuer/year. Associate and comma-bearing title suffixes
remain in names. Common issue dates are validated before retaining the stated year;
expiry/ID numbers cannot supply issue years. Compatible duplicate titles coalesce;
conflicting metadata records remain reviewable. Missing metadata stays null. Full
dates, IDs and URLs cannot be represented by the unchanged certification contract.

Open-source/extracurricular sections retain literal text in additive achievement
lists. Hackathon summaries stay one description rather than inventing multiple events
from a number. Numeric ML contribution/activity inputs remain manual. Counts derive
from actual lists; structural correction never creates synthetic records from totals.

Upload/analyze store no profiles. From-resume saves an unconfirmed JSON draft only
after successful extraction/analysis; OCR, corruption and analysis failures create
no draft/lock. Uploaded files remain temporary. APIs preserve their existing 500-char
preview and field provenance/snippets. Canonical profiles retain extracted values in
original_resume_values. Full raw resume text and binaries are not retained. Existing
transactions protect independent assessment/history during edits.

## Generalized storage/ownership guidance

The earlier local storage census and shared-email/history details are not public
release evidence. Duplicate-looking claims never establish common ownership.
Session/history references must remain associated with their original authorized
profile, and any migration requires an explicit mapping, backup and rollback
review. Current authentication and owned resume updates supersede the pre-auth
flow described in this historical document.

## Validation and remaining limits

Final isolated backend: 496 passed, 0 failed/errors/skipped/deselected; 10 existing
joblib/NumPy warnings. Node: 103 passed, 0 failed/skipped; lint/build passed. Chromium 156.0.8078.80 at 1440x1000: 10 final scenarios passed, 0 failed/skipped,
no page errors. All 530 protected phase-start files unchanged.

No authenticated or verified-email ownership path exists, so that branch cannot be
claimed implemented/tested. Direct repeated from-resume calls can create independent
same-email drafts. No historical inflated counts were bulk corrected. JSON cooperating
local-writer/crash/multi-host limits and stale full-profile concurrent edits remain.

Known-heading/English/fixed-vocabulary heuristics do not establish arbitrary-template
accuracy. Unknown headings, later repeated sections, multi-column layouts, DOCX
paragraph/table reading order, wrapped titles, negated skill prose, ambiguous GPA
scale and multiple education records remain review limitations. The downstream shared
taxonomy has a smaller vocabulary; unknown claims remain stored but may be absent from
canonical matching. Mobile/other-browser behavior and a broad accuracy benchmark were
not validated. Historical identity migration needs the approved plan above.

The final source inspection also found that the existing permissive personal-link
regex can treat a degree abbreviation such as `B.Tech` as a portfolio domain. This
personal-link false positive remains a follow-up issue; structural review can correct
or clear it without rewriting original extraction.
