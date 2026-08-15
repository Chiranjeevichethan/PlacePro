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


@app.get("/health", tags=["health"])
def health():
    """Liveness + model readiness check."""
    return {
        "status": "ok",
        "service": "placepro-prediction-api",
        "model_version": MODEL_VERSION,
    }
