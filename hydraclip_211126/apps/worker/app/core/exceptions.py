"""HydraClip Exception Module."""

from typing import Optional


class HydraClipException(Exception):
    """Base exception for HydraClip application."""
    
    def __init__(self, detail: str, status_code: int = 500):
        self.detail = detail
        self.status_code = status_code
        super().__init__(self.detail)


class NotFoundException(HydraClipException):
    """Resource not found exception."""
    
    def __init__(self, resource: str, id: Optional[str] = None):
        if id:
            detail = f"{resource} with id '{id}' not found"
        else:
            detail = f"{resource} not found"
        super().__init__(detail, status_code=404)


class ValidationException(HydraClipException):
    """Validation exception."""
    
    def __init__(self, detail: str):
        super().__init__(detail, status_code=422)


class UnauthorizedException(HydraClipException):
    """Unauthorized access exception."""
    
    def __init__(self, detail: str = "Unauthorized"):
        super().__init__(detail, status_code=401)


class ForbiddenException(HydraClipException):
    """Forbidden access exception."""
    
    def __init__(self, detail: str = "Forbidden"):
        super().__init__(detail, status_code=403)


class ConflictException(HydraClipException):
    """Conflict exception (e.g., duplicate resource)."""
    
    def __init__(self, detail: str):
        super().__init__(detail, status_code=409)


class RateLimitException(HydraClipException):
    """Rate limit exceeded exception."""
    
    def __init__(self, retry_after: int = 60):
        self.retry_after = retry_after
        super().__init__(
            f"Rate limit exceeded. Please try again in {retry_after} seconds.",
            status_code=429,
        )


class MaintenanceModeException(HydraClipException):
    """Maintenance mode exception."""
    
    def __init__(self, detail: str = "Service is under maintenance"):
        super().__init__(detail, status_code=503)