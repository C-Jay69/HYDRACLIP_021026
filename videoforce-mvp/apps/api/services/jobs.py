"""Generation job lifecycle.

This is the layer the HTTP API talks to, and it is deliberately independent of
*how* work gets executed. Right now jobs run as asyncio tasks in the API
process; Phase 4 replaces the runner with Celery by calling ``set_runner()``,
and nothing in the router or the state machine changes.

Status model
------------
``VideoJob.status``  pending -> running -> completed | failed | cancelled
``Video.status``     pending -> generating -> completed | failed

Every transition is a conditional UPDATE guarded on the expected current
status, so two runners claiming the same job cannot both win, and a cancel
racing a stage boundary cannot be silently overwritten.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Iterable, Sequence

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from apps.api.core.config import settings
from apps.api.core.db import SessionLocal
from apps.api.models import Project, Video, VideoJob
from apps.api.services import quota as quota_service
from apps.api.services.ai_pipeline import (
    AIPipeline,
    PipelineError,
    PiperTTS,
    StageNotImplemented,
    get_ai_pipeline,
)

logger = logging.getLogger(__name__)

JOB_TYPE_GENERATE = "generate"

# Job statuses that mean "work is still owed".
ACTIVE_JOB_STATUSES: tuple[str, ...] = ("pending", "running")

STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"

TERMINAL_JOB_STATUSES: tuple[str, ...] = (
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_CANCELLED,
)


# --- Stages -------------------------------------------------------------------


@dataclass(frozen=True)
class Stage:
    name: str
    #: progress_pct once this stage finishes
    progress_at_end: int
    description: str


STAGES: tuple[Stage, ...] = (
    Stage("script", 40, "Write the script with the LLM"),
    Stage("voiceover", 80, "Synthesise the voiceover with Piper"),
    Stage("assemble", 100, "Source stock footage and render the MP4"),
)

STAGE_NAMES: tuple[str, ...] = tuple(s.name for s in STAGES)

#: Stages a request runs when it does not say otherwise.
#:
#: Script only. Assembly is implemented now, but it still needs the Piper
#: binary, a voice model, ffmpeg and at least one stock provider API key --
#: so defaulting to the full set would make every out-of-the-box request
#: fail on a fresh checkout. Callers that have the dependencies ask for
#: ["script", "voiceover", "assemble"] explicitly, and /jobs/preflight
#: reports which of those are ready.
DEFAULT_STAGES: tuple[str, ...] = ("script",)


def ordered_stages(requested: Iterable[str]) -> list[Stage]:
    """Return the requested stages in pipeline order, de-duplicated."""
    wanted = set(requested)
    return [s for s in STAGES if s.name in wanted]


# --- Preflight -----------------------------------------------------------------


async def _NOOP_SYNTHESISER(text: str, destination: str) -> str:
    """Placeholder passed to the assembler during preflight only.

    ``VideoAssembler.unavailable_reason`` treats a missing synthesiser as a
    problem, which is right at render time and wrong here: preflight checks
    Piper separately and would otherwise report it twice.
    """
    raise NotImplementedError("preflight does not synthesise audio")



async def preflight(
    stages: Sequence[str],
    pipeline: AIPipeline | None = None,
) -> dict[str, str]:
    """Check each stage's tooling up front.

    Returns ``{stage_name: reason}`` for stages that cannot run. Callers use
    this to reject a request immediately rather than accept a job that is
    guaranteed to fail several seconds later.
    """
    pipeline = pipeline or get_ai_pipeline()
    problems: dict[str, str] = {}

    for stage in ordered_stages(stages):
        if stage.name == "script":
            reason = await pipeline.llm.unavailable_reason()
            if reason:
                problems[stage.name] = reason
        elif stage.name == "voiceover":
            reason = PiperTTS.unavailable_reason()
            if reason:
                problems[stage.name] = reason
        elif stage.name == "assemble":
            # Assembly needs ffmpeg, a voice model and at least one stock
            # provider. Report every missing piece together -- discovering
            # them one failed job at a time is miserable.
            from apps.api.services.assembly import VideoAssembler

            missing = []
            tts_reason = PiperTTS.unavailable_reason()
            if tts_reason:
                missing.append(f"narration is unavailable because {tts_reason}")

            assembler = VideoAssembler(synthesiser=_NOOP_SYNTHESISER)
            reason = assembler.unavailable_reason()
            if reason:
                missing.append(reason)

            if missing:
                problems[stage.name] = " ".join(missing)

    return problems


# --- Creation --------------------------------------------------------------------


def active_job_for_project(db: Session, project_id: int) -> VideoJob | None:
    """The in-flight generation job for a project, if any."""
    return db.scalars(
        select(VideoJob)
        .join(Video, Video.id == VideoJob.video_id)
        .where(
            Video.project_id == project_id,
            VideoJob.job_type == JOB_TYPE_GENERATE,
            VideoJob.status.in_(ACTIVE_JOB_STATUSES),
        )
        .order_by(VideoJob.id.desc())
        .limit(1)
    ).first()


def create_generation_job(
    db: Session,
    project: Project,
    *,
    style: str = "short_form",
    duration: int = 60,
    voice: str = "lessac",
    stages: Sequence[str] = DEFAULT_STAGES,
) -> tuple[Video, VideoJob]:
    """Create the Video and VideoJob rows for a generation run.

    Does not dispatch; the caller commits and then enqueues, so a job is never
    picked up by a runner before its row is visible.
    """
    selected = [s.name for s in ordered_stages(stages)]

    video = Video(
        project_id=project.id,
        user_id=project.user_id,
        status=STATUS_PENDING,
        generation_params_json={
            "topic": project.topic or project.title,
            "style": style,
            "duration": duration,
            "voice": voice,
            "stages": selected,
        },
    )
    db.add(video)
    db.flush()  # assign video.id without committing

    job = VideoJob(
        video_id=video.id,
        job_type=JOB_TYPE_GENERATE,
        status=STATUS_PENDING,
        progress_pct=0,
    )
    db.add(job)
    db.flush()

    return video, job


# --- Transitions -------------------------------------------------------------------


def _utcnow() -> datetime:
    # Stored naive-UTC to match the existing columns.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _claim(db: Session, job_id: int) -> bool:
    """Move pending -> running. False if already claimed or cancelled."""
    result = db.execute(
        update(VideoJob)
        .where(VideoJob.id == job_id, VideoJob.status == STATUS_PENDING)
        .values(status=STATUS_RUNNING, started_at=_utcnow(), progress_pct=0)
    )
    db.commit()
    return result.rowcount == 1


def _is_cancelled(db: Session, job_id: int) -> bool:
    db.expire_all()
    return db.scalar(select(VideoJob.status).where(VideoJob.id == job_id)) == STATUS_CANCELLED


def _set_progress(db: Session, job_id: int, pct: int) -> None:
    db.execute(
        update(VideoJob)
        .where(VideoJob.id == job_id, VideoJob.status == STATUS_RUNNING)
        .values(progress_pct=pct)
    )
    db.commit()


def _finish(
    db: Session,
    job_id: int,
    video_id: int,
    *,
    job_status: str,
    video_status: str,
    error: str | None = None,
    progress: int | None = None,
    from_statuses: Sequence[str] = (STATUS_RUNNING,),
) -> None:
    values: dict[str, Any] = {
        "status": job_status,
        "completed_at": _utcnow(),
        "error_message": error,
    }
    if progress is not None:
        values["progress_pct"] = progress

    # Guarded on the expected status so a cancel that landed first is not
    # clobbered by a stage finishing a moment later.
    db.execute(
        update(VideoJob)
        .where(VideoJob.id == job_id, VideoJob.status.in_(tuple(from_statuses)))
        .values(**values)
    )
    db.execute(
        update(Video)
        .where(Video.id == video_id)
        .values(status=video_status, error_message=error)
    )
    db.commit()


def request_cancel(db: Session, job: VideoJob) -> bool:
    """Ask a job to stop. False if it had already finished.

    A pending job is cancelled outright. A running job is marked cancelled and
    the runner notices at its next stage boundary -- stages shell out to
    external binaries and cannot be preempted mid-call.
    """
    result = db.execute(
        update(VideoJob)
        .where(VideoJob.id == job.id, VideoJob.status.in_(ACTIVE_JOB_STATUSES))
        .values(status=STATUS_CANCELLED, completed_at=_utcnow())
    )
    if result.rowcount == 1:
        db.execute(
            update(Video)
            .where(Video.id == job.video_id)
            .values(status=STATUS_PENDING)
        )
    db.commit()
    return result.rowcount == 1


# --- Execution ---------------------------------------------------------------------


async def run_generation_job(job_id: int, pipeline: AIPipeline | None = None) -> None:
    """Execute one generation job. Owns its own DB session.

    Never raises: a job failure is data, recorded on the row, not an exception
    thrown into whatever happens to be running this coroutine.
    """
    pipeline = pipeline or get_ai_pipeline()
    db = SessionLocal()
    try:
        job = db.get(VideoJob, job_id)
        if job is None:
            logger.warning("generation job %s vanished before it ran", job_id)
            return

        video = db.get(Video, job.video_id)
        if video is None:
            # Still "pending" at this point, so widen the guard.
            _finish(
                db, job_id, job.video_id,
                job_status=STATUS_FAILED, video_status=STATUS_FAILED,
                error="The video row was deleted before generation started.",
                from_statuses=ACTIVE_JOB_STATUSES,
            )
            return

        if not _claim(db, job_id):
            logger.info("generation job %s was cancelled or already claimed", job_id)
            return

        video_id = video.id
        user_id = video.user_id
        params = dict(video.generation_params_json or {})
        stages = ordered_stages(params.get("stages") or DEFAULT_STAGES)

        db.execute(update(Video).where(Video.id == video_id).values(status="generating"))
        db.commit()

        script: dict[str, Any] | None = None

        for stage in stages:
            if _is_cancelled(db, job_id):
                logger.info("generation job %s cancelled before stage %s", job_id, stage.name)
                db.execute(
                    update(Video).where(Video.id == video_id).values(status=STATUS_PENDING)
                )
                db.commit()
                return

            try:
                if stage.name == "script":
                    script = await pipeline.generate_script(
                        topic=params.get("topic") or "",
                        style=params.get("style", "short_form"),
                        duration=int(params.get("duration", 60)),
                    )
                    db.execute(
                        update(Video)
                        .where(Video.id == video_id)
                        .values(script_text=script.get("script"))
                    )
                    db.commit()

                elif stage.name == "voiceover":
                    if script is None:
                        # Resuming without a script stage: use the stored text.
                        stored = db.scalar(select(Video.script_text).where(Video.id == video_id))
                        if not stored:
                            raise PipelineError(
                                "voiceover needs a script, but this video has none"
                            )
                        script = {"script": stored}
                    audio_path = await pipeline.text_to_speech(
                        script["script"], voice=params.get("voice", "lessac")
                    )
                    db.execute(
                        update(Video).where(Video.id == video_id).values(storage_key=audio_path)
                    )
                    db.commit()

                elif stage.name == "assemble":
                    if not script:
                        stored = db.scalar(
                            select(Video.script_text).where(Video.id == video_id)
                        )
                        if not stored:
                            raise PipelineError(
                                "assembly needs a script, but this video has none"
                            )
                        script = {"script": stored}

                    script.setdefault("topic", params.get("topic", ""))
                    script.setdefault("voice", params.get("voice", "lessac"))

                    def _report(stage_name: str, fraction: float) -> None:
                        # Assembly is the long stage; surface sub-progress so
                        # a three-minute render is not a frozen 80%.
                        span = stage.progress_at_end - 80
                        _set_progress(db, job_id, 80 + int(span * fraction))

                    rendered = await pipeline.create_video_from_script(
                        script,
                        watermark=params.get("watermark", True),
                        on_progress=_report,
                    )

                    # The rendered file is the video now, not the voiceover
                    # the previous stage parked in storage_key.
                    existing = db.scalar(
                        select(Video.generation_params_json).where(
                            Video.id == video_id
                        )
                    ) or {}
                    merged = {**existing, "render": rendered}

                    db.execute(
                        update(Video)
                        .where(Video.id == video_id)
                        .values(
                            storage_key=rendered["video_path"],
                            generation_params_json=merged,
                        )
                    )
                    db.commit()

            except StageNotImplemented as exc:
                _finish(
                    db, job_id, video_id,
                    job_status=STATUS_FAILED, video_status=STATUS_FAILED,
                    error=f"Stage '{stage.name}' is not implemented: {exc}",
                )
                return
            except PipelineError as exc:
                _finish(
                    db, job_id, video_id,
                    job_status=STATUS_FAILED, video_status=STATUS_FAILED,
                    error=f"Stage '{stage.name}' failed: {exc}",
                )
                return
            except Exception as exc:  # noqa: BLE001 - must not escape the runner
                logger.exception("generation job %s crashed in stage %s", job_id, stage.name)
                _finish(
                    db, job_id, video_id,
                    job_status=STATUS_FAILED, video_status=STATUS_FAILED,
                    error=f"Stage '{stage.name}' failed: {type(exc).__name__}: {exc}",
                )
                return

            _set_progress(db, job_id, stage.progress_at_end)

        # Quota is charged here, on success only. A failed render must not bill
        # the user, and counting at request time would charge for crashes.
        quota_service.record_video_generated(db, user_id, video_id=video_id)
        _finish(
            db, job_id, video_id,
            job_status=STATUS_COMPLETED, video_status=STATUS_COMPLETED,
            progress=100,
        )
        logger.info("generation job %s completed", job_id)

    finally:
        db.close()


# --- Dispatch -------------------------------------------------------------------------

Runner = Callable[[int], Awaitable[None] | None]

#: Strong references to in-flight tasks. asyncio only holds weak ones, so a
#: task that nothing references can be garbage-collected mid-run.
_tasks: set[asyncio.Task] = set()


async def _default_runner(job_id: int) -> None:
    """Interim executor: run the job in this process, concurrently.

    Phase 4 swaps this for Celery. It is fine for development and obviously
    wrong for production -- the work shares a process with request handling,
    and anything in flight is lost on restart.
    """
    task = asyncio.create_task(
        asyncio.wait_for(run_generation_job(job_id), timeout=settings.JOB_TIMEOUT_SECONDS)
    )
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


_runner: Runner = _default_runner


def set_runner(runner: Runner) -> Runner:
    """Replace the executor. Returns the previous one so tests can restore it."""
    global _runner
    previous = _runner
    _runner = runner
    return previous


async def enqueue(job_id: int) -> None:
    result = _runner(job_id)
    if asyncio.iscoroutine(result) or isinstance(result, asyncio.Future):
        await result


def count_active_jobs(db: Session, user_id: int) -> int:
    """In-flight generation jobs for a user, used for quota reservation."""
    return int(
        db.scalar(
            select(func.count())
            .select_from(VideoJob)
            .join(Video, Video.id == VideoJob.video_id)
            .where(
                Video.user_id == user_id,
                VideoJob.job_type == JOB_TYPE_GENERATE,
                VideoJob.status.in_(ACTIVE_JOB_STATUSES),
            )
        )
        or 0
    )
