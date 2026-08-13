import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

# Load
df = pd.read_csv("data/placement.csv")

# Remove leakage
if "salary_package_lpa" in df.columns:
    df = df.drop(columns=["salary_package_lpa"])

# Remove ID
if "student_id" in df.columns:
    df = df.drop(columns=["student_id"])

# Target
df["placement_status"] = df["placement_status"].map({
    "Not Placed": 0,
    "Placed": 1
})

# Encode categorical columns
categorical = df.select_dtypes(include=["object"]).columns

for col in categorical:
    le = LabelEncoder()
    df[col] = le.fit_transform(df[col].astype(str))

X = df.drop(columns=["placement_status"])
y = df["placement_status"]

# Split
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42,
    stratify=y
)

# Random Forest
model = RandomForestClassifier(
    n_estimators=300,
    random_state=42,
    n_jobs=-1
)

model.fit(X_train, y_train)

# Importance
importance = pd.DataFrame({
    "Feature": X.columns,
    "Importance": model.feature_importances_
})

importance = importance.sort_values(
    "Importance",
    ascending=False
)

print("\n======================================")
print("PLACEPRO FEATURE IMPORTANCE")
print("======================================\n")

print(importance.to_string(index=False))

importance.to_csv(
    "results/feature_importance.csv",
    index=False
)

print("\n✅ Saved: results/feature_importance.csv")