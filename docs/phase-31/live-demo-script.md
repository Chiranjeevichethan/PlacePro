# PlacePro — isolated synthetic live demonstration script

> Publication refresh (2026-11-24): current capabilities, 50 operations/45 paths,
> required artifacts and verification boundaries are summarized in the
> [reviewed release snapshot](../../backend/DEPLOYMENT.md#reviewed-release-snapshot-2026-11-24). Earlier dated results remain historical;
> no new application tests, browser acceptance or Linux/Docker success are claimed.

Prepared 2026-11-09. Target duration: approximately **10–12 minutes**. The project
owner reports that the main workflows appeared to work across the three synthetic
accounts during manual rehearsal. This script is a repeatable presentation plan;
it does not claim new automated or fully recorded manual results.

Use only the isolated launcher. Do not start a generic backend against `data/`,
claim historical profiles, change authentication policy or run training scripts.
The following commands are for the operator's interactive rehearsal; Phase31's
documentation audit does not launch or stop your servers.

## Preparation before the examiner arrives

1. Use the existing installed environment/dependencies. Do not reinstall packages.
2. Choose free loopback ports; the launcher refuses occupied ports. Preserve any
   unrelated running service and choose different port arguments when necessary.
3. Open an interactive PowerShell terminal and run:

```powershell
# Run from the repository root with the existing pinned Python environment activated.
python -B scripts/demo.py
```

4. At `Choose a demo password ...`, enter a **15–128-character** password, press
   Enter, and repeat it at `Confirm demo password:`. Typed characters are hidden.
   The current launcher prompt and demo validator both require 15-128 characters.
   There is no fixed password; use the operator-chosen value for all three accounts.
5. Wait for the launcher to print `Open:` and the resume path. Keep the terminal open.
6. In Chrome, manually open **http://127.0.0.1:5173** using the default ports.
   The API is on **http://127.0.0.1:8765**; it is not the frontend address.
7. Record the actual printed `Synthetic-Resume.docx` path for the file picker. Each
   launch has a new temporary path—never hard-code a previous workspace name.

If ports must differ, the actual supported optional arguments are:

```powershell
# Example only: these ports must also be free.
python -B scripts/demo.py --api-port 8766 --frontend-port 5174
```

Use the corresponding printed frontend URL, `http://127.0.0.1:5174` in that
example. The launcher configures the child API's exact Origin and the new bundle's
API address. It creates a new temporary store/bundle each launch and retains it
after shutdown. Never expose it publicly or embed the password in slides/source.

## Synthetic account map

| Account | Initial fixtures | Demonstration purpose |
| --- | --- | --- |
| `demo-student-a@example.test` | Two owned synthetic profiles; primary profile has an actual model-calculated history entry | Dashboard, existing profile, multiple-profile switching. |
| `demo-student-b@example.test` | Its own two profiles and independent primary prediction history | Account isolation and independent workspace. |
| `demo-empty@example.test` | No profile/history initially | Resume extraction, review and first-profile onboarding. |

All names/colleges/projects/inputs are fictional. Company criteria remain DEMO
requirements. No score or placement outcome is fabricated for the demonstration.

## 1. Introduction and login — 30 seconds

**Do:** Show the login page and synthetic notice. Sign in as account A using the
operator-chosen password. Use email/password login; do not attempt self-service registration.

**Say:** “This is a local demonstration with fictional students. Login uses a
server-side cookie session; it is not a hard-coded frontend login.”

**Observe:** Protected navigation/dashboard appears after the real login completes.
If login fails, show the error honestly and verify the chosen credentials/printed URL.

## 2. Student dashboard — 45 seconds

**Do:** Identify the selected A profile. Show readiness, placement probability,
profile completion, assessment count, prediction trend and recommended companies.
Request the dashboard salary preview if inputs are usable.

**Say:** “The dashboard combines results for this owned profile. Model estimates,
preparation scores and practice results have different meanings. The initial
prediction was calculated by the backend from synthetic inputs.”

**Observe:** Values come from the API; an empty assessment history is expected on
a fresh launch. Salary preview does not append placement-prediction history.

## 3. Profile information — 45 seconds

**Do:** Open Student Profile. Show academics, skills, projects and model inputs.
Open Edit Profile, explain review/reconfirmation, then cancel if time is short.
Use the profile selector to show A's second profile and return to its primary profile.

**Say:** “An account may own multiple profiles. Selection refreshes the workspace;
the previous profile's results are not displayed under the new profile.”

**Observe:** Identity and profile-specific data change. The seeded profiles are
synthetic fixtures; do not imply that their fields were all extracted from a resume.

## 4. Resume onboarding — approximately 2 minutes

**Do:** Log out A and sign in as `demo-empty@example.test`. Show the empty workspace
and Create profile guidance. Upload the generated `Synthetic-Resume.docx` using
the current launcher-printed path. Review the extracted sections and confirm only
the claims you inspected.

If the profile is confirmed but ML inputs are missing, open Edit Profile and enter
the missing synthetic values below, save, then reconfirm. Follow the UI's next-step
guidance rather than claiming that extraction supplied the numeric skill scores.

| Field | Suggested explicitly synthetic input |
| --- | --- |
| Branch | CSE, explicitly selected if extraction needs correction |
| CGPA | 8.2, explicitly reviewed |
| College tier | Tier 3 |
| Backlogs | 0 |
| Coding / DSA | 7 / 7 on the existing 0–10 scales |
| Aptitude | 75 on the existing 0–100 scale |
| Communication / ML knowledge / system design | 7 / 5 / 4 |
| Open-source contributions / extracurricular activities | 0 / 1 |

Keep project/internship/certification counts derived from the actually reviewed
lists. Do not add fictitious experience just to force a high score. These are
suggested fixture inputs, not model outputs or verified student achievements.

**Say:** “The parser extracts readable document text and structured claims. It
does not turn the word Python into a coding score. I supply and review missing
information explicitly before using the stored-profile prediction.”

**Observe:** A new server-generated owned profile is created. Confirmation and
ML completeness are separate; review may be confirmed while inputs still need entry.

## 5. Placement prediction — 50 seconds

**Do:** On this newly reviewed profile, open Placement Prediction. Review prefilled
values, calculate, and expand “How to read this estimate.” Return to Dashboard
and use **Save profile prediction** to demonstrate persistent owned history.

**Say:** “The Logistic Regression pipeline produces this estimate. Class confidence
comes from the same probability and is not model accuracy. The independent form
is stateless; the dashboard save action creates authorized history separately.”

**Observe:** Use the actual returned number without promising a target probability.
Do not repeatedly save just to create a nicer trend; retry integrity may return
the compatible existing result rather than another entry.

Optional current-feature extension: open Experimental V1 to show its explicit
synthetic limitation and editable profile prefill. Goals, notifications and Resume
Builder/PDF export are implemented; rehearse them in the isolated environment
before including them in a presentation. These are proposed demonstration steps,
not claims that current browser acceptance has passed.

## 6. Salary prediction — 45 seconds

**Do:** Open Salary Prediction, review prefilled inputs, calculate and show the
annual LPA/conditional-on-placement qualification and model explanation.

**Say:** “This uses a separate Ridge model with its own 12-feature mapping. It is
an estimated annual salary if placed, not a guaranteed offer or confidence interval.”

**Observe:** Report the actual value. Do not describe salary edits as profile
updates; independent calculator edits stay local and do not create salary history.

## 7. Readiness and skill gaps — 40 seconds

**Do:** Open Skill Gap Analysis and identify a strength, a missing/insufficient
evidence item and an improvement action. Show the separate readiness score.

**Say:** “This is explainable preparation scoring, not the classifier's probability.
Missing evidence means the profile does not establish that skill; it is not proof
that the student lacks the skill. Learning links are a curated static catalogue.”

**Observe:** Do not guarantee a high score for the fresh resume profile. Incomplete
or limited evidence is a legitimate result and part of the demonstration.

## 8. Company recommendations — 50 seconds

**Do:** Open Company Recommendations and expand a card's reasons/requirements.
Explain ELIGIBLE, INCOMPLETE and NOT_ELIGIBLE where present. Show missing information.

**Say:** “Requirement checking comes before ranking. Mandatory failure overrides
recommendation status. These company requirements are labelled sample data,
not verified current hiring criteria.”

**Observe:** Preserve whatever groups the backend returns. Do not invent an
eligible company or a job role/cutoff that the card does not provide.

## 9. Assessments — approximately 100 seconds

**Do:** Open Mock Tests, choose Python and **5 questions** (the shortest current
UI option), review instructions, start, choose answers and submit once. Use the
visible randomized questions; do not use stored answer keys or fake a perfect result.

**Say:** “The server reserves an attempt slot and sets the deadline. Correct
answers are scored with difficulty-weighted points. Submission updates only this
owned profile's evidence and retains recovery/duplicate protections.”

**Observe:** A five-question assessment has a five-minute server limit, but you
can submit earlier. The score/level must be the actual server result, even if low.
Do not wait for expiry during the main live demo or bypass cooldown afterward.

## 10. Assessment history — 35 seconds

**Do:** Show the completed result/history through Mock Tests or the relevant
performance view. Identify skill, attempt, timestamp and score where displayed.

**Say:** “The record belongs to this account/profile/session. Completed duplicates
do not award evidence again. A same-skill retake is subject to normal 24-hour cooldown.”

**Observe:** The first completed attempt now exists; history may have been empty
before it. Do not claim a standalone history screen if the current UI presents
history within Mock Tests/Performance Analysis.

## 11. Performance analytics — 45 seconds

**Do:** Open Performance Analysis. Show the owned prediction history, assessment
result and readiness. Identify prediction source freshness if shown.

**Say:** “Analytics combines actual stored operations. Assessment evidence can
advance the profile revision, making a previous prediction historical rather
than current. A fresh estimate should use the current reviewed profile.”

**Observe:** Do not alter past scores/revisions to make the trend look better.
Readiness need not improve after a low-scoring assessment.

## 12. Switching student accounts — 60 seconds

**Do:** Log out the onboarding account. Sign in as A, show its two profiles;
log out and sign in as B, show B's independent two profiles and history. Select
B's second profile to demonstrate workspace refresh.

**Say:** “The account changes which profile references the server returns. A
profile ID or matching email alone never grants access to another student's data.”

**Observe:** Record only what you see: distinct owned lists and cleared workspaces.
Do not claim a complete adversarial access test from menu inspection; cross-account
API denial evidence comes from the separately recorded regression suites.

## 13. Logout and conclusion — 20 seconds

**Do:** Log out B and show the login page. Leave the terminal running until the
examiner is finished. Then Ctrl+C in the owned demo terminal stops its servers
and retains the temporary records.

**Say:** “We have shown profile onboarding, estimates, preparation guidance,
practice history and account separation. These are synthetic local workflows;
real activation, recruitment data and deployment validation remain future work.”

## Recovery and fallback plan

The listed step allocations total **685 seconds (11:25)**. Allow extra time for
login, file selection and questions; rehearse once with a stopwatch. If the college
allocates less time, use a seeded A profile for the short version and explain
resume onboarding with an accurately labelled recorded synthetic screenshot.

| Issue | Honest operator action |
| --- | --- |
| Occupied port | Choose other supported loopback port arguments; do not terminate an unrelated service. |
| Password rejected | Follow actual 15–128-character validator; keep password private. No credential override/backdoor. |
| Scanned/corrupt/unsupported resume | Use the launcher-generated readable DOCX; OCR is unavailable. Explain the error. |
| Missing/stale profile inputs | Review, save and reconfirm the current profile; reload a stale revision rather than overwriting it. |
| Network/backend failure | Show the error and retry explicitly after checking the owned terminal. Never substitute a fabricated result. |
| Assessment expired/cooldown/attempt limit | Explain the normal policy. Use another untouched synthetic profile or a fresh isolated demo for a later rehearsal, not a history rewrite. |
| Insufficient presentation time | Show existing A dashboard/model results, one company reason and an assessment result already produced in this isolated rehearsal; label prerecorded evidence accurately. |

Prepared synthetic screenshots can be a fallback if labelled as recorded screenshots,
not a successful live action. This package does not supply fabricated screenshots.
Record actual manual observations, failures and timings after rehearsing.
See [original launcher instructions](../phase-30-demo-workflow.md) and
[limitations](limitations-and-future-scope.md).
