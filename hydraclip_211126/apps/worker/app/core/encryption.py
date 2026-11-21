"""HydraClip Encryption Module."""

import base64
import hashlib
import hmac
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings

settings = get_settings()


def _get_fernet_key() -> bytes:
    """Get or create Fernet key from settings."""
    key = settings.secret_key.encode()
    # Derive a 32-byte key from the secret
    return base64.urlsafe_b64encode(hashlib.sha256(key).digest())


def encrypt_token(token: str) -> str:
    """Encrypt a token using Fernet."""
    if not token:
        return ""
    fernet = Fernet(_get_fernet_key())
    return fernet.encrypt(token.encode()).decode()


def decrypt_token(encrypted_token: str) -> str:
    """Decrypt a token using Fernet."""
    if not encrypted_token:
        return ""
    try:
        fernet = Fernet(_get_fernet_key())
        return fernet.decrypt(encrypted_token.encode()).decode()
    except InvalidToken:
        return ""


def encrypt_dict(data: dict) -> str:
    """Encrypt a dictionary as JSON string."""
    import json
    if not data:
        return ""
    fernet = Fernet(_get_fernet_key())
    return fernet.encrypt(json.dumps(data).encode()).decode()


def decrypt_dict(encrypted_data: str) -> dict:
    """Decrypt a JSON string to dictionary."""
    import json
    if not encrypted_data:
        return {}
    try:
        fernet = Fernet(_get_fernet_key())
        return json.loads(fernet.decrypt(encrypted_data.encode()).decode())
    except (InvalidToken, json.JSONDecodeError):
        return {}


def generate_secure_token(length: int = 32) -> str:
    """Generate a cryptographically secure random token."""
    return secrets.token_urlsafe(length)


def generate_api_key() -> str:
    """Generate an API key."""
    return f"hc_{secrets.token_urlsafe(32)}"