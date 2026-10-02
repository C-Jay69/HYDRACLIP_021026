"""Publishing a scheduled video to a platform.

The flow mirrors the job layer from Phase 3: every state transition is a
guarded UPDATE checked by ``rowcount``, so two workers racing on the same
schedule cannot both post.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import os
from datetime import datetime, timezone

from sqlalchemy import update
from sqlalchemy.orm import Session

from apps.api.models import Video
from apps.api.models.schedule import PublishedPost, Schedule
from apps.api.services.platforms import (
    PlatformError,
    PublishRequest,
    PublishResult,
    get_platform,
)
from apps.api.services.social_accounts import (
    AccountError,
    ReconnectRequired,
    ensure_fresh_token,
    find_for_platform,
)

logger = logging.getLogger(__name__)

STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_CANCELLED = "cancelled"
STATUS_FAILED = "failed"


class NotPublishable(RuntimeError):
    """The schedule cannot be published, and retrying will not help."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# --- Preflight ------------------------------------------------------------------


def preflight(db: Session, schedule: Schedule) -> tuple[Video, object]:
    """Check everything needed to publish, before touching the network.

    Returns ``(video, account)``. Raises :class:`NotPublishable` with a
    message meant to be shown to the user.
    """
    video = db.get(Video, schedule.video_id)
    if video is None:
        raise NotPublishable(
            f"Video {schedule.video_id} no longer exists."
        )
    if video.user_id != schedule.user_id:
        raise NotPublishable("The video does not belong to this user.")
    if video.status != "completed":
        raise NotPublishable(
            f"The video is '{video.status}', not 'completed', so there is "
            f"nothing to publish yet."
        )

    account = find_for_platform(db, schedule.user_id, schedule.platform)
    if account is None:
        raise NotPublishable(
            f"No active {schedule.platform} account is connected. Connect one "
            f"at /oauth/{schedule.platform}/authorize."
        )

    client = get_platform(schedule.platform)
    problem = client.configuration_error()
    if problem:
        raise NotPublishable(f"{client.label} is {problem}.")

    return video, account


def build_request(video: Video, schedule: Schedule, account) -> PublishRequest:
    """Assemble the provider-neutral publish request.

    ``storage_key`` is the only pointer the schema has to the rendered file.
    Whether it is a local path or an object-store key decides which providers
    can be used: the ones that fetch by URL need a public host, which this
    deployment does not yet have.
    """
    params = video.generation_params_json or {}
    local_path = video.storage_key if video.storage_key else None
    if local_path and not os.path.isfile(local_path):
        local_path = None

    return PublishRequest(
        video_url=params.get("public_url"),
        file_path=local_path,
        title=(params.get("title") or f"Video {video.id}")[:200],
        description=(video.script_text or "")[:5000],
        tags=list(params.get("tags") or []),
        privacy=params.get("privacy") or "private",
        account_id=account.account_id,
    )


def check_media_available(client, request: PublishRequest) -> None:
    """Fail early and clearly when the file the provider needs is missing.

    Worth doing separately: without it the user gets an opaque provider error
    hundreds of lines into an upload, instead of being told the video was
    never rendered.
    """
    if client.needs_public_url:
        if not request.video_url and not request.file_path:
            raise NotPublishable(
                f"{client.label} downloads the video from a public HTTPS URL. "
                f"No such URL is recorded for this video, and no local file "
                f"was found either. Video assembly and a public media host "
                f"must both be in place before {client.label} publishing can "
                f"work."
            )
    elif not request.file_path:
        raise NotPublishable(
            f"{client.label} uploads the file itself, but no rendered video "
            f"file exists at the recorded location. Video assembly is not "
            f"implemented yet, so there is nothing to upload."
        )


# --- Transitions ------------------------------------------------------------------


def claim(db: Session, schedule_id: int) -> Schedule | None:
    """Compare-and-set ``pending``/``running`` -> ``running``.

    ``running`` is accepted because ``dispatch_due_schedules`` already flips
    the row before enqueueing; the guard still rejects a schedule that has
    been cancelled or completed in the meantime.
    """
    result = db.execute(
        update(Schedule)
        .where(
            Schedule.id == schedule_id,
            Schedule.status.in_((STATUS_PENDING, STATUS_RUNNING)),
        )
        .values(status=STATUS_RUNNING, updated_at=_utcnow())
    )
    if result.rowcount != 1:
        db.rollback()
        return None
    db.commit()
    return db.get(Schedule, schedule_id)


def record_success(
    db: Session, schedule: Schedule, result: PublishResult, request: PublishRequest
) -> PublishedPost:
    db.execute(
        update(Schedule)
        .where(Schedule.id == schedule.id)
        .values(
            status=STATUS_COMPLETED,
            platform_post_id=result.post_id,
            platform_url=result.url,
            updated_at=_utcnow(),
        )
    )
    post = PublishedPost(
        video_id=schedule.video_id,
        schedule_id=schedule.id,
        user_id=schedule.user_id,
        platform=schedule.platform,
        platform_post_id=result.post_id,
        platform_url=result.url,
        title=request.title,
        description=request.description,
        tags=request.tags,
        status="published",
        published_at=_utcnow(),
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


def record_failure(db: Session, schedule: Schedule, reason: str) -> PublishedPost:
    db.execute(
        update(Schedule)
        .where(Schedule.id == schedule.id)
        .values(status=STATUS_FAILED, updated_at=_utcnow())
    )
    post = PublishedPost(
        video_id=schedule.video_id,
        schedule_id=schedule.id,
        user_id=schedule.user_id,
        platform=schedule.platform,
        status="failed",
        error_message=reason[:2000],
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


# --- Entry point ---------------------------------------------------------------------


def publish_schedule(db: Session, schedule_id: int) -> dict:
    """Publish one scheduled post. Never raises.

    Like ``run_generation_job``, this is the worker's entry point, so a
    failure has to end up recorded on the row rather than as a traceback the
    user can never see.
    """
    schedule = claim(db, schedule_id)
    if schedule is None:
        current = db.get(Schedule, schedule_id)
        state = current.status if current else "missing"
        logger.info(
            "Schedule %s was not claimable (status=%s); skipping.",
            schedule_id,
            state,
        )
        return {"schedule_id": schedule_id, "status": state, "published": False}

    try:
        video, account = preflight(db, schedule)
        client = get_platform(schedule.platform)
        request = build_request(video, schedule, account)
        check_media_available(client, request)

        token = _run(ensure_fresh_token(db, account))
        result = _run(client.publish(token, request))
    except (NotPublishable, ReconnectRequired) as exc:
        logger.warning("Schedule %s cannot be published: %s", schedule_id, exc)
        record_failure(db, schedule, str(exc))
        return {
            "schedule_id": schedule_id,
            "status": STATUS_FAILED,
            "published": False,
            "error": str(exc),
        }
    except (PlatformError, AccountError) as exc:
        logger.warning("Schedule %s failed to publish: %s", schedule_id, exc)
        record_failure(db, schedule, str(exc))
        return {
            "schedule_id": schedule_id,
            "status": STATUS_FAILED,
            "published": False,
            "error": str(exc),
        }
    except Exception as exc:  # noqa: BLE001 - the worker must never crash here
        logger.exception("Unexpected error publishing schedule %s", schedule_id)
        record_failure(db, schedule, f"Unexpected error: {exc}")
        return {
            "schedule_id": schedule_id,
            "status": STATUS_FAILED,
            "published": False,
            "error": str(exc),
        }

    post = record_success(db, schedule, result, request)
    logger.info(
        "Published schedule %s to %s as %s",
        schedule_id,
        schedule.platform,
        result.post_id,
    )
    return {
        "schedule_id": schedule_id,
        "status": STATUS_COMPLETED,
        "published": True,
        "platform_post_id": result.post_id,
        "platform_url": result.url,
        "published_post_id": post.id,
    }


def _run(awaitable):
    """Run an async provider call from the synchronous worker.

    The Celery worker is a plain thread with no running loop, so a fresh one
    is created per call. ``asyncio.run`` would be equivalent here but this
    form also works when a loop exists but is not running.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)

    # Already inside a loop (e.g. called from async test code): run the
    # coroutine on a separate loop in a worker thread, because asyncio.run
    # refuses to nest.
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, awaitable).result()
