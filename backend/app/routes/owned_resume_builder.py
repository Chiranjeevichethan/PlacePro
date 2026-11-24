"""Authenticated API for the student-owned resume builder and PDF export."""
import json

from fastapi import APIRouter, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.routing import APIRoute
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from ..schemas_resume_builder import ResumeDocument
from ..services.ownership_store import OwnershipNotFound, OwnershipUnavailable
from ..services.resume_builder_service import ResumeBuilderConflict, ResumeBuilderInvalid
from ..services.resume_builder_store import ResumeDraftStorageUnavailable
from ..services.session_service import InvalidSession


def create_owned_resume_builder_router(service):
    class ResumeBuilderRoute(APIRoute):
        def get_route_handler(self):
            original = super().get_route_handler()

            async def handler(request):
                try:
                    identity = getattr(request.state, 'authenticated_account', None)
                    if identity is None:
                        raise InvalidSession()
                    profile_id = request.path_params.get('profile_id')
                    if profile_id is not None:
                        await run_in_threadpool(service.authorize_profile, identity, profile_id)
                    if request.method == 'PUT':
                        body = bytearray()
                        async for chunk in request.stream():
                            body.extend(chunk)
                            if len(body) > 1024 * 1024:
                                return JSONResponse({'detail': 'Resume draft is too large.'}, status_code=413,
                                                    headers={'Cache-Control': 'private, no-store'})
                        request._body = bytes(body)
                        raw = json.loads(request._body)
                        if not isinstance(raw, dict):
                            raise RequestValidationError([])
                    response = await original(request)
                except OwnershipNotFound:
                    response = JSONResponse({'detail': 'Profile not found.'}, status_code=404)
                except InvalidSession:
                    response = JSONResponse({'detail': 'Authentication is required.'}, status_code=401)
                except (OwnershipUnavailable, ResumeDraftStorageUnavailable):
                    response = JSONResponse({'detail': 'Resume storage is temporarily unavailable.'}, status_code=503)
                except ResumeBuilderConflict as error:
                    response = JSONResponse({'detail': str(error)}, status_code=409)
                except ResumeBuilderInvalid as error:
                    response = JSONResponse({'detail': str(error)}, status_code=422)
                except (ValidationError, RequestValidationError, json.JSONDecodeError, UnicodeDecodeError):
                    response = JSONResponse({'detail': 'Invalid resume draft.'}, status_code=422)
                except Exception:
                    response = JSONResponse({'detail': 'Resume builder is temporarily unavailable.'}, status_code=503)
                response.headers['Cache-Control'] = 'private, no-store'
                return response

            return handler

    router = APIRouter(prefix='/api/profile/{profile_id}/resume-builder', tags=['owned resume builder'],
                       route_class=ResumeBuilderRoute)

    @router.get('')
    def get_draft(profile_id: str, request: Request):
        return service.get_draft(request.state.authenticated_account, profile_id)

    @router.put('')
    def save_draft(profile_id: str, body: ResumeDocument, request: Request):
        return service.save(request.state.authenticated_account, profile_id, body.model_dump(mode='json'))

    @router.post('/import')
    def import_profile(profile_id: str, request: Request):
        return service.import_profile(request.state.authenticated_account, profile_id)

    @router.post('/export.pdf')
    def export_pdf(profile_id: str, request: Request):
        pdf = service.export_pdf(request.state.authenticated_account, profile_id)
        return Response(pdf, media_type='application/pdf', headers={
            'Content-Disposition': 'attachment; filename="placepro-resume.pdf"',
            'Cache-Control': 'private, no-store',
            'X-Content-Type-Options': 'nosniff',
        })

    return router
