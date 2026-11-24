# ============================================================
# PLACEPRO - PHASE 8 - PREDICTION API
# ============================================================
#
# Start the server (from the project root):
#     python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8765 --reload
#
# Endpoints:
#     GET  /health      -> server + model status
#     POST /api/predict -> placement prediction
#     GET  /docs        -> interactive Swagger docs
#
# ============================================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes.experimental_v1 import router as experimental_v1_router
from .routes.resume import router as resume_router
from .routes.owned_analytics import create_owned_analytics_router
from .services.owned_analytics_service import OwnedAnalyticsService
from .routes.owned_profile import create_owned_profile_router
from .services.ownership_store import OwnershipStore
from .services.owned_profile_service import OwnedProfileService
from .routes.owned_assessment import create_owned_assessment_router
from .services.owned_assessment_service import OwnedAssessmentService
from .routes.owned_goals import create_owned_goals_router
from .services.goals_service import GoalsService
from .services.goals_store import GoalsStore
from .routes.owned_resume_builder import create_owned_resume_builder_router
from .services.resume_builder_service import ResumeBuilderService
from .services.resume_builder_store import ResumeBuilderStore
from .routes.auth import create_session_router, create_google_router
from .services.account_store import AccountStore
from .services.account_service import AccountService
from .services.dev_account import provision_development_student
from .services.google_auth import GoogleAuthService, GoogleOAuthConfig
from .services.session_store import SessionStore
from .services.session_service import SessionService
from .services.security_config import SecurityConfig
from .security import PrivateGate
from src.pipeline import MODEL_VERSION

def create_app(config=None):
    """Same domain routers, unconditional security gate. Construction writes no DB."""
    config = config or SecurityConfig.from_environment()
    application = FastAPI(
        title="PlacePro Prediction API",
        description="Authenticated form inference and owned profiles, assessments, prediction history and analytics.",
        version="1.0.0",
        docs_url='/docs' if config.mode == 'development' else None,
        redoc_url='/redoc' if config.mode == 'development' else None,
        openapi_url='/openapi.json' if config.mode == 'development' else None,
    )
    accounts = AccountService(AccountStore())
    sessions = SessionService(SessionStore(accounts.store),config)
    google = GoogleAuthService(accounts,sessions,GoogleOAuthConfig.from_environment(config),security=config)
    application.state.accounts = accounts
    application.state.sessions = sessions
    application.state.google_auth = google
    application.state.security_config = config
    # Explicit development mode only; a no-op unless the documented local
    # development student variables are configured.
    if config.mode == 'development':
        provision_development_student(accounts,config)
    owned_profiles=OwnedProfileService(OwnershipStore(sessions))
    application.state.owned_profiles=owned_profiles
    owned_assessments=OwnedAssessmentService(owned_profiles)
    application.state.owned_assessments=owned_assessments
    owned_analytics=OwnedAnalyticsService(owned_assessments)
    application.state.owned_analytics=owned_analytics
    owned_goals=GoalsService(owned_profiles,GoalsStore())
    application.state.owned_goals=owned_goals
    resume_builder=ResumeBuilderService(owned_profiles,ResumeBuilderStore())
    application.state.resume_builder=resume_builder
    application.include_router(experimental_v1_router)
    application.include_router(resume_router)
    application.include_router(create_owned_analytics_router(owned_analytics))
    application.include_router(create_owned_profile_router(owned_profiles))
    application.include_router(create_owned_assessment_router(owned_assessments))
    application.include_router(create_owned_goals_router(owned_goals))
    application.include_router(create_owned_resume_builder_router(resume_builder))
    application.include_router(create_google_router(google))
    application.include_router(create_session_router(accounts,sessions,config))

    @application.get('/health',tags=['health'])
    def health():
        """Static liveness, not proof of models/storage/deployment readiness."""
        return {'status':'ok','service':'placepro-prediction-api','model_version':MODEL_VERSION}

    application.add_middleware(PrivateGate,routes=application.routes,sessions=sessions,config=config)
    # Added last: CORS handles preflight and includes headers on gate responses.
    application.add_middleware(CORSMiddleware,allow_origins=list(config.origins),allow_credentials=True,
                               allow_methods=['GET','POST','PUT','DELETE'],
                               allow_headers=['Content-Type','X-CSRF-Token','Idempotency-Key'],max_age=600)
    return application


app = create_app()
