"""Video Generation Tasks."""

import asyncio
import logging
from celery import shared_task
from app.core.database import async_engine
from app.pipeline.orchestrator import VideoGenerationOrchestrator

logger = logging.getLogger(__name__)


def _run(coro):
    """Run a coroutine in a fresh loop and release loop-bound DB resources."""

    async def runner():
        try:
            return await coro
        finally:
            await async_engine.dispose()

    return asyncio.run(runner())


@shared_task(bind=True, name="tasks.video_generation.generate_video")
def generate_video(self, video_id: str, user_id: str):
    """Generate a video from a topic."""
    try:
        orchestrator = VideoGenerationOrchestrator()
        result = _run(orchestrator.generate(video_id, user_id))
        return result
    except Exception as e:
        logger.error(f"Video generation failed: {e}")
        raise self.retry(exc=e, countdown=60, max_retries=3)


@shared_task(bind=True, name="tasks.video_generation.regenerate_step")
def regenerate_step(self, video_id: str, step: str):
    """Regenerate a specific step of video generation."""
    try:
        orchestrator = VideoGenerationOrchestrator()
        result = _run(orchestrator.regenerate_step(video_id, step))
        return result
    except Exception as e:
        logger.error(f"Step regeneration failed: {e}")
        raise self.retry(exc=e, countdown=60, max_retries=3)