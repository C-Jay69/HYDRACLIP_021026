"""Schedule Service for Publishing."""

import logging
from typing import Optional

from app.models.schedule import Schedule, PublishedPost, ScheduleStatus, Platform
from app.models.video import Video, VideoStatus
from app.services.storage_service import get_file_url

logger = logging.getLogger(__name__)


async def publish_now(
    schedule: Schedule,
    video: Video,
    db,
) -> PublishedPost:
    """Publish a video immediately."""
    import secrets
    
    # Create published post record
    post = PublishedPost(
        id=secrets.token_urlsafe(16),
        video_id=video.id,
        schedule_id=schedule.id,
        user_id=video.user_id,
        platform=schedule.platform,
        title=video.title,
        description=video.description,
        status="pending",
    )
    db.add(post)
    await db.flush()
    
    # Platform-specific publishing
    if schedule.platform == Platform.YOUTUBE:
        # YouTube auto-publish via Data API v3
        try:
            from app.services.youtube_service import upload_to_youtube
            result = await upload_to_youtube(video, post)
            post.platform_post_id = result.get("video_id")
            post.platform_url = result.get("url")
            post.status = "published"
            post.published_at = datetime.now(timezone.utc)
        except Exception as e:
            logger.error(f"YouTube upload failed: {e}")
            post.status = "failed"
            post.error_message = str(e)
    else:
        # Manual export for other platforms
        post.status = "manual_required"
        post.error_message = f"Manual upload required for {schedule.platform}"
    
    await db.commit()
    return post


async def schedule_publish(
    schedule: Schedule,
    video: Video,
    db,
):
    """Schedule a video for future publishing."""
    # This would be called by Celery Beat
    pass