"""HydraClip FastAPI Application."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import get_settings, validate_settings, get_cors_origins
from app.core.database import init_db, close_db
from app.core.exceptions import HydraClipException
from app.core.middleware import add_cors_middleware, add_security_headers, add_rate_limit_headers
from app.core.rate_limiter import rate_limit_auth, rate_limit_general, rate_limit_generation
from app.core.security import verify_token
from app.core.encryption import decrypt_token
from app.core.database import get_db
from app.core.exceptions import MaintenanceModeError

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -&gt; AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown."""
    print("Starting HydraClip API...")
    await init_db()
    print("✓ Database connected")
    yield
    print("Shutting down HydraClip API...")
    await close_db()
    print("✓ Database connections closed")


app = FastAPI(
    title="HydraClip API",
    description="AI Video Generation & Publishing Platform",
    version="1.0.0",
    lifespan=lifespan,
)


# Middleware
add_cors_middleware(app)
add_security_headers(app)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", ".hydraclip.com"])
app.add_middleware(
    lambda: None,  # placeholder
)


# Custom exception handler
@app.exception_handler(HydraClipException)
async def hydraclip_exception_handler(request, exc: HydraClipException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": exc.detail},
    )


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "hydraclip-api", "timestamp": "2024-01-01T00:00:00Z"}


@app.get("/ready")
async def readiness_check():
    """Readiness check endpoint."""
    return {"status": "ready", "service": "hydraclip-api"}


# Auth routes
from app.routers import auth, users, projects, videos, schedules, publishing, oauth, billing, webhooks, templates, admin, health

app.include_router(auth.router, prefix="/api/auth")
app.include_router(users.router, prefix="/api/users")
app.include_router(projects.router, prefix="/api/projects")
app.include_router(videos.router, prefix="/api/videos")
app.include_router(schedules.router, prefix="/api/schedules")
app.include_router(publishing.router, prefix="/api/publishing")
app.include_router(oauth.router, prefix="/api/oauth")
app.include_router(billing.router, prefix="/api/billing")
app.include_router(webhooks.router, prefix="/api/webhooks")
app.include_router(templates.router, prefix="/api/templates")
app.include_router(admin.router, prefix="/api/admin")
app.include_router(health.router, prefix="/api")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
