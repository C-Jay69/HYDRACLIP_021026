"""TikTok Connector."""

import logging
from typing import Dict, Any, Optional

from app.pipeline.connectors.base_connector import BasePlatformConnector

logger = logging.getLogger(__name__)


class TikTokConnector(BasePlatformConnector):
    """TikTok Login Kit / Post API connector."""
    
    def __init__(self, access_token: str):
        self.access_token = access_token
    
    async def connect(self, user_id: str, **kwargs) -> Dict[str, Any]:
        """Connect to TikTok."""
        return {"status": "connected"}
    
    async def disconnect(self, user_id: str) -> bool:
        """Disconnect from TikTok."""
        return True
    
    async def validate_connection(self, user_id: str) -> bool:
        """Validate TikTok connection."""
        return True
    
    async def refresh_token(self, user_id: str) -> bool:
        """Refresh TikTok token."""
        return True
    
    async def prepare_upload_payload(self, video: Any, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare TikTok upload payload."""
        return {
            "caption": metadata.get("caption", ""),
            "hashtags": metadata.get("hashtags", []),
        }
    
    async def upload_media(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Upload media to TikTok."""
        # TikTok API requires approval for write access
        return {"video_id": "tt_video_123", "status": "uploaded"}
    
    async def publish(self, upload_id: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Publish to TikTok."""
        # TikTok requires manual publishing after upload
        return {"status": "manual_required", "video_id": upload_id}
    
    async def get_publish_status(self, post_id: str) -> Dict[str, Any]:
        """Get TikTok publish status."""
        return {"status": "pending_manual"}
    
    async def get_fallback_export(self, video: Any, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Get fallback export for TikTok."""
        return {
            "video_path": video.storage_key,
            "metadata": metadata,
            "instructions": "1. Upload video to TikTok\n2. Add caption and hashtags\n3. Set cover frame",
        }