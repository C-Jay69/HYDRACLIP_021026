"""Pydantic request/response schemas.

This package was an empty file — the API had no validated contracts at all.
"""

from apps.api.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    SignupRequest,
    TokenPair,
)
from apps.api.schemas.common import Message, Page
from apps.api.schemas.project import (
    ProjectCreate,
    ProjectPublic,
    ProjectUpdate,
    ProjectWithCounts,
)
from apps.api.schemas.user import UserPublic, UserUpdate
from apps.api.schemas.video import (
    QuotaStatus,
    VideoJobPublic,
    VideoPublic,
    VideoUpdate,
)

__all__ = [
    "LoginRequest",
    "Message",
    "Page",
    "ProjectCreate",
    "ProjectPublic",
    "ProjectUpdate",
    "ProjectWithCounts",
    "QuotaStatus",
    "RefreshRequest",
    "SignupRequest",
    "TokenPair",
    "UserPublic",
    "UserUpdate",
    "VideoJobPublic",
    "VideoPublic",
    "VideoUpdate",
]
