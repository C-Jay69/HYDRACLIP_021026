"""HydraClip API application factory.

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
from apps.api.routers import (
    admin,
    auth,
    billing,
    generation,
    oauth,
    passwords,
    projects,
    schedules,
    shutterstock,
    videos,
)

logger = logging.getLogger("hydraclip.api")


def create_app() -> FastAPI:
    app = FastAPI(
        title="HydraClip API",
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
        return {"status": "healthy", "service": "hydraclip-api"}

    @app.get("/readyz", tags=["system"])
    def readiness_check() -> dict[str, object]:
        """Readiness probe — verifies the database and the job queue."""
        from sqlalchemy import text

        from apps.api.core.db import engine
        from apps.api.services.task_queue import queue_health

        database = "ok"
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Readiness check failed: %s", exc)
            database = "unreachable"

        queue = queue_health()
        healthy = database == "ok" and queue.get("ok", False)

        return {
            "status": "ready" if healthy else "degraded",
            "database": database,
            "queue": queue,
        }

    app.include_router(auth.router)
    app.include_router(projects.router)
    app.include_router(videos.router)
    app.include_router(generation.router)
    app.include_router(shutterstock.router)
    app.include_router(oauth.router)
    app.include_router(schedules.router)
    app.include_router(passwords.router)
    app.include_router(billing.router)
    app.include_router(admin.router)

    # Chooses between the in-process runner and Celery. Done at app creation
    # so the choice (and the warning for "inline") is visible in the logs at
    # boot rather than on the first generation request.
    from apps.api.services.task_queue import configure_job_runner

    configure_job_runner()

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("apps.api.main:app", host="0.0.0.0", port=8000, reload=True)
