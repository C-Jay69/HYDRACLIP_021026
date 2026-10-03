"""Pexels: the preferred source for both footage and stills.

Why it leads the provider order:

* It has photos *and* video, so a single provider can usually fill an entire
  storyboard.
* ``orientation=portrait`` is supported on both search endpoints, unlike
  Pixabay whose video search has no orientation filter at all.
* Each video exposes ``video_files[]`` with real pixel dimensions, so we can
  pick a file that is already close to 1080x1920 rather than downloading 4K
  and throwing most of it away.
* No watermarks, and the licence is free for commercial use.

Guidelines that shape this code:

* "Whenever you are doing an API request make sure to show a prominent link
  to Pexels" and "always credit our photographers when possible" -- every
  asset carries its author and page URL, and those are rendered into the
  credits and persisted on the video.
* Rate limited to 200 requests/hour by default, so searches are cached (see
  :mod:`.cache`) exactly as Pixabay's terms separately require.
* Authorization is the bare API key -- *not* ``Bearer <key>``.
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

API_ROOT = "https://api.pexels.com/v1"
PHOTO_SEARCH = f"{API_ROOT}/search"
#: The documentation is explicit that /videos/ (without /v1) is deprecated.
VIDEO_SEARCH = f"{API_ROOT}/videos/search"

_cache = TTLCache(ttl_seconds=settings.STOCK_CACHE_TTL_SECONDS)


class PexelsProvider(StockProvider):
    name = "pexels"
    label = "Pexels"
    supports_video = True
    supports_images = True
    requires_attribution = True
    watermarked_previews = False

    @property
    def api_key(self) -> str:
        return settings.PEXELS_API_KEY

    def configuration_error(self) -> str | None:
        if not self.api_key:
            return "not configured: PEXELS_API_KEY must be set"
        return None

    def _headers(self) -> dict[str, str]:
        # Pexels wants the raw key, with no "Bearer " prefix.
        return {"Authorization": self.api_key}

    async def search(
        self,
        query: str,
        kind: str = VIDEO,
        orientation: str = "vertical",
        limit: int = 10,
    ) -> list[StockAsset]:
        self.require_configured()

        params: dict[str, object] = {
            "query": (query or "").strip(),
            "orientation": self._orientation(orientation),
            # Max is 80.
            "per_page": max(1, min(int(limit), 80)),
        }

        if kind == VIDEO:
            endpoint = VIDEO_SEARCH
            # "medium" means at least Full HD for videos -- enough for a
            # 1080-wide render without pulling 4K files.
            params["size"] = "medium"
        else:
            endpoint = PHOTO_SEARCH
            # "medium" means at least 12MP for photos.
            params["size"] = "medium"

        cache_key = f"{endpoint}?{json.dumps(params, sort_keys=True)}"
        cached = _cache.get(cache_key)
        if cached is not None:
            payload = cached
        else:
            async with self._client() as client:
                response = await client.get(
                    endpoint, params=params, headers=self._headers()
                )
            self._raise_for_status(response, "Pexels search")
            payload = response.json()
            _cache.set(cache_key, payload)

        if kind == VIDEO:
            items = payload.get("videos") or []
            assets = [self._parse_video(item) for item in items]
        else:
            items = payload.get("photos") or []
            assets = [self._parse_photo(item) for item in items]

        return [a for a in assets if a is not None][:limit]

    @staticmethod
    def _orientation(value: str) -> str:
        return {
            "vertical": "portrait",
            "portrait": "portrait",
            "horizontal": "landscape",
            "landscape": "landscape",
            "square": "square",
        }.get(value, "portrait")

    def _parse_photo(self, photo: dict) -> StockAsset | None:
        src = photo.get("src") or {}
        original = src.get("original")

        if original:
            # Pexels serves images through a resizing proxy that takes the
            # same query parameters src.portrait already uses. Asking for the
            # exact frame size keeps the download small and the crop centred.
            separator = "&" if "?" in original else "?"
            url = (
                f"{original}{separator}auto=compress&cs=tinysrgb&fit=crop"
                f"&w={settings.VIDEO_WIDTH}&h={settings.VIDEO_HEIGHT}"
            )
        else:
            url = src.get("portrait") or src.get("large2x") or src.get("large") or ""

        if not url:
            return None

        return StockAsset(
            provider=self.name,
            asset_id=str(photo.get("id", "")),
            kind=IMAGE,
            url=url,
            width=int(photo.get("width") or 0),
            height=int(photo.get("height") or 0),
            thumbnail=src.get("tiny"),
            page_url=photo.get("url", ""),
            author=photo.get("photographer", ""),
            author_url=photo.get("photographer_url"),
            license_note="Pexels License",
            raw=photo,
        )

    def _parse_video(self, video: dict) -> StockAsset | None:
        chosen = self._best_file(video.get("video_files") or [])
        if chosen is None:
            return None

        user = video.get("user") or {}

        return StockAsset(
            provider=self.name,
            asset_id=str(video.get("id", "")),
            kind=VIDEO,
            url=chosen.get("link", ""),
            width=int(chosen.get("width") or 0),
            height=int(chosen.get("height") or 0),
            duration=float(video.get("duration") or 0) or None,
            thumbnail=video.get("image"),
            page_url=video.get("url", ""),
            author=user.get("name", ""),
            author_url=user.get("url"),
            license_note="Pexels License",
            raw=video,
        )

    @staticmethod
    def _best_file(files: list[dict]) -> dict | None:
        """Pick the smallest file that still covers the output frame.

        ``video_files`` is an unordered mix of resolutions plus an HLS entry
        whose width and height are null. Downloading the 4K version to render
        at 1080x1920 wastes bandwidth and decode time, so prefer the smallest
        file that is at least as large as the target frame, and fall back to
        the largest available when nothing reaches it.
        """
        target_w = settings.VIDEO_WIDTH
        target_h = settings.VIDEO_HEIGHT

        usable = [
            f
            for f in files
            # The HLS entry is a playlist, not a file ffmpeg should be handed
            # here, and it reports null dimensions.
            if f.get("quality") != "hls"
            and f.get("link")
            and f.get("width")
            and f.get("height")
        ]
        if not usable:
            return None

        def area(f: dict) -> int:
            return int(f["width"]) * int(f["height"])

        covering = [
            f
            for f in usable
            if int(f["width"]) >= target_w and int(f["height"]) >= target_h
        ]
        if covering:
            return min(covering, key=area)

        # Nothing is big enough in both axes; take the highest resolution on
        # offer and let the scaler letterbox it.
        return max(usable, key=area)
