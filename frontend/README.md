# PLACEPRO – AI Placement Prediction System

> Publication refresh (2026-11-24): current capabilities, 50 operations/45 paths,
> required artifacts and verification boundaries are summarized in the
> [reviewed release snapshot](../backend/DEPLOYMENT.md#reviewed-release-snapshot-2026-11-24). Earlier dated results remain historical;
> no new application tests, browser acceptance or Linux/Docker success are claimed.

> An AI-based intelligent student placement prediction and recommendation system designed to help students understand their placement readiness and improve their career opportunities.

## 📌 Project Overview

**PlacePro** is an AI-powered student placement prediction platform that analyzes academic performance, technical skills, internships, certifications, projects, aptitude, and other student attributes to estimate placement probability.

The system provides students with:

- 📊 Placement readiness insights
- 🤖 AI/ML-based placement prediction
- 🎯 Personalized recommendations
- 📈 Performance analysis
- 👨‍🎓 Student profile management
- 🔍 Easy navigation and page search
- 🔐 Student authentication interface

This directory contains the **frontend application** of PlacePro. The repository
also contains its FastAPI backend. Follow the [Windows setup guide](../README.md)
for Python 3.14.6 x64, Node 24.15.0/npm 11.12.1, configuration and isolated tests.

---

## ✨ Features

### 🏠 Dashboard

The dashboard provides a quick overview of the placement system.

- Current profile readiness and completion
- Placement overview when confirmed model inputs are complete
- Historical assessment and placement activity
- Strength areas and evidence-based skill gaps
- Company recommendations with eligibility explanations

### 🎯 Placement Prediction

Students can enter their academic and professional information to generate a placement prediction.

The prediction interface supports:

- CGPA
- Skills
- Internship information
- Certifications
- Projects
- Aptitude performance
- Other placement-related attributes

Placement and salary pages call the real backend model APIs. Results follow the
submitted inputs and active profile revision; they require a running API.

### 👨‍🎓 Student Profile

Students can view and edit their profile information.

Profile information includes:

- Name
- Branch
- CGPA
- Attendance
- Certifications
- Internships
- Projects
- GitHub repositories
- LinkedIn connections
- College tier

Profile updates are persisted through the owned, revision-bound backend API.
Browser references/drafts do not establish ownership or replace saved profile data.
Existing-profile resume preview supports selected imports, corrections, Select All
and explicit confirmation; unselected fields retain saved values. Matching saved
values prefill Experimental V1 while current-session manual edits, including blanks,
are preserved.
New profile uploads create a separate owned draft and preserve the selected history.

### 📈 Performance Analysis

Provides visual analysis of student performance and placement-related metrics.

### 🔐 Authentication

The frontend uses real server sessions with:

- Email login
- Password field
- Session restoration after refresh
- Password visibility toggle
- Logout
- Google login UI

> Registration and recovery await approved email activation. Google OAuth is
> implemented but optional: it requires backend configuration and separate provider/hosting acceptance.
> GitHub and LinkedIn sign-in are not implemented. Secure cookies stay HttpOnly; CSRF is in memory. Only ACTIVE owned
> profiles can be selected. Account/profile switches clear old private views.
> Stateless placement/salary forms calculate without history; the dashboard's
> separate Save profile prediction action writes owned history with a retry key.

### 🔎 Page Search

The navigation bar includes a page search feature.

Supported interactions:

- Search pages
- Keyboard navigation
- Arrow-key selection
- Enter to navigate
- Escape to close
- Responsive mobile search

---

## 🛠️ Tech Stack

### Frontend

- React.js
- JavaScript
- HTML5
- CSS3
- Vite

### UI / Visualization

- Responsive CSS
- SVG icons and illustrations
- CSS gradients
- Interactive UI components

### Storage

- Browser Local Storage
- Session Storage

### Backend Integration

The frontend API layer connects readiness, eligibility/recommendations, resume/profile,
assessment/performance and placement/salary pages to the FastAPI backend.

---

## 📁 Project Structure

```text
frontend/
│
├── public/
│   ├── favicon.svg
│   └── icons.svg
│
├── src/
│   │
│   ├── assets/
│   │
│   ├── components/
│   │   ├── EditProfileModal.jsx
│   │   ├── IconMark.jsx
│   │   ├── Logo.jsx
│   │   ├── Navbar.jsx
│   │   ├── ProfileDropdown.jsx
│   │   ├── RecommendationPanel.jsx
│   │   ├── SearchBar.jsx
│   │   ├── Sidebar.jsx
│   │   ├── StatsCard.jsx
│   │   └── StudentForm.jsx
│   │
│   ├── pages/
│   │   ├── About.jsx
│   │   ├── Dashboard.jsx
│   │   ├── Login.jsx
│   │   ├── PerformanceAnalysis.jsx
│   │   ├── Prediction.jsx
│   │   └── StudentProfile.jsx
│   │
│   ├── services/
│   │   ├── api.js
│   │   └── auth.js
│   │
│   ├── App.jsx
│   ├── App.css
│   ├── index.css
│   └── main.jsx
│
├── index.html
├── package.json
├── package-lock.json
├── vite.config.js
└── README.md
```

## Development commands

In a new frontend directory, use `npm.cmd ci` with the existing lockfile. It removes
an existing `node_modules`, so preserve an existing environment and validate in a
separate copy when needed. Vite reads `frontend/.env.local`; its public optional
variables are listed in [.env.example](.env.example). Do not overwrite existing env files.

```powershell
npm.cmd run dev -- --host 127.0.0.1 --port 5173 --strictPort
npm.cmd run test
npm.cmd run lint
# Preserve earlier output by using a new build directory:
# Build requires the deployed HTTPS API origin; replace this example.
$env:NODE_ENV = 'production'
$env:VITE_API_BASE_URL = 'https://api.example.com'
$placeproBuild = Join-Path $PWD ('..\scratch\frontend-build-' + [guid]::NewGuid().ToString('N'))
npm.cmd run build -- --outDir $placeproBuild
```

The development API defaults to `http://127.0.0.1:8765`; start it in a separate terminal.
New checkouts contain no student records. See [root setup](../README.md) for explicit
resume/profile creation, startup helpers, troubleshooting and validation limitations.

## Vercel frontend deployment

Use `frontend` as the Vercel Root Directory, the Vite preset, the reviewed Node baseline (24.15.0 in CI),
`npm run build` as the Build Command, and `dist` as the Output Directory.
The included [vercel.json](vercel.json) serves `index.html` for frontend routes,
including direct visits and refreshes of `/experimental-v1-prediction`.
Backend `/api` and `/health` paths are excluded from the SPA fallback.

Set the public `VITE_API_BASE_URL` in Vercel's Production environment, and in
Preview if previews are enabled, before building. Use the actual HTTPS backend
origin, for example `https://api.example.com`, without `/api`, a base path, query,
fragment or credentials. Changing this value requires a new build. Production
builds fail if it is absent, HTTP or loopback; their emitted application code has
no localhost API fallback. Keep the existing local `.env.local` for development.

The backend is hosted separately. This configuration does not create API
functions or invent a backend proxy destination. Do not point the API variable
at the frontend origin unless a separate, reviewed API proxy is configured.
Prefer HTTPS frontend/API domains under the same site so the existing
`SameSite=Lax` cookies work. The backend must explicitly allow the frontend
origin and credentialed CORS; preview environments need their own approved
origin/storage arrangement. These frontend changes do not alter cookies,
authentication, CSRF, API paths or prediction contracts.

API requests retain `credentials: 'include'` and `cache: 'no-store'`. The Vercel
configuration also forbids caching `/api` responses at browser/CDN layers.
Responses from a directly addressed external API still require the backend's
`Cache-Control: private, no-store` policy; frontend hosting headers cannot
replace headers on another origin. Auth, owned-profile and production analytics
routes already set this header. Experimental V1 prediction responses currently
lack an explicit cache header, so verify the external host/CDN never caches
private responses, including POST predictions, before public use. Backend
changes are outside this frontend deployment preparation. Never put secrets in
`VITE_*` variables.

After a deployment is authorized, verify deep-link refreshes, login/session
restoration/logout, profile ownership, production placement/salary and separate V1 predictions, resume updates and
PDF downloads against the deployed backend. No backend is deployed by this
frontend configuration.

# Phase32 resume review and existing-profile update

Student Profile → Update from Resume now extracts PDF/DOCX through an ACTIVE-owned,
revision-bound preview. Upload does not save changes. The student chooses fields
to import, edits them, acknowledges review and confirms through the existing
profile API. Unselected values and manual ML inputs remain intact; account/profile
switching and source-revision guards continue to invalidate stale results.
Standalone resume routes remain blocked. No new dependencies were introduced.
The Node suite includes resumeUpdate.test.js and updated profileReview.test.js;
use the existing npm test, npm run lint and npm run build commands.
See [resume workflow](../docs/resume-upload-workflow.md) for contracts, limits,
security/error cases and the one-step-at-a-time manual Chrome checklist.
