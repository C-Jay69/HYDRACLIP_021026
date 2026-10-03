"""The authorisation-code flow, end to end against mocked providers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from apps.api.core.config import settings
from apps.api.models import User
from apps.api.models.system import SocialAccount
from apps.api.services import oauth as oauth_service
from apps.api.services.crypto import decrypt_token, seal_state, unseal_state
from apps.api.services.oauth import OAuthStateError
from apps.api.services.platforms import PlatformNotConfigured, TokenSet, get_platform


@pytest.fixture
def configured(monkeypatch):
    for name in ("YOUTUBE", "INSTAGRAM", "TIKTOK", "X"):
        monkeypatch.setattr(settings, f"{name}_CLIENT_ID", f"{name.lower()}-id")
        monkeypatch.setattr(settings, f"{name}_CLIENT_SECRET", "secret")
        monkeypatch.setattr(
            settings,
            f"{name}_REDIRECT_URI",
            f"https://app.example.com/oauth/{name.lower()}/callback",
        )


@pytest.fixture
def owner(client, db, auth_headers):
    headers = auth_headers(email="owner@example.com")
    user = db.query(User).filter(User.email == "owner@example.com").one()
    return user, headers


@pytest.fixture
def no_app_url(monkeypatch):
    """Blank APP_URL so the callback returns JSON instead of redirecting."""
    monkeypatch.setattr(settings, "APP_URL", "")


def callback(client, platform: str, **params):
    """Call a callback without following the redirect it normally issues."""
    return client.get(
        f"/oauth/{platform}/callback", params=params, follow_redirects=False
    )


def redirect_params(response):
    return parse_qs(urlparse(response.headers["location"]).query)


def stub_exchange(monkeypatch, platform: str, **token_kwargs):
    """Replace a provider's code exchange with a canned token."""
    captured = {}

    async def _exchange(code, code_verifier=None):
        captured["code"] = code
        captured["verifier"] = code_verifier
        defaults = dict(
            access_token="access-1",
            refresh_token="refresh-1",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            scope="s",
            account_id="acct-1",
            account_name="Connected",
        )
        defaults.update(token_kwargs)
        return TokenSet(**defaults)

    monkeypatch.setattr(get_platform(platform), "exchange_code", _exchange)
    return captured


class TestStartAuthorization:
    def test_state_binds_the_flow_to_the_user(self, configured):
        _url, state = oauth_service.start_authorization(user_id=42, platform="youtube")
        payload = unseal_state(state, 600)
        assert payload["user_id"] == 42
        assert payload["platform"] == "youtube"

    def test_pkce_verifier_is_generated_only_where_required(self, configured):
        _u, yt_state = oauth_service.start_authorization(1, "youtube")
        _u, x_state = oauth_service.start_authorization(1, "x")
        assert unseal_state(yt_state, 600)["verifier"] is None
        assert unseal_state(x_state, 600)["verifier"] is not None

    def test_the_challenge_in_the_url_matches_the_sealed_verifier(self, configured):
        import base64
        import hashlib

        url, state = oauth_service.start_authorization(1, "x")
        verifier = unseal_state(state, 600)["verifier"]
        expected = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .decode()
            .rstrip("=")
        )
        assert parse_qs(urlparse(url).query)["code_challenge"] == [expected]

    def test_each_attempt_gets_a_distinct_state(self, configured):
        _, first = oauth_service.start_authorization(1, "youtube")
        _, second = oauth_service.start_authorization(1, "youtube")
        assert first != second

    def test_unconfigured_platform_is_refused(self):
        with pytest.raises(PlatformNotConfigured):
            oauth_service.start_authorization(1, "youtube")


class TestReadState:
    def test_rejects_a_missing_state(self):
        with pytest.raises(OAuthStateError, match="did not return a state"):
            oauth_service.read_state("", "youtube")

    def test_rejects_a_state_minted_for_another_platform(self):
        """A state issued for YouTube must not be redeemable at TikTok's
        callback."""
        state = seal_state({"user_id": 1, "platform": "youtube"})
        with pytest.raises(OAuthStateError, match="does not match"):
            oauth_service.read_state(state, "tiktok")

    def test_rejects_a_state_without_a_user(self):
        state = seal_state({"platform": "youtube"})
        with pytest.raises(OAuthStateError, match="no user"):
            oauth_service.read_state(state, "youtube")

    def test_rejects_a_forged_state(self):
        with pytest.raises(OAuthStateError):
            oauth_service.read_state("forged", "youtube")


class TestAuthorizeEndpoint:
    def test_requires_authentication(self, client):
        assert client.get("/oauth/youtube/authorize").status_code == 401

    def test_returns_the_provider_url(self, client, owner, configured):
        _user, headers = owner
        response = client.get("/oauth/youtube/authorize", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["platform"] == "youtube"
        assert body["authorize_url"].startswith(
            "https://accounts.google.com/o/oauth2/v2/auth?"
        )

    def test_unknown_platform_is_404(self, client, owner, configured):
        _user, headers = owner
        assert client.get("/oauth/myspace/authorize", headers=headers).status_code == 404

    def test_unconfigured_platform_is_503(self, client, owner):
        _user, headers = owner
        response = client.get("/oauth/youtube/authorize", headers=headers)
        assert response.status_code == 503
        assert "YOUTUBE_CLIENT_ID" in response.json()["detail"]


class TestCallbackEndpoint:
    def test_a_successful_callback_stores_the_account(
        self, client, db, owner, configured, monkeypatch
    ):
        user, _headers = owner
        captured = stub_exchange(monkeypatch, "youtube")
        _url, state = oauth_service.start_authorization(user.id, "youtube")

        response = callback(client, "youtube", code="the-code", state=state)
        assert response.status_code == 303
        assert redirect_params(response)["status"] == ["connected"]
        assert captured["code"] == "the-code"

        account = db.query(SocialAccount).filter(SocialAccount.user_id == user.id).one()
        assert account.platform == "youtube"
        assert decrypt_token(account.access_token_encrypted) == "access-1"

    def test_the_callback_needs_no_bearer_token(
        self, client, owner, configured, monkeypatch
    ):
        """The browser arrives from the provider with no Authorization
        header; the sealed state is what identifies the user."""
        user, _headers = owner
        stub_exchange(monkeypatch, "youtube")
        _url, state = oauth_service.start_authorization(user.id, "youtube")

        response = callback(client, "youtube", code="c", state=state)
        assert response.status_code == 303
        assert redirect_params(response)["status"] == ["connected"]

    def test_the_pkce_verifier_is_replayed_to_the_provider(
        self, client, owner, configured, monkeypatch
    ):
        user, _headers = owner
        captured = stub_exchange(monkeypatch, "x")
        _url, state = oauth_service.start_authorization(user.id, "x")
        sealed_verifier = unseal_state(state, 600)["verifier"]

        callback(client, "x", code="c", state=state)
        assert captured["verifier"] == sealed_verifier

    def test_a_forged_state_is_rejected(self, client, db, owner, configured, monkeypatch):
        stub_exchange(monkeypatch, "youtube")
        response = callback(client, "youtube", code="c", state="forged")
        assert redirect_params(response)["status"] == ["failed"]
        assert db.query(SocialAccount).count() == 0

    def test_a_missing_state_is_rejected(self, client, db, owner, configured, monkeypatch):
        stub_exchange(monkeypatch, "youtube")
        response = callback(client, "youtube", code="c")
        assert redirect_params(response)["status"] == ["failed"]
        assert db.query(SocialAccount).count() == 0

    def test_a_state_from_another_platform_is_rejected(
        self, client, db, owner, configured, monkeypatch
    ):
        """A state issued for YouTube must not be redeemable at TikTok."""
        user, _headers = owner
        stub_exchange(monkeypatch, "tiktok")
        _url, state = oauth_service.start_authorization(user.id, "youtube")

        response = callback(client, "tiktok", code="c", state=state)
        assert redirect_params(response)["status"] == ["failed"]
        assert db.query(SocialAccount).count() == 0

    def test_a_declined_authorisation_is_reported_not_crashed(
        self, client, db, owner, configured
    ):
        response = callback(
            client, "youtube", error="access_denied", error_description="User said no"
        )
        assert response.status_code == 303
        assert redirect_params(response)["detail"] == ["User said no"]
        assert db.query(SocialAccount).count() == 0

    def test_a_callback_with_no_code_is_rejected(self, client, owner, configured):
        response = callback(client, "youtube", state="x")
        assert redirect_params(response)["status"] == ["failed"]

    def test_a_failing_token_exchange_is_reported(
        self, client, db, owner, configured, monkeypatch
    ):
        user, _headers = owner

        async def _boom(code, code_verifier=None):
            from apps.api.services.platforms import PlatformError

            raise PlatformError("invalid_grant: the code expired")

        monkeypatch.setattr(get_platform("youtube"), "exchange_code", _boom)
        _url, state = oauth_service.start_authorization(user.id, "youtube")

        response = callback(client, "youtube", code="c", state=state)
        assert redirect_params(response)["status"] == ["failed"]
        assert "the code expired" in redirect_params(response)["detail"][0]
        assert db.query(SocialAccount).count() == 0

    def test_unknown_platform_is_404(self, client, configured):
        assert client.get("/oauth/myspace/callback").status_code == 404

    def test_the_account_is_attached_to_the_user_in_the_state(
        self, client, db, make_user, owner, configured, monkeypatch
    ):
        """The callback has no session, so the state is the only thing
        deciding who owns the new connection."""
        _user, _headers = owner
        other = make_user(email="other@example.com")
        stub_exchange(monkeypatch, "youtube")
        _url, state = oauth_service.start_authorization(other.id, "youtube")

        callback(client, "youtube", code="c", state=state)

        account = db.query(SocialAccount).one()
        assert account.user_id == other.id


class TestCallbackWithoutAnAppUrl:
    """With APP_URL blank the callback answers in JSON, so the flow stays
    debuggable from a terminal."""

    def test_success_returns_json(
        self, client, owner, configured, monkeypatch, no_app_url
    ):
        user, _headers = owner
        stub_exchange(monkeypatch, "youtube")
        _url, state = oauth_service.start_authorization(user.id, "youtube")

        response = client.get(
            "/oauth/youtube/callback", params={"code": "c", "state": state}
        )
        assert response.status_code == 200
        assert response.json()["connected"] is True

    def test_failure_returns_400(self, client, owner, configured, no_app_url):
        response = client.get(
            "/oauth/youtube/callback", params={"error": "access_denied"}
        )
        assert response.status_code == 400
        assert response.json()["detail"]["connected"] is False


class TestFullExchangeAgainstMockedHttp:
    """The one path that exercises the real client code, not a stub."""

    def test_youtube_connect_through_to_storage(
        self, client, db, owner, configured, monkeypatch
    ):
        user, _headers = owner

        def handler(request: httpx.Request) -> httpx.Response:
            if "oauth2.googleapis.com" in str(request.url):
                return httpx.Response(
                    200,
                    json={
                        "access_token": "real-access",
                        "refresh_token": "real-refresh",
                        "expires_in": 3600,
                        "scope": "https://www.googleapis.com/auth/youtube.upload",
                    },
                )
            return httpx.Response(
                200,
                json={"items": [{"id": "UC9", "snippet": {"title": "Studio"}}]},
            )

        transport = httpx.MockTransport(handler)
        monkeypatch.setattr(
            get_platform("youtube"),
            "_client",
            lambda **kw: httpx.AsyncClient(transport=transport, timeout=5.0),
        )

        _url, state = oauth_service.start_authorization(user.id, "youtube")
        response = callback(client, "youtube", code="auth-code", state=state)
        assert response.status_code == 303, response.text
        assert redirect_params(response)["status"] == ["connected"]

        account = db.query(SocialAccount).one()
        assert account.account_id == "UC9"
        assert account.account_name == "Studio"
        assert decrypt_token(account.access_token_encrypted) == "real-access"
        assert decrypt_token(account.refresh_token_encrypted) == "real-refresh"
        assert account.expires_at is not None
        assert account.is_active is True
