"""Goal API; authentication, CSRF and profile ownership are checked before parsing."""
import json

from fastapi import APIRouter, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from ..schemas_goals import GoalInput, GoalUpdate, MilestoneInput, MilestoneUpdate
from ..services.goals_service import GoalConflict, GoalNotFound
from ..services.goals_store import GoalStorageUnavailable
from ..services.ownership_store import OwnershipNotFound, OwnershipUnavailable
from ..services.session_service import InvalidSession


class StrictGoalInput(GoalInput):
    model_config = ConfigDict(extra='forbid', hide_input_in_errors=True, str_strip_whitespace=True)


class StrictGoalUpdate(GoalUpdate):
    model_config = ConfigDict(extra='forbid', hide_input_in_errors=True, str_strip_whitespace=True)


class StrictMilestoneInput(MilestoneInput):
    model_config = ConfigDict(extra='forbid', hide_input_in_errors=True, str_strip_whitespace=True)


class StrictMilestoneUpdate(MilestoneUpdate):
    model_config = ConfigDict(extra='forbid', hide_input_in_errors=True, str_strip_whitespace=True)


class StrictNotificationRead(BaseModel):
    model_config = ConfigDict(extra='forbid', hide_input_in_errors=True)
    read: bool = Field(strict=True)


def create_owned_goals_router(service):
    class GoalsRoute(APIRoute):
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
                    if request.method in {'POST', 'PUT'}:
                        body = bytearray()
                        async for chunk in request.stream():
                            body.extend(chunk)
                            if len(body) > 64 * 1024:
                                return JSONResponse({'detail': 'Goal request is too large.'}, status_code=413,
                                                    headers={'Cache-Control': 'private, no-store'})
                        request._body = bytes(body)
                        raw = json.loads(request._body)
                        if not isinstance(raw, dict):
                            raise RequestValidationError([])
                    response = await original(request)
                except (OwnershipNotFound, GoalNotFound):
                    response = JSONResponse({'detail': 'Goal or profile not found.'}, status_code=404)
                except InvalidSession:
                    response = JSONResponse({'detail': 'Authentication is required.'}, status_code=401)
                except (OwnershipUnavailable, GoalStorageUnavailable):
                    response = JSONResponse({'detail': 'Goal storage is temporarily unavailable.'}, status_code=503)
                except GoalConflict as error:
                    response = JSONResponse({'detail': str(error)}, status_code=409)
                except (RequestValidationError, json.JSONDecodeError, UnicodeDecodeError):
                    response = JSONResponse({'detail': 'Invalid goal or milestone request.'}, status_code=422)
                except Exception:
                    response = JSONResponse({'detail': 'Goal service is temporarily unavailable.'}, status_code=503)
                response.headers['Cache-Control'] = 'private, no-store'
                return response

            return handler

    router = APIRouter(prefix='/api', tags=['owned goals'], route_class=GoalsRoute)

    @router.get('/profile/{profile_id}/goals')
    def list_goals(profile_id: str, request: Request):
        return service.list_goals(request.state.authenticated_account, profile_id)

    @router.post('/profile/{profile_id}/goals', status_code=201)
    def create_goal(profile_id: str, body: StrictGoalInput, request: Request):
        return service.create_goal(request.state.authenticated_account, profile_id, body.model_dump())

    @router.put('/profile/{profile_id}/goals/{goal_id}')
    def update_goal(profile_id: str, goal_id: str, body: StrictGoalUpdate, request: Request):
        return service.update_goal(request.state.authenticated_account, profile_id, goal_id,
                                   body.model_dump(exclude_unset=True))

    @router.delete('/profile/{profile_id}/goals/{goal_id}', status_code=204)
    def delete_goal(profile_id: str, goal_id: str, request: Request):
        service.delete_goal(request.state.authenticated_account, profile_id, goal_id)

    @router.post('/profile/{profile_id}/goals/{goal_id}/milestones', status_code=201)
    def create_milestone(profile_id: str, goal_id: str, body: StrictMilestoneInput, request: Request):
        return service.create_milestone(request.state.authenticated_account, profile_id, goal_id, body.model_dump())

    @router.put('/profile/{profile_id}/goals/{goal_id}/milestones/{milestone_id}')
    def update_milestone(profile_id: str, goal_id: str, milestone_id: str,
                         body: StrictMilestoneUpdate, request: Request):
        return service.update_milestone(request.state.authenticated_account, profile_id, goal_id, milestone_id,
                                        body.model_dump(exclude_unset=True))

    @router.delete('/profile/{profile_id}/goals/{goal_id}/milestones/{milestone_id}', status_code=204)
    def delete_milestone(profile_id: str, goal_id: str, milestone_id: str, request: Request):
        service.delete_milestone(request.state.authenticated_account, profile_id, goal_id, milestone_id)

    @router.get('/profile/{profile_id}/notifications')
    def list_notifications(profile_id: str, request: Request, unread_only: bool = False):
        return service.list_notifications(request.state.authenticated_account, profile_id, unread_only)

    @router.get('/profile/{profile_id}/notifications/unread-count')
    def unread_count(profile_id: str, request: Request):
        return {'unread_count': service.unread_notification_count(request.state.authenticated_account, profile_id)}

    @router.put('/profile/{profile_id}/notifications/{notification_id}')
    def mark_notification_read(profile_id: str, notification_id: str, body: StrictNotificationRead, request: Request):
        if not body.read:
            raise RequestValidationError([])
        return {'unread_count': service.mark_notification_read(request.state.authenticated_account,
                                                                profile_id, notification_id)}

    @router.post('/profile/{profile_id}/notifications/read-all')
    def mark_all_read(profile_id: str, request: Request):
        return {'unread_count': service.mark_all_notifications_read(request.state.authenticated_account, profile_id)}

    return router
