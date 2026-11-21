"""Project and Asset Models."""

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


class ProjectFormat(str, Enum):
    """Video format enumeration."""
    SHORT = "short"
    LONG = "long"


class ProjectAspectRatio(str, Enum):
    """Aspect ratio enumeration."""
    RATIO_9_16 = "9:16"
    RATIO_16_9 = "16:9"
    RATIO_1_1 = "1:1"


class ProjectStatus(str, Enum):
    """Project status enumeration."""
    DRAFT = "draft"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class Project(Base):
    """Project model."""
    
    __tablename__ = "projects"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    niche: Mapped[str] = mapped_column(String(100), default="general", nullable=False)
    platform_targets: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array
    format: Mapped[ProjectFormat] = mapped_column(Enum(ProjectFormat), default=ProjectFormat.SHORT, nullable=False)
    aspect_ratio: Mapped[ProjectAspectRatio] = mapped_column(Enum(ProjectAspectRatio), default=ProjectAspectRatio.RATIO_9_16, nullable=False)
    tone: Mapped[str] = mapped_column(String(50), default="educational", nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    status: Mapped[ProjectStatus] = mapped_column(Enum(ProjectStatus), default=ProjectStatus.DRAFT, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="projects")
    assets: Mapped[list["ProjectAsset"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    videos: Mapped[list["Video"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("ix_projects_user_id", "user_id"),
        Index("ix_projects_status", "status"),
    )


class ProjectAsset(Base):
    """Project asset model."""
    
    __tablename__ = "project_assets"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(50), nullable=False)  # logo, music, image, clip
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    
    # Relationships
    project: Mapped["Project"] = relationship(back_populates="assets")
    
    __table_args__ = (
        Index("ix_project_assets_project_id", "project_id"),
    )