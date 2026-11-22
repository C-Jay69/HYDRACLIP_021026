"""Unsplash background image provider.

We use Unsplash photos as the visual base for each scene. The renderer loads
the image URLs directly from images.unsplash.com, and the composition shows a
small photographer credit as required by the Unsplash API guidelines.
"""

import logging
from typing import Any, Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class UnsplashProvider:
    """Searches Unsplash for portrait background photos."""

    def __init__(self, access_key: Optional[str] = None):
        self.access_key = (
            access_key if access_key is not None else settings.unsplash_access_key
        )
        self.base_url = "https://api.unsplash.com"

    @property
    def enabled(self) -> bool:
        return bool(self.access_key)

    async def search_images(
        self,
        query: str,
        count: int = 6,
    ) -> list[dict[str, Any]]:
        if not self.enabled:
            logger.warning(
                "UNSPLASH_ACCESS_KEY is not set - rendering without photo backgrounds"
            )
            return []

        cleaned = " ".join((query or "").split())[:120] or "abstract background"
        images = await self._search(cleaned, count)

        if not images and cleaned != "abstract background":
            logger.info("No Unsplash results for %r; trying a generic query", cleaned)
            images = await self._search("abstract background", count)

        return images

    async def _search(self, query: str, count: int) -> list[dict[str, Any]]:
        params = {
            "query": query,
            "per_page": max(1, min(count, 10)),
            "orientation": "portrait",
            "content_filter": "high",
            "client_id": self.access_key,
        }
        headers = {
            "Accept-Version": "v1",
            "User-Agent": "HydraClip/1.0",
        }

        try:
            timeout = httpx.Timeout(20.0, connect=10.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(
                    f"{self.base_url}/search/photos",
                    params=params,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            logger.warning("Unsplash search failed: %s", exc)
            return []

        images: list[dict[str, Any]] = []
        for photo in data.get("results", []) or []:
            urls = photo.get("urls") or {}
            user = photo.get("user") or {}
            base = urls.get("raw") or urls.get("regular") or urls.get("small")
            if not base:
                continue

            # Ask Unsplash's CDN for a 1080x1920 portrait crop.
            base = base.split("?")[0]
            src = f"{base}?auto=format&fit=crop&w=1080&h=1920&q=80"
            name = (user.get("name") or "Unsplash").strip()

            images.append(
                {
                    "src": src,
                    "credit": f"Photo: {name} / Unsplash",
                    "photographer": name,
                    "photographer_url": (user.get("links") or {}).get("html"),
                    "alt": photo.get("alt_description") or "",
                    "id": photo.get("id"),
                }
            )

        logger.info("Unsplash returned %d photos for %r", len(images), query)
        return images[:count]
