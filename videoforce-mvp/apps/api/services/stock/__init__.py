"""Stock footage sourcing.

Four providers behind one interface. The default preference order is
``pexels, pixabay, unsplash, shutterstock``:

======================  =====  ======  ==========  ====================
Provider                Video  Photos  Watermark   Notes
======================  =====  ======  ==========  ====================
Pexels                  yes    yes     no          portrait filter on both
Pixabay                 yes    yes     no          no orientation on video
Unsplash                no     yes     no          download ping required
Shutterstock            yes    yes     **yes**     previews are comps
======================  =====  ======  ==========  ====================

Only providers with a configured API key take part, so an install with one
key works exactly as well as an install with four -- it just has a smaller
pool to draw from.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import httpx

from apps.api.core.config import settings
from apps.api.services.stock.base import (
    IMAGE,
    VIDEO,
    StockAsset,
    StockError,
    StockNotConfigured,
    StockProvider,
)
from apps.api.services.stock.pexels import PexelsProvider
from apps.api.services.stock.pixabay import PixabayProvider
from apps.api.services.stock.shutterstock import ShutterstockProvider
from apps.api.services.stock.unsplash import UnsplashProvider

logger = logging.getLogger(__name__)

__all__ = [
    "IMAGE",
    "VIDEO",
    "StockAsset",
    "StockError",
    "StockLibrary",
    "StockNotConfigured",
    "StockProvider",
    "PexelsProvider",
    "PixabayProvider",
    "ShutterstockProvider",
    "UnsplashProvider",
    "get_stock_library",
    "PROVIDER_CLASSES",
]

PROVIDER_CLASSES: dict[str, type[StockProvider]] = {
    PexelsProvider.name: PexelsProvider,
    PixabayProvider.name: PixabayProvider,
    UnsplashProvider.name: UnsplashProvider,
    ShutterstockProvider.name: ShutterstockProvider,
}

#: Downloads are capped so that one oversized clip cannot fill the disk.
MAX_DOWNLOAD_BYTES = 120 * 1024 * 1024


class StockLibrary:
    """Searches the configured providers in preference order."""

    def __init__(
        self,
        providers: list[StockProvider] | None = None,
        transport: object | None = None,
    ) -> None:
        if providers is not None:
            self._providers = providers
        else:
            self._providers = [cls() for cls in self._ordered_classes()]

        #: Test seam, matching StockProvider.transport.
        self.transport = transport
        if transport is not None:
            for provider in self._providers:
                provider.transport = transport

    @staticmethod
    def _ordered_classes() -> list[type[StockProvider]]:
        order = [
            part.strip().lower()
            for part in (settings.STOCK_PROVIDER_ORDER or "").split(",")
            if part.strip()
        ]
        classes = [PROVIDER_CLASSES[name] for name in order if name in PROVIDER_CLASSES]
        # Anything not named in the setting still gets a turn, at the back.
        classes += [c for c in PROVIDER_CLASSES.values() if c not in classes]
        return classes

    # --- Introspection -------------------------------------------------------

    def available(self) -> list[StockProvider]:
        """Providers that actually have credentials."""
        return [p for p in self._providers if p.configuration_error() is None]

    def status(self) -> list[dict]:
        """Per-provider readiness, for diagnostics and the health endpoint."""
        return [
            {
                "name": p.name,
                "label": p.label,
                "configured": p.configuration_error() is None,
                "reason": p.configuration_error(),
                "supports_video": p.supports_video,
                "supports_images": p.supports_images,
                "watermarked": p.watermarked_previews,
            }
            for p in self._providers
        ]

    def unavailable_reason(self) -> str | None:
        """Why sourcing cannot run at all, or None when it can.

        Mirrors the pattern already used by the TTS engine so the pipeline
        can explain itself instead of failing opaquely.
        """
        if self.available():
            return None
        names = ", ".join(
            f"{p.label} ({p.configuration_error()})" for p in self._providers
        )
        return (
            "No stock media provider is configured, so there is no footage to "
            f"assemble. Set at least one API key: {names}"
        )

    # --- Searching -----------------------------------------------------------

    async def find(
        self,
        query: str,
        prefer_video: bool = True,
        orientation: str = "vertical",
        limit: int = 10,
        exclude_ids: set[str] | None = None,
    ) -> list[StockAsset]:
        """Return candidate assets for one scene, best provider first.

        Tries video across every provider that has it before falling back to
        stills, because a moving clip beats a pan over a photograph. A
        provider that errors is logged and skipped -- one dead API key should
        not sink the render.
        """
        exclude_ids = exclude_ids or set()
        providers = self.available()
        if not providers:
            raise StockNotConfigured(self.unavailable_reason() or "No provider.")

        attempts: list[tuple[StockProvider, str]] = []
        if prefer_video:
            attempts += [(p, VIDEO) for p in providers if p.supports_video]
        attempts += [(p, IMAGE) for p in providers if p.supports_images]
        if not prefer_video:
            attempts += [(p, VIDEO) for p in providers if p.supports_video]

        results: list[StockAsset] = []
        errors: list[str] = []

        for provider, kind in attempts:
            try:
                found = await provider.search(
                    query, kind=kind, orientation=orientation, limit=limit
                )
            except StockError as exc:
                errors.append(f"{provider.label}: {exc}")
                logger.warning("Stock search failed on %s: %s", provider.name, exc)
                continue

            fresh = [
                a for a in found if f"{a.provider}:{a.asset_id}" not in exclude_ids
            ]
            if fresh:
                results.extend(fresh)
                # One good provider is enough; no need to spend another
                # provider's rate limit on the same scene.
                break

        if not results and errors:
            raise StockError("; ".join(errors))
        return results

    # --- Downloading ---------------------------------------------------------

    async def download(self, asset: StockAsset, destination: Path) -> Path:
        """Fetch an asset to local disk.

        Downloading rather than hotlinking is not an optimisation: Pixabay's
        terms forbid permanent hotlinking outright, and ffmpeg wants a local
        file regardless.
        """
        destination.parent.mkdir(parents=True, exist_ok=True)

        client_args: dict = {"timeout": 120.0, "follow_redirects": True}
        if self.transport is not None:
            client_args["transport"] = self.transport

        async with httpx.AsyncClient(**client_args) as client:
            async with client.stream("GET", asset.url) as response:
                if not response.is_success:
                    raise StockError(
                        f"Could not download {asset.provider} asset "
                        f"{asset.asset_id} ({response.status_code})."
                    )

                written = 0
                with destination.open("wb") as handle:
                    async for chunk in response.aiter_bytes(64 * 1024):
                        written += len(chunk)
                        if written > MAX_DOWNLOAD_BYTES:
                            handle.close()
                            destination.unlink(missing_ok=True)
                            raise StockError(
                                f"{asset.provider} asset {asset.asset_id} exceeds "
                                f"the {MAX_DOWNLOAD_BYTES // (1024 * 1024)}MB limit."
                            )
                        handle.write(chunk)

        if written == 0:
            destination.unlink(missing_ok=True)
            raise StockError(
                f"{asset.provider} asset {asset.asset_id} downloaded as 0 bytes."
            )

        # Unsplash requires this; everyone else no-ops.
        provider = self._provider_named(asset.provider)
        if provider is not None:
            try:
                await provider.note_download(asset)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Download tracking failed for %s: %s", asset.url, exc)

        return destination

    def _provider_named(self, name: str) -> StockProvider | None:
        for provider in self._providers:
            if provider.name == name:
                return provider
        return None


_library: StockLibrary | None = None
_lock = asyncio.Lock()


def get_stock_library() -> StockLibrary:
    """Process-wide library instance."""
    global _library
    if _library is None:
        _library = StockLibrary()
    return _library


def reset_stock_library() -> None:
    """Drop the cached instance. Used by tests that change settings."""
    global _library
    _library = None
