"""Symmetric encryption for stored secrets.

``social_accounts`` and ``platform_tokens`` have had columns named
``access_token_encrypted`` and ``refresh_token_encrypted`` since the initial
migration, but nothing in the codebase ever encrypted anything — the suffix
was the only protection those tokens had. This module makes the name true.

Fernet (AES-128-CBC + HMAC-SHA256) is used rather than raw AES because it is
authenticated, versioned and timestamped by construction, which rules out the
usual hand-rolled mistakes.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from apps.api.core.config import settings

logger = logging.getLogger(__name__)

#: Domain separation, so a key derived for tokens cannot decrypt OAuth state.
_TOKEN_CONTEXT = b"videoforce.token.v1"
_STATE_CONTEXT = b"videoforce.oauth-state.v1"


class DecryptionError(RuntimeError):
    """Ciphertext could not be decrypted with the current key."""


def _derive_key(context: bytes) -> bytes:
    """A urlsafe-base64 32-byte Fernet key.

    ``TOKEN_ENCRYPTION_KEY`` is used when set. Otherwise the key is derived
    from ``SECRET_KEY`` so the application works out of the box — at the cost
    of tying token decryptability to the JWT signing key: rotating
    ``SECRET_KEY`` would strand every stored token. Production should set an
    explicit key, and ``Settings`` warns when it is missing.
    """
    configured = settings.TOKEN_ENCRYPTION_KEY
    if configured:
        material = configured.encode()
    else:
        material = settings.SECRET_KEY.encode()

    digest = hashlib.sha256(material + b"|" + context).digest()
    return base64.urlsafe_b64encode(digest)


def _fernet(context: bytes) -> Fernet:
    return Fernet(_derive_key(context))


# --- Token storage ---------------------------------------------------------------


def encrypt_token(plaintext: str) -> str:
    """Encrypt an OAuth token for storage."""
    if plaintext is None:
        raise ValueError("refusing to encrypt None")
    return _fernet(_TOKEN_CONTEXT).encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    """Decrypt a stored OAuth token."""
    try:
        return _fernet(_TOKEN_CONTEXT).decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise DecryptionError(
            "Stored token could not be decrypted. The encryption key has "
            "probably changed; the account must be reconnected."
        ) from exc


def encrypt_optional(plaintext: str | None) -> str | None:
    return None if plaintext is None else encrypt_token(plaintext)


def decrypt_optional(ciphertext: str | None) -> str | None:
    return None if ciphertext is None else decrypt_token(ciphertext)


# --- OAuth state -------------------------------------------------------------------


def seal_state(payload: dict[str, Any]) -> str:
    """Encrypt an OAuth ``state`` blob.

    Encrypted rather than merely signed because the payload carries the PKCE
    code verifier, which must never be readable by anything that intercepts
    the redirect.
    """
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return _fernet(_STATE_CONTEXT).encrypt(raw).decode()


def unseal_state(token: str, max_age_seconds: int) -> dict[str, Any]:
    """Decrypt and age-check an OAuth ``state`` blob.

    Fernet stamps its own timestamp, so expiry is enforced by the primitive
    rather than by a field an attacker could influence.
    """
    try:
        raw = _fernet(_STATE_CONTEXT).decrypt(token.encode(), ttl=max_age_seconds)
    except InvalidToken as exc:
        raise DecryptionError("The OAuth state is invalid or has expired.") from exc

    try:
        payload = json.loads(raw)
    except ValueError as exc:
        raise DecryptionError("The OAuth state payload is malformed.") from exc

    if not isinstance(payload, dict):
        raise DecryptionError("The OAuth state payload is malformed.")
    return payload


def redact(secret: str | None, keep: int = 4) -> str:
    """A loggable fingerprint of a secret, never the secret itself."""
    if not secret:
        return "<none>"
    if len(secret) <= keep:
        return "*" * len(secret)
    return f"{'*' * (len(secret) - keep)}{secret[-keep:]}"
