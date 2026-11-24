# Phase 30.1 — Product demonstration readiness audit

> Historical snapshot: the original phase dates, design decisions and recorded
> test results below are preserved. Statements about the then-current inventory,
> unavailable features and pre-authentication behavior are superseded by the
> [reviewed 2026-11-24 release snapshot](../backend/DEPLOYMENT.md#reviewed-release-snapshot-2026-11-24).
> This documentation change reruns no application tests and establishes no new
> Linux/Docker or browser acceptance.

Audit date: 2026-11-09. The Phase 29 completion snapshot matches current source
and working-tree entries. The reported 1,118 backend/181 frontend tests and 40
Chromium assertions are retained prior evidence, not a new Phase 30 test run.
Classification below concerns the authenticated local student workflow; COMPLETE
does not mean publicly deployed, independently validated ML, or universally accessible.

| Feature | State | Verified evidence / limitation |
| --- | --- | --- |
| Registration and login | PARTIALLY COMPLETE | auth.py/security.py and Login.jsx use real session login; register deliberately returns 503 pending activation. Recovery/social login unavailable. |
| Session restoration and logout | COMPLETE | auth.js/apiTransport.js, session tests and real-browser refresh/revocation assertions. Cookies HttpOnly; CSRF in memory. |
| Student profile creation | COMPLETE | owned_profile.py/service and profile-ownership tests: server ID, active ownership, no historical claim. |
| Profile editing | COMPLETE | reviewed revision, full editable payload, stale 409 and explicit reconfirmation; EditProfileModal/profileReview and prior browser assertions. |
| Multiple profiles / switching | COMPLETE | server-owned list, account-scoped selection, remounted workspace, late-response rejection. |
| Resume-based profile creation | COMPLETE | owned from-resume -> draft review -> confirmation; DOCX real-browser and PDF/DOCX backend regressions. |
| Resume extraction | PARTIALLY COMPLETE | pypdf/python-docx plus integrity tests; scanned PDFs need OCR (not implemented). Standalone upload/analyze and existing-profile resume comparison remain UNAVAILABLE. |
| Placement probability | COMPLETE | real classifier, authenticated stateless form and separate owned stored prediction; no calculator/history contract change. |
| Salary prediction | COMPLETE | real Ridge calculation and qualified conditional result; separate form, no stored salary-history endpoint. |
| Placement readiness | COMPLETE | owned rule-based evidence/revision-consistent response and dashboard. It is distinct from model probability. |
| Skill-gap analysis | COMPLETE | owned readiness/evidence -> actionable gaps; learning resource catalogue is static. |
| Company eligibility | COMPLETE | owned eligibility endpoints with PASS/FAIL/UNKNOWN, existing demonstration requirements. Not real recruitment acceptance. |
| Company recommendations | COMPLETE | backend ranking/groups/reasons and live browser results; company requirements remain labelled DEMO. |
| Mock assessments | COMPLETE | bound start/get/submit, timer, recovery, cooldown/quota, scoring and once-only evidence. |
| Assessment history | COMPLETE | owned lifecycle GET with CSRF/Origin, browser history/results and backend isolation tests. |
| Performance analytics | COMPLETE | owned prediction/assessment histories, readiness and revision freshness; no demo fallback for accounts. |
| Dashboard | PARTIALLY COMPLETE | real readiness/prediction/history/companies; no salary preview, limited first-profile guidance, misleading REAL DATA chip for synthetic records. |
| Error handling / empty states | PARTIALLY COMPLETE | session unavailability/expiry, malformed response, CSRF and stale revision tested; empty workspace and recovery guidance can be clearer. |

## Five largest demonstration obstacles

1. Evaluators cannot self-register an activated account. Prior synthetic provisioning
   lives in scratch test harnesses, not a supported repeatable local demo launcher.
2. A fresh extracted resume lacks self-assessed ML inputs. The dashboard should lead
   the student to complete and confirm the profile before saving a model prediction.
3. Dashboard salary context is absent and its REAL DATA chip can imply a synthetic
   input represents a measured outcome. A qualified model estimate and explicit
   synthetic-demo label are needed.
4. The notification button displays an invented count of three and performs no
   action. Confidence/probability terminology needs an explanation rather than
   implying model accuracy or placement guarantees.
5. Existing company requirements are demonstration seed data; activation, OCR and
   live recruitment data are unavailable. A convincing rehearsal needs clear scope,
   consent-free synthetic fixtures and a complete walkthrough rather than hiding gaps.

## Implementation decisions

Reuse the unchanged app in explicit existing loopback development mode. Provision
only newly generated synthetic accounts into a new isolated directory; require real
password verification, session/CSRF and active profile ownership. Never accept an
existing storage directory or point the launcher at historical data. Credentials
must be operator-entered (masked), never shipped in frontend source or logs.
Use secured HTTP APIs for all demonstration profile/prediction/assessment operations.
The launcher must not introduce an activation endpoint or security bypass.

Improve journey guidance and dashboard salary/model presentation without changing
schemas, models, feature mappings or ranking/scoring mathematics. Retain every
existing page and assessment workflow. Validate the new launcher against isolated
fixtures and the real frontend bundle, then run the complete regression suites.

## Preservation baseline

Branch bhargav-frontend; HEAD f84099349d104e4e77c7080fba4465ca4e3470a4;
60 modified tracked, 93 grouped untracked, 128 expanded untracked, empty index. 3,086 baseline files include prior scratch/backups/evidence, excluding .git,
node_modules, virtual environments, caches, agent settings and this Phase 30
evidence folder only. The prior final inventory had 2,869 files: the 217-file
difference is retained Phase 29 evidence previously excluded by that phase's
inventory. No files were removed to reconcile counts.

Public deployment, real activation/provider, OCR and new recruitment data require
separate work. They do not block a strictly local isolated synthetic demonstration.

## Phase30.5 — ML/data presentation findings

Source reviewed: src/pipeline.py, ML feature mapper, salary request/service,
readiness/evidence engine, eligibility/recommendation service, frontend mapping
and result presenters, plus existing model regressions. Models/datasets remain
byte-identical; no accuracy, F1, R-squared or real-world calibration result is invented.

- Placement returns placed-class probability and predicted class from the served
  classifier. Confidence is max(p, 1-p), derived from that same probability,
  not independent accuracy. The UI now labels/explains model class confidence.
- Salary uses the existing placed-student Ridge model, known-tier preservation
  and documented missing-tier fallback. Its existing feature-support bounds and
  provisional extracurricular-count mapping limit interpretation; the new
  explanation states annual LPA, placement conditioning and uncertainty without
  fabricating an individual confidence interval.
- Canonical branches/tiers and documented frontend stateless branch synonyms
  remain unchanged. Unknown stored-profile branches require explicit correction;
  frontend stateless ISE-to-CSE mapping does not establish stored-profile support.
- Resume extraction never invents the ten self-assessed ML inputs. Genuine zero
  values remain distinct from missing values. Unsupported/out-of-range request
  handling and model-loading errors remain existing behavior, checked by regressions.
- Readiness weights and evidence provenance are unchanged. Missing/insufficient
  evidence does not prove inability. Company scores rank against demonstration
  requirements; they are not hiring probabilities or verified recruitment criteria.

126 focused placement/salary regressions pass with ten existing joblib/NumPy
warnings; 195 frontend tests, lint and a fresh build pass. Visual/browser checks
remain blocked by automatic tool approval-review failure; they are not counted
as successful Phase30 validation. See the final validation report for exact scope.

## Phase30.6 — Delivered state after the audit

The table above is the initial audit, not a claim that its dashboard obstacles
remain unresolved. The isolated launcher, empty/incomplete-profile next steps,
dashboard salary preview/placement meter, synthetic context, disabled notification
placeholder and estimate/evidence explanations are now implemented.
Company criteria remain explicitly sample data; activation/recovery and OCR remain
unavailable. No existing student record or ML asset was changed.

New validation passes 1,125 backend tests, 195 frontend tests, 54 real HTTP workflow
assertions, lint, production build and production startup/inventory checks.
The new visual/browser evaluation remains blocked, so a complete new browser
rehearsal is still required. See [validation and handoff](phase-30-validation.md)
and [demo run instructions](phase-30-demo-workflow.md) for the exact scope,
created/modified files, isolation results and limitations.
