"""Celery client used by the API to enqueue background work.

The API does not execute rendering itself - it hands jobs to the Celery worker
over Redis, and the worker talks to the Remotion render service.
"""

import logging

from celery import Celery

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

celery_client = Celery("hydraclip-api", broker=settings.redis_url)
celery_client.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
)


def enqueue_video_generation(video_id: str, user_id: str):
    """Queue the worker task that plans, renders and uploads a video."""
    return celery_client.send_task(
        "tasks.video_generation.generate_video",
        args=[video_id, user_id],
        queue="celery",
    )
