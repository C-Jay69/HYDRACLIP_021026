"""STT Provider: faster-whisper."""

import logging
from typing import Optional

from app.pipeline.providers.base import BaseSTTProvider

logger = logging.getLogger(__name__)


class FasterWhisperProvider(BaseSTTProvider):
    """faster-whisper STT provider."""
    
    def __init__(self, model_size: str = "tiny"):
        self.model_size = model_size
        self._model = None
    
    def _get_model(self):
        """Lazy load model."""
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
                self._model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
            except ImportError:
                logger.error("faster-whisper not installed")
                raise
        return self._model
    
    async def transcribe(self, audio_file: str, **kwargs) -> dict:
        """Transcribe audio to text with timestamps."""
        try:
            model = self._get_model()
            
            segments, info = model.transcribe(
                audio_file,
                beam_size=5,
                word_timestamps=True,
            )
            
            transcript = []
            for segment in segments:
                transcript.append({
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text,
                    "words": [
                        {"word": w.word, "start": w.start, "end": w.end}
                        for w in segment.words
                    ] if segment.words else [],
                })
            
            return {
                "language": info.language,
                "language_probability": info.language_probability,
                "duration": info.duration,
                "segments": transcript,
            }
        except Exception as e:
            logger.error(f"faster-whisper transcription failed: {e}")
            raise