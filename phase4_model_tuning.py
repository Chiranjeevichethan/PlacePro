# ============================================================
# PLACEPRO - INTELLIGENT STUDENT PLACEMENT PREDICTION SYSTEM
# Phase 4 - ML Model Tuning & Final Model Selection
# ============================================================
#
# Builds on Phase 3 (main.py). This phase:
#   1. Fixes the model-selection logic (ROC-AUC + F1, NOT accuracy)
#   2. Performs proper hyperparameter tuning (LR / RF / XGBoost)
#   3. Uses a leak-free feature-engineering + preprocessing pipeline
#   4. Evaluates the tuned models on a completely untouched test set
#   5. Saves ONLY the final model and provides a reusable
#      predict_placement() function (src/predictor.py)
#
# Usage:
#   python phase4_model_tuning.py                  # full pipeline
#   python phase4_model_tuning.py --sample 30000   # quick smoke test
#
# NOTE: --sample is ONLY for quick development verification.
# The final reported results must always come from the full dataset.
# ============================================================

import argparse
import os
import sys
import warnings

import joblib

import matplotlib

matplotlib.use("Agg")  # headless-safe figure saving
import matplotlib.pyplot as plt
import seaborn as sns

import numpy as np
import pandas as pd

# ------------------------------------------------------------
# MACHINE LEARNING
# ------------------------------------------------------------

from sklearn.compose import ColumnTransformer, make_column_selector
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.impute import SimpleImputer

from sklearn.model_selection import (
    train_test_split,
    StratifiedKFold,
    cross_validate,
    GridSearchCV,
    RandomizedSearchCV,
)

from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier

from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    roc_curve,
    confusion_matrix,
    classification_report,
)

from xgboost import XGBClassifier

warnings.filterwarnings("ignore")

# Force UTF-8 console output so emoji/symbols render on Windows
# consoles that default to cp1252.
for _stream in (sys.stdout, sys.stderr):
    if _stream is not None and hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

# ------------------------------------------------------------
# PROJECT MODULES
# ------------------------------------------------------------

# Ensure the project root is on sys.path so `src.*` imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.feature_engineering import FeatureEngineeringTransformer
from src.predictor import predict_placement

# ============================================================
# CONFIGURATION
# ============================================================

DATA_PATH = "data/placement.csv"

OUTPUT_DIR = "outputs"
RESULTS_DIR = "results"
MODEL_DIR = "models"

FINAL_MODEL_PATH = os.path.join(MODEL_DIR, "placepro_tuned_best_model.pkl")

RANDOM_STATE = 42

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)


def print_header(text):
    print("\n" + "=" * 70)
    print(text)
    print("=" * 70)


# ============================================================
# PIPELINE BUILDERS
# ============================================================

def build_preprocessor():
    """
    Numeric: median imputation -> StandardScaler
    Categorical: most-frequent imputation -> OneHotEncoder
    Columns are selected by dtype AFTER feature engineering, so the
    engineered columns are picked up automatically. The "string" dtype
    covers pandas 3.x (new default string dtype) and "object" covers
    pandas 2.x.
    """
    numeric_transformer = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])

    categorical_transformer = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ])

    return ColumnTransformer(
        transformers=[
            ("numeric", numeric_transformer,
             make_column_selector(dtype_include=np.number)),
            ("categorical", categorical_transformer,
             make_column_selector(dtype_include=["object", "category", "string"])),
        ]
    )


def build_pipeline(model):
    """
    Full leak-free pipeline:
        feature_engineering -> preprocessing -> model

    The feature-engineering transformer is embedded in the pipeline,
    so its statistics are fitted on each training fold only, and the
    saved model can be used for prediction with zero extra code.
    """
    return Pipeline(steps=[
        ("feature_engineering", FeatureEngineeringTransformer()),
        ("preprocessor", build_preprocessor()),
        ("model", model),
    ])


# ============================================================
# EVALUATION HELPER
# ============================================================

def evaluate_model(pipeline, X, y):
    """Return (metrics_dict, y_pred, y_prob) on any dataset."""
    y_pred = pipeline.predict(X)
    y_prob = pipeline.predict_proba(X)[:, 1]

    metrics = {
        "Accuracy": accuracy_score(y, y_pred),
        "Precision": precision_score(y, y_pred, zero_division=0),
        "Recall": recall_score(y, y_pred, zero_division=0),
        "F1 Score": f1_score(y, y_pred, zero_division=0),
        "ROC-AUC": roc_auc_score(y, y_prob),
    }
    return metrics, y_pred, y_prob


# ============================================================
# COMMAND LINE ARGUMENTS
# ============================================================

parser = argparse.ArgumentParser(
    description="PlacePro Phase 4 - ML model tuning and final selection."
)
parser.add_argument(
    "--sample",
    type=int,
    default=None,
    help="DEV ONLY: run on a random sample of N rows for a quick smoke test.",
)
args = parser.parse_args()

SMOKE_TEST = args.sample is not None
SAMPLE_N = args.sample

# Smaller search budgets during smoke tests (never for final results)
N_ITER = 5 if SMOKE_TEST else 20
INNER_FOLDS = 3 if SMOKE_TEST else 5

if SMOKE_TEST:
    print(f"⚠️  SMOKE TEST MODE: using only {SAMPLE_N} rows (dev only!)")


# ============================================================
# 1. LOAD DATASET
# ============================================================

print_header("PHASE 4 - LOAD DATASET")

if not os.path.exists(DATA_PATH):
    print("❌ Dataset not found!")
    print(f"Expected location: {DATA_PATH}")
    sys.exit(1)

df = pd.read_csv(DATA_PATH)

# Dev smoke test: random subsample of the data
if SMOKE_TEST:
    df = df.sample(n=min(SAMPLE_N, len(df)), random_state=RANDOM_STATE).reset_index(drop=True)

print("✅ Dataset loaded")
print("Shape:", df.shape)


# ============================================================
# 2. REMOVE DATA LEAKAGE / NON-PREDICTIVE COLUMNS
# ============================================================

print_header("DATA CLEANING")

# salary_package_lpa is a CONSEQUENCE of placement -> severe leakage
if "salary_package_lpa" in df.columns:
    df.drop("salary_package_lpa", axis=1, inplace=True)
    print("✅ Removed salary_package_lpa (data leakage)")

# student_id is a unique identifier with no predictive meaning
if "student_id" in df.columns:
    df.drop("student_id", axis=1, inplace=True)
    print("✅ Removed student_id (identifier)")


# ============================================================
# 3. TARGET ENCODING
# ============================================================

if "placement_status" not in df.columns:
    print("❌ placement_status column not found!")
    sys.exit(1)

# Map string labels -> 0/1 (also handles already-numeric targets)
df["placement_status"] = df["placement_status"].map({
    "Not Placed": 0,
    "Placed": 1,
})

df["placement_status"] = df["placement_status"].fillna(
    pd.to_numeric(df["placement_status"], errors="coerce")
)

if df["placement_status"].isnull().any():
    print("❌ Target contains unknown values.")
    sys.exit(1)

df["placement_status"] = df["placement_status"].astype(int)

print("\nTarget distribution:")
print(df["placement_status"].value_counts().to_string())


# ============================================================
# 4. CLASS IMBALANCE ANALYSIS
# ============================================================

print_header("CLASS IMBALANCE ANALYSIS")

placed_count = int((df["placement_status"] == 1).sum())
not_placed_count = int((df["placement_status"] == 0).sum())
total = len(df)

imbalance_ratio = max(placed_count, not_placed_count) / min(placed_count, not_placed_count)

print(f"Placed     (1): {placed_count:>7,}  ({placed_count / total * 100:.2f}%)")
print(f"Not Placed (0): {not_placed_count:>7,}  ({not_placed_count / total * 100:.2f}%)")
print(f"Imbalance ratio (majority/minority): {imbalance_ratio:.3f}")

if imbalance_ratio < 1.5:
    print("\n✅ Imbalance is MILD (ratio < 1.5).")
    print("   -> Class weighting is NOT assumed necessary.")
    print("   -> It is still TESTED for Logistic Regression and Random")
    print("      Forest via class_weight in the search grids, and the")
    print("      data decides whether it helps.")
else:
    print("\n⚠️  Notable imbalance detected -> class weighting is justified.")


# ============================================================
# 5. TRAIN / TEST SPLIT
# ============================================================

print_header("TRAIN / TEST SPLIT")

X = df.drop(columns=["placement_status"])
y = df["placement_status"]

# Stratified split keeps the class proportions identical in both sets.
# The test set is COMPLETELY untouched until final evaluation.
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=RANDOM_STATE,
    stratify=y,
)

print(f"Training samples: {len(X_train):,}")
print(f"Test samples:     {len(X_test):,}")
print("✅ Test set held out - only used for final evaluation")


# ============================================================
# 6. MODEL SELECTION LOGIC (FIXED vs PHASE 3)
# ============================================================

print_header("MODEL SELECTION LOGIC")

print("""
WHY ACCURACY ALONE IS NOT ENOUGH
--------------------------------
1. Accuracy treats every mistake as equal, but in placement prediction
   the two error types have different real-world costs:
      - False "PLACED"      -> false hope / wasted counseling effort
      - False "NOT PLACED"  -> a student who WOULD be placed is missed
2. With a ~54/46 class split, a naive "always predict majority" model
   already reaches ~54% accuracy, so accuracy alone is misleading.
3. Accuracy depends on a single 0.5 decision threshold.

THE METRICS WE COMPARE
----------------------
- Accuracy   : overall fraction correct (context only)
- Precision  : of predicted "Placed", how many really placed
- Recall     : of actually placed students, how many were caught
- F1 Score   : harmonic mean of precision & recall
- ROC-AUC    : ranking quality across ALL thresholds, robust to
               imbalance, threshold-independent
- CV score   : generalization across many train/validation splits

PRIMARY METRIC:  ROC-AUC
   Threshold-independent and robust to the mild imbalance. It measures
   how well the model RANKS placed vs not-placed students, which is
   exactly what a counseling/recommendation system needs.

TIE-BREAKER:    F1 Score
   When ROC-AUC is nearly tied, F1 balances precision (avoid false
   hope) and recall (avoid missed opportunities).

CROSS-VALIDATION confirms the choice is stable, not a lucky split.
""")


# ============================================================
# 7. BASELINE MODELS (Phase 3 defaults)
# ============================================================
#
# Same hyperparameters as Phase 3 (main.py), evaluated on the same
# untouched test set, so baseline-vs-tuned is an apples-to-apples
# comparison. Baseline models are NOT saved — only the final model is.

print_header("BASELINE MODELS (Phase 3 defaults)")

baseline_models = {
    "Logistic Regression": LogisticRegression(
        max_iter=2000,
        class_weight="balanced",
        random_state=RANDOM_STATE,
    ),
    "Decision Tree": DecisionTreeClassifier(
        max_depth=10,
        min_samples_split=20,
        min_samples_leaf=10,
        class_weight="balanced",
        random_state=RANDOM_STATE,
    ),
    "Random Forest": RandomForestClassifier(
        n_estimators=300,
        max_depth=15,
        min_samples_split=10,
        min_samples_leaf=3,
        class_weight="balanced",
        random_state=RANDOM_STATE,
        n_jobs=-1,
    ),
    "XGBoost": XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        objective="binary:logistic",
        random_state=RANDOM_STATE,
        n_jobs=-1,
    ),
}

baseline_rows = []

for model_name, model in baseline_models.items():
    print(f"🔄 Training baseline {model_name}...")

    pipeline = build_pipeline(model)
    pipeline.fit(X_train, y_train)

    metrics, _, _ = evaluate_model(pipeline, X_test, y_test)
    baseline_rows.append({"Model": model_name, **metrics})

baseline_df = pd.DataFrame(baseline_rows).sort_values("ROC-AUC", ascending=False)

print("\nBaseline performance (untouched test set):")
print(baseline_df.to_string(index=False))


# ============================================================
# 8. HYPERPARAMETER TUNING
# ============================================================
#
# - Logistic Regression : GridSearchCV     (small space -> full grid)
# - Random Forest       : RandomizedSearchCV (large space -> sampled)
# - XGBoost             : RandomizedSearchCV (large space -> sampled)
#
# All searches use StratifiedKFold and score on ROC-AUC (the primary
# metric chosen above). Preprocessing + feature engineering live in
# the pipeline, so every fold fits them on training data only
# (no leakage).

print_header("HYPERPARAMETER TUNING")

inner_cv = StratifiedKFold(
    n_splits=INNER_FOLDS,
    shuffle=True,
    random_state=RANDOM_STATE,
)

tuned_models = {}

# ------------------------------------------------------------
# 8a. LOGISTIC REGRESSION - GridSearchCV
# ------------------------------------------------------------

print("\n" + "-" * 70)
print("TUNING: Logistic Regression (GridSearchCV)")
print("-" * 70)

lr_param_grid = {
    "model__C": [0.01, 0.1, 1.0, 10.0],
    "model__penalty": ["l2"],
    "model__solver": ["lbfgs"],
    "model__class_weight": [None, "balanced"],
    "model__max_iter": [2000],
}

lr_search = GridSearchCV(
    estimator=build_pipeline(LogisticRegression(random_state=RANDOM_STATE)),
    param_grid=lr_param_grid,
    cv=inner_cv,
    scoring="roc_auc",
    n_jobs=-1,
    verbose=1,
)

lr_search.fit(X_train, y_train)

print("\n✅ Logistic Regression tuned")
print("Best params:", lr_search.best_params_)
print(f"Best CV ROC-AUC: {lr_search.best_score_:.4f}")

tuned_models["Logistic Regression (Tuned)"] = lr_search.best_estimator_

# ------------------------------------------------------------
# 8b. RANDOM FOREST - RandomizedSearchCV
# ------------------------------------------------------------

print("\n" + "-" * 70)
print("TUNING: Random Forest (RandomizedSearchCV)")
print("-" * 70)

rf_param_dist = {
    "model__n_estimators": [100, 200, 300],
    "model__max_depth": [10, 20, 30, None],
    "model__min_samples_split": [2, 5, 10],
    "model__min_samples_leaf": [1, 2, 4],
    "model__max_features": ["sqrt", "log2"],
    "model__class_weight": [None, "balanced"],
}

rf_search = RandomizedSearchCV(
    estimator=build_pipeline(
        RandomForestClassifier(random_state=RANDOM_STATE, n_jobs=-1)
    ),
    param_distributions=rf_param_dist,
    n_iter=N_ITER,
    cv=inner_cv,
    scoring="roc_auc",
    n_jobs=1,  # RF parallelises internally; avoids nested parallelism
    random_state=RANDOM_STATE,
    verbose=1,
)

rf_search.fit(X_train, y_train)

print("\n✅ Random Forest tuned")
print("Best params:", rf_search.best_params_)
print(f"Best CV ROC-AUC: {rf_search.best_score_:.4f}")

tuned_models["Random Forest (Tuned)"] = rf_search.best_estimator_

# ------------------------------------------------------------
# 8c. XGBOOST - RandomizedSearchCV
# ------------------------------------------------------------

print("\n" + "-" * 70)
print("TUNING: XGBoost (RandomizedSearchCV)")
print("-" * 70)

xgb_param_dist = {
    "model__n_estimators": [200, 300, 400],
    "model__max_depth": [3, 5, 7],
    "model__learning_rate": [0.05, 0.1, 0.2],
    "model__subsample": [0.7, 0.8, 1.0],
    "model__colsample_bytree": [0.7, 0.8, 1.0],
    "model__min_child_weight": [1, 3, 5],
    "model__reg_alpha": [0.0, 0.1, 1.0],
    "model__reg_lambda": [1.0, 2.0],
}

xgb_search = RandomizedSearchCV(
    estimator=build_pipeline(
        XGBClassifier(
            objective="binary:logistic",
            random_state=RANDOM_STATE,
            n_jobs=-1,
        )
    ),
    param_distributions=xgb_param_dist,
    n_iter=N_ITER,
    cv=inner_cv,
    scoring="roc_auc",
    n_jobs=1,  # XGBoost parallelises internally; avoids nested parallelism
    random_state=RANDOM_STATE,
    verbose=1,
)

xgb_search.fit(X_train, y_train)

print("\n✅ XGBoost tuned")
print("Best params:", xgb_search.best_params_)
print(f"Best CV ROC-AUC: {xgb_search.best_score_:.4f}")

tuned_models["XGBoost (Tuned)"] = xgb_search.best_estimator_


# ============================================================
# 9. EVALUATE TUNED MODELS ON THE UNTOUCHED TEST SET
# ============================================================

print_header("TUNED MODEL EVALUATION (untouched test set)")

tuned_rows = []
tuned_predictions = {}
tuned_roc_data = {}

for model_name, pipeline in tuned_models.items():
    metrics, y_pred, y_prob = evaluate_model(pipeline, X_test, y_test)
    tuned_rows.append({"Model": model_name, **metrics})
    tuned_predictions[model_name] = y_pred

    fpr, tpr, _ = roc_curve(y_test, y_prob)
    tuned_roc_data[model_name] = (fpr, tpr, metrics["ROC-AUC"])

    print(f"\n{model_name}:")
    print(f"  Accuracy : {metrics['Accuracy']:.4f}")
    print(f"  Precision: {metrics['Precision']:.4f}")
    print(f"  Recall   : {metrics['Recall']:.4f}")
    print(f"  F1 Score : {metrics['F1 Score']:.4f}")
    print(f"  ROC-AUC  : {metrics['ROC-AUC']:.4f}")

tuned_df = pd.DataFrame(tuned_rows)

# Sort by PRIMARY metric (ROC-AUC), then F1 as tie-breaker
tuned_df = tuned_df.sort_values(
    ["ROC-AUC", "F1 Score"],
    ascending=False,
).reset_index(drop=True)

print("\nTuned model comparison (sorted by ROC-AUC):")
print(tuned_df.to_string(index=False))


# ============================================================
# 10. CROSS-VALIDATION OF TUNED MODELS
# ============================================================
#
# 5-fold stratified CV on the full dataset (same protocol as Phase 3)
# to confirm the test-set results generalise beyond one split.

print_header("CROSS-VALIDATION OF TUNED MODELS")

outer_cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)

cv_rows = []

for model_name, pipeline in tuned_models.items():
    print(f"🔄 Cross-validating {model_name}...")

    scores = cross_validate(
        pipeline,
        X,
        y,
        cv=outer_cv,
        scoring=["accuracy", "roc_auc"],
        n_jobs=1,
    )

    cv_rows.append({
        "Model": model_name,
        "CV Mean Accuracy": scores["test_accuracy"].mean(),
        "CV Accuracy Std": scores["test_accuracy"].std(),
        "CV Mean ROC-AUC": scores["test_roc_auc"].mean(),
        "CV ROC-AUC Std": scores["test_roc_auc"].std(),
    })

cv_df = pd.DataFrame(cv_rows)

print("\nCross-validation results:")
print(cv_df.to_string(index=False))


# ============================================================
# 11. FINAL MODEL SELECTION
# ============================================================

print_header("FINAL MODEL SELECTION")

# ------------------------------------------------------------
# Selection rule (replaces the Phase 3 "best accuracy" logic):
#   PRIMARY   : ROC-AUC (threshold-independent, robust to imbalance)
#   TIE-BREAK : F1 Score
#
# Models whose test ROC-AUC is within ~2 cross-validation standard
# deviations of the best are considered statistically tied (the gap
# is just noise). F1 then decides the winner — it balances precision
# (avoid false hope) and recall (avoid missed placements).
# ------------------------------------------------------------

best_auc = tuned_df["ROC-AUC"].max()

max_auc_std = float(cv_df["CV ROC-AUC Std"].max())
tolerance = 2.0 * max_auc_std

tied_models = tuned_df[tuned_df["ROC-AUC"] >= best_auc - tolerance]
tied_models = tied_models.sort_values("F1 Score", ascending=False)

final_model_name = tied_models.iloc[0]["Model"]
final_pipeline = tuned_models[final_model_name]

# Find the matching CV row
final_cv_row = cv_df.loc[cv_df["Model"] == final_model_name].iloc[0]

final_metrics = tuned_df.loc[tuned_df["Model"] == final_model_name].iloc[0]

print(f"Best test ROC-AUC      : {best_auc:.4f}")
print(f"Max CV ROC-AUC std     : {max_auc_std:.4f}")
print(f"Tie tolerance (2x std) : {tolerance:.4f}")

print("\nModels within tolerance (statistically tied on ROC-AUC):")
print(tied_models[["Model", "ROC-AUC", "F1 Score"]].to_string(index=False))
print("Tie broken by F1 Score (precision / recall balance).")

print(f"\n🏆 Final model: {final_model_name}")
print(f"   Test Accuracy : {final_metrics['Accuracy']:.4f}")
print(f"   Test Precision: {final_metrics['Precision']:.4f}")
print(f"   Test Recall   : {final_metrics['Recall']:.4f}")
print(f"   Test F1 Score : {final_metrics['F1 Score']:.4f}")
print(f"   Test ROC-AUC  : {final_metrics['ROC-AUC']:.4f}")
print(f"   CV mean Acc   : {final_cv_row['CV Mean Accuracy']:.4f} (+/- {final_cv_row['CV Accuracy Std']:.4f})")
print(f"   CV mean AUC   : {final_cv_row['CV Mean ROC-AUC']:.4f} (+/- {final_cv_row['CV ROC-AUC Std']:.4f})")


# ============================================================
# 12. OUTPUTS - GRAPHS
# ============================================================

print_header("GENERATING GRAPHS")

# ------------------------------------------------------------
# 12a. Tuned model comparison (all 5 metrics)
# ------------------------------------------------------------

melted = tuned_df.melt(
    id_vars=["Model"],
    var_name="Metric",
    value_name="Score",
)

plt.figure(figsize=(12, 6))
sns.barplot(data=melted, x="Model", y="Score", hue="Metric")
plt.ylim(0, 1)
plt.title("PlacePro Phase 4 - Tuned Model Comparison")
plt.xlabel("Model")
plt.ylabel("Score")
plt.legend(title="Metric", bbox_to_anchor=(1.02, 1), loc="upper left")
plt.tight_layout()
plt.savefig(f"{OUTPUT_DIR}/tuned_model_comparison.png", dpi=300)
plt.close()
print("✅ tuned_model_comparison.png saved")

# ------------------------------------------------------------
# 12b. ROC curves for tuned models
# ------------------------------------------------------------

plt.figure(figsize=(9, 7))

for model_name, (fpr, tpr, auc_value) in tuned_roc_data.items():
    plt.plot(fpr, tpr, label=f"{model_name} (AUC={auc_value:.3f})")

plt.plot([0, 1], [0, 1], linestyle="--", color="gray")
plt.xlabel("False Positive Rate")
plt.ylabel("True Positive Rate")
plt.title("PlacePro Phase 4 - Tuned ROC Curves")
plt.legend(loc="lower right")
plt.tight_layout()
plt.savefig(f"{OUTPUT_DIR}/tuned_roc_curves.png", dpi=300)
plt.close()
print("✅ tuned_roc_curves.png saved")

# ------------------------------------------------------------
# 12c. Confusion matrices for tuned models
# ------------------------------------------------------------

fig, axes = plt.subplots(1, len(tuned_models), figsize=(18, 5))

for ax, (model_name, y_pred) in zip(axes, tuned_predictions.items()):
    cm = confusion_matrix(y_test, y_pred)

    sns.heatmap(
        cm,
        annot=True,
        fmt="d",
        cmap="Blues",
        xticklabels=["Not Placed", "Placed"],
        yticklabels=["Not Placed", "Placed"],
        ax=ax,
        cbar=False,
    )
    ax.set_title(model_name)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual")

plt.suptitle("PlacePro Phase 4 - Tuned Model Confusion Matrices")
plt.tight_layout()
plt.savefig(f"{OUTPUT_DIR}/tuned_confusion_matrix.png", dpi=300)
plt.close()
print("✅ tuned_confusion_matrix.png saved")

# ------------------------------------------------------------
# 12d. Feature importance of the FINAL model
# ------------------------------------------------------------

fe_step = final_pipeline.named_steps["feature_engineering"]
pre_step = final_pipeline.named_steps["preprocessor"]
model_step = final_pipeline.named_steps["model"]

# Final feature names after feature engineering + one-hot encoding
engineered_names = fe_step.get_feature_names_out(X_train.columns.tolist())
feature_names = pre_step.get_feature_names_out(engineered_names)

# Tree-based models expose feature_importances_, linear models expose
# coefficients (absolute value = strength of influence)
if hasattr(model_step, "feature_importances_"):
    importances = model_step.feature_importances_
else:
    importances = np.abs(model_step.coef_).ravel()

importance_df = pd.DataFrame({
    "Feature": feature_names,
    "Importance": importances,
})

importance_df = importance_df.sort_values("Importance", ascending=False).reset_index(drop=True)

top_features = importance_df.head(20).sort_values("Importance")

plt.figure(figsize=(10, 8))
sns.barplot(data=top_features, x="Importance", y="Feature")
plt.title(f"Top 20 Feature Importances - {final_model_name}")
plt.tight_layout()
plt.savefig(f"{OUTPUT_DIR}/tuned_feature_importance.png", dpi=300)
plt.close()
print("✅ tuned_feature_importance.png saved")

print("\nTop 10 features:")
print(importance_df.head(10).to_string(index=False))


# ============================================================
# 13. RESULTS - FILES
# ============================================================

# ------------------------------------------------------------
# 13a. results/tuned_model_comparison.csv
# ------------------------------------------------------------

tuned_df.to_csv(f"{RESULTS_DIR}/tuned_model_comparison.csv", index=False)
print("✅ results/tuned_model_comparison.csv saved")

# ------------------------------------------------------------
# 13b. results/tuned_cross_validation.csv
# ------------------------------------------------------------

cv_df.to_csv(f"{RESULTS_DIR}/tuned_cross_validation.csv", index=False)
print("✅ results/tuned_cross_validation.csv saved")

# ------------------------------------------------------------
# 13c. results/tuned_classification_report.txt (final model)
# ------------------------------------------------------------

final_pred = tuned_predictions[final_model_name]

report = classification_report(
    y_test,
    final_pred,
    target_names=["Not Placed", "Placed"],
    zero_division=0,
)

with open(f"{RESULTS_DIR}/tuned_classification_report.txt", "w") as file:
    file.write("PLACEPRO PHASE 4 - CLASSIFICATION REPORT\n")
    file.write("=========================================\n\n")
    file.write(f"Model: {final_model_name}\n\n")
    file.write(report)

print("✅ results/tuned_classification_report.txt saved")

# ------------------------------------------------------------
# 13d. results/tuned_final_results.txt
# ------------------------------------------------------------

with open(f"{RESULTS_DIR}/tuned_final_results.txt", "w") as file:
    file.write("PLACEPRO PHASE 4 - FINAL RESULTS\n")
    file.write("================================\n\n")

    file.write(f"Dataset samples : {len(df):,}\n")
    file.write(f"Features used   : {X.shape[1]} raw -> {len(feature_names)} after engineering + encoding\n")
    file.write(f"Train / Test    : {len(X_train):,} / {len(X_test):,} (stratified)\n\n")

    file.write("CLASS IMBALANCE\n")
    file.write("---------------\n")
    file.write(f"Placed     : {placed_count:,} ({placed_count / total * 100:.2f}%)\n")
    file.write(f"Not Placed : {not_placed_count:,} ({not_placed_count / total * 100:.2f}%)\n")
    file.write(f"Ratio      : {imbalance_ratio:.3f} (mild -> weighting tested, not assumed)\n\n")

    file.write("MODEL SELECTION LOGIC\n")
    file.write("---------------------\n")
    file.write("Primary metric : ROC-AUC (threshold-independent, robust to imbalance)\n")
    file.write("Tie-breaker    : F1 Score\n")
    file.write("Confirmation   : Stratified 5-fold cross-validation\n\n")

    file.write("BASELINE MODELS (Phase 3 defaults, test set)\n")
    file.write("---------------------------------------------\n")
    file.write(baseline_df.to_string(index=False))
    file.write("\n\n")

    file.write("TUNED MODELS (test set, sorted by ROC-AUC)\n")
    file.write("------------------------------------------\n")
    file.write(tuned_df.to_string(index=False))
    file.write("\n\n")

    file.write("TUNED MODELS CROSS-VALIDATION\n")
    file.write("-----------------------------\n")
    file.write(cv_df.to_string(index=False))
    file.write("\n\n")

    file.write("FINAL MODEL\n")
    file.write("-----------\n")
    file.write(f"Model            : {final_model_name}\n")
    file.write(f"Accuracy         : {final_metrics['Accuracy']:.4f}\n")
    file.write(f"Precision        : {final_metrics['Precision']:.4f}\n")
    file.write(f"Recall           : {final_metrics['Recall']:.4f}\n")
    file.write(f"F1 Score         : {final_metrics['F1 Score']:.4f}\n")
    file.write(f"ROC-AUC          : {final_metrics['ROC-AUC']:.4f}\n")
    file.write(f"CV mean accuracy : {final_cv_row['CV Mean Accuracy']:.4f}\n")
    file.write(f"CV mean ROC-AUC  : {final_cv_row['CV Mean ROC-AUC']:.4f}\n")
    file.write(f"Selection logic  : ROC-AUC primary, tolerance "
               f"{tolerance:.4f} (= 2x CV std), F1 tie-break\n\n")

    file.write("PREDICTION FUNCTION\n")
    file.write("-------------------\n")
    file.write("from src.predictor import predict_placement\n")
    file.write("result = predict_placement(student_data_dict)\n")
    file.write("result['status'] / result['probability']\n")

print("✅ results/tuned_final_results.txt saved")


# ============================================================
# 14. SAVE ONLY THE FINAL MODEL
# ============================================================
#
# The pipeline (feature engineering + preprocessing + tuned model)
# is saved as ONE file. models/*.pkl is already gitignored, so the
# large file is never committed to GitHub.

joblib.dump(final_pipeline, FINAL_MODEL_PATH)
print(f"✅ Final model saved: {FINAL_MODEL_PATH}")


# ============================================================
# 15. PREDICTION FUNCTION DEMO
# ============================================================

print_header("PREDICTION FUNCTION DEMO")

demo_rows = X_test.sample(5, random_state=RANDOM_STATE)

for i, (_, row) in enumerate(demo_rows.iterrows(), start=1):
    result = predict_placement(row.to_dict())
    actual = "PLACED" if y_test.loc[row.name] == 1 else "NOT PLACED"
    print(
        f"Student {i}: predicted {result['status']:<10} "
        f"({result['probability']:.2f}%)  |  actual: {actual}"
    )

print("\n✅ predict_placement() works with the exact training pipeline")


# ============================================================
# 16. FINAL SUMMARY
# ============================================================

print_header("PHASE 4 COMPLETED")

print("=" * 70)
print("PLACEPRO - PHASE 4: ML MODEL TUNING - SUMMARY")
print("=" * 70)

print("\n--- BASELINE MODELS (Phase 3 defaults) ---")
print(baseline_df.to_string(index=False))

print("\n--- TUNED MODELS ---")
print(tuned_df.to_string(index=False))

print("\n--- BEST MODEL (final selection) ---")
print(f"Model              : {final_model_name}")
print(f"Accuracy           : {final_metrics['Accuracy']:.4f}")
print(f"Precision          : {final_metrics['Precision']:.4f}")
print(f"Recall             : {final_metrics['Recall']:.4f}")
print(f"F1                 : {final_metrics['F1 Score']:.4f}")
print(f"ROC-AUC            : {final_metrics['ROC-AUC']:.4f}")
print(f"Cross-validation   : accuracy {final_cv_row['CV Mean Accuracy']:.4f} "
      f"| ROC-AUC {final_cv_row['CV Mean ROC-AUC']:.4f}")
print(f"Selection logic   : ROC-AUC primary (tolerance {tolerance:.4f} = 2x CV std), "
      f"F1 tie-break -> {final_model_name}")

print("\n--- FILES MODIFIED / CREATED ---")
print("Created:")
print("  phase4_model_tuning.py            - Phase 4 tuning pipeline (this script)")
print("  src/feature_engineering.py        - reusable leak-free feature engineering")
print("  src/predictor.py                  - predict_placement() function")
print("Modified:")
print("  README.md                         - Phase 4 documentation")
print("Generated outputs:")
print("  outputs/tuned_model_comparison.png")
print("  outputs/tuned_roc_curves.png")
print("  outputs/tuned_confusion_matrix.png")
print("  outputs/tuned_feature_importance.png")
print("  results/tuned_model_comparison.csv")
print("  results/tuned_cross_validation.csv")
print("  results/tuned_classification_report.txt")
print("  results/tuned_final_results.txt")
print(f"  models/{os.path.basename(FINAL_MODEL_PATH)}  (gitignored, not committed)")

print("\n🎉 PHASE 4 COMPLETED - PLACEPRO ML MODEL TUNING DONE!")
