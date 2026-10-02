"""Video reads, edits and deletion, plus the caller's usage quota.

Video *creation* is intentionally absent: videos come into existence through
the generation pipeline, which is the next phase of work. Letting clients POST
arbitrary video rows would bypass quota accounting entirely.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import delete, func, select

from apps.api.core.deps import CurrentUser, DbSession, OwnedVideo, PageParams
from apps.api.models import Video, VideoJob
from apps.api.schemas.common import Page
from apps.api.schemas.video import (
    VIDEO_STATUSES,
    QuotaStatus,
    VideoJobPublic,
    VideoPublic,
    VideoUpdate,
)
from apps.api.services import quota as quota_service

router = APIRouter(prefix="/videos", tags=["videos"])


@router.get("", response_model=Page[VideoPublic])
def list_videos(
    db: DbSession,
    user: CurrentUser,
    page: PageParams,
    status_filter: str | None = Query(default=None, alias="status"),
    project_id: int | None = Query(default=None),
) -> Page[VideoPublic]:
    """List the caller's videos across all projects, newest first."""
    filters = [Video.user_id == user.id]

    if status_filter:
        if status_filter not in VIDEO_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"status must be one of {', '.join(VIDEO_STATUSES)}.",
            )
        filters.append(Video.status == status_filter)

    if project_id is not None:
        filters.append(Video.project_id == project_id)

    total = db.scalar(select(func.count()).select_from(Video).where(*filters)) or 0
    videos = list(
        db.scalars(
            select(Video)
            .where(*filters)
            .order_by(Video.created_at.desc(), Video.id.desc())
            .limit(page.limit)
            .offset(page.offset)
        )
    )

    return Page.build(
        [VideoPublic.model_validate(v) for v in videos],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/quota", response_model=QuotaStatus)
def read_quota(db: DbSession, user: CurrentUser) -> QuotaStatus:
    """How many videos the caller may still generate this period.

    Declared before `/{video_id}` so the literal path wins the route match.
    """
    q = quota_service.get_quota(db, user.id)
    return QuotaStatus(
        plan_name=q.plan_name,
        limit_monthly=q.limit_monthly,
        used=q.used,
        remaining=q.remaining,
        unlimited=q.unlimited,
        period_start=q.period_start,
        period_end=q.period_end,
    )


@router.get("/{video_id}", response_model=VideoPublic)
def get_video(video: OwnedVideo) -> Video:
    return video


@router.patch("/{video_id}", response_model=VideoPublic)
def update_video(payload: VideoUpdate, video: OwnedVideo, db: DbSession) -> Video:
    """Edit the script before rendering.

    Rejected once the video is being generated — changing the script mid-render
    would silently desync the output from the stored text.
    """
    if video.status == "generating":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This video is currently generating and cannot be edited.",
        )

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(video, field, value)

    db.commit()
    db.refresh(video)
    return video


@router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_video(video: OwnedVideo, db: DbSession) -> Response:
    """Delete a video and its jobs.

    Usage events are left intact: quota is metered per period, so deleting a
    render does not hand back an allowance that was already consumed.
    """
    if video.status == "generating":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This video is currently generating. Cancel the job first.",
        )

    db.execute(delete(VideoJob).where(VideoJob.video_id == video.id))
    db.delete(video)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{video_id}/jobs", response_model=list[VideoJobPublic])
def list_video_jobs(video: OwnedVideo, db: DbSession) -> list[VideoJob]:
    """Job history for a video, newest first."""
    return list(
        db.scalars(
            select(VideoJob)
            .where(VideoJob.video_id == video.id)
            .order_by(VideoJob.created_at.desc(), VideoJob.id.desc())
        )
    )
