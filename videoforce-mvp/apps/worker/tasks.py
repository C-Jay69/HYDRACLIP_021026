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
from apps.api.services import maintenance
from apps.api.services.jobs import run_generation_job
from apps.worker.celery_app import (
    TASK_DISPATCH_SCHEDULES,
    TASK_GENERATE_VIDEO,
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
    db = SessionLocal()
    try:
        claimed = maintenance.claim_due_schedules(db)
        if claimed:
            # Publishing needs platform OAuth, which is the next phase.
            logger.info(
                "claimed %s due schedule(s) %s, but publishing is not "
                "implemented yet",
                len(claimed),
                claimed,
            )
        return {"claimed": claimed}
    finally:
        db.close()
