"""Account foundation only: credential success is not a session or permission."""
from dataclasses import dataclass

from .account_store import AccountStore
from .account_validation import normalize_account_email, validate_password
from .password_service import PasswordService


class InvalidCredentials(Exception):
    def __init__(self):
        super().__init__("Invalid credentials.")


@dataclass(frozen=True, repr=False)
class CredentialVerification:
    """Internal input for future session creation; never serialized by this phase."""
    account_id: str
    auth_version: int
    password_changed_at: str


class AccountService:
    def __init__(self, store: AccountStore, passwords: PasswordService | None = None):
        self.store = store
        self.passwords = passwords or PasswordService()

    def register(self, email: str, password: str) -> None:
        email = normalize_account_email(email)
        validate_password(password)
        # All valid requests hash before the UNIQUE insert, including duplicates.
        # A duplicate never replaces an existing hash/status or confirms its email.
        encoded = self.passwords.hash_password(password)
        self.store.create_account(email, encoded)

    def create_development_account(self, email: str, password: str, *, minimum: int) -> None:
        """Provision a local development fixture through the normal hash path.

        Public registration keeps its own policy; only the explicitly
        development-gated provisioning caller supplies a lower minimum.
        """
        email = normalize_account_email(email)
        validate_password(password, minimum=minimum)
        encoded = self.passwords.hash_password(password, minimum=minimum)
        self.store.create_account(email, encoded)

    def verify_credentials(self, email: str, password: str) -> CredentialVerification:
        try:
            email = normalize_account_email(email)
            validate_password(password, minimum=1)
        except ValueError:
            raise InvalidCredentials() from None
        account = self.store.get_by_email(email)
        matches = self.passwords.verify_password(account.password_hash if account else None, password)
        if not matches or account is None or account.status != "ACTIVE" or not account.email_verified_at:
            raise InvalidCredentials()
        accepted_hash = account.password_hash
        if self.passwords.needs_rehash(accepted_hash):
            replacement = self.passwords.hash_password(password)
            if not self.store.upgrade_hash(account, replacement):
                raise InvalidCredentials()
            accepted_hash = replacement
        current = self.store.get_by_email(email)
        if (current is None or current.account_id != account.account_id or current.auth_version != account.auth_version
                or current.password_hash != accepted_hash or current.status != "ACTIVE" or not current.email_verified_at):
            raise InvalidCredentials()
        # Future session acceptance must recheck version/status transactionally.
        return CredentialVerification(current.account_id, current.auth_version, current.password_changed_at)
