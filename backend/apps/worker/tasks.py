"""Celery tasks.

Thin wrappers only. The logic lives in ``apps.api.services`` so it can be
tested without a broker, and so the same code path runs whether jobs execute
inline or through Celery.
"""

from __future__ import annotations

import asyncio
import logging

from celery.exceptions import SoftTimeLimitExceeded

from apps.api.core.db import SessionLocal
from apps.api.services import maintenance, publishing
from apps.api.services.jobs import run_generation_job
from apps.worker.celery_app import (
    TASK_DISPATCH_SCHEDULES,
    TASK_GENERATE_VIDEO,
    TASK_PUBLISH_SCHEDULE,
    TASK_REAP_STALE_JOBS,
    TASK_SWEEP_WORK_DIR,
    celery_app,
)

logger = logging.getLogger(__name__)


@celery_app.task(name=TASK_GENERATE_VIDEO, bind=True)
def generate_video(self, job_id: int) -> dict:
    """Run one generation job.

    ``run_generation_job`` records failures on the row itself and does not
    raise, so there is deliberately no Celery-level retry: a retry would
    re-run a job whose status is already terminal.
    """
    try:
        asyncio.run(run_generation_job(job_id))
    except SoftTimeLimitExceeded:
        # Mark it failed rather than letting the hard limit kill us silently.
        logger.warning("generation job %s hit the soft time limit", job_id)
        db = SessionLocal()
        try:
            maintenance.reap_stale_jobs(db)
        finally:
            db.close()
        raise
    return {"job_id": job_id}


@celery_app.task(name=TASK_REAP_STALE_JOBS)
def reap_stale_jobs() -> dict:
    db = SessionLocal()
    try:
        return {"reaped": maintenance.reap_stale_jobs(db)}
    finally:
        db.close()


@celery_app.task(name=TASK_SWEEP_WORK_DIR)
def sweep_work_dir() -> dict:
    return {"removed": maintenance.sweep_work_dir()}


@celery_app.task(name=TASK_DISPATCH_SCHEDULES)
def dispatch_due_schedules() -> dict:
    """Claim schedules whose time has come and hand each to a publish task.

    Dispatch and publication are separate tasks so one slow upload cannot
    hold up the beat tick, and so a worker lost mid-upload affects only its
    own schedule.
    """
    db = SessionLocal()
    try:
        claimed = maintenance.claim_due_schedules(db)
    finally:
        db.close()

    dispatched = []
    for schedule_id in claimed:
        try:
            celery_app.send_task(TASK_PUBLISH_SCHEDULE, args=[schedule_id])
            dispatched.append(schedule_id)
        except Exception as exc:  # noqa: BLE001 - broker trouble
            # The row is already 'running'. Record the failure rather than
            # leaving it stuck there with no explanation.
            logger.exception("Could not enqueue publish for schedule %s", schedule_id)
            db = SessionLocal()
            try:
                schedule = db.get(publishing.Schedule, schedule_id)
                if schedule is not None:
                    publishing.record_failure(
                        db, schedule, f"Could not enqueue the publish task: {exc}"
                    )
            finally:
                db.close()

    if claimed:
        logger.info("dispatched %s due schedule(s): %s", len(dispatched), dispatched)
    return {"claimed": claimed, "dispatched": dispatched}


@celery_app.task(name=TASK_PUBLISH_SCHEDULE, bind=True)
def publish_schedule(self, schedule_id: int) -> dict:
    """Publish one scheduled post.

    No autoretry: ``publish_schedule`` records terminal failure on the row
    itself, and a blind retry risks double-posting when the provider
    actually succeeded but the response was lost.
    """
    db = SessionLocal()
    try:
        return publishing.publish_schedule(db, schedule_id)
    except SoftTimeLimitExceeded:
        logger.error("Publishing schedule %s exceeded its time limit", schedule_id)
        raise
    finally:
        db.close()
