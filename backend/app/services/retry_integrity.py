"""Account-scoped request fingerprints; existing JSON stores remain authoritative."""
import hashlib
import json
import uuid

from fastapi.exceptions import RequestValidationError


def request_key(request):
    values = request.headers.getlist('idempotency-key')
    if len(values) > 1 or (values and (not values[0].strip() or len(values[0]) > 128)):
        raise RequestValidationError([])
    return values[0] if values else None


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def request_identity(identity, operation, resource, key):
    return fingerprint([identity.account_id, operation, resource, key])


def creation_id(identity, operation, key):
    # A server-derived resource UUID, never an authentication secret or ownership proof.
    # Unkeyed creation retains random uuid4. A keyed retry finds the same reservation,
    # including a PENDING reservation; it never attaches an existing legacy record.
    digest = bytes.fromhex(request_identity(identity, operation, None, key))
    return str(uuid.UUID(bytes=digest[:16], version=4))
