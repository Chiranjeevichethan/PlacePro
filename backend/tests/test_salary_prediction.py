import math

import pytest
from fastapi.testclient import TestClient

from backend.tests.domain_app import app
from backend.tests.salary_summary import load_salary_summary
from backend.app.services import salary_prediction_service
from backend.app.services.salary_prediction_service import (
    DEFAULT_COLLEGE_TIER,
    FEATURE_SUPPORT,
    _convert_extracurricular_score,
    _convert_skill_score,
    _load_model,
    normalize_branch,
    normalize_college_tier,
    predict_salary,
    resolve_college_tier,
)

client = TestClient(app)


VALID_PAYLOAD = {
    "branch": "CSE",
    "college_tier": "Tier-2",
    "cgpa": 8.5,
    "backlogs": 0,
    "coding_skills": 8.0,
    "dsa_score": 8.0,
    "aptitude_score": 80.0,
    "communication_skills": 8.0,
    "ml_knowledge": 7.0,
    "system_design": 7.0,
    "internships": 2,
    "projects_count": 3,
    "certifications": 2,
    "hackathons": 2,
    "open_source_contributions": 1,
    "extracurriculars": 2,
}


def test_salary_prediction_success():
    response = client.post("/api/salary-predict", json=VALID_PAYLOAD)

    assert response.status_code == 200

    body = response.json()

    assert "predicted_salary_lpa" in body
    assert "model_version" in body

    assert isinstance(body["predicted_salary_lpa"], float)
    assert body["predicted_salary_lpa"] > 0
    assert body["model_version"] == "placepro-salary-v2"


def test_salary_prediction_uses_frontend_compatible_16_field_payload():
    response = client.post("/api/salary-predict", json=VALID_PAYLOAD)

    assert response.status_code == 200


def test_salary_prediction_rejects_invalid_cgpa():
    payload = VALID_PAYLOAD.copy()
    payload["cgpa"] = 11.0

    response = client.post("/api/salary-predict", json=payload)

    assert response.status_code == 422


def test_salary_prediction_rejects_missing_required_field():
    payload = VALID_PAYLOAD.copy()
    del payload["cgpa"]

    response = client.post("/api/salary-predict", json=payload)

    assert response.status_code == 422


# ------------------------------------------------------------------
# Category normalization (salary dataset uses "Tier 1" / "CSE" etc.)
# ------------------------------------------------------------------


@pytest.mark.parametrize(
    "spelling,expected",
    [
        ("Tier 1", "Tier 1"),
        ("Tier-1", "Tier 1"),
        (1, "Tier 1"),
        ("Tier 2", "Tier 2"),
        ("Tier-2", "Tier 2"),
        ("Tier 3", "Tier 3"),
        ("Tier-3", "Tier 3"),
        (3, "Tier 3"),
    ],
)
def test_normalize_college_tier(spelling, expected):
    assert normalize_college_tier(spelling) == expected


@pytest.mark.parametrize(
    "spelling,expected",
    [
        ("Computer Science & Engineering", "CSE"),
        ("Mechanical Engineering", "Mechanical"),
        ("ME", "Mechanical"),
        ("EE", "EEE"),
        ("CE", "Civil"),
        ("CSE", "CSE"),
    ],
)
def test_normalize_branch(spelling, expected):
    assert normalize_branch(spelling) == expected


@pytest.mark.parametrize(
    "tier_spelling",
    ["Tier 2", "Tier-2", "2"],
)
def test_api_tier_spellings_are_equivalent(tier_spelling):
    """All accepted tier spellings must hit the same one-hot category."""

    baseline = client.post("/api/salary-predict", json=VALID_PAYLOAD)

    payload = VALID_PAYLOAD.copy()
    payload["college_tier"] = tier_spelling
    response = client.post("/api/salary-predict", json=payload)

    assert baseline.status_code == 200
    assert response.status_code == 200
    assert (
        response.json()["predicted_salary_lpa"]
        == pytest.approx(baseline.json()["predicted_salary_lpa"])
    )


# ------------------------------------------------------------------
# Input scale conversion (frontend 0-10 -> dataset 20-100)
# ------------------------------------------------------------------


def test_convert_skill_score_scales_and_clamps():
    assert _convert_skill_score(8.0) == 80.0
    assert _convert_skill_score(10.0) == 100.0
    # Dataset range starts at 20; low inputs clamp to that floor.
    assert _convert_skill_score(0.0) == 20.0
    assert _convert_skill_score(1.5) == 20.0
    assert _convert_skill_score(12.0) == 100.0


def test_convert_extracurricular_score_scales_count_to_0_100():
    assert _convert_extracurricular_score(0) == 0.0
    assert _convert_extracurricular_score(3) == 100.0
    assert _convert_extracurricular_score(2) == pytest.approx(66.67, abs=0.01)


# ------------------------------------------------------------------
# Prediction sanity across representative profiles
# ------------------------------------------------------------------


def _profile(**overrides):
    profile = {
        "branch": "CSE",
        "college_tier": "Tier-2",
        "cgpa": 8.0,
        "backlogs": 0,
        "coding_skills": 7.0,
        "dsa_score": 7.0,
        "aptitude_score": 70.0,
        "communication_skills": 7.0,
        "ml_knowledge": 6.0,
        "system_design": 6.0,
        "internships": 1,
        "projects_count": 3,
        "certifications": 2,
        "hackathons": 1,
        "open_source_contributions": 1,
        "extracurriculars": 2,
    }
    profile.update(overrides)
    return profile


@pytest.mark.parametrize(
    "profile",
    [
        _profile(),
        _profile(cgpa=9.5, coding_skills=9.5, internships=4, backlogs=0),
        _profile(cgpa=5.0, coding_skills=2.0, backlogs=3, internships=0),
        _profile(college_tier="Tier 1", branch="IT"),
        _profile(college_tier="Tier 3", branch="Civil"),
    ],
)
def test_predictions_are_finite_and_positive(profile):
    result = predict_salary(profile)

    value = result["predicted_salary_lpa"]
    assert math.isfinite(value)
    assert value > 0
    assert result["model_version"] == "placepro-salary-v2"


def test_stronger_numeric_profile_predicts_higher_than_weak_profile():
    weak = predict_salary(
        _profile(cgpa=5.0, coding_skills=2.0, internships=0, backlogs=3)
    )
    strong = predict_salary(
        _profile(cgpa=9.5, coding_skills=9.5, internships=4, backlogs=0)
    )

    assert (
        strong["predicted_salary_lpa"] > weak["predicted_salary_lpa"]
    )


def test_higher_coding_score_predicts_higher_salary():
    """coding_skill_score has a positive learned Ridge coefficient."""

    low = predict_salary(_profile(coding_skills=3.0))
    high = predict_salary(_profile(coding_skills=9.0))

    assert high["predicted_salary_lpa"] > low["predicted_salary_lpa"]


def test_unknown_branch_passes_through_without_crashing():
    """handle_unknown="ignore" must keep odd branch strings working."""

    result = predict_salary(_profile(branch="Chemical Engineering"))

    assert math.isfinite(result["predicted_salary_lpa"])
    assert result["predicted_salary_lpa"] > 0


# ------------------------------------------------------------------
# college_tier is optional: the backend assigns the default internally
# ------------------------------------------------------------------


def _without_tier(payload):
    """The frontend no longer sends a college tier at all."""

    return {
        key: value
        for key, value in payload.items()
        if key != "college_tier"
    }


def test_api_works_when_college_tier_is_omitted():
    """Omitted tier (the new frontend payload) still predicts."""

    response = client.post(
        "/api/salary-predict",
        json=_without_tier(VALID_PAYLOAD),
    )

    assert response.status_code == 200

    body = response.json()

    assert isinstance(body["predicted_salary_lpa"], float)
    assert body["predicted_salary_lpa"] > 0
    assert body["model_version"] == "placepro-salary-v2"


@pytest.mark.parametrize("missing_value", [None, "", "   "])
def test_api_handles_null_and_empty_college_tier(missing_value):
    """null, empty-string and whitespace-only tiers are handled safely."""

    payload = {**VALID_PAYLOAD, "college_tier": missing_value}

    response = client.post("/api/salary-predict", json=payload)

    assert response.status_code == 200
    assert response.json()["predicted_salary_lpa"] > 0


def test_omitted_college_tier_matches_explicit_default_tier():
    """Omitting the tier behaves exactly like sending the default tier."""

    omitted = client.post(
        "/api/salary-predict",
        json=_without_tier(VALID_PAYLOAD),
    )
    explicit = client.post(
        "/api/salary-predict",
        json={**VALID_PAYLOAD, "college_tier": DEFAULT_COLLEGE_TIER},
    )

    assert omitted.status_code == 200
    assert explicit.status_code == 200
    assert omitted.json()["predicted_salary_lpa"] == pytest.approx(
        explicit.json()["predicted_salary_lpa"]
    )


def test_api_still_accepts_an_explicit_valid_college_tier():
    """Existing requests that still include a tier keep working."""

    baseline = client.post("/api/salary-predict", json=VALID_PAYLOAD)

    payload = {**VALID_PAYLOAD, "college_tier": "Tier 1"}
    response = client.post("/api/salary-predict", json=payload)

    assert response.status_code == 200
    assert response.json()["predicted_salary_lpa"] > 0
    # A different tier is a different feature value, not a rejected request.
    assert response.json()["predicted_salary_lpa"] != pytest.approx(
        baseline.json()["predicted_salary_lpa"]
    )


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, "Tier 2"),
        ("", "Tier 2"),
        ("   ", "Tier 2"),
        ("Tier 2", "Tier 2"),
        ("Tier-1", "Tier 1"),
        ("Tier-3", "Tier 3"),
        ("2", "Tier 2"),
    ],
)
def test_resolve_college_tier(value, expected):
    assert resolve_college_tier(value) == expected


@pytest.mark.parametrize("missing_value", [None, "", "   "])
def test_service_resolves_missing_tier_to_the_default(missing_value):
    expected = predict_salary(_profile(college_tier=DEFAULT_COLLEGE_TIER))

    result = predict_salary(_profile(college_tier=missing_value))

    assert result["predicted_salary_lpa"] == pytest.approx(
        expected["predicted_salary_lpa"]
    )


def test_service_accepts_a_profile_with_no_college_tier_key():
    profile = _profile()
    profile.pop("college_tier")

    result = predict_salary(profile)

    assert math.isfinite(result["predicted_salary_lpa"])
    assert result["predicted_salary_lpa"] > 0


def test_default_tier_is_a_category_the_served_model_knows():
    """The default is evidence-based, not arbitrary.

    DEFAULT_COLLEGE_TIER must be the category the served pipeline itself
    uses for a missing tier (its categorical SimpleImputer's most_frequent
    statistic) and one of the OneHotEncoder's known categories, so the
    resolved value can never be an unseen label.
    """

    preprocessor = _load_model().named_steps["preprocessor"]

    categorical_pipeline = None
    tier_index = None

    for name, transformer, columns in preprocessor.transformers_:
        if name == "categorical":
            categorical_pipeline = transformer
            tier_index = list(columns).index("college_tier")

    assert categorical_pipeline is not None

    imputer = categorical_pipeline.named_steps["imputer"]
    encoder = categorical_pipeline.named_steps["onehot"]

    assert imputer.strategy == "most_frequent"
    assert imputer.statistics_[tier_index] == DEFAULT_COLLEGE_TIER
    assert DEFAULT_COLLEGE_TIER in set(encoder.categories_[tier_index])


# ------------------------------------------------------------------
# Anti-extrapolation guard (the unrealistic-prediction root cause)
#
# The served model is a linear Ridge regression trained only on placed
# students, whose salaries in the training data span [7.11, 20.44] LPA.
# Feeding inputs outside the training feature support used to make it
# extrapolate below that range: the all-zero profile returned 4.11 LPA,
# which is LOWER than every salary the model was ever shown. These tests
# pin the fix (inputs clipped to the training support) and the bounds
# themselves to the training data - no expected salary is hardcoded.
# ------------------------------------------------------------------

# The 12 features the salary model consumes, in the pipeline's own order.
MODEL_FEATURES = [
    "cgpa",
    "branch",
    "college_tier",
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

def _training_target_range():
    """Independently verified target bounds; no training rows required."""

    target = load_salary_summary()["target"]
    assert target["column"] == "salary_package_lpa" and target["unit"] == "LPA"
    assert target["population"] == "placed"
    return target["minimum"], target["maximum"]


ALL_ZERO_PROFILE = _profile(
    cgpa=0.0,
    backlogs=5,
    coding_skills=0,
    dsa_score=0,
    aptitude_score=0.0,
    communication_skills=0,
    ml_knowledge=0,
    system_design=0,
    internships=0,
    projects_count=0,
    certifications=0,
    hackathons=0,
    open_source_contributions=0,
    extracurriculars=0,
)


def _capture_model_input(monkeypatch, profile):
    """Run the real inference path and return the frame it handed the model."""

    recorded = []

    class _RecordingPipeline:
        def __init__(self, inner):
            self._inner = inner

        def predict(self, frame):
            recorded.append(frame.copy())
            return self._inner.predict(frame)

    real_pipeline = _load_model()

    monkeypatch.setattr(
        salary_prediction_service,
        "_load_model",
        lambda: _RecordingPipeline(real_pipeline),
    )

    predict_salary(profile)

    return recorded[0]


def test_feature_support_bounds_are_the_training_data_min_and_max():
    """Compare with recorded data aggregates, independently of service constants."""

    summary = load_salary_summary()
    assert summary["model_features"] == MODEL_FEATURES
    support = summary["numeric_feature_support"]

    assert set(FEATURE_SUPPORT) == set(MODEL_FEATURES) - {
        "branch",
        "college_tier",
    }
    assert set(support) == set(FEATURE_SUPPORT)

    for feature, (low, high) in FEATURE_SUPPORT.items():
        assert low == pytest.approx(support[feature][0]), feature
        assert high == pytest.approx(support[feature][1]), feature


def test_prediction_stays_on_the_lpa_scale_of_the_training_target():
    low, high = _training_target_range()

    value = predict_salary(_profile())["predicted_salary_lpa"]

    assert low <= value <= high


@pytest.mark.parametrize(
    "profile",
    [
        ALL_ZERO_PROFILE,
        _profile(cgpa=0.0),
        _profile(
            cgpa=0.0,
            aptitude_score=0.0,
            coding_skills=0.0,
            communication_skills=0.0,
        ),
        _profile(
            cgpa=6.0,
            backlogs=5,
            coding_skills=2,
            dsa_score=2,
            aptitude_score=2,
            communication_skills=2,
            ml_knowledge=2,
            system_design=2,
            internships=0,
            projects_count=1,
            certifications=2,
            hackathons=1,
            open_source_contributions=0,
            extracurriculars=0,
        ),
        _profile(
            cgpa=10.0,
            coding_skills=10.0,
            aptitude_score=100.0,
            communication_skills=10.0,
            internships=60,
            projects_count=80,
            certifications=90,
            hackathons=50,
            extracurriculars=40,
        ),
    ],
)
def test_predictions_never_leave_the_training_target_range(profile):
    """Regression test for the reported amounts: no salary below 7.11 LPA."""

    low, high = _training_target_range()

    value = predict_salary(profile)["predicted_salary_lpa"]

    assert math.isfinite(value)
    assert low <= value <= high


def test_all_zero_profile_is_not_extrapolated_below_the_training_floor():
    """The reported 4.11 LPA was below every salary in the training data."""

    low, _ = _training_target_range()

    value = predict_salary(ALL_ZERO_PROFILE)["predicted_salary_lpa"]

    assert value >= low


def test_cgpa_below_the_training_minimum_is_clipped_not_extrapolated():
    at_floor = predict_salary(_profile(cgpa=FEATURE_SUPPORT["cgpa"][0]))
    below_floor = predict_salary(_profile(cgpa=0.0))

    assert below_floor["predicted_salary_lpa"] == pytest.approx(
        at_floor["predicted_salary_lpa"]
    )


def test_aptitude_below_the_training_minimum_is_clipped_not_extrapolated():
    floor = FEATURE_SUPPORT["aptitude_score"][0]

    at_floor = predict_salary(_profile(aptitude_score=floor))
    below_floor = predict_salary(_profile(aptitude_score=0.0))

    assert below_floor["predicted_salary_lpa"] == pytest.approx(
        at_floor["predicted_salary_lpa"]
    )


def test_counts_above_the_training_maximum_are_clipped_not_extrapolated():
    ceiling = FEATURE_SUPPORT["internships_count"][1]

    at_ceiling = predict_salary(_profile(internships=ceiling))
    above_ceiling = predict_salary(_profile(internships=100))

    assert above_ceiling["predicted_salary_lpa"] == pytest.approx(
        at_ceiling["predicted_salary_lpa"]
    )


def test_in_support_values_are_not_flattened_by_the_guard():
    """Inside the supported range the model must still respond to its inputs."""

    values = [
        predict_salary(_profile(cgpa=cgpa))["predicted_salary_lpa"]
        for cgpa in (4.5, 6.0, 7.5, 9.0, 10.0)
    ]

    assert len(set(values)) == len(values)
    assert values == sorted(values)


def test_model_input_preserves_zeros_and_clips_out_of_support_values(
    monkeypatch,
):
    """A real 0 must reach the model as 0 - never a default or an imputed mean."""

    frame = _capture_model_input(monkeypatch, ALL_ZERO_PROFILE)
    row = frame.iloc[0]

    # In-support zeros are preserved exactly (`backlogs` 5 is the data max).
    assert row["internships_count"] == 0
    assert row["projects_count"] == 0
    assert row["certifications_count"] == 0
    assert row["hackathons_participated"] == 0
    assert row["extracurricular_score"] == 0.0
    assert row["backlogs"] == 5

    # Out-of-support values are clipped to the training range, not defaulted
    # to a mean, a median, or any other substituted value.
    assert row["cgpa"] == FEATURE_SUPPORT["cgpa"][0]
    assert row["coding_skill_score"] == FEATURE_SUPPORT["coding_skill_score"][0]
    assert row["aptitude_score"] == FEATURE_SUPPORT["aptitude_score"][0]


def test_model_input_columns_and_order_match_the_trained_pipeline(monkeypatch):
    frame = _capture_model_input(monkeypatch, _profile())

    expected = list(
        _load_model().named_steps["preprocessor"].feature_names_in_
    )

    assert list(frame.columns) == MODEL_FEATURES
    assert list(frame.columns) == expected


def test_salary_increases_with_profile_strength():
    """The model responds to its inputs rather than returning an average."""

    weak = predict_salary(ALL_ZERO_PROFILE)["predicted_salary_lpa"]
    moderate = predict_salary(_profile())["predicted_salary_lpa"]
    strong = predict_salary(
        _profile(
            cgpa=9.5,
            coding_skills=9.5,
            aptitude_score=95.0,
            communication_skills=9.0,
            internships=4,
            projects_count=6,
            certifications=5,
            hackathons=3,
            extracurriculars=3,
        )
    )["predicted_salary_lpa"]

    assert weak < moderate < strong


def test_cgpa_and_internships_move_the_prediction():
    """These are the two features the training data actually ties to salary."""

    base = predict_salary(_profile(cgpa=5.0, internships=0))[
        "predicted_salary_lpa"
    ]
    higher_cgpa = predict_salary(_profile(cgpa=9.0, internships=0))[
        "predicted_salary_lpa"
    ]
    more_internships = predict_salary(_profile(cgpa=5.0, internships=4))[
        "predicted_salary_lpa"
    ]

    assert higher_cgpa > base
    assert more_internships > base


# ------------------------------------------------------------------
# API boundary, invalid, and missing-value handling
# ------------------------------------------------------------------


@pytest.mark.parametrize(
    "field,value",
    [
        ("cgpa", -1.0),
        ("backlogs", -1),
        ("coding_skills", -0.1),
        ("dsa_score", -1.0),
        ("aptitude_score", -1.0),
        ("communication_skills", -1.0),
        ("ml_knowledge", -1.0),
        ("system_design", -1.0),
        ("internships", -1),
        ("projects_count", -1),
        ("certifications", -1),
        ("hackathons", -1),
        ("open_source_contributions", -1),
        ("extracurriculars", -1),
    ],
)
def test_api_rejects_negative_values(field, value):
    payload = {**VALID_PAYLOAD, field: value}

    assert client.post("/api/salary-predict", json=payload).status_code == 422


@pytest.mark.parametrize(
    "field,value",
    [
        ("cgpa", 10.5),
        ("cgpa", 11.0),
        ("coding_skills", 10.1),
        ("dsa_score", 10.1),
        ("aptitude_score", 100.1),
        ("aptitude_score", 101.0),
        ("communication_skills", 10.1),
        ("ml_knowledge", 10.1),
        ("system_design", 10.1),
    ],
)
def test_api_rejects_values_above_the_permitted_ranges(field, value):
    payload = {**VALID_PAYLOAD, field: value}

    assert client.post("/api/salary-predict", json=payload).status_code == 422


@pytest.mark.parametrize(
    "overrides",
    [
        {"cgpa": 0.0},
        {"cgpa": 10.0},
        {"coding_skills": 0.0},
        {"coding_skills": 10.0},
        {"aptitude_score": 0.0},
        {"aptitude_score": 100.0},
        {"communication_skills": 0.0},
        {"communication_skills": 10.0},
        {"dsa_score": 0.0},
        {"ml_knowledge": 10.0},
        {"system_design": 0.0},
        {"backlogs": 0},
        {"internships": 0},
        {"projects_count": 0},
        {"certifications": 0},
        {"hackathons": 0},
        {"open_source_contributions": 0},
        {"extracurriculars": 0},
    ],
)
def test_api_accepts_valid_boundary_values(overrides):
    payload = {**VALID_PAYLOAD, **overrides}

    response = client.post("/api/salary-predict", json=payload)

    assert response.status_code == 200

    low, high = _training_target_range()
    value = response.json()["predicted_salary_lpa"]

    assert math.isfinite(value)
    assert low <= value <= high


@pytest.mark.parametrize(
    "field",
    [
        "cgpa",
        "backlogs",
        "coding_skills",
        "aptitude_score",
        "internships",
        "projects_count",
        "extracurriculars",
    ],
)
def test_api_rejects_missing_numeric_fields(field):
    payload = {k: v for k, v in VALID_PAYLOAD.items() if k != field}

    assert client.post("/api/salary-predict", json=payload).status_code == 422


@pytest.mark.parametrize(
    "field",
    [
        "cgpa",
        "backlogs",
        "coding_skills",
        "aptitude_score",
        "internships",
        "projects_count",
        "extracurriculars",
    ],
)
def test_api_rejects_null_numeric_fields(field):
    payload = {**VALID_PAYLOAD, field: None}

    assert client.post("/api/salary-predict", json=payload).status_code == 422


def test_api_rejects_missing_branch():
    payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "branch"}

    assert client.post("/api/salary-predict", json=payload).status_code == 422


def test_api_response_contract_and_scale():
    response = client.post("/api/salary-predict", json=VALID_PAYLOAD)

    assert response.status_code == 200

    body = response.json()

    assert set(body) == {"predicted_salary_lpa", "model_version"}
    assert isinstance(body["predicted_salary_lpa"], float)
    assert body["model_version"] == "placepro-salary-v2"

    low, high = _training_target_range()

    assert low <= body["predicted_salary_lpa"] <= high
