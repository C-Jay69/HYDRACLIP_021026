from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON
from sqlalchemy.sql import func
from . import Base


class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, nullable=False)
    user_id = Column(Integer, nullable=False)
    platform = Column(String, nullable=False)  # youtube, instagram, tiktok, x
    scheduled_at = Column(DateTime, nullable=False)
    timezone = Column(String, default="UTC")
    status = Column(String, default="pending")  # pending, running, completed, cancelled, failed
    platform_post_id = Column(String, nullable=True)  # ID of the published post on the platform
    platform_url = Column(String, nullable=True)  # URL of the published post
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class PublishedPost(Base):
    __tablename__ = "published_posts"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, nullable=False)
    schedule_id = Column(Integer, nullable=True)
    user_id = Column(Integer, nullable=False)
    platform = Column(String, nullable=False)
    platform_post_id = Column(String, nullable=True)
    platform_url = Column(String, nullable=True)
    title = Column(String)
    description = Column(Text)
    tags = Column(JSON, default=list)
    status = Column(String, default="pending")  # pending, published, failed
    published_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())