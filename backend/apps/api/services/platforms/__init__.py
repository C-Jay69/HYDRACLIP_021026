"""Publishing platform clients and the registry that resolves them."""

from __future__ import annotations

from apps.api.services.platforms.base import (
    PlatformAuthError,
    PlatformClient,
    PlatformError,
    PlatformNotConfigured,
    PublishError,
    PublishRequest,
    PublishResult,
    TokenSet,
    generate_pkce_pair,
)
from apps.api.services.platforms.instagram import InstagramClient
from apps.api.services.platforms.tiktok import TikTokClient
from apps.api.services.platforms.x import XClient
from apps.api.services.platforms.youtube import YouTubeClient

_REGISTRY: dict[str, PlatformClient] = {
    client.name: client
    for client in (YouTubeClient(), InstagramClient(), TikTokClient(), XClient())
}

#: Stable ordering for API responses.
SUPPORTED_PLATFORMS: tuple[str, ...] = tuple(_REGISTRY)


class UnknownPlatform(PlatformError):
    """The requested platform is not one we support."""


def get_platform(name: str) -> PlatformClient:
    """Resolve a platform client by name, case-insensitively."""
    client = _REGISTRY.get((name or "").strip().lower())
    if client is None:
        raise UnknownPlatform(
            f"Unknown platform '{name}'. Supported platforms are: "
            f"{', '.join(SUPPORTED_PLATFORMS)}."
        )
    return client


def all_platforms() -> list[PlatformClient]:
    return [_REGISTRY[name] for name in SUPPORTED_PLATFORMS]


__all__ = [
    "InstagramClient",
    "PlatformAuthError",
    "PlatformClient",
    "PlatformError",
    "PlatformNotConfigured",
    "PublishError",
    "PublishRequest",
    "PublishResult",
    "SUPPORTED_PLATFORMS",
    "TikTokClient",
    "TokenSet",
    "UnknownPlatform",
    "XClient",
    "YouTubeClient",
    "all_platforms",
    "generate_pkce_pair",
    "get_platform",
]
