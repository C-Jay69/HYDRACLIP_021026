from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON
from sqlalchemy.sql import func
from . import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    title = Column(String, nullable=False)
    topic = Column(String)
    status = Column(String, default="pending")  # pending, generating, completed, failed
    settings_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, nullable=False)
    user_id = Column(Integer, nullable=False)
    status = Column(String, default="pending")  # pending, generating, completed, failed
    storage_key = Column(String)  # MinIO key for stored video
    script_text = Column(Text)
    error_message = Column(Text, nullable=True)
    duration_seconds = Column(Integer)
    resolution = Column(String)
    format = Column(String)
    generation_params_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class VideoJob(Base):
    __tablename__ = "video_jobs"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, nullable=False)
    job_type = Column(String, nullable=False)  # generate, publish, regenerate
    status = Column(String, default="pending")  # pending, running, completed, failed
    progress_pct = Column(Integer, default=0)
    celery_task_id = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())