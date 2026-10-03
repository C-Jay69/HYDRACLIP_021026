"""Shared FastAPI dependencies: database session, current user, role guards."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from apps.api.core.db import get_db
from apps.api.models import Project, User, Video
from apps.api.schemas.common import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from apps.api.services.auth import TokenError, decode_token

# auto_error=False so a missing header produces our 401 shape, not FastAPI's.
bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]

CREDENTIALS_HEADERS = {"WWW-Authenticate": "Bearer"}


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers=CREDENTIALS_HEADERS,
    )


def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
) -> User:
    """Resolve the bearer token to an active user, or raise 401."""
    if credentials is None or not credentials.credentials:
        raise _unauthorized("Not authenticated.")

    try:
        payload = decode_token(credentials.credentials, expected_type="access")
    except TokenError as exc:
        raise _unauthorized(str(exc)) from exc

    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise _unauthorized("Token subject is invalid.") from exc

    user = db.get(User, user_id)
    if user is None:
        raise _unauthorized("User no longer exists.")
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated.",
        )

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_admin(user: CurrentUser) -> User:
    """Allow only ADMIN users through."""
    if (user.role or "").upper() != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges are required.",
        )
    return user


AdminUser = Annotated[User, Depends(require_admin)]


def client_ip(request: Request) -> str:
    """Best-effort client IP, honouring a single proxy hop."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# --- Pagination --------------------------------------------------------------


@dataclass(frozen=True)
class Pagination:
    limit: int
    offset: int


def pagination(
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
) -> Pagination:
    return Pagination(limit=limit, offset=offset)


PageParams = Annotated[Pagination, Depends(pagination)]


# --- Resource ownership -------------------------------------------------------
#
# These return 404 (not 403) when the caller does not own the row. A 403 would
# confirm that the id exists and belongs to someone else, which is an
# information leak; 404 makes "missing" and "not yours" indistinguishable.
# Administrators may read any row, per the admin requirements in the spec.


def _is_admin(user: User) -> bool:
    return (user.role or "").upper() == "ADMIN"


def get_owned_project(
    project_id: int,
    db: DbSession,
    user: CurrentUser,
) -> Project:
    project = db.get(Project, project_id)
    if project is None or (project.user_id != user.id and not _is_admin(user)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )
    return project


OwnedProject = Annotated[Project, Depends(get_owned_project)]


def get_owned_video(
    video_id: int,
    db: DbSession,
    user: CurrentUser,
) -> Video:
    video = db.get(Video, video_id)
    if video is None or (video.user_id != user.id and not _is_admin(user)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found.",
        )
    return video


OwnedVideo = Annotated[Video, Depends(get_owned_video)]
