"""Videoforce API application factory.

Changes from the previous version:

* ``from .app.core.config import settings`` pointed at a package that had no
  ``__init__.py`` chain, so the module could not be imported at all. Imports
  are now absolute against the ``apps.api`` package.
* Endpoints are mounted from routers instead of being declared inline.
* CORS no longer passes ``None``/duplicate origins through to Starlette.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.core.config import settings
from apps.api.routers import auth, projects, shutterstock, videos

logger = logging.getLogger("videoforce.api")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Videoforce API",
        description="AI-powered video content scheduling platform",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/healthz", tags=["system"])
    def health_check() -> dict[str, str]:
        """Liveness probe."""
        return {"status": "healthy", "service": "videoforce-api"}

    @app.get("/readyz", tags=["system"])
    def readiness_check() -> dict[str, str]:
        """Readiness probe — verifies the database is reachable."""
        from sqlalchemy import text

        from apps.api.core.db import engine

        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Readiness check failed: %s", exc)
            return {"status": "degraded", "database": "unreachable"}

        return {"status": "ready", "database": "ok"}

    app.include_router(auth.router)
    app.include_router(projects.router)
    app.include_router(videos.router)
    app.include_router(shutterstock.router)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("apps.api.main:app", host="0.0.0.0", port=8000, reload=True)
