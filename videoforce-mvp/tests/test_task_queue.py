"""Runner selection, Celery dispatch, and the Celery app's configuration.

No broker is required: dispatch is asserted against a fake Celery app.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from apps.api.core.config import settings
from apps.api.models import Project, Video, VideoJob
from apps.api.services import jobs as job_service
from apps.api.services import task_queue


@pytest.fixture
def restore_runner():
    previous = job_service._runner
    yield
    job_service.set_runner(previous)


# --- Runner selection -----------------------------------------------------------


def test_default_is_the_inline_runner(monkeypatch, restore_runner):
    monkeypatch.setattr(settings, "JOB_RUNNER", "inline")
    assert task_queue.configure_job_runner() == "inline"
    assert job_service._runner is job_service._default_runner


def test_celery_runner_is_installed_when_configured(monkeypatch, restore_runner):
    monkeypatch.setattr(settings, "JOB_RUNNER", "celery")
    assert task_queue.configure_job_runner() == "celery"
    assert job_service._runner is task_queue.celery_runner


def test_job_runner_setting_rejects_unknown_values(monkeypatch):
    """A typo in JOB_RUNNER should fail at boot, not silently run inline."""
    from pydantic import ValidationError

    from apps.api.core.config import Settings

    with pytest.raises(ValidationError):
        Settings(
            SECRET_KEY="x" * 32,
            DATABASE_URL="sqlite:///:memory:",
            JOB_RUNNER="celary",
        )


# --- Broker URL handling ------------------------------------------------------------


def test_broker_defaults_to_redis_url(monkeypatch):
    monkeypatch.setattr(settings, "CELERY_BROKER_URL", "")
    monkeypatch.setattr(settings, "REDIS_URL", "redis://example:6379/3")
    assert settings.celery_broker_url == "redis://example:6379/3"


def test_explicit_broker_wins(monkeypatch):
    monkeypatch.setattr(settings, "CELERY_BROKER_URL", "amqp://rabbit:5672//")
    assert settings.celery_broker_url == "amqp://rabbit:5672//"


@pytest.mark.parametrize(
    "configured,expected",
    [
        ("postgresql://u:p@h/db", "db+postgresql://u:p@h/db"),
        ("postgres://u:p@h/db", "db+postgres://u:p@h/db"),
        ("sqlite:////tmp/x.db", "db+sqlite:////tmp/x.db"),
        ("redis://h:6379/1", "redis://h:6379/1"),
        ("db+postgresql://u:p@h/db", "db+postgresql://u:p@h/db"),
    ],
)
def test_database_result_backends_get_the_db_prefix(monkeypatch, configured, expected):
    """Celery reads the scheme as a backend *module* name: a bare
    "postgresql://" raises ModuleNotFoundError and takes the worker down."""
    monkeypatch.setattr(settings, "CELERY_RESULT_BACKEND", configured)
    assert settings.celery_result_backend == expected


def test_broker_passwords_are_redacted_before_logging():
    assert task_queue._redact("redis://:hunter2@redis:6379/0") == "redis://***@redis:6379/0"
    assert task_queue._redact("redis://redis:6379/0") == "redis://redis:6379/0"


# --- Dispatch ---------------------------------------------------------------------------


async def test_celery_runner_sends_the_task_by_name(monkeypatch, db, make_user):
    """Dispatch must not import apps.worker.tasks into the API process."""
    user = make_user()
    project = Project(user_id=user.id, title="P", topic="t", status="pending")
    db.add(project)
    db.commit()
    db.refresh(project)
    video, job = job_service.create_generation_job(db, project)
    db.commit()

    fake_app = MagicMock()
    fake_app.send_task.return_value = MagicMock(id="task-abc-123")
    monkeypatch.setattr(task_queue, "_celery_app", lambda: fake_app)

    await task_queue.celery_runner(job.id)

    fake_app.send_task.assert_called_once()
    name, kwargs = fake_app.send_task.call_args[0][0], fake_app.send_task.call_args[1]
    assert name == "videoforce.generate_video"
    assert kwargs["args"] == [job.id]


async def test_dispatch_records_the_task_id(monkeypatch, db, make_user):
    """Needed to correlate a stuck job with what flower shows."""
    user = make_user()
    project = Project(user_id=user.id, title="P", topic="t", status="pending")
    db.add(project)
    db.commit()
    db.refresh(project)
    video, job = job_service.create_generation_job(db, project)
    db.commit()
    job_id = job.id

    fake_app = MagicMock()
    fake_app.send_task.return_value = MagicMock(id="task-abc-123")
    monkeypatch.setattr(task_queue, "_celery_app", lambda: fake_app)

    await task_queue.celery_runner(job_id)

    db.expire_all()
    assert db.get(VideoJob, job_id).celery_task_id == "task-abc-123"


async def test_an_unreachable_broker_surfaces_as_503(monkeypatch, db, make_user):
    """Better a clear 503 than a job row that no worker will ever see."""
    user = make_user()
    project = Project(user_id=user.id, title="P", topic="t", status="pending")
    db.add(project)
    db.commit()
    db.refresh(project)
    video, job = job_service.create_generation_job(db, project)
    db.commit()

    fake_app = MagicMock()
    fake_app.send_task.side_effect = OSError("Connection refused")
    monkeypatch.setattr(task_queue, "_celery_app", lambda: fake_app)

    with pytest.raises(HTTPException) as exc:
        await task_queue.celery_runner(job.id)

    assert exc.value.status_code == 503
    assert "queue is unavailable" in exc.value.detail


# --- Celery application configuration -----------------------------------------------------


def test_celery_app_registers_every_task():
    import apps.worker.tasks  # noqa: F401  (registers them)
    from apps.worker.celery_app import celery_app

    registered = {n for n in celery_app.tasks if n.startswith("videoforce.")}
    assert registered == {
        "videoforce.generate_video",
        "videoforce.reap_stale_jobs",
        "videoforce.sweep_work_dir",
        "videoforce.dispatch_due_schedules",
        "videoforce.publish_schedule",
    }


def test_long_tasks_are_configured_safely():
    from apps.worker.celery_app import celery_app

    conf = celery_app.conf
    # Without late acks a worker crash loses the job silently.
    assert conf.task_acks_late is True
    assert conf.task_reject_on_worker_lost is True
    # With prefetching, one worker hoards long jobs while its peers idle.
    assert conf.worker_prefetch_multiplier == 1
    # The soft limit must fire first so the job can record its own failure.
    assert conf.task_soft_time_limit < conf.task_time_limit


def test_maintenance_is_routed_off_the_generation_queue():
    """Housekeeping must not queue behind a 15-minute render."""
    from apps.worker.celery_app import celery_app

    routes = celery_app.conf.task_routes
    # Publishing waits on provider processing, so it belongs with the other
    # slow work rather than in front of short maintenance ticks.
    for task in ("videoforce.generate_video", "videoforce.publish_schedule"):
        assert routes[task]["queue"] == "generation"
    for task in (
        "videoforce.reap_stale_jobs",
        "videoforce.sweep_work_dir",
        "videoforce.dispatch_due_schedules",
    ):
        assert routes[task]["queue"] == "maintenance"


def test_beat_schedules_all_three_periodic_tasks():
    from apps.worker.celery_app import celery_app

    scheduled = {entry["task"] for entry in celery_app.conf.beat_schedule.values()}
    assert scheduled == {
        "videoforce.reap_stale_jobs",
        "videoforce.sweep_work_dir",
        "videoforce.dispatch_due_schedules",
    }


# --- Readiness --------------------------------------------------------------------------------


def test_queue_health_is_trivially_ok_for_the_inline_runner(monkeypatch):
    monkeypatch.setattr(settings, "JOB_RUNNER", "inline")
    assert task_queue.queue_health() == {"runner": "inline", "ok": True}


def test_queue_health_reports_an_unreachable_broker(monkeypatch):
    monkeypatch.setattr(settings, "JOB_RUNNER", "celery")

    fake_app = MagicMock()
    fake_app.connection_for_read.side_effect = OSError("Connection refused")
    monkeypatch.setattr(task_queue, "_celery_app", lambda: fake_app)

    health = task_queue.queue_health()
    assert health["ok"] is False
    assert health["error"] == "OSError"


def test_readyz_reports_degraded_when_the_queue_is_down(client, monkeypatch):
    monkeypatch.setattr(settings, "JOB_RUNNER", "celery")

    fake_app = MagicMock()
    fake_app.connection_for_read.side_effect = OSError("refused")
    monkeypatch.setattr(task_queue, "_celery_app", lambda: fake_app)

    body = client.get("/readyz").json()
    assert body["status"] == "degraded"
    assert body["database"] == "ok"
    assert body["queue"]["ok"] is False
