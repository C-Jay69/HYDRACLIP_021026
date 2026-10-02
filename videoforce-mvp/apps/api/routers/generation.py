"""Generation endpoints: start a job, follow it, cancel it.

Before this, ``AIPipeline`` had no caller anywhere in the codebase.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select

from apps.api.core.deps import CurrentUser, DbSession, OwnedProject
from apps.api.models import Video, VideoJob
from apps.api.schemas.job import (
    GenerationAccepted,
    GenerationRequest,
    PipelineStatus,
    StageInfo,
    StockProviderInfo,
)
from apps.api.schemas.video import VideoJobPublic, VideoPublic
from apps.api.core.config import settings
from apps.api.services import jobs as job_service
from apps.api.services import quota as quota_service
from apps.api.services.stock import get_stock_library

router = APIRouter(tags=["generation"])


@router.get("/pipeline/status", response_model=PipelineStatus)
async def pipeline_status(user: CurrentUser) -> PipelineStatus:
    """Which pipeline stages this deployment can actually run.

    Lets a client disable controls it cannot fulfil instead of discovering the
    missing tooling through a failed job.
    """
    problems = await job_service.preflight(job_service.STAGE_NAMES)
    return PipelineStatus(
        stages=[
            StageInfo(
                name=stage.name,
                description=stage.description,
                available=stage.name not in problems,
                reason=problems.get(stage.name),
            )
            for stage in job_service.STAGES
        ],
        default_stages=list(job_service.DEFAULT_STAGES),
        # Which footage sources are usable, so a client can tell "no API key"
        # apart from "nothing matched your topic".
        stock_providers=[
            StockProviderInfo(**entry) for entry in get_stock_library().status()
        ],
        output_format={
            "width": settings.VIDEO_WIDTH,
            "height": settings.VIDEO_HEIGHT,
            "fps": settings.VIDEO_FPS,
        },
    )


@router.post(
    "/projects/{project_id}/generate",
    response_model=GenerationAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_generation(
    payload: GenerationRequest,
    project: OwnedProject,
    db: DbSession,
    user: CurrentUser,
) -> GenerationAccepted:
    """Start generating a video for this project.

    Returns 202 with a job to poll. The work itself is asynchronous.
    """
    stages = list(payload.stages) if payload.stages else list(job_service.DEFAULT_STAGES)

    # One generation per project at a time. Without this, a double-clicked
    # button creates two videos and bills the user twice.
    existing = job_service.active_job_for_project(db, project.id)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"A generation job is already {existing.status} for this project "
                f"(job {existing.id}). Cancel it before starting another."
            ),
        )

    # Charged on success, but in-flight jobs hold a slot so concurrent
    # requests cannot all pass this gate on the same remaining allowance.
    quota_service.assert_quota_available(db, user.id)

    # Fail fast rather than queue work that cannot possibly finish.
    problems = await job_service.preflight(stages)
    if problems:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": "The generation pipeline is not ready for the requested stages.",
                "unavailable_stages": problems,
            },
        )

    video, job = job_service.create_generation_job(
        db,
        project,
        style=payload.style,
        duration=payload.duration,
        voice=payload.voice,
        stages=stages,
    )
    # Commit before dispatch: a runner must never look for a row that the
    # transaction has not made visible yet.
    db.commit()
    db.refresh(video)
    db.refresh(job)

    await job_service.enqueue(job.id)
    db.refresh(job)

    return GenerationAccepted(
        job=VideoJobPublic.model_validate(job),
        video=VideoPublic.model_validate(video),
        stages=stages,
        poll_url=f"/jobs/{job.id}",
    )


def _owned_job(db, user, job_id: int) -> VideoJob:
    """Resolve a job the caller owns, 404 otherwise.

    Jobs hang off videos, so ownership is checked one hop away. As elsewhere,
    another user's job is indistinguishable from a missing one.
    """
    row = db.execute(
        select(VideoJob, Video.user_id)
        .join(Video, Video.id == VideoJob.video_id)
        .where(VideoJob.id == job_id)
    ).first()

    is_admin = (user.role or "").upper() == "ADMIN"
    if row is None or (row[1] != user.id and not is_admin):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found."
        )
    return row[0]


@router.get("/jobs/{job_id}", response_model=VideoJobPublic)
def get_job(job_id: int, db: DbSession, user: CurrentUser) -> VideoJob:
    """Poll a generation job."""
    return _owned_job(db, user, job_id)


@router.post("/jobs/{job_id}/cancel", response_model=VideoJobPublic)
def cancel_job(job_id: int, db: DbSession, user: CurrentUser) -> VideoJob:
    """Cancel a pending or running job.

    A running stage shells out to an external binary and cannot be preempted,
    so cancellation takes effect at the next stage boundary.
    """
    job = _owned_job(db, user, job_id)

    if not job_service.request_cancel(db, job):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job {job.id} has already finished ({job.status}).",
        )

    db.expire_all()
    return _owned_job(db, user, job_id)
