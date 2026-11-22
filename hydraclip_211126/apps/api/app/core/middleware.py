"""HydraClip Middleware Module."""

from typing import Callable, Dict, List, Union

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to responses."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline'; img-src 'self' data:;"
        return response


class MaintenanceModeMiddleware(BaseHTTPMiddleware):
    """Block requests when maintenance mode is enabled."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        from app.config import get_settings
        from app.core.exceptions import MaintenanceModeException

        settings = get_settings()
        if settings.maintenance_mode and not request.url.path.startswith("/api/admin"):
            # Allow health checks and admin
            if not (request.url.path == "/health" or request.url.path == "/ready" or request.url.path.startswith("/api/admin")):
                raise MaintenanceModeException("Service is under maintenance")

        response = await call_next(request)
        return response


def add_middleware(app, middleware_list: list) -> None:
    """Add middleware to FastAPI app."""
    for middleware in middleware_list:
        app.add_middleware(middleware)


def get_middleware_stack() -> list:
    """Get list of middleware to add."""
    return [
        SecurityHeadersMiddleware,
    ]
def add_cors_middleware(app) -> None:
    """Add CORS middleware using origins from settings."""
    from fastapi.middleware.cors import CORSMiddleware
    try:
        from app.config import get_cors_origins
        origins = get_cors_origins()
    except Exception:
        origins = ["http://localhost:3000", "http://localhost:8000"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        # Allow any localhost/127.0.0.1 port for local development
        # (Next.js may pick 3000-3023 depending on what is already running).
        allow_origin_regex=r"^http://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        max_age=600,
    )

def add_security_headers(app) -> None:
    """Add security headers middleware."""
    app.add_middleware(SecurityHeadersMiddleware)

def add_rate_limit_headers(app) -> None:
    """No-op for now - rate limiting is handled in rate_limiter.py."""
    return None
