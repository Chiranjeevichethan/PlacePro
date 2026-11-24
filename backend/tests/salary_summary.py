"""Test-only aggregate provenance; never read or publish training rows."""
from functools import lru_cache
import hashlib
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SUMMARY_PATH = Path(__file__).with_name("fixtures") / "salary_training_summary.json"


@lru_cache(maxsize=1)
def load_salary_summary():
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    assert summary["schema_version"] == 1
    model = summary["provenance"]["model"]
    assert model["path"] == "models/placepro_salary_model_v2.pkl"
    digest = hashlib.sha256((PROJECT_ROOT / model["path"]).read_bytes()).hexdigest()
    assert digest == model["sha256"], "Salary summary provenance does not match the served artifact."
    return summary
