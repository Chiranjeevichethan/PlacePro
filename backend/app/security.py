"""Central fail-closed ASGI boundary, before request parsing or domain side effects.

No bypass option exists. Ownership stages will explicitly authorize domain routes.
"""
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Match
from starlette.concurrency import run_in_threadpool
from fastapi.routing import iter_route_contexts

from .services.account_store import AccountStorageError
from .services.session_service import InvalidSession, InvalidCSRF

OWNERSHIP_PENDING = 'Student operations are unavailable pending ownership enforcement.'
PUBLIC = {('GET','/health'), ('GET','/api/companies'), ('GET','/api/companies/{company_id}')}
ENTRY = {('POST','/api/auth/register'), ('GET','/api/auth/login-challenge'), ('POST','/api/auth/login')}
SESSION = {('GET','/api/auth/session'), ('GET','/api/auth/csrf'),
           ('POST','/api/auth/logout'), ('POST','/api/auth/session/renew')}
# Google sign-in entry points: no PlacePro session yet. The callback is a
# top-level provider redirect, so its CSRF proof is the single-use state
# cookie/nonce pair rather than an Origin header.
OAUTH = {('GET','/api/auth/google/start'), ('GET','/api/auth/google/callback')}
PROFILES = {('GET','/api/account/profiles'),('GET','/api/profile/{profile_id}'),('PUT','/api/profile/{profile_id}'),
            ('POST','/api/profile/from-resume'),('POST','/api/profile/verify'),
            ('POST','/api/profile/{profile_id}/resume-preview'),
            ('GET','/api/profile/{profile_id}/resume-builder'),
            ('PUT','/api/profile/{profile_id}/resume-builder'),
            ('POST','/api/profile/{profile_id}/resume-builder/import'),
            ('POST','/api/profile/{profile_id}/resume-builder/export.pdf')}
ASSESSMENTS = {('POST','/api/assessment/start'),('POST','/api/assessment/{assessment_id}/submit'),
               ('GET','/api/assessment/{assessment_id}'),('GET','/api/profile/{profile_id}/assessments')}
ANALYTICS = {('POST','/api/experimental/v1/predict'),('POST','/api/predict'),('POST','/api/salary-predict'),('POST','/api/profile/{profile_id}/predict'),
             *[('GET','/api/profile/{profile_id}/'+suffix) for suffix in
               ('readiness','placement-summary','eligibility','eligibility/{company_id}','recommendations','skills','performance')]}
GOALS = {('GET','/api/profile/{profile_id}/goals'), ('POST','/api/profile/{profile_id}/goals'),
         ('PUT','/api/profile/{profile_id}/goals/{goal_id}'), ('DELETE','/api/profile/{profile_id}/goals/{goal_id}'),
         ('POST','/api/profile/{profile_id}/goals/{goal_id}/milestones'),
         ('PUT','/api/profile/{profile_id}/goals/{goal_id}/milestones/{milestone_id}'),
         ('DELETE','/api/profile/{profile_id}/goals/{goal_id}/milestones/{milestone_id}'),
         ('GET','/api/profile/{profile_id}/notifications'),
         ('GET','/api/profile/{profile_id}/notifications/unread-count'),
         ('PUT','/api/profile/{profile_id}/notifications/{notification_id}'),
         ('POST','/api/profile/{profile_id}/notifications/read-all')}
SIDE_EFFECT_GET = {'/api/assessment/{assessment_id}', '/api/profile/{profile_id}/assessments'}
DOCS = {'/docs','/docs/oauth2-redirect','/redoc','/openapi.json'}


def csrf_required(method, path):
    return method not in {'GET','HEAD','OPTIONS'} or path in SIDE_EFFECT_GET


def single_cookie(request, name):
    # Ambiguous duplicate cookies must not be resolved differently by components.
    parts = [part.strip() for raw in request.headers.getlist('cookie') for part in raw.split(';')]
    matches = [p.split('=',1)[1] for p in parts if p.split('=',1)[0] == name and '=' in p]
    return matches[0] if len(matches) == 1 else None


class PrivateGate:
    def __init__(self, app, *, routes, sessions, config):
        self.app, self.routes, self.sessions, self.config = app, routes, sessions, config

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'websocket':
            await send({'type':'websocket.close','code':1008})
            return
        if scope['type'] != 'http':
            await self.app(scope,receive,send)
            return
        request = Request(scope)
        path, method = scope['path'], scope['method']
        route, match = None, Match.NONE
        for candidate in iter_route_contexts(self.routes):
            candidate_match, _ = candidate.matches(scope)
            if candidate_match == Match.FULL:
                route, match = candidate, candidate_match
                break
            if candidate_match == Match.PARTIAL and match == Match.NONE:
                route, match = candidate, candidate_match
        template = route.path if route else path
        operation = (method,template)

        async def reject(code, detail):
            await JSONResponse({'detail':detail},status_code=code,
                               headers={'Cache-Control':'private, no-store'})(scope,receive,send)

        if operation in PUBLIC and match == Match.FULL:
            await self.app(scope,receive,send)
            return
        if path in DOCS:
            if (self.config.mode == 'development' and method in {'GET','HEAD'} and match == Match.FULL
                    and self.config.transport_allowed(request) and self.config.origin_allowed(request)):
                await self.app(scope,receive,send)
            else:
                await reject(404,'Not found.')
            return
        if match == Match.NONE and not path.startswith('/api'):
            await reject(404,'Not found.')
            return
        if operation in OAUTH and match == Match.FULL:
            if not self.config.transport_allowed(request):
                await reject(403,'Secure transport is required.')
                return
            if operation == ('GET','/api/auth/google/start') and not self.config.origin_allowed(request,required=True):
                await reject(403,'Request origin is not allowed.')
                return
            await self.app(scope,receive,send)
            return
        if (operation not in ENTRY and operation != ('POST','/api/auth/logout')
                and single_cookie(request,self.config.cookie_name) is None):
            await reject(401,'Authentication is required.')
            return
        if not self.config.transport_allowed(request):
            await reject(403,'Secure transport is required.')
            return
        if not self.config.origin_allowed(request):
            await reject(403,'Request origin is not allowed.')
            return
        if operation == ('POST','/api/auth/register') and match == Match.FULL:
            await reject(503,'Registration is unavailable until approved email verification is implemented.')
            return
        if operation in ENTRY and match == Match.FULL:
            if not self.config.origin_allowed(request,required=True):
                await reject(403,'Request origin is not allowed.')
                return
            await self.app(scope,receive,send)
            return
        # Logout owns its transactional validation, including rotation/logout races.
        if operation == ('POST','/api/auth/logout') and match == Match.FULL:
            if not self.config.origin_allowed(request,required=True):
                await reject(403,'Request origin is not allowed.')
                return
            await self.app(scope,receive,send)
            return
        secret = single_cookie(request,self.config.cookie_name)
        try:
            identity = await run_in_threadpool(self.sessions.resolve,secret)
            if csrf_required(method,template):
                if not self.config.origin_allowed(request,required=True):
                    raise InvalidCSRF()
                tokens = request.headers.getlist('x-csrf-token')
                await run_in_threadpool(self.sessions.check_csrf,secret,identity,tokens[0] if len(tokens)==1 else None)
            if match == Match.NONE:
                await reject(404,'Not found.')
            elif match == Match.PARTIAL:
                await reject(405,'Method not allowed.')
            elif operation not in SESSION | PROFILES | ASSESSMENTS | ANALYTICS | GOALS:
                await reject(503,OWNERSHIP_PENDING)
            else:
                if operation == ('GET','/api/auth/csrf') and not self.config.origin_allowed(request,required=True):
                    raise InvalidCSRF()
                scope.setdefault('state',{})['authenticated_account'] = identity
                await self.app(scope,receive,send)
        except InvalidSession:
            await reject(401,'Authentication is required.')
        except InvalidCSRF:
            await reject(403,'CSRF validation failed.')
        except AccountStorageError:
            await reject(503,'Authentication storage is temporarily unavailable.')
