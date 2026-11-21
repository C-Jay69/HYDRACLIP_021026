"""Users Router."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import oauth2_scheme, decode_token
from app.models.user import User, Subscription, Plan
from app.models.social import SocialAccount

router = APIRouter(prefix="/users", tags=["users"])


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None


class UserUsage(BaseModel):
    videos_this_month: int
    video_limit_monthly: Optional[int]
    storage_used_gb: float
    storage_limit_gb: int
    quota_remaining: int


class SocialAccountResponse(BaseModel):
    id: str
    platform: str
    account_name: str
    account_id: Optional[str]
    is_active: bool
    connected_at: str


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get current user from token."""
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.get("/me")
async def get_me(
    user: User = Depends(get_current_user),
):
    """Get current user profile."""
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role.value,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "plan": user.plan,
        "subscription_status": user.subscription_status,
        "video_limit_monthly": user.video_limit_monthly,
        "storage_limit_gb": user.storage_limit_gb,
        "videos_this_month": user.videos_this_month,
        "storage_used_gb": user.storage_used_gb,
        "created_at": user.created_at.isoformat(),
    }


@router.put("/me")
async def update_me(
    update: UserUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update current user profile."""
    if update.name:
        user.name = update.name
    if update.email:
        # Check if email is taken
        result = await db.execute(select(User).where(User.email == update.email))
        existing = result.scalar_one_or_none()
        if existing and existing.id != user.id:
            raise HTTPException(status_code=409, detail="Email already taken")
        user.email = update.email
    
    await db.commit()
    await db.refresh(user)
    
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role.value,
        "plan": user.plan,
    }


@router.get("/me/usage", response_model=UserUsage)
async def get_usage(
    user: User = Depends(get_current_user),
):
    """Get current user usage stats."""
    quota_remaining = 0
    if user.video_limit_monthly and user.video_limit_monthly > 0:
        quota_remaining = max(0, user.video_limit_monthly - user.videos_this_month)
    elif user.video_limit_monthly == -1:
        quota_remaining = -1  # unlimited
    
    return UserUsage(
        videos_this_month=user.videos_this_month,
        video_limit_monthly=user.video_limit_monthly,
        storage_used_gb=user.storage_used_gb,
        storage_limit_gb=user.storage_limit_gb,
        quota_remaining=quota_remaining,
    )


@router.get("/me/social-accounts", response_model=list[SocialAccountResponse])
async def get_social_accounts(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user's connected social accounts."""
    result = await db.execute(
        select(SocialAccount).where(SocialAccount.user_id == user.id)
    )
    accounts = result.scalars().all()
    
    return [
        SocialAccountResponse(
            id=acc.id,
            platform=acc.platform,
            account_name=acc.account_name,
            account_id=acc.account_id,
            is_active=acc.is_active,
            connected_at=acc.connected_at.isoformat(),
        )
        for acc in accounts
    ]


@router.delete("/me/social-accounts/{platform}")
async def disconnect_social_account(
    platform: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Disconnect a social account."""
    result = await db.execute(
        select(SocialAccount).where(
            SocialAccount.user_id == user.id,
            SocialAccount.platform == platform,
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    await db.delete(account)
    await db.commit()
    
    return {"success": True, "message": f"Disconnected {platform}"}