"""HTTP client for the Remotion render service."""

import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class RenderClient:
    """Calls the Node/Remotion service and returns the rendered MP4 bytes."""

    def __init__(self, base_url: str | None = None, timeout_seconds: int | None = None):
        self.base_url = (base_url or settings.renderer_url).rstrip("/")
        self.timeout_seconds = timeout_seconds or settings.render_timeout_seconds

    async def health(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{self.base_url}/health")
            response.raise_for_status()
            return response.json()

    async def render(self, input_props: dict[str, Any]) -> bytes:
        """Render a composition with the given input props and return MP4 bytes."""
        timeout = httpx.Timeout(self.timeout_seconds, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{self.base_url}/render",
                json={"inputProps": input_props},
            )

        if response.status_code != 200:
            detail = response.text[:500]
            raise RuntimeError(
                f"Remotion renderer returned HTTP {response.status_code}: {detail}"
            )

        content_type = response.headers.get("content-type", "")
        if "video/mp4" not in content_type:
            raise RuntimeError(
                f"Remotion renderer returned unexpected content type: {content_type}"
            )
        if not response.content:
            raise RuntimeError("Remotion renderer returned an empty video")

        logger.info("Rendered video: %s bytes", len(response.content))
        return response.content
