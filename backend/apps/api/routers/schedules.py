"""Scheduling videos for publication, and the record of what was published.

Phase 4 built the beat tick that claims due schedules, but nothing could
create a row for it to find. These are those endpoints.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, select

from apps.api.core.deps import CurrentUser, DbSession, PageParams
from apps.api.models import Video
from apps.api.models.schedule import PublishedPost, Schedule
from apps.api.schemas.common import Page
from apps.api.schemas.social import (
    SCHEDULE_STATUSES,
    PublishedPostPublic,
    ScheduleCreate,
    SchedulePublic,
)
from apps.api.services import publishing
from apps.api.services import social_accounts as accounts_service
from apps.api.services.platforms import get_platform

router = APIRouter(tags=["schedules"])

#: Statuses a user is allowed to cancel from. A running publish is already
#: talking to the provider, so cancelling it would be a lie.
CANCELLABLE = (publishing.STATUS_PENDING,)


def _naive_utc(value: datetime) -> datetime:
    """Normalise to naive UTC, matching the column type.

    Clients legitimately send offsets ("2026-10-05T09:00:00-05:00"); storing
    that verbatim next to naive rows would make every comparison wrong.
    """
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


@router.post(
    "/schedules", response_model=SchedulePublic, status_code=status.HTTP_201_CREATED
)
def create_schedule(
    payload: ScheduleCreate, db: DbSession, user: CurrentUser
) -> SchedulePublic:
    """Schedule a video for publication.

    The checks here are the ones that can be made now; whether the file can
    actually be uploaded is re-checked at publish time, because a video that
    is still generating today may well be ready by the scheduled hour.
    """
    video = db.get(Video, payload.video_id)
    if video is None or video.user_id != user.id:
        # 404 rather than 403 for someone else's video, matching the
        # ownership convention used everywhere else in the API.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Video not found."
        )

    client = get_platform(payload.platform)
    problem = client.configuration_error()
    if problem:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"{client.label} is {problem}.",
        )

    account = accounts_service.find_for_platform(db, user.id, payload.platform)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"No active {client.label} account is connected. Connect one "
                f"before scheduling."
            ),
        )

    scheduled_at = _naive_utc(payload.scheduled_at)
    if scheduled_at < datetime.now(timezone.utc).replace(tzinfo=None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="scheduled_at is in the past.",
        )

    duplicate = db.scalars(
        select(Schedule).where(
            Schedule.video_id == payload.video_id,
            Schedule.platform == payload.platform,
            Schedule.status.in_((publishing.STATUS_PENDING, publishing.STATUS_RUNNING)),
        )
    ).first()
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"This video is already scheduled for {client.label} "
                f"(schedule {duplicate.id})."
            ),
        )

    schedule = Schedule(
        video_id=payload.video_id,
        user_id=user.id,
        platform=payload.platform,
        scheduled_at=scheduled_at,
        timezone=payload.timezone,
        status=publishing.STATUS_PENDING,
    )
    db.add(schedule)

    # Per-post metadata has nowhere to live on `schedules`, so it rides on
    # the video's params. Adding columns for it is a schema change this
    # phase deliberately avoids.
    params = dict(video.generation_params_json or {})
    if payload.title:
        params["title"] = payload.title
    if payload.description:
        params["description"] = payload.description
    if payload.tags:
        params["tags"] = payload.tags
    params["privacy"] = payload.privacy
    video.generation_params_json = params

    db.commit()
    db.refresh(schedule)
    return SchedulePublic.model_validate(schedule)


@router.get("/schedules", response_model=Page[SchedulePublic])
def list_schedules(
    db: DbSession,
    user: CurrentUser,
    page: PageParams,
    status_filter: str | None = Query(default=None, alias="status"),
    platform: str | None = Query(default=None),
) -> Page[SchedulePublic]:
    """The caller's schedules, soonest first."""
    filters = [Schedule.user_id == user.id]

    if status_filter:
        if status_filter not in SCHEDULE_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"status must be one of {', '.join(SCHEDULE_STATUSES)}.",
            )
        filters.append(Schedule.status == status_filter)

    if platform:
        filters.append(Schedule.platform == platform.strip().lower())

    total = db.scalar(select(func.count()).select_from(Schedule).where(*filters)) or 0
    rows = list(
        db.scalars(
            select(Schedule)
            .where(*filters)
            .order_by(Schedule.scheduled_at, Schedule.id)
            .limit(page.limit)
            .offset(page.offset)
        )
    )
    return Page.build(
        [SchedulePublic.model_validate(r) for r in rows],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/schedules/{schedule_id}", response_model=SchedulePublic)
def get_schedule(schedule_id: int, db: DbSession, user: CurrentUser) -> SchedulePublic:
    schedule = _owned(db, user.id, schedule_id)
    return SchedulePublic.model_validate(schedule)


@router.delete("/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_schedule(schedule_id: int, db: DbSession, user: CurrentUser) -> Response:
    """Cancel a pending schedule.

    A schedule already being published cannot be cancelled: the request is
    in flight at the provider and pretending otherwise would leave the user
    with a post they were told was cancelled.
    """
    schedule = _owned(db, user.id, schedule_id)

    if schedule.status not in CANCELLABLE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"A schedule that is '{schedule.status}' cannot be cancelled."
            ),
        )

    schedule.status = publishing.STATUS_CANCELLED
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/published-posts", response_model=Page[PublishedPostPublic])
def list_published_posts(
    db: DbSession,
    user: CurrentUser,
    page: PageParams,
    platform: str | None = Query(default=None),
) -> Page[PublishedPostPublic]:
    """Every publish attempt, successful or not, newest first."""
    filters = [PublishedPost.user_id == user.id]
    if platform:
        filters.append(PublishedPost.platform == platform.strip().lower())

    total = db.scalar(
        select(func.count()).select_from(PublishedPost).where(*filters)
    ) or 0
    rows = list(
        db.scalars(
            select(PublishedPost)
            .where(*filters)
            .order_by(PublishedPost.id.desc())
            .limit(page.limit)
            .offset(page.offset)
        )
    )
    return Page.build(
        [PublishedPostPublic.model_validate(r) for r in rows],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


def _owned(db, user_id: int, schedule_id: int) -> Schedule:
    schedule = db.get(Schedule, schedule_id)
    if schedule is None or schedule.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found."
        )
    return schedule
