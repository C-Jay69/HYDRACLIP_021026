from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional, Dict, Any
import os

from .app.core.config import settings
from .services.shutterstock import get_shutterstock_api, ShutterstockAPI

# Create FastAPI app
app = FastAPI(
    title="Videoforce API",
    description="AI-powered video content scheduling platform",
    version="0.1.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.APP_URL, settings.NEXT_PUBLIC_APP_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint
@app.get("/healthz")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "videoforce-api"}


# Shutterstock API endpoints
@app.get("/shutterstock/images/search", response_model=Dict[str, Any])
async def search_shutterstock_images(
    query: str,
    page: int = 1,
    per_page: int = 25,
    orientation: str = "portrait",
    license_type: str = "rm",
    ssh_api: ShutterstockAPI = Depends(get_shutterstock_api),
):
    """Search for stock images on Shutterstock.
    
    Args:
        query: Search query text
        page: Page number (1-indexed)
        per_page: Results per page (max 25)
        orientation: portrait, landscape, square
        license_type: rm (royalty-free managed), rf (royalty-free)
    
    Returns:
        Shutterstock search results with image metadata
    """
    try:
        results = await ssh_api.search_images(
            query=query,
            page=page,
            per_page=per_page,
            orientation=orientation,
            license_type=license_type,
        )
        return results
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Shutterstock API error: {str(e)}",
        )


@app.get("/shutterstock/videos/search", response_model=Dict[str, Any])
async def search_shutterstock_videos(
    query: str,
    page: int = 1,
    per_page: int = 25,
    license_type: str = "rm",
    ssh_api: ShutterstockAPI = Depends(get_shutterstock_api),
):
    """Search for stock videos on Shutterstock.
    
    Args:
        query: Search query text
        page: Page number (1-indexed)
        per_page: Results per page (max 25)
        license_type: rm (royalty-free managed), rf (royalty-free)
    
    Returns:
        Shutterstock search results with video metadata
    """
    try:
        results = await ssh_api.search_videos(
            query=query,
            page=page,
            per_page=per_page,
            license_type=license_type,
        )
        return results
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Shutterstock API error: {str(e)}",
        )


@app.get("/shutterstock/audio/search", response_model=Dict[str, Any])
async def search_shutterstock_audio(
    query: str,
    page: int = 1,
    per_page: int = 25,
    license_type: str = "rm",
    ssh_api: ShutterstockAPI = Depends(get_shutterstock_api),
):
    """Search for stock audio on Shutterstock.
    
    Args:
        query: Search query text
        page: Page number (1-indexed)
        per_page: Results per page (max 25)
        license_type: rm (royalty-free managed), rf (royalty-free)
    
    Returns:
        Shutterstock search results with audio metadata
    """
    try:
        results = await ssh_api.search_audio(
            query=query,
            page=page,
            per_page=per_page,
            license_type=license_type,
        )
        return results
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Shutterstock API error: {str(e)}",
        )


@app.get("/shutterstock/images/{image_id}", response_model=Dict[str, Any])
async def get_shutterstock_image(
    image_id: int,
    ssh_api: ShutterstockAPI = Depends(get_shutterstock_api),
):
    """Get image details by ID from Shutterstock.
    
    Args:
        image_id: Shutterstock image ID
    
    Returns:
        Image details including licensing options
    """
    try:
        result = await ssh_api.get_image_by_id(image_id=image_id)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Shutterstock API error: {str(e)}",
        )


@app.get("/shutterstock/videos/{video_id}", response_model=Dict[str, Any])
async def get_shutterstock_video(
    video_id: int,
    ssh_api: ShutterstockAPI = Depends(get_shutterstock_api),
):
    """Get video details by ID from Shutterstock.
    
    Args:
        video_id: Shutterstock video ID
    
    Returns:
        Video details including licensing options
    """
    try:
        result = await ssh_api.get_video_by_id(video_id=video_id)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Shutterstock API error: {str(e)}",
        )


@app.get("/shutterstock/licensing/{media_id}", response_model=Dict[str, Any])
async def get_shutterstock_licensing(
    media_id: int,
    media_type: str = "image",
    ssh_api: ShutterstockAPI = Depends(get_shutterstock_api),
):
    """Get licensing options for a Shutterstock media item.
    
    Args:
        media_id: Shutterstock media ID
        media_type: image or video
    
    Returns:
        Licensing options with pricing
    """
    try:
        result = await ssh_api.get_licensing_options(
            media_id=media_id,
            media_type=media_type,
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Shutterstock API error: {str(e)}",
        )


# Include additional routers would go here
# from apps.api.routes import ...
# app.include_router(...)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)