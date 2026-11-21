"""Publishing Tasks."""

import logging
from celery import shared_task
from app.core.database import AsyncSessionLocal
from app.models.schedule import Schedule, PublishedPost, ScheduleStatus
from app.models.video import Video, VideoStatus
from app.services.schedule_service import publish_now
from sqlalchemy import select

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="tasks.publishing.publish_scheduled")
def publish_scheduled(self, schedule_id: str):
    """Publish a scheduled post."""
    try:
        async def _publish():
            from app.core.database import AsyncSessionLocal
            async with AsyncSessionLocal() as db:
                # Get schedule
                result = await db.execute(select(Schedule).where(Schedule.id == schedule_id))
                schedule = result.scalar_one_or_none()
                if not schedule:
                    return {"error": "Schedule not found"}
                
                # Get video
                from app.models.video import Video
                result = await db.execute(select(Video).where(Video.id == schedule.video_id))
                video = result.scalar_one_or_none()
                if not video:
                    return {"error": "Video not found"}
                
                # Publish
                post = await publish_now(schedule, video, db)
                return {"post_id": post.id, "status": post.status}
        
        # Run async function
        import asyncio
        result = asyncio.run(_publish())
        return result
    except Exception as e:
        logger.error(f"Scheduled publish failed: {e}")
        raise self.retry(exc=e, countdown=60, max_retries=3)


@shared_task(bind=True, name="tasks.publishing.publish_now")
def publish_now_task(self, video_id: str, platform: str):
    """Publish a video immediately."""
    try:
        async def _publish():
            from app.core.database import AsyncSessionLocal
            async with AsyncSessionLocal() as db:
                # Get video
                result = await db.execute(select(Video).where(Video.id == video_id))
                video = result.scalar_one_or_none()
                if not video:
                    return {"error": "Video not found"}
                
                # Get schedule
                from app.models.schedule import Schedule, ScheduleStatus
                result = await db.execute(
                    select(Schedule).where(
                        Schedule.video_id == video_id,
                        Schedule.platform == platform,
                        Schedule.status == ScheduleStatus.PENDING,
                    )
                )
                schedule = result.scalar_one_or_none()
                
                # Publish
                if schedule:
                    post = await publish_now(schedule, video, db)
                    return {"post_id": post.id, "status": post.status}
                else:
                    # Direct publish
                    return {"error": "No schedule found"}
        
        import asyncio
        result = asyncio.run(_publish())
        return result
    except Exception as e:
        logger.error(f"Immediate publish failed: {e}")
        raise self.retry(exc=e, countdown=60, max_retries=3)