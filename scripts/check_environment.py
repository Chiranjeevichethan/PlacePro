"""Read-only dependency/import/model preflight; never initialise application stores."""

import argparse
import importlib
from importlib import metadata
import json
import math
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[1]


def read_pins(path):
    pins = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line.startswith("-r "):
            pins.update(read_pins(path.parent / line[3:].strip()))
        elif line:
            name, version = line.split("==", 1)
            if name in pins and pins[name] != version:
                raise ValueError(f"Conflicting dependency pins: {name}")
            pins[name] = version
    return pins


def dependency_errors(pins):
    errors = []
    for name, expected in pins.items():
        try:
            actual = metadata.version(name)
        except metadata.PackageNotFoundError:
            errors.append(f"Missing {name}=={expected}")
            continue
        if actual != expected:
            errors.append(f"{name}: installed {actual}, expected {expected}")
    return errors


def model_smoke():
    from src.pipeline import DEFAULT_MODEL_PATH, predict_placement
    from backend.app.services.salary_prediction_service import MODEL_PATH, predict_salary

    for value in (DEFAULT_MODEL_PATH, MODEL_PATH):
        if not Path(value).is_file():
            raise FileNotFoundError(
                f"Missing required model: {value}. Restore the trusted project artifact; "
                "do not run training as a setup fix."
            )
    inputs = {
        "branch": "CSE", "college_tier": "Tier-1", "cgpa": 8.5,
        "backlogs": 0, "coding_skills": 8.2, "dsa_score": 8.0,
        "aptitude_score": 85.0, "communication_skills": 7.5,
        "ml_knowledge": 6.5, "system_design": 5.0, "internships": 2,
        "projects_count": 4, "certifications": 2, "hackathons": 1,
        "open_source_contributions": 1, "extracurriculars": 1,
    }
    placement = predict_placement(inputs)
    salary = predict_salary(inputs)
    probability = placement["placement_probability"]
    if not math.isfinite(probability) or not 0 <= probability <= 1:
        raise ValueError("Placement smoke returned an invalid probability")
    if not math.isfinite(salary["predicted_salary_lpa"]):
        raise ValueError("Salary smoke returned an invalid prediction")
    return {"placement": placement, "salary": salary}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--development", action="store_true", help="Also check test tools")
    parser.add_argument("--models", action="store_true", help="Load existing models and infer once")
    args = parser.parse_args(argv)
    expected = (ROOT / ".python-version").read_text().strip()
    if platform.python_version() != expected or platform.machine().lower() not in {"amd64", "x86_64"}:
        print(f"Use CPython {expected} Windows x64 for the validated environment. "
              f"Selected: {platform.python_version()} {platform.machine()} ({sys.executable})",
              file=sys.stderr)
        return 1
    manifest = ROOT / ("requirements-dev.txt" if args.development else "requirements.txt")
    errors = dependency_errors(read_pins(manifest))
    if errors:
        print("\n".join(errors), file=sys.stderr)
        print(f"Install with the selected interpreter: python -m pip install -r {manifest.name}",
              file=sys.stderr)
        return 1
    sys.path.insert(0, str(ROOT))
    try:
        for name in ("backend.app.main", "docx", "pypdf", "python_multipart"):
            importlib.import_module(name)
        if args.development:
            importlib.import_module("starlette.testclient")
        if args.models:
            print(json.dumps(model_smoke(), indent=2))
    except Exception as exc:
        print(f"Preflight failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(f"Preflight passed: Python {expected}; {len(read_pins(manifest))} pinned packages; "
          f"application imports OK ({sys.executable}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
