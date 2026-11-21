"""Video and Video Job Models."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class VideoStatus(str, Enum):
    """Video status enumeration."""
    QUEUED = "queued"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class VideoJobStatus(str, Enum):
    """Video job status enumeration."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class VideoJobType(str, Enum):
    """Video job type enumeration."""
    SCRIPT = "script"
    VOICEOVER = "voiceover"
    SUBTITLES = "subtitles"
    RENDER = "render"
    FULL_PIPELINE = "full_pipeline"


class Video(Base):
    """Video model."""
    
    __tablename__ = "videos"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    script_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[VideoStatus] = mapped_column(Enum(VideoStatus), default=VideoStatus.QUEUED, nullable=False)
    storage_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    resolution: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    format: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )
    
    # Relationships
    project: Mapped["Project"] = relationship(back_populates="videos")
    user: Mapped["User"] = relationship(back_populates="videos")
    video_jobs: Mapped[list["VideoJob"]] = relationship(back_populates="video", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("ix_videos_user_id", "user_id"),
        Index("ix_videos_project_id", "project_id"),
        Index("ix_videos_status", "status"),
    )


class VideoJob(Base):
    """Video job model."""
    
    __tablename__ = "video_jobs"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    video_id: Mapped[str] = mapped_column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)
    job_type: Mapped[VideoJobType] = mapped_column(Enum(VideoJobType), nullable=False)
    status: Mapped[VideoJobStatus] = mapped_column(Enum(VideoJobStatus), default=VideoJobStatus.QUEUED, nullable=False)
    progress_pct: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    
    # Relationships
    video: Mapped["Video"] = relationship(back_populates="video_jobs")
    
    __table_args__ = (
        Index("ix_video_jobs_video_id", "video_id"),
        Index("ix_video_jobs_status", "status"),
    )