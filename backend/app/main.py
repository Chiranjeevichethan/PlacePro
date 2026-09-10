# ============================================================
# PLACEPRO - PHASE 8 - PREDICTION API
# ============================================================
#
# Start the server (from the project root):
#     uvicorn backend.app.main:app --reload
#
# Endpoints:
#     GET  /health      -> server + model status
#     POST /api/predict -> placement prediction
#     GET  /docs        -> interactive Swagger docs
#
# ============================================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes.predict import router as predict_router
from .routes.resume import router as resume_router
from .routes.profile import router as profile_router
from .routes.readiness import router as readiness_router
from .routes.eligibility import router as eligibility_router
from .routes.recommendation import router as recommendation_router
from .routes.assessment import router as assessment_router
from .routes.performance import router as performance_router
from src.pipeline import MODEL_VERSION

app = FastAPI(
    title="PlacePro Prediction API",
    description="AI-based student placement prediction (Phase 8 final pipeline).",
    version="1.0.0",
)

# CORS: open for development - the web frontend calls this API.
# Tighten before production deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(predict_router)
app.include_router(resume_router)
app.include_router(profile_router)
app.include_router(readiness_router)
app.include_router(eligibility_router)
app.include_router(recommendation_router)
app.include_router(assessment_router)
app.include_router(performance_router)


@app.get("/health", tags=["health"])
def health():
    """Liveness + model readiness check."""
    return {
        "status": "ok",
        "service": "placepro-prediction-api",
        "model_version": MODEL_VERSION,
    }
