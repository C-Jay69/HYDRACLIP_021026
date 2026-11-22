"""Admin Router."""

from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from app.core.database import get_db
from app.core.security import oauth2_scheme, decode_token
from app.models.user import User, UserRole
from app.models.video import Video, VideoJob, VideoJobStatus
from app.models.billing import BillingEvent
from app.models.user import Plan
from app.models.system import SystemSetting, AdminAuditLog
from app.models.social import SocialAccount

router = APIRouter(prefix="/admin", tags=["admin"])


async def get_admin_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get current admin user from token."""
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if user.role != UserRole.ADMIN:
            raise HTTPException(status_code=403, detail="Admin access required")
        return user
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.get("/metrics")
async def get_metrics(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Get platform metrics for admin dashboard."""
    from datetime import datetime, timedelta
    
    # Total users
    users_result = await db.execute(select(func.count(User.id)))
    total_users = users_result.scalar() or 0
    
    # New users last 7 days
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    new_users_result = await db.execute(
        select(func.count(User.id)).where(User.created_at >= week_ago)
    )
    new_users_7d = new_users_result.scalar() or 0
    
    # Active subscriptions
    active_subscriptions_result = await db.execute(
        select(func.count(User.id)).where(User.subscription_status == "active")
    )
    active_subscriptions = active_subscriptions_result.scalar() or 0
    
    # MRR estimate
    plans_result = await db.execute(select(Plan).where(Plan.is_active == True))
    plans = plans_result.scalars().all()
    mrr = sum(p.price_cents for p in plans if p.price_cents > 0) / 100
    
    # Videos today
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    videos_today_result = await db.execute(
        select(func.count(Video.id)).where(Video.created_at >= today_start)
    )
    videos_today = videos_today_result.scalar() or 0
    
    # Videos this month
    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    videos_month_result = await db.execute(
        select(func.count(Video.id)).where(Video.created_at >= month_start)
    )
    videos_this_month = videos_month_result.scalar() or 0
    
    # Jobs
    jobs_result = await db.execute(select(VideoJob))
    jobs = jobs_result.scalars().all()
    jobs_queued = sum(1 for j in jobs if j.status == VideoJobStatus.QUEUED)
    jobs_running = sum(1 for j in jobs if j.status == VideoJobStatus.RUNNING)
    jobs_failed = sum(1 for j in jobs if j.status == VideoJobStatus.FAILED)
    
    # Storage
    storage_result = await db.execute(
        select(func.sum(User.storage_used_gb)).where(User.is_active == True)
    )
    storage_used_gb = storage_result.scalar() or 0
    
    # Published posts by platform
    published_result = await db.execute(select(Video.id, Video.user_id, Video.title))
    published_by_platform = {}
    for v in published_result.scalars().all():
        pass
    
    return {
        "total_users": total_users,
        "new_users_7d": new_users_7d,
        "active_subscriptions": active_subscriptions,
        "mrr_estimate": mrr,
        "videos_today": videos_today,
        "videos_this_month": videos_this_month,
        "jobs_queued": jobs_queued,
        "jobs_running": jobs_running,
        "jobs_failed": jobs_failed,
        "storage_used_gb": storage_used_gb,
        "published_by_platform": published_by_platform,
    }


@router.get("/users")
async def list_users(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """List all users."""
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    
    return [
        {
            "id": u.id,
            "email": u.email,
            "name": u.name,
            "role": u.role.value,
            "is_active": u.is_active,
            "is_verified": u.is_verified,
            "plan": u.plan,
            "subscription_status": u.subscription_status,
            "video_limit_monthly": u.video_limit_monthly,
            "storage_limit_gb": u.storage_limit_gb,
            "videos_this_month": u.videos_this_month,
            "storage_used_gb": u.storage_used_gb,
            "created_at": u.created_at.isoformat(),
        }
        for u in users
    ]


@router.get("/jobs")
async def list_jobs(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """List all video jobs."""
    result = await db.execute(select(VideoJob).order_by(VideoJob.created_at.desc()))
    jobs = result.scalars().all()
    
    return [
        {
            "id": j.id,
            "video_id": j.video_id,
            "job_type": j.job_type.value,
            "status": j.status.value,
            "progress_pct": j.progress_pct,
            "error_message": j.error_message,
            "created_at": j.created_at.isoformat(),
        }
        for j in jobs
    ]


@router.get("/settings")
async def get_settings(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Get system settings."""
    result = await db.execute(select(SystemSetting))
    settings = result.scalars().all()
    
    return [
        {
            "key": s.key,
            "value": s.value,
            "value_type": s.value_type,
            "description": s.description,
        }
        for s in settings
    ]


@router.put("/settings/{key}")
async def update_setting(
    key: str,
    value: str,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a system setting."""
    result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
    setting = result.scalar_one_or_none()
    if not setting:
        raise HTTPException(status_code=404, detail="Setting not found")
    
    setting.value = value
    setting.updated_at = datetime.now(timezone.utc)
    setting.updated_by = admin.id
    
    await db.commit()
    
    return {"success": True, "key": key, "value": value}


@router.get("/logs")
async def get_logs(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Get admin audit logs."""
    result = await db.execute(select(AdminAuditLog).order_by(AdminAuditLog.created_at.desc()).limit(100))
    logs = result.scalars().all()
    
    return [
        {
            "id": l.id,
            "admin_id": l.admin_id,
            "action": l.action,
            "target_type": l.target_type,
            "target_id": l.target_id,
            "metadata_json": l.metadata_json,
            "ip_address": l.ip_address,
            "created_at": l.created_at.isoformat(),
        }
        for l in logs
    ]


@router.post("/maintenance/toggle")
async def toggle_maintenance(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Toggle maintenance mode."""
    from app.config import get_settings
    settings = get_settings()
    settings.maintenance_mode = not settings.maintenance_mode
    
    return {"success": True, "maintenance_mode": settings.maintenance_mode}