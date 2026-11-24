"""Isolated V1 contract and honest projection of the existing synthetic dataset."""

MODEL_VERSION = "placepro-experimental-v1-16-inputs"
INPUT_COLUMNS = [
    "branch", "college_tier", "cgpa", "backlogs", "coding_skills", "dsa_score",
    "ml_knowledge", "system_design", "projects_count", "certifications",
    "aptitude_score", "communication_skills", "internships", "hackathons",
    "open_source_contributions", "extracurriculars",
]
SOURCE_COLUMNS = {
    "branch": "branch", "college_tier": "college_tier", "cgpa": "cgpa",
    "backlogs": "backlogs", "coding_skills": "coding_skill_score",
    "projects_count": "projects_count", "certifications": "certifications_count",
    "aptitude_score": "aptitude_score", "communication_skills": "communication_skill_score",
    "internships": "internships_count", "hackathons": "hackathons_participated",
}
MODEL_FEATURES = list(SOURCE_COLUMNS)
CATEGORICAL = ["branch", "college_tier"]
IGNORED_INPUTS = [column for column in INPUT_COLUMNS if column not in MODEL_FEATURES]
UNSEEN_BRANCHES = ("ISE", "Chemical")
BRANCH_NORMALIZATION = {"EEE": "EE", "Mechanical": "ME", "Civil": "CE"}
TIER_NORMALIZATION = {"Tier 1": "Tier-1", "Tier 2": "Tier-2", "Tier 3": "Tier-3"}


def project_training_features(dataset):
    """No imputation or invented columns. Score division changes units, not claims."""
    features = dataset[list(SOURCE_COLUMNS.values())].copy()
    features.columns = MODEL_FEATURES
    features["branch"] = features["branch"].replace(BRANCH_NORMALIZATION)
    features["college_tier"] = features["college_tier"].replace(TIER_NORMALIZATION)
    for column in ("coding_skills", "communication_skills"):
        features[column] = features[column] / 10.0
    return features
