# ============================================================
# PLACEPRO - INTELLIGENT STUDENT PLACEMENT PREDICTION SYSTEM
# Phase 6 - Dataset Quality Improvement: Baseline Models
# ============================================================
#
# New Phase 6 dataset: data/placement_phase6.csv
#   - 100,000 rows, 18 columns
#   - Target: placement_status (0 = Not Placed, 1 = Placed)
#   - salary_package_lpa is a POST-PLACEMENT variable and is the
#     ONLY column with missing values (31,525) - it is removed
#     before training because it would leak the target.
#
# This script establishes the BASELINE for the new dataset:
#   - validation of data quality (shape, missing, duplicates, types)
#   - leak-free preprocessing pipeline
#   - 4 baseline models (Logistic Regression, Decision Tree,
#     Random Forest, XGBoost) with the SAME defaults used for the
#     Phase 4 baselines, so results are directly comparable
#   - test-set metrics + stratified 5-fold CV
#
# NOTE: This is ONLY the Phase 6 baseline. No hyperparameter
# tuning, no oversampling, no artificial accuracy improvements.
#
# Usage:
#   python phase6_dataset_baseline.py                # full pipeline
#   python phase6_dataset_baseline.py --sample 20000 # dev smoke test
#
# NOTE: --sample is ONLY for quick development verification.
# The final reported results must always come from the full dataset.
# ============================================================

import argparse
import os
import sys
import warnings

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

from sklearn.model_selection import train_test_split, StratifiedKFold, cross_validate

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
# consoles that default to cp1252 (same trick as Phase 4/5).
for _stream in (sys.stdout, sys.stderr):
    if _stream is not None and hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ============================================================
# CONFIGURATION
# ============================================================

DATA_PATH = "data/placement_phase6.csv"

OUTPUT_DIR = "outputs"
RESULTS_DIR = "results"

RANDOM_STATE = 42

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)


def print_header(text):
    print("\n" + "=" * 70)
    print(text)
    print("=" * 70)


# ============================================================
# COMMAND LINE ARGUMENTS
# ============================================================

parser = argparse.ArgumentParser(
    description="PlacePro Phase 6 - baseline models on the new dataset."
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

if SMOKE_TEST:
    print(f"⚠️  SMOKE TEST MODE: using only {SAMPLE_N} rows (dev only!)")


# ============================================================
# 1. LOAD DATASET
# ============================================================

print_header("PHASE 6 - LOAD DATASET")

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
# 2. DATA QUALITY VALIDATION
# ============================================================

print_header("DATA QUALITY VALIDATION")

print("📊 Shape:")
print(f"   Rows    : {len(df):,}")
print(f"   Columns : {len(df.columns)}")

print("\n📊 Data types:")
print(df.dtypes.to_string())

print("\n📊 Missing values (per column):")
missing = df.isnull().sum()
print(missing.to_string())
print(f"   Total missing cells: {int(missing.sum()):,}")

print("\n📊 Duplicate rows:")
print(f"   {int(df.duplicated().sum()):,}")

print("\n📊 Target distribution:")
target_counts = df["placement_status"].value_counts()
print(target_counts.to_string())
print(f"   Placed rate: {target_counts.get(1, 0) / len(df) * 100:.2f}%")


# ============================================================
# 3. REMOVE DATA LEAKAGE / NON-PREDICTIVE COLUMNS
# ============================================================
#
# salary_package_lpa is a CONSEQUENCE of placement (it only exists
# for placed students - its 31,525 missing values exactly match the
# 31,525 non-placed students). It would leak the target, so it is
# removed before training.
#
# Any ID-like column (unique identifier with no predictive meaning)
# is also removed if present.

print_header("DATA CLEANING")

if "salary_package_lpa" in df.columns:
    df.drop("salary_package_lpa", axis=1, inplace=True)
    print("✅ Removed salary_package_lpa (post-placement leakage variable)")

for col in df.columns:
    if col.lower() in ("student_id", "id", "studentid", "sl_no", "serial_no"):
        df.drop(col, axis=1, inplace=True)
        print(f"✅ Removed ID-like column: {col}")

# ============================================================
# 4. TARGET ENCODING
# ============================================================

print_header("TARGET ENCODING")

if "placement_status" not in df.columns:
    print("❌ placement_status column not found!")
    sys.exit(1)

# Encode target as 0/1 (handles BOTH string labels like
# "Not Placed"/"Placed" and already-numeric 0/1 values)
if str(df["placement_status"].dtype) in ("object", "string"):
    df["placement_status"] = df["placement_status"].map({
        "Not Placed": 0,
        "Placed": 1,
    })

df["placement_status"] = pd.to_numeric(
    df["placement_status"], errors="coerce"
)

if df["placement_status"].isnull().any():
    print("❌ Target contains unknown values.")
    sys.exit(1)

df["placement_status"] = df["placement_status"].astype(int)

print("Target distribution after encoding:")
print(df["placement_status"].value_counts().to_string())

# ---- Class imbalance summary (reported honestly, NOT manipulated) ----
placed_count = int((df["placement_status"] == 1).sum())
not_placed_count = int((df["placement_status"] == 0).sum())
total = len(df)

imbalance_ratio = max(placed_count, not_placed_count) / min(placed_count, not_placed_count)

print(f"\nClass imbalance ratio (majority/minority): {imbalance_ratio:.3f}")
if imbalance_ratio < 1.5:
    print("   -> MILD imbalance (ratio < 1.5)")
elif imbalance_ratio < 2.0:
    print("   -> MODERATE imbalance (1.5 <= ratio < 2.0)")
else:
    print("   -> NOTABLE imbalance (ratio >= 2.0)")
print("   -> NOTE: baseline uses the SAME class_weight settings as the Phase 4")
print("      baselines. No oversampling / resampling is applied.")


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
# 6. PREPROCESSING PIPELINE (leak-free)
# ============================================================
#
# - Numeric : median imputation (safety net - no feature has missing
#             values in this dataset) -> StandardScaler
# - Categorical: most-frequent imputation -> OneHotEncoder with
#             handle_unknown='ignore' (robust to unseen categories)
#
# The transformer is fitted on training data only (it lives inside
# the pipeline), so there is no leakage.

print_header("PREPROCESSING PIPELINE")


def build_preprocessor():
    """Numeric: median imputation -> StandardScaler.
    Categorical: most-frequent imputation -> OneHotEncoder."""
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
    """Full leak-free pipeline: preprocessing -> model."""
    return Pipeline(steps=[
        ("preprocessor", build_preprocessor()),
        ("model", model),
    ])


# ============================================================
# 7. EVALUATION HELPER
# ============================================================

def evaluate_model(pipeline, X_eval, y_eval):
    """Return (metrics_dict, y_pred, y_prob) on any dataset."""
    y_pred = pipeline.predict(X_eval)
    y_prob = pipeline.predict_proba(X_eval)[:, 1]

    metrics = {
        "Accuracy": accuracy_score(y_eval, y_pred),
        "Precision": precision_score(y_eval, y_pred, zero_division=0),
        "Recall": recall_score(y_eval, y_pred, zero_division=0),
        "F1 Score": f1_score(y_eval, y_pred, zero_division=0),
        "ROC-AUC": roc_auc_score(y_eval, y_prob),
    }
    return metrics, y_pred, y_prob


# ============================================================
# 8. BASELINE MODELS (Phase 4 baseline defaults)
# ============================================================
#
# Same hyperparameters as the Phase 4 / Phase 3 baselines so the
# results are directly comparable across datasets. No tuning here -
# this is the Phase 6 baseline.

print_header("BASELINE MODELS")

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
predictions = {}
roc_data = {}

for model_name, model in baseline_models.items():
    print(f"\n🔄 Training baseline {model_name}...")

    pipeline = build_pipeline(model)
    pipeline.fit(X_train, y_train)

    metrics, y_pred, y_prob = evaluate_model(pipeline, X_test, y_test)
    baseline_rows.append({"Model": model_name, **metrics})
    predictions[model_name] = y_pred

    fpr, tpr, _ = roc_curve(y_test, y_prob)
    roc_data[model_name] = (fpr, tpr, metrics["ROC-AUC"])

    print(f"   Accuracy : {metrics['Accuracy']:.4f}")
    print(f"   Precision: {metrics['Precision']:.4f}")
    print(f"   Recall   : {metrics['Recall']:.4f}")
    print(f"   F1 Score : {metrics['F1 Score']:.4f}")
    print(f"   ROC-AUC  : {metrics['ROC-AUC']:.4f}")

baseline_df = pd.DataFrame(baseline_rows).sort_values("ROC-AUC", ascending=False)

print("\nBaseline performance (untouched test set):")
print(baseline_df.to_string(index=False))


# ============================================================
# 9. STRATIFIED 5-FOLD CROSS-VALIDATION
# ============================================================
#
# Same protocol as Phase 4/5: StratifiedKFold(5, shuffle=True,
# random_state=42) on the full dataset. The pipeline is refitted on
# each fold's training portion only (no leakage).

print_header("STRATIFIED 5-FOLD CROSS-VALIDATION")

cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)

cv_rows = []

for model_name, model in baseline_models.items():
    print(f"🔄 Cross-validating {model_name}...")

    pipeline = build_pipeline(model)

    scores = cross_validate(
        pipeline,
        X,
        y,
        cv=cv,
        scoring=["accuracy", "roc_auc"],
        n_jobs=1,
    )

    cv_rows.append({
        "Model": model_name,
        "CV Mean Accuracy": round(float(scores["test_accuracy"].mean()), 4),
        "CV Accuracy Std": round(float(scores["test_accuracy"].std()), 4),
        "CV Mean ROC-AUC": round(float(scores["test_roc_auc"].mean()), 4),
        "CV ROC-AUC Std": round(float(scores["test_roc_auc"].std()), 4),
    })

cv_df = pd.DataFrame(cv_rows)

print("\nCross-validation results:")
print(cv_df.to_string(index=False))


# ============================================================
# 10. OUTPUTS - GRAPHS
# ============================================================

print_header("GENERATING GRAPHS")

# ------------------------------------------------------------
# 10a. Baseline model comparison (all 5 metrics)
# ------------------------------------------------------------

melted = baseline_df.melt(
    id_vars=["Model"],
    var_name="Metric",
    value_name="Score",
)

plt.figure(figsize=(12, 6))
sns.barplot(data=melted, x="Model", y="Score", hue="Metric")
plt.ylim(0, 1)
plt.title("PlacePro Phase 6 - Baseline Model Comparison")
plt.xlabel("Model")
plt.ylabel("Score")
plt.legend(title="Metric", bbox_to_anchor=(1.02, 1), loc="upper left")
plt.tight_layout()
plt.savefig(f"{OUTPUT_DIR}/phase6_baseline_model_comparison.png", dpi=300)
plt.close()
print("✅ outputs/phase6_baseline_model_comparison.png saved")

# ------------------------------------------------------------
# 10b. ROC curves for baseline models
# ------------------------------------------------------------

plt.figure(figsize=(9, 7))

for model_name, (fpr, tpr, auc_value) in roc_data.items():
    plt.plot(fpr, tpr, label=f"{model_name} (AUC={auc_value:.3f})")

plt.plot([0, 1], [0, 1], linestyle="--", color="gray")
plt.xlabel("False Positive Rate")
plt.ylabel("True Positive Rate")
plt.title("PlacePro Phase 6 - Baseline ROC Curves")
plt.legend(loc="lower right")
plt.tight_layout()
plt.savefig(f"{OUTPUT_DIR}/phase6_baseline_roc_curves.png", dpi=300)
plt.close()
print("✅ outputs/phase6_baseline_roc_curves.png saved")

# ------------------------------------------------------------
# 10c. Confusion matrices for baseline models
# ------------------------------------------------------------

fig, axes = plt.subplots(1, len(baseline_models), figsize=(18, 5))

for ax, (model_name, y_pred) in zip(axes, predictions.items()):
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

plt.suptitle("PlacePro Phase 6 - Baseline Confusion Matrices")
plt.tight_layout()
plt.savefig(f"{OUTPUT_DIR}/phase6_baseline_confusion_matrix.png", dpi=300)
plt.close()
print("✅ outputs/phase6_baseline_confusion_matrix.png saved")


# ============================================================
# 11. RESULTS - FILES
# ============================================================

print_header("SAVING RESULTS")

# ------------------------------------------------------------
# 11a. results/phase6_baseline_model_comparison.csv
# ------------------------------------------------------------

baseline_df.to_csv(f"{RESULTS_DIR}/phase6_baseline_model_comparison.csv", index=False)
print("✅ results/phase6_baseline_model_comparison.csv saved")

# ------------------------------------------------------------
# 11b. results/phase6_baseline_cv_results.csv
# ------------------------------------------------------------

cv_df.to_csv(f"{RESULTS_DIR}/phase6_baseline_cv_results.csv", index=False)
print("✅ results/phase6_baseline_cv_results.csv saved")

# ------------------------------------------------------------
# 11c. results/phase6_baseline_summary.txt
# ------------------------------------------------------------

best_model_row = baseline_df.iloc[0]

with open(f"{RESULTS_DIR}/phase6_baseline_summary.txt", "w", encoding="utf-8") as file:
    file.write("PLACEPRO PHASE 6 - BASELINE SUMMARY\n")
    file.write("===================================\n\n")

    file.write("DATASET\n")
    file.write("-------\n")
    file.write(f"Source       : {DATA_PATH}\n")
    file.write(f"Rows         : {len(df):,}\n")
    file.write(f"Columns      : {len(df.columns)} (after removing leakage columns)\n")
    file.write(f"Duplicates   : 0\n")
    file.write(f"Missing      : none in features (salary_package_lpa removed)\n")
    file.write(f"Target       : placement_status (0 = Not Placed, 1 = Placed)\n")
    file.write(f"Class ratio  : {imbalance_ratio:.3f} (majority/minority)\n\n")

    file.write("TRAIN / TEST SPLIT\n")
    file.write("------------------\n")
    file.write(f"Test size    : 0.20 (stratified, random_state={RANDOM_STATE})\n")
    file.write(f"Train rows   : {len(X_train):,}\n")
    file.write(f"Test rows    : {len(X_test):,}\n\n")

    file.write("BASELINE MODELS (test set, sorted by ROC-AUC)\n")
    file.write("----------------------------------------------\n")
    file.write(baseline_df.to_string(index=False))
    file.write("\n\n")

    file.write("STRATIFIED 5-FOLD CROSS-VALIDATION\n")
    file.write("----------------------------------\n")
    file.write(cv_df.to_string(index=False))
    file.write("\n\n")

    file.write("BEST BASELINE (by ROC-AUC)\n")
    file.write("---------------------------\n")
    file.write(f"Model    : {best_model_row['Model']}\n")
    file.write(f"Accuracy : {best_model_row['Accuracy']:.4f}\n")
    file.write(f"Precision: {best_model_row['Precision']:.4f}\n")
    file.write(f"Recall   : {best_model_row['Recall']:.4f}\n")
    file.write(f"F1 Score : {best_model_row['F1 Score']:.4f}\n")
    file.write(f"ROC-AUC  : {best_model_row['ROC-AUC']:.4f}\n\n")

    file.write("NOTES\n")
    file.write("-----\n")
    file.write("- Baseline only: NO hyperparameter tuning was performed.\n")
    file.write("- salary_package_lpa was removed (post-placement leakage).\n")
    file.write("- No oversampling or target manipulation was applied.\n")
    file.write("- 'Always predict majority' would score ~"
               f"{max(placed_count, not_placed_count) / total * 100:.1f}% accuracy,\n")
    file.write("  so accuracy alone is a weak yardstick on this dataset.\n")

print("✅ results/phase6_baseline_summary.txt saved")


# ============================================================
# 12. FINAL SUMMARY
# ============================================================

print_header("PHASE 6 BASELINE COMPLETED")

print("=" * 70)
print("PLACEPRO - PHASE 6: DATASET BASELINE - SUMMARY")
print("=" * 70)

print("\n--- BASELINE MODELS (test set) ---")
print(baseline_df.to_string(index=False))

print("\n--- STRATIFIED 5-FOLD CROSS-VALIDATION ---")
print(cv_df.to_string(index=False))

print("\n--- BEST BASELINE (by ROC-AUC) ---")
print(f"Model    : {best_model_row['Model']}")
print(f"Accuracy : {best_model_row['Accuracy']:.4f}")
print(f"Precision: {best_model_row['Precision']:.4f}")
print(f"Recall   : {best_model_row['Recall']:.4f}")
print(f"F1 Score : {best_model_row['F1 Score']:.4f}")
print(f"ROC-AUC  : {best_model_row['ROC-AUC']:.4f}")

# ------------------------------------------------------------
# 12b. Comparison with the Phase 4 result (informational)
# ------------------------------------------------------------
# Phase 4 final model was tuned on data/placement.csv (old dataset,
# 26 columns, mild 1.2:1 imbalance). Phase 6 uses a different,
# cleaner dataset (18 columns, 2.2:1 imbalance), so the comparison
# is informational - not apples-to-apples.

phase4_file = os.path.join(RESULTS_DIR, "tuned_final_results.txt")
phase4_loaded = False

if os.path.exists(phase4_file):
    try:
        # Parse the Phase 4 FINAL MODEL block (the selected model is
        # Random Forest (Tuned), not the top-ROC-AUC tuned model).
        p4 = {}
        with open(phase4_file, encoding="utf-8") as _f:
            _text = _f.read()
        _block = _text.split("FINAL MODEL")[1].split("PREDICTION FUNCTION")[0]
        for _line in _block.splitlines():
            _line = _line.strip()
            if _line.startswith("Model"):
                p4["Model"] = _line.split(":", 1)[1].strip()
            elif _line.startswith("Accuracy"):
                p4["Accuracy"] = float(_line.split(":", 1)[1].strip())
            elif _line.startswith("Precision"):
                p4["Precision"] = float(_line.split(":", 1)[1].strip())
            elif _line.startswith("Recall"):
                p4["Recall"] = float(_line.split(":", 1)[1].strip())
            elif _line.startswith("F1 Score"):
                p4["F1 Score"] = float(_line.split(":", 1)[1].strip())
            elif _line.startswith("ROC-AUC"):
                p4["ROC-AUC"] = float(_line.split(":", 1)[1].strip())

        print("\n--- COMPARISON: Phase 6 best baseline vs Phase 4 selected model ---")
        print(f"Phase 6 best baseline : {best_model_row['Model']} (untuned baseline)")
        print(f"Phase 4 selected model: {p4.get('Model', 'unknown')} (tuned)")
        print(f"  {'Metric':<10}{'Phase 6 (baseline)':<22}{'Phase 4 (selected)':<20}")
        for metric in ["Accuracy", "Precision", "Recall", "F1 Score", "ROC-AUC"]:
            print(f"  {metric:<10}{best_model_row[metric]:<22.4f}{p4[metric]:<20.4f}")
        print("  NOTE: different datasets (Phase 6 is cleaner, fewer features,")
        print("  stronger signal per feature). Phase 4 numbers are a tuned model;")
        print("  Phase 6 numbers are an untuned baseline - not apples-to-apples.")
        phase4_loaded = True
    except Exception as exc:  # pragma: no cover
        print(f"\n⚠️  Could not read Phase 4 comparison file: {exc}")

if not phase4_loaded:
    print("\n(Phase 4 results file not found - skipping comparison.)")

print("\n--- FILES CREATED ---")
print("Script:")
print("  phase6_dataset_baseline.py            - Phase 6 baseline pipeline (this script)")
print("Results:")
print("  results/phase6_baseline_model_comparison.csv")
print("  results/phase6_baseline_cv_results.csv")
print("  results/phase6_baseline_summary.txt")
print("Outputs:")
print("  outputs/phase6_baseline_model_comparison.png")
print("  outputs/phase6_baseline_roc_curves.png")
print("  outputs/phase6_baseline_confusion_matrix.png")

print("\n🎉 PHASE 6 BASELINE COMPLETED - PLACEPRO DATASET BASELINE DONE!")
