# ============================================================
# PLACEPRO - REUSABLE FEATURE ENGINEERING TRANSFORMER
# Phase 4 - Leak-free Feature Engineering
# ============================================================
#
# The Phase 3 feature engineering (main.py) was written inline and
# fitted `academic_skill_index` min/max statistics on the FULL dataset
# (train + test), which is a (mild) form of data leakage.
#
# This transformer extracts the SAME rules into a single reusable
# component that:
#   1. Fits its statistics on TRAINING data only.
#   2. Applies the identical rules at training, validation, testing
#      and prediction time.
#   3. Can be embedded as the first step of a scikit-learn Pipeline,
#      so the saved model file automatically contains it.
#
# Because it is a scikit-learn Transformer, it is compatible with
# GridSearchCV / RandomizedSearchCV / cross_validate — every fold
# refits the statistics on that fold's training portion only.

import numpy as np
import pandas as pd

from sklearn.base import BaseEstimator, TransformerMixin


class FeatureEngineeringTransformer(BaseEstimator, TransformerMixin):
    """
    Applies the PlacePro feature-engineering rules.

    Rules (identical to Phase 3, main.py):
        - high_cgpa           : cgpa >= 7.5
        - has_internship      : internships_count > 0
        - project_level       : binned projects_count -> {0, 1, 2}
        - overall_skill_score : mean of the 5 skill scores
        - experience_score    : sum of the 4 experience counters
        - academic_skill_index: mean of min-max normalised academic
                                scores (statistics fitted on train only)

    transform(X) returns a DataFrame with the ORIGINAL columns plus
    the engineered columns appended — the same layout Phase 3 used.
    """

    def __init__(self):
        # Detected at fit time from the actual columns present
        self.skill_columns_ = []
        self.experience_columns_ = []
        self.academic_columns_ = []

        # Min/max statistics fitted on training data only
        self.academic_min_ = {}
        self.academic_max_ = {}

    # ------------------------------------------------------------
    # fit: learn any statistics required by the rules
    # ------------------------------------------------------------
    def fit(self, X, y=None):
        skill_columns = [
            "coding_skill_score",
            "aptitude_score",
            "logical_reasoning_score",
            "communication_skill_score",
            "mock_interview_score",
        ]
        self.skill_columns_ = [c for c in skill_columns if c in X.columns]

        experience_columns = [
            "internships_count",
            "projects_count",
            "certifications_count",
            "hackathons_participated",
        ]
        self.experience_columns_ = [
            c for c in experience_columns if c in X.columns
        ]

        academic_columns = [
            "cgpa",
            "attendance_percentage",
            "coding_skill_score",
            "aptitude_score",
        ]
        self.academic_columns_ = [
            c for c in academic_columns if c in X.columns
        ]

        # Min/max are fitted on the TRAINING data only (leak-free)
        if len(self.academic_columns_) >= 2:
            for col in self.academic_columns_:
                self.academic_min_[col] = float(X[col].min())
                self.academic_max_[col] = float(X[col].max())

        return self

    # ------------------------------------------------------------
    # transform: apply the rules to any input data
    # ------------------------------------------------------------
    def transform(self, X):
        X = X.copy()

        # ---- high_cgpa ----
        if "cgpa" in X.columns:
            X["high_cgpa"] = (X["cgpa"] >= 7.5).astype(int)

        # ---- has_internship ----
        if "internships_count" in X.columns:
            X["has_internship"] = (X["internships_count"] > 0).astype(int)

        # ---- project_level ----
        if "projects_count" in X.columns:
            X["project_level"] = pd.cut(
                X["projects_count"],
                bins=[-1, 0, 2, np.inf],
                labels=[0, 1, 2],
            ).astype(int)

        # ---- overall_skill_score ----
        if len(self.skill_columns_) >= 2:
            X["overall_skill_score"] = X[self.skill_columns_].mean(axis=1)

        # ---- experience_score ----
        if len(self.experience_columns_) >= 2:
            X["experience_score"] = X[self.experience_columns_].sum(axis=1)

        # ---- academic_skill_index (uses train-fitted min/max) ----
        if len(self.academic_columns_) >= 2:
            temp = pd.DataFrame(index=X.index)
            for col in self.academic_columns_:
                col_min = self.academic_min_[col]
                col_max = self.academic_max_[col]
                if col_max != col_min:
                    temp[col] = (X[col] - col_min) / (col_max - col_min) * 100
                else:
                    temp[col] = 0.0
            X["academic_skill_index"] = temp.mean(axis=1)

        return X

    # ------------------------------------------------------------
    # get_feature_names_out: report final column names
    # (used for feature-importance labelling)
    # ------------------------------------------------------------
    def get_feature_names_out(self, input_features=None):
        base = list(input_features) if input_features is not None else []

        engineered = []
        if "cgpa" in base:
            engineered.append("high_cgpa")
        if "internships_count" in base:
            engineered.append("has_internship")
        if "projects_count" in base:
            engineered.append("project_level")
        if len(self.skill_columns_) >= 2:
            engineered.append("overall_skill_score")
        if len(self.experience_columns_) >= 2:
            engineered.append("experience_score")
        if len(self.academic_columns_) >= 2:
            engineered.append("academic_skill_index")

        return base + engineered
