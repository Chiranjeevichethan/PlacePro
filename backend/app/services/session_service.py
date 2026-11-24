"""Opaque sessions; credentials alone never select or authorize student resources."""
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import math
import re
import secrets
import time
import uuid

from .account_service import InvalidCredentials
from .session_store import SessionStore, InvalidSession, SessionExpired
from .security_config import SecurityConfig

TOKEN = re.compile(r'^[A-Za-z0-9_-]{43}$')


class InvalidCSRF(Exception):
    pass


class SessionCapacity(Exception):
    pass


def digest(secret):
    return hashlib.sha256(secret.encode('ascii')).hexdigest()


def csrf_token(secret, nonce):
    return hmac.new(secret.encode('ascii'), ('placepro-csrf:' + nonce).encode('ascii'), hashlib.sha256).hexdigest()


def valid_secret(secret):
    return isinstance(secret, str) and TOKEN.fullmatch(secret) is not None


def token_matches(secret, nonce, token):
    return (isinstance(token, str) and len(token) == 64 and token.isascii()
            and hmac.compare_digest(csrf_token(secret, nonce), token))


def utc(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


@dataclass(frozen=True, repr=False)
class SessionIdentity:
    account_id: str
    email: str
    session_id: str
    family_id: str
    csrf_nonce: str
    idle_expires_at: float
    absolute_expires_at: float

    def public(self):
        return {'account': {'account_id': self.account_id, 'email': self.email},
                'idle_expires_at': utc(self.idle_expires_at), 'absolute_expires_at': utc(self.absolute_expires_at)}


class SessionService:
    def __init__(self, store: SessionStore, config: SecurityConfig, clock=time.time):
        self.store, self.config, self.clock = store, config, clock

    def _account_valid(self, row, account):
        return (account is not None and account['status'] == 'ACTIVE' and account['email_verified_at']
                and account['auth_version'] == row['auth_version']
                and account['password_changed_at'] == row['password_changed_at'])

    def _valid(self, connection, row, now, *, rotated=False):
        if row and (any(not isinstance(row[key], (int,float)) or not math.isfinite(row[key])
                        for key in ('created_at','last_activity_at','idle_expires_at','absolute_expires_at'))
                    or not isinstance(row['csrf_nonce'],str) or not re.fullmatch('[0-9a-f]{64}',row['csrf_nonce'])):
            raise InvalidSession()
        if not row:
            raise InvalidSession()
        if now >= row['idle_expires_at'] or now >= row['absolute_expires_at']:
            if row['revoked_at'] is None:
                raise SessionExpired(row['session_id'],now)
            raise InvalidSession()
        if row['revoked_at'] is not None and not (rotated and row['revocation_reason'] in {'ROTATED', 'LOGOUT'}):
            raise InvalidSession()
        account = self.store.account(connection, row['account_id'])
        if not self._account_valid(row, account):
            raise InvalidSession()
        return account

    def _identity(self, row, account):
        return SessionIdentity(account['account_id'], account['email_normalized'], row['session_id'], row['family_id'],
                               row['csrf_nonce'], row['idle_expires_at'], row['absolute_expires_at'])

    def resolve(self, secret):
        if not valid_secret(secret):
            raise InvalidSession()
        with self.store.transaction() as connection:
            row = self.store.session(connection, digest(secret), self.config.mode)
            account = self._valid(connection, row, self.clock())
            return self._identity(row, account)

    def validate_identity(self, connection, identity):
        """Recheck a gate-issued identity in a short resource-acceptance transaction."""
        if connection is None or not isinstance(identity,SessionIdentity):
            raise InvalidSession()
        record=connection.execute('SELECT * FROM sessions WHERE session_id=? AND context=?',
                                  (identity.session_id,self.config.mode)).fetchone()
        row=dict(record) if record else None
        account=self._valid(connection,row,self.clock())
        if account['account_id']!=identity.account_id or row['family_id']!=identity.family_id:
            raise InvalidSession()
        return account

    def touch(self, secret):
        """Only approved requests renew activity, never gate-denied domain requests."""
        if not valid_secret(secret):
            raise InvalidSession()
        now = self.clock()
        with self.store.transaction(write=True) as connection:
            row = self.store.session(connection, digest(secret), self.config.mode)
            account = self._valid(connection, row, now)
            if now - row['last_activity_at'] >= self.config.activity_seconds:
                row['last_activity_at'] = now
                row['idle_expires_at'] = min(now + self.config.idle_seconds, row['absolute_expires_at'])
                connection.execute('UPDATE sessions SET last_activity_at=?,idle_expires_at=? WHERE session_id=?',
                                   (now, row['idle_expires_at'], row['session_id']))
            return self._identity(row, account)

    def challenge(self):
        secret, nonce, now = secrets.token_urlsafe(32), secrets.token_hex(32), self.clock()
        with self.store.transaction(write=True) as connection:
            # Only expired anonymous challenges are removed; never account/history records.
            connection.execute('DELETE FROM login_challenges WHERE expires_at <= ?', (now,))
            connection.execute('INSERT INTO login_challenges VALUES (?,?,?,?,?,0,NULL)',
                               (digest(secret), nonce, self.config.mode, now, now + self.config.challenge_seconds))
        return secret, csrf_token(secret, nonce)

    def _challenge(self, connection, secret, token, now):
        row = connection.execute('SELECT * FROM login_challenges WHERE secret_hash=? AND context=?',
                                 (digest(secret), self.config.mode)).fetchone()
        if (not row or row['consumed_at'] is not None or now >= row['expires_at'] or row['attempts'] >= 5
                or not token_matches(secret, row['csrf_nonce'], token)):
            raise InvalidCSRF()
        return row

    def begin_login(self, secret, token):
        if not valid_secret(secret):
            raise InvalidCSRF()
        with self.store.transaction(write=True) as connection:
            self._challenge(connection, secret, token, self.clock())
            connection.execute('UPDATE login_challenges SET attempts=attempts+1 WHERE secret_hash=?', (digest(secret),))

    def create(self, proof, challenge_secret, token, previous_secret=None):
        if not valid_secret(challenge_secret):
            raise InvalidCSRF()
        now = self.clock()
        with self.store.transaction(write=True) as connection:
            # begin_login increments attempts before bounded credential work. Permit fifth completion.
            challenge = connection.execute('SELECT * FROM login_challenges WHERE secret_hash=? AND context=?',
                                           (digest(challenge_secret), self.config.mode)).fetchone()
            if (not challenge or challenge['consumed_at'] is not None or now >= challenge['expires_at']
                    or not 1 <= challenge['attempts'] <= 5 or not token_matches(challenge_secret, challenge['csrf_nonce'], token)):
                raise InvalidCSRF()
            account = self.store.account(connection, proof.account_id)
            if (not account or account['status'] != 'ACTIVE' or not account['email_verified_at']
                    or account['auth_version'] != proof.auth_version or account['password_changed_at'] != proof.password_changed_at):
                raise InvalidCredentials()
            previous = self._previous(connection, previous_secret, now)
            secret, row = self._issue(connection, account, now, previous)
            connection.execute('UPDATE login_challenges SET consumed_at=? WHERE secret_hash=?', (now,digest(challenge_secret)))
            return secret, self._identity(row,account)

    def create_for_verified_account(self, account_id, previous_secret=None):
        """Issue a session after an external flow proved the account's email.

        The single-use OAuth state/nonce is the CSRF proof, so no login challenge
        is consumed. Account status/version are rechecked in the same write
        transaction that persists the session.
        """
        now = self.clock()
        with self.store.transaction(write=True) as connection:
            account = self.store.account(connection, account_id)
            if not account or account['status'] != 'ACTIVE' or not account['email_verified_at']:
                raise InvalidCredentials()
            previous = self._previous(connection, previous_secret, now)
            secret, row = self._issue(connection, account, now, previous)
            return secret, self._identity(row,account)

    def _previous(self, connection, secret, now):
        if not valid_secret(secret):
            return None
        previous = self.store.session(connection,digest(secret),self.config.mode)
        if previous:
            try:
                self._valid(connection,previous,now)
            except InvalidSession:
                return None
        return previous

    def _issue(self, connection, account, now, previous=None):
        active = connection.execute('SELECT family_id FROM sessions WHERE account_id=? AND revoked_at IS NULL '
                                    'AND idle_expires_at>? AND absolute_expires_at>? ORDER BY created_at',
                                    (account['account_id'],now,now)).fetchall()
        count = sum(not previous or old[0] != previous['family_id'] for old in active)
        if count >= self.config.max_sessions:
            raise SessionCapacity()
        if previous:
            connection.execute("UPDATE sessions SET revoked_at=?,revocation_reason='REPLACED' WHERE family_id=? AND revoked_at IS NULL",
                               (now,previous['family_id']))
        return self._new_row_in(connection, account, now)

    def _new_row_in(self, connection, account, now, *, family=None, absolute=None):
        secret = secrets.token_urlsafe(32)
        absolute = absolute if absolute is not None else now+self.config.absolute_seconds
        row = dict(session_id=str(uuid.uuid4()),family_id=family or str(uuid.uuid4()),account_id=account['account_id'],
                   secret_hash=digest(secret),csrf_nonce=secrets.token_hex(32),context=self.config.mode,
                   auth_version=account['auth_version'],password_changed_at=account['password_changed_at'],
                   created_at=now,last_activity_at=now,idle_expires_at=min(now+self.config.idle_seconds,absolute),
                   absolute_expires_at=absolute,revoked_at=None,revocation_reason=None)
        self.store.insert_session(connection,row)
        return secret,row

    def check_csrf(self, secret, identity, token):
        if not token_matches(secret, identity.csrf_nonce, token):
            raise InvalidCSRF()

    def rotate(self, secret, token):
        if not valid_secret(secret):
            raise InvalidSession()
        now = self.clock()
        with self.store.transaction(write=True) as connection:
            row = self.store.session(connection,digest(secret),self.config.mode)
            account = self._valid(connection,row,now)
            if not token_matches(secret,row['csrf_nonce'],token):
                raise InvalidCSRF()
            connection.execute("UPDATE sessions SET revoked_at=?,revocation_reason='ROTATED' WHERE session_id=?",(now,row['session_id']))
            replacement, new = self._new_row_in(connection,account,now,family=row['family_id'],absolute=row['absolute_expires_at'])
            return replacement,self._identity(new,account)

    def logout(self, secret, token):
        """Old rotated token can only revoke its family, never resolve/read/renew."""
        if not valid_secret(secret):
            raise InvalidSession()
        now = self.clock()
        with self.store.transaction(write=True) as connection:
            row = self.store.session(connection,digest(secret),self.config.mode)
            self._valid(connection,row,now,rotated=True)
            if not token_matches(secret,row['csrf_nonce'],token):
                raise InvalidCSRF()
            connection.execute("UPDATE sessions SET revoked_at=?,revocation_reason='LOGOUT' WHERE family_id=? AND revoked_at IS NULL",
                               (now,row['family_id']))

    def revoke_account(self, account_id):
        """Internal future password/deactivation hook; no public endpoint."""
        with self.store.transaction(write=True) as connection:
            connection.execute("UPDATE sessions SET revoked_at=?,revocation_reason='ACCOUNT' WHERE account_id=? AND revoked_at IS NULL",
                               (self.clock(),account_id))
