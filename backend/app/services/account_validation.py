"""Narrow account email/password policy; independent of resume contact parsing."""
from email.headerregistry import Address
from email.errors import HeaderParseError
import re

import idna

_LOCAL = re.compile(r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*\Z")


def normalize_account_email(value: str) -> str:
    """ASCII dot-atom local part + strict IDNA domain, case-insensitive account key.

    No DNS queries, provider aliases, quoted local parts or international local
    parts. Surrounding whitespace is removed; internal whitespace is rejected.
    Syntax validation never proves mailbox control or profile ownership.
    """
    if not isinstance(value, str) or len(value) > 320:
        raise ValueError("Enter a valid account email address.")
    value = value.strip()
    if any(ord(c) < 33 or ord(c) == 127 for c in value):
        raise ValueError("Enter a valid account email address.")
    try:
        parsed = Address(addr_spec=value)
        local, domain = value.rsplit("@", 1)
        if parsed.username != local or parsed.domain != domain or not _LOCAL.fullmatch(local) or len(local) > 64:
            raise ValueError
        ascii_domain = idna.encode(domain.lower(), strict=True, std3_rules=True).decode("ascii").lower()
        if "." not in ascii_domain or ascii_domain.endswith("."):
            raise ValueError
        normalized = local.lower() + "@" + ascii_domain
        if len(normalized) > 254:
            raise ValueError
        return normalized
    except (ValueError, HeaderParseError, idna.IDNAError, UnicodeError):
        raise ValueError("Enter a valid account email address.") from None


def validate_password(value: str, *, minimum: int = 15) -> str:
    """Preserve exact text; bound characters and UTF-8 bytes before hashing."""
    if not isinstance(value, str) or not minimum <= len(value) <= 128:
        raise ValueError(f"Password must contain {minimum} to 128 characters.")
    try:
        if len(value.encode("utf-8")) > 512:
            raise ValueError
    except (ValueError, UnicodeError):
        raise ValueError("Password contains unsupported or oversized text.") from None
    return value
