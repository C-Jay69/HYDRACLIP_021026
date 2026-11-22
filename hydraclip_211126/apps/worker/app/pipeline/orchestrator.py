"""Video Generation Orchestrator.

Pipeline:
1. OpenRouter (or deterministic fallback) produces a structured video plan.
2. Edge TTS / Piper (or silence) produces the voiceover audio.
3. The Remotion render service renders the composition to an MP4.
4. The MP4 is uploaded to S3-compatible storage (SeaweedFS/MinIO).
"""

import asyncio
import base64
import io
import logging
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from typing import Optional

from minio import Minio
from sqlalchemy import select

from app.config import get_settings
from app.core.database import AsyncSessionLocal
from app.models.video import Video, VideoJob, VideoJobStatus, VideoJobType, VideoStatus
from app.pipeline.providers.openrouter import OpenRouterProvider, VideoPlan
from app.pipeline.providers.tts import EdgeTTSProvider, PiperTTSProvider
from app.pipeline.providers.unsplash import UnsplashProvider
from app.pipeline.render_client import RenderClient

settings = get_settings()
logger = logging.getLogger(__name__)


class VideoGenerationOrchestrator:
    """Orchestrates the full video generation pipeline."""

    def __init__(self):
        self.planner = OpenRouterProvider()
        self.unsplash = UnsplashProvider()
        self.tts_provider = EdgeTTSProvider()
        self.tts_fallback = PiperTTSProvider(model_path=settings.piper_model_path)
        self.renderer = RenderClient()
        self.storage = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=False,
            region="us-east-1",
        )

    async def generate(self, video_id: str, user_id: str) -> dict:
        """Run the full video generation pipeline."""
        async with AsyncSessionLocal() as db:
            video: Optional[Video] = None
            workdir = tempfile.mkdtemp(prefix=f"hydraclip-{video_id}-")
            try:
                result = await db.execute(select(Video).where(Video.id == video_id))
                video = result.scalar_one_or_none()
                if not video:
                    raise ValueError(f"Video {video_id} not found")

                video.status = VideoStatus.GENERATING
                await self._update_job(
                    db,
                    video_id,
                    VideoJobStatus.RUNNING,
                    5,
                    "Planning video...",
                    started=True,
                )
                await db.commit()

                # 1. Plan the video (OpenRouter, with deterministic fallback)
                plan = await self.planner.generate_plan(
                    topic=video.title,
                    title=video.title,
                    description=video.description,
                    duration_seconds=30,
                )
                video.script_text = plan.narration
                await self._update_job(
                    db, video_id, VideoJobStatus.RUNNING, 25, "Script ready"
                )

                # 2. Find visuals and generate the voiceover in parallel.
                description = (
                    (video.description or "").replace("Video about ", "").strip()
                )
                image_query = f"{video.title} {description}".strip()
                image_count = max(3, min(len(plan.scenes), 6))
                photos, audio_path = await asyncio.gather(
                    self.unsplash.search_images(image_query, count=image_count),
                    self._make_audio(plan, workdir),
                )
                if not photos:
                    logger.warning(
                        "No Unsplash photos found; using the gradient background"
                    )

                duration = self._audio_duration(audio_path) or self._estimate_duration(
                    plan.narration
                )
                duration = max(5.0, min(180.0, duration))
                await self._update_job(
                    db,
                    video_id,
                    VideoJobStatus.RUNNING,
                    45,
                    f"Visuals ready ({len(photos)} photos), voiceover {duration:.1f}s",
                )

                # 3. Render with Remotion
                input_props = plan.to_input_props(
                    audio_src=self._to_data_uri(audio_path),
                    duration_seconds=duration,
                    images=photos,
                )
                await self._update_job(
                    db, video_id, VideoJobStatus.RUNNING, 55, "Rendering video..."
                )
                video_bytes = await self.renderer.render(input_props)

                # 4. Upload to object storage
                await self._update_job(
                    db, video_id, VideoJobStatus.RUNNING, 90, "Uploading video..."
                )
                storage_key = f"videos/{video_id}.mp4"
                self._upload(storage_key, video_bytes)

                video.status = VideoStatus.COMPLETED
                video.storage_key = storage_key
                video.duration_seconds = int(round(duration))
                video.resolution = "1080x1920"
                video.format = "mp4"
                video.error_message = None
                await self._update_job(
                    db,
                    video_id,
                    VideoJobStatus.COMPLETED,
                    100,
                    "Video complete",
                    completed=True,
                )
                await db.commit()

                logger.info(
                    "Video %s generated (%s bytes, %.1fs)", video_id, len(video_bytes), duration
                )
                return {
                    "success": True,
                    "video_id": video_id,
                    "storage_key": storage_key,
                    "duration_seconds": round(duration, 2),
                }

            except Exception as exc:
                logger.exception("Video generation failed for %s: %s", video_id, exc)
                await db.rollback()
                try:
                    result = await db.execute(select(Video).where(Video.id == video_id))
                    video = result.scalar_one_or_none()
                    if video is not None:
                        video.status = VideoStatus.FAILED
                        video.error_message = str(exc)
                    await self._update_job(
                        db,
                        video_id,
                        VideoJobStatus.FAILED,
                        error_message=str(exc),
                    )
                    await db.commit()
                except Exception:
                    logger.exception("Could not record failure for video %s", video_id)
                    await db.rollback()
                raise
            finally:
                shutil.rmtree(workdir, ignore_errors=True)

    async def _make_audio(self, plan: VideoPlan, workdir: str) -> str:
        """Generate voiceover audio with fallbacks, returning a usable file path."""
        mp3_path = os.path.join(workdir, "voiceover.mp3")
        try:
            path = await self.tts_provider.synthesize(
                text=plan.narration,
                voice="en-US-AriaNeural",
                language="en",
                output_path=mp3_path,
            )
            if self._is_nonempty(path):
                return path
        except Exception as exc:
            logger.warning("Edge TTS failed: %s", exc)

        wav_path = os.path.join(workdir, "voiceover.wav")
        try:
            path = await self.tts_fallback.synthesize(
                text=plan.narration,
                voice="en_US-lessac-medium",
                language="en",
                output_path=wav_path,
            )
            if self._is_nonempty(path):
                return path
        except Exception as exc:
            logger.warning("Piper TTS failed: %s", exc)

        # Last resort: silent audio so the render still succeeds.
        duration = self._estimate_duration(plan.narration)
        logger.warning("Falling back to %.1fs of silence for the voiceover", duration)
        return self._silent_audio(duration, mp3_path)

    @staticmethod
    def _is_nonempty(path: Optional[str]) -> bool:
        return bool(path) and os.path.exists(path) and os.path.getsize(path) > 1024

    @staticmethod
    def _estimate_duration(text: str) -> float:
        words = max(1, len(text.split()))
        return max(8.0, min(90.0, words / 2.5 + 2.0))

    @staticmethod
    def _audio_duration(path: str) -> Optional[float]:
        """Return audio duration in seconds using ffprobe."""
        try:
            process = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    path,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if process.returncode == 0:
                return float(process.stdout.strip())
        except Exception as exc:
            logger.warning("ffprobe failed: %s", exc)
        return None

    @staticmethod
    def _silent_audio(duration: float, output_path: str) -> str:
        process = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "anullsrc=r=44100:cl=mono",
                "-t",
                f"{duration:.2f}",
                "-q:a",
                "9",
                "-acodec",
                "libmp3lame",
                output_path,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if process.returncode != 0:
            raise RuntimeError(f"ffmpeg silence generation failed: {process.stderr[-500:]}")
        return output_path

    @staticmethod
    def _to_data_uri(path: str) -> str:
        extension = os.path.splitext(path)[1].lower()
        mime = "audio/wav" if extension == ".wav" else "audio/mpeg"
        with open(path, "rb") as handle:
            encoded = base64.b64encode(handle.read()).decode("ascii")
        return f"data:{mime};base64,{encoded}"

    def _upload(self, storage_key: str, data: bytes) -> None:
        bucket = settings.minio_bucket
        if not self.storage.bucket_exists(bucket):
            self.storage.make_bucket(bucket)
        self.storage.put_object(
            bucket,
            storage_key,
            io.BytesIO(data),
            len(data),
            content_type="video/mp4",
        )

    async def _update_job(
        self,
        db,
        video_id: str,
        status: VideoJobStatus,
        progress: Optional[int] = None,
        message: Optional[str] = None,
        started: bool = False,
        completed: bool = False,
        error_message: Optional[str] = None,
    ) -> None:
        """Update the full-pipeline job belonging to a video."""
        result = await db.execute(
            select(VideoJob)
            .where(VideoJob.video_id == video_id)
            .order_by(VideoJob.created_at)
            .limit(1)
        )
        job = result.scalar_one_or_none()

        if job is None:
            job = VideoJob(
                id=f"{video_id}_job",
                video_id=video_id,
                job_type=VideoJobType.FULL_PIPELINE,
                status=status,
                progress_pct=progress or 0,
            )
            db.add(job)

        job.status = status
        if progress is not None:
            job.progress_pct = progress
        if started and job.started_at is None:
            job.started_at = datetime.now(timezone.utc)
        if completed:
            job.completed_at = datetime.now(timezone.utc)
        if error_message is not None:
            job.error_message = error_message
        if message:
            logger.info("[%s] %s", video_id, message)

        await db.commit()

    async def regenerate_step(self, video_id: str, step: str) -> dict:
        """Regenerate a specific step."""
        return {"success": True, "video_id": video_id, "step": step}
