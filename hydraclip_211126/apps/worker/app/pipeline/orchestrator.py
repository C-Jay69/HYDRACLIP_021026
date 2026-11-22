"""Video Generation Orchestrator."""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.video import Video, VideoJob, VideoStatus, VideoJobType, VideoJobStatus
from app.pipeline.providers.text_generation import OllamaProvider
from app.pipeline.providers.tts import EdgeTTSProvider, PiperTTSProvider
from app.pipeline.providers.stt import FasterWhisperProvider
from app.pipeline.providers.video_render import FFmpegVideoRenderProvider
from app.pipeline.providers.thumbnail import TemplateThumbnailProvider
from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class VideoGenerationOrchestrator:
    """Orchestrates the full video generation pipeline."""

    def __init__(self):
        self.text_provider = OllamaProvider(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
        )
        self.tts_provider = EdgeTTSProvider()
        self.tts_fallback = PiperTTSProvider(model_path=settings.piper_model_path)
        self.stt_provider = FasterWhisperProvider(model_size=settings.whisper_model_size)
        self.video_provider = FFmpegVideoRenderProvider()
        self.thumbnail_provider = TemplateThumbnailProvider()

    async def generate(self, video_id: str, user_id: str) -> dict:
        """Run the full video generation pipeline."""
        async with AsyncSessionLocal() as db:
            video: Optional[Video] = None
            try:
                # Get video
                result = await db.execute(select(Video).where(Video.id == video_id))
                video = result.scalar_one_or_none()
                if not video:
                    raise ValueError(f"Video {video_id} not found")

                # Update video status
                video.status = VideoStatus.GENERATING
                await self._update_job(db, video_id, VideoJobStatus.RUNNING, 5, "Starting generation...", started=True)
                await db.commit()

                # Step 1: Generate script
                await self._update_job(db, video_id, VideoJobStatus.RUNNING, 10, "Generating script...")
                script = await self.text_provider.generate_script(
                    topic=video.title,
                    prompt="Create an engaging short-form video script with hook, key points, and CTA.",
                )
                video.script_text = script
                await self._update_job(db, video_id, VideoJobStatus.RUNNING, 25, "Script generated")

                # Step 2: Generate voiceover
                await self._update_job(db, video_id, VideoJobStatus.RUNNING, 45, "Generating voiceover...")
                audio_file = await self._generate_voiceover(script, video)
                await self._update_job(db, video_id, VideoJobStatus.RUNNING, 65, "Voiceover complete")

                # Step 3: Generate subtitles
                await self._update_job(db, video_id, VideoJobStatus.RUNNING, 75, "Generating subtitles...")
                subtitles = await self._generate_subtitles(audio_file)
                await self._update_job(db, video_id, VideoJobStatus.RUNNING, 85, "Subtitles complete")

                # Step 4: Render video
                await self._update_job(db, video_id, VideoJobStatus.RUNNING, 90, "Rendering video...")
                output_path = await self._render_video(script, audio_file, subtitles, video)

                # Mark complete
                video.status = VideoStatus.COMPLETED
                video.storage_key = output_path
                video.duration_seconds = 60
                video.resolution = "1080x1920"
                video.format = "mp4"
                await self._update_job(db, video_id, VideoJobStatus.COMPLETED, 100, "Video complete", completed=True)
                await db.commit()

                logger.info(f"Video {video_id} generation complete")
                return {"success": True, "video_id": video_id, "storage_key": output_path}

            except Exception as e:
                logger.exception(f"Video generation failed for {video_id}: {e}")
                await db.rollback()
                try:
                    result = await db.execute(select(Video).where(Video.id == video_id))
                    video = result.scalar_one_or_none()
                    if video is not None:
                        video.status = VideoStatus.FAILED
                        video.error_message = str(e)
                    await self._update_job(
                        db,
                        video_id,
                        VideoJobStatus.FAILED,
                        error_message=str(e),
                    )
                    await db.commit()
                except Exception:
                    logger.exception(f"Could not record failure for video {video_id}")
                    await db.rollback()
                raise

    async def _generate_voiceover(self, script: str, video: Video) -> str:
        """Generate voiceover with fallback."""
        voice = getattr(video, "voice", None) or "en-US-AriaNeural"
        language = getattr(video, "language", None) or "en"
        try:
            return await self.tts_provider.synthesize(
                text=script,
                voice=voice,
                language=language,
                output_path=f"/tmp/{video.id}_voiceover.wav",
            )
        except Exception as e:
            logger.warning(f"Edge TTS failed, trying Piper: {e}")
            return await self.tts_fallback.synthesize(
                text=script,
                voice=voice,
                language=language,
                output_path=f"/tmp/{video.id}_voiceover.wav",
            )

    async def _generate_subtitles(self, audio_file: str) -> str:
        """Generate subtitles from audio."""
        result = await self.stt_provider.transcribe(audio_file)

        # Convert to SRT format
        srt_path = audio_file.replace(".wav", ".srt")
        with open(srt_path, "w") as f:
            for i, segment in enumerate(result.get("segments", []), 1):
                f.write(f"{i}\n")
                f.write(f"{self._format_time(segment['start'])} --> {self._format_time(segment['end'])}\n")
                f.write(f"{segment['text']}\n\n")

        return srt_path

    def _format_time(self, seconds: float) -> str:
        """Format seconds to SRT time format."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    async def _render_video(self, script: str, audio_file: str, subtitles: str, video: Video) -> str:
        """Render the final video."""
        output_path = f"/tmp/{video.id}.mp4"

        if video.format == "short":
            await self.video_provider.render_short_form(
                script=script,
                audio_file=audio_file,
                subtitles=subtitles,
                output_path=output_path,
            )
        else:
            await self.video_provider.render_long_form(
                script=script,
                audio_file=audio_file,
                subtitles=subtitles,
                output_path=output_path,
            )

        return output_path

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
    ):
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
            logger.info(f"[{video_id}] {message}")

        await db.commit()

    async def regenerate_step(self, video_id: str, step: str) -> dict:
        """Regenerate a specific step."""
        # Implementation for step regeneration
        return {"success": True, "video_id": video_id, "step": step}
