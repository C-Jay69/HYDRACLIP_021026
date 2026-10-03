"""Pixabay: free, royalty-free, no watermark, and it has video.

Terms that shape this code (from Pixabay's API documentation):

* "requests must be cached for 24 hours" -- see :mod:`.cache`.
* "permanent hotlinking of images is not allowed ... download them to your
  server first" -- the renderer downloads every asset before use.
* "show your users where the images and videos are from" -- attribution is
  carried on every :class:`StockAsset` and persisted with the video.
"""

from __future__ import annotations

import json

from apps.api.core.config import settings
from apps.api.services.stock.base import (
    IMAGE,
    VIDEO,
    StockAsset,
    StockProvider,
)
from apps.api.services.stock.cache import TTLCache

IMAGE_ENDPOINT = "https://pixabay.com/api/"
VIDEO_ENDPOINT = "https://pixabay.com/api/videos/"

_cache = TTLCache(ttl_seconds=settings.STOCK_CACHE_TTL_SECONDS)


class PixabayProvider(StockProvider):
    name = "pixabay"
    label = "Pixabay"
    supports_video = True
    supports_images = True
    requires_attribution = True
    watermarked_previews = False

    @property
    def api_key(self) -> str:
        return settings.PIXABAY_API_KEY

    def configuration_error(self) -> str | None:
        if not self.api_key:
            return "not configured: PIXABAY_API_KEY must be set"
        return None

    async def search(
        self,
        query: str,
        kind: str = VIDEO,
        orientation: str = "vertical",
        limit: int = 10,
    ) -> list[StockAsset]:
        self.require_configured()

        # Pixabay caps the search term at 100 characters.
        query = (query or "").strip()[:100]

        params: dict[str, object] = {
            "key": self.api_key,
            "q": query,
            "safesearch": "true",
            "order": "popular",
            # The API rejects per_page below 3.
            "per_page": max(3, min(int(limit), 200)),
        }

        if kind == VIDEO:
            endpoint = VIDEO_ENDPOINT
            params["video_type"] = "film"
        else:
            endpoint = IMAGE_ENDPOINT
            params["image_type"] = "photo"
            # Pixabay's image orientation vocabulary is horizontal/vertical,
            # unlike Unsplash's landscape/portrait.
            if orientation in ("vertical", "portrait"):
                params["orientation"] = "vertical"
            elif orientation in ("horizontal", "landscape"):
                params["orientation"] = "horizontal"

        cache_key = self._cache_key(endpoint, params)
        cached = _cache.get(cache_key)
        if cached is not None:
            payload = cached
        else:
            async with self._client() as client:
                response = await client.get(endpoint, params=params)
            self._raise_for_status(response, "Pixabay search")
            payload = response.json()
            _cache.set(cache_key, payload)

        hits = payload.get("hits") or []
        parse = self._parse_video if kind == VIDEO else self._parse_image
        assets = [parse(hit) for hit in hits]
        return [a for a in assets if a is not None][:limit]

    @staticmethod
    def _cache_key(endpoint: str, params: dict) -> str:
        # The key never includes the API key itself.
        safe = {k: v for k, v in params.items() if k != "key"}
        return f"{endpoint}?{json.dumps(safe, sort_keys=True)}"

    def _parse_image(self, hit: dict) -> StockAsset | None:
        # largeImageURL (1280px) is available to every key; fullHDURL and
        # imageURL require approved full API access, so prefer them only when
        # present.
        url = hit.get("fullHDURL") or hit.get("largeImageURL") or hit.get("webformatURL")
        if not url:
            return None

        return StockAsset(
            provider=self.name,
            asset_id=str(hit.get("id", "")),
            kind=IMAGE,
            url=url,
            width=int(hit.get("imageWidth") or 0),
            height=int(hit.get("imageHeight") or 0),
            thumbnail=hit.get("previewURL"),
            page_url=hit.get("pageURL", ""),
            author=hit.get("user", ""),
            author_url=self._user_url(hit),
            license_note="Pixabay Content License",
            raw=hit,
        )

    def _parse_video(self, hit: dict) -> StockAsset | None:
        streams = hit.get("videos") or {}

        # "medium" is guaranteed present for every Pixabay video and is
        # typically 1920x1080 -- plenty for a 1080-wide render, and far
        # smaller than "large" (often 4K).
        for size in ("medium", "small", "large", "tiny"):
            stream = streams.get(size) or {}
            url = stream.get("url")
            if url:
                break
        else:
            return None

        return StockAsset(
            provider=self.name,
            asset_id=str(hit.get("id", "")),
            kind=VIDEO,
            url=url,
            width=int(stream.get("width") or 0),
            height=int(stream.get("height") or 0),
            duration=float(hit.get("duration") or 0) or None,
            thumbnail=stream.get("thumbnail"),
            page_url=hit.get("pageURL", ""),
            author=hit.get("user", ""),
            author_url=self._user_url(hit),
            license_note="Pixabay Content License",
            raw=hit,
        )

    @staticmethod
    def _user_url(hit: dict) -> str | None:
        user = hit.get("user")
        user_id = hit.get("user_id")
        if user and user_id:
            return f"https://pixabay.com/users/{user}-{user_id}/"
        return None
