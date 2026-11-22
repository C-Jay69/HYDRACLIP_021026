"""Video Service for Generation Pipeline."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.video import Video, VideoJob, VideoStatus, VideoJobType, VideoJobStatus

logger = logging.getLogger(__name__)


async def generate_video_pipeline(
    video_id: str,
    user_id: str,
    db_session_factory=None,
):
    """Run the full video generation pipeline."""
    async with AsyncSessionLocal() as db:
        video: Optional[Video] = None
        try:
            # Get video
            result = await db.execute(select(Video).where(Video.id == video_id))
            video = result.scalar_one_or_none()
            if not video:
                logger.error(f"Video {video_id} not found")
                return

            # Update status
            video.status = VideoStatus.GENERATING
            await update_job(db, video_id, VideoJobStatus.RUNNING, 5, started=True)
            await db.commit()

            # Step 1: Generate script
            await update_job(db, video_id, VideoJobStatus.RUNNING, 10)
            await asyncio.sleep(2)  # Simulate processing
            video.script_text = f"Script for: {video.title}\n\nThis is a generated script about {video.description}."
            await update_job(db, video_id, VideoJobStatus.RUNNING, 25)

            # Step 2: Generate voiceover
            await update_job(db, video_id, VideoJobStatus.RUNNING, 45)
            await asyncio.sleep(2)

            # Step 3: Generate subtitles
            await update_job(db, video_id, VideoJobStatus.RUNNING, 75)
            await asyncio.sleep(2)

            # Step 4: Render video
            await update_job(db, video_id, VideoJobStatus.RUNNING, 90)
            await asyncio.sleep(2)

            # Mark complete
            video.status = VideoStatus.COMPLETED
            video.storage_key = f"videos/{video_id}.mp4"
            video.duration_seconds = 60
            video.resolution = "1080x1920"
            video.format = "mp4"
            await update_job(db, video_id, VideoJobStatus.COMPLETED, 100, completed=True)

            await db.commit()
            logger.info(f"Video {video_id} generation complete")

        except Exception as e:
            logger.exception(f"Video generation failed for {video_id}: {e}")
            await db.rollback()
            try:
                result = await db.execute(select(Video).where(Video.id == video_id))
                video = result.scalar_one_or_none()
                if video is not None:
                    video.status = VideoStatus.FAILED
                    video.error_message = str(e)
                await update_job(
                    db,
                    video_id,
                    VideoJobStatus.FAILED,
                    error_message=str(e),
                )
                await db.commit()
            except Exception:
                logger.exception(f"Could not record failure for video {video_id}")
                await db.rollback()


async def update_job(
    db,
    video_id: str,
    status: VideoJobStatus,
    progress: Optional[int] = None,
    started: bool = False,
    completed: bool = False,
    error_message: Optional[str] = None,
):
    """Update the generation job that belongs to a video.

    Only one FULL_PIPELINE job is created per video, so this updates that
    job rather than looking for one job per pipeline step.
    """
    result = await db.execute(
        select(VideoJob)
        .where(VideoJob.video_id == video_id)
        .order_by(VideoJob.created_at)
        .limit(1)
    )
    job = result.scalar_one_or_none()

    if job is None:
        job = VideoJob(
            id=f"{video_id}_job",
            video_id=video_id,
            job_type=VideoJobType.FULL_PIPELINE,
            status=status,
            progress_pct=progress or 0,
        )
        db.add(job)

    job.status = status
    if progress is not None:
        job.progress_pct = progress
    if started and job.started_at is None:
        job.started_at = datetime.now(timezone.utc)
    if completed:
        job.completed_at = datetime.now(timezone.utc)
    if error_message is not None:
        job.error_message = error_message

    await db.commit()


async def fail_video(video_id: str, error_message: str) -> None:
    """Mark a video and its job as failed."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Video).where(Video.id == video_id))
        video = result.scalar_one_or_none()
        if video is not None:
            video.status = VideoStatus.FAILED
            video.error_message = error_message
        await update_job(db, video_id, VideoJobStatus.FAILED, error_message=error_message)
        await db.commit()
