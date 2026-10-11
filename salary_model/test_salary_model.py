import os
import joblib
import pandas as pd

MODEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "models",
    "placepro_salary_model_v2.pkl"
)

model = joblib.load(MODEL_PATH)

student = pd.DataFrame([{
    "cgpa": 8.5,
    "branch": "CSE",
    "college_tier": "Tier-2",
    "internships_count": 2,
    "projects_count": 3,
    "certifications_count": 2,
    "coding_skill_score": 8.0,
    "aptitude_score": 80.0,
    "communication_skill_score": 8.0,
    "hackathons_participated": 2,
    "backlogs": 0,
    "extracurricular_score": 2.0
}])

prediction = model.predict(student)[0]

print("=" * 50)
print("PLACEPRO SALARY MODEL TEST")
print("=" * 50)
print(f"Predicted Salary: {prediction:.2f} LPA")
