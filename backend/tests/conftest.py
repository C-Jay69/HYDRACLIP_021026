"""Shared test fixtures.

The environment is configured *before* any ``apps.api`` import, because
``core/config.py`` builds its Settings singleton and ``core/db.py`` builds the
engine at module import time.
"""

from __future__ import annotations

import os

# Must precede the apps.api imports below.
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key-not-used-anywhere-real"
os.environ["ACCESS_TOKEN_EXPIRES_IN"] = "3600"
os.environ["REFRESH_TOKEN_EXPIRES_IN"] = "86400"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from apps.api.core.db import Base, SessionLocal, engine  # noqa: E402
from apps.api.main import app  # noqa: E402
from apps.api.models import User  # noqa: E402
from apps.api.services.auth import hash_password  # noqa: E402
from apps.api.services.rate_limit import login_rate_limiter  # noqa: E402

VALID_PASSWORD = "correct-horse-battery-staple"


@pytest.fixture(autouse=True)
def _fresh_database():
    """Recreate every table before each test and clear rate-limit state."""
    import apps.api.models  # noqa: F401  (registers the models on Base)

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    login_rate_limiter.clear()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def make_user(db):
    """Factory for persisted users."""

    def _make(
        email: str = "user@example.com",
        password: str = VALID_PASSWORD,
        role: str = "USER",
        is_active: bool = True,
    ) -> User:
        user = User(
            email=email.lower(),
            password_hash=hash_password(password),
            name="Test User",
            role=role,
            is_active=is_active,
            is_verified=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    return _make


@pytest.fixture
def auth_headers(client, make_user):
    """Create a user and return Authorization headers for them."""

    def _headers(email: str = "user@example.com", role: str = "USER") -> dict[str, str]:
        make_user(email=email, role=role)
        response = client.post(
            "/auth/login", json={"email": email, "password": VALID_PASSWORD}
        )
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    return _headers
