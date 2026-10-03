"""API routers.

The API previously defined every endpoint inline in ``main.py`` with no
``APIRouter`` anywhere, which is why it could not grow past stock media search.
"""

from apps.api.routers import auth, generation, projects, shutterstock, videos

__all__ = ["auth", "generation", "projects", "shutterstock", "videos"]
