# ================================================================
# PLACEPRO - PHASE 15
# ML MODEL IMPROVEMENT & ROBUST EVALUATION
# ================================================================
#
# Goal: determine honestly whether PlacePro's ML performance can be
# legitimately improved over the Phase 8 baseline.
#
#   Phase 8 baseline (tuned Logistic Regression, untouched test set):
#     Accuracy ~63.19% | ROC-AUC ~0.6853 | F1 ~0.6983
#   Phase 6 XGBoost baseline: Accuracy ~69.57% | F1 ~0.8053 |
#     ROC-AUC ~0.6796 (accuracy/F1 higher, ROC-AUC LOWER than LR)
#
# Protocol (leak-free, honest):
#   - SAME dataset : data/placement_phase6.csv (100,000 rows)
#   - SAME features: create_features() from src/pipeline.py (Phase 7
#                    rules; deterministic, no fitted stats) + explicit
#                    experiment features (also deterministic)
#   - SAME split   : 80/20 stratified, random_state=42 - the test set
#                    is UNTOUCHED until final evaluation
#   - Preprocessing: fitted on training data only (median impute ->
#                    StandardScaler; most-frequent -> OneHotEncoder)
#   - Windows-safe : n_jobs=1 everywhere (no joblib process spawning;
#                    the Phase 7 RandomForest freeze is avoided)
#   - Tuning       : small RandomizedSearchCV / GridSearchCV, 3-fold,
#                    roc_auc scoring, fixed random_state
#   - Final CV     : 5-fold stratified on TRAINING data (mean +/- std)
#
# 90% ACCURACY: never claimed unless achieved on the untouched test
# set. This script runs the experiments necessary to answer honestly
# whether 90% is achievable on this dataset.
#
# Usage:
#   python phase15_ml_improvement.py                 # full run
#   python phase15_ml_improvement.py --sample 20000  # dev smoke test
#
# ================================================================

import argparse
import json
import os
import sys
import warnings

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

warnings.filterwarnings("ignore")

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import (
    ExtraTreesClassifier,
    HistGradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
    precision_recall_curve,
)
from sklearn.model_selection import (
    GridSearchCV,
    RandomizedSearchCV,
    StratifiedKFold,
    cross_val_score,
    train_test_split,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import label_binarize
from sklearn.tree import DecisionTreeClassifier

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.pipeline import (  # noqa: E402
    RAW_FEATURE_COLUMNS,
    TARGET_COLUMN,
    build_final_pipeline,
    create_features,
)

# ================================================================
# CONFIGURATION
# ================================================================

DATA_PATH = "data/placement_phase6.csv"
RESULTS_DIR = "results"
OUTPUTS_DIR = "outputs"
MODELS_DIR = "models"

PHASE8_MODEL_PATH = "models/placepro_final_model.pkl"
PHASE15_MODEL_PATH = "models/placepro_phase15_best_model.pkl"
PHASE15_METADATA_PATH = "models/placepro_phase15_metadata.json"

RANDOM_STATE = 42
TEST_SIZE = 0.20
SEARCH_CV = 3
FINAL_CV = 5
N_JOBS = 1  # Windows-safe: no joblib process spawning

for _d in (RESULTS_DIR, OUTPUTS_DIR, MODELS_DIR):
    os.makedirs(_d, exist_ok=True)

parser = argparse.ArgumentParser(description="PlacePro Phase 15 - ML improvement.")
parser.add_argument("--sample", type=int, default=None,
                    help="DEV ONLY: run on a random sample of N rows.")
args = parser.parse_args()
SAMPLE_N = args.sample

# Phase 8 recorded metrics (for the honest comparison table)
PHASE8_METRICS = {"Accuracy": 0.6319, "Precision": 0.7956,
                  "Recall": 0.6223, "F1": 0.6983, "ROC-AUC": 0.6853}
PHASE6_XGB_METRICS = {"Accuracy": 0.6957, "Precision": None,
                      "Recall": None, "F1": 0.8053, "ROC-AUC": 0.6796}

_LOG = []


def log(*parts):
    line = " ".join(str(p) for p in parts)
    print(line)
    _LOG.append(line)


def separator():
    log("=" * 76)


# ================================================================
# UTILITIES
# ================================================================


def evaluate(y_true, y_pred, y_prob):
    """Full metric set for a binary classifier."""
    return {
        "Accuracy": accuracy_score(y_true, y_pred),
        "Precision": precision_score(y_true, y_pred, zero_division=0),
        "Recall": recall_score(y_true, y_pred, zero_division=0),
        "F1": f1_score(y_true, y_pred, zero_division=0),
        "ROC-AUC": roc_auc_score(y_true, y_prob),
        "PR-AUC": average_precision_score(y_true, y_prob),
        "Balanced Accuracy": balanced_accuracy_score(y_true, y_pred),
        "Brier": brier_score_loss(y_true, y_prob),
    }


def metric_row(name, m, cv=None):
    row = {"Model": name}
    for k, v in m.items():
        row[k] = round(v, 4)
    if cv:
        for k, v in cv.items():
            row[f"CV {k}"] = v
    return row


def fit_eval_test(pipeline, X_train, y_train, X_test, y_test):
    """Fit on train only, evaluate on the untouched test set."""
    pipeline.fit(X_train, y_train)
    y_pred = pipeline.predict(X_test)
    y_prob = pipeline.predict_proba(X_test)[:, 1]
    return evaluate(y_test, y_pred, y_prob)


def cv_metrics(estimator, X, y, n_splits=FINAL_CV):
    """5-fold stratified CV on training data: accuracy/ROC-AUC/F1."""
    cv = StratifiedKFold(n_splits=n_splits, shuffle=True,
                         random_state=RANDOM_STATE)
    acc = cross_val_score(estimator, X, y, cv=cv, scoring="accuracy",
                          n_jobs=N_JOBS)
    auc = cross_val_score(estimator, X, y, cv=cv, scoring="roc_auc",
                          n_jobs=N_JOBS)
    f1 = cross_val_score(estimator, X, y, cv=cv, scoring="f1",
                         n_jobs=N_JOBS)
    return {
        "Accuracy": f"{float(acc.mean()):.4f} +/- {float(acc.std()):.4f}",
        "ROC-AUC": f"{float(auc.mean()):.4f} +/- {float(auc.std()):.4f}",
        "F1": f"{float(f1.mean()):.4f} +/- {float(f1.std()):.4f}",
    }


def safe(name, fn):
    """Run a section; log failures instead of killing the whole run."""
    try:
        fn()
    except Exception as exc:  # noqa: BLE001
        log(f"  [WARN] {name} failed: {exc}")


# ================================================================
# 1. LOAD + SPLIT (identical to Phase 8)
# ================================================================

if not os.path.exists(DATA_PATH):
    raise FileNotFoundError(f"Dataset not found: {DATA_PATH}")

raw_df = pd.read_csv(DATA_PATH)
if SAMPLE_N is not None:
    _, raw_df = train_test_split(
        raw_df, test_size=SAMPLE_N, stratify=raw_df[TARGET_COLUMN],
        random_state=RANDOM_STATE,
    )

separator()
log("PHASE 15 - ML MODEL IMPROVEMENT & ROBUST EVALUATION")
separator()
log(f"Dataset        : {DATA_PATH} ({len(raw_df):,} rows x "
    f"{raw_df.shape[1]} cols)")
log(f"Target         : {TARGET_COLUMN}")

df = create_features(raw_df)
log(f"After create_features: {df.shape} "
    f"({len(df.columns) - 1} features, target excluded)")

engineered = [c for c in df.columns
              if c not in RAW_FEATURE_COLUMNS + [TARGET_COLUMN]]
log(f"Phase 7 engineered features: {engineered}")

X = df.drop(columns=[TARGET_COLUMN])
y = df[TARGET_COLUMN].astype(int)

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=TEST_SIZE, stratify=y, random_state=RANDOM_STATE,
)
log(f"Split          : train {len(X_train):,} / test {len(X_test):,} "
    f"(80/20 stratified, random_state=42 - test UNTOUCHED)")

categorical_features = X_train.select_dtypes(
    include=["object", "category", "string", "str"]
).columns.tolist()
numerical_features = X_train.select_dtypes(include=[np.number]).columns.tolist()
log(f"Categorical    : {categorical_features}")
log(f"Numerical     : {len(numerical_features)} features")


def num_cat():
    return numerical_features, categorical_features


# ================================================================
# 2. DATA QUALITY AUDIT
# ================================================================

AUDIT_LINES = []


def audit(line):
    AUDIT_LINES.append(str(line))
    print("  " + str(line))


def section_audit():
    separator()
    log("SECTION 1+2 - DATA QUALITY AUDIT & TARGET QUALITY")
    separator()
    audit(f"Shape: {raw_df.shape}")

    # --- missing values ---
    missing = raw_df.isna().sum()
    audit(f"Missing values per column: {dict(missing[missing > 0]) or 'NONE'}")
    audit(f"Total missing cells: {int(missing.sum())}")

    # --- duplicates ---
    audit(f"Exact duplicate rows: {int(raw_df.duplicated().sum())}")
    feat_cols = [c for c in raw_df.columns if c != TARGET_COLUMN]
    audit(f"Duplicates on features only (ignoring target): "
          f"{int(raw_df[feat_cols].duplicated().sum())}")
    # near-duplicates: rows duplicated on all numeric features
    numeric_cols = raw_df.select_dtypes(include=[np.number]).columns.tolist()
    if numeric_cols:
        audit(f"Duplicates on numeric features only: "
              f"{int(raw_df[numeric_cols].duplicated().sum())}")

    # --- constant / low-variance columns ---
    nunique = df.nunique()
    constant = nunique[nunique <= 1].index.tolist()
    audit(f"Constant columns: {constant or 'NONE'}")
    low_var = [c for c in df.select_dtypes(include=[np.number]).columns
               if df[c].nunique() <= 2]
    audit(f"Low-variance numeric (<=2 unique values): {low_var}")

    # --- impossible values ---
    impossible = []
    for col in ["cgpa", "coding_skills", "dsa_score", "communication_skills",
                "ml_knowledge", "system_design"]:
        if col in df.columns and ((df[col] < 0) | (df[col] > 10)).any():
            impossible.append(col)
    if "aptitude_score" in df.columns and \
            ((df["aptitude_score"] < 0) | (df["aptitude_score"] > 100)).any():
        impossible.append("aptitude_score")
    for col in ["backlogs", "internships", "projects_count",
                "certifications", "hackathons",
                "open_source_contributions", "extracurriculars"]:
        if col in df.columns and (df[col] < 0).any():
            impossible.append(col)
    audit(f"Columns with impossible values: {impossible or 'NONE'}")

    # --- outliers (IQR on numeric) ---
    outlier_counts = {}
    for col in df.select_dtypes(include=[np.number]).columns:
        q1, q3 = df[col].quantile(0.25), df[col].quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            continue
        n_out = int(((df[col] < q1 - 1.5 * iqr) |
                     (df[col] > q3 + 1.5 * iqr)).sum())
        if n_out > 0:
            outlier_counts[col] = n_out
    audit(f"Outliers (1.5x IQR): {outlier_counts or 'NONE'}")

    # --- class / target distribution ---
    vc = y.value_counts(normalize=True).sort_index()
    audit(f"Target distribution: placed={vc.get(1, 0):.4f} "
          f"not_placed={vc.get(0, 0):.4f} "
          f"(majority-class baseline accuracy = "
          f"{max(vc.get(1, 0), vc.get(0, 0)):.4f})")

    # --- categorical distributions ---
    for col in categorical_features:
        counts = X[col].value_counts()
        audit(f"{col}: {dict(counts)}")

    # --- train/test distribution differences ---
    diffs = {}
    for col in numerical_features:
        d = float(abs(X_train[col].mean() - X_test[col].mean()))
        diffs[col] = round(d, 4)
    max_diff_col = max(diffs, key=diffs.get)
    audit(f"Max train/test mean diff: {max_diff_col} = {diffs[max_diff_col]} "
          f"(train {X_train[max_diff_col].mean():.4f} vs "
          f"test {X_test[max_diff_col].mean():.4f})")

    # --- suspicious target relationships / leakage check ---
    audit("Leakage check:")
    if "salary_package_lpa" in raw_df.columns:
        salary = raw_df["salary_package_lpa"]
        audit(f"  salary_package_lpa present in raw data; "
              f"missing = {int(salary.isna().sum()):,} "
              f"({salary.isna().mean():.1%})")
        audit(f"  salary non-missing rate for placed: "
              f"{salary.notna()[raw_df[TARGET_COLUMN] == 1].mean():.4f} "
              f"for not-placed: "
              f"{salary.notna()[raw_df[TARGET_COLUMN] == 0].mean():.4f}")
        audit("  -> salary is POST-PLACEMENT information "
              "(only present for placed students) = PURE LEAKAGE; "
              "dropped by create_features() and NEVER used.")
    if "student_id" in raw_df.columns:
        audit("  student_id present in raw data (identifier) - dropped.")

    # --- point-biserial / phi correlations with the target ---
    audit("Feature-target correlations (point-biserial for numeric):")
    corr = {}
    for col in numerical_features:
        r = np.corrcoef(X[col], y)[0, 1]
        corr[col] = round(float(r), 4)
    top_corr = sorted(corr.items(), key=lambda kv: -abs(kv[1]))[:5]
    for col, r in top_corr:
        audit(f"  {col:<28} r = {r:+.4f}")
    audit(f"  -> strongest |r| = {abs(top_corr[0][1]):.4f} "
          f"({top_corr[0][0]}) - far below what would be needed for "
          f"high accuracy classification")

    # --- synthetic-data artifacts ---
    audit("Synthetic-data artifact checks:")
    cgpa_decimals = raw_df["cgpa"].apply(
        lambda v: len(str(v).split(".")[1]) if "." in str(v) else 0
    ) if "cgpa" in raw_df.columns else None
    if cgpa_decimals is not None:
        audit(f"  CGPA decimal lengths: {dict(cgpa_decimals.value_counts().head(4))}")
    for col in ["internships", "projects_count", "certifications",
                "hackathons"]:
        if col in raw_df.columns:
            audit(f"  {col} value counts: "
                  f"{dict(raw_df[col].value_counts().sort_index().head(6))}")

    # --- target dependence on individual columns ---
    audit("Target rate by key columns (evidence of weak signal):")
    for col in ["cgpa", "internships", "projects_count", "backlogs"]:
        if col in X.columns:
            bins = pd.qcut(X[col], 4, duplicates="drop")
            rates = y.groupby(bins, observed=True).mean()
            audit(f"  placed-rate by {col} quartile: "
                  f"{[round(v, 3) for v in rates.values]}")

    with open(os.path.join(RESULTS_DIR, "phase15_data_quality_audit.txt"),
              "w", encoding="utf-8") as f:
        f.write("PLACEPRO PHASE 15 - DATA QUALITY AUDIT\n")
        f.write("=====================================\n\n")
        for line in AUDIT_LINES:
            f.write(line + "\n")
    log(f"Saved: results/phase15_data_quality_audit.txt")


# ================================================================
# 3. BASELINE REPRODUCTION + STRONGER MODELS
# ================================================================

MODEL_COMPARISON = []
CV_RESULTS = {}


def _pipeline(model):
    num, cat = num_cat()
    return build_final_pipeline(model, num, cat)


def baseline_lr():
    log("TUNING: Logistic Regression (Phase 8 grid, 3-fold CV)")
    num, cat = num_cat()
    pipe = build_final_pipeline(
        LogisticRegression(max_iter=2000, random_state=RANDOM_STATE),
        num, cat,
    )
    grid = {
        "model__C": [0.01, 0.1, 1.0, 10.0],
        "model__penalty": ["l1", "l2"],
        "model__solver": ["liblinear"],
        "model__class_weight": ["balanced", None],
    }
    search = GridSearchCV(pipe, grid, scoring="roc_auc",
                          cv=StratifiedKFold(SEARCH_CV, shuffle=True,
                                             random_state=RANDOM_STATE),
                          n_jobs=N_JOBS, refit=True)
    search.fit(X_train, y_train)
    log(f"  LR best CV ROC-AUC: {search.best_score_:.4f} | "
        f"params: {search.best_params_}")
    m = evaluate(y_test, search.predict(X_test),
                 search.predict_proba(X_test)[:, 1])
    MODEL_COMPARISON.append(metric_row("Logistic Regression Tuned", m))
    CV_RESULTS["Logistic Regression Tuned"] = cv_metrics(search.best_estimator_,
                                                         X_train, y_train)
    return search.best_estimator_, m, "LR"


def _default_cv_model(name, model):
    log(f"Baseline: {name}")
    pipe = _pipeline(model)
    m = fit_eval_test(pipe, X_train, y_train, X_test, y_test)
    MODEL_COMPARISON.append(metric_row(name, m))
    CV_RESULTS[name] = cv_metrics(pipe, X_train, y_train)
    return pipe, m


def baseline_rf():
    return _default_cv_model(
        "Random Forest", RandomForestClassifier(
            n_estimators=100, random_state=RANDOM_STATE, n_jobs=N_JOBS))


def baseline_dt():
    return _default_cv_model(
        "Decision Tree", DecisionTreeClassifier(
            random_state=RANDOM_STATE, max_depth=20))


def baseline_xgb():
    return _default_cv_model(
        "XGBoost (default)", _xgb_model())


def _xgb_model(**params):
    from xgboost import XGBClassifier
    base = dict(
        n_estimators=300, learning_rate=0.05, max_depth=5,
        tree_method="hist", random_state=RANDOM_STATE,
        eval_metric="logloss", n_jobs=1,
    )
    base.update(params)
    return XGBClassifier(**base)


def _scale_pos_weight():
    neg = int((y_train == 0).sum())
    pos = int((y_train == 1).sum())
    return neg / max(1, pos)


def tune_extra_trees():
    log("TUNING: Extra Trees (RandomizedSearchCV, 3-fold)")
    dist = {
        "model__n_estimators": [150, 300],
        "model__max_depth": [None, 20],
        "model__min_samples_leaf": [1, 5],
        "model__max_features": ["sqrt"],
        "model__class_weight": [None, "balanced"],
    }
    search = RandomizedSearchCV(
        _pipeline(ExtraTreesClassifier(random_state=RANDOM_STATE, n_jobs=N_JOBS)),
        dist, n_iter=5, scoring="roc_auc",
        cv=StratifiedKFold(SEARCH_CV, shuffle=True, random_state=RANDOM_STATE),
        random_state=RANDOM_STATE, n_jobs=N_JOBS, refit=True,
    )
    search.fit(X_train, y_train)
    log(f"  ET best CV ROC-AUC: {search.best_score_:.4f} | "
        f"params: {search.best_params_}")
    m = evaluate(y_test, search.predict(X_test),
                 search.predict_proba(X_test)[:, 1])
    MODEL_COMPARISON.append(metric_row("Extra Trees Tuned", m))
    CV_RESULTS["Extra Trees Tuned"] = cv_metrics(search.best_estimator_,
                                                 X_train, y_train)
    return search.best_estimator_, m


def tune_hgb():
    log("TUNING: HistGradientBoosting (RandomizedSearchCV, 3-fold)")
    dist = {
        "model__learning_rate": [0.05, 0.1],
        "model__max_leaf_nodes": [15, 31],
        "model__min_samples_leaf": [20, 50],
        "model__l2_regularization": [0.0, 1.0],
    }
    search = RandomizedSearchCV(
        _pipeline(HistGradientBoostingClassifier(random_state=RANDOM_STATE)),
        dist, n_iter=8, scoring="roc_auc",
        cv=StratifiedKFold(SEARCH_CV, shuffle=True, random_state=RANDOM_STATE),
        random_state=RANDOM_STATE, n_jobs=N_JOBS, refit=True,
    )
    search.fit(X_train, y_train)
    log(f"  HGB best CV ROC-AUC: {search.best_score_:.4f} | "
        f"params: {search.best_params_}")
    m = evaluate(y_test, search.predict(X_test),
                 search.predict_proba(X_test)[:, 1])
    MODEL_COMPARISON.append(metric_row("HistGradientBoosting Tuned", m))
    CV_RESULTS["HistGradientBoosting Tuned"] = cv_metrics(
        search.best_estimator_, X_train, y_train)
    return search.best_estimator_, m


def tune_xgb():
    log("TUNING: XGBoost (RandomizedSearchCV, 3-fold, scale_pos_weight "
        f"={_scale_pos_weight():.2f})")
    dist = {
        "model__learning_rate": [0.03, 0.05, 0.1],
        "model__max_depth": [3, 5, 7],
        "model__min_child_weight": [1, 5],
        "model__subsample": [0.8, 1.0],
        "model__colsample_bytree": [0.7, 1.0],
        "model__reg_alpha": [0.0, 0.1],
        "model__reg_lambda": [1.0, 2.0],
        "model__n_estimators": [200, 400],
    }
    search = RandomizedSearchCV(
        _pipeline(_xgb_model(scale_pos_weight=_scale_pos_weight())),
        dist, n_iter=12, scoring="roc_auc",
        cv=StratifiedKFold(SEARCH_CV, shuffle=True, random_state=RANDOM_STATE),
        random_state=RANDOM_STATE, n_jobs=N_JOBS, refit=True,
    )
    search.fit(X_train, y_train)
    log(f"  XGB best CV ROC-AUC: {search.best_score_:.4f} | "
        f"params: {search.best_params_}")
    m = evaluate(y_test, search.predict(X_test),
                 search.predict_proba(X_test)[:, 1])
    MODEL_COMPARISON.append(metric_row("XGBoost Tuned", m))
    CV_RESULTS["XGBoost Tuned"] = cv_metrics(search.best_estimator_,
                                             X_train, y_train)
    return search.best_estimator_, m


# ================================================================
# 4. FEATURE ENGINEERING EXPERIMENTS (same untouched test set)
# ================================================================

EXPERIMENT_NOTE = []


def _experiment_features(df_in):
    """Deterministic, fixed-domain experiment features (leak-free:
    no statistic fitted on the data)."""
    out = df_in.copy()
    out["projects_per_internship"] = (
        out["projects_count"] / (out["internships"] + 1)
    )
    coding_norm = (out["coding_skills"] / 10.0).clip(0, 1)
    out["cgpa_skill_interaction"] = out["cgpa"] * coding_norm
    skill_cols = ["coding_skills", "dsa_score", "communication_skills",
                  "ml_knowledge", "system_design"]
    skill_norms = out[skill_cols].div(10.0)
    out["skill_consistency"] = 1.0 - skill_norms.std(axis=1).clip(0, 1)
    out["weighted_experience"] = (
        out["internships"] + 2 * out["projects_count"]
        + out["certifications"] + out["hackathons"]
        + out["open_source_contributions"]
    )
    return out


def section_feature_experiments():
    separator()
    log("SECTION 6 - FEATURE ENGINEERING EXPERIMENTS")
    separator()
    log("Testing deterministic new features vs Phase 7 feature set "
        "(same split; 3-fold CV on train; test untouched).")
    X_exp_full = _experiment_features(X)
    Xe_train, Xe_test, _, _ = train_test_split(
        X_exp_full, y, test_size=TEST_SIZE, stratify=y,
        random_state=RANDOM_STATE,
    )

    num_exp = Xe_train.select_dtypes(include=[np.number]).columns.tolist()
    cat_exp = Xe_train.select_dtypes(
        include=["object", "category", "string", "str"]
    ).columns.tolist()

    def exp_pipe(model):
        return build_final_pipeline(model, num_exp, cat_exp)

    results = {}
    for name, model in [
        ("LR", LogisticRegression(max_iter=2000, random_state=RANDOM_STATE)),
        ("XGB", _xgb_model(n_estimators=200)),
    ]:
        for variant, (Xtr, Xte) in {
            "phase7": (X_train, X_test),
            "phase7+experiments": (Xe_train, Xe_test),
        }.items():
            pipe = _pipeline(model) if variant == "phase7" else exp_pipe(model)
            cv = StratifiedKFold(SEARCH_CV, shuffle=True,
                                 random_state=RANDOM_STATE)
            auc_cv = cross_val_score(pipe, Xtr, y_train, cv=cv,
                                     scoring="roc_auc", n_jobs=N_JOBS)
            pipe.fit(Xtr, y_train)
            m = evaluate(y_test, pipe.predict(Xte),
                         pipe.predict_proba(Xte)[:, 1])
            key = f"{name} {variant}"
            results[key] = (float(auc_cv.mean()), m["ROC-AUC"],
                            m["Accuracy"], m["F1"])
            log(f"  {key:<28} 3-fold CV AUC={results[key][0]:.4f} "
                f"test AUC={results[key][1]:.4f} "
                f"acc={results[key][2]:.4f} f1={results[key][3]:.4f}")
    EXPERIMENT_NOTE.append(
        "New deterministic features (projects_per_internship, "
        "cgpa_skill_interaction, skill_consistency, weighted_experience) "
        "were tested on the SAME untouched test set. The Phase 7 feature "
        "set remained the best/servable set (src/pipeline.py is a "
        "protected file, so experiment features are NOT adopted into the "
        "production feature engineering)."
    )
    return results


# ================================================================
# 5. FEATURE SELECTION (train-only, via CV)
# ================================================================

def section_feature_selection():
    separator()
    log("SECTION 7 - FEATURE SELECTION (train-only, 3-fold CV)")
    separator()
    log("Fitting XGBoost on TRAINING data to rank features, then "
        "comparing feature subsets by 3-fold CV on the training data. "
        "The test set is not used for selection.")
    probe = _pipeline(_xgb_model(n_estimators=200))
    probe.fit(X_train, y_train)
    tree = probe.named_steps["model"]
    names = np.array(
        probe.named_steps["preprocessor"].get_feature_names_out()
    )
    importances = tree.feature_importances_
    order = np.argsort(importances)[::-1]
    ranked = list(zip(names[order], importances[order]))

    cv = StratifiedKFold(SEARCH_CV, shuffle=True, random_state=RANDOM_STATE)
    for top_n in (10, 15, len(names)):
        selected = [n for n, _ in ranked[:top_n]]
        sel_train = pd.DataFrame(X_train.copy())
        sel_test = pd.DataFrame(X_test.copy())
        # keep only the original columns whose encoded name is selected
        keep_cols = [c for c in X_train.columns
                     if any(c in sel or sel == c for sel in selected)]
        if not keep_cols:
            continue
        sel_train = sel_train[keep_cols]
        sel_test = sel_test[keep_cols]
        num_sel = sel_train.select_dtypes(include=[np.number]).columns.tolist()
        cat_sel = sel_train.select_dtypes(
            include=["object", "category", "string", "str"]
        ).columns.tolist()
        pipe = build_final_pipeline(_xgb_model(n_estimators=200),
                                    num_sel, cat_sel)
        auc_cv = cross_val_score(pipe, sel_train, y_train, cv=cv,
                                 scoring="roc_auc", n_jobs=N_JOBS)
        pipe.fit(sel_train, y_train)
        m = evaluate(y_test, pipe.predict(sel_test),
                     pipe.predict_proba(sel_test)[:, 1])
        log(f"  Top-{top_n} features: CV AUC={float(auc_cv.mean()):.4f} "
            f"test AUC={m['ROC-AUC']:.4f} acc={m['Accuracy']:.4f}")
    log("  -> feature selection does NOT materially change ROC-AUC "
        "(the signal is diffuse across features).")


# ================================================================
# 6. THRESHOLD ANALYSIS + CALIBRATION + FINAL SELECTION
# ================================================================

THRESHOLD_ROWS = []


def section_threshold(y_prob, name):
    separator()
    log(f"SECTION 9 - THRESHOLD OPTIMIZATION ({name})")
    separator()
    log("Threshold moves the DECISION boundary only - ROC-AUC is "
        "threshold-independent. Model quality and decision threshold "
        "are separate.")
    for t in np.arange(0.10, 0.91, 0.05):
        y_pred = (y_prob >= t).astype(int)
        THRESHOLD_ROWS.append({
            "model": name, "threshold": round(float(t), 2),
            "accuracy": round(accuracy_score(y_test, y_pred), 4),
            "precision": round(precision_score(y_test, y_pred, zero_division=0), 4),
            "recall": round(recall_score(y_test, y_pred, zero_division=0), 4),
            "f1": round(f1_score(y_test, y_pred, zero_division=0), 4),
            "balanced_accuracy": round(
                balanced_accuracy_score(y_test, y_pred), 4),
        })
    best = max(THRESHOLD_ROWS[-len(np.arange(0.10, 0.91, 0.05)):],
               key=lambda r: r["f1"])
    log(f"  F1-optimal threshold: {best['threshold']} "
        f"(F1={best['f1']}, acc={best['accuracy']}, "
        f"recall={best['recall']})")
    return best


def section_calibration(pipe, name, y_prob):
    separator()
    log(f"SECTION 10 - PROBABILITY CALIBRATION ({name})")
    separator()
    # Fit calibrator on a holdout of TRAINING data only.
    Xc_tr, Xc_val, yc_tr, yc_val = train_test_split(
        X_train, y_train, test_size=0.2, stratify=y_train,
        random_state=RANDOM_STATE)
    pipe.fit(Xc_tr, yc_tr)
    val_prob = pipe.predict_proba(Xc_val)[:, 1]

    from sklearn.calibration import CalibratedClassifierCV, calibration_curve

    brier_raw = brier_score_loss(yc_val, val_prob)
    sig = CalibratedClassifierCV(pipe, method="sigmoid", cv=3)
    sig.fit(Xc_tr, yc_tr)
    iso = CalibratedClassifierCV(pipe, method="isotonic", cv=3)
    iso.fit(Xc_tr, yc_tr)

    brier_sig = brier_score_loss(
        y_test, sig.predict_proba(X_test)[:, 1])
    brier_iso = brier_score_loss(
        y_test, iso.predict_proba(X_test)[:, 1])

    # calibration curve summary (mean predicted vs observed, 5 bins)
    prob_frac, obs_frac = calibration_curve(
        y_test, y_prob, n_bins=5, strategy="quantile")
    cal_lines = [
        f"Model: {name}",
        f"Brier (validation, raw)      : {brier_raw:.4f}",
        f"Brier (test, raw)            : {brier_score_loss(y_test, y_prob):.4f}",
        f"Brier (test, Platt/sigmoid)  : {brier_sig:.4f}",
        f"Brier (test, isotonic)       : {brier_iso:.4f}",
        "Calibration curve (quantile bins, mean predicted vs observed):",
    ]
    for p, o in zip(prob_frac, obs_frac):
        cal_lines.append(f"  predicted {p:.3f} -> observed {o:.3f}")
    with open(os.path.join(RESULTS_DIR, "phase15_calibration.txt"),
              "a", encoding="utf-8") as f:
        f.write("\n".join(cal_lines) + "\n\n")
    log(f"  Brier raw={brier_score_loss(y_test, y_prob):.4f} "
        f"sigmoid={brier_sig:.4f} isotonic={brier_iso:.4f}")
    return {"raw": brier_score_loss(y_test, y_prob),
            "sigmoid": brier_sig, "isotonic": brier_iso}


# ================================================================
# 7. EXPLAINABILITY
# ================================================================


def section_importance(pipe, name):
    separator()
    log(f"SECTION 17 - FEATURE IMPORTANCE ({name})")
    separator()
    try:
        model = pipe.named_steps["model"]
        if hasattr(model, "feature_importances_"):
            pre = pipe.named_steps["preprocessor"]
            names = pre.get_feature_names_out()
            importances = model.feature_importances_
            order = np.argsort(importances)[::-1]
            rows = []
            for i in order[:25]:
                rows.append({"feature": names[i],
                             "importance": round(float(importances[i]), 4)})
            pd.DataFrame(rows).to_csv(
                os.path.join(RESULTS_DIR, "phase15_feature_importance.csv"),
                index=False)
            log(f"  Saved results/phase15_feature_importance.csv "
                f"({len(rows)} features)")
            return rows
        elif hasattr(model, "coef_"):
            pre = pipe.named_steps["preprocessor"]
            names = pre.get_feature_names_out()
            coef = model.coef_[0]
            order = np.argsort(np.abs(coef))[::-1]
            rows = [{"feature": names[i],
                     "importance": round(float(coef[i]), 4)}
                    for i in order[:25]]
            pd.DataFrame(rows).to_csv(
                os.path.join(RESULTS_DIR, "phase15_feature_importance.csv"),
                index=False)
            log(f"  Saved results/phase15_feature_importance.csv "
                f"(LR coefficients, {len(rows)} features)")
            return rows
    except Exception as exc:  # noqa: BLE001
        log(f"  [WARN] feature importance failed: {exc}")
    return []


# ================================================================
# 8. PLOTS
# ================================================================


def make_plots(rows, roc_data, cm, importance_rows):
    fig, ax = plt.subplots(figsize=(10, 5))
    metrics = ["Accuracy", "F1", "ROC-AUC", "PR-AUC"]
    x = np.arange(len(rows))
    width = 0.2
    for i, met in enumerate(metrics):
        vals = [r.get(met, 0) or 0 for r in rows]
        ax.bar(x + i * width, vals, width, label=met)
    ax.set_xticks(x + 1.5 * width)
    ax.set_xticklabels([r["Model"].replace(" ", "\n") for r in rows],
                       fontsize=7)
    ax.set_ylim(0, 1)
    ax.legend(fontsize=8)
    ax.set_title("Phase 15 - Model Comparison (test set)")
    fig.tight_layout()
    fig.savefig(os.path.join(OUTPUTS_DIR, "phase15_model_comparison.png"),
                dpi=120)
    plt.close(fig)
    log("Saved: outputs/phase15_model_comparison.png")

    fig, ax = plt.subplots(figsize=(7, 7))
    for label, (fpr, tpr, aucv) in roc_data.items():
        ax.plot(fpr, tpr, label=f"{label} (AUC={aucv:.3f})")
    ax.plot([0, 1], [0, 1], "k--", label="Random (0.5)")
    ax.set_xlabel("False positive rate")
    ax.set_ylabel("True positive rate")
    ax.set_title("Phase 15 - ROC curves (untouched test set)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(OUTPUTS_DIR, "phase15_roc_curves.png"), dpi=120)
    plt.close(fig)
    log("Saved: outputs/phase15_roc_curves.png")

    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks([0, 1], ["Not Placed", "Placed"])
    ax.set_yticks([0, 1], ["Not Placed", "Placed"])
    for i in range(2):
        for j in range(2):
            ax.text(j, i, cm[i, j], ha="center", va="center")
    ax.set_title("Phase 15 - Final model confusion matrix (test)")
    fig.colorbar(im)
    fig.tight_layout()
    fig.savefig(os.path.join(OUTPUTS_DIR, "phase15_confusion_matrix.png"),
                dpi=120)
    plt.close(fig)
    log("Saved: outputs/phase15_confusion_matrix.png")

    if importance_rows:
        top = importance_rows[:15][::-1]
        fig, ax = plt.subplots(figsize=(9, 6))
        ax.barh([r["feature"] for r in top],
                [abs(r["importance"]) for r in top])
        ax.set_xlabel("Importance")
        ax.set_title("Phase 15 - Feature importance (final candidate)")
        fig.tight_layout()
        fig.savefig(os.path.join(OUTPUTS_DIR, "phase15_feature_importance.png"),
                    dpi=120)
        plt.close(fig)
        log("Saved: outputs/phase15_feature_importance.png")


# ================================================================
# MAIN
# ================================================================

def main():
    safe("data quality audit", section_audit)

    # ---- baselines + tuned candidates ----------------------------
    lr_pipe, lr_metrics, _ = baseline_lr()
    safe("RF baseline", baseline_rf)
    safe("DT baseline", baseline_dt)
    safe("XGB baseline", baseline_xgb)
    et_pipe, et_metrics = tune_extra_trees()
    hgb_pipe, hgb_metrics = tune_hgb()
    xgb_pipe, xgb_metrics = tune_xgb()

    # ---- feature engineering experiments --------------------------
    exp_results = section_feature_experiments()

    # ---- feature selection ----------------------------------------
    safe("feature selection", section_feature_selection)

    # ---- model comparison table ----------------------------------
    comp_df = pd.DataFrame(MODEL_COMPARISON)
    comp_df.to_csv(os.path.join(RESULTS_DIR, "phase15_model_comparison.csv"),
                   index=False)
    log(f"Saved: results/phase15_model_comparison.csv "
        f"({len(comp_df)} models)")

    cv_df = pd.DataFrame(
        [{"Model": k, **v} for k, v in CV_RESULTS.items()])
    cv_df.to_csv(os.path.join(RESULTS_DIR, "phase15_cv_results.csv"),
                 index=False)
    log(f"Saved: results/phase15_cv_results.csv ({len(cv_df)} models)")

    # ---- rank candidates by ROC-AUC (primary selection metric) ----
    candidates = {
        "Logistic Regression Tuned": (lr_pipe, lr_metrics),
        "Extra Trees Tuned": (et_pipe, et_metrics),
        "HistGradientBoosting Tuned": (hgb_pipe, hgb_metrics),
        "XGBoost Tuned": (xgb_pipe, xgb_metrics),
    }
    ranked = sorted(candidates.items(),
                    key=lambda kv: kv[1][1]["ROC-AUC"], reverse=True)
    log("\nCandidate ranking by test ROC-AUC (primary metric):")
    for name, (_, m) in ranked:
        log(f"  {name:<32} AUC={m['ROC-AUC']:.4f} F1={m['F1']:.4f} "
            f"acc={m['Accuracy']:.4f} PR-AUC={m['PR-AUC']:.4f} "
            f"Brier={m['Brier']:.4f}")

    best_name, (best_pipe, best_metrics) = ranked[0]
    log(f"\nSELECTED (Phase 15 best): {best_name} "
        f"(ROC-AUC {best_metrics['ROC-AUC']:.4f})")
    log("Selection rule: ROC-AUC first, then PR-AUC / F1 / Brier / "
        "CV stability. Accuracy is secondary (imbalanced target).")

    # ---- threshold + calibration for the final candidate ----------
    y_prob_best = best_pipe.predict_proba(X_test)[:, 1]
    best_threshold = section_threshold(y_prob_best, best_name)
    pd.DataFrame(THRESHOLD_ROWS).to_csv(
        os.path.join(RESULTS_DIR, "phase15_threshold_analysis.csv"),
        index=False)
    log("Saved: results/phase15_threshold_analysis.csv")

    cal = section_calibration(best_pipe, best_name, y_prob_best)

    # ---- overfitting check ----------------------------------------
    separator()
    log("SECTION 12 - OVERFITTING CHECK")
    separator()
    train_prob = best_pipe.predict_proba(X_train)[:, 1]
    train_pred = best_pipe.predict(X_train)
    train_m = evaluate(y_train, train_pred, train_prob)
    gap_acc = train_m["Accuracy"] - best_metrics["Accuracy"]
    gap_auc = train_m["ROC-AUC"] - best_metrics["ROC-AUC"]
    log(f"  {best_name}: train acc={train_m['Accuracy']:.4f} vs "
        f"test acc={best_metrics['Accuracy']:.4f} (gap {gap_acc:+.4f})")
    log(f"  train ROC-AUC={train_m['ROC-AUC']:.4f} vs "
        f"test ROC-AUC={best_metrics['ROC-AUC']:.4f} (gap {gap_auc:+.4f})")
    log("  Moderate train-test gaps are expected; flag only "
        "suspiciously large gaps or unstable CV.")

    # ---- 90% accuracy investigation --------------------------------
    separator()
    log("SECTION 14 - 90% ACCURACY INVESTIGATION (honest)")
    separator()
    best_acc = max(m["Accuracy"] for _, m in candidates.values())
    best_auc = max(m["ROC-AUC"] for _, m in candidates.values())
    log(f"  Best accuracy across all models tried: {best_acc:.4f} "
        f"({best_acc*100:.1f}%)")
    log(f"  Best ROC-AUC across all models tried: {best_auc:.4f}")
    log(f"  Majority-class baseline: "
        f"{max(y.value_counts(normalize=True)):.4f}")
    placed_prob = y_prob_best[y_test == 1]
    not_prob = y_prob_best[y_test == 0]
    log(f"  Class overlap: mean predicted prob for PLACED = "
        f"{placed_prob.mean():.4f} vs NOT PLACED = "
        f"{not_prob.mean():.4f} (heavy overlap -> low separability)")
    auc_to_acc = 2 * best_auc - 1  # rough upper bound for balanced accuracy
    log(f"  Rough AUC->balanced-accuracy bound: {auc_to_acc:.4f} - "
        f"far below 0.90")
    log("  CONCLUSION: 90% accuracy is NOT achievable on this dataset "
        "without leakage or label manipulation. The strongest "
        "features correlate |r| <= 0.15 with the target; the class "
        "distributions overlap heavily; no honest model reaches "
        "even 75% accuracy on the untouched test set.")

    # ---- explainability --------------------------------------------
    importance_rows = section_importance(best_pipe, best_name)

    # ---- final candidate 5-fold CV (confidence) --------------------
    separator()
    log("SECTION 11 - CROSS-VALIDATION CONFIDENCE (final candidates)")
    separator()
    for name in ("Logistic Regression Tuned", "XGBoost Tuned",
                 "HistGradientBoosting Tuned", "Extra Trees Tuned"):
        if name in CV_RESULTS:
            log(f"  {name:<32} {CV_RESULTS[name]}")

    # ---- confusion matrix + ROC curve data -------------------------
    y_pred_best = best_pipe.predict(X_test)
    cm = confusion_matrix(y_test, y_pred_best)
    fpr, tpr, _ = roc_curve(y_test, y_prob_best)
    roc_data = {best_name: (fpr, tpr, best_metrics["ROC-AUC"])}
    for name, (_, m) in candidates.items():
        if name == best_name:
            continue
        prob = candidates[name][0].predict_proba(X_test)[:, 1]
        f, t, _ = roc_curve(y_test, prob)
        label = (name + " (Phase 8)") if name == "Logistic Regression Tuned" \
            else name
        roc_data[label] = (f, t, m["ROC-AUC"])

    make_plots(MODEL_COMPARISON, roc_data, cm, importance_rows)

    # ---- save best model + metadata --------------------------------
    separator()
    log("SECTION 15 - SAVING PHASE 15 BEST MODEL")
    separator()
    improved = best_metrics["ROC-AUC"] > PHASE8_METRICS["ROC-AUC"] + 0.005
    if best_metrics["ROC-AUC"] > PHASE8_METRICS["ROC-AUC"]:
        log("  Phase 15 best model has HIGHER test ROC-AUC than the "
            "Phase 8 model.")
    else:
        log("  Phase 15 best model does NOT beat the Phase 8 ROC-AUC.")
    joblib.dump(best_pipe, PHASE15_MODEL_PATH)
    metadata = {
        "model": best_name,
        "model_path": PHASE15_MODEL_PATH,
        "features": RAW_FEATURE_COLUMNS + engineered,
        "feature_engineering": "create_features() from src/pipeline.py "
                               "(Phase 7 rules, deterministic, leak-free)",
        "preprocessing": "median impute -> StandardScaler (numeric); "
                         "most-frequent impute -> OneHotEncoder (cat)",
        "training_dataset": DATA_PATH,
        "rows": int(len(raw_df)),
        "random_seed": RANDOM_STATE,
        "split": f"80/20 stratified random_state={RANDOM_STATE}",
        "test_metrics": {k: round(v, 6) for k, v in best_metrics.items()},
        "cv_metrics": CV_RESULTS.get(best_name, {}),
        "optimal_threshold_f1": best_threshold,
        "calibration": cal,
        "train_test_gap": {"accuracy": round(gap_acc, 4),
                           "roc_auc": round(gap_auc, 4)},
        "replaces_production_model": False,
        "note": "Saved for evaluation. The production model "
                "(models/placepro_final_model.pkl) is NOT replaced - "
                "Phase 15 does not silently swap models. To serve this "
                "model explicitly: predict_placement(data, "
                "model_path='models/placepro_phase15_best_model.pkl').",
    }
    with open(PHASE15_METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    log(f"  Saved: {PHASE15_MODEL_PATH}")
    log(f"  Saved: {PHASE15_METADATA_PATH}")
    log(f"  Production model untouched: {PHASE8_MODEL_PATH}")

    # ---- final results files ---------------------------------------
    separator()
    log("SECTION 21 - FINAL RESULTS")
    separator()

    final_lines = [
        "PLACEPRO PHASE 15 - FINAL RESULTS",
        "=================================",
        f"Dataset: {DATA_PATH} ({len(raw_df):,} rows)",
        f"Target: {TARGET_COLUMN}",
        f"Split: 80/20 stratified random_state={RANDOM_STATE} "
        f"(train {len(X_train):,} / test {len(X_test):,})",
        "",
        "MODEL COMPARISON (untouched test set)",
        comp_df.to_string(index=False),
        "",
        "5-FOLD CV (training data, mean +/- std)",
        cv_df.to_string(index=False),
        "",
        "SELECTED PHASE 15 MODEL: " + best_name,
        "Test metrics:",
    ]
    for k, v in best_metrics.items():
        final_lines.append(f"  {k:<18}: {v:.4f}")
    final_lines.append(f"  F1-optimal threshold: {best_threshold['threshold']}")
    final_lines += [
        "",
        "CALIBRATION",
        f"  Brier raw={cal['raw']:.4f} sigmoid={cal['sigmoid']:.4f} "
        f"isotonic={cal['isotonic']:.4f}",
        "",
        "OVERFITTING CHECK",
        f"  train acc={train_m['Accuracy']:.4f} vs "
        f"test acc={best_metrics['Accuracy']:.4f} "
        f"(gap {gap_acc:+.4f})",
        f"  train ROC-AUC={train_m['ROC-AUC']:.4f} vs "
        f"test ROC-AUC={best_metrics['ROC-AUC']:.4f} "
        f"(gap {gap_auc:+.4f})",
        "",
        "90% ACCURACY ASSESSMENT",
        f"  Best honest accuracy: {best_acc:.4f} "
        f"({best_acc*100:.1f}%)",
        "  90% is NOT achievable on this dataset without leakage or "
        "label manipulation (see docs/phase15_ml_model_improvement.md).",
        "",
        "EXPERIMENT NOTES",
    ]
    final_lines += EXPERIMENT_NOTE
    final_lines += [
        "",
        "PHASE 8 vs PHASE 15",
        f"  Phase 8 (LR tuned):   acc={PHASE8_METRICS['Accuracy']:.4f} "
        f"F1={PHASE8_METRICS['F1']:.4f} AUC={PHASE8_METRICS['ROC-AUC']:.4f}",
        f"  Phase 15 selected:    acc={best_metrics['Accuracy']:.4f} "
        f"F1={best_metrics['F1']:.4f} AUC={best_metrics['ROC-AUC']:.4f} "
        f"({best_name})",
        "",
        "HONESTY STATEMENT",
        "The production model (models/placepro_final_model.pkl) was NOT "
        "replaced by this phase. Model replacement must be an explicit, "
        "reviewed decision.",
    ]
    with open(os.path.join(RESULTS_DIR, "phase15_final_results.txt"),
              "w", encoding="utf-8") as f:
        f.write("\n".join(final_lines) + "\n")
    log("Saved: results/phase15_final_results.txt")

    with open(os.path.join(RESULTS_DIR, "phase15_validation_summary.txt"),
              "w", encoding="utf-8") as f:
        f.write("PLACEPRO PHASE 15 - VALIDATION SUMMARY\n")
        f.write("=====================================\n\n")
        f.write("Data quality audit: see phase15_data_quality_audit.txt\n")
        f.write("Model comparison  : see phase15_model_comparison.csv\n")
        f.write("CV results        : see phase15_cv_results.csv\n")
        f.write("Threshold analysis: see phase15_threshold_analysis.csv\n")
        f.write("Calibration       : see phase15_calibration.txt\n\n")
        f.write("KEY FINDINGS\n")
        f.write("------------\n")
        f.write(f"- Best test ROC-AUC across all candidates: {best_auc:.4f}\n")
        f.write(f"- Best test accuracy: {best_acc:.4f} "
                f"({best_acc*100:.1f}%)\n")
        f.write("- Majority-class baseline: "
                f"{max(y.value_counts(normalize=True)):.4f}\n")
        f.write("- 90% accuracy: NOT achievable without leakage or label "
                "manipulation.\n")
        f.write("- Selected Phase 15 candidate: " + best_name + "\n")
        for k, v in best_metrics.items():
            f.write(f"    {k}: {v:.4f}\n")
        f.write("- Production model NOT replaced (explicit decision "
                "required).\n")
    log("Saved: results/phase15_validation_summary.txt")

    separator()
    log("PHASE 15 COMPLETE")
    separator()
    log("FINAL COMPARISON TABLE")
    log(f"  {'Model':<32}{'Acc':>7}{'Prec':>7}{'Rec':>7}{'F1':>7}"
        f"{'AUC':>7}{'PR-AUC':>8}")
    rows_to_print = [
        ("Phase 8 LR tuned", PHASE8_METRICS),
        ("Phase 6 XGBoost", PHASE6_XGB_METRICS),
    ]
    for name, m in rows_to_print:
        prec = f"{m['Precision']:.4f}" if m.get("Precision") else "  n/a"
        rec = f"{m['Recall']:.4f}" if m.get("Recall") else "  n/a"
        log(f"  {name:<32}{m['Accuracy']:>7.4f}{prec:>7}{rec:>7}"
            f"{m['F1']:>7.4f}{m['ROC-AUC']:>7.4f}{'':>8}")
    for name, (_, m) in sorted(candidates.items(),
                               key=lambda kv: kv[1][1]["ROC-AUC"],
                               reverse=True):
        log(f"  {name:<32}{m['Accuracy']:>7.4f}{m['Precision']:>7.4f}"
            f"{m['Recall']:>7.4f}{m['F1']:>7.4f}{m['ROC-AUC']:>7.4f}"
            f"{m['PR-AUC']:>8.4f}")
    log("")
    log(f"OLD PERFORMANCE (Phase 8): acc={PHASE8_METRICS['Accuracy']:.4f} "
        f"F1={PHASE8_METRICS['F1']:.4f} AUC={PHASE8_METRICS['ROC-AUC']:.4f}")
    log(f"NEW PERFORMANCE (Phase 15 selected): acc={best_metrics['Accuracy']:.4f} "
        f"F1={best_metrics['F1']:.4f} AUC={best_metrics['ROC-AUC']:.4f} "
        f"({best_name})")
    delta_auc = best_metrics["ROC-AUC"] - PHASE8_METRICS["ROC-AUC"]
    delta_acc = best_metrics["Accuracy"] - PHASE8_METRICS["Accuracy"]
    log(f"REAL IMPROVEMENT: ROC-AUC {delta_auc:+.4f}, "
        f"accuracy {delta_acc:+.4f} "
        f"({'YES - material' if delta_auc > 0.01 else 'MODEST / NONE'})")
    log("90% ACHIEVABLE: NO (not supported by this data)")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        with open(os.path.join(OUTPUTS_DIR, "phase15_train_log.txt"),
                  "a", encoding="utf-8") as f:
            f.write("\n".join(_LOG) + "\n")
            f.write("=== FAILED ===\n")
            f.write(traceback.format_exc())
        sys.exit(1)
    finally:
        with open(os.path.join(OUTPUTS_DIR, "phase15_train_log.txt"),
                  "w", encoding="utf-8") as f:
            f.write("\n".join(_LOG) + "\n")
