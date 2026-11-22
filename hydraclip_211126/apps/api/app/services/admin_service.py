"""Admin Service for Platform Management."""

import logging
from typing import Optional

from app.core.database import AsyncSessionLocal
from app.models.user import User, UserRole
from app.models.system import AdminAuditLog

logger = logging.getLogger(__name__)


async def log_admin_action(
    admin_id: str,
    action: str,
    target_type: str,
    target_id: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> AdminAuditLog:
    """Log an admin action for audit."""
    from app.models.system import AdminAuditLog
    from datetime import datetime, timezone
    
    log = AdminAuditLog(
        id=f"log_{admin_id}_{action}_{target_id}",
        admin_id=admin_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        metadata_json=metadata,
        ip_address="127.0.0.1",
        created_at=datetime.now(timezone.utc),
    )
    
    async with AsyncSessionLocal() as db:
        db.add(log)
        await db.commit()
        await db.refresh(log)
    
    return log


async def get_admin_metrics() -> dict:
    """Get platform metrics."""
    # In production, query database for real metrics
    return {
        "total_users": 0,
        "new_users_7d": 0,
        "active_subscriptions": 0,
        "mrr_estimate": 0,
        "videos_today": 0,
        "videos_this_month": 0,
        "jobs_queued": 0,
        "jobs_running": 0,
        "jobs_failed": 0,
        "storage_used_gb": 0,
        "published_by_platform": {},
    }