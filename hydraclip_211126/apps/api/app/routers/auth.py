"""Authentication Router."""

import hashlib
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Body, Response, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    decode_token,
    oauth2_scheme,
)
from app.core.rate_limiter import rate_limit_auth
from app.models.user import User, Session, UserRole
from app.config import get_settings

settings = get_settings()

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str
    is_active: bool
    is_verified: bool
    plan: Optional[str]
    subscription_status: Optional[str]
    video_limit_monthly: Optional[int]
    storage_limit_gb: int


def create_session(user_id: str, db: AsyncSession) -> tuple[Session, str]:
    """Create a new session for user and return it with the raw refresh token."""
    import secrets
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)

    session = Session(
        id=secrets.token_urlsafe(16),
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(session)
    return session, token


import hashlib


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(rate_limit_auth),
):
    """Register a new user."""
    # Check if email exists
    result = await db.execute(select(User).where(User.email == body.email))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    
    # Create user
    user = User(
        id=secrets.token_urlsafe(16),
        email=body.email,
        password_hash=get_password_hash(body.password),
        name=body.name,
        role=UserRole.USER,
        is_active=True,
        is_verified=False,
        plan="Free",
        video_limit_monthly=settings.free_video_limit,
        storage_limit_gb=settings.storage_limit_free_gb,
    )
    db.add(user)
    await db.flush()

    # Create session
    session, refresh_token = create_session(user.id, db)
    await db.commit()

    # Create tokens
    access_token = create_access_token(subject=user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role.value,
            "plan": user.plan,
        },
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(rate_limit_auth),
):
    """Login user."""
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )
    
    # Create session
    session, refresh_token = create_session(user.id, db)
    await db.commit()

    # Create tokens
    access_token = create_access_token(subject=user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role.value,
            "plan": user.plan,
        },
    )


@router.post("/logout")
async def logout(
    response: Response,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """Logout user (invalidate session)."""
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if user_id:
            # Delete all sessions for user
            await db.execute(
                Session.__table__.delete().where(Session.user_id == user_id)
            )
            await db.commit()
    except Exception:
        pass
    
    return {"success": True, "message": "Logged out successfully"}


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    """Exchange a refresh token for a new access token.

    The database stores only the SHA-256 hash of the refresh token. The token
    is rotated on every refresh so a stolen refresh token is single-use.
    """
    token_hash = hashlib.sha256(body.refresh_token.encode()).hexdigest()

    result = await db.execute(
        select(Session).where(Session.token_hash == token_hash)
    )
    session = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    expires_at = session.expires_at if session else None
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if session is None or expires_at is None or expires_at <= now:
        raise HTTPException(status_code=401, detail="Session expired")

    result = await db.execute(select(User).where(User.id == session.user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    # Rotate the refresh token
    new_refresh_token = secrets.token_urlsafe(32)
    session.token_hash = hashlib.sha256(new_refresh_token.encode()).hexdigest()
    session.expires_at = now + timedelta(days=settings.refresh_token_expire_days)
    await db.commit()

    access_token = create_access_token(subject=user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        user={
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role.value,
            "plan": user.plan,
        },
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """Get current user info."""
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            role=user.role.value,
            is_active=user.is_active,
            is_verified=user.is_verified,
            plan=user.plan,
            subscription_status=user.subscription_status,
            video_limit_monthly=user.video_limit_monthly,
            storage_limit_gb=user.storage_limit_gb,
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")