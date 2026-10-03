"""The Celery application, shared by the worker and the API.

The API imports this module only to dispatch by name; it never imports
``tasks``, so queueing a job does not drag the pipeline into the web process.

``docker-compose.yml`` has always run a ``flower`` container pointed at a
Celery broker, but no Celery app and no ``apps/worker`` package existed —
flower had nothing to monitor.
"""

from __future__ import annotations

from celery import Celery
from celery.schedules import schedule as celery_schedule

from apps.api.core.config import settings

#: Task names are referenced as strings by the API so that dispatch does not
#: require importing task implementations.
TASK_GENERATE_VIDEO = "videoforce.generate_video"
TASK_REAP_STALE_JOBS = "videoforce.reap_stale_jobs"
TASK_SWEEP_WORK_DIR = "videoforce.sweep_work_dir"
TASK_DISPATCH_SCHEDULES = "videoforce.dispatch_due_schedules"
TASK_PUBLISH_SCHEDULE = "videoforce.publish_schedule"

QUEUE_GENERATION = "generation"
QUEUE_MAINTENANCE = "maintenance"


def create_celery_app() -> Celery:
    app = Celery(
        "videoforce",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
        include=["apps.worker.tasks"],
    )

    app.conf.update(
        # Celery 6 stops honouring broker_connection_retry at startup;
        # being explicit keeps the worker resilient to a broker that comes up
        # after it does (exactly what happens under compose).
        broker_connection_retry_on_startup=True,
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        # Redelivery on worker loss. Generation is long-running, so a task
        # must not be acknowledged until it finishes.
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        # Long tasks + prefetch means one worker hoards the queue while its
        # peers idle.
        worker_prefetch_multiplier=1,
        # Hard ceiling slightly above the soft one, so a job gets the chance
        # to record its own failure before being killed.
        task_soft_time_limit=int(settings.JOB_TIMEOUT_SECONDS),
        task_time_limit=int(settings.JOB_TIMEOUT_SECONDS) + 60,
        result_expires=86_400,
        # The filesystem transport (used by the test suite, which has no
        # Redis) needs its spool directories named explicitly.
        broker_transport_options=(
            {
                "data_folder_in": f"{settings.MEDIA_WORK_DIR}/broker/out",
                "data_folder_out": f"{settings.MEDIA_WORK_DIR}/broker/out",
                "data_folder_processed": f"{settings.MEDIA_WORK_DIR}/broker/processed",
            }
            if settings.celery_broker_url.startswith("filesystem://")
            else {}
        ),
        task_default_queue=QUEUE_GENERATION,
        task_routes={
            TASK_GENERATE_VIDEO: {"queue": QUEUE_GENERATION},
            TASK_REAP_STALE_JOBS: {"queue": QUEUE_MAINTENANCE},
            TASK_SWEEP_WORK_DIR: {"queue": QUEUE_MAINTENANCE},
            TASK_DISPATCH_SCHEDULES: {"queue": QUEUE_MAINTENANCE},
            # Publishing uploads large files and waits on provider
            # processing, so it belongs on the slow queue beside
            # generation rather than blocking short maintenance ticks.
            TASK_PUBLISH_SCHEDULE: {"queue": QUEUE_GENERATION},
        },
        beat_schedule={
            "reap-stale-jobs": {
                "task": TASK_REAP_STALE_JOBS,
                "schedule": celery_schedule(settings.STALE_JOB_SWEEP_SECONDS),
            },
            "sweep-work-dir": {
                "task": TASK_SWEEP_WORK_DIR,
                "schedule": celery_schedule(settings.WORK_DIR_SWEEP_SECONDS),
            },
            "dispatch-due-schedules": {
                "task": TASK_DISPATCH_SCHEDULES,
                "schedule": celery_schedule(settings.SCHEDULE_TICK_SECONDS),
            },
        },
    )
    return app


celery_app = create_celery_app()
