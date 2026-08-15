# PlacePro — Phase 8 Technical Report

**Final ML Pipeline & Backend Foundation**

Date: August 2026
Branch: `phase7-feature-engineering-tuning` (Phase 8 work)

---

## 0. Pipeline lineage (which ML pipeline is the latest)

| Phase | Artifact | Dataset | Status |
|-------|----------|---------|--------|
| 3 | `main.py` | `data/placement.csv` (old, 26 cols) | Superseded |
| 4 | `phase4_model_tuning.py` → `src/predictor.py` | `data/placement.csv` | Superseded |
| 5 | `phase5_model_validation.py` (branch) | `data/placement.csv` | Superseded |
| 6 | `phase6_dataset_baseline.py` | `data/placement_phase6.csv` (new, 18 cols) | Baseline for new dataset |
| **7** | **`phase7_model_tuning.py`** | **`data/placement_phase6.csv`** | **Latest ML pipeline** |
| **8** | **`phase8_final_pipeline.py` + `src/pipeline.py`** | **`data/placement_phase6.csv`** | **This report** |

**The Phase 7 pipeline is the latest and is what Phase 8 productizes.** Phase 7
selected **Logistic Regression (tuned)** as the final model but never saved it
to disk. Phase 8 therefore:

1. Reproduces Phase 7 exactly (same dataset, same feature engineering, same
   split, same tuning grid) — verified to match Phase 7's recorded test metrics
   within ±0.005 on every metric (see §7).
2. Saves the **entire pipeline** (feature engineering + preprocessing + model)
   as one file: `models/placepro_final_model.pkl`.
3. Exposes it through a FastAPI backend: `POST /api/predict`.

---

## 1. Final dataset

| Property | Value |
|----------|-------|
| File | `data/placement_phase6.csv` |
| Rows | 100,000 |
| Columns | 18 (16 features + target + 1 leakage) |
| Duplicates | 0 |
| Missing values | None in features (`salary_package_lpa` is the only column with missing values and is removed — see §4) |
| Class balance | 68.5% Placed / 31.5% Not Placed (2.17:1) |
| Split | 80/20 stratified, `random_state=42` → 80,000 train / 20,000 test |
| Test set | Completely untouched until final evaluation |

## 2. Target column

- **Column:** `placement_status`
- **Encoding:** `1 = Placed`, `0 = Not Placed` (already numeric in this dataset)
- **Use:** binary classification (Placed vs Not Placed)

## 3. Input features

16 raw features (the exact columns the model was trained on):

| # | Column | Type | Domain |
|---|--------|------|--------|
| 1 | `branch` | categorical | CE, CSE, Chemical, ECE, EE, IT, ME |
| 2 | `college_tier` | categorical | Tier-1, Tier-2, Tier-3 |
| 3 | `cgpa` | numeric | 0–10 |
| 4 | `backlogs` | numeric (int) | ≥ 0 |
| 5 | `coding_skills` | numeric | 0–10 |
| 6 | `dsa_score` | numeric | 0–10 |
| 7 | `aptitude_score` | numeric | 0–100 |
| 8 | `communication_skills` | numeric | 0–10 |
| 9 | `ml_knowledge` | numeric | 0–10 |
| 10 | `system_design` | numeric | 0–10 |
| 11 | `internships` | numeric (int) | ≥ 0 |
| 12 | `projects_count` | numeric (int) | ≥ 0 |
| 13 | `certifications` | numeric (int) | ≥ 0 |
| 14 | `hackathons` | numeric (int) | ≥ 0 |
| 15 | `open_source_contributions` | numeric (int) | ≥ 0 |
| 16 | `extracurriculars` | numeric (int) | ≥ 0 |

## 4. Leakage columns

| Column | Reason it is excluded |
|--------|----------------------|
| `salary_package_lpa` | **Post-placement variable** — it only exists for placed students; its 31,525 missing values exactly match the non-placed students. Using it would leak the target. |
| `student_id` | Unique identifier with no predictive meaning (not present in this dataset, dropped defensively). |
| `placement_status` | The target itself — never an input. |

`src/pipeline.py` defensively drops all of these before prediction
(`LEAKAGE_COLUMNS`), and `create_features()` removes them from training data.

## 5. Feature engineering

All transforms are **deterministic, fixed-domain rules** (Phase 7 rules,
verbatim in `src/pipeline.create_features`). No statistic is fitted on the
full dataset, so there is **no leakage** and engineering can run before any
split. 10 engineered features are added:

| Feature | Rule |
|---------|------|
| `overall_skill_score` | mean of 6 normalized skills (aptitude/100, skills/10) |
| `academic_skill_index` | mean of cgpa/10, aptitude/100, dsa/10, coding/10 |
| `experience_score` | mean of `log1p` over 5 experience counts |
| `high_cgpa` | `cgpa >= 7.5` |
| `has_internship` | `internships >= 1` |
| `project_level` | `digitize(projects_count, [1,3,5])` → 0–3 |
| `coding_experience_interaction` | `coding_skills * (internships + 1)` |
| `cgpa_projects_interaction` | `cgpa * (projects_count + 1)` |
| `backlog_risk` | `backlogs >= 1` |
| `strong_candidate_indicator` | cgpa ≥ 7.5 AND coding ≥ 6 AND internships ≥ 1 |

Total model input after engineering: **24 numeric + 2 categorical** features
(raw 16 → 26 after engineering, before encoding).

## 6. Preprocessing

Applied **inside the saved pipeline** (fitted on training folds only):

- **Numeric (24):** median imputation → `StandardScaler`
- **Categorical (2: `branch`, `college_tier`):** most-frequent imputation →
  `OneHotEncoder(handle_unknown="ignore")` (unseen categories are safe)
- Column lists are explicit and captured at fit time → robust to column
  ordering and dtype changes at prediction time

## 7. Selected model

**Logistic Regression (tuned)** — the exact Phase 7 winner, reproduced with
the identical tuning protocol:

- `GridSearchCV`, 3-fold stratified CV, scoring = `roc_auc`
- Grid: `C ∈ {0.01, 0.1, 1, 10}` × `penalty ∈ {l1, l2}` ×
  `class_weight ∈ {balanced, None}` (solver `liblinear`, `max_iter=2000`)
- **Best params:** `C=0.01`, `penalty=l2`, `class_weight=balanced`,
  `solver=liblinear`
- Selection metric (Phase 4/7 convention): **ROC-AUC** primary, F1 tie-breaker
  — not accuracy alone
- Saved as one joblib pipeline:
  `feature_engineering → preprocessing → LogisticRegression`
  at `models/placepro_final_model.pkl` (`model_version: placepro-final-v1`)

## 8. Model performance (untouched test set — honest numbers)

| Metric | Value |
|--------|-------|
| **Accuracy** | **0.6319 (63.19%)** |
| Precision | 0.7956 |
| Recall | 0.6223 |
| F1 | 0.6983 |
| ROC-AUC | 0.6853 |
| 5-fold CV accuracy | 0.6289 ± 0.0039 |
| 5-fold CV ROC-AUC | 0.6858 ± 0.0034 |
| Confusion matrix | TN=5,373 / FP=917 / FN=6,289 / TP=7,421 |

**Honesty statement — 90% accuracy is NOT claimed.** The untouched test set
demonstrates **63.19%** accuracy. Phase 7's analysis
(`results/phase7_validation_summary.txt`, section 8) documents why ~90% is
not achievable on this dataset without leakage or label manipulation:

- The strongest single-feature correlation with the target is only r = 0.149
  (cgpa).
- Classes overlap heavily: placement depends on unobserved factors (interview
  performance, company demand, timing) not present in the dataset.
- An always-predict-majority baseline already scores 68.5% accuracy; the
  model's real value is its ROC-AUC (ranking quality) and calibrated
  probabilities, not raw accuracy.

## 9. Exact expected input schema

`POST /api/predict` request body (`backend/app/schemas.py` → `StudentProfile`):

```json
{
  "branch": "CSE",
  "college_tier": "Tier-1",
  "cgpa": 8.5,
  "backlogs": 0,
  "coding_skills": 8.2,
  "dsa_score": 8.0,
  "aptitude_score": 85.0,
  "communication_skills": 7.5,
  "ml_knowledge": 6.5,
  "system_design": 5.0,
  "internships": 2,
  "projects_count": 4,
  "certifications": 2,
  "hackathons": 1,
  "open_source_contributions": 1,
  "extracurriculars": 1
}
```

All 16 fields are **required** (missing fields → HTTP 422 with per-field
details). Type/range validation: scores 0–10, `cgpa` 0–10, `aptitude_score`
0–100, counts ≥ 0. Extra fields (e.g. `student_id`, `salary_package_lpa`,
`placement_status`) are accepted but **ignored/dropped** before prediction —
they never reach the model.

## 10. Output schema

`POST /api/predict` response (`backend/app/schemas.py` → `PredictionResponse`):

```json
{
  "placement_probability": 0.947732,
  "prediction": "PLACED",
  "confidence": 0.947732,
  "model_version": "placepro-final-v1"
}
```

| Field | Type | Definition |
|-------|------|------------|
| `placement_probability` | float 0–1 | P(Placed) from the model |
| `prediction` | string | `"PLACED"` if `placement_probability >= 0.50`, else `"NOT PLACED"` (Phase 7 production threshold) |
| `confidence` | float 0–1 | Model certainty in its prediction = `max(p, 1-p)` |
| `model_version` | string | Served model tag (for monitoring) |

---

## How to run

```bash
# 1. Train + save the final model (already done; re-run to regenerate)
python phase8_final_pipeline.py

# 2. Start the API (from the project root)
uvicorn backend.app.main:app --reload

# 3. Test
python backend/tests/test_predict.py          # smoke tests (service + HTTP)
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/api/predict \
     -H "Content-Type: application/json" \
     -d '{"branch":"CSE","college_tier":"Tier-1","cgpa":8.5,"backlogs":0,
          "coding_skills":8.2,"dsa_score":8.0,"aptitude_score":85.0,
          "communication_skills":7.5,"ml_knowledge":6.5,"system_design":5.0,
          "internships":2,"projects_count":4,"certifications":2,
          "hackathons":1,"open_source_contributions":1,"extracurriculars":1}'
```

Interactive docs: http://127.0.0.1:8000/docs

## Files created in Phase 8

- `src/pipeline.py` — canonical reusable prediction pipeline
- `phase8_final_pipeline.py` — final model training script
- `backend/app/main.py` — FastAPI app (`/health`, CORS)
- `backend/app/schemas.py` — request/response schemas
- `backend/app/routes/predict.py` — `POST /api/predict`
- `backend/app/services/prediction_service.py` — model service wrapper
- `backend/tests/test_predict.py` — smoke tests
- `docs/phase8_technical_report.md` — this report
- `models/placepro_final_model.pkl` — saved pipeline (gitignored)
- `results/phase8_model_metrics.csv`, `results/phase8_final_results.txt`

## Not in scope (per Phase 8 instructions)

- Resume parsing — **not built**
- Frontend modifications — **none** (API is CORS-open for the future frontend)
