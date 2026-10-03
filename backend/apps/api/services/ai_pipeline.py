"""Local-first AI pipeline: Ollama (LLM), Piper (TTS), Whisper (STT), FFmpeg.

Nothing in this module was reachable before: no caller existed anywhere in the
codebase, and ``generate_script`` raised ``AttributeError`` on its own return
statement, so the pipeline had never run even once. See ANALYSIS.md §6.
"""

import asyncio
import json
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from apps.api.core.config import settings

# Scratch space for intermediate artefacts. Each run gets a unique filename:
# the previous fixed paths meant two concurrent jobs overwrote each other.
WORK_DIR = Path(settings.MEDIA_WORK_DIR)


class PipelineError(RuntimeError):
    """Base class for pipeline failures that are expected and reportable."""


class StageUnavailable(PipelineError):
    """A stage cannot run because its external tooling is missing."""


class StageNotImplemented(PipelineError):
    """A stage is declared but has no implementation yet."""


def _work_path(suffix: str, prefix: str = "hc") -> str:
    """A collision-free path inside the work directory."""
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    return str(WORK_DIR / f"{prefix}_{uuid.uuid4().hex}{suffix}")


class OllamaLLM:
    """Local LLM client using Ollama."""

    def __init__(self, base_url: str = None, model: str = None):
        # Previously hardcoded, so OLLAMA_BASE_URL / OLLAMA_MODEL were ignored
        # and a deployment pointed at a real Ollama host still called localhost.
        self.base_url = base_url or settings.OLLAMA_BASE_URL
        self.model = model or settings.OLLAMA_MODEL
        self.timeout = settings.OLLAMA_TIMEOUT_SECONDS
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Created on first use.

        Building an AsyncClient in __init__ binds it to whichever event loop
        happens to be current at construction time; this class is held in a
        module-level singleton, so that loop is usually the wrong one.
        """
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout)
        return self._client

    async def generate(self, prompt: str, system: str = None, 
                       max_tokens: int = 500, temperature: float = 0.7) -> str:
        """Generate text using Ollama LLM.
        
        Args:
            prompt: The user prompt
            system: System/instruction prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
        
        Returns:
            Generated text response
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
        }

        response = await self.client.post("/api/chat", json=payload)
        response.raise_for_status()
        result = response.json()
        
        if "message" in result and "content" in result["message"]:
            return result["message"]["content"]
        elif "response" in result:
            return result["response"]
        else:
            return str(result)

    async def unavailable_reason(self) -> Optional[str]:
        """Why generation would fail right now, or None if Ollama looks ready.

        Checked before a job is accepted so callers get an immediate, specific
        error instead of a queued job that is certain to fail.
        """
        try:
            response = await self.client.get("/api/tags", timeout=5.0)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return f"Ollama is unreachable at {self.base_url} ({type(exc).__name__})"

        try:
            installed = {m["name"] for m in response.json().get("models", [])}
        except (ValueError, KeyError, TypeError):
            return None  # Reachable but an unexpected body; let the job try.

        # Ollama reports tags as "llama3.2:latest"; accept a bare-name match.
        if installed and not any(
            name == self.model or name.split(":")[0] == self.model.split(":")[0]
            for name in installed
        ):
            return (
                f"the model '{self.model}' is not pulled on {self.base_url} "
                f"(available: {', '.join(sorted(installed)) or 'none'})"
            )
        return None

    async def embed(self, text: str) -> List[float]:
        """Get embeddings from Ollama.
        
        Args:
            text: Text to embed
        
        Returns:
            Embedding vector
        """
        # /api/embeddings takes "prompt"; "input" belongs to the newer /api/embed.
        payload = {"model": self.model, "prompt": text}
        response = await self.client.post("/api/embeddings", json=payload)
        response.raise_for_status()
        result = response.json()
        return result.get("embedding", [])

    async def close(self):
        if self._client is not None:
            await self._client.aclose()
            self._client = None


class PiperTTS:
    """Local TTS using Piper."""

    #: Voice name -> model filename, resolved under settings.PIPER_MODEL_PATH.
    VOICES = {
        "lessac": "en_US-lessac-medium.onnx",
        "ruffalo": "en_US-ruffalo-medium.onnx",
        "isley": "en_US-isley-medium.onnx",
    }

    def __init__(self, model_path: str = None, voice: str = "lessac"):
        if model_path is None:
            filename = self.VOICES.get(voice, self.VOICES["lessac"])
            model_path = str(Path(settings.PIPER_MODEL_PATH) / filename)
        self.model_path = model_path
        self.model = Path(self.model_path)

    @classmethod
    def unavailable_reason(cls, voice: str = "lessac") -> Optional[str]:
        """Why synthesis would fail right now, or None if it would work."""
        if shutil.which("piper") is None:
            return "the 'piper' binary is not on PATH"
        model = Path(settings.PIPER_MODEL_PATH) / cls.VOICES.get(voice, cls.VOICES["lessac"])
        if not model.exists():
            return f"the Piper voice model is missing at {model}"
        return None

    def synthesize(self, text: str, output_path: str = None) -> str:
        """Synthesize speech from text using Piper.
        
        Args:
            text: Text to synthesize
            output_path: Path to save the WAV file (if None, returns base64)
        
        Returns:
            Path to the generated audio file
        """
        if not self.model.exists():
            raise FileNotFoundError(f"Piper model not found at {self.model_path}")

        # Was a fixed /tmp/tts_output.wav, so concurrent jobs clobbered one another.
        output_path = output_path or _work_path(".wav", prefix="tts")

        cmd = [
            "piper",
            "--model", str(self.model),
            "--output_file", output_path,
        ]

        process = subprocess.run(
            cmd,
            input=text,
            capture_output=True,
            text=True,
            timeout=settings.TTS_TIMEOUT_SECONDS,
        )

        if process.returncode != 0:
            raise RuntimeError(f"Piper TTS failed: {process.stderr.strip()}")

        return output_path

    async def synthesize_async(self, text: str, output_path: str = None) -> str:
        """Async version of Piper TTS."""
        return await asyncio.get_event_loop().run_in_executor(
            None, self.synthesize, text, output_path
        )


class WhisperSTT:
    """Local STT using faster-whisper."""

    def __init__(self, model_size: str = None):
        self.model_size = model_size or settings.WHISPER_MODEL_SIZE
        # Loaded on first transcription, not here: _load_model() in __init__
        # pulled a multi-hundred-MB model into memory just to build the object,
        # on whatever thread happened to construct the pipeline singleton.
        self.model = None

    def _load_model(self):
        """Load the faster-whisper model, if the package is installed."""
        if self.model is not None:
            return
        try:
            from faster_whisper import WhisperModel
            self.model = WhisperModel(self.model_size, compute_type="auto")
        except ImportError:
            # Caller falls back to the whisper CLI.
            pass

    def transcribe(self, audio_path: str) -> Dict[str, Any]:
        """Transcribe audio using Whisper.
        
        Args:
            audio_path: Path to the audio file
        
        Returns:
            Dict with transcription text, segments, language
        """
        self._load_model()
        if self.model is None:
            return self._transcribe_cli(audio_path)

        segments, info = self.model.transcribe(audio_path)
        
        text = " ".join(segment.text for segment in segments)

        return {
            "text": text,
            "language": info.language,
            "duration": info.duration,
            "segments": [segment.text for segment in segments],
        }

    def _transcribe_cli(self, audio_path: str) -> Dict[str, Any]:
        """Fallback transcription using whisper CLI."""
        result = subprocess.run(
            ["whisper", audio_path, "--model", self.model_size, "--json"],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Whisper CLI failed: {result.stderr}")

        data = json.loads(result.stdout)
        text = data["text"]

        return {
            "text": text,
            "language": data.get("language", "unknown"),
            "duration": data.get("duration", 0),
            "segments": data.get("segments", []),
        }

    async def transcribe_async(self, audio_path: str) -> Dict[str, Any]:
        """Async version of Whisper STT."""
        return await asyncio.get_event_loop().run_in_executor(
            None, self.transcribe, audio_path
        )


def _ffmpeg() -> str:
    """The ffmpeg binary to run.

    These helpers used to invoke the bare name "ffmpeg", so they only worked
    when a system package happened to be installed and silently ignored
    FFMPEG_BINARY. Resolution now goes through services.media, which also
    picks up the imageio-ffmpeg wheel on checkouts without a system build.
    """
    from apps.api.services.media import ffmpeg_path

    return ffmpeg_path()


class FFmpegProcessor:
    """Local video/audio processing using FFmpeg."""

    @staticmethod
    def resize_video(input_path: str, output_path: str, 
                     width: int = 1080, height: int = 1920) -> str:
        """Resize video for vertical format (9:16).
        
        Args:
            input_path: Input video path
            output_path: Output video path
            width: Target width
            height: Target height
        
        Returns:
            Output video path
        """
        cmd = [
            _ffmpeg(), "-i", input_path,
            "-vf", f"scale={width}:{height}:force_original_aspect_ratio=increase,"
                   f"crop={width}:{height}",
            "-c:v", "libx264",
            "-preset", "fast",
 "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
            "-y", output_path,
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

    @staticmethod
    def add_watermark(input_path: str, output_path: str, 
                      watermark_text: str = None,
                      logo_path: str = None) -> str:
        """Add watermark to video.
        
        Args:
            input_path: Input video path
            output_path: Output video path
            watermark_text: Text watermark
            logo_path: Logo image path
        
        Returns:
            Output video path
        """
        from apps.api.services import subtitles as subs

        # Each step reads whatever the previous one produced. Previously
        # both branches read `input_path` and wrote `output_path`, so asking
        # for text *and* a logo silently discarded the text.
        current = input_path

        if watermark_text:
            # Rendered with libass rather than drawtext: drawtext is an
            # optional ffmpeg build flag and is absent from the static
            # build used when no system ffmpeg is installed, where this
            # step failed with "No such filter: 'drawtext'". libass is
            # already required for burned-in captions.
            overlay = _work_path(".ass", prefix="mark")
            Path(overlay).write_text(
                subs.watermark_ass(
                    watermark_text,
                    width=settings.VIDEO_WIDTH,
                    height=settings.VIDEO_HEIGHT,
                ),
                encoding="utf-8",
            )
            stage_out = output_path if not logo_path else _work_path(".mp4", prefix="mark")
            cmd = [
                _ffmpeg(), "-i", current,
                "-vf", f"ass='{subs.escape_for_filter(overlay)}'",
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "23",
                "-c:a", "copy",
                "-y", stage_out,
            ]
            subprocess.run(cmd, capture_output=True, check=True)
            current = stage_out

        if logo_path:
            cmd = [
                _ffmpeg(), "-i", current,
                "-i", logo_path,
                "-filter_complex", "[1:v][0:v]overlay=main_w-overlay_w-10:main_h-overlay_h-10",
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "23",
                "-c:a", "copy",
                "-y", output_path,
            ]
            subprocess.run(cmd, capture_output=True, check=True)
            current = output_path

        if current != output_path:
            # Nothing was asked for; still honour the output contract.
            shutil.copyfile(current, output_path)

        return output_path

    @staticmethod
    def extract_audio(video_path: str, output_path: str = None) -> str:
        """Extract audio from video.
        
        Args:
            video_path: Input video path
            output_path: Output audio path (defaults to same dir with .wav)
        
        Returns:
            Output audio path
        """
        if output_path is None:
            output_path = video_path.replace(".mp4", ".wav")
        
        cmd = [
            _ffmpeg(), "-i", video_path,
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", 1,
            "-y", output_path,
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

    @staticmethod
    def concatenate_videos(input_paths: List[str], output_path: str) -> str:
        """Concatenate multiple videos into one.
        
        Args:
            input_paths: List of input video paths
            output_path: Output video path
        
        Returns:
            Output video path
        """
        # Was a fixed /tmp/ffmpeg_concat_list.txt, so two renders running at
        # the same time overwrote each other's list and spliced the wrong
        # clips together. Same class of bug as the fixed TTS output path.
        file_list_path = _work_path(".txt", prefix="concat")
        with open(file_list_path, "w") as f:
            for path in input_paths:
                f.write(f"file '{Path(path).resolve()}'\n")

        cmd = [
            _ffmpeg(), "-f", "concat", "-safe", "0",
            "-i", file_list_path,
            "-c", "copy",
            "-y", output_path,
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

    @staticmethod
    def adjust_volume(input_path: str, output_path: str, 
                      volume_multiplier: float = 1.0) -> str:
        """Adjust audio volume.
        
        Args:
            input_path: Input audio/video path
            output_path: Output path
            volume_multiplier: Volume multiplier (0.5 = half volume, 2.0 = double)
        
        Returns:
            Output path
        """
        cmd = [
            _ffmpeg(), "-i", input_path,
            "-filter_complex", f"[0:a]volume={volume_multiplier}[a]",
            "-map", "0:v",
            "-map", "[a]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-y", output_path,
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path


class AIPipeline:
    """Composite AI pipeline combining LLM, TTS, STT, and FFmpeg."""

    def __init__(self,
                 llm_model: str = None,
                 tts_model_path: str = None,
                 stt_model_size: str = None):
        self.llm = OllamaLLM(model=llm_model)
        self.tts = PiperTTS(model_path=tts_model_path)
        self.stt = WhisperSTT(model_size=stt_model_size)
        self.ffmpeg = FFmpegProcessor()

    async def generate_script(self, topic: str, style: str = "short_form",
                             duration: int = 60) -> Dict[str, Any]:
        """Generate a video script using Ollama.
        
        Args:
            topic: Video topic
            style: Script style (short_form, long_form, intro, outro)
            duration: Target duration in seconds
        
        Returns:
            Dict with script text and generation metadata
        """
        style_prompts = {
            "short_form": f"""
            Generate a captivating short-form video script about {topic}.
            Include an engaging hook, 3 key points, and a call-to-action.
            Keep it under {duration} seconds when spoken.
            Format: [HOOK] [POINT1] [POINT2] [POINT3] [CTA]
            """,
            "long_form": f"""
            Generate an introductory section for a long-form video about {topic}.
            Set up the problem, present the solution, and outline what viewers will learn.
            Keep it under {duration} seconds when spoken.
            Format: [PROBLEM] [SOLUTION] [OUTCOME]
            """,
            "intro": f"""
            Generate a video intro about {topic}.
            Hook the viewer, establish credibility, and preview what's ahead.
            Keep it under {duration} seconds when spoken.
            """
        }

        prompt = style_prompts.get(style, style_prompts["short_form"])

        system = "You are a video script writer. Generate engaging, conversational scripts optimized for short-form video platforms."

        script_text = await self.llm.generate(prompt, system=system, 
                                              max_tokens=800, temperature=0.8)

        return {
            "script": script_text,
            "topic": topic,
            "style": style,
            "duration": duration,
            # Was: `subprocess.list2cmdline.__self__ if hasattr else "unknown"`,
            # which raised AttributeError on every call -- list2cmdline is a
            # plain function with no __self__, and the bare `hasattr` builtin is
            # always truthy so the "unknown" branch was unreachable. This single
            # expression meant the pipeline could never return successfully.
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "model": self.llm.model,
        }

    async def text_to_speech(self, text: str, voice: str = "lessac") -> str:
        """Convert text to speech using Piper.
        
        Args:
            text: Text to convert
            voice: Voice model name
        
        Returns:
            Path to generated WAV audio file
        """
        # Voice -> model resolution lives on PiperTTS so it honours
        # PIPER_MODEL_PATH instead of hardcoding /models/piper.
        tts = PiperTTS(voice=voice)
        # Synthesis shells out to a binary; keep it off the event loop.
        return await tts.synthesize_async(text)

    async def speech_to_text(self, audio_path: str) -> Dict[str, Any]:
        """Convert speech to text using Whisper.
        
        Args:
            audio_path: Path to audio file
        
        Returns:
            Dict with transcription and metadata
        """
        result = await self.stt.transcribe_async(audio_path)
        return result

    async def create_video_from_script(
        self,
        script: Dict[str, Any],
        stock_media: List[Dict] = None,
        watermark: bool = True,
        output_path: str = None,
        on_progress: Any = None,
    ) -> Dict[str, Any]:
        """Render a finished MP4 from a generated script.

        No frames are generated. The video is assembled from stock footage
        sourced scene by scene, narrated with Piper, and captioned from the
        narration text. See services/assembly.py for the stage breakdown.

        Args:
            script: Script dict from generate_script()
            stock_media: Ignored. Footage is sourced per scene now, because
                one flat list cannot be matched to individual scenes.
            watermark: Whether to burn the branding watermark on afterwards.
            output_path: Where to write the MP4. Defaults to the work dir.
            on_progress: Optional (stage, fraction) callback.

        Returns:
            Dict describing the rendered file.
        """
        from apps.api.services.assembly import (
            AssemblyError,
            AssemblyUnavailable,
            VideoAssembler,
        )

        text = script.get("script") or ""
        if not text.strip():
            raise PipelineError("The script is empty, so there is nothing to render.")

        voice = script.get("voice") or "lessac"

        # The assembler narrates scene by scene so it can measure each
        # segment, so hand it a synthesiser bound to the chosen voice
        # rather than the whole-script text_to_speech().
        tts = PiperTTS(voice=voice)

        async def synthesise(segment: str, destination: str) -> str:
            return await tts.synthesize_async(segment, destination)

        assembler = VideoAssembler(synthesiser=synthesise)

        # Check Piper here too: the assembler can only see that *a*
        # synthesiser was supplied, not that its voice model exists.
        tts_problem = PiperTTS.unavailable_reason(voice)
        if tts_problem:
            raise StageUnavailable(f"Narration is unavailable because {tts_problem}.")

        problem = assembler.unavailable_reason()
        if problem:
            raise StageUnavailable(problem)

        if output_path is None:
            # Never built from the topic: a topic of "../../etc/x" used to
            # escape the work directory entirely.
            output_path = _work_path(".mp4", prefix="video")

        try:
            result = await assembler.render(
                text,
                topic=script.get("topic", ""),
                output_path=output_path,
                on_progress=on_progress,
            )
        except AssemblyUnavailable as exc:
            # A missing dependency is not a bad request; surface it as an
            # unavailable stage so the job layer can say so plainly.
            raise StageUnavailable(str(exc)) from exc
        except AssemblyError as exc:
            raise PipelineError(str(exc)) from exc

        final_path = str(result.video_path)

        watermark_applied = False
        if watermark:
            stamped = _work_path(".mp4", prefix="wm")
            try:
                FFmpegProcessor.add_watermark(
                    final_path, stamped, watermark_text="HydraClip"
                )
                final_path = stamped
                watermark_applied = True
            except Exception as exc:  # noqa: BLE001
                # A missing watermark is cosmetic; losing the whole render
                # over it would not be. It must not be *reported* as applied
                # though -- that is the same dishonesty this stage used to
                # have when it claimed to render videos it never wrote.
                result.warnings.append(f"Watermarking failed: {exc}")

        payload = {
            "status": "rendered",
            "video_path": final_path,
            "subtitle_path": (
                str(result.subtitle_path) if result.subtitle_path else None
            ),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "watermarked": watermark_applied,
            **result.summary(),
        }
        return payload

    async def close(self):
        """Close all underlying connections."""
        await self.llm.close()


# Create singleton pipeline instance
_pipeline_instance = None


def get_ai_pipeline() -> AIPipeline:
    """Get or create the AI pipeline instance."""
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = AIPipeline()
    return _pipeline_instance