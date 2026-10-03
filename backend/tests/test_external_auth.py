"""Supabase email and Google OIDC login tests."""

from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest

from apps.api.core.config import settings
from apps.api.services import external_auth
from apps.api.services.crypto import seal_state


@pytest.mark.asyncio
async def test_supabase_password_login_uses_password_grant(monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setattr(settings, "SUPABASE_ANON_KEY", "publishable-key")
    seen: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"access_token": "supabase-access"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        result = await external_auth.supabase_password_login(
            "USER@EXAMPLE.COM", "secret", client=client
        )

    assert result["access_token"] == "supabase-access"
    assert seen[0].url.path == "/auth/v1/token"
    assert seen[0].url.params["grant_type"] == "password"
    assert seen[0].headers["apikey"] == "publishable-key"


@pytest.mark.asyncio
async def test_supabase_user_maps_verified_identity(monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setattr(settings, "SUPABASE_ANON_KEY", "publishable-key")

    def respond(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer session-token"
        return httpx.Response(
            200,
            json={
                "id": "subject",
                "email": "Person@Example.com",
                "email_confirmed_at": "2026-10-02T00:00:00Z",
                "user_metadata": {"full_name": "Person"},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        profile = await external_auth.supabase_user("session-token", client=client)

    assert profile.email == "person@example.com"
    assert profile.name == "Person"
    assert profile.email_verified is True


def test_google_authorize_reuses_youtube_client(monkeypatch):
    monkeypatch.setattr(settings, "YOUTUBE_CLIENT_ID", "youtube-client")
    monkeypatch.setattr(settings, "YOUTUBE_CLIENT_SECRET", "youtube-secret")
    monkeypatch.setattr(
        settings, "GOOGLE_LOGIN_REDIRECT_URI", "http://localhost:8000/auth/google/callback"
    )

    url = httpx.URL(external_auth.google_authorize_url())

    assert url.host == "accounts.google.com"
    assert url.params["client_id"] == "youtube-client"
    assert url.params["scope"] == "openid email profile"
    assert url.params["redirect_uri"].endswith("/auth/google/callback")
    assert url.params["state"]


@pytest.mark.asyncio
async def test_google_identity_exchanges_code_and_reads_userinfo(monkeypatch):
    monkeypatch.setattr(settings, "YOUTUBE_CLIENT_ID", "youtube-client")
    monkeypatch.setattr(settings, "YOUTUBE_CLIENT_SECRET", "youtube-secret")
    monkeypatch.setattr(
        settings, "GOOGLE_LOGIN_REDIRECT_URI", "http://localhost:8000/auth/google/callback"
    )
    state = seal_state({"purpose": "google_login", "nonce": "n"})

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "google-access"})
        assert request.headers["authorization"] == "Bearer google-access"
        return httpx.Response(
            200,
            json={
                "sub": "google-subject",
                "email": "google@example.com",
                "email_verified": True,
                "name": "Google User",
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        profile = await external_auth.google_identity("code", state, client=client)

    assert profile.email == "google@example.com"
    assert profile.name == "Google User"


@pytest.mark.asyncio
async def test_supabase_login_endpoint_issues_local_tokens(client, monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setattr(settings, "SUPABASE_ANON_KEY", "publishable-key")
    monkeypatch.setattr(
        external_auth,
        "supabase_password_login",
        AsyncMock(return_value={"access_token": "verified-session"}),
    )
    monkeypatch.setattr(
        external_auth,
        "supabase_user",
        AsyncMock(
            return_value=external_auth.IdentityProfile(
                email="supabase@example.com", name="Supa", email_verified=True
            )
        ),
    )

    response = client.post(
        "/auth/supabase/login",
        json={"email": "supabase@example.com", "password": "valid-password"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["authenticated"] is True
    assert body["tokens"]["access_token"]
    assert body["tokens"]["user"]["email"] == "supabase@example.com"


def test_external_login_cannot_reactivate_a_deactivated_user(db, make_user):
    make_user(email="disabled@example.com", is_active=False)

    with pytest.raises(external_auth.ExternalAuthError, match="deactivated"):
        external_auth.sync_local_user(
            db,
            external_auth.IdentityProfile(
                email="disabled@example.com", email_verified=True
            ),
        )


def test_auth_provider_probe_does_not_expose_credentials(client, monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setattr(settings, "SUPABASE_ANON_KEY", "do-not-return")
    monkeypatch.setattr(settings, "YOUTUBE_CLIENT_ID", "client-id")
    monkeypatch.setattr(settings, "YOUTUBE_CLIENT_SECRET", "do-not-return")

    response = client.get("/auth/providers")

    assert response.status_code == 200
    assert response.json()["supabase_email"] is True
    assert response.json()["google"] is True
    assert "do-not-return" not in response.text
