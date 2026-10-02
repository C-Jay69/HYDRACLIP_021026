"""Common shape for stock media providers.

Each provider returns wildly different JSON, so everything is normalised to
:class:`StockAsset` before the renderer sees it. Attribution travels with the
asset rather than being looked up later, because both Pixabay and Unsplash
require crediting the source and a credit you have to reconstruct afterwards
is a credit that eventually goes missing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

IMAGE = "image"
VIDEO = "video"


class StockError(RuntimeError):
    """A stock provider interaction failed."""


class StockNotConfigured(StockError):
    """The provider has no API key."""


@dataclass
class StockAsset:
    """One piece of footage, normalised across providers."""

    provider: str
    asset_id: str
    kind: str  # IMAGE or VIDEO
    url: str
    """Direct media URL. Downloaded before use -- Pixabay forbids permanent
    hotlinking and the renderer needs local bytes anyway."""

    width: int = 0
    height: int = 0
    duration: float | None = None
    thumbnail: str | None = None

    # --- Attribution ------------------------------------------------------
    page_url: str = ""
    author: str = ""
    author_url: str | None = None
    license_note: str = ""

    #: True when the only available file carries a visible watermark, which
    #: makes the render a draft rather than something publishable.
    watermarked: bool = False

    #: Unsplash requires a GET to this URL whenever a photo is downloaded.
    download_tracking_url: str | None = None

    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def is_vertical(self) -> bool:
        return self.height > self.width

    def attribution(self) -> str:
        """A human-readable credit line."""
        label = {
            "pixabay": "Pixabay",
            "unsplash": "Unsplash",
            "shutterstock": "Shutterstock",
        }.get(self.provider, self.provider.title())

        if self.author:
            return f"{self.author} / {label}"
        return label

    def to_dict(self) -> dict[str, Any]:
        """Persisted on the video so credits survive without re-querying."""
        return {
            "provider": self.provider,
            "asset_id": self.asset_id,
            "kind": self.kind,
            "page_url": self.page_url,
            "author": self.author,
            "author_url": self.author_url,
            "license": self.license_note,
            "watermarked": self.watermarked,
            "credit": self.attribution(),
        }


class StockProvider:
    """Base class for a stock media source."""

    name: str = ""
    label: str = ""
    supports_video: bool = False
    supports_images: bool = True

    #: Whether the provider's terms require visible credit.
    requires_attribution: bool = True

    #: Whether returned files carry a watermark.
    watermarked_previews: bool = False

    def configuration_error(self) -> str | None:
        raise NotImplementedError

    def require_configured(self) -> None:
        problem = self.configuration_error()
        if problem:
            raise StockNotConfigured(f"{self.label} is {problem}.")

    async def search(
        self,
        query: str,
        kind: str = VIDEO,
        orientation: str = "vertical",
        limit: int = 10,
    ) -> list[StockAsset]:
        raise NotImplementedError

    async def note_download(self, asset: StockAsset) -> None:
        """Hook for providers that require download tracking. Default no-op."""
        return None

    # --- Helpers ---------------------------------------------------------------

    #: Test seam. When set, every client this provider builds uses it, which
    #: lets the suite replay documented API responses without a network.
    transport: Any = None

    def _client(self, **kwargs: Any) -> httpx.AsyncClient:
        kwargs.setdefault("timeout", 30.0)
        if self.transport is not None:
            kwargs.setdefault("transport", self.transport)
        return httpx.AsyncClient(**kwargs)

    @staticmethod
    def _raise_for_status(response: httpx.Response, action: str) -> None:
        if response.is_success:
            return
        if response.status_code == 429:
            raise StockError(
                f"{action} hit the provider's rate limit. "
                f"Slow down or cache more aggressively."
            )
        detail = response.text[:300]
        try:
            body = response.json()
            if isinstance(body, dict):
                errors = body.get("errors")
                if isinstance(errors, list) and errors:
                    detail = "; ".join(str(e) for e in errors)[:300]
        except ValueError:
            # Pixabay returns plain text on error, not JSON.
            pass
        raise StockError(f"{action} failed ({response.status_code}): {detail}")
