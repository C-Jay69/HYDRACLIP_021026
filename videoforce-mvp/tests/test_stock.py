"""Stock providers, exercised against mocked API responses.

No API keys for Pexels, Pixabay, Unsplash or Shutterstock are available
here, and this sandbox cannot reach any of them, so every provider is
verified against an ``httpx.MockTransport`` replaying the response shapes
from each vendor's published documentation. That proves we send the
parameters the API expects and correctly interpret what it returns; it does
not prove the live services behave as documented.

The fixtures below are trimmed copies of the exact examples in each
vendor's docs, so a change in our parsing that breaks on real data should
break here too.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from apps.api.core.config import settings
from apps.api.services.stock import (
    IMAGE,
    VIDEO,
    PexelsProvider,
    PixabayProvider,
    ShutterstockProvider,
    StockAsset,
    StockError,
    StockLibrary,
    StockNotConfigured,
    UnsplashProvider,
)
from apps.api.services.stock import cache as cache_module
from apps.api.services.stock import pexels as pexels_module
from apps.api.services.stock import pixabay as pixabay_module


# --- Fixtures from the published documentation --------------------------------

PEXELS_VIDEO_RESPONSE = {
    "page": 1,
    "per_page": 1,
    "total_results": 20475,
    "videos": [
        {
            "id": 2499611,
            "width": 1080,
            "height": 1920,
            "url": "https://www.pexels.com/video/2499611/",
            "image": "https://images.pexels.com/videos/2499611/thumb.jpg",
            "duration": 22,
            "user": {
                "id": 680589,
                "name": "Joey Farina",
                "url": "https://www.pexels.com/@joey",
            },
            "video_files": [
                {
                    "id": 125004,
                    "quality": "hd",
                    "file_type": "video/mp4",
                    "width": 1080,
                    "height": 1920,
                    "link": "https://player.vimeo.com/external/342571552.hd.mp4",
                },
                {
                    "id": 125005,
                    "quality": "sd",
                    "file_type": "video/mp4",
                    "width": 540,
                    "height": 960,
                    "link": "https://player.vimeo.com/external/342571552.sd.mp4",
                },
                {
                    "id": 125007,
                    "quality": "hd",
                    "file_type": "video/mp4",
                    "width": 2160,
                    "height": 3840,
                    "link": "https://player.vimeo.com/external/342571552.4k.mp4",
                },
                {
                    "id": 125009,
                    "quality": "hls",
                    "file_type": "video/mp4",
                    "width": None,
                    "height": None,
                    "link": "https://player.vimeo.com/external/342571552.m3u8",
                },
            ],
        }
    ],
}

PEXELS_PHOTO_RESPONSE = {
    "total_results": 10000,
    "page": 1,
    "per_page": 1,
    "photos": [
        {
            "id": 3573351,
            "width": 3066,
            "height": 3968,
            "url": "https://www.pexels.com/photo/trees-during-day-3573351/",
            "photographer": "Lukas Rodriguez",
            "photographer_url": "https://www.pexels.com/@lukas-rodriguez-1845331",
            "photographer_id": 1845331,
            "avg_color": "#374824",
            "src": {
                "original": "https://images.pexels.com/photos/3573351/photo.png",
                "portrait": "https://images.pexels.com/photos/3573351/photo.png?h=1200&w=800",
                "tiny": "https://images.pexels.com/photos/3573351/photo.png?w=280",
            },
            "alt": "Trees during day",
        }
    ],
}

PIXABAY_VIDEO_RESPONSE = {
    "total": 300,
    "totalHits": 100,
    "hits": [
        {
            "id": 125,
            "pageURL": "https://pixabay.com/videos/id-125/",
            "duration": 12,
            "user": "CoverrFreeFootage",
            "user_id": 1234,
            "videos": {
                "large": {"url": "", "width": 0, "height": 0, "size": 0},
                "medium": {
                    "url": "https://cdn.pixabay.com/video/125/medium.mp4",
                    "width": 1920,
                    "height": 1080,
                    "size": 6615235,
                    "thumbnail": "https://cdn.pixabay.com/video/125/medium.jpg",
                },
                "small": {
                    "url": "https://cdn.pixabay.com/video/125/small.mp4",
                    "width": 1280,
                    "height": 720,
                    "size": 3100000,
                },
            },
        }
    ],
}

PIXABAY_IMAGE_RESPONSE = {
    "total": 4692,
    "totalHits": 500,
    "hits": [
        {
            "id": 195893,
            "pageURL": "https://pixabay.com/photos/blossom-bloom-flower-195893/",
            "type": "photo",
            "tags": "blossom, bloom, flower",
            "previewURL": "https://cdn.pixabay.com/photo/195893_150.jpg",
            "webformatURL": "https://cdn.pixabay.com/photo/195893_640.jpg",
            "largeImageURL": "https://pixabay.com/get/195893_1280.jpg",
            "imageWidth": 4000,
            "imageHeight": 2250,
            "user": "Josch13",
            "user_id": 48777,
        }
    ],
}

UNSPLASH_RESPONSE = {
    "total": 133,
    "total_pages": 7,
    "results": [
        {
            "id": "eOLpJytrbsQ",
            "width": 4000,
            "height": 3000,
            "color": "#A7A2A1",
            "blur_hash": "LaLXMa9Fx[D%~q%MtQM|kDRjtRIU",
            "alt_description": "A man drinking a coffee.",
            "urls": {
                "raw": "https://images.unsplash.com/face-springmorning.jpg?ixid=TEST123",
                "full": "https://images.unsplash.com/face-springmorning.jpg?q=75&fm=jpg",
                "regular": "https://images.unsplash.com/face-springmorning.jpg?w=1080",
                "small": "https://images.unsplash.com/face-springmorning.jpg?w=400",
                "thumb": "https://images.unsplash.com/face-springmorning.jpg?w=200",
            },
            "links": {
                "self": "https://api.unsplash.com/photos/eOLpJytrbsQ",
                "html": "https://unsplash.com/photos/eOLpJytrbsQ",
                "download": "https://unsplash.com/photos/eOLpJytrbsQ/download",
                "download_location": (
                    "https://api.unsplash.com/photos/eOLpJytrbsQ/download"
                ),
            },
            "user": {
                "id": "Ul0QVz12Goo",
                "username": "ugmonk",
                "name": "Jeff Sheldon",
                "links": {"html": "https://unsplash.com/@ugmonk"},
            },
        }
    ],
}


def transport_for(payload, status=200, capture=None, text_body=None):
    """A MockTransport that records the request and replays a payload."""

    def handler(request: httpx.Request) -> httpx.Response:
        if capture is not None:
            capture.append(request)
        if text_body is not None:
            return httpx.Response(status, text=text_body)
        return httpx.Response(status, json=payload)

    return httpx.MockTransport(handler)


@pytest.fixture(autouse=True)
def clear_caches():
    """Search caching is required by Pixabay; it must not leak between tests."""
    pexels_module._cache.clear()
    pixabay_module._cache.clear()
    yield
    pexels_module._cache.clear()
    pixabay_module._cache.clear()


# --- Configuration ------------------------------------------------------------


def test_providers_report_missing_keys_by_name():
    """An unconfigured provider says which variable to set."""
    for provider, variable in (
        (PexelsProvider(), "PEXELS_API_KEY"),
        (PixabayProvider(), "PIXABAY_API_KEY"),
        (UnsplashProvider(), "UNSPLASH_ACCESS_KEY"),
        (ShutterstockProvider(), "SHUTTERSTOCK_API_TOKEN"),
    ):
        reason = provider.configuration_error()
        assert reason is not None
        assert variable in reason


async def test_search_without_a_key_raises_not_configured():
    with pytest.raises(StockNotConfigured):
        await PexelsProvider().search("ocean")


# --- Pexels -------------------------------------------------------------------


async def test_pexels_video_search_sends_documented_parameters(monkeypatch):
    monkeypatch.setattr(settings, "PEXELS_API_KEY", "pexels-key")
    captured: list[httpx.Request] = []

    provider = PexelsProvider()
    provider.transport = transport_for(PEXELS_VIDEO_RESPONSE, capture=captured)
    await provider.search("ocean plastic", kind=VIDEO, limit=5)

    request = captured[0]
    assert request.url.path == "/v1/videos/search"
    assert request.url.params["query"] == "ocean plastic"
    assert request.url.params["orientation"] == "portrait"
    assert request.url.params["per_page"] == "5"
    # Pexels wants the bare key, not "Bearer <key>".
    assert request.headers["authorization"] == "pexels-key"


async def test_pexels_picks_the_smallest_file_that_covers_the_frame(monkeypatch):
    """4K is wasteful when the output is 1080x1920; 540x960 is too small."""
    monkeypatch.setattr(settings, "PEXELS_API_KEY", "pexels-key")
    provider = PexelsProvider()
    provider.transport = transport_for(PEXELS_VIDEO_RESPONSE)

    assets = await provider.search("ocean", kind=VIDEO)

    assert len(assets) == 1
    asset = assets[0]
    assert asset.width == 1080 and asset.height == 1920
    assert asset.url.endswith(".hd.mp4")
    assert asset.duration == 22.0
    assert asset.author == "Joey Farina"
    assert asset.license_note == "Pexels License"
    assert asset.watermarked is False


async def test_pexels_skips_the_hls_entry(monkeypatch):
    """The HLS entry is a playlist with null dimensions, not a file."""
    monkeypatch.setattr(settings, "PEXELS_API_KEY", "pexels-key")
    only_hls = {
        "videos": [
            {
                "id": 1,
                "duration": 5,
                "user": {"name": "N"},
                "video_files": [
                    {
                        "quality": "hls",
                        "width": None,
                        "height": None,
                        "link": "https://example.com/x.m3u8",
                    }
                ],
            }
        ]
    }
    provider = PexelsProvider()
    provider.transport = transport_for(only_hls)

    assert await provider.search("ocean", kind=VIDEO) == []


async def test_pexels_photo_requests_the_output_frame_size(monkeypatch):
    monkeypatch.setattr(settings, "PEXELS_API_KEY", "pexels-key")
    provider = PexelsProvider()
    provider.transport = transport_for(PEXELS_PHOTO_RESPONSE)

    asset = (await provider.search("trees", kind=IMAGE))[0]

    assert asset.kind == IMAGE
    assert f"w={settings.VIDEO_WIDTH}" in asset.url
    assert f"h={settings.VIDEO_HEIGHT}" in asset.url
    assert "fit=crop" in asset.url
    assert asset.author == "Lukas Rodriguez"


async def test_pexels_search_results_are_cached(monkeypatch):
    """Pexels allows 200 requests an hour; a repeat search must not spend one."""
    monkeypatch.setattr(settings, "PEXELS_API_KEY", "pexels-key")
    captured: list[httpx.Request] = []
    provider = PexelsProvider()
    provider.transport = transport_for(PEXELS_VIDEO_RESPONSE, capture=captured)

    await provider.search("ocean", kind=VIDEO)
    await provider.search("ocean", kind=VIDEO)

    assert len(captured) == 1


# --- Pixabay ------------------------------------------------------------------


async def test_pixabay_authenticates_with_a_query_parameter(monkeypatch):
    """Pixabay takes the key as `key=`, not a header."""
    monkeypatch.setattr(settings, "PIXABAY_API_KEY", "pixabay-key")
    captured: list[httpx.Request] = []
    provider = PixabayProvider()
    provider.transport = transport_for(PIXABAY_IMAGE_RESPONSE, capture=captured)

    await provider.search("flowers", kind=IMAGE)

    request = captured[0]
    assert request.url.params["key"] == "pixabay-key"
    assert "authorization" not in request.headers
    # Pixabay's vocabulary is vertical/horizontal, not portrait/landscape.
    assert request.url.params["orientation"] == "vertical"


async def test_pixabay_video_search_omits_orientation(monkeypatch):
    """The video endpoint has no orientation filter; sending one is wrong."""
    monkeypatch.setattr(settings, "PIXABAY_API_KEY", "pixabay-key")
    captured: list[httpx.Request] = []
    provider = PixabayProvider()
    provider.transport = transport_for(PIXABAY_VIDEO_RESPONSE, capture=captured)

    await provider.search("nature", kind=VIDEO)

    assert "orientation" not in captured[0].url.params


async def test_pixabay_skips_the_empty_large_stream(monkeypatch):
    """`large` is often an empty URL with size 0; `medium` always exists."""
    monkeypatch.setattr(settings, "PIXABAY_API_KEY", "pixabay-key")
    provider = PixabayProvider()
    provider.transport = transport_for(PIXABAY_VIDEO_RESPONSE)

    asset = (await provider.search("nature", kind=VIDEO))[0]

    assert asset.url == "https://cdn.pixabay.com/video/125/medium.mp4"
    assert (asset.width, asset.height) == (1920, 1080)
    assert asset.duration == 12.0


async def test_pixabay_image_prefers_the_largest_permitted_url(monkeypatch):
    """fullHDURL needs approved access; largeImageURL does not."""
    monkeypatch.setattr(settings, "PIXABAY_API_KEY", "pixabay-key")
    provider = PixabayProvider()
    provider.transport = transport_for(PIXABAY_IMAGE_RESPONSE)

    asset = (await provider.search("flowers", kind=IMAGE))[0]

    assert asset.url == "https://pixabay.com/get/195893_1280.jpg"
    assert asset.author == "Josch13"
    assert asset.author_url == "https://pixabay.com/users/Josch13-48777/"


async def test_pixabay_cache_key_excludes_the_api_key(monkeypatch):
    monkeypatch.setattr(settings, "PIXABAY_API_KEY", "secret-key-value")
    provider = PixabayProvider()
    provider.transport = transport_for(PIXABAY_IMAGE_RESPONSE)

    await provider.search("flowers", kind=IMAGE)

    assert all("secret-key-value" not in k for k in pixabay_module._cache._data)


async def test_pixabay_rate_limit_is_reported_plainly(monkeypatch):
    """Pixabay returns a plain-text body, which must not break error handling."""
    monkeypatch.setattr(settings, "PIXABAY_API_KEY", "pixabay-key")
    provider = PixabayProvider()
    provider.transport = transport_for(
        None, status=429, text_body="API rate limit exceeded"
    )

    with pytest.raises(StockError, match="rate limit"):
        await provider.search("flowers", kind=IMAGE)


async def test_pixabay_query_is_truncated_to_the_documented_limit(monkeypatch):
    monkeypatch.setattr(settings, "PIXABAY_API_KEY", "pixabay-key")
    captured: list[httpx.Request] = []
    provider = PixabayProvider()
    provider.transport = transport_for(PIXABAY_IMAGE_RESPONSE, capture=captured)

    await provider.search("word " * 60, kind=IMAGE)

    assert len(captured[0].url.params["q"]) <= 100


# --- Unsplash -----------------------------------------------------------------


async def test_unsplash_sends_client_id_and_version(monkeypatch):
    monkeypatch.setattr(settings, "UNSPLASH_ACCESS_KEY", "unsplash-key")
    captured: list[httpx.Request] = []
    provider = UnsplashProvider()
    provider.transport = transport_for(UNSPLASH_RESPONSE, capture=captured)

    await provider.search("coffee")

    request = captured[0]
    assert request.headers["authorization"] == "Client-ID unsplash-key"
    assert request.headers["accept-version"] == "v1"
    assert request.url.params["orientation"] == "portrait"


async def test_unsplash_preserves_the_ixid_when_resizing(monkeypatch):
    """The guidelines require ixid to survive URL manipulation."""
    monkeypatch.setattr(settings, "UNSPLASH_ACCESS_KEY", "unsplash-key")
    provider = UnsplashProvider()
    provider.transport = transport_for(UNSPLASH_RESPONSE)

    asset = (await provider.search("coffee"))[0]

    assert "ixid=TEST123" in asset.url
    assert f"w={settings.VIDEO_WIDTH}" in asset.url
    assert asset.author == "Jeff Sheldon"


async def test_unsplash_refuses_video_requests(monkeypatch):
    monkeypatch.setattr(settings, "UNSPLASH_ACCESS_KEY", "unsplash-key")
    provider = UnsplashProvider()

    with pytest.raises(StockError, match="no video library"):
        await provider.search("coffee", kind=VIDEO)


async def test_unsplash_reports_downloads(monkeypatch):
    """Pinging download_location on every download is mandatory."""
    monkeypatch.setattr(settings, "UNSPLASH_ACCESS_KEY", "unsplash-key")
    captured: list[httpx.Request] = []
    provider = UnsplashProvider()
    provider.transport = transport_for({"url": "ok"}, capture=captured)

    await provider.note_download(
        StockAsset(
            provider="unsplash",
            asset_id="eOLpJytrbsQ",
            kind=IMAGE,
            url="https://images.unsplash.com/x.jpg",
            download_tracking_url=(
                "https://api.unsplash.com/photos/eOLpJytrbsQ/download"
            ),
        )
    )

    assert len(captured) == 1
    assert captured[0].url.path == "/photos/eOLpJytrbsQ/download"


async def test_download_tracking_failure_does_not_raise(monkeypatch):
    """Losing a view count is not a reason to fail a render."""
    monkeypatch.setattr(settings, "UNSPLASH_ACCESS_KEY", "unsplash-key")

    def explode(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("network down")

    provider = UnsplashProvider()
    provider.transport = httpx.MockTransport(explode)

    await provider.note_download(
        StockAsset(
            provider="unsplash",
            asset_id="x",
            kind=IMAGE,
            url="https://images.unsplash.com/x.jpg",
            download_tracking_url="https://api.unsplash.com/photos/x/download",
        )
    )


# --- Shutterstock -------------------------------------------------------------


async def test_shutterstock_assets_are_flagged_as_watermarked(monkeypatch):
    """Search previews are comps; a render using one is not publishable."""
    monkeypatch.setattr(settings, "SHUTTERSTOCK_API_TOKEN", "sstk-token")

    class FakeAPI:
        async def search_videos(self, query, per_page=25):
            return {
                "data": [
                    {
                        "id": "1234",
                        "duration": 10,
                        "contributor": {"display_name": "Someone"},
                        "assets": {
                            "preview_mp4": {
                                "url": "https://ak.picdn.net/preview.mp4",
                                "width": 640,
                                "height": 360,
                            }
                        },
                    }
                ]
            }

        async def close(self):
            return None

    provider = ShutterstockProvider(api=FakeAPI())
    asset = (await provider.search("ocean", kind=VIDEO))[0]

    assert asset.watermarked is True
    assert "licence required" in asset.license_note


# --- Attribution --------------------------------------------------------------


def test_attribution_names_the_photographer_and_the_source():
    asset = StockAsset(
        provider="pexels",
        asset_id="1",
        kind=VIDEO,
        url="https://example.com/x.mp4",
        author="Joey Farina",
    )
    assert asset.attribution() == "Joey Farina / Pexels"
    assert asset.to_dict()["credit"] == "Joey Farina / Pexels"


def test_attribution_falls_back_to_the_source_alone():
    asset = StockAsset(
        provider="pixabay", asset_id="1", kind=IMAGE, url="https://x/y.jpg"
    )
    assert asset.attribution() == "Pixabay"


# --- Library ------------------------------------------------------------------


def test_library_respects_the_configured_provider_order(monkeypatch):
    monkeypatch.setattr(settings, "STOCK_PROVIDER_ORDER", "unsplash,pexels")
    names = [p.name for p in StockLibrary()._providers]
    assert names[:2] == ["unsplash", "pexels"]
    # Unlisted providers still appear, at the back.
    assert set(names) == {"pexels", "pixabay", "unsplash", "shutterstock"}


def test_library_explains_itself_when_nothing_is_configured(monkeypatch):
    for key in (
        "PEXELS_API_KEY",
        "PIXABAY_API_KEY",
        "UNSPLASH_ACCESS_KEY",
        "SHUTTERSTOCK_API_TOKEN",
    ):
        monkeypatch.setattr(settings, key, "")

    reason = StockLibrary().unavailable_reason()
    assert reason is not None
    assert "PEXELS_API_KEY" in reason


def test_library_is_ready_with_one_key(monkeypatch):
    monkeypatch.setattr(settings, "PEXELS_API_KEY", "k")
    library = StockLibrary()
    assert library.unavailable_reason() is None
    assert [p.name for p in library.available()] == ["pexels"]


async def test_library_skips_a_failing_provider(monkeypatch):
    """One dead API key must not sink the whole render."""
    monkeypatch.setattr(settings, "PEXELS_API_KEY", "k")
    monkeypatch.setattr(settings, "PIXABAY_API_KEY", "k")
    monkeypatch.setattr(settings, "STOCK_PROVIDER_ORDER", "pexels,pixabay")

    library = StockLibrary()
    pexels, pixabay = library._providers[0], library._providers[1]
    pexels.transport = transport_for(None, status=401, text_body="bad key")
    pixabay.transport = transport_for(PIXABAY_VIDEO_RESPONSE)

    assets = await library.find("nature")

    assert len(assets) == 1
    assert assets[0].provider == "pixabay"


async def test_library_excludes_already_used_assets(monkeypatch):
    monkeypatch.setattr(settings, "PEXELS_API_KEY", "k")
    monkeypatch.setattr(settings, "STOCK_PROVIDER_ORDER", "pexels")

    library = StockLibrary(providers=[PexelsProvider()])
    library._providers[0].transport = transport_for(PEXELS_VIDEO_RESPONSE)

    assert await library.find("ocean", exclude_ids={"pexels:2499611"}) == []


async def test_library_downloads_to_disk(tmp_path, monkeypatch):
    """Pixabay forbids hotlinking, so bytes must land locally."""
    monkeypatch.setattr(settings, "PEXELS_API_KEY", "k")
    payload = b"\x00\x01binary-video-bytes" * 100

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=payload)

    library = StockLibrary(
        providers=[PexelsProvider()], transport=httpx.MockTransport(handler)
    )
    asset = StockAsset(
        provider="pexels", asset_id="1", kind=VIDEO, url="https://x/clip.mp4"
    )

    destination = tmp_path / "nested" / "clip.mp4"
    await library.download(asset, destination)

    assert destination.read_bytes() == payload


async def test_library_rejects_an_empty_download(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "PEXELS_API_KEY", "k")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"")

    library = StockLibrary(
        providers=[PexelsProvider()], transport=httpx.MockTransport(handler)
    )
    asset = StockAsset(
        provider="pexels", asset_id="1", kind=VIDEO, url="https://x/clip.mp4"
    )

    with pytest.raises(StockError, match="0 bytes"):
        await library.download(asset, tmp_path / "clip.mp4")

    assert not (tmp_path / "clip.mp4").exists()


async def test_library_enforces_the_download_size_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "PEXELS_API_KEY", "k")
    monkeypatch.setattr("apps.api.services.stock.MAX_DOWNLOAD_BYTES", 1024)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * 5000)

    library = StockLibrary(
        providers=[PexelsProvider()], transport=httpx.MockTransport(handler)
    )
    asset = StockAsset(
        provider="pexels", asset_id="1", kind=VIDEO, url="https://x/huge.mp4"
    )

    with pytest.raises(StockError, match="exceeds"):
        await library.download(asset, tmp_path / "huge.mp4")

    assert not (tmp_path / "huge.mp4").exists()


# --- Cache --------------------------------------------------------------------


def test_cache_expires_entries():
    import time

    cache = cache_module.TTLCache(ttl_seconds=0)
    cache.set("k", "v")
    time.sleep(0.01)
    assert cache.get("k") is None


def test_cache_is_bounded():
    cache = cache_module.TTLCache(ttl_seconds=3600, max_entries=3)
    for i in range(10):
        cache.set(f"k{i}", i)
    assert len(cache) <= 3
