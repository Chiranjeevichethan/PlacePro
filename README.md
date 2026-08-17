# PlacePro

## AI-Based Student Placement Prediction and Recommendation System

PlacePro is a machine learning based system designed to predict student placement status and provide placement-related recommendations.

## Current Progress

### Phase 3 (main.py)

- Dataset integration
- Data preprocessing
- Missing value handling
- Categorical encoding
- Feature engineering
- Exploratory Data Analysis
- Decision Tree
- Random Forest
- XGBoost
- Model evaluation
- Feature importance analysis

### Phase 4 (`phase4_model_tuning.py`)

- Fixes the model-selection logic (ROC-AUC primary, F1 tie-breaker — not accuracy alone)
- Leak-free feature engineering (`src/feature_engineering.py`) fitted on training data only
- Hyperparameter tuning with `GridSearchCV` / `RandomizedSearchCV` + `StratifiedKFold`
  - Logistic Regression, Random Forest, XGBoost
- Class imbalance analysis (mild ~1.2:1 — weighting tested, not assumed)
- Tuned models evaluated on a completely untouched test set
- Final model saved to `models/placepro_tuned_best_model.pkl` (gitignored)
- Reusable prediction function: `from src.predictor import predict_placement`

Run Phase 4:

```bash
python phase4_model_tuning.py
```

(`--sample N` runs a quick dev-only smoke test on N rows.)

### Phase 6 (`phase6_dataset_baseline.py`)

- New, cleaner 100k-row dataset: `data/placement_phase6.csv` (18 columns)
- Leak-free baseline models + stratified 5-fold CV

### Phase 7 (`phase7_model_tuning.py`)

- Deterministic (leak-free) feature engineering on the Phase 6 dataset
- Tuned Logistic Regression selected as best model (ROC-AUC 0.6853,
  accuracy 0.6319 — reported honestly, no 90% claim)

### Phase 8 — Final ML pipeline + backend foundation

- **Final pipeline** (`src/pipeline.py`): one reusable prediction function
  `predict_placement()` returning `placement_probability`, `prediction`
  (PLACED / NOT PLACED), `confidence`
- **Training** (`phase8_final_pipeline.py`): reproduces the Phase 7 pipeline
  exactly and saves it as ONE joblib file `models/placepro_final_model.pkl`
- **Prediction API** (`backend/`, FastAPI):
  - `POST /api/predict` — prediction for a raw student profile
  - `GET /health` — liveness + model version
  - Interactive docs at `/docs`
- Full details: `docs/phase8_technical_report.md`

Run Phase 8:

```bash
python phase8_final_pipeline.py                     # train + save model
uvicorn backend.app.main:app --reload               # start the API
python backend/tests/test_predict.py                # smoke tests
```

### Phase 9 — Resume upload & intelligent extraction

- **`POST /api/resume/upload`** (multipart, field `file`) accepts **PDF**
  (pypdf) and **DOCX** (python-docx) resumes and returns a structured
  student profile (personal, education, skills, experience, internships,
  projects, certifications, achievements) plus heuristic extraction
  confidence and a `needs_verification` list
- **Never invents data**: missing fields are `null`/`[]`; skills are
  returned as found, never converted into scores
- **Secure handling**: 5 MB limit, magic-byte + MIME validation, temp
  storage with cleanup, no execution, no persistence, no auth yet
- Resume extraction is **not yet wired to ML prediction** (Phase 10)
- Full details: `docs/phase9_resume_extraction.md`

Run Phase 9:

```bash
uvicorn backend.app.main:app --reload               # start the API
python backend/tests/test_resume.py                 # 82 checks (needs server for HTTP)
curl -X POST http://127.0.0.1:8000/api/resume/upload -F "file=@resume.pdf;type=application/pdf"
```

### Phase 10 — Resume → verified student profile

- **Canonical profile** (`backend/app/schemas_profile.py`) with clear
  provenance separation: `provenance.resume` (extracted), `provenance.user`
  (student-edited), `provenance.ml` (reserved for Phase 11)
- New endpoints:
  - `POST /api/profile/from-resume` — resume → draft profile (not verified)
  - `PUT /api/profile/{id}` — student edits (reset `verified` to false)
  - `POST /api/profile/verify` — explicit confirmation (`verified: true`)
  - `GET /api/profile/{id}` — fetch a stored profile
- **ML feature mapping** (`backend/app/services/ml_feature_mapping.py`):
  maps the verified profile to the exact 16 Phase 8 model inputs using only
  defensible relationships (cgpa, branch synonyms, list counts); the other
  10 features are user-provided via `ml_inputs` — **nothing is invented**
  (skills are never converted into scores)
- **Completion check**: `profile_complete` + `missing_fields` tells the
  frontend what the student still needs to enter
- No prediction yet — Phase 11 wires the verified profile to the model
- Full details: `docs/phase10_verified_student_profile.md`

Run Phase 10:

```bash
uvicorn backend.app.main:app --reload
python backend/tests/test_profile.py                # 69 checks (needs server for HTTP)
```

### Phase 11 — Verified profile → placement prediction

- **`POST /api/profile/{id}/predict`** — connects a **verified, complete**
  profile to the existing Phase 8 model (`models/placepro_final_model.pkl`
  via `src/pipeline.py`; no second model, no retraining, no duplicated
  feature engineering)
- Guards: profile must exist (404), must be **verified** (`verified: true`),
  and all 16 ML features must be present — otherwise the model is never
  called and `missing_fields` / `reason` are returned (nothing invented)
- Returns `ready_for_prediction`, `prediction`, `placement_probability`,
  `confidence`, `model_version` and records a **prediction history** on the
  profile (timestamp, model_version, probability, prediction; server-controlled)
- **Accuracy is ~63% / ROC-AUC 0.685 — 90% is NOT claimed** (actual Phase 8
  metrics, unchanged)
- Full details: `docs/phase11_prediction_integration.md`

Run Phase 11:

```bash
uvicorn backend.app.main:app --reload
python backend/tests/test_predict_profile.py        # 38 checks (needs server for HTTP)
```

### Phase 12 — Skill gap + placement readiness engine

- **`GET /api/profile/{id}/readiness`** — transparent rule-based analysis of a
  **verified** profile: 0-100 readiness score with a documented breakdown,
  evidence-based strengths, skill gaps vs. a configurable placement skill
  requirement set, and a prioritized improvement plan (unverified -> 422)
- **`GET /api/profile/{id}/placement-summary`** — Phase 11 ML prediction **and**
  Phase 12 readiness reported side by side (never merged)
- All skill logic lives in one configurable module
  (`backend/app/services/skill_taxonomy.py`): 8-category taxonomy, exact-match
  normalization (`js`→JavaScript, `ml`→Machine Learning, `dsa`→[Data
  Structures, Algorithms], ...), and the requirement set with documented
  HIGH/MEDIUM/LOW priorities
- Honesty rules: missing skills are reported as *"not found in verified
  profile"* (never "student does not know X"); skill presence is never
  converted into a numeric skill score; the readiness score is NOT ML
  accuracy and is never presented as such
- ML placement probability still comes ONLY from the Phase 8 model
  (accuracy ~63% / ROC-AUC 0.685 — unchanged, 90% not claimed)
- Full details: `docs/phase12_skill_gap_readiness.md`

Run Phase 12:

```bash
uvicorn backend.app.main:app --reload
python backend/tests/test_readiness.py              # 82 checks (needs server for HTTP)
```

### Phase 13 — Company eligibility engine

- **`GET /api/companies`** and **`GET /api/companies/{id}`** — list / inspect
  the configured demo companies (7 active, clearly labeled **SAMPLE / DEMO**
  requirements; the inactive example `ArchiveTech` demonstrates the `active`
  flag and is excluded)
- **`GET /api/profile/{id}/eligibility/{company_id}`** — transparent
  PASS/FAIL/UNKNOWN analysis of a **verified** profile against one company:
  requirements satisfied / not satisfied, missing information, reasons and
  optional improvement actions
- **`GET /api/profile/{id}/eligibility`** — eligibility against all active
  companies, grouped into `eligible` / `not_eligible` / `incomplete` with
  pass/fail/unknown counts and major reasons
- Honesty rules: missing data is **UNKNOWN, never failure** (missing CGPA →
  `INCOMPLETE`, not "not eligible"); a missing required skill is "not found
  in the verified profile" + "add verified evidence" action — never "the
  student doesn't know it"; **preferred skills never block eligibility**
- **Eligibility is NOT the ML probability** — it is driven only by company
  requirements; placement prediction and eligibility are separate systems
- Reuses the Phase 12 skill taxonomy/normalization and the Phase 10
  ML-feature mapping (no duplicate implementations)
- Company requirements are server-side config only (`backend/app/data/
  companies.py`) — clients cannot modify them
- Full details: `docs/phase13_company_eligibility.md`

Run Phase 13:

```bash
uvicorn backend.app.main:app --reload
python backend/tests/test_eligibility.py            # 74 checks (needs server for HTTP)
```

### Phase 14 — Company recommendation engine

- **`GET /api/profile/{id}/recommendations[?limit=N]`** — ranks every active
  demo company for a **verified** profile using five transparent signals:
  eligibility (30), skill match (25), readiness (20), model-estimated
  placement probability (15), profile completeness (10) — a documented
  0-100 weighted formula, **not** an ML probability
- Results grouped into `recommended` / `eligible` / `incomplete` /
  `not_recommended`, each sorted by score descending
- **Eligibility override**: mandatory failures force `NOT_RECOMMENDED` and
  missing information forces `INCOMPLETE` — an ineligible company can never
  become recommended just because its number looks high
- Every item explains itself: reasons (e.g. *"Not recommended because Your
  CGPA is 6.8, while the minimum requirement is 7.5"*), skill match
  breakdown, and improvement actions (*"Strengthen Data Structures
  knowledge"*)
- Honesty: probability is always labeled *"Model-estimated placement
  probability"* — never "you will get this company"; missing ML features
  are never invented (probability simply absent)
- Reuses Phase 13 eligibility, Phase 12 readiness + taxonomy, and the
  Phase 8 model via the Phase 10 mapping (read-only view — no prediction
  history written); `?limit=` validated 1-50
- Full details: `docs/phase14_company_recommendation.md`

Run Phase 14:

```bash
uvicorn backend.app.main:app --reload
python backend/tests/test_recommendations.py        # 105 checks (needs server for HTTP)
```

### Phase 15 — ML model improvement & robust evaluation

- `phase15_ml_improvement.py` — full data-quality audit, exact Phase 8
  baseline reproduction, stronger models (tuned XGBoost, Extra Trees,
  HistGradientBoosting), feature-engineering experiments, feature
  selection, class-imbalance handling, threshold analysis,
  calibration, 5-fold CV confidence, overfitting check, explainability
  (all Windows-safe, `n_jobs=1`, untouched 80/20 stratified test set,
  `random_state=42`)
- **Honest result: NO material improvement found.** Tuned Logistic
  Regression keeps the best ROC-AUC (**0.6853**) and reproduces Phase 8
  exactly; HGB wins accuracy/F1 (0.6977 / 0.8100) but with a **lower**
  ROC-AUC (0.6829) — the same tradeoff Phase 6 observed
- **90% accuracy: NOT achievable** on this dataset (best honest accuracy
  ≈ 69.8%, majority baseline 68.5%, strongest correlation |r| ≤ 0.17,
  heavy class overlap) — no leakage, no label manipulation
- F1-optimal threshold **0.25** lifts F1 0.698 → 0.815 and accuracy
  0.632 → 0.696 (decision-only improvement; ROC-AUC unchanged);
  calibration (Brier 0.224 → 0.196) documented
- Saved `models/placepro_phase15_best_model.pkl` + metadata as an
  **evaluation artifact** — the production model
  (`models/placepro_final_model.pkl`) was **NOT replaced** (explicit
  decision, never silent)
- Full details: `docs/phase15_ml_model_improvement.md`

Run Phase 15:

```bash
python phase15_ml_improvement.py                 # full run (~40-60 min)
python backend/tests/test_phase15_model.py       # 23 checks (needs server for HTTP)
```

### Phase 16 — Resume Intelligence 2.0

- **Additive intelligence layer** on top of the Phase 9 extraction:
  field **provenance** (`{value, source, evidence}`), heuristic
  **confidence labels** (`high`/`medium`/`low` — extraction
  confidence, never ML confidence), **resume diagnostics** (pages,
  words, detected sections, completeness %, OCR flag) and an
  **extraction summary** (counts + presence flags)
- **`POST /api/resume/analyze`** (NEW) — full analysis WITHOUT
  creating a profile (preview before profile creation); scanned PDFs
  return an explicit **`OCR_REQUIRED`** 422 instead of an empty profile
- **`POST /api/profile/from-resume`** (ENHANCED, backward compatible) —
  Phase 10 contract preserved; adds `provenance`, `confidence`,
  `diagnostics`, `extraction_summary`, `feature_availability`
- **Feature availability** statuses (AVAILABLE_FROM_RESUME /
  AVAILABLE_FROM_USER / CALCULATED / REQUIRES_MANUAL_INPUT / UNKNOWN)
  reuse Phase 10 `ml_feature_mapping` — skills are NEVER converted
  into numeric scores
- **Edit provenance**: editing an extracted field marks it `user` and
  preserves the original resume value in `original_resume_values`
  (e.g. CGPA 8.1 → edited 8.2 keeps `8.1` server-side)
- **OCR is not implemented** — scanned PDFs are detected and surfaced
  explicitly as `OCR_REQUIRED`, never silently ignored
- Full details: `docs/phase16_resume_intelligence.md`

Run Phase 16:

```bash
python backend/tests/test_resume_intelligence.py  # 106 checks (needs server for HTTP)
```

### Phase 17 — Skill assessment engine

- **Real, evidence-based skill assessment** — a resume mention is NOT a
  skill score; a numerical score comes ONLY from an actual assessment,
  evaluated **server-side** (answer keys never leave the server)
- **144 questions / 12 skills** (Python, Java, C, C++, JavaScript, SQL,
  Data Structures, Algorithms, React, Machine Learning, HTML/CSS, Git),
  EASY/MEDIUM/HARD weighted by difficulty points (1/2/3), with
  per-topic and per-difficulty breakdowns
- **`POST /api/assessment/start`** (questions, never answers) →
  **`POST /api/assessment/{id}/submit`** (server-side scoring →
  verified evidence `{skill, score, level, source: "assessment",
  verified: true}`) — plus `GET /api/assessment/{id}`,
  `GET /api/profile/{id}/assessments`, `GET /api/profile/{id}/skills`
- **Provenance preserved**: resume (`source=resume`, verified=false) and
  assessment (`source=assessment`, verified=true) evidence coexist on
  the profile; resume evidence is never overwritten
- **Attempt limits** (3/skill) + **24 h cooldown**, configurable;
  repeated attempts cannot inflate readiness (only the latest score
  counts, bonus capped at 5 pts)
- **Readiness (Phase 12):** documented capped assessment bonus;
  **Recommendations (Phase 14):** an assessed skill is the primary
  evidence — scoring below 60 means it does NOT satisfy a company's
  required skill even if the resume lists it
- **Honest limitation**: scores reflect performance on the PlacePro
  question bank, not a validated psychometric test — never presented
  as guaranteed real-world expertise
- Full details: `docs/phase17_skill_assessment.md`

Run Phase 17:

```bash
python backend/tests/test_assessment.py  # 85 checks (needs server for HTTP)
```

### Phase 18 — Student dashboard (React frontend)

- **Professional, responsive Student Dashboard** bringing the complete
  student workflow into ONE interface: resume upload → profile review →
  verification → prediction → readiness → skill assessment → companies →
  recommendations → improvement plan
- **Pure frontend phase**: consumes ONLY the existing Phase 8–17 APIs;
  no backend business logic changed, no endpoints added/removed, ML
  pipeline files untouched
- **React + Vite + TypeScript** under `frontend/`, with a dedicated API
  service layer (`src/api/`), centralized response types (`src/types/`),
  `VITE_API_URL` for the backend URL (never hard-coded), loading/
  error/empty states, retry buttons, toasts, confirmation dialogs and a
  mobile-first responsive layout (sidebar collapses to a hamburger
  top bar)
- **Honest presentation**: ML placement probability is always labeled
  "model-estimated" and never merged with the rule-based readiness
  score; missing skills are reported as "not found in verified profile";
  demo company requirements are labeled sample data
- **Demo mode (no auth yet)**: a development `profile_id` is isolated in
  `frontend/src/config/demo.ts` (`VITE_DEMO_PROFILE_ID`); seed a verified,
  ML-complete demo profile with `python backend/scripts/seed_demo_profile.py`
  (optional `--assess-all` also seeds demo assessment evidence)
- Full details: `docs/phase18_student_dashboard.md`

Run Phase 18:

```bash
uvicorn backend.app.main:app --reload       # backend on :8000
python backend/scripts/seed_demo_profile.py # demo profile (dev tool)
cd frontend && npm install && npm run dev    # dashboard on :5173
```

## Dataset

The project uses a student placement dataset containing academic, technical, behavioral and extracurricular attributes.

## Technologies

- Python
- Pandas
- NumPy
- Scikit-learn
- Matplotlib
- Seaborn
- XGBoost

## Team

PlacePro Major Project Team