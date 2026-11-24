"""Synthetic domain regression harness, deliberately not a deployment application.

Retains pre-auth API/business assertions without any production bypass. Production
security tests must import backend.app.main, never this harness.
"""
from fastapi import FastAPI
import os
from pathlib import Path
from backend.app.routes import predict, resume, profile, readiness, eligibility, recommendation, assessment, performance, salary
from src.pipeline import MODEL_VERSION

# Refuse accidental use against the project stores, even outside pytest.
_paths = [Path(os.environ[key]).resolve() if os.environ.get(key) else None for key in
          ('PLACEPRO_PROFILES_DIR','PLACEPRO_ASSESSMENTS_DIR','PLACEPRO_COMPANIES_DB','PLACEPRO_AUTH_DB','PLACEPRO_GOALS_DB',
           'PLACEPRO_RESUME_BUILDER_DB')]
_project_data = Path(__file__).resolve().parents[2] / 'data'
if (any(p is None or p.is_relative_to(_project_data) for p in _paths)
        or len({p.parent for p in _paths}) != 1 or not _paths[0].parent.name.startswith('placepro_tests_')):
    raise RuntimeError('Domain regression harness requires isolated test storage.')

app = FastAPI()
for module in (predict,resume,profile,readiness,eligibility,recommendation,assessment,performance,salary):
    app.include_router(module.router)


@app.get('/health')
def health():
    return {'status':'ok','service':'placepro-prediction-api','model_version':MODEL_VERSION}
