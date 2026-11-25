"""Ownership-secured profile transport; the original domain router stays intact."""
import json
import re

from fastapi import APIRouter,File,Form,UploadFile,Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as FormHTTPException

from ..schemas_owned_profile import OwnedProfileRequest,OwnedProfileResponse,OwnedResumeResponse
from ..services.ownership_store import OwnershipNotFound,OwnershipConflict,OwnershipUnavailable
from ..services.session_service import InvalidSession
from ..services.profile_service import ProfileNotFoundError,ProfileServiceError
from ..services.resume_service import MAX_FILE_SIZE,ResumeServiceError
from .profile import DRAFT_MESSAGE
from ..services.retry_integrity import request_key

NOT_FOUND='Profile not found.'
INVALID='Invalid profile request. Review the fields and revision.'


def create_owned_profile_router(service):
    class OwnedRoute(APIRoute):
        def get_route_handler(self):
            original=super().get_route_handler()
            async def handler(request):
                form=None
                try:
                    identity=getattr(request.state,'authenticated_account',None)
                    if identity is None:
                        raise InvalidSession()
                    profile_id=request.path_params.get('profile_id')
                    if profile_id is not None:
                        if request.url.path.endswith('/resume-preview'):
                            await run_in_threadpool(service.get,identity,profile_id)
                        else:
                            await run_in_threadpool(service.authorize,identity,profile_id)
                    if request.method == 'POST' and request.url.path.endswith(('/from-resume','/resume-preview')):
                        # Bound the multipart request before Starlette spools uploaded files.
                        body=bytearray()
                        async for chunk in request.stream():
                            if len(body)+len(chunk)>MAX_FILE_SIZE+64*1024:
                                return JSONResponse({'detail':'Resume upload is too large. Maximum file size is 5 MB.'},
                                                    status_code=413,headers={'Cache-Control':'private, no-store'})
                            body.extend(chunk)
                        request._body=bytes(body)
                        form=await request.form()
                        preview=request.url.path.endswith('/resume-preview')
                        if set(form)!= ({'file','revision'} if preview else {'file'}) or len(form.getlist('file'))!=1:
                            raise RequestValidationError([])
                        if preview and (len(form.getlist('revision'))!=1 or
                                        not isinstance(form['revision'],str) or
                                        not re.fullmatch(r'[1-9][0-9]{0,9}',form['revision'])):
                            raise RequestValidationError([])
                    elif request.method in {'POST','PUT'}:
                        body=bytearray()
                        async for chunk in request.stream():
                            body.extend(chunk)
                            if len(body)>1024*1024:
                                return JSONResponse({'detail':'Profile request is too large.'},status_code=413,
                                                    headers={'Cache-Control':'private, no-store'})
                        request._body=bytes(body)
                        raw=json.loads(request._body)
                        if not isinstance(raw,dict):
                            raise RequestValidationError([])
                        # Resolve a verify target before any profile-field validation.
                        if request.url.path.endswith('/verify') and raw.get('profile_id') is not None:
                            await run_in_threadpool(service.authorize,identity,raw['profile_id'])
                    request.state.retry_key=request_key(request) if request.method in {'POST','PUT'} else None
                    response=await original(request)
                except (OwnershipNotFound,ProfileNotFoundError):
                    response=JSONResponse({'detail':NOT_FOUND},status_code=404)
                except InvalidSession:
                    response=JSONResponse({'detail':'Authentication is required.'},status_code=401)
                except OwnershipConflict:
                    response=JSONResponse({'detail':'Profile creation could not be completed.'},status_code=409)
                except OwnershipUnavailable:
                    response=JSONResponse({'detail':'Profile access is temporarily unavailable.'},status_code=503)
                except (RequestValidationError,json.JSONDecodeError,UnicodeDecodeError):
                    response=JSONResponse({'detail':INVALID},status_code=422)
                except FormHTTPException as error:
                    response=JSONResponse({'detail':'Invalid upload request.'},status_code=error.status_code
                                          if error.status_code in {400,413} else 503)
                except ResumeServiceError as error:
                    messages={400:'The resume file is empty or invalid.',
                              413:'Resume file is too large. Maximum size is 5 MB.',
                              415:'Upload a PDF or DOCX resume with a matching file type.',
                              422:'Resume could not be extracted. Upload a readable, valid PDF or DOCX.'}
                    response=JSONResponse({'detail':messages.get(error.status_code,'Resume processing failed.')},
                                          status_code=error.status_code)
                except ProfileServiceError as error:
                    response=JSONResponse({'detail':str(error)},status_code=error.status_code)
                except Exception:
                    # Do not disclose filesystem errors, private JSON or extraction internals.
                    response=JSONResponse({'detail':'Profile processing is temporarily unavailable.'},status_code=503)
                finally:
                    if form is not None:
                        await form.close()
                response.headers['Cache-Control']='private, no-store'
                return response
            return handler

    router=APIRouter(tags=['owned profiles'],route_class=OwnedRoute)

    @router.get('/api/account/profiles')
    def owned_profiles(request:Request):
        return service.list_owned(request.state.authenticated_account)

    @router.get('/api/profile/{profile_id}',response_model=OwnedProfileResponse)
    def get(profile_id:str,request:Request):
        profile,completion=service.get(request.state.authenticated_account,profile_id)
        return {'profile':profile,'completion':completion,'message':'Profile retrieved.'}

    @router.put('/api/profile/{profile_id}',response_model=OwnedProfileResponse)
    def update(profile_id:str,body:OwnedProfileRequest,request:Request):
        profile,completion=service.update(request.state.authenticated_account,profile_id,body.model_dump(),request_id=request.state.retry_key)
        return {'profile':profile,'completion':completion,'message':'Profile updated. Re-confirm the profile to verify it.'}

    @router.post('/api/profile/verify',response_model=OwnedProfileResponse)
    def verify(body:OwnedProfileRequest,request:Request):
        identity=request.state.authenticated_account
        if body.profile_id is None:
            profile,completion=service.create_confirmed(identity,body.model_dump(),request_id=request.state.retry_key)
        else:
            profile,completion=service.update(identity,body.profile_id,body.model_dump(),confirming=True,request_id=request.state.retry_key)
        message=('Profile verified. All ML-required fields are available.' if completion['profile_complete'] else
                 f"Profile verified, but {len(completion['missing_fields'])} ML-required field(s) still need manual input before a prediction can be made.")
        return {'profile':profile,'completion':completion,'message':message}

    @router.post('/api/profile/from-resume',response_model=OwnedResumeResponse)
    async def from_resume(request:Request,file:UploadFile=File(...)):
        content=await file.read(MAX_FILE_SIZE+1)
        if len(content)>MAX_FILE_SIZE:
            return JSONResponse({'detail':f'File too large. Maximum size is {MAX_FILE_SIZE//(1024*1024)} MB.'},status_code=413)
        profile,completion,analysis=await run_in_threadpool(service.create_resume,request.state.authenticated_account,
                                                          file.filename or '',content,file.content_type,request.state.retry_key)
        return {'profile':profile,'completion':completion,'message':DRAFT_MESSAGE,
                'provenance':analysis['provenance'],'confidence':analysis['confidence'],'diagnostics':analysis['diagnostics'],
                'extraction_summary':analysis['extraction_summary'],'feature_availability':analysis['completeness']['feature_availability']}

    @router.post('/api/profile/{profile_id}/resume-preview',response_model=OwnedResumeResponse)
    async def resume_preview(profile_id:str,request:Request,file:UploadFile=File(...),revision:int=Form(...)):
        content=await file.read(MAX_FILE_SIZE+1)
        profile,completion,analysis=await run_in_threadpool(service.preview_resume,request.state.authenticated_account,
            profile_id,revision,file.filename or '',content,file.content_type)
        return {'profile':profile,'completion':completion,
                'message':'Extraction only. Choose which fields to use, correct them, then confirm to update this profile.',
                'provenance':analysis['provenance'],'confidence':analysis['confidence'],'diagnostics':analysis['diagnostics'],
                'extraction_summary':analysis['extraction_summary'],'feature_availability':analysis['completeness']['feature_availability']}

    return router
