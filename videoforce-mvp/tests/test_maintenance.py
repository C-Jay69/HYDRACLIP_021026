"""Periodic housekeeping: the stale-job reaper, the work-dir sweeper, and
claiming due schedules.

These run on celery beat but are tested directly, without a broker.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import pytest

from apps.api.core.config import settings
from apps.api.models import Project, Schedule, Video, VideoJob
from apps.api.services import maintenance
from apps.api.services import quota as quota_service


def _naive_utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _job(db, user_id: int, *, status: str, age_seconds: float, started: bool = True):
    now = _naive_utcnow()
    created = now - timedelta(seconds=age_seconds)

    project = Project(user_id=user_id, title="P", topic="t", status="generating")
    db.add(project)
    db.flush()
    video = Video(project_id=project.id, user_id=user_id, status="generating")
    db.add(video)
    db.flush()
    job = VideoJob(
        video_id=video.id,
        job_type="generate",
        status=status,
        created_at=created,
        started_at=created if started else None,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


# --- Reaping stale jobs ---------------------------------------------------------


def test_running_job_past_the_timeout_is_failed(db, make_user):
    user = make_user()
    job = _job(db, user.id, status="running", age_seconds=settings.JOB_TIMEOUT_SECONDS + 60)

    assert maintenance.reap_stale_jobs(db) == 1

    db.expire_all()
    reaped = db.get(VideoJob, job.id)
    assert reaped.status == "failed"
    assert "Timed out" in reaped.error_message
    assert reaped.completed_at is not None


def test_the_video_is_failed_alongside_its_job(db, make_user):
    user = make_user()
    job = _job(db, user.id, status="running", age_seconds=settings.JOB_TIMEOUT_SECONDS + 60)
    video_id = job.video_id

    maintenance.reap_stale_jobs(db)

    db.expire_all()
    video = db.get(Video, video_id)
    assert video.status == "failed"
    assert "Timed out" in video.error_message


def test_a_recent_running_job_is_left_alone(db, make_user):
    user = make_user()
    job = _job(db, user.id, status="running", age_seconds=30)

    assert maintenance.reap_stale_jobs(db) == 0

    db.expire_all()
    assert db.get(VideoJob, job.id).status == "running"


def test_pending_job_past_the_grace_period_is_failed(db, make_user):
    """A dispatch that never reached a worker would otherwise hang forever."""
    user = make_user()
    job = _job(
        db,
        user.id,
        status="pending",
        age_seconds=maintenance.UNCLAIMED_JOB_GRACE_SECONDS + 60,
        started=False,
    )

    assert maintenance.reap_stale_jobs(db) == 1

    db.expire_all()
    reaped = db.get(VideoJob, job.id)
    assert reaped.status == "failed"
    assert "Never started" in reaped.error_message


def test_a_recently_queued_pending_job_is_left_alone(db, make_user):
    user = make_user()
    job = _job(db, user.id, status="pending", age_seconds=5, started=False)

    assert maintenance.reap_stale_jobs(db) == 0

    db.expire_all()
    assert db.get(VideoJob, job.id).status == "pending"


def test_terminal_jobs_are_never_touched(db, make_user):
    user = make_user()
    for status in ("completed", "failed", "cancelled"):
        _job(db, user.id, status=status, age_seconds=99_999)

    assert maintenance.reap_stale_jobs(db) == 0


def test_reaping_releases_the_quota_slot(db, make_user):
    """The real cost of a wedged job: it holds one of three monthly slots."""
    user = make_user()
    _job(db, user.id, status="running", age_seconds=settings.JOB_TIMEOUT_SECONDS + 60)

    assert quota_service.get_quota(db, user.id).in_flight == 1
    maintenance.reap_stale_jobs(db)
    assert quota_service.get_quota(db, user.id).in_flight == 0


def test_reaping_does_not_consume_quota(db, make_user):
    """A job killed by a dead worker must not bill the user."""
    user = make_user()
    _job(db, user.id, status="running", age_seconds=settings.JOB_TIMEOUT_SECONDS + 60)

    maintenance.reap_stale_jobs(db)
    assert quota_service.get_quota(db, user.id).used == 0


def test_reaping_is_idempotent(db, make_user):
    user = make_user()
    _job(db, user.id, status="running", age_seconds=settings.JOB_TIMEOUT_SECONDS + 60)

    assert maintenance.reap_stale_jobs(db) == 1
    assert maintenance.reap_stale_jobs(db) == 0


# --- Sweeping the work directory ----------------------------------------------------


def test_old_artefacts_are_removed(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "MEDIA_WORK_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "WORK_DIR_TTL_SECONDS", 3600.0)

    old = tmp_path / "old.wav"
    old.write_bytes(b"x")
    import os

    stale = time.time() - 7200
    os.utime(old, (stale, stale))

    assert maintenance.sweep_work_dir() == 1
    assert not old.exists()


def test_fresh_artefacts_survive(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "MEDIA_WORK_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "WORK_DIR_TTL_SECONDS", 3600.0)

    fresh = tmp_path / "fresh.wav"
    fresh.write_bytes(b"x")

    assert maintenance.sweep_work_dir() == 0
    assert fresh.exists()


def test_sweeping_skips_directories(monkeypatch, tmp_path):
    """The filesystem broker keeps its spool here; deleting it loses messages."""
    monkeypatch.setattr(settings, "MEDIA_WORK_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "WORK_DIR_TTL_SECONDS", 0.0)

    nested = tmp_path / "broker"
    nested.mkdir()

    maintenance.sweep_work_dir()
    assert nested.is_dir()


def test_sweeping_a_missing_directory_is_not_an_error(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "MEDIA_WORK_DIR", str(tmp_path / "nope"))
    assert maintenance.sweep_work_dir() == 0


# --- Claiming due schedules ------------------------------------------------------------


def _schedule(db, user_id: int, *, minutes: float, status: str = "pending") -> Schedule:
    row = Schedule(
        video_id=1,
        user_id=user_id,
        platform="youtube",
        scheduled_at=_naive_utcnow() + timedelta(minutes=minutes),
        status=status,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_a_due_schedule_is_claimed(db, make_user):
    user = make_user()
    row = _schedule(db, user.id, minutes=-5)

    assert maintenance.claim_due_schedules(db) == [row.id]

    db.expire_all()
    assert db.get(Schedule, row.id).status == "running"


def test_a_future_schedule_is_not_claimed(db, make_user):
    user = make_user()
    row = _schedule(db, user.id, minutes=60)

    assert maintenance.claim_due_schedules(db) == []

    db.expire_all()
    assert db.get(Schedule, row.id).status == "pending"


def test_a_schedule_is_claimed_only_once(db, make_user):
    """Two overlapping beat ticks must not publish the same post twice."""
    user = make_user()
    _schedule(db, user.id, minutes=-5)

    first = maintenance.claim_due_schedules(db)
    second = maintenance.claim_due_schedules(db)

    assert len(first) == 1
    assert second == []


def test_cancelled_schedules_are_skipped(db, make_user):
    user = make_user()
    _schedule(db, user.id, minutes=-5, status="cancelled")
    assert maintenance.claim_due_schedules(db) == []


def test_due_schedules_are_claimed_in_time_order(db, make_user):
    user = make_user()
    later = _schedule(db, user.id, minutes=-1)
    earlier = _schedule(db, user.id, minutes=-30)

    assert maintenance.claim_due_schedules(db) == [earlier.id, later.id]
