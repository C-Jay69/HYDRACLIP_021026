"""Unsplash: photos only, with mandatory download tracking.

Two of Unsplash's API guidelines are load-bearing here:

* Every download must trigger a GET to the photo's ``download_location``.
  That is what :meth:`UnsplashProvider.note_download` is for, and the
  renderer calls it for every asset it actually fetches.
* The ``ixid`` query parameter must survive any URL manipulation, so sizing
  is done by appending imgix parameters to ``urls.raw`` rather than by
  rebuilding the URL.
"""

from __future__ import annotations

import logging

from apps.api.core.config import settings
from apps.api.services.stock.base import (
    IMAGE,
    VIDEO,
    StockAsset,
    StockError,
    StockProvider,
)

logger = logging.getLogger(__name__)

API_ROOT = "https://api.unsplash.com"


class UnsplashProvider(StockProvider):
    name = "unsplash"
    label = "Unsplash"
    #: Unsplash has no video library at all.
    supports_video = False
    supports_images = True
    requires_attribution = True
    watermarked_previews = False

    @property
    def access_key(self) -> str:
        return settings.UNSPLASH_ACCESS_KEY

    def configuration_error(self) -> str | None:
        if not self.access_key:
            return "not configured: UNSPLASH_ACCESS_KEY must be set"
        return None

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Client-ID {self.access_key}",
            # Pinning the version keeps a future default bump from silently
            # changing the response shape.
            "Accept-Version": "v1",
        }

    async def search(
        self,
        query: str,
        kind: str = IMAGE,
        orientation: str = "vertical",
        limit: int = 10,
    ) -> list[StockAsset]:
        self.require_configured()

        if kind == VIDEO:
            raise StockError("Unsplash has no video library; request images instead.")

        params = {
            "query": (query or "").strip(),
            "per_page": max(1, min(int(limit), 30)),
            "orientation": self._orientation(orientation),
            "content_filter": "high",
        }

        async with self._client() as client:
            response = await client.get(
                f"{API_ROOT}/search/photos", params=params, headers=self._headers()
            )
        self._raise_for_status(response, "Unsplash search")

        results = response.json().get("results") or []
        return [self._parse(photo) for photo in results][:limit]

    @staticmethod
    def _orientation(value: str) -> str:
        return {
            "vertical": "portrait",
            "portrait": "portrait",
            "horizontal": "landscape",
            "landscape": "landscape",
        }.get(value, "portrait")

    def _parse(self, photo: dict) -> StockAsset:
        urls = photo.get("urls") or {}
        raw = urls.get("raw")

        # Ask imgix for exactly the frame size we render at, so the download
        # is as small as it can be. The ixid in `raw` is preserved because we
        # only append.
        if raw:
            separator = "&" if "?" in raw else "?"
            url = (
                f"{raw}{separator}w={settings.VIDEO_WIDTH}"
                f"&h={settings.VIDEO_HEIGHT}&fit=crop&crop=entropy&fm=jpg&q=85"
            )
        else:
            url = urls.get("regular") or urls.get("full") or ""

        user = photo.get("user") or {}
        links = photo.get("links") or {}
        user_links = user.get("links") or {}

        return StockAsset(
            provider=self.name,
            asset_id=str(photo.get("id", "")),
            kind=IMAGE,
            url=url,
            width=int(photo.get("width") or 0),
            height=int(photo.get("height") or 0),
            thumbnail=urls.get("thumb"),
            page_url=links.get("html", ""),
            author=user.get("name") or user.get("username") or "",
            author_url=user_links.get("html"),
            license_note="Unsplash License",
            download_tracking_url=links.get("download_location"),
            raw=photo,
        )

    async def note_download(self, asset: StockAsset) -> None:
        """Report the download, as the API guidelines require.

        Deliberately non-fatal: failing to record a view is not a reason to
        abandon a render that has already fetched the bytes.
        """
        if not asset.download_tracking_url:
            return
        try:
            async with self._client(timeout=10.0) as client:
                await client.get(
                    asset.download_tracking_url, headers=self._headers()
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Could not report the Unsplash download for %s: %s",
                asset.asset_id,
                exc,
            )
