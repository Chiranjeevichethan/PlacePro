"""Authentication endpoint factories.

Main installs real sessions behind the unconditional private gate. The isolated
29.6.2 foundation contract is retained separately and never issues a session.
"""
from fastapi import APIRouter, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from ..schemas_auth import LoginRequest, RegistrationRequest, RegistrationResponse
from ..services.account_service import AccountService, InvalidCredentials
from ..services.account_store import AccountStorageError
from ..services.password_service import PasswordServiceUnavailable

UNAVAILABLE = "Account sign-in is unavailable until secure sessions and CSRF protection are implemented."


def create_auth_router(service: AccountService | None = None) -> APIRouter:
    class FoundationRoute(APIRoute):
        def get_route_handler(self):
            original = super().get_route_handler()

            async def handler(request):
                if service is None:
                    return JSONResponse(status_code=503, content={"detail": UNAVAILABLE},
                                        headers={"Cache-Control": "private, no-store"})
                try:
                    response = await original(request)
                except RequestValidationError:
                    # FastAPI's default errors include password inputs/JSON bodies.
                    response = JSONResponse(status_code=422, content={"detail": "Invalid authentication request. Check the email and password requirements."})
                response.headers["Cache-Control"] = "private, no-store"
                return response

            return handler

    result = APIRouter(prefix="/api/auth", tags=["authentication foundation"], route_class=FoundationRoute)

    @result.post("/register", status_code=202, response_model=RegistrationResponse,
                 summary="Staged registration; production endpoint disabled",
                 responses={503: {"description": "Foundation disabled or account processing unavailable"}})
    def register(body: RegistrationRequest):
        try:
            service.register(body.email, body.password.get_secret_value())
        except (AccountStorageError, PasswordServiceUnavailable):
            raise HTTPException(status_code=503, detail="Account processing is temporarily unavailable.",
                                headers={"Cache-Control": "private, no-store", "Retry-After": "1"}) from None
        return RegistrationResponse()

    @result.post("/login", status_code=503, summary="Credential verification only; no session is issued",
                 responses={401: {"description": "Invalid credentials"},
                            503: {"description": "Secure sessions unavailable; no login success"}})
    def login(body: LoginRequest):
        try:
            service.verify_credentials(body.email, body.password.get_secret_value())
        except InvalidCredentials:
            raise HTTPException(status_code=401, detail="Invalid credentials.",
                                headers={"Cache-Control": "private, no-store"}) from None
        except (AccountStorageError, PasswordServiceUnavailable):
            raise HTTPException(status_code=503, detail="Account processing is temporarily unavailable.",
                                headers={"Cache-Control": "private, no-store", "Retry-After": "1"}) from None
        # Never serialize internal account identity or return authenticated success.
        raise HTTPException(status_code=503, detail=UNAVAILABLE,
                            headers={"Cache-Control": "private, no-store"})

    return result


def create_google_router(google):
    """Google OAuth entry points; the provider proves the account's email."""
    from fastapi import Request, Response
    from ..security import single_cookie
    from ..services.account_store import AccountStorageError
    from ..services.google_auth import GoogleAuthError
    from ..services.password_service import PasswordServiceUnavailable
    from ..services.session_service import SessionCapacity

    class GoogleRoute(APIRoute):
        def get_route_handler(self):
            original = super().get_route_handler()

            async def handler(request):
                response = await original(request)
                response.headers['Cache-Control'] = 'private, no-store'
                return response

            return handler

    result = APIRouter(prefix='/api/auth/google', tags=['google authentication'],
                       route_class=GoogleRoute)

    @result.get('/start', summary='Begin Google OAuth 2.0 authorization code flow')
    def start(response: Response):
        if not google.enabled:
            raise HTTPException(status_code=503,
                                detail='Google sign-in is not configured on this server.',
                                headers={'Cache-Control': 'private, no-store'})
        return {'authorization_url': google.begin(response)}

    @result.get('/callback', summary='Google OAuth 2.0 redirect endpoint')
    def callback(request: Request, code: str | None = None,
                 state: str | None = None, error: str | None = None):
        security = google.security
        try:
            secret = google.complete(single_cookie(request, security.oauth_cookie), state, code, error,
                                     previous_secret=single_cookie(request, security.cookie_name))[0]
        except GoogleAuthError as failure:
            response = google.redirect('auth_error', failure.reason)
        except SessionCapacity:
            response = google.redirect('auth_error', 'google_session_limit')
        except (AccountStorageError, PasswordServiceUnavailable):
            response = google.redirect('auth_error', 'google_unavailable')
        else:
            response = google.redirect('auth', 'google')
            security.set_cookie(response, secret)
        security.clear_oauth_cookie(response)
        response.headers['Cache-Control'] = 'private, no-store'
        return response

    return result


def create_session_router(accounts, sessions, config):
    """Real session contract; the application always installs the private gate."""
    from fastapi import Request, Response
    from starlette.concurrency import run_in_threadpool
    from ..security import single_cookie
    from ..services.session_service import InvalidSession, InvalidCSRF, SessionCapacity, csrf_token

    class SessionRoute(APIRoute):
        def get_route_handler(self):
            original = super().get_route_handler()

            async def handler(request):
                try:
                    if request.url.path == '/api/auth/login':
                        tokens = request.headers.getlist('x-csrf-token')
                        await run_in_threadpool(sessions.begin_login, single_cookie(request,config.challenge_cookie),
                                                tokens[0] if len(tokens)==1 else None)
                        # Bound authentication request buffering; never echo bodies.
                        body = bytearray()
                        async for chunk in request.stream():
                            body.extend(chunk)
                            if len(body) > 16384:
                                return JSONResponse({'detail':'Authentication request is too large.'},status_code=413,
                                                    headers={'Cache-Control':'private, no-store'})
                        request._body = bytes(body)
                    response = await original(request)
                except RequestValidationError:
                    response = JSONResponse({'detail':'Invalid authentication request. Check the email and password requirements.'},status_code=422)
                except InvalidCredentials:
                    response = JSONResponse({'detail':'Invalid credentials.'},status_code=401)
                except InvalidSession:
                    response = JSONResponse({'detail':'Authentication is required.'},status_code=401)
                except InvalidCSRF:
                    response = JSONResponse({'detail':'CSRF validation failed.'},status_code=403)
                except SessionCapacity:
                    response = JSONResponse({'detail':'Active session limit reached.'},status_code=409)
                except (AccountStorageError, PasswordServiceUnavailable):
                    response = JSONResponse({'detail':'Account processing is temporarily unavailable.'},status_code=503,
                                            headers={'Retry-After':'1'})
                response.headers['Cache-Control'] = 'private, no-store'
                return response
            return handler

    result = APIRouter(prefix='/api/auth',tags=['authentication'],route_class=SessionRoute)

    @result.post('/register',status_code=503)
    def register():
        raise HTTPException(503,'Registration is unavailable until approved email verification is implemented.')

    @result.get('/login-challenge')
    def login_challenge(response: Response):
        secret, token = sessions.challenge()
        config.set_cookie(response,secret,challenge=True)
        return {'csrf_token':token}

    @result.post('/login')
    def login(body: LoginRequest, request: Request, response: Response):
        proof = accounts.verify_credentials(body.email,body.password.get_secret_value())
        secret, identity = sessions.create(proof,single_cookie(request,config.challenge_cookie),request.headers.get('x-csrf-token'),
                                          previous_secret=single_cookie(request,config.cookie_name))
        config.set_cookie(response,secret)
        config.clear_cookie(response,challenge=True)
        return identity.public()

    @result.get('/session')
    def current_session(request: Request):
        return sessions.touch(single_cookie(request,config.cookie_name)).public()

    @result.get('/csrf')
    def csrf(request: Request):
        secret = single_cookie(request,config.cookie_name)
        identity = sessions.touch(secret)
        return {'csrf_token':csrf_token(secret,identity.csrf_nonce)}

    @result.post('/session/renew')
    def renew(request: Request, response: Response):
        secret, identity = sessions.rotate(single_cookie(request,config.cookie_name),request.headers.get('x-csrf-token'))
        config.set_cookie(response,secret)
        return identity.public()

    @result.post('/logout',status_code=204)
    def logout(request: Request):
        secret = single_cookie(request,config.cookie_name)
        if secret is not None:
            tokens = request.headers.getlist('x-csrf-token')
            sessions.logout(secret,tokens[0] if len(tokens)==1 else None)
        elif config.cookie_name+'=' in request.headers.get('cookie',''):
            raise InvalidSession()
        response = Response(status_code=204)
        config.clear_cookie(response)
        config.clear_cookie(response,challenge=True)
        return response

    return result


router = create_auth_router()  # Retained isolated foundation contract; main uses real sessions.
