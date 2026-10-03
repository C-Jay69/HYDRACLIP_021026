"""Authentication endpoints: signup, login, refresh, logout, profile."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import func, select

from apps.api.core.config import settings
from apps.api.core.deps import CurrentUser, DbSession, client_ip
from apps.api.models import User
from apps.api.schemas.auth import LoginRequest, RefreshRequest, SignupRequest, TokenPair
from apps.api.schemas.user import UserPublic, UserUpdate
from apps.api.services.auth import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from apps.api.services.rate_limit import login_rate_limiter

router = APIRouter(prefix="/auth", tags=["auth"])


def _normalise_email(email: str) -> str:
    return email.strip().lower()


def _issue_tokens(user: User) -> TokenPair:
    claims = {"email": user.email, "role": user.role}
    return TokenPair(
        access_token=create_access_token(user.id, extra_claims=claims),
        refresh_token=create_refresh_token(user.id),
        expires_in=settings.ACCESS_TOKEN_EXPIRES_IN,
        user=UserPublic.model_validate(user),
    )


@router.post("/signup", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: DbSession) -> TokenPair:
    """Register a new account and return a token pair."""
    email = _normalise_email(payload.email)

    existing = db.scalar(select(User).where(func.lower(User.email) == email))
    if existing is not None:
        # 409 rather than a generic 400 so clients can branch on it.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists.",
        )

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        name=payload.name,
        role="USER",
        is_active=True,
        is_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return _issue_tokens(user)


@router.post("/login", response_model=TokenPair)
def login(payload: LoginRequest, request: Request, db: DbSession) -> TokenPair:
    """Exchange email + password for a token pair."""
    email = _normalise_email(payload.email)
    limiter_key = f"{email}|{client_ip(request)}"

    if not login_rate_limiter.check(limiter_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Try again later.",
            headers={"Retry-After": str(login_rate_limiter.retry_after(limiter_key))},
        )

    user = db.scalar(select(User).where(func.lower(User.email) == email))

    # Always run a verification so a missing user and a wrong password take a
    # comparable amount of time, and return the same message either way.
    password_ok = verify_password(payload.password, user.password_hash if user else "")

    if user is None or not password_ok:
        login_rate_limiter.register_failure(limiter_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated.",
        )

    login_rate_limiter.reset(limiter_key)
    return _issue_tokens(user)


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, db: DbSession) -> TokenPair:
    """Exchange a valid refresh token for a new token pair."""
    try:
        claims = decode_token(payload.refresh_token, expected_type="refresh")
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = db.get(User, int(claims["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is no longer active.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return _issue_tokens(user)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def logout(_: CurrentUser) -> Response:
    """Log out.

    Tokens are stateless, so this only confirms the caller was authenticated;
    the client is responsible for discarding them. A server-side deny-list
    belongs here once Redis is wired up.
    """
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserPublic)
def read_me(user: CurrentUser) -> User:
    return user


@router.patch("/me", response_model=UserPublic)
def update_me(payload: UserUpdate, user: CurrentUser, db: DbSession) -> User:
    if payload.name is not None:
        user.name = payload.name
    db.commit()
    db.refresh(user)
    return user
