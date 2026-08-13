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

### Phase 5 (`phase5_model_validation.py`)

Rigorous validation of the Phase 4 tuned model (`models/placepro_tuned_best_model.pkl`) without retraining:

- **Test split**: stratified holdout, `test_size=0.20`, `random_state=42` — identical to Phase 4, so the test set was untouched during tuning
- **Test-set validation**: Accuracy, Precision, Recall, F1, ROC-AUC, confusion matrix, classification report
- **Stratified 5-fold cross-validation**: per-fold Accuracy / Precision / Recall / F1 / ROC-AUC with mean ± std
- **Train vs test comparison**: overfitting check (flagged honestly when gaps are large)
- **Confusion matrix, ROC curve, Precision-Recall curve** plots
- **Threshold analysis**: 0.30–0.70 trade-off between false positives (false hope) and false negatives (missed placements) — production threshold unchanged
- **Calibration**: Brier score + calibration curve (compared against the constant base-rate predictor)
- **Leakage checks**: verifies `salary_package_lpa` / `student_id` exclusion, train-only feature-engineering fit (Phase 4 fix), and split ordering
- **Class imbalance**: objective check with ratio and severity verdict (mild ~1.2:1)

Run Phase 5:

```bash
python phase5_model_validation.py
```

(`--sample N` runs a quick dev-only smoke test on N rows.)

Outputs are written to `results/phase5_*` and `outputs/phase5_*`.

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