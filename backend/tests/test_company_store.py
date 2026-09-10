# ============================================================
# PLACEPRO - PHASE 28C - COMPANY STORE TEST SUITE
# ============================================================
#
# Focused tests for the SQLite-backed company store:
#   1.  Initialization (schema created, auto-seeded)
#   2.  Demo seed loading (8 companies, idempotent)
#   3.  Active/inactive filtering (7 active, company_900 inactive)
#   4.  Company lookup (by id, unknown -> None)
#   5.  Requirement-set retrieval (provenance metadata)
#   6.  provided=false behavior (absent fields stay absent)
#   7.  Provenance fields (DEMO labeling end to end)
#   8.  Deterministic results (identical repeated reads, stable order)
#   9.  Compatibility with Phase 13 eligibility + Phase 14 scoring
#       (unchanged weights and threshold; store company dicts behave
#       exactly like the old flat demo dicts)
#
# Run:
#   python -m pytest backend/tests/test_company_store.py -q
#
# Service-level only (no HTTP server required). The store is pointed
# at a temp database so the tests never touch data/companies.db.
#
# ============================================================

import os
import sys
import tempfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BACKEND_ROOT)
sys.path.insert(0, BACKEND_ROOT)
sys.path.insert(0, PROJECT_ROOT)

# Isolate the store DB BEFORE any service use (one temp file per run).
_TMP_DIR = tempfile.mkdtemp(prefix="placepro_companies_store_test_")

from backend.app.services import company_store as store  # noqa: E402

store.reset_for_tests(os.path.join(_TMP_DIR, "companies_test.db"))

from backend.app.services.eligibility_service import (  # noqa: E402
    evaluate_company_eligibility,
)
from backend.app.services.recommendation_service import (  # noqa: E402
    RECOMMENDED_THRESHOLD,
    SCORE_WEIGHTS,
    compute_skill_match,
)

SEED_ACTIVE_IDS = [f"company_{i:03d}" for i in range(1, 8)]  # 001..007
SEED_TOTAL = 8  # 7 active + company_900 (inactive)


# ------------------------------------------------------------
# Minimal verified-style profile (no resume pipeline needed).
# Meets every DemoTech (company_001) requirement incl. preferred.
# ------------------------------------------------------------


def _demotech_eligible_profile() -> dict:
    return {
        "profile_id": "store-test-profile",
        "verified": True,
        "personal": {"name": "Test Student", "email": "test@example.com"},
        "education": {"cgpa": 8.2, "branch": "CSE", "graduation_year": 2026},
        "skills": {"other_skills": ["Python", "SQL", "Data Structures",
                                    "AWS", "Docker"]},
        "internships": [{"company": "X"}],
        "projects": [{"project_name": "P1"}, {"project_name": "P2"}],
        "certifications": [{"name": "AWS Certified Cloud Practitioner"}],
        "achievements": {},
        "ml_inputs": {"backlogs": 0, "aptitude_score": 80.0},
    }


# ------------------------------------------------------------
# 1. INITIALIZATION
# ------------------------------------------------------------


def test_initialization_creates_schema_and_seeds():
    store.initialize()  # already initialized by reset_for_tests
    assert os.path.exists(store.DB_PATH), "database file must exist"

    import sqlite3
    conn = sqlite3.connect(store.DB_PATH)
    try:
        tables = {
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    finally:
        conn.close()
    assert {"companies", "requirement_sets", "requirements"} <= tables


# ------------------------------------------------------------
# 2. DEMO SEED LOADING
# ------------------------------------------------------------


def test_demo_seed_loaded():
    assert store.count_companies() == SEED_TOTAL
    assert store.count_companies(active_only=True) == len(SEED_ACTIVE_IDS)


def test_seeding_idempotent():
    # Re-initializing must NOT duplicate or alter seed rows.
    store._initialized = False
    store.initialize()
    assert store.count_companies() == SEED_TOTAL
    first = store.get_company("company_001")
    second = store.get_company("company_001")
    assert first["requirements"] == second["requirements"]
    assert (first["requirement_set"] == second["requirement_set"])


# ------------------------------------------------------------
# 3. ACTIVE / INACTIVE FILTERING
# ------------------------------------------------------------


def test_active_filtering():
    active = store.get_active_companies()
    ids = [c["company_id"] for c in active]
    assert ids == SEED_ACTIVE_IDS, "active list must match seed, ordered"
    assert "company_900" not in ids, "inactive company must be excluded"

    inactive = store.get_company("company_900")
    assert inactive is not None, "inactive company still resolvable by id"
    assert inactive["active"] is False


# ------------------------------------------------------------
# 4. COMPANY LOOKUP
# ------------------------------------------------------------


def test_company_lookup():
    company = store.get_company("company_001")
    assert company is not None
    assert company["company_name"] == "DemoTech"
    assert company["industry"] == "Software (DEMO requirements)"
    assert company["roles"] == ["Software Engineer"]
    assert company["locations"] == []  # never invented for demo data
    assert store.get_company("company_nope") is None


# ------------------------------------------------------------
# 5. REQUIREMENT-SET RETRIEVAL
# ------------------------------------------------------------


def test_requirement_set_retrieval():
    meta = store.get_requirement_set("company_001")
    assert meta is not None
    assert meta["requirement_set_id"] == "company_001_demo_v1"
    assert meta["source_type"] == "DEMO"
    assert meta["verification_status"] == "DEMO"
    assert meta["source_url"] is None
    assert meta["verified_at"] is None
    assert meta["verified_by"] is None
    assert meta["recruitment_cycle"] is None
    assert "DEMO" in (meta["notes"] or "")
    assert store.get_requirement_set("company_nope") is None


def test_per_field_requirement_view():
    per_field = store.get_requirement_set_requirements("company_001")
    assert set(per_field) == set(store.REQUIREMENT_FIELDS)
    # Provided values survive round-trip (including zero values).
    assert per_field["min_cgpa"] == {"provided": True, "value": 7.5}
    assert per_field["max_backlogs"] == {"provided": True, "value": 0}
    assert per_field["min_certifications"] == {"provided": True, "value": 0}
    assert per_field["required_skills"] == {
        "provided": True,
        "value": ["Python", "SQL", "Data Structures"],
    }
    # company_002 has no allowed_graduation_years / min_certifications
    # in the seed -> explicitly not provided, never a guessed value.
    per_field_002 = store.get_requirement_set_requirements("company_002")
    assert per_field_002["allowed_graduation_years"] == {
        "provided": False, "value": None,
    }
    assert per_field_002["min_certifications"] == {
        "provided": False, "value": None,
    }


# ------------------------------------------------------------
# 6. PROVIDED = FALSE BEHAVIOR (Phase 13 semantics preserved)
# ------------------------------------------------------------


def test_not_provided_fields_stay_absent():
    # Flat company dict: not-provided fields are simply absent, exactly
    # like the old flat demo dicts -> eligibility treats them as
    # "not evaluated" (no requirement check is produced for them).
    company_002 = store.get_company("company_002")
    reqs = company_002["requirements"]
    assert "allowed_graduation_years" not in reqs
    assert "min_certifications" not in reqs
    # Provided fields remain.
    assert reqs["min_cgpa"] == 8.0

    # A required-skills check on a company WITHOUT that field must not
    # invent one: company_900 lacks required_skills entirely.
    company_900 = store.get_company("company_900")
    assert "required_skills" not in company_900["requirements"]
    assert "preferred_skills" not in company_900["requirements"]

    # Eligibility against company_002 for a student with missing
    # graduation-year info: the graduation-year checker must not run
    # (field not provided), so missing_information cannot contain it.
    profile = _demotech_eligible_profile()
    profile["education"]["graduation_year"] = None
    result = evaluate_company_eligibility(profile, company_002)
    labels = {r["requirement"] for r in result["requirements"]["unknown"]}
    assert "Graduation Year" not in labels
    assert "graduation_year" not in result["missing_information"]


# ------------------------------------------------------------
# 7. PROVENANCE FIELDS
# ------------------------------------------------------------


def test_provenance_on_company_dicts():
    for company in store.get_active_companies():
        meta = company["requirement_set"]
        assert meta["source_type"] == "DEMO"
        assert meta["verification_status"] == "DEMO"
        assert meta["source_url"] is None
        assert meta["verified_at"] is None
    demo = store.get_company("company_001")
    assert "NOT official hiring criteria" in demo["notes"]


# ------------------------------------------------------------
# 8. DETERMINISTIC RESULTS
# ------------------------------------------------------------


def test_deterministic_results():
    a = store.get_active_companies()
    b = store.get_active_companies()
    assert a == b, "repeated reads must be identical"
    ids = [c["company_id"] for c in a]
    assert ids == sorted(ids), "stable company order"
    assert store.get_company("company_003") == store.get_company("company_003")


# ------------------------------------------------------------
# 9. COMPATIBILITY WITH EXISTING ENGINES
# ------------------------------------------------------------


def test_weights_and_threshold_unchanged():
    # Documented heuristics - NOT empirically validated; must remain
    # exactly as before Phase 28C.
    assert SCORE_WEIGHTS == {
        "eligibility": 30,
        "skill_match": 25,
        "readiness": 20,
        "placement_probability": 15,
        "profile_completeness": 10,
    }
    assert RECOMMENDED_THRESHOLD == 75.0


def test_eligibility_and_skill_match_against_store():
    profile = _demotech_eligible_profile()
    company = store.get_company("company_001")

    result = evaluate_company_eligibility(profile, company)
    assert result["status"] == "ELIGIBLE"
    assert result["requirements"]["failed"] == []
    assert result["requirements"]["unknown"] == []
    assert "placement_probability" not in result  # ML never used here

    present = {"Python", "SQL", "Data Structures", "AWS", "Docker"}
    match = compute_skill_match(company, present)
    assert match["score"] == 100.0
    assert match["required_missing"] == []
    assert match["preferred_missing"] == []

    # Weak student fails DemoTech exactly as before the store existed.
    weak = _demotech_eligible_profile()
    weak["education"]["cgpa"] = 6.0
    weak_result = evaluate_company_eligibility(weak, company)
    assert weak_result["status"] == "NOT_ELIGIBLE"
    failed = {r["requirement"] for r in weak_result["requirements"]["failed"]}
    assert "Minimum CGPA" in failed


# ------------------------------------------------------------
# MAIN (plain-python entry point, mirrors the other suites)
# ------------------------------------------------------------

if __name__ == "__main__":
    functions = [
        value for name, value in sorted(globals().items())
        if name.startswith("test_") and callable(value)
    ]
    failed = 0
    for fn in functions:
        try:
            fn()
            print(f"  PASS {fn.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"  FAIL {fn.__name__}: {exc}")
    print(f"\n{len(functions) - failed}/{len(functions)} passed")
    sys.exit(1 if failed else 0)
