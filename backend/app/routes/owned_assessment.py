"""Secured assessment transport; original domain routes remain isolated regressions."""
import json

from fastapi import APIRouter, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import ConfigDict
from starlette.concurrency import run_in_threadpool

from ..schemas_assessment import (StartAssessmentRequest, SubmitAssessmentRequest,
                                 StartAssessmentResponse, SubmitAssessmentResponse, AssessmentHistoryResponse)
from ..services.ownership_store import OwnershipNotFound, OwnershipUnavailable
from ..services.session_service import InvalidSession
from ..services.assessment_service import (AssessmentError, AssessmentNotFoundError, AssessmentOwnershipError,
                                         AssessmentRetryError, AssessmentStorageError, UnknownSkillError)
from ..services.profile_service import ProfileNotFoundError, ProfileServiceError
from .assessment import _retry_response
from ..services.retry_integrity import request_key


class OwnedStartRequest(StartAssessmentRequest):
    model_config = ConfigDict(extra='forbid', hide_input_in_errors=True)


class OwnedSubmitRequest(SubmitAssessmentRequest):
    model_config = ConfigDict(extra='forbid', hide_input_in_errors=True)


def create_owned_assessment_router(service):
    class OwnedRoute(APIRoute):
        def get_route_handler(self):
            original = super().get_route_handler()
            async def handler(request):
                try:
                    identity = getattr(request.state, 'authenticated_account', None)
                    if identity is None:
                        raise InvalidSession()
                    assessment_id = request.path_params.get('assessment_id')
                    profile_id = request.path_params.get('profile_id')
                    if assessment_id is not None:
                        access = await run_in_threadpool(service.assessment_access, identity, assessment_id)
                    elif profile_id is not None:
                        await run_in_threadpool(service.profile_access, identity, profile_id)
                    if request.method == 'POST':
                        body = bytearray()
                        async for chunk in request.stream():
                            body.extend(chunk)
                            if len(body) > 1024*1024:
                                return JSONResponse({'detail':'Assessment request is too large.'},status_code=413,
                                                    headers={'Cache-Control':'private, no-store'})
                        request._body = bytes(body)
                        raw = json.loads(request._body)
                        if not isinstance(raw, dict):
                            raise RequestValidationError([])
                        if assessment_id is None:
                            if 'profile_id' in raw:
                                await run_in_threadpool(service.profile_access, identity, raw['profile_id'])
                        elif 'profile_id' in raw and raw['profile_id'] != access.profile_id:
                            raise AssessmentNotFoundError('Assessment not found.')
                    request.state.retry_key=request_key(request) if request.method=='POST' else None
                    response = await original(request)
                except (OwnershipNotFound, ProfileNotFoundError, AssessmentNotFoundError, AssessmentOwnershipError) as error:
                    detail = 'Assessment not found.' if request.path_params.get('assessment_id') is not None else 'Profile not found.'
                    response = JSONResponse({'detail':detail},status_code=404)
                except InvalidSession:
                    response = JSONResponse({'detail':'Authentication is required.'},status_code=401)
                except (OwnershipUnavailable, AssessmentStorageError):
                    response = JSONResponse({'detail':'Assessment storage is temporarily unavailable.'},status_code=503)
                except AssessmentRetryError as error:
                    response = _retry_response(error)
                except UnknownSkillError:
                    response = JSONResponse({'detail':'Unsupported assessment skill.'},status_code=404)
                except (RequestValidationError, json.JSONDecodeError, UnicodeDecodeError):
                    response = JSONResponse({'detail':'Invalid assessment request.'},status_code=422)
                except (AssessmentError, ProfileServiceError) as error:
                    response = JSONResponse({'detail':str(error)},status_code=error.status_code)
                except Exception:
                    response = JSONResponse({'detail':'Assessment processing is temporarily unavailable.'},status_code=503)
                response.headers['Cache-Control'] = 'private, no-store'
                return response
            return handler

    router = APIRouter(prefix='/api', tags=['owned assessments'], route_class=OwnedRoute)

    @router.post('/assessment/start', response_model=StartAssessmentResponse)
    def start(body:OwnedStartRequest, request:Request):
        return service.start(request.state.authenticated_account, body.profile_id, body.skill, body.num_questions,request_id=request.state.retry_key)

    @router.get('/assessment/{assessment_id}')
    def get(assessment_id:str, request:Request):
        return service.get(request.state.authenticated_account, assessment_id)

    @router.post('/assessment/{assessment_id}/submit', response_model=SubmitAssessmentResponse)
    def submit(assessment_id:str, body:OwnedSubmitRequest, request:Request):
        return service.submit(request.state.authenticated_account, assessment_id, body.profile_id, body.answers,request_id=request.state.retry_key)

    @router.get('/profile/{profile_id}/assessments', response_model=AssessmentHistoryResponse)
    def history(profile_id:str, request:Request):
        return service.history(request.state.authenticated_account, profile_id)

    return router
