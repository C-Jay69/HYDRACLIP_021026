"""Celery Beat Schedule Configuration."""

from celery.schedules import crontab

BEAT_SCHEDULE = {
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
}