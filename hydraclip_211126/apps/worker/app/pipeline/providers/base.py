"""Base Provider Interface for HydraClip Pipeline."""

from abc import ABC, abstractmethod
from typing import Optional


class BaseTextGenerationProvider(ABC):
    """Base text generation provider interface."""
    
    @abstractmethod
    async def generate_script(self, topic: str, prompt: str, **kwargs) -> str:
        """Generate script for topic."""
        pass
    
    @abstractmethod
    async def generate_title(self, topic: str, script: str, **kwargs) -> str:
        """Generate video title."""
        pass
    
    @abstractmethod
    async def generate_description(self, topic: str, title: str, script: str, **kwargs) -> str:
        """Generate video description."""
        pass
    
    @abstractmethod
    async def generate_hashtags(self, topic: str, **kwargs) -> list:
        """Generate hashtags."""
        pass
    
    @abstractmethod
    async def generate_scene_plan(self, topic: str, script: str, **kwargs) -> list:
        """Generate scene plan."""
        pass
    
    @abstractmethod
    async def generate_cta(self, topic: str, script: str, **kwargs) -> str:
        """Generate call to action."""
        pass


class BaseTTSProvider(ABC):
    """Base text-to-speech provider interface."""
    
    @abstractmethod
    async def synthesize(self, text: str, voice: str, language: str, **kwargs) -> str:
        """Synthesize text to audio file."""
        pass


class BaseSTTProvider(ABC):
    """Base speech-to-text provider interface."""
    
    @abstractmethod
    async def transcribe(self, audio_file: str, **kwargs) -> dict:
        """Transcribe audio to text with timestamps."""
        pass


class BaseThumbnailProvider(ABC):
    """Base thumbnail provider interface."""
    
    @abstractmethod
    async def generate(self, title: str, topic: str, **kwargs) -> str:
        """Generate thumbnail."""
        pass


class BaseVideoRenderProvider(ABC):
    """Base video render provider interface."""
    
    @abstractmethod
    async def render_short_form(self, script: str, audio_file: str, subtitles: str, **kwargs) -> str:
        """Render short-form video."""
        pass
    
    @abstractmethod
    async def render_long_form(self, script: str, audio_file: str, subtitles: str, **kwargs) -> str:
        """Render long-form video."""
        pass
    
    @abstractmethod
    async def add_captions(self, video_path: str, subtitles: str, style: str, **kwargs) -> str:
        """Add captions to video."""
        pass
    
    @abstractmethod
    async def add_intro_outro(self, video_path: str, intro: str, outro: str, **kwargs) -> str:
        """Add intro/outro to video."""
        pass
    
    @abstractmethod
    async def add_music(self, video_path: str, music_file: str, **kwargs) -> str:
        """Add music to video."""
        pass
    
    @abstractmethod
    async def add_logo_overlay(self, video_path: str, logo_file: str, **kwargs) -> str:
        """Add logo overlay to video."""
        pass
    
    @abstractmethod
    async def export_for_platform(self, video_path: str, platform: str, **kwargs) -> str:
        """Export video for specific platform."""
        pass