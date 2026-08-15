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