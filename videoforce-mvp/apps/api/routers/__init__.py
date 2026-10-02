"""API routers.

The API previously defined every endpoint inline in ``main.py`` with no
``APIRouter`` anywhere, which is why it could not grow past stock media search.
"""

from apps.api.routers import auth, shutterstock

__all__ = ["auth", "shutterstock"]
