"""Database engine, session factory and the FastAPI session dependency.

None of this existed before: `seed.py` built its own engine inline and the API
had no way to talk to Postgres at all.
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from apps.api.core.config import settings
from apps.api.models import Base

__all__ = ["Base", "engine", "SessionLocal", "get_db", "create_all"]


def _build_engine() -> Engine:
    url = settings.DATABASE_URL

    # SQLite (used by the test suite) needs a different connect config and
    # does not support pool pre-ping semantics in the same way.
    if url.startswith("sqlite"):
        from sqlalchemy.pool import StaticPool

        return create_engine(
            url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool if ":memory:" in url else None,
            future=True,
        )

    return create_engine(url, pool_pre_ping=True, pool_recycle=1800, future=True)


engine = _build_engine()

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


def get_db() -> Generator[Session, None, None]:
    """Yield a request-scoped session and always close it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all() -> None:
    """Create every table directly from the models.

    Intended for tests and local throwaway databases. Real environments should
    go through Alembic (`alembic upgrade head`).
    """
    # Importing the model modules registers them on Base.metadata.
    import apps.api.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
