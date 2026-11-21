"""Videos Router."""

from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import oauth2_scheme, decode_token
from app.models.user import User
from app.models.video import Video, VideoJob, VideoStatus, VideoJobType
import secrets
from app.services.video_service import generate_video_pipeline
from app.services.storage_service import upload_file, delete_file, get_file_url

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
    request: VideoGenerateRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a video from a topic."""
    import json
    
    # Create video record
    video = Video(
        id=secrets.token_urlsafe(16),
        user_id=user.id,
        title=request.title,
        description=f"Video about {request.topic}",
        script_text=None,
        status=VideoStatus.QUEUED,
    )
    db.add(video)
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
    
    # Start generation pipeline in background
    background_tasks.add_task(
        generate_video_pipeline,
        video_id=video.id,
        user_id=user.id,
        db_session_factory=lambda: db,
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
                "log_text": j.log_text,
                "error_message": j.error_message,
            }
            for j in jobs
        ],
        "error_message": video.error_message,
    )


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