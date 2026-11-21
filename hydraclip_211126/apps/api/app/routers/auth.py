"""Authentication Router."""

from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
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


def create_session(user_id: str, db: AsyncSession) -> Session:
    """Create a new session for user."""
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
    return session


import hashlib


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(rate_limit_auth),
):
    """Register a new user."""
    # Check if email exists
    result = await db.execute(select(User).where(User.email == request.email))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    
    # Create user
    user = User(
        id=secrets.token_urlsafe(16),
        email=request.email,
        password_hash=get_password_hash(request.password),
        name=request.name,
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
    session = create_session(user.id, db)
    await db.commit()
    
    # Create tokens
    access_token = create_access_token(subject=user.id)
    refresh_token = session.token_hash
    
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
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(rate_limit_auth),
):
    """Login user."""
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(request.password, user.password_hash):
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
    session = create_session(user.id, db)
    await db.commit()
    
    # Create tokens
    access_token = create_access_token(subject=user.id)
    refresh_token = session.token_hash
    
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
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """Refresh access token using refresh token."""
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Verify session exists
        result = await db.execute(
            select(Session).where(Session.user_id == user_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=401, detail="Session expired")
        
        # Create new access token
        access_token = create_access_token(subject=user_id)
        
        # Get user
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=token,
            user={
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "role": user.role.value,
                "plan": user.plan,
            },
        )
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid refresh token")


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