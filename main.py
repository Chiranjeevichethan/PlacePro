# ============================================================
# PLACEPRO - INTELLIGENT STUDENT PLACEMENT PREDICTION SYSTEM
# Phase 3 - Optimized ML Pipeline
# ============================================================

import os
import warnings
import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

warnings.filterwarnings("ignore")

# ------------------------------------------------------------
# MACHINE LEARNING
# ------------------------------------------------------------

from sklearn.model_selection import (
    train_test_split,
    StratifiedKFold,
    cross_val_score,
    RandomizedSearchCV
)

from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import (
    OneHotEncoder,
    StandardScaler
)

from sklearn.impute import SimpleImputer

from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier

from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    classification_report,
    confusion_matrix,
    roc_curve
)

from sklearn.inspection import permutation_importance

from xgboost import XGBClassifier


# ============================================================
# CONFIGURATION
# ============================================================

DATA_PATH = "data/placement.csv"

OUTPUT_DIR = "outputs"
RESULTS_DIR = "results"
MODEL_DIR = "models"

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def print_header(text):
    print("\n" + "=" * 65)
    print(text)
    print("=" * 65)


# ============================================================
# 1. LOAD DATASET
# ============================================================

print_header("PLACEPRO - PLACEMENT PREDICTION SYSTEM")

if not os.path.exists(DATA_PATH):
    print("❌ Dataset not found!")
    print(f"Expected location: {DATA_PATH}")
    exit()

df = pd.read_csv(DATA_PATH)

print("\n✅ Dataset Loaded")
print("Shape:", df.shape)

print("\nColumns:")
print(df.columns.tolist())


# ============================================================
# 2. BASIC DATA ANALYSIS
# ============================================================

print_header("DATASET INFORMATION")

print("\nDataset Shape:")
print(df.shape)

print("\nMissing Values:")
print(df.isnull().sum().sum())

print("\nDuplicate Rows:")
print(df.duplicated().sum())

print("\nTarget Distribution:")
print(df["placement_status"].value_counts())


# ============================================================
# 3. REMOVE DATA LEAKAGE
# ============================================================

print_header("DATA CLEANING")

# Salary is NOT allowed as a placement predictor.
# It is a consequence of placement and creates severe leakage.

if "salary_package_lpa" in df.columns:
    df.drop("salary_package_lpa", axis=1, inplace=True)
    print("✅ Removed salary_package_lpa (data leakage)")

# Student ID has no predictive meaning.
if "student_id" in df.columns:
    df.drop("student_id", axis=1, inplace=True)
    print("✅ Removed student_id")


# ============================================================
# 4. TARGET ENCODING
# ============================================================

if "placement_status" not in df.columns:
    print("❌ placement_status column not found!")
    exit()

print("\nOriginal Target Values:")
print(df["placement_status"].value_counts())

df["placement_status"] = df["placement_status"].map({
    "Not Placed": 0,
    "Placed": 1
})

# Handle if target was already numeric
df["placement_status"] = df["placement_status"].fillna(
    pd.to_numeric(df["placement_status"], errors="coerce")
)

if df["placement_status"].isnull().any():
    print("❌ Target contains unknown values.")
    exit()

df["placement_status"] = df["placement_status"].astype(int)

print("\nEncoded Target:")
print("Not Placed → 0")
print("Placed     → 1")

print("\nTarget Distribution:")
print(df["placement_status"].value_counts())


# ============================================================
# 5. FEATURE ENGINEERING
# ============================================================

print_header("FEATURE ENGINEERING")

# ------------------------------------------------------------
# CGPA category
# ------------------------------------------------------------

if "cgpa" in df.columns:
    df["high_cgpa"] = (df["cgpa"] >= 7.5).astype(int)
    print("✅ high_cgpa created")


# ------------------------------------------------------------
# Internship indicator
# ------------------------------------------------------------

if "internships_count" in df.columns:
    df["has_internship"] = (
        df["internships_count"] > 0
    ).astype(int)

    print("✅ has_internship created")


# ------------------------------------------------------------
# Project level
# ------------------------------------------------------------

if "projects_count" in df.columns:
    df["project_level"] = pd.cut(
        df["projects_count"],
        bins=[-1, 0, 2, np.inf],
        labels=[0, 1, 2]
    ).astype(int)

    print("✅ project_level created")


# ------------------------------------------------------------
# Overall technical skill score
# ------------------------------------------------------------

skill_columns = [
    "coding_skill_score",
    "aptitude_score",
    "logical_reasoning_score",
    "communication_skill_score",
    "mock_interview_score"
]

existing_skill_columns = [
    c for c in skill_columns if c in df.columns
]

if len(existing_skill_columns) >= 2:

    df["overall_skill_score"] = (
        df[existing_skill_columns]
        .mean(axis=1)
    )

    print("✅ overall_skill_score created")


# ------------------------------------------------------------
# Experience score
# ------------------------------------------------------------

experience_columns = [
    "internships_count",
    "projects_count",
    "certifications_count",
    "hackathons_participated"
]

existing_experience_columns = [
    c for c in experience_columns if c in df.columns
]

if len(existing_experience_columns) >= 2:

    df["experience_score"] = (
        df[existing_experience_columns]
        .sum(axis=1)
    )

    print("✅ experience_score created")


# ------------------------------------------------------------
# Academic / professional score
# ------------------------------------------------------------

academic_columns = [
    "cgpa",
    "attendance_percentage",
    "coding_skill_score",
    "aptitude_score"
]

existing_academic_columns = [
    c for c in academic_columns if c in df.columns
]

if len(existing_academic_columns) >= 2:

    # Normalize each component to approximately 0-100
    temp = pd.DataFrame(index=df.index)

    for col in existing_academic_columns:

        col_min = df[col].min()
        col_max = df[col].max()

        if col_max != col_min:
            temp[col] = (
                (df[col] - col_min)
                / (col_max - col_min)
                * 100
            )
        else:
            temp[col] = 0

    df["academic_skill_index"] = temp.mean(axis=1)

    print("✅ academic_skill_index created")


print("\nTotal Features After Feature Engineering:")
print(len(df.columns) - 1)


# ============================================================
# 6. EDA
# ============================================================

print_header("EXPLORATORY DATA ANALYSIS")


# ------------------------------------------------------------
# Placement distribution
# ------------------------------------------------------------

plt.figure(figsize=(7, 5))

sns.countplot(
    x="placement_status",
    data=df
)

plt.title("Placement Distribution")
plt.xlabel("Placement Status")
plt.ylabel("Number of Students")

plt.xticks(
    [0, 1],
    ["Not Placed", "Placed"]
)

plt.tight_layout()

plt.savefig(
    f"{OUTPUT_DIR}/placement_distribution.png",
    dpi=300
)

plt.close()

print("✅ placement_distribution.png saved")


# ------------------------------------------------------------
# CGPA vs placement
# ------------------------------------------------------------

if "cgpa" in df.columns:

    plt.figure(figsize=(7, 5))

    sns.boxplot(
        x="placement_status",
        y="cgpa",
        data=df
    )

    plt.title("CGPA vs Placement")
    plt.xlabel("Placement Status")
    plt.ylabel("CGPA")

    plt.xticks(
        [0, 1],
        ["Not Placed", "Placed"]
    )

    plt.tight_layout()

    plt.savefig(
        f"{OUTPUT_DIR}/cgpa_vs_placement.png",
        dpi=300
    )

    plt.close()

    print("✅ cgpa_vs_placement.png saved")


# ------------------------------------------------------------
# Correlation heatmap
# ------------------------------------------------------------

numeric_df = df.select_dtypes(include=np.number)

plt.figure(figsize=(15, 11))

sns.heatmap(
    numeric_df.corr(),
    cmap="coolwarm",
    center=0
)

plt.title("Feature Correlation Heatmap")

plt.tight_layout()

plt.savefig(
    f"{OUTPUT_DIR}/heatmap.png",
    dpi=300
)

plt.close()

print("✅ heatmap.png saved")


# ============================================================
# 7. PREPARE X AND Y
# ============================================================

print_header("PREPARING DATA")

X = df.drop(
    columns=["placement_status"]
)

y = df["placement_status"]

print("Number of samples:", len(X))
print("Number of features:", X.shape[1])


# ============================================================
# 8. TRAIN / TEST SPLIT
# ============================================================

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42,
    stratify=y
)

print("\nTraining samples:", len(X_train))
print("Testing samples:", len(X_test))


# ============================================================
# 9. IDENTIFY FEATURE TYPES
# ============================================================

numeric_features = X_train.select_dtypes(
    include=np.number
).columns.tolist()

categorical_features = X_train.select_dtypes(
    include=["object", "category"]
).columns.tolist()

print("\nNumeric features:", len(numeric_features))
print("Categorical features:", len(categorical_features))

print("\nCategorical Columns:")
print(categorical_features)


# ============================================================
# 10. PREPROCESSING PIPELINE
# ============================================================

# Numeric:
# Missing values → median
# Scaling → StandardScaler

numeric_transformer = Pipeline(
    steps=[
        (
            "imputer",
            SimpleImputer(strategy="median")
        ),
        (
            "scaler",
            StandardScaler()
        )
    ]
)


# Categorical:
# Missing values → most frequent
# Encoding → OneHotEncoder

categorical_transformer = Pipeline(
    steps=[
        (
            "imputer",
            SimpleImputer(strategy="most_frequent")
        ),
        (
            "encoder",
            OneHotEncoder(
                handle_unknown="ignore",
                sparse_output=False
            )
        )
    ]
)


preprocessor = ColumnTransformer(
    transformers=[
        (
            "numeric",
            numeric_transformer,
            numeric_features
        ),
        (
            "categorical",
            categorical_transformer,
            categorical_features
        )
    ]
)


# ============================================================
# 11. MODELS
# ============================================================

models = {

    "Logistic Regression":
        LogisticRegression(
            max_iter=2000,
            class_weight="balanced",
            random_state=42
        ),

    "Decision Tree":
        DecisionTreeClassifier(
            max_depth=10,
            min_samples_split=20,
            min_samples_leaf=10,
            class_weight="balanced",
            random_state=42
        ),

    "Random Forest":
        RandomForestClassifier(
            n_estimators=300,
            max_depth=15,
            min_samples_split=10,
            min_samples_leaf=3,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1
        ),

    "XGBoost":
        XGBClassifier(
            n_estimators=300,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            objective="binary:logistic",
            eval_metric="logloss",
            random_state=42,
            n_jobs=-1
        )
}


# ============================================================
# 12. TRAIN MODELS
# ============================================================

print_header("MODEL TRAINING")

results = []

trained_models = {}

predictions = {}

roc_data = {}


for model_name, model in models.items():

    print(f"\n🔄 Training {model_name}...")

    pipeline = Pipeline(
        steps=[
            (
                "preprocessor",
                preprocessor
            ),
            (
                "model",
                model
            )
        ]
    )

    pipeline.fit(
        X_train,
        y_train
    )

    y_pred = pipeline.predict(X_test)

    y_prob = pipeline.predict_proba(
        X_test
    )[:, 1]

    # Metrics
    accuracy = accuracy_score(
        y_test,
        y_pred
    )

    precision = precision_score(
        y_test,
        y_pred,
        zero_division=0
    )

    recall = recall_score(
        y_test,
        y_pred,
        zero_division=0
    )

    f1 = f1_score(
        y_test,
        y_pred,
        zero_division=0
    )

    roc_auc = roc_auc_score(
        y_test,
        y_prob
    )

    results.append({
        "Model": model_name,
        "Accuracy": accuracy,
        "Precision": precision,
        "Recall": recall,
        "F1 Score": f1,
        "ROC-AUC": roc_auc
    })

    trained_models[model_name] = pipeline
    predictions[model_name] = y_pred

    fpr, tpr, _ = roc_curve(
        y_test,
        y_prob
    )

    roc_data[model_name] = (
        fpr,
        tpr,
        roc_auc
    )

    print(f"✅ {model_name} completed")
    print(f"Accuracy : {accuracy:.4f}")
    print(f"Precision: {precision:.4f}")
    print(f"Recall   : {recall:.4f}")
    print(f"F1 Score : {f1:.4f}")
    print(f"ROC-AUC  : {roc_auc:.4f}")


# ============================================================
# 13. MODEL COMPARISON
# ============================================================

print_header("MODEL COMPARISON")

results_df = pd.DataFrame(results)

results_df = results_df.sort_values(
    by="ROC-AUC",
    ascending=False
)

print(
    results_df.to_string(
        index=False
    )
)

results_df.to_csv(
    f"{RESULTS_DIR}/model_comparison.csv",
    index=False
)

print("\n✅ model_comparison.csv saved")


# ============================================================
# 14. MODEL COMPARISON GRAPH
# ============================================================

plt.figure(figsize=(10, 6))

plot_df = results_df.sort_values(
    "Accuracy",
    ascending=True
)

sns.barplot(
    data=plot_df,
    x="Accuracy",
    y="Model"
)

plt.xlim(0, 1)

plt.title(
    "PlacePro - Model Accuracy Comparison"
)

plt.xlabel("Accuracy")
plt.ylabel("Model")

plt.tight_layout()

plt.savefig(
    f"{OUTPUT_DIR}/model_comparison.png",
    dpi=300
)

plt.close()

print("✅ model_comparison.png saved")


# ============================================================
# 15. ROC CURVES
# ============================================================

plt.figure(figsize=(9, 7))

for model_name, (
    fpr,
    tpr,
    auc_value
) in roc_data.items():

    plt.plot(
        fpr,
        tpr,
        label=f"{model_name} (AUC={auc_value:.3f})"
    )

plt.plot(
    [0, 1],
    [0, 1],
    linestyle="--"
)

plt.xlabel("False Positive Rate")
plt.ylabel("True Positive Rate")

plt.title(
    "ROC Curves - PlacePro Models"
)

plt.legend()

plt.tight_layout()

plt.savefig(
    f"{OUTPUT_DIR}/roc_curves.png",
    dpi=300
)

plt.close()

print("✅ roc_curves.png saved")


# ============================================================
# 16. CONFUSION MATRICES
# ============================================================

for model_name, y_pred in predictions.items():

    cm = confusion_matrix(
        y_test,
        y_pred
    )

    plt.figure(figsize=(6, 5))

    sns.heatmap(
        cm,
        annot=True,
        fmt="d",
        cmap="Blues",
        xticklabels=[
            "Not Placed",
            "Placed"
        ],
        yticklabels=[
            "Not Placed",
            "Placed"
        ]
    )

    plt.title(
        f"Confusion Matrix - {model_name}"
    )

    plt.xlabel("Predicted")
    plt.ylabel("Actual")

    plt.tight_layout()

    filename = (
        model_name
        .lower()
        .replace(" ", "_")
        + "_confusion_matrix.png"
    )

    plt.savefig(
        f"{OUTPUT_DIR}/{filename}",
        dpi=300
    )

    plt.close()


print("✅ Confusion matrices saved")


# ============================================================
# 17. CLASSIFICATION REPORT FOR BEST MODEL
# ============================================================

# We select best based on ROC-AUC
best_model_name = results_df.iloc[0]["Model"]

best_model = trained_models[
    best_model_name
]

best_predictions = predictions[
    best_model_name
]

print_header(
    f"BEST MODEL: {best_model_name}"
)

print(
    classification_report(
        y_test,
        best_predictions,
        target_names=[
            "Not Placed",
            "Placed"
        ],
        zero_division=0
    )
)


# ============================================================
# 18. SAVE CLASSIFICATION REPORT
# ============================================================

report = classification_report(
    y_test,
    best_predictions,
    target_names=[
        "Not Placed",
        "Placed"
    ],
    zero_division=0
)

with open(
    f"{RESULTS_DIR}/classification_report.txt",
    "w"
) as file:

    file.write(
        f"Best Model: {best_model_name}\n\n"
    )

    file.write(report)


# ============================================================
# 19. FEATURE IMPORTANCE
# ============================================================

print_header(
    "FEATURE IMPORTANCE ANALYSIS"
)

# Use Random Forest for feature importance
rf_pipeline = trained_models[
    "Random Forest"
]

rf_model = rf_pipeline.named_steps[
    "model"
]

rf_preprocessor = rf_pipeline.named_steps[
    "preprocessor"
]

# Get transformed feature names
try:

    feature_names = (
        rf_preprocessor
        .get_feature_names_out()
    )

    importances = rf_model.feature_importances_

    feature_importance_df = pd.DataFrame({
        "Feature": feature_names,
        "Importance": importances
    })

    feature_importance_df = (
        feature_importance_df
        .sort_values(
            "Importance",
            ascending=False
        )
    )

    feature_importance_df.to_csv(
        f"{RESULTS_DIR}/feature_importance.csv",
        index=False
    )

    print(
        feature_importance_df.head(20)
        .to_string(index=False)
    )

    # Top 20
    top_features = (
        feature_importance_df
        .head(20)
        .sort_values(
            "Importance"
        )
    )

    plt.figure(
        figsize=(10, 8)
    )

    sns.barplot(
        data=top_features,
        x="Importance",
        y="Feature"
    )

    plt.title(
        "Top 20 Feature Importances - Random Forest"
    )

    plt.tight_layout()

    plt.savefig(
        f"{OUTPUT_DIR}/feature_importance.png",
        dpi=300
    )

    plt.close()

    print(
        "\n✅ feature_importance.png saved"
    )

except Exception as e:

    print(
        "⚠️ Feature importance could not be generated:"
    )

    print(e)


# ============================================================
# 20. CROSS VALIDATION
# ============================================================

print_header(
    "CROSS-VALIDATION"
)

cv = StratifiedKFold(
    n_splits=3,
    shuffle=True,
    random_state=42
)

cv_results = []

# To keep runtime reasonable, evaluate each model
# using the existing pipelines.

for model_name, pipeline in trained_models.items():

    print(
        f"🔄 Cross-validating {model_name}..."
    )

    scores = cross_val_score(
        pipeline,
        X,
        y,
        cv=cv,
        scoring="accuracy",
        n_jobs=-1
    )

    cv_results.append({
        "Model": model_name,
        "CV Mean Accuracy": scores.mean(),
        "CV Std": scores.std()
    })

    print(
        f"Mean Accuracy: {scores.mean():.4f}"
    )

cv_df = pd.DataFrame(
    cv_results
)

cv_df.to_csv(
    f"{RESULTS_DIR}/cross_validation_results.csv",
    index=False
)

print(
    "\n✅ cross_validation_results.csv saved"
)


# ============================================================
# 21. SAVE BEST MODEL
# ============================================================

best_model_path = (
    f"{MODEL_DIR}/best_placepro_model.pkl"
)

joblib.dump(
    best_model,
    best_model_path
)

print(
    f"\n✅ Best model saved: {best_model_path}"
)


# ============================================================
# 22. SAVE ALL MODELS
# ============================================================

for model_name, model_pipeline in trained_models.items():

    filename = (
        model_name
        .lower()
        .replace(" ", "_")
        + ".pkl"
    )

    joblib.dump(
        model_pipeline,
        f"{MODEL_DIR}/{filename}"
    )

print("✅ All trained models saved")


# ============================================================
# 23. FINAL RESULTS FILE
# ============================================================

with open(
    f"{RESULTS_DIR}/final_results.txt",
    "w"
) as file:

    file.write(
        "PLACEPRO - FINAL MACHINE LEARNING RESULTS\n"
    )

    file.write(
        "==========================================\n\n"
    )

    file.write(
        f"Dataset Samples: {len(df)}\n"
    )

    file.write(
        f"Features Used: {X.shape[1]}\n\n"
    )

    file.write(
        "MODEL PERFORMANCE\n"
    )

    file.write(
        "-----------------\n\n"
    )

    file.write(
        results_df.to_string(
            index=False
        )
    )

    file.write(
        "\n\n==========================================\n"
    )

    file.write(
        f"Best Model: {best_model_name}\n"
    )

    file.write(
        f"Best Accuracy: "
        f"{results_df.iloc[0]['Accuracy']:.4f}\n"
    )

    file.write(
        f"Best ROC-AUC: "
        f"{results_df.iloc[0]['ROC-AUC']:.4f}\n"
    )


# ============================================================
# 24. FINAL SUMMARY
# ============================================================

print_header(
    "PLACEPRO - ML PIPELINE COMPLETED"
)

print(
    f"🏆 Best Model: {best_model_name}"
)

print(
    f"📊 Accuracy: "
    f"{results_df.iloc[0]['Accuracy'] * 100:.2f}%"
)

print(
    f"📈 ROC-AUC: "
    f"{results_df.iloc[0]['ROC-AUC']:.4f}"
)

print("\n📁 Generated folders:")

print("   outputs/")
print("   results/")
print("   models/")

print("\n📄 Important files:")

print("   results/model_comparison.csv")
print("   results/feature_importance.csv")
print("   results/cross_validation_results.csv")
print("   results/classification_report.txt")
print("   results/final_results.txt")

print("\n🎉 PLACEPRO PHASE 3 ML PIPELINE COMPLETED!")