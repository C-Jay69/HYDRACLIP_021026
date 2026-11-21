"""Celery Application Configuration."""

from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "hydraclip",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "tasks.video_generation",
        "tasks.publishing",
        "tasks.scheduling",
        "tasks.maintenance",
    ],
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,
    task_soft_time_limit=3000,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
    beat_schedule={
        "check-scheduled-posts": {
            "task": "tasks.scheduling.check_scheduled_posts",
            "schedule": 60.0,  # Every minute
        },
        "cleanup-old-jobs": {
            "task": "tasks.maintenance.cleanup_old_jobs",
            "schedule": crontab(hour=3, minute=0),  # Daily at 3 AM
        },
        "reset-monthly-quotas": {
            "task": "tasks.maintenance.reset_monthly_quotas",
            "schedule": crontab(day_of_month=1, hour=0, minute=0),  # First of month
        },
    },
)

# Auto-discover tasks
celery_app.autodiscover_tasks()


@celery_app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")