"""Schedule and Published Post Models."""

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


class ScheduleStatus(str, Enum):
    """Schedule status enumeration."""
    PENDING = "pending"
    PUBLISHED = "published"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Platform(str, Enum):
    """Social platform enumeration."""
    YOUTUBE = "youtube"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    X = "x"


class Schedule(Base):
    """Schedule model."""
    
    __tablename__ = "schedules"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    video_id: Mapped[str] = mapped_column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    platform: Mapped[Platform] = mapped_column(Enum(Platform), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), default="UTC", nullable=False)
    status: Mapped[ScheduleStatus] = mapped_column(Enum(ScheduleStatus), default=ScheduleStatus.PENDING, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )
    
    # Relationships
    video: Mapped["Video"] = relationship(back_populates="schedules")
    user: Mapped["User"] = relationship(back_populates="schedules")
    published_posts: Mapped[list["PublishedPost"]] = relationship(back_populates="schedule", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("ix_schedules_user_id", "user_id"),
        Index("ix_schedules_video_id", "video_id"),
        Index("ix_schedules_scheduled_at", "scheduled_at"),
        Index("ix_schedules_status", "status"),
    )


class PublishedPostStatus(str, Enum):
    """Published post status enumeration."""
    PENDING = "pending"
    PUBLISHED = "published"
    FAILED = "failed"
    MANUAL_REQUIRED = "manual_required"


class PublishedPost(Base):
    """Published post model."""
    
    __tablename__ = "published_posts"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    video_id: Mapped[str] = mapped_column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)
    schedule_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("schedules.id", ondelete="SET NULL"), nullable=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    platform: Mapped[Platform] = mapped_column(Enum(Platform), nullable=False)
    platform_post_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    platform_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    status: Mapped[PublishedPostStatus] = mapped_column(Enum(PublishedPostStatus), default=PublishedPostStatus.PENDING, nullable=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    
    # Relationships
    video: Mapped["Video"] = relationship(back_populates="published_posts")
    schedule: Mapped[Optional["Schedule"]] = relationship(back_populates="published_posts")
    user: Mapped["User"] = relationship(back_populates="published_posts")
    
    __table_args__ = (
        Index("ix_published_posts_user_id", "user_id"),
        Index("ix_published_posts_video_id", "video_id"),
        Index("ix_published_posts_platform", "platform"),
        Index("ix_published_posts_status", "status"),
    )