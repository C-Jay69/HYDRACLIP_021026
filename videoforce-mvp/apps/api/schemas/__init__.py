"""Pydantic request/response schemas.

This package was an empty file — the API had no validated contracts at all.
"""

from apps.api.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    SignupRequest,
    TokenPair,
)
from apps.api.schemas.user import UserPublic, UserUpdate

__all__ = [
    "LoginRequest",
    "RefreshRequest",
    "SignupRequest",
    "TokenPair",
    "UserPublic",
    "UserUpdate",
]
