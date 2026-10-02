"""Shutterstock, wrapped in the common provider interface.

This adapter sits on top of the pre-existing
:mod:`apps.api.services.shutterstock` client rather than replacing it, so the
raw-JSON client stays available for anything that wants licensing calls.

Shutterstock ranks last in the default provider order for one reason: the
URLs returned by search are *comp* previews and they carry a visible
watermark. Getting a clean file requires a paid licensing call that this
codebase does not make. Assets from here are therefore flagged
``watermarked=True``, which marks the whole render as a draft that must not
be published.
"""

from __future__ import annotations

from apps.api.core.config import settings
from apps.api.services.shutterstock import ShutterstockAPI
from apps.api.services.stock.base import (
    IMAGE,
    VIDEO,
    StockAsset,
    StockError,
    StockProvider,
)


class ShutterstockProvider(StockProvider):
    name = "shutterstock"
    label = "Shutterstock"
    supports_video = True
    supports_images = True
    requires_attribution = False
    #: The decisive difference from the free providers.
    watermarked_previews = True

    def __init__(self, api: ShutterstockAPI | None = None) -> None:
        self._api = api

    def configuration_error(self) -> str | None:
        if not settings.SHUTTERSTOCK_API_TOKEN:
            return "not configured: SHUTTERSTOCK_API_TOKEN must be set"
        return None

    async def search(
        self,
        query: str,
        kind: str = VIDEO,
        orientation: str = "vertical",
        limit: int = 10,
    ) -> list[StockAsset]:
        self.require_configured()

        api = self._api or ShutterstockAPI()
        per_page = max(1, min(int(limit), 25))

        try:
            if kind == VIDEO:
                payload = await api.search_videos(query, per_page=per_page)
                parse = self._parse_video
            else:
                payload = await api.search_images(
                    query,
                    per_page=per_page,
                    orientation=(
                        "portrait"
                        if orientation in ("vertical", "portrait")
                        else "landscape"
                    ),
                )
                parse = self._parse_image
        except Exception as exc:  # noqa: BLE001
            raise StockError(f"Shutterstock search failed: {exc}") from exc
        finally:
            if self._api is None:
                await api.close()

        assets = [parse(item) for item in (payload.get("data") or [])]
        return [a for a in assets if a is not None][:limit]

    def _parse_image(self, item: dict) -> StockAsset | None:
        assets = item.get("assets") or {}
        preview = (
            assets.get("huge_thumb")
            or assets.get("preview_1500")
            or assets.get("preview")
            or {}
        )
        url = preview.get("url")
        if not url:
            return None

        contributor = item.get("contributor") or {}
        return StockAsset(
            provider=self.name,
            asset_id=str(item.get("id", "")),
            kind=IMAGE,
            url=url,
            width=int(preview.get("width") or 0),
            height=int(preview.get("height") or 0),
            thumbnail=(assets.get("small_thumb") or {}).get("url"),
            page_url=f"https://www.shutterstock.com/image-photo/-{item.get('id', '')}",
            author=contributor.get("display_name") or contributor.get("id") or "",
            license_note="Shutterstock comp preview - licence required before use",
            watermarked=True,
            raw=item,
        )

    def _parse_video(self, item: dict) -> StockAsset | None:
        assets = item.get("assets") or {}
        preview = (
            assets.get("preview_mp4")
            or assets.get("preview_webm")
            or assets.get("preview_jpg")
            or {}
        )
        url = preview.get("url")
        if not url:
            return None

        contributor = item.get("contributor") or {}
        return StockAsset(
            provider=self.name,
            asset_id=str(item.get("id", "")),
            kind=VIDEO,
            url=url,
            width=int(preview.get("width") or 0),
            height=int(preview.get("height") or 0),
            duration=float(item.get("duration") or 0) or None,
            thumbnail=(assets.get("thumb_jpg") or {}).get("url"),
            page_url=f"https://www.shutterstock.com/video/clip-{item.get('id', '')}",
            author=contributor.get("display_name") or contributor.get("id") or "",
            license_note="Shutterstock comp preview - licence required before use",
            watermarked=True,
            raw=item,
        )
