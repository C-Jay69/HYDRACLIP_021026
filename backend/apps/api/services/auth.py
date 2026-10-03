"""Password hashing and JWT issuing/verification.

``seed.py`` has always imported ``hash_password`` from this module, but the
module did not exist — so seeding failed at import time.

Password storage
----------------
bcrypt silently truncates input at 72 bytes, which turns a long passphrase into
a much weaker secret. To remove the limit entirely, passwords are SHA-256
digested and base64-encoded before being passed to bcrypt (the same
construction passlib calls ``bcrypt_sha256``). The digest is 44 base64 bytes,
comfortably under the limit, and no entropy is discarded.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import bcrypt
import jwt

from apps.api.core.config import settings

TokenType = Literal["access", "refresh"]

__all__ = [
    "hash_password",
    "verify_password",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "TokenError",
]


class TokenError(Exception):
    """Raised when a JWT is missing, malformed, expired or the wrong type."""


def _prehash(password: str) -> bytes:
    """SHA-256 + base64 so bcrypt never sees more than 72 bytes."""
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return base64.b64encode(digest)


def hash_password(password: str) -> str:
    """Return a bcrypt hash for ``password``."""
    if not password:
        raise ValueError("Password must not be empty.")
    return bcrypt.hashpw(_prehash(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Constant-time check of ``password`` against a stored bcrypt hash."""
    if not password or not password_hash:
        return False
    try:
        return bcrypt.checkpw(_prehash(password), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        # Malformed hash in the database — treat as a failed login, not a 500.
        return False


def _create_token(
    subject: str | int,
    token_type: TokenType,
    expires_in: int,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in)).timestamp()),
        "jti": uuid.uuid4().hex,
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(
    subject: str | int,
    extra_claims: dict[str, Any] | None = None,
    expires_in: int | None = None,
) -> str:
    return _create_token(
        subject,
        "access",
        expires_in if expires_in is not None else settings.ACCESS_TOKEN_EXPIRES_IN,
        extra_claims,
    )


def create_refresh_token(
    subject: str | int,
    expires_in: int | None = None,
) -> str:
    return _create_token(
        subject,
        "refresh",
        expires_in if expires_in is not None else settings.REFRESH_TOKEN_EXPIRES_IN,
    )


def decode_token(token: str, expected_type: TokenType | None = None) -> dict[str, Any]:
    """Decode and validate a JWT.

    Raises ``TokenError`` for anything invalid so callers never have to catch
    PyJWT's exception hierarchy directly.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("Token has expired.") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError("Token is invalid.") from exc

    if expected_type is not None and payload.get("type") != expected_type:
        raise TokenError(f"Expected a {expected_type} token.")

    return payload


def generate_verification_token() -> str:
    """Opaque, URL-safe token for email verification / password reset."""
    return secrets.token_urlsafe(32)
