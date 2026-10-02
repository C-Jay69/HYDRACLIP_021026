"""Periodic housekeeping, invoked by Celery beat.

The logic lives here rather than in the worker package so it can be tested
without a broker. ``apps/worker/tasks.py`` is a thin wrapper over these
functions.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from apps.api.core.config import settings
from apps.api.models import Schedule, Video, VideoJob
from apps.api.services.jobs import (
    ACTIVE_JOB_STATUSES,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_RUNNING,
)

logger = logging.getLogger(__name__)

#: A pending job older than this was almost certainly never delivered to a
#: worker -- a broker hiccup, or an inline runner lost to a restart.
UNCLAIMED_JOB_GRACE_SECONDS = 600.0


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def reap_stale_jobs(db: Session, now: datetime | None = None) -> int:
    """Fail jobs that can no longer be running, and release their quota slot.

    Two cases, both of which otherwise leave a job "in flight" forever and
    permanently consume one of the user's monthly slots:

    * ``running`` past ``JOB_TIMEOUT_SECONDS`` -- the worker died mid-task.
    * ``pending`` past the grace period -- the dispatch never arrived.
    """
    now = now or _utcnow()
    running_cutoff = now - timedelta(seconds=settings.JOB_TIMEOUT_SECONDS)
    pending_cutoff = now - timedelta(seconds=UNCLAIMED_JOB_GRACE_SECONDS)

    stale = list(
        db.scalars(
            select(VideoJob).where(
                VideoJob.status.in_(ACTIVE_JOB_STATUSES),
                (
                    (VideoJob.status == STATUS_RUNNING)
                    & (VideoJob.started_at.is_not(None))
                    & (VideoJob.started_at < running_cutoff)
                )
                | (
                    (VideoJob.status == STATUS_PENDING)
                    & (VideoJob.created_at.is_not(None))
                    & (VideoJob.created_at < pending_cutoff)
                ),
            )
        )
    )

    for job in stale:
        # Captured before the UPDATE: executing it expires the ORM object, so
        # reading job.status afterwards would report "failed" either way.
        original_status = job.status

        if original_status == STATUS_RUNNING:
            reason = (
                f"Timed out: no progress for more than "
                f"{int(settings.JOB_TIMEOUT_SECONDS)}s. The worker running it "
                f"probably died."
            )
        else:
            reason = (
                f"Never started: no worker claimed this job within "
                f"{int(UNCLAIMED_JOB_GRACE_SECONDS)}s."
            )

        db.execute(
            update(VideoJob)
            .where(VideoJob.id == job.id, VideoJob.status == original_status)
            .values(status=STATUS_FAILED, completed_at=now, error_message=reason)
        )
        db.execute(
            update(Video)
            .where(Video.id == job.video_id)
            .values(status=STATUS_FAILED, error_message=reason)
        )
        logger.warning("reaped stale job %s (was %s)", job.id, original_status)

    if stale:
        db.commit()

    return len(stale)


def sweep_work_dir(now: float | None = None) -> int:
    """Delete intermediate artefacts older than WORK_DIR_TTL_SECONDS.

    Generation writes WAV and MP4 files into a scratch directory. Nothing
    cleaned them up, so the volume filled over time.
    """
    work_dir = Path(settings.MEDIA_WORK_DIR)
    if not work_dir.is_dir():
        return 0

    now = now if now is not None else time.time()
    cutoff = now - settings.WORK_DIR_TTL_SECONDS
    removed = 0

    for entry in work_dir.iterdir():
        if not entry.is_file():
            continue
        try:
            if entry.stat().st_mtime < cutoff:
                entry.unlink()
                removed += 1
        except OSError as exc:  # a concurrent job may already have moved it
            logger.debug("could not remove %s: %s", entry, exc)

    if removed:
        logger.info("swept %s stale artefact(s) from %s", removed, work_dir)
    return removed


def claim_due_schedules(db: Session, now: datetime | None = None) -> list[int]:
    """Claim schedules whose time has come, returning their ids.

    Claiming flips ``pending`` -> ``running`` with a guarded UPDATE, so two
    beat ticks overlapping cannot publish the same post twice.

    Claiming only marks the rows; the caller enqueues a publish task per id.
    Splitting it that way keeps the beat tick short and stops one slow
    upload from delaying every other due post.
    """
    now = now or _utcnow()

    due = list(
        db.scalars(
            select(Schedule)
            .where(Schedule.status == STATUS_PENDING, Schedule.scheduled_at <= now)
            .order_by(Schedule.scheduled_at)
        )
    )

    claimed: list[int] = []
    for schedule in due:
        result = db.execute(
            update(Schedule)
            .where(Schedule.id == schedule.id, Schedule.status == STATUS_PENDING)
            .values(status=STATUS_RUNNING)
        )
        if result.rowcount == 1:
            claimed.append(schedule.id)

    if claimed:
        db.commit()

    return claimed
