import httpx
from apps.api.app.core.config import settings


class ShutterstockAPI:
    """Shutterstock API client for stock media search and licensing."""

    def __init__(self, api_token: str = None):
        self.api_token = api_token or settings.SHUTTERSTOCK_API_TOKEN
        self.base_url = "https://api.shutterstock.com/v2"
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    async def search_images(self, query: str, page: int = 1, per_page: int = 25, 
                           orientation: str = "portrait", license_type: str = "rm") -> dict:
        """Search for stock images.
        
        Args:
            query: Search query text
            page: Page number (1-indexed)
            per_page: Results per page (max 25)
            orientation: portrait, landscape, square
            license_type: rm (royalty-free managed), rf (royalty-free)
        
        Returns:
            Parsed response with image results
        """
        params = {
            "query": query,
            "page": page,
            "per_page": per_page,
            "orientation": orientation,
            "license_type": license_type,
        }
        response = await self.client.get("/images/search", params=params)
        response.raise_for_status()
        return response.json()

    async def search_videos(self, query: str, page: int = 1, per_page: int = 25,
                           license_type: str = "rm") -> dict:
        """Search for stock videos.
        
        Args:
            query: Search query text
            page: Page number (1-indexed)
            per_page: Results per page (max 25)
            license_type: rm (royalty-free managed), rf (royalty-free)
        
        Returns:
            Parsed response with video results
        """
        params = {
            "query": query,
            "page": page,
            "per_page": per_page,
            "license_type": license_type,
        }
        response = await self.client.get("/videos/search", params=params)
        response.raise_for_status()
        return response.json()

    async def search_audio(self, query: str, page: int = 1, per_page: int = 25,
                           license_type: str = "rm") -> dict:
        """Search for stock audio.
        
        Args:
            query: Search query text
            page: Page number (1-indexed)
            per_page: Results per page (max 25)
            license_type: rm (royalty-free managed), rf (royalty-free)
        
        Returns:
            Parsed response with audio results
        """
        params = {
            "query": query,
            "page": page,
            "per_page": per_page,
            "license_type": license_type,
        }
        response = await self.client.get("/audio/search", params=params)
        response.raise_for_status()
        return response.json()

    async def get_image_by_id(self, image_id: int) -> dict:
        """Get image details by ID.
        
        Args:
            image_id: Shutterstock image ID
        
        Returns:
            Parsed response with image details
        """
        response = await self.client.get(f"/images/{image_id}")
        response.raise_for_status()
        return response.json()

    async def get_video_by_id(self, video_id: int) -> dict:
        """Get video details by ID.
        
        Args:
            video_id: Shutterstock video ID
        
        Returns:
            Parsed response with video details
        """
        response = await self.client.get(f"/videos/{video_id}")
        response.raise_for_status()
        return response.json()

    async def get_licensing_options(self, media_id: int, media_type: str = "image") -> dict:
        """Get licensing options for a media item.
        
        Args:
            media_id: Shutterstock media ID
            media_type: image or video
        
        Returns:
            Parsed response with licensing options and pricing
        """
        if media_type == "image":
            response = await self.client.get(f"/images/{media_id}/licensing")
        else:
            response = await self.client.get(f"/videos/{media_id}/licensing")
        response.raise_for_status()
        return response.json()

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


# Create a singleton instance (lazy initialization)
_shutterstock_instance = None


def get_shutterstock_api() -> ShutterstockAPI:
    """Get or create the Shutterstock API instance."""
    global _shutterstock_instance
    if _shutterstock_instance is None:
        _shutterstock_instance = ShutterstockAPI()
    return _shutterstock_instance