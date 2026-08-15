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