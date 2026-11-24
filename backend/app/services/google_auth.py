"""Google OAuth 2.0 student sign-in (authorization code + PKCE + state + nonce).

Disabled unless GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are configured; no
credential is invented and no Google password is ever requested or stored. The
browser returns only an authorization code. The backend exchanges it directly
with Google over TLS, verifies the returned ID token with Google's tokeninfo
endpoint plus local issuer/audience/expiry/nonce checks, and then creates or
links exactly one ordinary PlacePro student account. That account receives the
same opaque server session as email/password sign-in.
"""
from dataclasses import dataclass, field
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen

from fastapi.responses import RedirectResponse

from .account_service import AccountService
from .account_validation import normalize_account_email
from .identity_store import IdentityStore
from .security_config import SecurityConfig, LOOPBACK
from .session_service import SessionService, valid_secret

AUTHORIZATION_ENDPOINT = 'https://accounts.google.com/o/oauth2/v2/auth'
TOKEN_ENDPOINT = 'https://oauth2.googleapis.com/token'
TOKENINFO_ENDPOINT = 'https://oauth2.googleapis.com/tokeninfo'
CALLBACK_PATH = '/api/auth/google/callback'
ISSUERS = frozenset({'https://accounts.google.com', 'accounts.google.com'})
SCOPES = 'openid email profile'
CLOCK_SKEW = 60
STATE_TTL = 300
SUBJECT = re.compile(r'[!-~]{1,255}\Z')


class GoogleOAuthConfigurationError(ValueError):
    """Startup configuration is incomplete or unsafe; sign-in stays disabled."""


class GoogleAuthError(Exception):
    """Safe, user-facing failure classification; never carries provider detail."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__('Google sign-in could not be completed.')


@dataclass(frozen=True)
class GoogleIdentity:
    subject: str = field(repr=False)
    email: str
    email_verified: bool


@dataclass(frozen=True)
class GoogleOAuthConfig:
    client_id: str = ''
    client_secret: str = field(default='', repr=False)
    redirect_uri: str = ''
    app_url: str = ''

    @property
    def enabled(self) -> bool:
        return bool(self.client_id and self.client_secret and self.redirect_uri and self.app_url)

    @classmethod
    def from_environment(cls, security: SecurityConfig) -> "GoogleOAuthConfig":
        client_id = os.environ.get('GOOGLE_CLIENT_ID', '').strip()
        client_secret = os.environ.get('GOOGLE_CLIENT_SECRET', '').strip()
        if not client_id and not client_secret:
            return cls()
        if not client_id or not client_secret:
            raise GoogleOAuthConfigurationError(
                'Google sign-in requires both GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.')
        redirect_uri = os.environ.get('GOOGLE_REDIRECT_URI', '').strip() or (
            'https://127.0.0.1:8765' if security.secure else 'http://127.0.0.1:8765') + CALLBACK_PATH
        app_url = os.environ.get('PLACEPRO_APP_URL', '').strip() or (
            security.origins[0] if security.origins else '')
        cls._validate(security, redirect_uri, app_url)
        return cls(client_id, client_secret, redirect_uri, app_url.rstrip('/'))

    @staticmethod
    def _validate(security: SecurityConfig, redirect_uri: str, app_url: str) -> None:
        parsed = urlsplit(redirect_uri)
        if (parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username
                or parsed.password or parsed.path != CALLBACK_PATH or parsed.query or parsed.fragment):
            raise GoogleOAuthConfigurationError(
                'GOOGLE_REDIRECT_URI must be an absolute origin plus ' + CALLBACK_PATH + '.')
        if parsed.port is None:
            raise GoogleOAuthConfigurationError('GOOGLE_REDIRECT_URI must include an explicit port.')
        if security.secure and parsed.scheme != 'https':
            raise GoogleOAuthConfigurationError(
                'Production Google sign-in requires an HTTPS redirect URI.')
        if not security.secure and (parsed.scheme != 'http' or parsed.hostname not in LOOPBACK):
            raise GoogleOAuthConfigurationError(
                'Development Google sign-in requires a loopback HTTP redirect URI.')
        if app_url not in security.origins:
            raise GoogleOAuthConfigurationError(
                'PLACEPRO_APP_URL must exactly match one of the configured allowed origins.')


def verify_claims(claims, *, client_id: str, nonce: str, now: float) -> GoogleIdentity:
    """Validate Google's ID-token claims locally after the tokeninfo response.

    Rejects wrong issuer/audience, expired tokens, replayed nonces and
    unverified email addresses. Google's tokeninfo response already verified
    the token signature; these checks bind it to this flow and this client.
    """
    if not isinstance(claims, dict):
        raise GoogleAuthError('google_invalid')
    if claims.get('iss') not in ISSUERS or claims.get('aud') != client_id:
        raise GoogleAuthError('google_invalid')
    if claims.get('azp') not in (None, client_id):
        raise GoogleAuthError('google_invalid')
    try:
        expires = int(claims.get('exp'))
    except (TypeError, ValueError):
        raise GoogleAuthError('google_invalid') from None
    if expires <= now - CLOCK_SKEW:
        raise GoogleAuthError('google_invalid')
    issued = claims.get('iat')
    if issued is not None:
        try:
            issued = int(issued)
        except (TypeError, ValueError):
            raise GoogleAuthError('google_invalid') from None
        if issued > now + CLOCK_SKEW:
            raise GoogleAuthError('google_invalid')
    claimed_nonce = claims.get('nonce')
    if (not isinstance(claimed_nonce, str) or not isinstance(nonce, str)
            or not hmac.compare_digest(claimed_nonce, nonce)):
        raise GoogleAuthError('google_invalid')
    subject = claims.get('sub')
    if not isinstance(subject, str) or not SUBJECT.fullmatch(subject):
        raise GoogleAuthError('google_invalid')
    try:
        email = normalize_account_email(claims.get('email'))
    except ValueError:
        raise GoogleAuthError('google_invalid') from None
    verified = claims.get('email_verified')
    if verified is not True and verified != 'true':
        raise GoogleAuthError('google_unverified')
    return GoogleIdentity(subject, email, True)


class GoogleOAuthClient:
    """Minimal Google HTTP client; tokens and claims are never logged."""

    def __init__(self, config: GoogleOAuthConfig, *, opener=urlopen, clock=time.time, timeout=10):
        self.config, self._open, self.clock, self.timeout = config, opener, clock, timeout

    def authorization_url(self, state: str, nonce: str, code_challenge: str) -> str:
        query = urlencode({
            'client_id': self.config.client_id,
            'redirect_uri': self.config.redirect_uri,
            'response_type': 'code',
            'scope': SCOPES,
            'state': state,
            'nonce': nonce,
            'code_challenge': code_challenge,
            'code_challenge_method': 'S256',
            'access_type': 'online',
            'prompt': 'select_account',
        })
        return AUTHORIZATION_ENDPOINT + '?' + query

    def _json(self, url: str, *, data: bytes | None = None) -> dict:
        headers = {'Accept': 'application/json'}
        if data is not None:
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
        request = Request(url, data=data, headers=headers, method='POST' if data is not None else 'GET')
        try:
            with self._open(request, timeout=self.timeout) as response:
                if response.status != 200:
                    raise GoogleAuthError('google_invalid')
                raw = response.read(65536)
        except GoogleAuthError:
            raise
        except HTTPError as error:
            raise GoogleAuthError('google_invalid' if error.code in (400, 401, 403)
                                  else 'google_unavailable') from None
        except (URLError, OSError):
            raise GoogleAuthError('google_unavailable') from None
        try:
            payload = json.loads(raw.decode('utf-8'))
        except (ValueError, UnicodeError):
            raise GoogleAuthError('google_unavailable') from None
        if not isinstance(payload, dict):
            raise GoogleAuthError('google_unavailable')
        return payload

    def exchange_code(self, code, code_verifier, nonce) -> GoogleIdentity:
        if not isinstance(code, str) or not 1 <= len(code) <= 2048:
            raise GoogleAuthError('google_invalid')
        if not isinstance(code_verifier, str) or not 43 <= len(code_verifier) <= 128:
            raise GoogleAuthError('google_state')
        payload = urlencode({
            'code': code,
            'client_id': self.config.client_id,
            'client_secret': self.config.client_secret,
            'redirect_uri': self.config.redirect_uri,
            'grant_type': 'authorization_code',
            'code_verifier': code_verifier,
        }).encode('ascii')
        tokens = self._json(TOKEN_ENDPOINT, data=payload)
        id_token = tokens.get('id_token')
        if not isinstance(id_token, str) or not 16 <= len(id_token) <= 8192:
            raise GoogleAuthError('google_invalid')
        claims = self._json(TOKENINFO_ENDPOINT + '?id_token=' + quote(id_token, safe=''))
        return verify_claims(claims, client_id=self.config.client_id, nonce=nonce, now=self.clock())


class GoogleAuthService:
    def __init__(self, accounts: AccountService, sessions: SessionService,
                 config: GoogleOAuthConfig, *, security: SecurityConfig | None = None,
                 store: IdentityStore | None = None, client: GoogleOAuthClient | None = None,
                 clock=time.time):
        self.accounts, self.sessions, self.config = accounts, sessions, config
        self.security = security or sessions.config
        self.store = store or IdentityStore(accounts.store)
        self.client = client or GoogleOAuthClient(config, clock=clock)
        self.clock = clock

    @property
    def enabled(self) -> bool:
        return self.config.enabled

    def begin(self, response) -> str:
        """Create single-use state/nonce/PKCE and bind it to an HttpOnly cookie."""
        if not self.enabled:
            raise GoogleAuthError('google_not_configured')
        state, nonce, verifier = (secrets.token_urlsafe(32), secrets.token_hex(32),
                                  secrets.token_urlsafe(64))
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode('ascii')).digest()).rstrip(b'=').decode('ascii')
        self.store.create_challenge(state, nonce, verifier, self.security.mode,
                                    now=self.clock(), ttl=STATE_TTL)
        self.security.set_oauth_cookie(response, state)
        return self.client.authorization_url(state, nonce, challenge)

    def complete(self, state_cookie, state, code, error, *, previous_secret=None):
        """Validate state, exchange the code and issue the ordinary session."""
        if error:
            raise GoogleAuthError('google_denied')
        if not self.enabled:
            raise GoogleAuthError('google_not_configured')
        if not valid_secret(state) or not valid_secret(state_cookie) or not hmac.compare_digest(state, state_cookie):
            raise GoogleAuthError('google_state')
        challenge = self.store.consume_challenge(state, self.security.mode, now=self.clock())
        if challenge is None:
            raise GoogleAuthError('google_state')
        identity = self.client.exchange_code(code, challenge['code_verifier'], challenge['nonce'])
        account_id = self.resolve(identity)
        secret, session = self.sessions.create_for_verified_account(
            account_id, previous_secret=previous_secret)
        return secret, session

    def resolve(self, identity: GoogleIdentity) -> str:
        """Map a verified Google identity to exactly one PlacePro account."""
        if not identity.email_verified:
            raise GoogleAuthError('google_unverified')
        try:
            email = normalize_account_email(identity.email)
        except ValueError:
            raise GoogleAuthError('google_invalid') from None
        for _ in range(2):
            linked = self.store.linked_account('google', identity.subject)
            if linked:
                account = self.accounts.store.get_by_id(linked)
                if not account or account.status != 'ACTIVE' or not account.email_verified_at:
                    raise GoogleAuthError('google_inactive')
                if account.email_normalized != email:
                    raise GoogleAuthError('google_conflict')
                return account.account_id
            account = self.accounts.store.get_by_email(email)
            if account is None:
                # A Google-only account gets a random, immediately discarded
                # local password hash: password sign-in stays impossible for it.
                self.accounts.register(email, secrets.token_urlsafe(32))
                account = self.accounts.store.get_by_email(email)
                if account is None:
                    raise GoogleAuthError('google_unavailable')
                if account.status != 'PENDING_EMAIL' or account.email_verified_at is not None:
                    continue  # Concurrent creation won; resolve again.
                if not self.accounts.store.activate_pending(account.account_id):
                    continue
                self.store.record_origin(account.account_id, 'GOOGLE')
                self.store.link('google', identity.subject, account.account_id)
                return account.account_id
            if not account.email_verified_at:
                # An unverified (pending) account is never linked by an email claim.
                raise GoogleAuthError('google_unverified')
            if account.status != 'ACTIVE':
                raise GoogleAuthError('google_inactive')
            if self.store.account_providers(account.account_id):
                raise GoogleAuthError('google_conflict')
            if self.store.link('google', identity.subject, account.account_id):
                return account.account_id
        raise GoogleAuthError('google_conflict')

    def redirect(self, key: str, value: str) -> RedirectResponse:
        target = f'{self.config.app_url}/?{urlencode({key: value})}'
        return RedirectResponse(target, status_code=303)
