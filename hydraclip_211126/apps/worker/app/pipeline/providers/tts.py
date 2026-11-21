"""TTS Providers: Edge TTS (primary) and Piper (fallback)."""

import logging
import os
import subprocess
from typing import Optional

from app.pipeline.providers.base import BaseTTSProvider

logger = logging.getLogger(__name__)


class EdgeTTSProvider(BaseTTSProvider):
    """Edge TTS provider (cloud-based, free)."""
    
    def __init__(self, voice: str = "en-US-AriaNeural"):
        self.voice = voice
    
    async def synthesize(self, text: str, voice: str, language: str, **kwargs) -> str:
        """Synthesize text to audio file using Edge TTS."""
        try:
            import edge_tts
            import asyncio
            
            output_path = kwargs.get("output_path", "/tmp/output.wav")
            
            communicate = edge_tts.Communicate(text, voice or self.voice)
            await communicate.save(output_path)
            
            return output_path
        except ImportError:
            logger.error("edge-tts not installed")
            raise
        except Exception as e:
            logger.error(f"Edge TTS failed: {e}")
            raise


class PiperTTSProvider(BaseTTSProvider):
    """Piper TTS provider (fully local)."""
    
    def __init__(self, model_path: str = "/models/piper"):
        self.model_path = model_path
    
    async def synthesize(self, text: str, voice: str, language: str, **kwargs) -> str:
        """Synthesize text to audio file using Piper."""
        try:
            output_path = kwargs.get("output_path", "/tmp/output.wav")
            
            # Use Piper CLI
            model_file = f"{self.model_path}/{voice}.onnx"
            if not os.path.exists(model_file):
                # Try default model
                model_file = f"{self.model_path}/default.onnx"
            
            cmd = [
                "piper",
                "--model", model_file,
                "--output_file", output_path,
            ]
            
            process = subprocess.run(
                cmd,
                input=text,
                capture_output=True,
                text=True,
                timeout=60,
            )
            
            if process.returncode != 0:
                raise Exception(f"Piper failed: {process.stderr}")
            
            return output_path
        except FileNotFoundError:
            logger.error("Piper not installed")
            raise
        except Exception as e:
            logger.error(f"Piper TTS failed: {e}")
            raise