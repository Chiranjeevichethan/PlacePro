# ================================================================
# PLACEPRO - PHASE 7
# FEATURE ENGINEERING + MODEL TUNING
# ================================================================
#
# Dataset : data/placement_phase6.csv (100,000 rows, 18 columns)
# Target  : placement_status (1 = Placed, 0 = Not Placed)
#
# LEAKAGE SAFETY
#   - salary_package_lpa is a POST-PLACEMENT variable -> NEVER used.
#   - All engineered features are deterministic row-level transforms
#     (fixed domain scales like aptitude/100, skills/10). No statistic
#     is fitted on the full dataset before the split, so the Phase 4
#     "academic_skill_index fitted on full data" class of leak cannot
#     recur.
#   - Every fitted transformer (imputer, scaler, encoder, model) is
#     trained inside the Pipeline / CV folds on TRAINING data only.
#
# PERFORMANCE DESIGN (Windows + Python 3.13, 100k rows)
#   - RandomizedSearchCV / GridSearchCV run with n_jobs=1 -> NO joblib
#     process spawning (the #1 cause of freezes on Windows).
#   - XGBoost uses tree_method="hist" and its internal OpenMP threads.
#   - Random Forest is NOT tuned (Phase 6 showed RF search is slow and
#     gains little); it stays a default engineered baseline.
#   - Hyperparameter searches are deliberately small and practical.
#
# USAGE
#   python phase7_model_tuning.py                # full pipeline
#   python phase7_model_tuning.py --sample 20000 # quick dev smoke test
#
# ================================================================

import os
import sys
import warnings

# Force UTF-8 console output (Windows defaults to cp1252 and can crash
# on some characters).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")  # headless plotting (no GUI freeze on Windows)
import matplotlib.pyplot as plt

from sklearn.model_selection import (
    train_test_split,
    StratifiedKFold,
    GridSearchCV,
    RandomizedSearchCV,
    cross_val_score,
)
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    roc_curve,
    classification_report,
    confusion_matrix,
)

from scipy.stats import loguniform, randint, uniform

try:
    from xgboost import XGBClassifier
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False


# ================================================================
# CONFIGURATION
# ================================================================

DATA_PATH = "data/placement_phase6.csv"

RESULTS_DIR = "results"
OUTPUTS_DIR = "outputs"

os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(OUTPUTS_DIR, exist_ok=True)

RANDOM_STATE = 42
TEST_SIZE = 0.20

# Keep search processes single-threaded for Windows stability.
SEARCH_N_JOBS = 1

# Cross-validation: 3-fold inside the searches, 5-fold for final CV.
SEARCH_CV_FOLDS = 3
FINAL_CV_FOLDS = 5

# Search sizes (deliberately small for 100k rows).
N_ITER_LR = 16      # full grid: 4 C x 2 penalty x 2 class_weight
N_ITER_XGB = 10     # randomized draws

# Parse optional --sample flag (dev smoke test only).
SAMPLE = None
if "--sample" in sys.argv:
    idx = sys.argv.index("--sample")
    SAMPLE = int(sys.argv[idx + 1])
    print(f"[DEV MODE] Using only {SAMPLE} rows for a smoke test.\n")


# ================================================================
# HELPERS
# ================================================================

def separator():
    print("=" * 72)


def evaluate_model(name, model, X_test, y_test):
    """Evaluate a fitted model on the untouched test set."""
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    metrics = {
        "Model": name,
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

    report = classification_report(
        y_test, y_pred,
        target_names=["Not Placed", "Placed"],
        zero_division=0,
    )

    return metrics, y_pred, y_prob, report


def cross_validate_model(model, X_train, y_train, n_splits=FINAL_CV_FOLDS):
    """5-fold stratified CV (accuracy + ROC-AUC) on training data."""
    cv = StratifiedKFold(
        n_splits=n_splits, shuffle=True, random_state=RANDOM_STATE
    )
    acc = cross_val_score(
        model, X_train, y_train, cv=cv, scoring="accuracy", n_jobs=SEARCH_N_JOBS
    )
    auc = cross_val_score(
        model, X_train, y_train, cv=cv, scoring="roc_auc", n_jobs=SEARCH_N_JOBS
    )
    return acc.mean(), acc.std(), auc.mean(), auc.std()


# ================================================================
# FEATURE ENGINEERING (deterministic, leak-free)
# ================================================================
#
# Only fixed-domain transforms are used here:
#   aptitude_score  : 0-100
#   cgpa, skills    : 0-10
#   counts          : internships, projects_count, certifications,
#                     hackathons, open_source_contributions
# Nothing is fitted on the data, so engineering can safely run before
# the split without leaking.

def create_features(df):
    df = df.copy()

    # ---- Drop post-placement / ID leakage columns -----------------
    for col in ["salary_package_lpa", "student_id"]:
        if col in df.columns:
            df = df.drop(columns=[col])
            print(f"[FE] Removed leakage column: {col}")

    # ---- Normalized skill components (fixed scales) ---------------
    def norm01(s, hi):
        return (df[s] / hi).clip(0, 1) if s in df.columns else None

    coding = norm01("coding_skills", 10)
    dsa = norm01("dsa_score", 10)
    aptitude = norm01("aptitude_score", 100)
    comm = norm01("communication_skills", 10)
    ml = norm01("ml_knowledge", 10)
    sysd = norm01("system_design", 10)

    def mean_of(cols):
        present = [c for c in cols if c is not None]
        if not present:
            return None
        return pd.concat(present, axis=1).mean(axis=1)

    # 1. Overall skill score (all six skills, aptitude on 0-100 scale)
    overall = mean_of([coding, dsa, aptitude, comm, ml, sysd])
    if overall is not None:
        df["overall_skill_score"] = overall

    # 2. Academic skill index (academics + aptitude + DSA)
    academic = mean_of(
        [norm01("cgpa", 10), aptitude, dsa, coding]
    )
    if academic is not None:
        df["academic_skill_index"] = academic

    # 3. Experience score (log-scaled count features)
    exp_cols = [
        "internships", "projects_count", "certifications",
        "hackathons", "open_source_contributions",
    ]
    present_exp = [c for c in exp_cols if c in df.columns]
    if present_exp:
        df["experience_score"] = (
            np.log1p(df[present_exp]).mean(axis=1)
        )

    # 4. High CGPA indicator
    if "cgpa" in df.columns:
        df["high_cgpa"] = (df["cgpa"] >= 7.5).astype(int)

    # 5. Has internship indicator
    if "internships" in df.columns:
        df["has_internship"] = (df["internships"] >= 1).astype(int)

    # 6. Project level (0 / 1-2 / 3-4 / 5+ projects)
    if "projects_count" in df.columns:
        df["project_level"] = np.digitize(
            df["projects_count"], bins=[1, 3, 5]
        )

    # 7. Coding x experience interaction
    if coding is not None and "internships" in df.columns:
        df["coding_experience_interaction"] = (
            df["coding_skills"] * (df["internships"] + 1)
        )

    # 8. CGPA x projects interaction
    if "cgpa" in df.columns and "projects_count" in df.columns:
        df["cgpa_projects_interaction"] = (
            df["cgpa"] * (df["projects_count"] + 1)
        )

    # 9. Backlog risk indicator
    if "backlogs" in df.columns:
        df["backlog_risk"] = (df["backlogs"] >= 1).astype(int)

    # 10. Strong candidate indicator
    if all(
        c in df.columns
        for c in ["cgpa", "coding_skills", "internships"]
    ):
        df["strong_candidate_indicator"] = (
            (df["cgpa"] >= 7.5)
            & (df["coding_skills"] >= 6)
            & (df["internships"] >= 1)
        ).astype(int)

    return df


# ================================================================
# LOAD DATA
# ================================================================

separator()
print("PLACEPRO PHASE 7 - FEATURE ENGINEERING + MODEL TUNING")
separator()

if not os.path.exists(DATA_PATH):
    raise FileNotFoundError(
        f"Dataset not found: {DATA_PATH}\n"
        "Make sure data/placement_phase6.csv exists."
    )

df = pd.read_csv(DATA_PATH)

if SAMPLE is not None:
    # Stratified subsample for smoke tests ONLY.
    _, df = train_test_split(
        df, test_size=SAMPLE, stratify=df["placement_status"],
        random_state=RANDOM_STATE,
    )

print(f"\nLoaded dataset: {DATA_PATH}")
print(f"Shape: {df.shape}")

if "placement_status" not in df.columns:
    raise ValueError("Target column 'placement_status' not found.")


# ================================================================
# APPLY FEATURE ENGINEERING
# ================================================================

df = create_features(df)

base_cols = [
    "placement_status", "branch", "college_tier", "cgpa",
    "backlogs", "coding_skills", "dsa_score", "aptitude_score",
    "communication_skills", "ml_knowledge", "system_design",
    "internships", "projects_count", "certifications",
    "hackathons", "open_source_contributions", "extracurriculars",
]
engineered_cols = [c for c in df.columns if c not in base_cols]
print(f"\nShape after feature engineering: {df.shape}")
print(f"Engineered features added: {engineered_cols}")


# ================================================================
# TARGET + SPLIT
# ================================================================

X = df.drop(columns=["placement_status"])
y = df["placement_status"].astype(int)

X_train, X_test, y_train, y_test = train_test_split(
    X, y,
    test_size=TEST_SIZE,
    stratify=y,
    random_state=RANDOM_STATE,
)

print(f"\nTraining rows : {len(X_train):,}")
print(f"Testing rows  : {len(X_test):,}")
print(f"Test set class ratio (1/0): "
      f"{(y_test == 1).sum():,} / {(y_test == 0).sum():,}")


# ================================================================
# FEATURE TYPES + PREPROCESSOR
# ================================================================

categorical_features = X_train.select_dtypes(
    include=["object", "category"]
).columns.tolist()

numerical_features = X_train.select_dtypes(
    include=[np.number]
).columns.tolist()

print(f"\nCategorical features: {categorical_features}")
print(f"Numerical features: {len(numerical_features)}")

numeric_transformer = Pipeline([
    ("imputer", SimpleImputer(strategy="median")),
    ("scaler", StandardScaler()),
])

categorical_transformer = Pipeline([
    ("imputer", SimpleImputer(strategy="most_frequent")),
    ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
])

preprocessor = ColumnTransformer(
    transformers=[
        ("num", numeric_transformer, numerical_features),
        ("cat", categorical_transformer, categorical_features),
    ],
    remainder="drop",
)

cv_search = StratifiedKFold(
    n_splits=SEARCH_CV_FOLDS, shuffle=True, random_state=RANDOM_STATE
)


# ================================================================
# PHASE 6 BASELINE RESULTS (loaded for comparison)
# ================================================================

phase6_comparison_path = os.path.join(
    RESULTS_DIR, "phase6_baseline_model_comparison.csv"
)
phase6_cv_path = os.path.join(
    RESULTS_DIR, "phase6_baseline_cv_results.csv"
)

phase6_rows = []
phase6_cv = {}

if os.path.exists(phase6_comparison_path):
    p6 = pd.read_csv(phase6_comparison_path)
    phase6_cv_df = (
        pd.read_csv(phase6_cv_path)
        if os.path.exists(phase6_cv_path) else None
    )
    if phase6_cv_df is not None:
        phase6_cv = dict(zip(
            phase6_cv_df["Model"],
            zip(
                phase6_cv_df["CV Mean Accuracy"],
                phase6_cv_df["CV Mean ROC-AUC"],
            ),
        ))

    for _, row in p6.iterrows():
        cv_acc, cv_auc = phase6_cv.get(row["Model"], (np.nan, np.nan))
        phase6_rows.append({
            "Model": f"{row['Model']} (Phase 6)",
            "Tier": "Phase 6 Baseline",
            "Accuracy": row["Accuracy"],
            "Precision": row["Precision"],
            "Recall": row["Recall"],
            "F1": row["F1 Score"],
            "ROC-AUC": row["ROC-AUC"],
            "CV Accuracy": cv_acc,
            "CV ROC-AUC": cv_auc,
        })
    print(f"\nLoaded {len(phase6_rows)} Phase 6 baseline rows "
          f"from {phase6_comparison_path}")
else:
    print("\n[WARN] Phase 6 comparison CSV not found - "
          "skipping baseline comparison.")


# ================================================================
# STORAGE
# ================================================================

all_rows = list(phase6_rows)
model_dict = {}      # name -> fitted estimator (Phase 7 models)
prob_dict = {}       # name -> test probabilities (for ROC plot)
pred_dict = {}       # name -> test predictions
best_report = None
best_model_name = None


def register(name, tier, metrics, estimator, y_prob, y_pred, report,
             cv_acc=None, cv_auc=None):
    metrics_row = {
        "Model": name,
        "Tier": tier,
        "Accuracy": metrics["Accuracy"],
        "Precision": metrics["Precision"],
        "Recall": metrics["Recall"],
        "F1": metrics["F1"],
        "ROC-AUC": metrics["ROC-AUC"],
        "CV Accuracy": cv_acc,
        "CV ROC-AUC": cv_auc,
    }
    all_rows.append(metrics_row)
    model_dict[name] = estimator
    prob_dict[name] = y_prob
    pred_dict[name] = y_pred
    if report is not None:
        global best_report, best_model_name
        best_report = report
        best_model_name = name


# ================================================================
# 1. PHASE 7 ENGINEERED BASELINES (default hyperparameters)
# ================================================================

print()
separator()
print("PHASE 7 ENGINEERED BASELINES (defaults, engineered features)")
separator()

# ---- 1a. Logistic Regression (defaults) -------------------------
print("\n[1a] Logistic Regression (engineered, default)...")
lr_default = Pipeline([
    ("preprocessor", preprocessor),
    ("model", LogisticRegression(
        class_weight="balanced", max_iter=2000, random_state=RANDOM_STATE
    )),
])
lr_default.fit(X_train, y_train)
m, p, prob, rep = evaluate_model(
    "Logistic Regression (Phase 7)", lr_default, X_test, y_test
)
register("Logistic Regression (Phase 7)", "Phase 7 Engineered",
         m, lr_default, prob, p, rep)

# ---- 1b. Random Forest (defaults) -------------------------------
print("\n[1b] Random Forest (engineered, default)...")
rf_default = Pipeline([
    ("preprocessor", preprocessor),
    ("model", RandomForestClassifier(
        class_weight="balanced", random_state=RANDOM_STATE, n_jobs=1
    )),
])
rf_default.fit(X_train, y_train)
m, p, prob, rep = evaluate_model(
    "Random Forest (Phase 7)", rf_default, X_test, y_test
)
register("Random Forest (Phase 7)", "Phase 7 Engineered",
         m, rf_default, prob, p, rep)

# ---- 1c. XGBoost (defaults) -------------------------------------
if XGBOOST_AVAILABLE:
    print("\n[1c] XGBoost (engineered, default)...")
    xgb_default = Pipeline([
        ("preprocessor", preprocessor),
        ("model", XGBClassifier(
            objective="binary:logistic",
            eval_metric="logloss",
            tree_method="hist",
            random_state=RANDOM_STATE,
            n_jobs=4,
        )),
    ])
    xgb_default.fit(X_train, y_train)
    m, p, prob, rep = evaluate_model(
        "XGBoost (Phase 7)", xgb_default, X_test, y_test
    )
    register("XGBoost (Phase 7)", "Phase 7 Engineered",
             m, xgb_default, prob, p, rep)
else:
    print("\n[WARN] XGBoost not installed - skipping XGBoost models.")


# ================================================================
# 2. LOGISTIC REGRESSION TUNING (small grid)
# ================================================================

print()
separator()
print("TUNING: Logistic Regression (small grid, 3-fold CV)")
separator()

lr_pipeline = Pipeline([
    ("preprocessor", preprocessor),
    ("model", LogisticRegression(max_iter=2000, random_state=RANDOM_STATE)),
])

lr_params = {
    "model__C": [0.01, 0.1, 1.0, 10.0],
    "model__penalty": ["l1", "l2"],
    "model__solver": ["liblinear"],
    "model__class_weight": ["balanced", None],
}

lr_search = GridSearchCV(
    estimator=lr_pipeline,
    param_grid=lr_params,
    scoring="roc_auc",
    cv=cv_search,
    n_jobs=SEARCH_N_JOBS,
    verbose=1,
    refit=True,
)

lr_search.fit(X_train, y_train)

print(f"\nBest CV ROC-AUC: {lr_search.best_score_:.4f}")
print(f"Best params: {lr_search.best_params_}")

m, p, prob, rep = evaluate_model(
    "Logistic Regression Tuned", lr_search.best_estimator_, X_test, y_test
)

print("\n  Running 5-fold CV on tuned LR...")
cv_acc, cv_acc_std, cv_auc, cv_auc_std = cross_validate_model(
    lr_search.best_estimator_, X_train, y_train
)
print(f"  CV Accuracy: {cv_acc:.4f} +/- {cv_acc_std:.4f}")
print(f"  CV ROC-AUC : {cv_auc:.4f} +/- {cv_auc_std:.4f}")

register(
    "Logistic Regression Tuned", "Phase 7 Tuned",
    m, lr_search.best_estimator_, prob, p, rep,
    cv_acc=cv_acc, cv_auc=cv_auc,
)


# ================================================================
# 3. XGBOOST TUNING (moderate randomized search)
# ================================================================

if XGBOOST_AVAILABLE:

    print()
    separator()
    print("TUNING: XGBoost (randomized search, 3-fold CV)")
    separator()

    # scale_pos_weight from TRAINING labels only (moderate 2.17:1
    # imbalance) - lets the search decide whether to use it.
    neg = int((y_train == 0).sum())
    pos = int((y_train == 1).sum())
    spw_default = round(neg / pos, 3)
    print(f"\nTrain class counts: 1={pos:,} 0={neg:,} "
          f"(ratio {pos / neg:.2f}:1)")
    print(f"scale_pos_weight candidates include computed "
          f"{spw_default} and 1.0 (no weighting)")

    xgb_pipeline = Pipeline([
        ("preprocessor", preprocessor),
        ("model", XGBClassifier(
            objective="binary:logistic",
            eval_metric="logloss",
            tree_method="hist",
            random_state=RANDOM_STATE,
            n_jobs=4,
        )),
    ])

    xgb_params = {
        "model__n_estimators": randint(100, 301),
        "model__max_depth": randint(3, 7),
        "model__learning_rate": uniform(0.02, 0.20),
        "model__subsample": uniform(0.7, 1.0),
        "model__colsample_bytree": uniform(0.7, 1.0),
        "model__min_child_weight": randint(1, 7),
        "model__reg_alpha": loguniform(1e-3, 1.0),
        "model__reg_lambda": loguniform(1e-3, 1.0),
        "model__scale_pos_weight": [spw_default, 1.0],
    }

    xgb_search = RandomizedSearchCV(
        estimator=xgb_pipeline,
        param_distributions=xgb_params,
        n_iter=N_ITER_XGB,
        scoring="roc_auc",
        cv=cv_search,
        random_state=RANDOM_STATE,
        n_jobs=SEARCH_N_JOBS,
        verbose=1,
        refit=True,
    )

    print("\nStarting XGBoost randomized search "
          f"({N_ITER_XGB} draws x {SEARCH_CV_FOLDS} folds)...")

    xgb_search.fit(X_train, y_train)

    print(f"\nBest CV ROC-AUC: {xgb_search.best_score_:.4f}")
    print(f"Best params: {xgb_search.best_params_}")

    m, p, prob, rep = evaluate_model(
        "XGBoost Tuned", xgb_search.best_estimator_, X_test, y_test
    )

    print("\n  Running 5-fold CV on tuned XGBoost...")
    cv_acc, cv_acc_std, cv_auc, cv_auc_std = cross_validate_model(
        xgb_search.best_estimator_, X_train, y_train
    )
    print(f"  CV Accuracy: {cv_acc:.4f} +/- {cv_acc_std:.4f}")
    print(f"  CV ROC-AUC : {cv_auc:.4f} +/- {cv_auc_std:.4f}")

    register(
        "XGBoost Tuned", "Phase 7 Tuned",
        m, xgb_search.best_estimator_, prob, p, rep,
        cv_acc=cv_acc, cv_auc=cv_auc,
    )


# ================================================================
# MODEL COMPARISON TABLE
# ================================================================

print()
separator()
print("PHASE 7 MODEL COMPARISON")
separator()

comparison_df = pd.DataFrame(all_rows)

# Sort: Phase 6 baselines stay grouped; Phase 7 models by ROC-AUC.
phase6_mask = comparison_df["Tier"] == "Phase 6 Baseline"
phase7_df = comparison_df[~phase6_mask].sort_values(
    "ROC-AUC", ascending=False
)
phase6_df = comparison_df[phase6_mask]
comparison_df = pd.concat([phase7_df, phase6_df], ignore_index=True)

print(comparison_df[
    ["Model", "Tier", "Accuracy", "Precision", "Recall",
     "F1", "ROC-AUC", "CV Accuracy", "CV ROC-AUC"]
].to_string(index=False))


# ================================================================
# BEST MODEL SELECTION (Phase 7 tuned models only)
# ================================================================
#
# Primary metric : ROC-AUC (threshold-independent, ranking quality)
# Tie-breaker    : F1 (precision/recall balance)
# NOT selected on accuracy alone.

tuned_df = comparison_df[
    comparison_df["Tier"] == "Phase 7 Tuned"
].copy()

if len(tuned_df) > 0:
    tuned_df = tuned_df.sort_values(
        ["ROC-AUC", "F1"], ascending=False
    )
    best_row = tuned_df.iloc[0]
    best_model_name = best_row["Model"]
else:
    best_row = None
    best_model_name = None

if best_model_name is not None:
    print("\n" + "=" * 72)
    print(f"BEST PHASE 7 MODEL: {best_model_name}")
    print("=" * 72)
    print(f"  Test Accuracy : {best_row['Accuracy']:.4f}")
    print(f"  Test Precision: {best_row['Precision']:.4f}")
    print(f"  Test Recall   : {best_row['Recall']:.4f}")
    print(f"  Test F1       : {best_row['F1']:.4f}")
    print(f"  Test ROC-AUC  : {best_row['ROC-AUC']:.4f}")
    if not np.isnan(best_row["CV Accuracy"]):
        print(f"  5-fold CV Acc : {best_row['CV Accuracy']:.4f}")
    if not np.isnan(best_row["CV ROC-AUC"]):
        print(f"  5-fold CV AUC : {best_row['CV ROC-AUC']:.4f}")


# ================================================================
# THRESHOLD ANALYSIS (best model only)
# ================================================================

print()
separator()
print("THRESHOLD ANALYSIS (best model - analysis only)")
separator()

threshold_rows = []

if best_model_name is not None and best_model_name in prob_dict:
    y_prob_best = prob_dict[best_model_name]

    for thr in [0.30, 0.40, 0.50, 0.60, 0.70]:
        y_pred_thr = (y_prob_best >= thr).astype(int)
        threshold_rows.append({
            "Threshold": thr,
            "Precision": precision_score(y_test, y_pred_thr, zero_division=0),
            "Recall": recall_score(y_test, y_pred_thr, zero_division=0),
            "F1": f1_score(y_test, y_pred_thr, zero_division=0),
            "Accuracy": accuracy_score(y_test, y_pred_thr),
        })

    threshold_df = pd.DataFrame(threshold_rows)
    print(threshold_df.to_string(index=False))

    # Find the F1-optimal threshold over a fine grid (analysis only).
    best_thr, best_f1 = 0.50, 0.0
    for t in np.arange(0.20, 0.85, 0.01):
        f1t = f1_score(
            y_test, (y_prob_best >= t).astype(int), zero_division=0
        )
        if f1t > best_f1:
            best_thr, best_f1 = t, f1t
    print(f"\nBest-F1 threshold (analysis only): {best_thr:.2f} "
          f"(F1 = {best_f1:.4f})")
    print("NOTE: production threshold stays at 0.50 - this is "
          "diagnostic only.")
else:
    threshold_df = pd.DataFrame()


# ================================================================
# FEATURE IMPORTANCE (tuned XGBoost)
# ================================================================

print()
separator()
print("FEATURE IMPORTANCE")
separator()

feature_importance_rows = []

imp_model_name = None
for candidate in ["XGBoost Tuned", "Random Forest (Phase 7)"]:
    if candidate in model_dict:
        imp_model_name = candidate
        break

if imp_model_name is not None:
    est = model_dict[imp_model_name]

    # Recover preprocessed feature names from the pipeline.
    try:
        pre = est.named_steps["preprocessor"]
        feature_names = pre.get_feature_names_out()
    except Exception:
        feature_names = None

    if hasattr(est.named_steps["model"], "feature_importances_"):
        importances = est.named_steps["model"].feature_importances_

        if feature_names is not None and len(feature_names) == len(importances):
            imp_df = pd.DataFrame({
                "feature": feature_names,
                "importance": importances,
            })
        else:
            imp_df = pd.DataFrame({
                "feature": [f"f{i}" for i in range(len(importances))],
                "importance": importances,
            })

        imp_df = imp_df.sort_values("importance", ascending=False)

        print(f"Feature importance source: {imp_model_name}")
        print(imp_df.head(15).to_string(index=False))

        # Save full feature importance (top 30).
        imp_df.head(30).to_csv(
            os.path.join(RESULTS_DIR, "phase7_feature_importance.csv"),
            index=False,
        )

        # ---- Plot top 15 -----------------------------------------
        top = imp_df.head(15).iloc[::-1]
        plt.figure(figsize=(9, 7))
        plt.barh(top["feature"], top["importance"], color="#2c7fb8")
        plt.xlabel("Importance")
        plt.title(f"Feature Importance - {imp_model_name}")
        plt.tight_layout()
        plt.savefig(
            os.path.join(OUTPUTS_DIR, "phase7_feature_importance.png"),
            dpi=150,
        )
        plt.close()
        print("Saved outputs/phase7_feature_importance.png")
    else:
        print("No feature_importances_ available.")
else:
    print("No suitable model for feature importance.")


# ================================================================
# PLOTS
# ================================================================

print()
separator()
print("GENERATING PLOTS")
separator()

# ---- 1. Model comparison bar chart ------------------------------
plot_df = comparison_df.copy()
metrics_cols = ["Accuracy", "Precision", "Recall", "F1", "ROC-AUC"]

plt.figure(figsize=(12, 6))
x_pos = np.arange(len(plot_df))
width = 0.8 / len(metrics_cols)

for i, col in enumerate(metrics_cols):
    plt.bar(
        x_pos + (i - len(metrics_cols) / 2) * width + width / 2,
        plot_df[col].astype(float),
        width,
        label=col,
    )

plt.xticks(x_pos, plot_df["Model"], rotation=40, ha="right")
plt.ylabel("Score")
plt.ylim(0, 1)
plt.legend(loc="lower right")
plt.title("Phase 7 Model Comparison")
plt.grid(axis="y", alpha=0.3)
plt.tight_layout()
plt.savefig(
    os.path.join(OUTPUTS_DIR, "phase7_model_comparison.png"), dpi=150
)
plt.close()
print("Saved outputs/phase7_model_comparison.png")

# ---- 2. ROC curves (all Phase 7 models) -------------------------
plt.figure(figsize=(8, 7))
for name, prob in prob_dict.items():
    if "Phase 6" in name:
        continue
    fpr, tpr, _ = roc_curve(y_test, prob)
    auc_val = roc_auc_score(y_test, prob)
    plt.plot(fpr, tpr, label=f"{name} (AUC={auc_val:.3f})")

plt.plot([0, 1], [0, 1], "k--", alpha=0.4, label="Random")
plt.xlabel("False Positive Rate")
plt.ylabel("True Positive Rate")
plt.title("Phase 7 ROC Curves")
plt.legend(loc="lower right")
plt.grid(alpha=0.3)
plt.tight_layout()
plt.savefig(
    os.path.join(OUTPUTS_DIR, "phase7_roc_curves.png"), dpi=150
)
plt.close()
print("Saved outputs/phase7_roc_curves.png")

# ---- 3. Confusion matrix (best model) ---------------------------
if best_model_name is not None and best_model_name in pred_dict:
    cm = confusion_matrix(y_test, pred_dict[best_model_name])

    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xticklabels(["Not Placed", "Placed"])
    ax.set_yticklabels(["Not Placed", "Placed"])
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual")

    for i in range(2):
        for j in range(2):
            ax.text(j, i, f"{cm[i, j]:,}", ha="center", va="center",
                    fontsize=14,
                    color="white" if cm[i, j] > cm.max() / 2 else "black")

    ax.set_title(f"Confusion Matrix - {best_model_name}")
    fig.colorbar(im, ax=ax)
    plt.tight_layout()
    plt.savefig(
        os.path.join(OUTPUTS_DIR, "phase7_confusion_matrix.png"), dpi=150
    )
    plt.close()
    print(f"Saved outputs/phase7_confusion_matrix.png "
          f"(model: {best_model_name})")


# ================================================================
# SAVE RESULTS
# ================================================================

print()
separator()
print("SAVING RESULTS")
separator()

# ---- 1. Model comparison CSV -------------------------------------
comparison_path = os.path.join(
    RESULTS_DIR, "phase7_model_comparison.csv"
)
comparison_df.to_csv(comparison_path, index=False)
print(f"Saved {comparison_path}")

# ---- 2. Classification report (best model) -----------------------
report_path = os.path.join(
    RESULTS_DIR, "phase7_classification_report.txt"
)
if best_report is not None:
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("PLACEPRO PHASE 7 - CLASSIFICATION REPORT\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"Best model: {best_model_name}\n\n")
        f.write(best_report)
    print(f"Saved {report_path}")
else:
    print(f"[WARN] No report to save - skipping {report_path}")

# ---- 3. Threshold analysis CSV -----------------------------------
if len(threshold_df) > 0:
    thr_path = os.path.join(RESULTS_DIR, "phase7_threshold_analysis.csv")
    threshold_df.to_csv(thr_path, index=False)
    print(f"Saved {thr_path}")

# ---- 4. Validation summary text ----------------------------------
summary_path = os.path.join(RESULTS_DIR, "phase7_validation_summary.txt")

with open(summary_path, "w", encoding="utf-8") as f:
    f.write("PLACEPRO PHASE 7 - VALIDATION SUMMARY\n")
    f.write("=" * 60 + "\n\n")

    f.write("1. DATASET\n")
    f.write(f"   File: {DATA_PATH}\n")
    f.write(f"   Rows: {len(df):,} (full dataset)\n")
    f.write(f"   Split: 80/20 stratified, random_state=42\n")
    f.write(f"   Train rows: {len(X_train):,}\n")
    f.write(f"   Test rows:  {len(X_test):,}\n\n")

    f.write("2. LEAKAGE SAFETY\n")
    f.write("   - salary_package_lpa removed (post-placement variable).\n")
    f.write("   - student_id removed if present.\n")
    f.write("   - Engineered features use FIXED domain scales "
            "(aptitude/100, skills/10, log1p counts)\n"
            "     -> no statistic fitted on the full dataset.\n")
    f.write("   - Imputer/scaler/encoder/models fitted ONLY on "
            "training folds.\n\n")

    f.write("3. FEATURE ENGINEERING ADDED\n")
    f.write("   - overall_skill_score (mean of 6 normalized skills)\n")
    f.write("   - academic_skill_index (cgpa + aptitude + DSA + coding)\n")
    f.write("   - experience_score (log1p mean of experience counts)\n")
    f.write("   - high_cgpa, has_internship, project_level\n")
    f.write("   - coding_experience_interaction, "
            "cgpa_projects_interaction\n")
    f.write("   - backlog_risk, strong_candidate_indicator\n\n")

    f.write("4. WEAK / REDUNDANT FEATURES IDENTIFIED (correlation "
            "with target)\n")
    f.write("   Very weak (|r| < 0.05): extracurriculars (-0.005), "
            "system_design (-0.002),\n"
            "   ml_knowledge (0.002), open_source_contributions "
            "(0.023), hackathons (0.033)\n")
    f.write("   Weak (|r| < 0.10): aptitude (0.045), communication "
            "(0.051), certifications (0.056)\n")
    f.write("   Strongest: cgpa (0.149), internships (0.100), "
            "coding_skills (0.088), dsa (0.087)\n")
    f.write("   NOTE: weak features were kept (regularized models "
            "handle them safely); they\n"
            "   can be dropped later with negligible impact.\n\n")

    f.write("5. MODEL COMPARISON\n")
    f.write(comparison_df[
        ["Model", "Tier", "Accuracy", "Precision", "Recall",
         "F1", "ROC-AUC", "CV Accuracy", "CV ROC-AUC"]
    ].to_string(index=False) + "\n\n")

    f.write("6. BEST MODEL (selected by ROC-AUC, tie-break F1)\n")
    if best_row is not None:
        f.write(f"   {best_model_name}\n")
        f.write(f"   Test Accuracy : {best_row['Accuracy']:.4f}\n")
        f.write(f"   Test Precision: {best_row['Precision']:.4f}\n")
        f.write(f"   Test Recall   : {best_row['Recall']:.4f}\n")
        f.write(f"   Test F1       : {best_row['F1']:.4f}\n")
        f.write(f"   Test ROC-AUC  : {best_row['ROC-AUC']:.4f}\n")
        if not np.isnan(best_row["CV Accuracy"]):
            f.write(f"   5-fold CV Acc : "
                    f"{best_row['CV Accuracy']:.4f}\n")
        if not np.isnan(best_row["CV ROC-AUC"]):
            f.write(f"   5-fold CV AUC : "
                    f"{best_row['CV ROC-AUC']:.4f}\n")
    f.write("\n")

    if len(threshold_df) > 0:
        f.write("7. THRESHOLD ANALYSIS (best model, analysis only)\n")
        f.write(threshold_df.to_string(index=False) + "\n")
        f.write(f"\n   Best-F1 threshold: {best_thr:.2f} "
                f"(F1 = {best_f1:.4f})\n")
        f.write("   Production threshold remains 0.50 - analysis only.\n\n")

    f.write("8. HONEST ASSESSMENT OF 90% ACCURACY\n")
    f.write("   90% accuracy is NOT realistically achievable with "
            "this dataset without\n")
    f.write("   leakage or label manipulation. Reasons:\n")
    f.write("   - Strongest single-feature correlation is only "
            "r = 0.149 (cgpa).\n")
    f.write("   - Classes overlap heavily: placement depends on "
            "unobserved factors\n")
    f.write("     (interview performance, company demand, timing), "
            "not in the dataset.\n")
    f.write("   - ROC-AUC plateaus around 0.68-0.69 even after "
            "feature engineering and\n")
    f.write("     tuning; accuracy is bounded by the majority class "
            "(68.5%) plus the\n")
    f.write("     small learnable signal above it.\n")
    f.write("   - An always-predict-majority baseline already scores "
            "68.5% accuracy;\n")
    f.write("     reported gains must be measured against THAT, not "
            "90%.\n\n")

    f.write("9. BACKEND DECISION GUIDE\n")
    f.write("   - Use ROC-AUC (ranking quality) as the primary "
            "model-selection metric.\n")
    f.write("   - Use F1 as the tie-breaker; tune the decision "
            "threshold on business\n")
    f.write("     priorities (false-hope vs missed placement).\n")
    f.write("   - For a recommendation system, calibrated "
            "probabilities matter more\n")
    f.write("     than raw accuracy - prefer the model with the "
            "best ROC-AUC and\n")
    f.write("     use threshold + probability outputs in the app.\n")

    f.write("\nEND OF PHASE 7 SUMMARY\n")

print(f"Saved {summary_path}")


# ================================================================
# FINAL OUTPUT
# ================================================================

print()
separator()
print("PHASE 7 COMPLETED")
separator()

if best_model_name is not None:
    print(f"\nBest Phase 7 model: {best_model_name}")
    print(f"  Test Accuracy : {best_row['Accuracy']:.4f}")
    print(f"  Test Precision: {best_row['Precision']:.4f}")
    print(f"  Test Recall   : {best_row['Recall']:.4f}")
    print(f"  Test F1       : {best_row['F1']:.4f}")
    print(f"  Test ROC-AUC  : {best_row['ROC-AUC']:.4f}")

print("\nFiles created:")
print(f"  - {comparison_path}")
print(f"  - {report_path}")
print(f"  - {os.path.join(RESULTS_DIR, 'phase7_feature_importance.csv')}")
print(f"  - {thr_path}")
print(f"  - {summary_path}")
print("  - outputs/phase7_model_comparison.png")
print("  - outputs/phase7_feature_importance.png")
print("  - outputs/phase7_roc_curves.png")
print("  - outputs/phase7_confusion_matrix.png")

print("\nDone.")
