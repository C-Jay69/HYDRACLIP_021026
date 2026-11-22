"""Videos Router."""

import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import oauth2_scheme, decode_token
from app.core.celery_client import enqueue_video_generation
from app.models.user import User
from app.models.video import Video, VideoJob, VideoStatus, VideoJobType, VideoJobStatus
from app.models.project import Project
import secrets
from app.services.storage_service import (
    delete_file,
    get_file_url,
    file_exists,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/videos", tags=["videos"])


class VideoGenerateRequest(BaseModel):
    title: str
    topic: str


class VideoResponse(BaseModel):
    id: str
    user_id: str
    title: str
    description: str
    script_text: Optional[str]
    status: str
    storage_key: Optional[str]
    duration_seconds: Optional[int]
    resolution: Optional[str]
    format: Optional[str]
    error_message: Optional[str]
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


@router.get("", response_model=List[VideoResponse])
async def list_videos(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List user's videos."""
    result = await db.execute(
        select(Video)
        .where(Video.user_id == user.id)
        .order_by(desc(Video.created_at))
    )
    videos = result.scalars().all()
    
    return [
        VideoResponse(
            id=v.id,
            user_id=v.user_id,
            title=v.title,
            description=v.description or "",
            script_text=v.script_text,
            status=v.status.value,
            storage_key=v.storage_key,
            duration_seconds=v.duration_seconds,
            resolution=v.resolution,
            format=v.format,
            error_message=v.error_message,
            created_at=v.created_at.isoformat(),
        )
        for v in videos
    ]


@router.get("/{video_id}", response_model=VideoResponse)
async def get_video(
    video_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a video by ID."""
    result = await db.execute(
        select(Video).where(Video.id == video_id, Video.user_id == user.id)
    )
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    return VideoResponse(
        id=video.id,
        user_id=video.user_id,
        title=video.title,
        description=video.description or "",
        script_text=video.script_text,
        status=video.status.value,
        storage_key=video.storage_key,
        duration_seconds=video.duration_seconds,
        resolution=video.resolution,
        format=video.format,
        error_message=video.error_message,
        created_at=video.created_at.isoformat(),
    )


@router.post("/generate", response_model=VideoResponse, status_code=status.HTTP_201_CREATED)
async def generate_video(
    body: VideoGenerateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a video from a topic."""
    # Find or create a default project for this user (Video requires project_id)
    result = await db.execute(select(Project).where(Project.user_id == user.id).limit(1))
    project = result.scalar_one_or_none()
    if project is None:
        project = Project(
            id=secrets.token_urlsafe(16),
            user_id=user.id,
            title=body.title,
            topic=body.topic,
            platform_targets="[]",
        )
        db.add(project)
        await db.commit()
        await db.refresh(project)

    # Create video record
    video = Video(
        id=secrets.token_urlsafe(16),
        project_id=project.id,
        user_id=user.id,
        title=body.title,
        description=f"Video about {body.topic}",
        script_text=None,
        status=VideoStatus.QUEUED,
    )
    db.add(video)
    # Track monthly usage for the user's quota.
    user.videos_this_month = (user.videos_this_month or 0) + 1
    await db.commit()
    await db.refresh(video)
    
    # Create generation job
    job = VideoJob(
        id=secrets.token_urlsafe(16),
        video_id=video.id,
        job_type=VideoJobType.FULL_PIPELINE,
        status=VideoJobStatus.QUEUED,
    )
    db.add(job)
    await db.commit()

    # Hand the job to the Celery worker, which plans with OpenRouter,
    # renders with Remotion and uploads the result to object storage.
    try:
        task = enqueue_video_generation(video.id, user.id)
        job.celery_task_id = task.id
        await db.commit()
    except Exception as exc:
        logger.exception("Could not enqueue generation for video %s", video.id)
        video.status = VideoStatus.FAILED
        video.error_message = f"Could not queue generation job: {exc}"
        job.status = VideoJobStatus.FAILED
        job.error_message = video.error_message
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Video generation queue is unavailable",
        )

    return VideoResponse(
        id=video.id,
        user_id=video.user_id,
        title=video.title,
        description=video.description,
        script_text=video.script_text,
        status=video.status.value,
        storage_key=video.storage_key,
        duration_seconds=video.duration_seconds,
        resolution=video.resolution,
        format=video.format,
        error_message=video.error_message,
        created_at=video.created_at.isoformat(),
    )


@router.get("/{video_id}/status")
async def get_video_status(
    video_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get video generation status."""
    result = await db.execute(
        select(Video).where(Video.id == video_id, Video.user_id == user.id)
    )
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Get jobs
    job_result = await db.execute(
        select(VideoJob).where(VideoJob.video_id == video_id)
    )
    jobs = job_result.scalars().all()
    
    return {
        "video_id": video.id,
        "status": video.status.value,
        "progress": sum(j.progress_pct for j in jobs) // max(len(jobs), 1),
        "jobs": [
            {
                "id": j.id,
                "job_type": j.job_type.value,
                "status": j.status.value,
                "progress_pct": j.progress_pct,
                "error_message": j.error_message,
                "started_at": j.started_at.isoformat() if j.started_at else None,
                "completed_at": j.completed_at.isoformat() if j.completed_at else None,
            }
            for j in jobs
        ],
        "error_message": video.error_message,
    }


@router.get("/{video_id}/download")
async def download_video(
    video_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Download a generated video."""
    result = await db.execute(
        select(Video).where(Video.id == video_id, Video.user_id == user.id)
    )
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    if not video.storage_key:
        raise HTTPException(status_code=404, detail="Video not yet generated")

    if not file_exists(video.storage_key):
        raise HTTPException(
            status_code=404,
            detail="Video file is not available in storage",
        )

    return {"download_url": get_file_url(video.storage_key)}


@router.delete("/{video_id}")
async def delete_video(
    video_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a video."""
    result = await db.execute(
        select(Video).where(Video.id == video_id, Video.user_id == user.id)
    )
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Delete from storage
    if video.storage_key:
        await delete_file(video.storage_key)
    
    # Delete video record
    await db.delete(video)
    await db.commit()
    
    return {"success": True, "message": "Video deleted"}