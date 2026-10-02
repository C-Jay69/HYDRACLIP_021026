"""Selects how background jobs execute, and dispatches them.

Phase 3 left ``jobs.set_runner()`` as the seam between the HTTP layer and the
executor. This module is what plugs into it:

* ``inline``  — asyncio tasks inside the API process. Fine for development,
  wrong for production: the work competes with request handling and anything
  in flight is lost on restart.
* ``celery``  — hand the job id to the worker fleet.

Dispatch goes through ``send_task`` by name, so the API never imports
``apps.worker.tasks`` and therefore never pulls the pipeline, ffmpeg bindings
or model loaders into the web process.
"""

from __future__ import annotations

import logging

from fastapi import HTTPException, status

from apps.api.core.config import settings
from apps.api.services import jobs as job_service

logger = logging.getLogger(__name__)


def _celery_app():
    # Imported lazily so that `celery` is only required when it is used.
    from apps.worker.celery_app import celery_app

    return celery_app


async def celery_runner(job_id: int) -> None:
    """Queue a generation job on the worker fleet."""
    from apps.worker.celery_app import TASK_GENERATE_VIDEO

    try:
        result = _celery_app().send_task(TASK_GENERATE_VIDEO, args=[job_id])
    except Exception as exc:  # broker unreachable, auth failure, ...
        logger.exception("could not queue generation job %s", job_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "The job queue is unavailable, so generation could not be "
                "started. Please try again shortly."
            ),
        ) from exc

    # Recording the task id makes a stuck job traceable in flower.
    _record_task_id(job_id, result.id)


def _record_task_id(job_id: int, task_id: str) -> None:
    from apps.api.core.db import SessionLocal
    from apps.api.models import VideoJob

    db = SessionLocal()
    try:
        db.query(VideoJob).filter(VideoJob.id == job_id).update(
            {"celery_task_id": task_id}
        )
        db.commit()
    except Exception:  # noqa: BLE001 - never fail dispatch over bookkeeping
        logger.warning("could not record celery task id for job %s", job_id)
        db.rollback()
    finally:
        db.close()


def configure_job_runner() -> str:
    """Install the runner named by settings.JOB_RUNNER. Returns its name."""
    if settings.JOB_RUNNER == "celery":
        job_service.set_runner(celery_runner)
        logger.info(
            "job runner: celery (broker %s)", _redact(settings.celery_broker_url)
        )
        return "celery"

    logger.warning(
        "job runner: inline — jobs run inside the API process and are lost "
        "on restart. Set JOB_RUNNER=celery with a worker for production."
    )
    return "inline"


def _redact(url: str) -> str:
    """Hide any password in a broker URL before it reaches the logs."""
    if "@" not in url:
        return url
    scheme, _, rest = url.partition("://")
    _, _, host = rest.rpartition("@")
    return f"{scheme}://***@{host}"


def queue_health() -> dict:
    """Broker reachability, for the readiness probe."""
    if settings.JOB_RUNNER != "celery":
        return {"runner": "inline", "ok": True}

    try:
        conn = _celery_app().connection_for_read()
        conn.ensure_connection(max_retries=0, timeout=2)
        conn.release()
        return {"runner": "celery", "ok": True}
    except Exception as exc:  # noqa: BLE001
        return {"runner": "celery", "ok": False, "error": type(exc).__name__}
