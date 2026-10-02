import subprocess
import json
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List
import httpx


class OllamaLLM:
    """Local LLM client using Ollama."""

    def __init__(self, base_url: str = None, model: str = None):
        self.base_url = base_url or "http://localhost:11434"
        self.model = model or "llama3.2"
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=60.0)

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

    async def embed(self, text: str) -> List[float]:
        """Get embeddings from Ollama.
        
        Args:
            text: Text to embed
        
        Returns:
            Embedding vector
        """
        payload = {"model": self.model, "input": text}
        response = await self.client.post("/api/embeddings", json=payload)
        response.raise_for_status()
        result = response.json()
        return result.get("embedding", [])

    async def close(self):
        await self.client.aclose()


class PiperTTS:
    """Local TTS using Piper."""

    def __init__(self, model_path: str = None):
        self.model_path = model_path or "/models/piper/en_US-lessac-medium.onnx"
        self.model = Path(self.model_path)

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

        cmd = [
            "piper",
            "--model", str(self.model),
            "--output_file", output_path or "/tmp/tts_output.wav",
        ]

        process = subprocess.run(
            cmd,
            input=text,
            capture_output=True,
            text=True,
        )

        if process.returncode != 0:
            raise RuntimeError(f"Piper TTS failed: {process.stderr}")

        return output_path or "/tmp/tts_output.wav"

    async def synthesize_async(self, text: str, output_path: str = None) -> str:
        """Async version of Piper TTS."""
        return await asyncio.get_event_loop().run_in_executor(
            None, self.synthesize, text, output_path
        )


class WhisperSTT:
    """Local STT using faster-whisper."""

    def __init__(self, model_size: str = "base"):
        self.model_size = model_size
        self.model = None
        self._load_model()

    def _load_model(self):
        """Load the faster-whisper model."""
        try:
            from faster_whisper import WhisperModel
            self.model = WhisperModel(self.model_size, compute_type="auto")
        except ImportError:
            # Fallback: use subprocess with whisper command
            pass

    def transcribe(self, audio_path: str) -> Dict[str, Any]:
        """Transcribe audio using Whisper.
        
        Args:
            audio_path: Path to the audio file
        
        Returns:
            Dict with transcription text, segments, language
        """
        if self.model is None:
            # Try loading on demand
            try:
                from faster_whisper import WhisperModel
                self.model = WhisperModel(self.model_size, compute_type="auto")
            except ImportError:
                # Fallback to command-line whisper
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
            "ffmpeg", "-i", input_path,
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
        if watermark_text:
            cmd = [
                "ffmpeg", "-i", input_path,
                "-vf", f"drawtext=text='{watermark_text}':"
                       "fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
                       "fontsize=24:fontcolor=white@0.8:x=(w-text_w-10):y=(h-text_h-10)",
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "23",
                "-c:a", "copy",
                "-y", output_path,
            ]
            subprocess.run(cmd, capture_output=True, check=True)
        
        if logo_path:
            cmd = [
                "ffmpeg", "-i", input_path,
                "-i", logo_path,
                "-filter_complex", "[1:v][0:v]overlay=main_w-overlay_w-10:main_h-overlay_h-10",
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "23",
                "-c:a", "copy",
                "-y", output_path,
            ]
            subprocess.run(cmd, capture_output=True, check=True)
        
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
            "ffmpeg", "-i", video_path,
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
        # Create file list for ffmpeg concat
        file_list_path = "/tmp/ffmpeg_concat_list.txt"
        with open(file_list_path, "w") as f:
            for path in input_paths:
                f.write(f"file '{path}'\n")

        cmd = [
            "ffmpeg", "-f", "concat", "-safe", "0",
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
            "ffmpeg", "-i", input_path,
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
                 llm_model: str = "llama3.2",
                 tts_model_path: str = None,
                 stt_model_size: str = "base"):
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
            "generated_at": subprocess.list2cmdline.__self__ if hasattr else "unknown",
        }

    async def text_to_speech(self, text: str, voice: str = "lessac") -> str:
        """Convert text to speech using Piper.
        
        Args:
            text: Text to convert
            voice: Voice model name
        
        Returns:
            Path to generated WAV audio file
        """
        # Update the Piper model path based on voice
        model_map = {
            "lessac": "/models/piper/en_US-lessac-medium.onnx",
            "ruffalo": "/models/piper/en_US-ruffalo-medium.onnx",
            "isley": "/models/piper/en_US-isley-medium.onnx",
        }
        
        model_path = model_map.get(voice, self.tts.model_path)
        
        # Reinitialize with correct model
        from ..app.core.config import settings
        tts = PiperTTS(model_path=model_path)
        audio_path = tts.synthesize(text)
        return audio_path

    async def speech_to_text(self, audio_path: str) -> Dict[str, Any]:
        """Convert speech to text using Whisper.
        
        Args:
            audio_path: Path to audio file
        
        Returns:
            Dict with transcription and metadata
        """
        result = await self.stt.transcribe_async(audio_path)
        return result

    async def create_video_from_script(self, script: Dict[str, Any], 
                                       stock_media: List[Dict] = None,
                                       watermark: bool = True) -> Dict[str, Any]:
        """Create a complete video from a generated script.
        
        This is a high-level orchestration that:
        1. Generates TTS audio from the script
        2. Searches Shutterstock for relevant stock media
        3. Combines audio + video using FFmpeg
        4. Adds watermark if needed
        
        Args:
            script: Script dict from generate_script()
            stock_media: Pre-selected Shutterstock media items
            watermark: Whether to add branding watermark
        
        Returns:
            Dict with video generation metadata and storage path
        """
        # Step 1: Generate TTS audio
        audio_path = await self.text_to_speech(script["script"])
        
        # Step 2: Search for stock media if not provided
        video_urls = []
        if stock_media:
            video_urls = [m.get("preview_url") or m.get("url") for m in stock_media[:5]]
        
        # Step 3: Create video using FFmpeg
        # For now, we'll create a basic structure
        # In a full implementation, this would use the stock media URLs 
        # with a video editing library
        
        output_path = f"/tmp/video_{script['topic'].replace(' ', '_')}.mp4"
        
        # This is a simplified example - real implementation would:
        # - Download stock media videos/images
        # - Combine with audio
        # - Add transitions, titles, etc.
        
        # For now, just return the audio and metadata
        return {
            "audio_path": audio_path,
            "video_urls": video_urls,
            "script": script["script"],
            "topic": script["topic"],
            "output_path": output_path,
            "status": "generated",
            "watermark": watermark,
        }

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