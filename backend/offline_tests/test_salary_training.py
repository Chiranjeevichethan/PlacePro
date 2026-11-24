"""Explicit external-data analysis, outside the default runtime testpaths.

Reads approved original data and the served artifact; never trains or writes them.
"""
import hashlib
import os
from pathlib import Path

import pandas as pd
import pytest
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

from backend.app.services.salary_prediction_service import _load_model
from backend.tests.salary_summary import load_salary_summary


@pytest.fixture(scope="module")
def training_rows():
    configured = os.environ.get("PLACEPRO_SALARY_ANALYSIS_DATA")
    if not configured:
        pytest.fail("Set PLACEPRO_SALARY_ANALYSIS_DATA to approved original data for this explicit offline suite.")
    path = Path(configured)
    if not path.is_file():
        pytest.fail("Approved offline salary dataset is unavailable.")
    summary = load_salary_summary()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == summary["provenance"]["dataset"]["sha256"], "Offline dataset does not match recorded provenance."
    rows = pd.read_csv(path, usecols=summary["model_features"] + ["placement_status", "salary_package_lpa"])
    rows["placement_status"] = rows["placement_status"].astype(str).str.strip().str.lower()
    return rows


def test_training_target_is_lpa_for_placed_students_only(training_rows):
    summary = load_salary_summary()
    placed = training_rows[training_rows["placement_status"] == "placed"]
    not_placed = training_rows[training_rows["placement_status"] != "placed"]
    low, high = summary["target"]["minimum"], summary["target"]["maximum"]
    assert low == pytest.approx(placed["salary_package_lpa"].min())
    assert high == pytest.approx(placed["salary_package_lpa"].max())
    assert 5.0 < low < high < 50.0
    assert (not_placed["salary_package_lpa"] == 0).all()
    assert len(training_rows) == summary["population"]["total_rows"]
    assert len(placed) == summary["population"]["placed_rows"]
    assert len(not_placed) == summary["population"]["not_placed_rows"]
    assert bool((not_placed["salary_package_lpa"] == 0).all()) == summary["population"]["not_placed_salary_all_zero"]
    for feature, (minimum, maximum) in summary["numeric_feature_support"].items():
        assert minimum == pytest.approx(placed[feature].min()), feature
        assert maximum == pytest.approx(placed[feature].max()), feature


def test_served_artifact_keeps_its_documented_holdout_quality(training_rows):
    """Same held-out split and thresholds; no claim of real-world accuracy."""
    placed = training_rows[training_rows["placement_status"] == "placed"]
    _, X_test, _, y_test = train_test_split(
        placed[load_salary_summary()["model_features"]],
        placed["salary_package_lpa"],
        test_size=0.20,
        random_state=42,
    )
    predictions = _load_model().predict(X_test)
    assert mean_absolute_error(y_test, predictions) < 1.0
    assert mean_squared_error(y_test, predictions) ** 0.5 < 1.3
    assert r2_score(y_test, predictions) > 0.5
