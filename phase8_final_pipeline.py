# ================================================================
# PLACEPRO - PHASE 8
# FINAL ML PIPELINE + BACKEND FOUNDATION (training half)
# ================================================================
#
# Builds the ONE production model that the Phase 8 backend serves.
#
# Faithfully replicates the Phase 7 final pipeline:
#   - Dataset        : data/placement_phase6.csv (100,000 rows, 18 cols)
#   - Target         : placement_status (1 = Placed, 0 = Not Placed)
#   - Feature eng.   : create_features() from src/pipeline.py
#                      (deterministic Phase 7 rules - no fitted stats,
#                       so no leakage)
#   - Split          : 80/20 stratified, random_state=42
#                      (SAME split as Phase 7 - test set untouched)
#   - Model          : Logistic Regression tuned with the SAME
#                      GridSearchCV grid as Phase 7 (C, penalty,
#                      class_weight; 3-fold CV, roc_auc scoring)
#   - Preprocessing  : median impute -> StandardScaler (numeric),
#                      most-frequent impute -> OneHotEncoder(ignore)
#                      (categorical), fitted on training folds only
#
# The ENTIRE pipeline (feature engineering + preprocessing + model)
# is saved as ONE joblib file: models/placepro_final_model.pkl
#
# Performance is reported honestly from the UNTOUCHED test set.
# Phase 7's best model scored ~0.632 accuracy / 0.685 ROC-AUC.
# 90% accuracy is NOT claimed - the data cannot support it (see
# results/phase7_validation_summary.txt, section 8).
#
# Usage:
#   python phase8_final_pipeline.py                # full run
#   python phase8_final_pipeline.py --sample 20000 # dev smoke test
#
# ================================================================

import argparse
import os
import sys
import warnings

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

warnings.filterwarnings("ignore")

import joblib
import numpy as np
import pandas as pd

from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GridSearchCV, StratifiedKFold, train_test_split, cross_val_score

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.pipeline import (
    build_final_pipeline,
    create_features,
    predict_placement,
    RAW_FEATURE_COLUMNS,
    TARGET_COLUMN,
)

# ================================================================
# CONFIGURATION
# ================================================================

DATA_PATH = "data/placement_phase6.csv"
MODEL_PATH = "models/placepro_final_model.pkl"
RESULTS_DIR = "results"

os.makedirs(RESULTS_DIR, exist_ok=True)

RANDOM_STATE = 42
TEST_SIZE = 0.20

SEARCH_CV_FOLDS = 3
FINAL_CV_FOLDS = 5
SEARCH_N_JOBS = 1  # no joblib process spawning on Windows

# The exact Phase 7 Logistic Regression tuning grid
LR_PARAM_GRID = {
    "model__C": [0.01, 0.1, 1.0, 10.0],
    "model__penalty": ["l1", "l2"],
    "model__solver": ["liblinear"],
    "model__class_weight": ["balanced", None],
}

parser = argparse.ArgumentParser(description="PlacePro Phase 8 - final model training.")
parser.add_argument("--sample", type=int, default=None,
                    help="DEV ONLY: run on a random sample of N rows.")
args = parser.parse_args()

SAMPLE_N = args.sample
if SAMPLE_N is not None:
    print(f"[DEV MODE] Using only {SAMPLE_N} rows for a smoke test.\n")


def separator():
    print("=" * 72)


# ================================================================
# 1. LOAD DATASET
# ================================================================

separator()
print("PHASE 8 - FINAL PIPELINE TRAINING")
separator()

if not os.path.exists(DATA_PATH):
    raise FileNotFoundError(f"Dataset not found: {DATA_PATH}")

df = pd.read_csv(DATA_PATH)

if SAMPLE_N is not None:
    _, df = train_test_split(
        df, test_size=SAMPLE_N, stratify=df[TARGET_COLUMN],
        random_state=RANDOM_STATE,
    )

print(f"\nLoaded dataset: {DATA_PATH}")
print(f"Shape: {df.shape}")

# ================================================================
# 2. LEAKAGE SAFETY + FEATURE ENGINEERING
# ================================================================

# create_features() drops salary_package_lpa / student_id if present
# (post-placement leakage / identifiers) and applies the Phase 7
# engineered features (all deterministic fixed-domain transforms).
df = create_features(df)

print("\nFeature engineering applied (Phase 7 rules, deterministic, leak-free).")
print(f"Shape after engineering: {df.shape}")

engineered = [
    c for c in df.columns
    if c not in RAW_FEATURE_COLUMNS + [TARGET_COLUMN]
]
print(f"Engineered features: {engineered}")

# ================================================================
# 3. TRAIN / TEST SPLIT (identical to Phase 7)
# ================================================================

X = df.drop(columns=[TARGET_COLUMN])
y = df[TARGET_COLUMN].astype(int)

X_train, X_test, y_train, y_test = train_test_split(
    X, y,
    test_size=TEST_SIZE,
    stratify=y,
    random_state=RANDOM_STATE,
)

print(f"\nTraining rows : {len(X_train):,}")
print(f"Testing rows  : {len(X_test):,}")
print("Test set is UNTOUCHED until final evaluation.")

# ================================================================
# 4. FEATURE TYPES (explicit lists, captured from training data)
# ================================================================

categorical_features = X_train.select_dtypes(
    include=["object", "category", "string", "str"]
).columns.tolist()

numerical_features = X_train.select_dtypes(
    include=[np.number]
).columns.tolist()

print(f"\nCategorical features: {categorical_features}")
print(f"Numerical features ({len(numerical_features)}): "
      f"{numerical_features}")

# ================================================================
# 5. LOGISTIC REGRESSION TUNING (Phase 7 grid, identical protocol)
# ================================================================

separator()
print("TUNING: Logistic Regression (Phase 7 grid, 3-fold CV)")
separator()

cv_search = StratifiedKFold(
    n_splits=SEARCH_CV_FOLDS, shuffle=True, random_state=RANDOM_STATE
)

lr_pipeline = build_final_pipeline(
    LogisticRegression(max_iter=2000, random_state=RANDOM_STATE),
    numerical_features,
    categorical_features,
)

lr_search = GridSearchCV(
    estimator=lr_pipeline,
    param_grid=LR_PARAM_GRID,
    scoring="roc_auc",
    cv=cv_search,
    n_jobs=SEARCH_N_JOBS,
    verbose=1,
    refit=True,
)

lr_search.fit(X_train, y_train)

print(f"\nBest CV ROC-AUC: {lr_search.best_score_:.4f}")
print(f"Best params: {lr_search.best_params_}")

final_pipeline = lr_search.best_estimator_

# ================================================================
# 6. EVALUATION ON THE UNTOUCHED TEST SET (honest numbers)
# ================================================================

separator()
print("EVALUATION ON UNTOUCHED TEST SET")
separator()

y_pred = final_pipeline.predict(X_test)
y_prob = final_pipeline.predict_proba(X_test)[:, 1]

metrics = {
    "Accuracy": accuracy_score(y_test, y_pred),
    "Precision": precision_score(y_test, y_pred, zero_division=0),
    "Recall": recall_score(y_test, y_pred, zero_division=0),
    "F1": f1_score(y_test, y_pred, zero_division=0),
    "ROC-AUC": roc_auc_score(y_test, y_prob),
}

print(f"  Accuracy : {metrics['Accuracy']:.4f}")
print(f"  Precision: {metrics['Precision']:.4f}")
print(f"  Recall   : {metrics['Recall']:.4f}")
print(f"  F1       : {metrics['F1']:.4f}")
print(f"  ROC-AUC  : {metrics['ROC-AUC']:.4f}")

# ---- 5-fold CV on training data (parity with Phase 7) ----------
print("\n  Running 5-fold CV on training data...")
cv = StratifiedKFold(n_splits=FINAL_CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)
cv_acc = cross_val_score(final_pipeline, X_train, y_train, cv=cv,
                         scoring="accuracy", n_jobs=SEARCH_N_JOBS)
cv_auc = cross_val_score(final_pipeline, X_train, y_train, cv=cv,
                         scoring="roc_auc", n_jobs=SEARCH_N_JOBS)
cv_acc_mean, cv_acc_std = float(cv_acc.mean()), float(cv_acc.std())
cv_auc_mean, cv_auc_std = float(cv_auc.mean()), float(cv_auc.std())
print(f"  CV Accuracy: {cv_acc_mean:.4f} +/- {cv_acc_std:.4f}")
print(f"  CV ROC-AUC : {cv_auc_mean:.4f} +/- {cv_auc_std:.4f}")

# ---- Classification report + confusion matrix ------------------
report = classification_report(
    y_test, y_pred,
    target_names=["Not Placed", "Placed"],
    zero_division=0,
)
print("\nClassification report:")
print(report)

cm = confusion_matrix(y_test, y_pred)
print(f"Confusion matrix:\n{cm}")

# ================================================================
# 7. HONEST CROSS-CHECK vs PHASE 7 (identical protocol expected)
# ================================================================

separator()
print("HONEST CROSS-CHECK vs PHASE 7")
separator()

phase7_row = {
    "Accuracy": 0.63185,
    "Precision": 0.79556,
    "Recall": 0.62227,
    "F1": 0.69832,
    "ROC-AUC": 0.68533,
}
print("Phase 7 'Logistic Regression Tuned' (recorded in "
      "results/phase7_model_comparison.csv):")
print(f"  Accuracy : {phase7_row['Accuracy']:.4f}")
print(f"  Precision: {phase7_row['Precision']:.4f}")
print(f"  Recall   : {phase7_row['Recall']:.4f}")
print(f"  F1       : {phase7_row['F1']:.4f}")
print(f"  ROC-AUC  : {phase7_row['ROC-AUC']:.4f}")

tolerance = 0.005
deviations = {
    k: abs(metrics[k] - phase7_row[k]) for k in phase7_row
}
if all(d <= tolerance for d in deviations.values()):
    print("\n✅ Phase 8 reproduction matches Phase 7 within "
          f"±{tolerance} on every metric - same protocol, same split.")
else:
    print("\n⚠️  Phase 8 metrics deviate from the recorded Phase 7 "
          "numbers. Investigate before serving this model.")
    print(f"   Deviations: { {k: round(v, 5) for k, v in deviations.items()} }")

print("\nNOTE ON 90% ACCURACY: the untouched test set demonstrates "
      f"{metrics['Accuracy']:.4f} accuracy ({metrics['Accuracy']*100:.2f}%).")
print("90% accuracy is NOT claimed - it is not achievable on this "
      "dataset without leakage or label manipulation (Phase 7, section 8).")

# ================================================================
# 8. SAVE THE FINAL PIPELINE (ONE joblib file)
# ================================================================

separator()
print("SAVING FINAL PIPELINE")
separator()

os.makedirs("models", exist_ok=True)
joblib.dump(final_pipeline, MODEL_PATH)
print(f"✅ Saved: {MODEL_PATH}")

# ================================================================
# 9. RESULTS FILES
# ================================================================

metrics_row = {
    "Model": "Logistic Regression Tuned",
    **metrics,
    "CV Accuracy": cv_acc_mean,
    "CV Accuracy Std": cv_acc_std,
    "CV ROC-AUC": cv_auc_mean,
    "CV ROC-AUC Std": cv_auc_std,
}
pd.DataFrame([metrics_row]).to_csv(
    os.path.join(RESULTS_DIR, "phase8_model_metrics.csv"), index=False
)
print(f"✅ Saved: results/phase8_model_metrics.csv")

with open(os.path.join(RESULTS_DIR, "phase8_final_results.txt"), "w",
          encoding="utf-8") as f:
    f.write("PLACEPRO PHASE 8 - FINAL PIPELINE RESULTS\n")
    f.write("==========================================\n\n")
    f.write(f"Dataset          : {DATA_PATH} ({len(df):,} rows)\n")
    f.write(f"Target           : {TARGET_COLUMN} (1 = Placed, 0 = Not Placed)\n")
    f.write(f"Raw features     : {len(RAW_FEATURE_COLUMNS)}\n")
    f.write(f"Engineered feats : {len(engineered)}\n")
    f.write(f"Split            : 80/20 stratified, random_state=42 "
            f"(train {len(X_train):,} / test {len(X_test):,})\n")
    f.write(f"Best params      : {lr_search.best_params_}\n\n")
    f.write("TEST-SET METRICS (untouched test set)\n")
    f.write("-------------------------------------\n")
    for k, v in metrics.items():
        f.write(f"  {k:<10}: {v:.4f}\n")
    f.write("\n5-FOLD CV (training data)\n")
    f.write("-------------------------\n")
    f.write(f"  Accuracy : {cv_acc_mean:.4f} +/- {cv_acc_std:.4f}\n")
    f.write(f"  ROC-AUC  : {cv_auc_mean:.4f} +/- {cv_auc_std:.4f}\n\n")
    f.write("CLASSIFICATION REPORT\n")
    f.write("---------------------\n")
    f.write(report)
    f.write("\nCONFUSION MATRIX\n")
    f.write("----------------\n")
    f.write(str(cm) + "\n\n")
    f.write("HONESTY STATEMENT\n")
    f.write("-----------------\n")
    f.write(f"Untouched test-set accuracy is {metrics['Accuracy']:.4f} "
            f"({metrics['Accuracy']*100:.2f}%).\n")
    f.write("90% accuracy is NOT claimed - the dataset cannot support it "
            "without leakage or label manipulation.\n")
    f.write("Phase 7 analysis (results/phase7_validation_summary.txt, "
            "section 8) documents why.\n")

print(f"✅ Saved: results/phase8_final_results.txt")

# ================================================================
# 10. PREDICTION FUNCTION DEMO (exact output schema)
# ================================================================

separator()
print("PREDICTION FUNCTION DEMO (exact output schema)")
separator()

demo_rows = X_test.sample(5, random_state=RANDOM_STATE)

for i, (_, row) in enumerate(demo_rows.iterrows(), start=1):
    result = predict_placement(row.to_dict())
    actual = "PLACED" if y_test.loc[row.name] == 1 else "NOT PLACED"
    print(
        f"Student {i}: prediction={result['prediction']:<10} "
        f"placement_probability={result['placement_probability']:.4f} "
        f"confidence={result['confidence']:.4f} | actual: {actual}"
    )

print("\n✅ predict_placement() returns the exact Phase 8 output schema")

# ================================================================
# 11. FINAL SUMMARY
# ================================================================

separator()
print("PHASE 8 - FINAL PIPELINE TRAINING COMPLETED")
separator()
print(f"\nModel saved     : {MODEL_PATH}")
print(f"Test accuracy  : {metrics['Accuracy']:.4f}")
print(f"Test ROC-AUC   : {metrics['ROC-AUC']:.4f}")
print(f"Test F1        : {metrics['F1']:.4f}")
print("\nNext: start the backend with")
print("  uvicorn backend.app.main:app --reload")
print("then POST a student profile to http://127.0.0.1:8000/api/predict")
