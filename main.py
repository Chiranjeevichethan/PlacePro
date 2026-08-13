# ==============================
# PLACEPRO - FINAL CORRECT VERSION
# ==============================

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report

# ==============================
# 1. LOAD DATASET
# ==============================

try:
    df = pd.read_csv("placement.csv")
except:
    print("❌ ERROR: placement.csv not found. Put file in same folder.")
    exit()


# # ==============================
# # 1. LOAD DATASET
# # ==============================

# df = pd.read_csv("placement.csv")

# 🔥 REMOVE DATA LEAKAGE COLUMN (VERY IMPORTANT)
if 'salary_package_lpa' in df.columns:
    df.drop('salary_package_lpa', axis=1, inplace=True)

print("\n✅ Dataset Loaded")
print("Shape:", df.shape)
print("Columns:", df.columns.tolist())


print("\n✅ Dataset Loaded")
print("Shape:", df.shape)
print("Columns:", df.columns.tolist())

# ==============================
# 2. DATA PREPROCESSING
# ==============================

# Handle missing values
df.fillna(df.mean(numeric_only=True), inplace=True)

# Drop ID column (not useful)
if 'student_id' in df.columns:
    df.drop('student_id', axis=1, inplace=True)

# Encode categorical columns
le = LabelEncoder()
for col in df.columns:
    if df[col].dtype == 'object':
        df[col] = le.fit_transform(df[col])

# ==============================
# 3. TARGET COLUMN FIX
# ==============================

# Use correct target
target = 'placement_status'

# Ensure binary (0/1)
df[target] = df[target].apply(lambda x: 1 if x == 1 else 0)

print("\n🎯 Target Column:", target)

# ==============================
# 4. FEATURE ENGINEERING
# ==============================

# Create useful features
if 'cgpa' in df.columns:
    df['high_cgpa'] = df['cgpa'].apply(lambda x: 1 if x > 7 else 0)

if 'internships_count' in df.columns:
    df['has_internship'] = df['internships_count'].apply(lambda x: 1 if x > 0 else 0)

if 'projects_count' in df.columns:
    df['project_level'] = df['projects_count'].apply(lambda x: 2 if x >= 3 else (1 if x > 0 else 0))

# ==============================
# 5. EDA (SAVE GRAPHS)
# ==============================

# Placement distribution
plt.figure()
sns.countplot(x=target, data=df)
plt.title("Placement Distribution")
plt.savefig("placement_distribution.png")
plt.close()

# CGPA vs Placement
if 'cgpa' in df.columns:
    plt.figure()
    sns.boxplot(x=target, y='cgpa', data=df)
    plt.title("CGPA vs Placement")
    plt.savefig("cgpa_vs_placement.png")
    plt.close()

# Heatmap
plt.figure(figsize=(10,6))
sns.heatmap(df.corr(), cmap='coolwarm')
plt.title("Correlation Heatmap")
plt.savefig("heatmap.png")
plt.close()

# ==============================
# 6. PREPARE DATA
# ==============================

X = df.drop(target, axis=1)
y = df[target]

# Scale features
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# Train-test split
X_train, X_test, y_train, y_test = train_test_split(
    X_scaled, y, test_size=0.2, random_state=42
)

# ==============================
# 7. MODEL TRAINING
# ==============================

dt = DecisionTreeClassifier()
rf = RandomForestClassifier(n_estimators=100)

dt.fit(X_train, y_train)
rf.fit(X_train, y_train)

# ==============================
# 8. EVALUATION
# ==============================

y_pred_dt = dt.predict(X_test)
y_pred_rf = rf.predict(X_test)

dt_acc = accuracy_score(y_test, y_pred_dt)
rf_acc = accuracy_score(y_test, y_pred_rf)

print("\n📊 RESULTS")
print("Decision Tree Accuracy:", dt_acc)
print("Random Forest Accuracy:", rf_acc)

print("\nRandom Forest Report:\n", classification_report(y_test, y_pred_rf))

# ==============================
# 9. FEATURE IMPORTANCE
# ==============================

feat_df = pd.DataFrame({
    'Feature': X.columns,
    'Importance': rf.feature_importances_
}).sort_values(by='Importance', ascending=False)

plt.figure(figsize=(8,5))
sns.barplot(x='Importance', y='Feature', data=feat_df)
plt.title("Feature Importance")
plt.savefig("feature_importance.png")
plt.close()

# ==============================
# 10. SAVE RESULTS
# ==============================

with open("results.txt", "w") as f:
    f.write("Decision Tree Accuracy: " + str(dt_acc) + "\n")
    f.write("Random Forest Accuracy: " + str(rf_acc) + "\n")

print("\n✅ All outputs saved successfully!")
