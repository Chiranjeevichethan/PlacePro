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