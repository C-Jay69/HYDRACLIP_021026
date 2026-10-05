"""Password reset flow: request, consume, single-use enforcement."""

from __future__ import annotations

import pytest

from apps.api.routers.passwords import password_reset_limiter
from apps.api.services import password_reset as reset_service
from tests.conftest import VALID_PASSWORD

NEW_PASSWORD = "brand-new-passphrase-42"


@pytest.fixture(autouse=True)
def _quiet_email(monkeypatch):
    """Never touch SMTP; the token comes back from ``request_reset`` directly."""
    monkeypatch.setattr(reset_service, "send_reset_email", lambda email, token: None)
    # Generous limiter: individual tests that exercise the limiter patch it lower.
    monkeypatch.setattr(password_reset_limiter, "max_attempts", 1000)


class TestForgotPassword:
    def test_known_and_unknown_addresses_get_the_same_answer(self, client, make_user):
        make_user(email="known@example.com")

        known = client.post(
            "/auth/forgot-password", json={"email": "known@example.com"}
        )
        unknown = client.post(
            "/auth/forgot-password", json={"email": "nobody@example.com"}
        )

        assert known.status_code == unknown.status_code == 200
        assert known.json() == unknown.json()

    def test_is_rate_limited(self, client, make_user, monkeypatch):
        make_user(email="flood@example.com")
        monkeypatch.setattr(password_reset_limiter, "max_attempts", 3)

        codes = [
            client.post(
                "/auth/forgot-password", json={"email": "flood@example.com"}
            ).status_code
            for _ in range(5)
        ]

        assert codes[-1] == 429
        assert codes[:3] == [200, 200, 200]


class TestResetFlow:
    def test_full_flow_changes_the_password(self, client, db, make_user):
        make_user(email="resetter@example.com")

        token = reset_service.request_reset(db, "resetter@example.com")
        assert token

        response = client.post(
            "/auth/reset-password",
            json={"token": token, "new_password": NEW_PASSWORD},
        )
        assert response.status_code == 200

        old_login = client.post(
            "/auth/login",
            json={"email": "resetter@example.com", "password": VALID_PASSWORD},
        )
        new_login = client.post(
            "/auth/login",
            json={"email": "resetter@example.com", "password": NEW_PASSWORD},
        )
        assert old_login.status_code == 401
        assert new_login.status_code == 200

    def test_a_token_cannot_be_replayed(self, client, db, make_user):
        make_user(email="once@example.com")
        token = reset_service.request_reset(db, "once@example.com")

        first = client.post(
            "/auth/reset-password",
            json={"token": token, "new_password": NEW_PASSWORD},
        )
        second = client.post(
            "/auth/reset-password",
            json={"token": token, "new_password": NEW_PASSWORD},
        )

        assert first.status_code == 200
        assert second.status_code == 400

    def test_a_weak_new_password_is_rejected(self, client, db, make_user):
        make_user(email="weak@example.com")
        token = reset_service.request_reset(db, "weak@example.com")

        response = client.post(
            "/auth/reset-password",
            json={"token": token, "new_password": "short"},
        )
        assert response.status_code == 422

    def test_an_invalid_token_is_rejected(self, client):
        response = client.post(
            "/auth/reset-password",
            json={"token": "not-a-jwt", "new_password": NEW_PASSWORD},
        )
        assert response.status_code == 400
