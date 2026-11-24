"""Authenticated stateless forms and ownership-enforced profile analytics."""
from typing import Optional

from fastapi import APIRouter, Request, Header, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.concurrency import run_in_threadpool

from ..schemas import StudentProfile, PredictionResponse
from ..schemas_salary import SalaryPredictionRequest, SalaryPredictionResponse
from ..schemas_profile import ProfilePredictionResponse
from ..schemas_readiness import ReadinessResponse, PlacementSummaryResponse
from ..schemas_recommendation import RecommendationsResponse
from ..schemas_eligibility import CompanyEligibilityResponse, AllCompanyEligibilityResponse, CompanySummary, CompanyDetail
from ..schemas_performance import PerformanceResponse
from ..schemas_assessment import SkillsViewResponse
from ..services import prediction_service, salary_prediction_service
from ..services.ownership_store import OwnershipNotFound, OwnershipUnavailable
from ..services.session_service import InvalidSession
from ..services.profile_service import ProfileServiceError, ProfileNotFoundError
from ..services.assessment_service import AssessmentStorageError
from ..services.owned_analytics_service import AnalyticsUnavailable
from ..services.readiness_service import ReadinessServiceError
from ..services.recommendation_service import RecommendationServiceError
from ..services.eligibility_service import EligibilityServiceError, CompanyNotFoundError
from ..services.performance_service import PerformanceServiceError
from .eligibility import companies_list, companies_detail


def create_owned_analytics_router(service):
    class OwnedRoute(APIRoute):
        def get_route_handler(self):
            original=super().get_route_handler()
            async def handler(request):
                try:
                    identity=getattr(request.state,'authenticated_account',None)
                    if identity is None:
                        raise InvalidSession()
                    profile_id=request.path_params.get('profile_id')
                    if profile_id is not None:
                        await run_in_threadpool(service.authorize,identity,profile_id)
                    if request.method=='POST' and profile_id is not None:
                        keys=request.headers.getlist('idempotency-key')
                        if len(keys)>1 or (keys and (not keys[0] or len(keys[0])>128)):
                            raise RequestValidationError([])
                    response=await original(request)
                except (OwnershipNotFound,ProfileNotFoundError):
                    response=JSONResponse({'detail':'Profile not found.'},status_code=404)
                except InvalidSession:
                    response=JSONResponse({'detail':'Authentication is required.'},status_code=401)
                except (OwnershipUnavailable,AnalyticsUnavailable,AssessmentStorageError,FileNotFoundError):
                    response=JSONResponse({'detail':'Student analysis is temporarily unavailable.'},status_code=503)
                except RequestValidationError:
                    response=JSONResponse({'detail':'Invalid analysis request.'},status_code=422)
                except CompanyNotFoundError:
                    response=JSONResponse({'detail':'Company not found.'},status_code=404)
                except (ProfileServiceError,ReadinessServiceError,EligibilityServiceError,RecommendationServiceError,PerformanceServiceError) as error:
                    messages={409:'The prediction request is no longer current. Refresh before predicting.',
                              422:'A verified profile with valid fields is required.',503:'Student analysis is temporarily unavailable.'}
                    response=JSONResponse({'detail':messages.get(error.status_code,'Student analysis could not be completed.')},status_code=error.status_code)
                except Exception:
                    response=JSONResponse({'detail':'Student analysis is temporarily unavailable.'},status_code=503)
                response.headers['Cache-Control']='private, no-store'
                return response
            return handler

    router=APIRouter(tags=['owned analytics'],route_class=OwnedRoute)

    @router.post('/api/predict',response_model=PredictionResponse)
    def form_predict(body:StudentProfile,request:Request):
        # Approved independent calculation: no profile lookup, association or history.
        return prediction_service.predict(body.model_dump())

    @router.post('/api/salary-predict',response_model=SalaryPredictionResponse)
    def form_salary(body:SalaryPredictionRequest,request:Request):
        return salary_prediction_service.predict_salary(body.model_dump())

    @router.post('/api/profile/{profile_id}/predict',response_model=ProfilePredictionResponse)
    def profile_predict(profile_id:str,request:Request,idempotency_key:str|None=Header(default=None,max_length=128)):
        return service.predict(request.state.authenticated_account,profile_id,idempotency_key)

    @router.get('/api/profile/{profile_id}/readiness',response_model=ReadinessResponse)
    def readiness(profile_id:str,request:Request):
        return service.read(request.state.authenticated_account,profile_id,'readiness')

    @router.get('/api/profile/{profile_id}/placement-summary',response_model=PlacementSummaryResponse)
    def summary(profile_id:str,request:Request):
        return service.read(request.state.authenticated_account,profile_id,'placement-summary')

    @router.get('/api/profile/{profile_id}/eligibility',response_model=AllCompanyEligibilityResponse)
    def eligibility(profile_id:str,request:Request):
        return service.read(request.state.authenticated_account,profile_id,'eligibility')

    @router.get('/api/profile/{profile_id}/eligibility/{company_id}',response_model=CompanyEligibilityResponse)
    def company_eligibility(profile_id:str,company_id:str,request:Request):
        return service.read(request.state.authenticated_account,profile_id,'company-eligibility',company_id=company_id)

    @router.get('/api/profile/{profile_id}/recommendations',response_model=RecommendationsResponse)
    def recommendations(profile_id:str,request:Request,limit:Optional[int]=Query(None,ge=1,le=50)):
        return service.read(request.state.authenticated_account,profile_id,'recommendations',limit=limit)

    @router.get('/api/profile/{profile_id}/skills',response_model=SkillsViewResponse)
    def skills(profile_id:str,request:Request):
        return service.read(request.state.authenticated_account,profile_id,'skills')

    @router.get('/api/profile/{profile_id}/performance',response_model=PerformanceResponse)
    def performance(profile_id:str,request:Request):
        return service.read(request.state.authenticated_account,profile_id,'performance')

    # Public company handlers retain their original models and gate classification.
    public=APIRouter(tags=['eligibility'])
    public.add_api_route('/api/companies',companies_list,methods=['GET'],response_model=list[CompanySummary])
    public.add_api_route('/api/companies/{company_id}',companies_detail,methods=['GET'],response_model=CompanyDetail)
    router.include_router(public)
    return router
