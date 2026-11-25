"""Argon2id with bounded work; never log passwords or serialized hashes."""
from contextlib import contextmanager
import secrets
import threading

from argon2 import PasswordHasher, Type, extract_parameters
from argon2.exceptions import HashingError, InvalidHashError, VerificationError

from .account_validation import validate_password

_WORK = threading.BoundedSemaphore(2)


class PasswordServiceUnavailable(Exception):
    """No credentials were accepted; caller may safely retry later."""


@contextmanager
def _bounded_work():
    if not _WORK.acquire(timeout=5):
        raise PasswordServiceUnavailable("Credential processing is temporarily unavailable.")
    try:
        yield
    finally:
        _WORK.release()


class PasswordService:
    def __init__(self):
        self.hasher = PasswordHasher(type=Type.ID, time_cost=3, memory_cost=65536,
                                     parallelism=1, hash_len=32, salt_len=16)
        # A random, non-account dummy hash equalizes unknown-account verification.
        with _bounded_work():
            try:
                self._dummy_hash = self.hasher.hash(secrets.token_urlsafe(32))
            except HashingError:
                raise PasswordServiceUnavailable("Credential processing is temporarily unavailable.") from None

    def hash_password(self, password: str, *, minimum: int = 15) -> str:
        # Public registration keeps the 15-character minimum; only the explicit
        # development fixture provisioning path lowers it.
        validate_password(password, minimum=minimum)
        with _bounded_work():
            try:
                return self.hasher.hash(password)
            except HashingError:
                raise PasswordServiceUnavailable("Credential processing is temporarily unavailable.") from None

    @staticmethod
    def _safe_hash(encoded: str) -> bool:
        # Do not let corrupted records request unbounded memory/CPU from libargon2.
        if not isinstance(encoded, str) or len(encoded) > 512:
            return False
        try:
            p = extract_parameters(encoded)
            return (p.type == Type.ID and p.version == 19 and 8192 <= p.memory_cost <= 131072
                    and 1 <= p.time_cost <= 6 and 1 <= p.parallelism <= 4
                    and 16 <= p.salt_len <= 64 and 16 <= p.hash_len <= 64)
        except (InvalidHashError, ValueError, TypeError):
            return False

    def verify_password(self, encoded: str | None, password: str) -> bool:
        validate_password(password, minimum=1)
        usable = self._safe_hash(encoded)
        target = encoded if usable else self._dummy_hash
        with _bounded_work():
            try:
                matches = self.hasher.verify(target, password)
                return bool(matches and usable)
            except (VerificationError, InvalidHashError):
                return False

    def needs_rehash(self, encoded: str) -> bool:
        if not self._safe_hash(encoded):
            return False
        p = extract_parameters(encoded)
        # check_needs_rehash reports any difference, including stronger costs.
        # Keep those hashes; an automatic parameter upgrade must not weaken them.
        if (p.memory_cost > self.hasher.memory_cost or p.time_cost > self.hasher.time_cost
                or p.hash_len > self.hasher.hash_len or p.salt_len > self.hasher.salt_len):
            return False
        return self.hasher.check_needs_rehash(encoded)
