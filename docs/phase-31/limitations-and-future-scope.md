# PlacePro — limitations, evidence and future scope

> Publication refresh (2026-11-24): current capabilities, 50 operations/45 paths,
> required artifacts and verification boundaries are summarized in the
> [reviewed release snapshot](../../backend/DEPLOYMENT.md#reviewed-release-snapshot-2026-11-24). Earlier dated results remain historical;
> no new application tests, browser acceptance or Linux/Docker success are claimed.

Prepared 2026-11-09. This document supports an honest final-year presentation of
the current working tree. Phase31 is an audit/preparation phase: no application,
authentication, ownership, historical data, model, dataset or dependency changes
are authorized or implemented here.

Read with the [overview](project-overview.md), [architecture](system-architecture.md),
[presentation outline](presentation-outline.md), [demo script](live-demo-script.md)
and [viva answers](viva-questions-and-answers.md).

## What the available evidence establishes

| Evidence | What it establishes | What it does not establish |
| --- | --- | --- |
| Current frontend/backend source and registered API inventory | Implemented routes, transport, ownership/revision checks, inference and rule logic; 50 operations across 45 paths. | That every workflow has been freshly tested or that the product is publicly deployable. |
| Read-only served model inspection | Logistic Regression placement pipeline and Ridge salary pipeline, their transforms and selected parameters. | Complete original training lineage, unbiased data, calibration or real-world performance. |
| Available CSV inspection | Two identical files, 100,000 rows, 26 columns; 54,459 Placed and 45,541 Not Placed labels; no blank/null-like cells in the audit check. | Dataset source authenticity, actual placement outcomes, registered user count or reproduction of the final placement model. |
| Recorded Phase30 validation | 1,125 backend tests and 195 frontend tests passed; 54 real HTTP assertions; lint and production build passed. | Fresh Phase31 test results, complete rendering/device checks, ML accuracy or security certification. |
| Recorded Phase29 browser validation | 40 Chromium assertions in that earlier phase. | New Phase30/31 browser execution or universal browser compatibility. |
| Owner's manual rehearsal report | Main workflows appeared to work across all three isolated synthetic accounts. | An independently audited scenario log, screenshots, assertion count or measured usability result. |
| Phase31 documentation/preservation checks | Preparation documents can be checked against inspected evidence, with earlier files/journal preserved. | A new software validation suite or changes fixing the limitations below. |

Historical Phase30 backend totals are 1,125 passed, zero failed/errors/skipped/
deselected and ten existing joblib/NumPy shape-deprecation warnings. Frontend totals
are 195 passed, zero failed/cancelled/skipped/todo, with deselection not applicable.
The build retained its intentional outside-root output notice. New Phase30 automated
browser/visual execution was blocked by approval-review failures; the subsequent
manual report is a separate evidence category. Phase31 reruns no backend/frontend
suite and performs no browser navigation.

## Demonstrable implementation and unavailable features

| Area | Current capability | Boundary to state to examiners |
| --- | --- | --- |
| Login/session/logout | Real server-side cookie sessions for available ACTIVE accounts; restoration, expiry and revocation handling. | Public registration/activation and recovery are unavailable. Google OAuth is implemented but optional and not provider/hosting-accepted. No working email-verification service is claimed. |
| Profiles | Safe new creation/review/editing and multiple ACTIVE owned profiles with revision checks. | Historical unowned records remain inaccessible; no automatic email-based claiming or profile merge. |
| Resume onboarding | Owned creation from readable PDF/DOCX, max 5 MB, extraction and student review. | Two standalone resume upload/analyze routes remain blocked; owned existing-profile preview/selective update is implemented; scanned-resume OCR remains unavailable. Numeric skill scores are not inferred from mentions. |
| Placement | Authenticated stateless form calculation and separate owned-profile history save/retrieval through secured analytics. | No verified final-artifact-linked accuracy or real-world probability calibration; not a placement outcome or guarantee. |
| Salary | Authenticated stateless Ridge estimate with explicit mapping, annual LPA and conditional-on-placement qualifications. | No salary-history API or individual uncertainty interval. Shared form fields are not all used by the salary model. |
| Readiness/skill gaps | Evidence-based weighted guidance and canonical skill matching. | Policy weights are not learned probability/accuracy. Missing evidence does not prove lack of ability. Learning links are static. |
| Eligibility/recommendations | PASS/FAIL/UNKNOWN requirements and weighted ranking with a mandatory-failure override. | Company criteria are DEMO/sample data, not verified current recruitment requirements. Ranking is not a trained hiring model. |
| Assessments/performance | Randomized questions, server deadlines/scoring, private history, attempts/cooldown and recoverable once-only evidence. | Question-bank practice is not professional certification; unlimited retakes/cooldown bypass are unavailable. |
| Dashboard/UI | Shared selected profile, probability/qualified salary preview, readiness/company/history views and guarded profile switching. | No independent visual/accessibility certification or complete device/browser-compatibility evaluation. |
| Local synthetic demo | Fresh temporary storage, three fixture accounts, generated resume, normal authentication/ownership and read-only model use. | Not a public trial account system, production administrator, real student outcome experiment or deployment-ready service. |

## Machine-learning and dataset limitations

### Dataset provenance and reproducibility

The available placement.csv and salary_model/placement.csv have the same SHA256:
b9d88bd7afd389d42aa3c308fc026b50983f717c399597302c2f06bce2436e99.
Historical notes describe synthetic data; the original provider/generator is not
verified. Do not assign a dataset source such as Kaggle or a university without evidence.

The final placement artifact accepts sixteen raw features that differ from the
available CSV. Referenced data/placement_phase6.csv and phase8_final_pipeline.py
are absent. The saved artifact and inference logic exist, but exact original
placement training-data/split/run reproduction is not established.

Historical inspection of the salary training source found placed records and an 80/20 split with
random_state 42 and MAE-based model comparison. It must not be executed during
preparation because it writes model artifacts. The training script and CSVs are excluded from the runtime release; the checked-in
aggregate summary records provenance without requiring them for inference.

### Performance metrics and interpretation

No final placement accuracy is asserted. Probability and max(p, 1-p) class confidence
are model outputs, not measured correctness or calibrated individual chances.
Software test counts must not be used as ML performance metrics.

The historical salary-evaluation summary reports historical salary MAE 0.797784 LPA, RMSE 0.998541 LPA
and R² 0.606406 on 10,892 rows, reconstructed from the script split on 2026-11-06.
Those values are not newly rerun results, independent real-world holdout evidence
or fully established original training-run provenance. They are deliberately
excluded from headline presentation claims; explain their qualification if asked.

Salary input clipping limits individual feature values, but Ridge can still
predict outside observed target bounds. Unusual combinations of supported values
may still lack meaningful training support. Provisional extracurricular mapping,
unseen categories and self-reported scores add interpretation uncertainty.

### Evidence and decision validity

Profile confirmation records reviewed student claims. It is not independent
verification of academic achievements or competence. Qualifying assessment evidence
comes from the configured practice bank, not employer observation.

Readiness/recommendation weights are explicit design policies. They have not been
validated as causal interventions or real hiring probabilities. Branch/tier and
unverified data-generation choices can introduce fairness concerns; no subgroup
or deployment fairness certification is claimed.

## Storage, retry and deployment limitations

- Authentication/company SQLite and student JSON are separate stores. There is
  no shared distributed atomic transaction.
- Profile publication stages PENDING ownership, exclusive JSON creation and ACTIVE
  activation. Interrupted/pending creation remains quarantined; automatic repair
  is not implemented.
- Local cooperating thread/OS locks and SQLite constraints protect inspected
  operations. They do not establish multi-host coordination, power-loss safety
  or network-filesystem correctness.
- Account/operation/resource-scoped retry identities require valid session,
  ownership and payload/source/revision compatibility. They are not secret access
  credentials; completed assessment duplicates still return 409.
- Retry keys/receipts lack TTL cleanup. This audit neither deletes retained
  evidence nor implements retention/recovery policy.
- HTTPS and production cookie/Origin policies exist, but public deployment,
  load capacity, operational recovery and complete privacy/security review have
  not been established.
- The health endpoint is static liveness; a successful response is not proof that
  models, storage and every student feature are ready.

## Discrepancies resolved in the preparation material

The following are documentation/claim distinctions, not application fixes made in Phase31.

| Earlier wording or possible assumption | Verified current evidence | Presentation wording |
| --- | --- | --- |
| Historical demo prompt/docs and frontend registration validation mentioned 12–128 characters. | Backend password validation requires 15–128; public registration is currently blocked. | Choose a hidden demo password of 15–128 characters. The launcher prompt now matches its validator; do not weaken validation. |
| All saved models in the repository are candidate “production models.” | Served placement artifact is Logistic Regression; served salary artifact is Ridge. Other experiment/backup artifacts exist. | Explain the two production artifacts and the separately served synthetic V1 artifact. |
| Available 100,000-row CSV fully explains the final placement training run. | Its schema differs from the final raw contract; referenced final training files are missing. | Separate available-data counts from unverified final placement lineage. |
| Pipeline comments imply complete no-leakage/training consistency proof. | Inference exclusions/transforms are inspectable; original split/data provenance is incomplete. | Describe verified inference protection without certifying the absent training experiment. |
| Clipping salary inputs necessarily keeps salary inside training target bounds. | Ridge has no target-range constraint. Some service comments overstate the guard. | Individual input-range guards reduce extrapolation; outputs are not guaranteed bounded. |
| A shared form field must affect both models. | Salary ignores DSA, ML knowledge, system design and open-source contribution fields. | Explain separate feature contracts and mapping. |
| RESERVED → IN_PROGRESS → SUBMITTING → COMPLETED → COOLDOWN → RETAKE are all persisted enums. | Persisted assessment states are IN_PROGRESS, SUBMITTING, COMPLETED and EXPIRED. Reservation, cooldown and retake are workflow policies. | Use the actual state diagram and describe policies separately. |
| Earlier report totals remain the latest validation. | Phase30 recorded 1,125 backend, 195 frontend and 54 HTTP assertions; later reviewed Windows totals are 1,362 backend and 462 frontend; Phase29 Chromium 40 are older evidence. | Label every count by phase and type; do not combine overlapping suites or call HTTP assertions browser assertions. |
| New manual rehearsal makes the previous blocked browser checks “passed.” | User reports observed main-workflow success; no complete quantified manual evidence was supplied. | Keep historical blockage and later manual observation distinct. |

No stale documentation or source comment is silently changed to conceal these
differences. This package provides accurate wording while preserving existing work.

## Future scope — proposals only

| Priority | Proposed next work | Evidence/approval needed |
| --- | --- | --- |
| Presentation preparation | Build the actual slides, collect manually captured synthetic screenshots, rehearse timing and team ownership of explanations. | Confirm college time limit, names/guide details and actual recorded observations. No application changes required. |
| Reproducible ML evidence | Recover final training provenance; link dataset, split, preprocessing, parameters and artifact hashes; evaluate on permitted representative data. | Separate approval before any training/model/dataset change. Never backfill a metric as though it came from the original run. |
| Account onboarding | Implement approved email activation/recovery and user-facing flows while retaining secure sessions/ownership. | Architecture/service decisions, credentials and security validation under a separately authorized implementation phase. |
| Recruitment data | Add permitted current company requirements with source/version tracking and evaluate usefulness. | Verified sources, domain review and data-use permission; no invented cutoffs. |
| Resume improvements | Evaluate OCR/structured extraction and better evidence review on permitted documents. | Privacy/file-security evaluation and approval for dependencies/services. Current readable extraction remains accurately labelled. |
| Storage/operations | Review pending repair, retention, backup/recovery, multi-worker deployment and cross-store consistency requirements. | Explicit approval for migrations/new storage or historical-data operations; tested non-destructive recovery plans. |
| Product evaluation | Record systematic end-to-end, device, accessibility and user-experience scenarios. | Isolated accounts/data and measured results. Public deployment requires its own evidence and approval. |

Do not advertise these proposals as completed features. Phase31 does not launch
an implementation phase or change the existing trust boundary.

## Safe demonstration boundary

Use the [live-demo script](live-demo-script.md) and the existing
[launcher guide](../phase-30-demo-workflow.md). The operator chooses the hidden
password; it is not printed or embedded in source. Each run creates a fresh isolated
workspace and normal authenticated fixtures. Use the generated readable synthetic
resume, actual returned model/practice results and sample company criteria.

Do not show historical student records, cookies, authentication secrets, answer
keys or private developer-tool responses. Do not claim guaranteed placement,
salary offers, real hiring criteria, successful unsupported operations or complete
security certification. If a live action fails, explain the failure and use only
accurately labelled recorded synthetic evidence.

## Preservation and preparation verification

The Phase31 baseline uses SHA256 hashes for existing project/data/model/evidence
files and read-only Git state. It excludes .git, dependency/virtual-environment
directories, caches, agent-setting directories and this phase's own evidence
directory. It includes retained earlier scratch evidence. The baseline contains
3,178 files, 60 modified tracked files, 99 grouped untracked entries and 140
expanded untracked paths, with an empty index.

No dependency installation, application server,
browser automation, schema migration, model training or historical student write
is part of this phase. 
