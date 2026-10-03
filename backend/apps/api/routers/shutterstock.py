"""Shutterstock stock media endpoints.

Moved verbatim (behaviour-wise) out of ``main.py`` into a router. The repeated
try/except blocks are collapsed into one helper.
"""

from __future__ import annotations

from collections.abc import Awaitable
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Query, status

from apps.api.services.shutterstock import ShutterstockAPI, get_shutterstock_api

router = APIRouter(prefix="/shutterstock", tags=["stock-media"])

ApiDep = Depends(get_shutterstock_api)


async def _call(operation: Callable[[], Awaitable[dict[str, Any]]]) -> dict[str, Any]:
    """Run an upstream call, mapping failures to 502."""
    try:
        return await operation()
    except Exception as exc:  # noqa: BLE001 - upstream client raises broadly
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Shutterstock API error: {exc}",
        ) from exc


@router.get("/images/search")
async def search_images(
    query: str = Query(min_length=1),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=25),
    orientation: str = "portrait",
    license_type: str = "rm",
    api: ShutterstockAPI = ApiDep,
) -> dict[str, Any]:
    """Search stock images."""
    return await _call(
        lambda: api.search_images(
            query=query,
            page=page,
            per_page=per_page,
            orientation=orientation,
            license_type=license_type,
        )
    )


@router.get("/videos/search")
async def search_videos(
    query: str = Query(min_length=1),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=25),
    license_type: str = "rm",
    api: ShutterstockAPI = ApiDep,
) -> dict[str, Any]:
    """Search stock video."""
    return await _call(
        lambda: api.search_videos(
            query=query, page=page, per_page=per_page, license_type=license_type
        )
    )


@router.get("/audio/search")
async def search_audio(
    query: str = Query(min_length=1),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=25),
    license_type: str = "rm",
    api: ShutterstockAPI = ApiDep,
) -> dict[str, Any]:
    """Search stock audio."""
    return await _call(
        lambda: api.search_audio(
            query=query, page=page, per_page=per_page, license_type=license_type
        )
    )


@router.get("/images/{image_id}")
async def get_image(image_id: int, api: ShutterstockAPI = ApiDep) -> dict[str, Any]:
    return await _call(lambda: api.get_image_by_id(image_id=image_id))


@router.get("/videos/{video_id}")
async def get_video(video_id: int, api: ShutterstockAPI = ApiDep) -> dict[str, Any]:
    return await _call(lambda: api.get_video_by_id(video_id=video_id))


@router.get("/licensing/{media_id}")
async def get_licensing(
    media_id: int,
    media_type: str = "image",
    api: ShutterstockAPI = ApiDep,
) -> dict[str, Any]:
    return await _call(
        lambda: api.get_licensing_options(media_id=media_id, media_type=media_type)
    )
