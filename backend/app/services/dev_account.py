"""Local development student account provisioning.

The development credential exists only in an explicitly selected development
runtime and is created through this backend mechanism, never from frontend
code. Passwords are hashed by the existing Argon2id service and no password or
hash is ever logged or returned. Accounts are never duplicated and an existing
account's password is never silently replaced.
"""
import os

from .account_service import AccountService
from .account_validation import normalize_account_email, validate_password
from .account_store import AccountStorageError
from .identity_store import IdentityStore
from .password_service import PasswordServiceUnavailable

DEFAULT_DEVELOPMENT_EMAIL = 'student@placepro.com'
EMAIL_VARIABLE = 'PLACEPRO_DEV_STUDENT_EMAIL'
PASSWORD_VARIABLE = 'PLACEPRO_DEV_STUDENT_PASSWORD'
# Development fixtures accept 8-128 characters so the documented local
# credential can exist; student registration keeps the 15-character minimum.
DEVELOPMENT_MINIMUM_PASSWORD = 8


class DevelopmentAccountError(Exception):
    """Provisioning refused; the message never contains a password or hash."""


def configured_credentials():
    """Return (email, password) when configured, else None; never a partial pair."""
    email = os.environ.get(EMAIL_VARIABLE, '').strip()
    password = os.environ.get(PASSWORD_VARIABLE, '')
    if not email and not password:
        return None
    if not email:
        email = DEFAULT_DEVELOPMENT_EMAIL
    if not password:
        raise DevelopmentAccountError(
            f'{PASSWORD_VARIABLE} is required when {EMAIL_VARIABLE} is set.')
    return email, password


def provision_development_student(accounts: AccountService, config):
    """Idempotently ensure the local development student account is ACTIVE.

    Returns a small status mapping, or None when provisioning is not
    configured. Never runs in production mode and never rewrites an existing
    account's password, status or hash.
    """
    configured = configured_credentials()
    if config.mode != 'development':
        if configured is not None:
            raise DevelopmentAccountError(
                'Local development student provisioning requires PLACEPRO_SECURITY_MODE=development.')
        return None
    if configured is None:
        return None
    raw_email, password = configured
    try:
        email = normalize_account_email(raw_email)
        validate_password(password, minimum=DEVELOPMENT_MINIMUM_PASSWORD)
    except ValueError as error:
        raise DevelopmentAccountError(str(error)) from None
    try:
        store = accounts.store
        account = store.get_by_email(email)
        created = False
        if account is None:
            accounts.create_development_account(email, password,
                                                minimum=DEVELOPMENT_MINIMUM_PASSWORD)
            account = store.get_by_email(email)
            if account is None:
                raise DevelopmentAccountError('The development account could not be created.')
            created = True
        activated = False
        if account.status == 'PENDING_EMAIL':
            if not store.activate_pending(account.account_id):
                raise DevelopmentAccountError('The development account could not be activated.')
            activated = True
            account = store.get_by_email(email)
        if account is None or account.status != 'ACTIVE' or not account.email_verified_at:
            raise DevelopmentAccountError(
                'A student account with this email exists but is not active; '
                'it was not changed by development provisioning.')
        IdentityStore(store).record_origin(account.account_id, 'LOCAL_DEVELOPMENT')
    except (AccountStorageError, PasswordServiceUnavailable):
        raise DevelopmentAccountError(
            'Account storage is temporarily unavailable; no development account was created.') from None
    return {'email': email, 'created': created, 'activated': activated,
            'origin': 'LOCAL_DEVELOPMENT'}
