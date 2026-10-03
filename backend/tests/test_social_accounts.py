"""Credential storage, refresh and the account endpoints."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from apps.api.core.config import settings
from apps.api.models.system import SocialAccount
from apps.api.services import social_accounts as accounts
from apps.api.services.crypto import decrypt_token, encrypt_token
from apps.api.services.platforms import PlatformAuthError, TokenSet
from apps.api.services.social_accounts import ReconnectRequired


@pytest.fixture
def configured(monkeypatch):
    for name in ("YOUTUBE", "INSTAGRAM", "TIKTOK", "X"):
        monkeypatch.setattr(settings, f"{name}_CLIENT_ID", "id")
        monkeypatch.setattr(settings, f"{name}_CLIENT_SECRET", "secret")
        monkeypatch.setattr(settings, f"{name}_REDIRECT_URI", "https://a/cb")


def token_set(**kwargs) -> TokenSet:
    base = dict(
        access_token="access-1",
        refresh_token="refresh-1",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
        scope="scope",
        account_id="acc-1",
        account_name="Channel",
    )
    base.update(kwargs)
    return TokenSet(**base)


class TestUpsert:
    def test_tokens_are_stored_encrypted(self, db, make_user):
        user = make_user()
        account = accounts.upsert_account(db, user.id, "youtube", token_set())

        assert account.access_token_encrypted != "access-1"
        assert "access-1" not in account.access_token_encrypted
        assert decrypt_token(account.access_token_encrypted) == "access-1"
        assert decrypt_token(account.refresh_token_encrypted) == "refresh-1"

    def test_identity_and_scope_are_recorded(self, db, make_user):
        user = make_user()
        account = accounts.upsert_account(db, user.id, "youtube", token_set())
        assert account.account_id == "acc-1"
        assert account.account_name == "Channel"
        assert account.scope == "scope"
        assert account.is_active is True

    def test_reconnecting_updates_rather_than_duplicates(self, db, make_user):
        user = make_user()
        first = accounts.upsert_account(db, user.id, "youtube", token_set())
        second = accounts.upsert_account(
            db, user.id, "youtube", token_set(access_token="access-2")
        )

        assert first.id == second.id
        assert len(accounts.list_accounts(db, user.id)) == 1
        assert decrypt_token(second.access_token_encrypted) == "access-2"

    def test_a_second_account_on_the_same_platform_is_allowed(self, db, make_user):
        user = make_user()
        accounts.upsert_account(db, user.id, "youtube", token_set(account_id="a"))
        accounts.upsert_account(db, user.id, "youtube", token_set(account_id="b"))
        assert len(accounts.list_accounts(db, user.id)) == 2

    def test_absent_refresh_token_does_not_erase_the_stored_one(self, db, make_user):
        """Google omits the refresh token on re-consent; blanking it would
        kill the connection at the next expiry."""
        user = make_user()
        accounts.upsert_account(db, user.id, "youtube", token_set())
        updated = accounts.upsert_account(
            db, user.id, "youtube", token_set(refresh_token=None)
        )
        assert decrypt_token(updated.refresh_token_encrypted) == "refresh-1"

    def test_reconnecting_clears_a_previous_error(self, db, make_user):
        user = make_user()
        account = accounts.upsert_account(db, user.id, "youtube", token_set())
        accounts.mark_failed(db, account, "it broke")
        assert account.is_active is False

        revived = accounts.upsert_account(db, user.id, "youtube", token_set())
        assert revived.is_active is True
        assert revived.last_error is None

    def test_expires_at_is_stored_naive(self, db, make_user):
        """Mixing naive and aware datetimes in one column makes every
        comparison raise."""
        user = make_user()
        account = accounts.upsert_account(db, user.id, "youtube", token_set())
        assert account.expires_at.tzinfo is None


class TestDisconnect:
    def test_disconnect_erases_the_tokens(self, db, make_user):
        user = make_user()
        account = accounts.upsert_account(db, user.id, "youtube", token_set())
        accounts.disconnect(db, account)

        assert account.is_active is False
        assert account.refresh_token_encrypted is None
        assert decrypt_token(account.access_token_encrypted) == ""

    def test_disconnect_keeps_the_row_for_history(self, db, make_user):
        user = make_user()
        account = accounts.upsert_account(db, user.id, "youtube", token_set())
        accounts.disconnect(db, account)
        assert db.get(SocialAccount, account.id) is not None


class TestLookup:
    def test_find_for_platform_ignores_inactive_accounts(self, db, make_user):
        user = make_user()
        account = accounts.upsert_account(db, user.id, "youtube", token_set())
        assert accounts.find_for_platform(db, user.id, "youtube") is not None

        accounts.disconnect(db, account)
        assert accounts.find_for_platform(db, user.id, "youtube") is None

    def test_accounts_are_scoped_to_their_owner(self, db, make_user):
        owner = make_user(email="owner@example.com")
        other = make_user(email="other@example.com")
        accounts.upsert_account(db, owner.id, "youtube", token_set())
        assert accounts.list_accounts(db, other.id) == []


class TestExpiry:
    def test_a_token_without_an_expiry_never_expires(self, db, make_user):
        user = make_user()
        account = accounts.upsert_account(db, user.id, "youtube", token_set(expires_at=None))
        assert accounts.is_expiring(account) is False

    def test_a_token_inside_the_leeway_is_expiring(self, db, make_user):
        user = make_user()
        account = accounts.upsert_account(
            db,
            user.id,
            "youtube",
            token_set(expires_at=datetime.now(timezone.utc) + timedelta(seconds=60)),
        )
        assert accounts.is_expiring(account) is True

    def test_a_naive_expiry_is_treated_as_utc(self, db, make_user):
        """SQLite returns naive datetimes; comparing one to an aware now()
        would raise instead of answering the question."""
        user = make_user()
        account = accounts.upsert_account(db, user.id, "youtube", token_set())
        account.expires_at = datetime.utcnow() + timedelta(hours=5)
        assert accounts.is_expiring(account) is False


class TestEnsureFreshToken:
    def test_a_valid_token_is_returned_untouched(self, db, make_user, configured):
        user = make_user()
        account = accounts.upsert_account(db, user.id, "youtube", token_set())
        assert asyncio.run(accounts.ensure_fresh_token(db, account)) == "access-1"

    def test_an_expiring_token_is_refreshed_and_persisted(
        self, db, make_user, configured, monkeypatch
    ):
        user = make_user()
        account = accounts.upsert_account(
            db,
            user.id,
            "youtube",
            token_set(expires_at=datetime.now(timezone.utc) + timedelta(seconds=10)),
        )

        async def fake_refresh(refresh_token):
            assert refresh_token == "refresh-1"
            return TokenSet(
                access_token="access-2",
                refresh_token="refresh-2",
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            )

        from apps.api.services.platforms import get_platform

        monkeypatch.setattr(get_platform("youtube"), "refresh", fake_refresh)

        assert asyncio.run(accounts.ensure_fresh_token(db, account)) == "access-2"

        db.expire_all()
        stored = db.get(SocialAccount, account.id)
        assert decrypt_token(stored.access_token_encrypted) == "access-2"
        assert decrypt_token(stored.refresh_token_encrypted) == "refresh-2"

    def test_a_disconnected_account_cannot_be_used(self, db, make_user, configured):
        user = make_user()
        account = accounts.upsert_account(db, user.id, "youtube", token_set())
        accounts.disconnect(db, account)

        with pytest.raises(ReconnectRequired, match="disconnected"):
            asyncio.run(accounts.ensure_fresh_token(db, account))

    def test_an_expired_token_with_no_refresh_token_requires_reconnection(
        self, db, make_user, configured
    ):
        user = make_user()
        account = accounts.upsert_account(
            db,
            user.id,
            "youtube",
            token_set(
                refresh_token=None,
                expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            ),
        )

        with pytest.raises(ReconnectRequired, match="no refresh token"):
            asyncio.run(accounts.ensure_fresh_token(db, account))
        assert account.is_active is False

    def test_a_rejected_refresh_deactivates_the_account(
        self, db, make_user, configured, monkeypatch
    ):
        user = make_user()
        account = accounts.upsert_account(
            db,
            user.id,
            "youtube",
            token_set(expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)),
        )

        async def rejected(refresh_token):
            raise PlatformAuthError("invalid_grant")

        from apps.api.services.platforms import get_platform

        monkeypatch.setattr(get_platform("youtube"), "refresh", rejected)

        with pytest.raises(ReconnectRequired):
            asyncio.run(accounts.ensure_fresh_token(db, account))

        db.expire_all()
        stored = db.get(SocialAccount, account.id)
        assert stored.is_active is False
        assert "invalid_grant" in stored.last_error

    def test_a_transient_refresh_failure_does_not_deactivate(
        self, db, make_user, configured, monkeypatch
    ):
        """A network blip must not force the user to reconnect."""
        user = make_user()
        account = accounts.upsert_account(
            db,
            user.id,
            "youtube",
            token_set(expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)),
        )

        async def boom(refresh_token):
            raise OSError("connection reset")

        from apps.api.services.platforms import get_platform

        monkeypatch.setattr(get_platform("youtube"), "refresh", boom)

        with pytest.raises(accounts.AccountError):
            asyncio.run(accounts.ensure_fresh_token(db, account))
        assert account.is_active is True

    def test_instagram_refreshes_with_its_access_token(
        self, db, make_user, configured, monkeypatch
    ):
        """Instagram issues no refresh token; the long-lived access token
        renews itself."""
        user = make_user()
        account = accounts.upsert_account(
            db,
            user.id,
            "instagram",
            token_set(
                refresh_token=None,
                expires_at=datetime.now(timezone.utc) + timedelta(seconds=30),
            ),
        )

        seen = {}

        async def fake_refresh(credential):
            seen["credential"] = credential
            return TokenSet(
                access_token="renewed",
                expires_at=datetime.now(timezone.utc) + timedelta(days=60),
            )

        from apps.api.services.platforms import get_platform

        monkeypatch.setattr(get_platform("instagram"), "refresh", fake_refresh)

        assert asyncio.run(accounts.ensure_fresh_token(db, account)) == "renewed"
        assert seen["credential"] == "access-1"

    def test_undecryptable_token_requires_reconnection(
        self, db, make_user, configured, monkeypatch
    ):
        user = make_user()
        account = accounts.upsert_account(db, user.id, "youtube", token_set())
        monkeypatch.setattr(settings, "TOKEN_ENCRYPTION_KEY", "a-rotated-key")

        with pytest.raises(ReconnectRequired, match="reconnected"):
            asyncio.run(accounts.ensure_fresh_token(db, account))


class TestAccountEndpoints:
    def test_listing_requires_authentication(self, client):
        assert client.get("/accounts").status_code == 401

    def test_listing_returns_the_callers_accounts(
        self, client, db, make_user, auth_headers
    ):
        headers = auth_headers(email="owner@example.com")
        from apps.api.models import User

        owner = db.query(User).filter(User.email == "owner@example.com").one()
        accounts.upsert_account(db, owner.id, "youtube", token_set())

        response = client.get("/accounts", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["platform"] == "youtube"
        assert body[0]["account_name"] == "Channel"

    def test_listing_never_exposes_token_material(
        self, client, db, make_user, auth_headers
    ):
        headers = auth_headers(email="owner@example.com")
        from apps.api.models import User

        owner = db.query(User).filter(User.email == "owner@example.com").one()
        accounts.upsert_account(db, owner.id, "youtube", token_set())

        raw = client.get("/accounts", headers=headers).text
        assert "access-1" not in raw
        assert "refresh-1" not in raw
        assert "encrypted" not in raw

    def test_disconnect_clears_the_tokens(self, client, db, auth_headers):
        headers = auth_headers(email="owner@example.com")
        from apps.api.models import User

        owner = db.query(User).filter(User.email == "owner@example.com").one()
        account = accounts.upsert_account(db, owner.id, "youtube", token_set())

        assert client.delete(f"/accounts/{account.id}", headers=headers).status_code == 204

        db.expire_all()
        stored = db.get(SocialAccount, account.id)
        assert stored.is_active is False
        assert decrypt_token(stored.access_token_encrypted) == ""

    def test_cannot_disconnect_someone_elses_account(
        self, client, db, make_user, auth_headers
    ):
        victim = make_user(email="victim@example.com")
        account = accounts.upsert_account(db, victim.id, "youtube", token_set())

        headers = auth_headers(email="attacker@example.com")
        assert client.delete(f"/accounts/{account.id}", headers=headers).status_code == 404

        db.expire_all()
        assert db.get(SocialAccount, account.id).is_active is True

    def test_disconnecting_a_missing_account_is_404(self, client, auth_headers):
        headers = auth_headers()
        assert client.delete("/accounts/9999", headers=headers).status_code == 404


class TestPlatformsEndpoint:
    def test_lists_every_platform_with_its_readiness(self, client):
        response = client.get("/platforms")
        assert response.status_code == 200
        body = response.json()
        assert {p["name"] for p in body} == {"youtube", "instagram", "tiktok", "x"}
        # Nothing is configured in the test environment.
        assert all(p["configured"] is False for p in body)
        assert all(p["detail"] for p in body)

    def test_reports_which_platforms_need_a_public_url(self, client):
        body = {p["name"]: p for p in client.get("/platforms").json()}
        assert body["instagram"]["requires_public_url"] is True
        assert body["tiktok"]["requires_public_url"] is True
        assert body["youtube"]["requires_public_url"] is False

    def test_is_public(self, client):
        """The connect screen is rendered before the user picks an account,
        so this must not require a token."""
        assert client.get("/platforms").status_code == 200
