# Phase 18 — PlacePro Student Dashboard

Phase 18 adds a professional, responsive **Student Dashboard** — a React
single-page application that brings the complete student workflow
(resume → profile → verification → prediction → readiness → assessment →
companies → recommendations → improvement plan) into one interface.

It is a **pure frontend phase**: no backend business logic was changed,
no endpoints were added or removed, and the ML pipeline files
(`src/pipeline.py`, `phase8_final_pipeline.py`) are untouched. The
frontend only **consumes the existing Phase 8–17 APIs**.

---

## 1. Architecture

```
┌─────────────────────────────── frontend/ (React + Vite + TS) ───────────────────────────────┐
│                                                                                              │
│  pages/        dashboard, resume, profile, prediction, readiness, assessment,                │
│                skills, companies, recommendations, improvement-plan                          │
│     │                                                                                        │
│  hooks/        useApi (loading/error/data/retry), useProfile context                         │
│     │                                                                                        │
│  api/          client.ts (fetch wrapper + VITE_API_URL) + endpoint modules                   │
│     │                                                                                        │
│  types/        centralized response types mirroring the backend pydantic schemas             │
│     └─────────────── HTTP (CORS open in dev) ───────────────────────────┐                    │
│                                                                         ▼                    │
│                       FastAPI backend (unchanged): /api/profile, /api/resume, /api/assessment,│
│                       /api/companies, /api/readiness, /api/predict (Phases 8-17)             │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```

Key principles:

- **Reuse, never duplicate**: every page calls the existing endpoints
  through `src/api/`. No fake endpoints, no duplicated business logic,
  no hard-coded prediction results.
- **Honesty**: model-estimated placement probability is always labeled as
  an estimate; readiness ≠ ML probability is stated on the readiness page;
  missing skills are reported as "not found in verified profile", never
  "student doesn't know X".
- **No auth yet**: a development/demo `profile_id` is used, isolated in
  `frontend/src/config/demo.ts` (`VITE_DEMO_PROFILE_ID`).

## 2. Frontend structure

```
frontend/
  index.html, vite.config.ts, tsconfig.json, package.json
  .env.example                      # VITE_API_URL, VITE_DEMO_PROFILE_ID
  src/
    main.tsx                        # entry: router + Toast + Profile providers
    App.tsx                         # route table
    api/
      client.ts                     # fetch wrapper, ApiError, upload helper
      index.ts                      # profilesApi, resumeApi, readinessApi,
                                    #   companiesApi, recommendationsApi, assessmentApi
    types/index.ts                  # centralized API response types
    config/demo.ts                  # ISOLATED demo config (profile id, skill list, limits)
    context/ProfileContext.tsx      # loads the demo profile once, exposes refresh()
    hooks/useApi.ts                 # { data, loading, error, refetch }
    layouts/DashboardLayout.tsx     # responsive sidebar/topbar shell
    components/
      PageHeader.tsx, ProfileGate.tsx   # verified-profile guard
      ui/                           # Card, Badge, ProgressBar, ProgressRing,
                                    #   StatCard, Tooltip, Modal, Toast, StateBox
    pages/
      DashboardPage.tsx, ResumePage.tsx, ProfilePage.tsx, PredictionPage.tsx,
      ReadinessPage.tsx, AssessmentPage.tsx, SkillsPage.tsx, CompaniesPage.tsx,
      RecommendationsPage.tsx, ImprovementPlanPage.tsx, NotFoundPage.tsx
    utils/format.ts                 # percent/score/date/status-label helpers
    styles/global.css               # design tokens + component styles
```

## 3. API integration (all existing endpoints)

| Page | Endpoint(s) used |
|------|------------------|
| Dashboard | `GET /api/profile/{id}`, `GET /api/profile/{id}/placement-summary`, `GET /api/profile/{id}/skills`, `GET /api/profile/{id}/assessments`, `GET /api/profile/{id}/eligibility`, `GET /api/profile/{id}/recommendations?limit=4` |
| Resume | `POST /api/profile/from-resume` (multipart) |
| Profile | `GET /api/profile/{id}`, `PUT /api/profile/{id}`, `POST /api/profile/verify` |
| Prediction | `POST /api/profile/{id}/predict` |
| Readiness | `GET /api/profile/{id}/readiness`, `GET /api/profile/{id}/placement-summary` |
| Assessment | `POST /api/assessment/start`, `POST /api/assessment/{id}/submit`, `GET /api/profile/{id}/assessments` |
| Skills | `GET /api/profile/{id}/skills` |
| Companies | `GET /api/companies`, `GET /api/profile/{id}/eligibility`, `GET /api/profile/{id}/eligibility/{company_id}` |
| Recommendations | `GET /api/profile/{id}/recommendations` |
| Improvement Plan | `GET /api/profile/{id}/readiness`, `GET /api/profile/{id}/skills`, `GET /api/profile/{id}/recommendations` |

All calls go through `src/api/` — components never call `fetch` directly.

## 4. Page descriptions

- **/dashboard** — overview: profile completion %, verification status,
  ML placement probability (labeled "Model estimate"), readiness score,
  strengths, skill gaps, recommended companies, assessment progress and
  top improvement actions.
- **/resume** — drag-and-drop PDF/DOCX upload with loading state; shows
  extraction summary, per-field confidence, provenance (source + evidence),
  feature availability and an explicit "requires manual verification" list.
  Scanned PDFs surface a friendly **OCR_REQUIRED** error. The extracted
  draft is then reviewed/edited on the Profile page.
- **/profile** — full editable profile (personal, education, skills,
  experience, internships, projects, certifications, achievements, ML
  inputs). Shows verified/unverified state, resume-derived vs user-edited
  provenance, missing fields and completion. Saving resets verification;
  a **confirmation dialog** shows exactly what will become verified before
  submitting `POST /api/profile/verify`, with success/failure states.
- **/prediction** — runs the existing prediction API; shows probability,
  prediction, confidence and model version with a clear "model-estimated,
  not a guarantee" label, plus prediction history. Missing fields are
  shown instead of inventing a result.
- **/readiness** — readiness score ring, level, documented breakdown bars,
  strengths with evidence, skill gaps (prioritized) and profile
  completeness. Explicitly states **readiness ≠ ML probability**.
- **/assessment** — skill selection (12 skills) with per-skill attempt
  count and latest score; one-question-at-a-time flow with progress,
  difficulty and topic indicators; server-side submit → result screen
  (score, level, difficulty + topic breakdown); full history table.
  Attempt-limit (429) and cooldown errors are surfaced. Answer keys are
  never fetched or shown.
- **/skills** — combined skill view clearly distinguishing **assessment
  evidence** (score, level, verified ✓) from **resume/user mentions**
  (no score).
- **/companies** — eligibility for all active companies grouped into
  ELIGIBLE / NOT ELIGIBLE / INCOMPLETE with passed/failed/unknown counts
  and a per-company requirement drill-down (PASS/FAIL/UNKNOWN rows).
  Sample/demo requirements are labeled as such.
- **/recommendations** — ranked recommendation cards with status, score,
  eligibility, skill match (matched/missing), readiness, ML probability
  and improvement actions.
- **/improvement-plan** — prioritized action list aggregated from
  readiness skill gaps, assessment coverage, profile completeness and
  recommendation improvement actions, grouped by category (Complete
  assessment / Improve technical skill / Company requirement / Profile
  completeness).

## 5. Resume → Profile → Prediction data flow

The dashboard's core workflow (upload resume → review profile → verify →
predict) is wired together by three pieces that keep the **active
profile** in sync:

1. **ProfileContext owns the active profile id.** It lives in
   `localStorage` (`placepro_active_profile_id`) so it survives reloads,
   and falls back to `VITE_DEMO_PROFILE_ID` until a resume is imported.
   `switchProfile(id)` stores the id and re-fetches the profile.
2. **Resume import switches the whole dashboard.**
   `POST /api/profile/from-resume` creates a new, **unverified draft
   profile**. `ResumePage` then calls `switchProfile(newProfileId)`, so
   every page (Profile, Prediction, Readiness, Assessment, …) immediately
   reads the imported profile instead of the demo one (which is left
   untouched).
3. **Prediction always runs against the latest profile.**
   `PredictionPage` calls `refresh()` before
   `POST /api/profile/{id}/predict`, so it never predicts with stale
   in-memory data. Refreshing an already-loaded profile is **silent**: it
   does not flip the global loading flag, because `ProfileGate` swaps to a
   full-page loader while loading and would unmount the prediction page
   mid-flight, discarding its in-flight result.

Step by step (what the browser smoke test exercises):

| Step | Action | Result |
|------|--------|--------|
| 1 | Upload a PDF/DOCX resume on **/resume** | Draft profile created (unverified); `localStorage.placepro_active_profile_id` set to the new id; dashboard greeting switches to the extracted name |
| 2 | Review on **/profile** | Extracted fields (name, email, education, skills, projects, …) pre-filled with resume provenance; missing ML fields flagged |
| 3 | Fill ML inputs + **Verify** | `POST /api/profile/verify` marks the profile verified (all 16 Phase 8 features available) |
| 4 | **Run prediction** on /prediction | `refresh()` → `POST /api/profile/{id}/predict` → model-estimated probability shown and recorded in the new profile's `prediction_history` |

**Failure modes surfaced by the UI (nothing is invented):**

- Unverified profile → prediction page is gated ("Profile not verified").
- Missing ML fields → `ready_for_prediction=false` with the exact missing
  fields listed (the model is never called with missing inputs).
- Profile edited after a prediction → the edit resets verification; the
  next Run refreshes first and surfaces the unverified gate instead of
  predicting on stale data.

## 6. State management

- **ProfileContext** loads the demo profile once and exposes
  `{ profile, completion, profileId, loading, error, refresh, switchProfile }`.
  Pages call `refresh()` after save/verify to keep everything in sync;
  `switchProfile()` is used after resume import. Refresh of an
  already-loaded profile is silent (no loading flash) so gated pages are
  not unmounted mid-flight.
- **useApi** hook provides `{ data, loading, error, refetch }` for each
  page-level fetch. There is no global store library — the app is
  fetch-per-page by design (the backend is stateless JSON storage).
- Assessment question flow is local component state (answers, current
  question, phase select/taking/result).

## 7. Error handling

- Centralized `ApiError` (status, detail, FastAPI validation messages) in
  `src/types`; all endpoints throw it through `apiFetch`.
- Every page renders a consistent **error state with a Retry button** and
  **loading skeletons**.
- Empty states everywhere (no profile, no assessments, no companies, ...).
- Toast notifications for success/failure (save, verify, assessment
  submit, upload).
- Confirmation dialogs for destructive/irreversible actions (profile
  verification).
- FastAPI validation errors (422 with field messages) are parsed and shown.
- OCR_REQUIRED resumes get a dedicated, friendly error block.

## 8. Responsive & UX

- Desktop: fixed sidebar navigation + content grid (4/3/2 columns).
- Tablet/mobile (< 860px): collapsible sidebar behind a hamburger top bar
  with backdrop; grids collapse to 1–2 columns; tables scroll
  horizontally.
- Progress rings/bars, status badges with semantic colors, skill chips,
  tooltips, accessible labels and consistent spacing. No excessive
  animation, no fake statistics, no fake logos.

## 9. Setup commands

Backend (from the project root):

```bash
uvicorn backend.app.main:app --reload        # http://127.0.0.1:8000
```

Create the demo profile (development tool — no auth yet):

```bash
python backend/scripts/seed_demo_profile.py              # demo-student
python backend/scripts/seed_demo_profile.py --assess-all # + demo assessment evidence (fabricated, opt-in)
```

Frontend:

```bash
cd frontend
npm install
cp .env.example .env        # optional; defaults point at 127.0.0.1:8000
npm run dev                 # http://localhost:5173
```

Production build / typecheck:

```bash
cd frontend && npm run build      # tsc --noEmit + vite build
cd frontend && npm run typecheck
```

## 10. Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `VITE_API_URL` | `http://127.0.0.1:8000` | Backend base URL (never hard-coded in components) |
| `VITE_DEMO_PROFILE_ID` | `demo-student` | Demo profile used until auth exists |

## 11. Testing performed

- `npm run build` and `npm run typecheck` — clean.
- All Phase 8–17 backend suites re-run with **0 failures**
  (service-level + HTTP-level against a running server):
  `test_assessment`, `test_eligibility`, `test_predict`,
  `test_predict_profile`, `test_profile`, `test_readiness`,
  `test_recommendations`, `test_resume`, `test_resume_intelligence`.
- API integration smoke-tested with curl for every page's endpoints
  (profile, readiness, placement-summary, predict, companies, eligibility,
  recommendations, skills, assessments, assessment start/submit, resume
  upload).
- Browser smoke test (headless Chrome via agent-browser):
  - Dashboard renders live data (completion 100%, ML 83% PLACED,
    readiness 65, strengths, gaps).
  - Skills page shows assessment vs mention evidence correctly.
  - Full assessment flow in the UI: start → answer 10 questions →
    submit → result screen with difficulty/topic breakdowns → history.
  - Companies and Recommendations pages render grouped results.
  - Mobile viewport (390px): topbar/hamburger appears, grids collapse to
    one column, sidebar opens/closes via the hamburger.
- **Phase 18.1 browser smoke test (headless Chromium via Playwright):**
  the full Resume → Profile → Prediction flow — fresh load falls back to
  the demo profile; resume upload creates a draft and switches
  `localStorage` + every page to it (dashboard greeting, Profile fields,
  Prediction gate); ML inputs + verify through the UI; prediction runs on
  the new profile and records `prediction_history` there; re-running
  WITHOUT a reload uses fresh data (probability changed 80.2% → 84.9%
  after a CGPA edit) and surfaces the unverified gate when the profile
  was invalidated server-side. This caught and fixed one regression: an
  eager `refresh()` during `run()` flipped the global loading flag and
  unmounted the gated prediction page mid-flight (fixed by making
  refreshes of an already-loaded profile silent — see section 5/6).

## 12. Known limitations

- **No authentication** (by design, per spec): the dashboard uses a single
  demo `profile_id` from `VITE_DEMO_PROFILE_ID`, isolated in
  `src/config/demo.ts`. Real per-student identity is a later phase.
- **Windows file-lock flakiness**: the backend's atomic JSON write
  (`os.replace`) can occasionally hit `WinError 5` under OneDrive/Defender
  on Windows. It is transient (retry succeeds) and the dashboard surfaces
  it with the standard error state + Retry. The backend storage code was
  intentionally left untouched per the Phase 18 constraints.
- The supported assessment skill list is duplicated as frontend config
  (`src/config/demo.ts`) because the backend exposes no public skill-list
  endpoint; the list is public/documented (Phase 17 docs).
- No timed assessments, no OCR for scanned PDFs, no admin/company
  management UI — all inherited from the backend (later phases).
- Demo company requirements are sample data, clearly labeled as such in
  the UI.

## 13. Files

- **New (frontend):** `frontend/` (Vite + React + TS app) — see section 2.
- **New (backend dev tool):** `backend/scripts/seed_demo_profile.py`.
- **New (docs):** `docs/phase18_student_dashboard.md`, README Phase 18
  section.
- **Modified:** `README.md` only (Phase 18 section). No backend files
  were modified.
