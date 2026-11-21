"""Ollama Text Generation Provider."""

import httpx
import logging
from typing import Optional

from app.pipeline.providers.base import BaseTextGenerationProvider

logger = logging.getLogger(__name__)


class OllamaProvider(BaseTextGenerationProvider):
    """Ollama text generation provider."""
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.2"):
        self.base_url = base_url
        self.model = model
    
    async def generate_script(self, topic: str, prompt: str, **kwargs) -> str:
        """Generate script for topic."""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": f"{prompt}\n\nTopic: {topic}",
                        "stream": False,
                    },
                )
                result = response.json()
                return result.get("response", "")
        except Exception as e:
            logger.error(f"Ollama script generation failed: {e}")
            return f"Script for: {topic}\n\nThis is a fallback script about {topic}."
    
    async def generate_title(self, topic: str, script: str, **kwargs) -> str:
        """Generate video title."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": f"Create a catchy YouTube title for: {topic}\n\nScript: {script[:500]}",
                        "stream": False,
                    },
                )
                result = response.json()
                return result.get("response", topic)
        except Exception as e:
            logger.error(f"Ollama title generation failed: {e}")
            return topic
    
    async def generate_description(self, topic: str, title: str, script: str, **kwargs) -> str:
        """Generate video description."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": f"Write a YouTube video description for: {title}\n\nTopic: {topic}",
                        "stream": False,
                    },
                )
                result = response.json()
                return result.get("response", f"A video about {topic}")
        except Exception as e:
            logger.error(f"Ollama description generation failed: {e}")
            return f"A video about {topic}"
    
    async def generate_hashtags(self, topic: str, **kwargs) -> list:
        """Generate hashtags."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": f"Generate 10 hashtags for: {topic}\nReturn only hashtags separated by spaces.",
                        "stream": False,
                    },
                )
                result = response.json()
                text = result.get("response", "")
                return [h.strip() for h in text.split() if h.startswith("#")]
        except Exception as e:
            logger.error(f"Ollama hashtag generation failed: {e}")
            return [f"#{topic.replace(' ', '')}", "#ai", "#video"]
    
    async def generate_scene_plan(self, topic: str, script: str, **kwargs) -> list:
        """Generate scene plan."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": f"Create a scene plan for a video about: {topic}\n\nScript: {script[:1000]}\n\nReturn as JSON array of scenes with start_time, end_time, description.",
                        "stream": False,
                    },
                )
                result = response.json()
                text = result.get("response", "[]")
                import json
                try:
                    return json.loads(text)
                except:
                    return [{"start": 0, "end": 60, "description": topic}]
        except Exception as e:
            logger.error(f"Ollama scene plan generation failed: {e}")
            return [{"start": 0, "end": 60, "description": topic}]
    
    async def generate_cta(self, topic: str, script: str, **kwargs) -> str:
        """Generate call to action."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": f"Create a call to action for a video about: {topic}",
                        "stream": False,
                    },
                )
                result = response.json()
                return result.get("response", "Like and subscribe!")
        except Exception as e:
            logger.error(f"Ollama CTA generation failed: {e}")
            return "Like and subscribe!"