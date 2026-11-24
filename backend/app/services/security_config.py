"""Fail-closed deployment policy; HTTP development must be explicitly selected."""
from dataclasses import dataclass
import os
from urllib.parse import urlsplit

LOOPBACK = frozenset({'localhost', '127.0.0.1', '::1'})


@dataclass(frozen=True)
class SecurityConfig:
    mode: str = 'production'
    origins: tuple[str, ...] = ()
    idle_seconds: int = 1800
    absolute_seconds: int = 43200
    activity_seconds: int = 30
    challenge_seconds: int = 300
    max_sessions: int = 10

    def __post_init__(self):
        if self.mode not in {'production', 'development'}:
            raise ValueError('Invalid security mode.')
        for origin in self.origins:
            parsed = urlsplit(origin)
            if (not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query
                    or parsed.fragment or origin == 'null' or '*' in origin
                    or parsed.scheme not in {'http', 'https'}):
                raise ValueError('Allowed origins must be explicit origins without paths.')
            if self.mode == 'production' and parsed.scheme != 'https':
                raise ValueError('Production origins require HTTPS.')
            if self.mode == 'development' and parsed.hostname not in LOOPBACK:
                raise ValueError('Development origins require loopback hosts.')
            _ = parsed.port  # Validate invalid ports, too.
        if (not 60 <= self.idle_seconds <= self.absolute_seconds <= 604800
                or not 0 <= self.activity_seconds < self.idle_seconds
                or not 30 <= self.challenge_seconds <= 600 or not 1 <= self.max_sessions <= 50):
            raise ValueError('Invalid session lifetime or capacity.')

    @classmethod
    def from_environment(cls):
        mode = os.environ.get('PLACEPRO_SECURITY_MODE', 'production')
        default = 'http://127.0.0.1:5173' if mode == 'development' else ''
        origins = tuple(p.strip() for p in os.environ.get('PLACEPRO_ALLOWED_ORIGINS', default).split(',') if p.strip())
        return cls(mode=mode, origins=origins,
                   idle_seconds=int(os.environ.get('PLACEPRO_SESSION_IDLE_SECONDS', '1800')),
                   absolute_seconds=int(os.environ.get('PLACEPRO_SESSION_ABSOLUTE_SECONDS', '43200')))

    @property
    def secure(self):
        return self.mode == 'production'

    @property
    def cookie_name(self):
        return '__Host-placepro_session' if self.secure else 'placepro_dev_session'

    @property
    def challenge_cookie(self):
        return '__Host-placepro_login' if self.secure else 'placepro_dev_login'

    @property
    def oauth_cookie(self):
        return '__Host-placepro_oauth' if self.secure else 'placepro_dev_oauth'

    def transport_allowed(self, request):
        if self.secure:
            return request.url.scheme == 'https'
        return (request.url.hostname in LOOPBACK and request.url.scheme in {'http', 'https'}
                and request.client is not None and request.client.host in {'127.0.0.1','::1'})

    def origin_allowed(self, request, required=False):
        values = request.headers.getlist('origin')
        if not values:
            return not required
        return len(values) == 1 and values[0] in self.origins

    def set_cookie(self, response, secret, *, challenge=False):
        response.set_cookie(self.challenge_cookie if challenge else self.cookie_name, secret,
                            max_age=self.challenge_seconds if challenge else None,
                            path='/', secure=self.secure, httponly=True, samesite='lax')

    def clear_cookie(self, response, *, challenge=False):
        response.delete_cookie(self.challenge_cookie if challenge else self.cookie_name,
                               path='/', secure=self.secure, httponly=True, samesite='lax')

    def set_oauth_cookie(self, response, secret):
        response.set_cookie(self.oauth_cookie, secret, max_age=self.challenge_seconds,
                            path='/', secure=self.secure, httponly=True, samesite='lax')

    def clear_oauth_cookie(self, response):
        response.delete_cookie(self.oauth_cookie, path='/', secure=self.secure,
                               httponly=True, samesite='lax')
