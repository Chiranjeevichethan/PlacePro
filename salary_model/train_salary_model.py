import os
import time
import joblib
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor, ExtraTreesRegressor


# ============================================================
# PLACEPRO SALARY MODEL - COMPATIBLE VERSION
# ============================================================

DATA_PATH = os.path.join(
    os.path.dirname(__file__),
    "placement.csv"
)

df = pd.read_csv(DATA_PATH)

print("=" * 65)
print("PLACEPRO SALARY MODEL - 12 FEATURE VERSION")
print("=" * 65)

print(f"Original dataset: {df.shape}")


# ============================================================
# 1. KEEP ONLY PLACED STUDENTS
# ============================================================

df["placement_status"] = (
    df["placement_status"]
    .astype(str)
    .str.strip()
    .str.lower()
)

df = df[df["placement_status"] == "placed"].copy()

print(f"Placed students: {len(df)}")


# ============================================================
# 2. PLACEPRO-COMPATIBLE FEATURE MAPPING
# ============================================================

FEATURE_MAP = {
    "cgpa": "cgpa",
    "branch": "branch",
    "college_tier": "college_tier",
    "internships": "internships_count",
    "projects_count": "projects_count",
    "certifications": "certifications_count",
    "coding_skills": "coding_skill_score",
    "aptitude_score": "aptitude_score",
    "communication_skills": "communication_skill_score",
    "hackathons": "hackathons_participated",
    "backlogs": "backlogs",
    "extracurriculars": "extracurricular_score",
}

TARGET = "salary_package_lpa"

# Dataset columns
dataset_features = list(FEATURE_MAP.values())

X = df[dataset_features].copy()
y = df[TARGET].copy()


# ============================================================
# 3. DISPLAY FEATURES
# ============================================================

print("\nFeatures used by salary model:")

for placepro_name, dataset_name in FEATURE_MAP.items():
    print(f"  {placepro_name:25} <- {dataset_name}")

print(f"\nTarget: {TARGET}")


# ============================================================
# 4. IDENTIFY TYPES
# ============================================================

categorical_features = [
    "branch",
    "college_tier",
]

numeric_features = [
    "cgpa",
    "internships_count",
    "projects_count",
    "certifications_count",
    "coding_skill_score",
    "aptitude_score",
    "communication_skill_score",
    "hackathons_participated",
    "backlogs",
    "extracurricular_score",
]


# ============================================================
# 5. PREPROCESSING
# ============================================================

numeric_pipeline = Pipeline(
    steps=[
        ("imputer", SimpleImputer(strategy="median"))
    ]
)

categorical_pipeline = Pipeline(
    steps=[
        ("imputer", SimpleImputer(strategy="most_frequent")),
        (
            "onehot",
            OneHotEncoder(
                handle_unknown="ignore",
                sparse_output=False
            )
        )
    ]
)

preprocessor = ColumnTransformer(
    transformers=[
        ("numeric", numeric_pipeline, numeric_features),
        ("categorical", categorical_pipeline, categorical_features),
    ]
)


# ============================================================
# 6. TRAIN / TEST SPLIT
# ============================================================

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42
)

print(f"\nTraining rows: {len(X_train)}")
print(f"Testing rows:  {len(X_test)}")


# ============================================================
# 7. MODELS
# ============================================================

models = {
    "Ridge": Ridge(alpha=1.0),

    "Random Forest": RandomForestRegressor(
        n_estimators=200,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1
    ),

    "Gradient Boosting": GradientBoostingRegressor(
        n_estimators=150,
        learning_rate=0.05,
        max_depth=3,
        random_state=42
    ),

    "Extra Trees": ExtraTreesRegressor(
        n_estimators=200,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1
    ),
}


# ============================================================
# 8. TRAIN + EVALUATE
# ============================================================

results = []
trained_models = {}

for name, model in models.items():

    print("\n" + "-" * 65)
    print(f"Training: {name}")

    start = time.time()

    pipeline = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("model", model),
        ]
    )

    pipeline.fit(X_train, y_train)

    predictions = pipeline.predict(X_test)

    mae = mean_absolute_error(
        y_test,
        predictions
    )

    rmse = mean_squared_error(
        y_test,
        predictions
    ) ** 0.5

    r2 = r2_score(
        y_test,
        predictions
    )

    elapsed = time.time() - start

    results.append({
        "Model": name,
        "MAE": mae,
        "RMSE": rmse,
        "R2": r2,
        "Time_seconds": elapsed,
    })

    trained_models[name] = pipeline

    print(f"MAE:  {mae:.4f}")
    print(f"RMSE: {rmse:.4f}")
    print(f"R²:   {r2:.4f}")
    print(f"Time: {elapsed:.2f} seconds")


# ============================================================
# 9. COMPARE
# ============================================================

results_df = pd.DataFrame(results)

results_df = results_df.sort_values(
    by="MAE",
    ascending=True
)

print("\n" + "=" * 65)
print("MODEL COMPARISON")
print("=" * 65)

print(results_df.to_string(index=False))


# ============================================================
# 10. SELECT BEST MODEL
# ============================================================

best_model_name = results_df.iloc[0]["Model"]
best_model = trained_models[best_model_name]

print("\n" + "=" * 65)
print(f"BEST MODEL: {best_model_name}")
print("=" * 65)


# ============================================================
# 11. SAVE AS A NEW FILE
# ============================================================

project_root = os.path.dirname(
    os.path.dirname(__file__)
)

models_directory = os.path.join(
    project_root,
    "models"
)

os.makedirs(
    models_directory,
    exist_ok=True
)

model_path = os.path.join(
    models_directory,
    "placepro_salary_model_v2.pkl"
)

joblib.dump(
    best_model,
    model_path
)

print("\nSaved compatible salary model:")
print(model_path)

print("\nTraining complete.")