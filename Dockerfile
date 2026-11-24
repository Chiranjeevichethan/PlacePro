# syntax=docker/dockerfile:1
# Build from the repository root; the frontend is hosted separately.
FROM python:3.14.6-slim-bookworm@sha256:4c92ffcde4dd6f1ff72a24518f49fd4990b27134987dfa31a733badde66df9f8

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLACEPRO_SECURITY_MODE=production \
    PLACEPRO_AUTH_DB=/var/lib/placepro/auth/accounts.sqlite3 \
    PLACEPRO_COMPANIES_DB=/var/lib/placepro/companies.db \
    PLACEPRO_GOALS_DB=/var/lib/placepro/goals/goals.sqlite3 \
    PLACEPRO_RESUME_BUILDER_DB=/var/lib/placepro/resume_builder/resume_builder.sqlite3 \
    PLACEPRO_PROFILES_DIR=/var/lib/placepro/profiles \
    PLACEPRO_ASSESSMENTS_DIR=/var/lib/placepro/assessments

WORKDIR /app

# Native Python dependencies use release wheels, not an on-image compiler.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 placepro \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin placepro \
    && install -d -o 10001 -g 10001 -m 0700 /var/lib/placepro

COPY requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir --only-binary=:all: -r requirements.txt \
    && python -m pip check

COPY backend/__init__.py backend/container_start.py ./backend/
COPY backend/app/ ./backend/app/
COPY src/pipeline.py ./src/pipeline.py
COPY experimental/v1/feature_schema.py ./experimental/v1/feature_schema.py
COPY models/placepro_final_model.pkl models/placepro_salary_model_v2.pkl ./models/
COPY experimental/v1/placepro_v1_production_fields.pkl ./experimental/v1/

USER 10001:10001

# Fail the build on broken imports/artifacts; never initialise stores or train.
RUN python -B -c "import backend.app.main; import joblib; from backend.app.services.experimental_v1_service import _load_model; joblib.load('models/placepro_final_model.pkl'); joblib.load('models/placepro_salary_model_v2.pkl'); _load_model()"

EXPOSE 8000
CMD ["python", "-B", "-m", "backend.container_start"]
