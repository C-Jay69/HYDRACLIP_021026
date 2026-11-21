"""Video Service for Generation Pipeline."""

import asyncio
import logging
from typing import Optional

from app.core.database import AsyncSessionLocal
from app.models.video import Video, VideoJob, VideoStatus, VideoJobType
from app.services.storage_service import upload_file, get_file_url

logger = logging.getLogger(__name__)


async def generate_video_pipeline(
    video_id: str,
    user_id: str,
    db_session_factory,
):
    """Run the full video generation pipeline."""
    async with AsyncSessionLocal() as db:
        try:
            # Get video
            from sqlalchemy import select
            result = await db.execute(select(Video).where(Video.id == video_id))
            video = result.scalar_one_or_none()
            if not video:
                logger.error(f"Video {video_id} not found")
                return
            
            # Update status
            video.status = VideoStatus.GENERATING
            await db.commit()
            
            # Step 1: Generate script
            await update_job(db, video_id, "script", "running", 10, "Generating script...")
            await asyncio.sleep(2)  # Simulate processing
            video.script_text = f"Script for: {video.title}\n\nThis is a generated script about {video.description}."
            await update_job(db, video_id, "script", "completed", 25, "Script generated")
            
            # Step 2: Generate voiceover
            await update_job(db, video_id, "voiceover", "running", 45, "Generating voiceover...")
            await asyncio.sleep(2)
            await update_job(db, video_id, "voiceover", "completed", 65, "Voiceover complete")
            
            # Step 3: Generate subtitles
            await update_job(db, video_id, "subtitles", "running", 75, "Generating subtitles...")
            await asyncio.sleep(2)
            await update_job(db, video_id, "subtitles", "completed", 85, "Subtitles complete")
            
            # Step 4: Render video
            await update_job(db, video_id, "render", "running", 90, "Rendering video...")
            await asyncio.sleep(2)
            
            # Mark complete
            video.status = VideoStatus.COMPLETED
            video.storage_key = f"videos/{video_id}.mp4"
            video.duration_seconds = 60
            video.resolution = "1080x1920"
            video.format = "mp4"
            await update_job(db, video_id, "render", "completed", 100, "Video complete")
            
            await db.commit()
            logger.info(f"Video {video_id} generation complete")
            
        except Exception as e:
            logger.error(f"Video generation failed: {e}")
            video.status = VideoStatus.FAILED
            video.error_message = str(e)
            await db.commit()


async def update_job(
    db,
    video_id: str,
    job_type: str,
    status: str,
    progress: int,
    log_text: str,
):
    """Update a video job."""
    from sqlalchemy import select
    from app.models.video import VideoJob, VideoJobStatus
    
    result = await db.execute(
        select(VideoJob).where(VideoJob.video_id == video_id, VideoJob.job_type == job_type)
    )
    job = result.scalar_one_or_none()
    
    if job:
        job.status = VideoJobStatus(status)
        job.progress_pct = progress
        job.log_text = log_text
        await db.commit()