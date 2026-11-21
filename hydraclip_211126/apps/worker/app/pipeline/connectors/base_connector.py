"""Base Platform Connector Interface."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class BasePlatformConnector(ABC):
    """Base platform connector interface."""
    
    @abstractmethod
    async def connect(self, user_id: str, **kwargs) -> Dict[str, Any]:
        """Connect to platform."""
        pass
    
    @abstractmethod
    async def disconnect(self, user_id: str) -> bool:
        """Disconnect from platform."""
        pass
    
    @abstractmethod
    async def validate_connection(self, user_id: str) -> bool:
        """Validate connection."""
        pass
    
    @abstractmethod
    async def refresh_token(self, user_id: str) -> bool:
        """Refresh access token."""
        pass
    
    @abstractmethod
    async def prepare_upload_payload(self, video: Any, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare upload payload."""
        pass
    
    @abstractmethod
    async def upload_media(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Upload media."""
        pass
    
    @abstractmethod
    async def publish(self, upload_id: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Publish media."""
        pass
    
    @abstractmethod
    async def get_publish_status(self, post_id: str) -> Dict[str, Any]:
        """Get publish status."""
        pass
    
    @abstractmethod
    async def get_fallback_export(self, video: Any, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Get fallback export."""
        pass