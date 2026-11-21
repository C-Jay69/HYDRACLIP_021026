"""Schedules Router."""

from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import oauth2_scheme, decode_token
from app.models.user import User
from app.models.schedule import Schedule, ScheduleStatus, Platform
import secrets
from app.services.schedule_service import publish_now

router = APIRouter(prefix="/schedules", tags=["schedules"])


class ScheduleCreate(BaseModel):
    video_id: str
    platform: Platform
    scheduled_at: str
    timezone: str = "UTC"


class ScheduleUpdate(BaseModel):
    status: Optional[ScheduleStatus] = None


class ScheduleResponse(BaseModel):
    id: str
    video_id: str
    user_id: str
    platform: str
    scheduled_at: str
    timezone: str
    status: str
    created_at: str


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


@router.get("", response_model=List[ScheduleResponse])
async def list_schedules(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List user's schedules."""
    result = await db.execute(
        select(Schedule)
        .where(Schedule.user_id == user.id)
        .order_by(Schedule.scheduled_at)
    )
    schedules = result.scalars().all()
    
    return [
        ScheduleResponse(
            id=s.id,
            video_id=s.video_id,
            user_id=s.user_id,
            platform=s.platform.value,
            scheduled_at=s.scheduled_at.isoformat(),
            timezone=s.timezone,
            status=s.status.value,
            created_at=s.created_at.isoformat(),
        )
        for s in schedules
    ]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_schedule(
    schedule: ScheduleCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new schedule."""
    result = await db.execute(
        select(Video).where(Video.id == schedule.video_id, Video.user_id == user.id)
    )
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    new_schedule = Schedule(
        id=secrets.token_urlsafe(16),
        video_id=schedule.video_id,
        user_id=user.id,
        platform=schedule.platform,
        scheduled_at=schedule.scheduled_at,
        timezone=schedule.timezone,
        status=ScheduleStatus.PENDING,
    )
    db.add(new_schedule)
    await db.commit()
    await db.refresh(new_schedule)
    
    return {"success": True, "schedule_id": new_schedule.id}


@router.post("/{schedule_id}/publish-now")
async def publish_now_endpoint(
    schedule_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Publish a schedule immediately."""
    result = await db.execute(
        select(Schedule).where(Schedule.id == schedule_id, Schedule.user_id == user.id)
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    result = await db.execute(
        select(Video).where(Video.id == schedule.video_id, Video.user_id == user.id)
    )
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    if video.status != VideoStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Video not yet generated")
    
    published_post = await publish_now(schedule, video, db)
    
    return {
        "success": True,
        "published_post_id": published_post.id,
        "platform_post_id": published_post.platform_post_id,
        "platform_url": published_post.platform_url,
    }