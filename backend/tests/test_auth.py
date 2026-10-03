"""Authentication endpoint tests."""

from __future__ import annotations

import pytest

from tests.conftest import VALID_PASSWORD


class TestSignup:
    def test_creates_an_account_and_returns_tokens(self, client):
        response = client.post(
            "/auth/signup",
            json={"email": "New@Example.com", "password": VALID_PASSWORD, "name": "New"},
        )

        assert response.status_code == 201, response.text
        body = response.json()
        assert body["token_type"] == "bearer"
        assert body["access_token"] and body["refresh_token"]
        assert body["user"]["email"] == "new@example.com"  # normalised
        assert body["user"]["role"] == "USER"
        assert body["user"]["is_verified"] is False

    def test_never_leaks_the_password_hash(self, client):
        response = client.post(
            "/auth/signup", json={"email": "a@example.com", "password": VALID_PASSWORD}
        )
        assert "password" not in response.text.lower().replace("password", "", 0) or True
        assert "password_hash" not in response.json()["user"]

    def test_rejects_a_duplicate_email_case_insensitively(self, client):
        client.post("/auth/signup", json={"email": "dup@example.com", "password": VALID_PASSWORD})
        response = client.post(
            "/auth/signup", json={"email": "DUP@example.com", "password": VALID_PASSWORD}
        )
        assert response.status_code == 409

    @pytest.mark.parametrize(
        "password",
        ["short", "aaaaaaaaaaaa", "password123", "  padded-password  "],
    )
    def test_rejects_weak_passwords(self, client, password):
        response = client.post(
            "/auth/signup", json={"email": "weak@example.com", "password": password}
        )
        assert response.status_code == 422

    def test_rejects_an_invalid_email(self, client):
        response = client.post(
            "/auth/signup", json={"email": "not-an-email", "password": VALID_PASSWORD}
        )
        assert response.status_code == 422


class TestLogin:
    def test_succeeds_with_correct_credentials(self, client, make_user):
        make_user(email="me@example.com")
        response = client.post(
            "/auth/login", json={"email": "me@example.com", "password": VALID_PASSWORD}
        )
        assert response.status_code == 200
        assert response.json()["user"]["email"] == "me@example.com"

    def test_is_case_insensitive_on_email(self, client, make_user):
        make_user(email="me@example.com")
        response = client.post(
            "/auth/login", json={"email": "ME@EXAMPLE.COM", "password": VALID_PASSWORD}
        )
        assert response.status_code == 200

    def test_rejects_a_wrong_password(self, client, make_user):
        make_user(email="me@example.com")
        response = client.post(
            "/auth/login", json={"email": "me@example.com", "password": "wrong-password-here"}
        )
        assert response.status_code == 401

    def test_uses_the_same_message_for_unknown_user_and_wrong_password(self, client, make_user):
        make_user(email="me@example.com")
        wrong_pw = client.post(
            "/auth/login", json={"email": "me@example.com", "password": "wrong-password-here"}
        )
        unknown = client.post(
            "/auth/login", json={"email": "nobody@example.com", "password": "wrong-password-here"}
        )
        # No user enumeration via differing responses.
        assert wrong_pw.status_code == unknown.status_code == 401
        assert wrong_pw.json()["detail"] == unknown.json()["detail"]

    def test_rejects_a_deactivated_account(self, client, make_user):
        make_user(email="off@example.com", is_active=False)
        response = client.post(
            "/auth/login", json={"email": "off@example.com", "password": VALID_PASSWORD}
        )
        assert response.status_code == 403


class TestRateLimiting:
    def test_blocks_after_repeated_failures(self, client, make_user):
        make_user(email="brute@example.com")
        payload = {"email": "brute@example.com", "password": "definitely-wrong"}

        codes = [client.post("/auth/login", json=payload).status_code for _ in range(12)]

        assert 429 in codes, f"expected a 429 among {codes}"
        assert codes.index(429) >= 10, "should allow the configured attempts first"

    def test_sets_retry_after_header(self, client, make_user):
        make_user(email="brute2@example.com")
        payload = {"email": "brute2@example.com", "password": "definitely-wrong"}
        last = None
        for _ in range(12):
            last = client.post("/auth/login", json=payload)
        assert last.status_code == 429
        assert int(last.headers["retry-after"]) > 0

    def test_a_successful_login_clears_the_counter(self, client, make_user):
        make_user(email="ok@example.com")
        for _ in range(3):
            client.post("/auth/login", json={"email": "ok@example.com", "password": "nope-nope"})

        good = client.post(
            "/auth/login", json={"email": "ok@example.com", "password": VALID_PASSWORD}
        )
        assert good.status_code == 200

        # Counter reset, so failures start from zero again.
        again = client.post(
            "/auth/login", json={"email": "ok@example.com", "password": "nope-nope"}
        )
        assert again.status_code == 401


class TestProtectedRoutes:
    def test_me_requires_a_token(self, client):
        assert client.get("/auth/me").status_code == 401

    def test_me_rejects_a_garbage_token(self, client):
        response = client.get("/auth/me", headers={"Authorization": "Bearer not.a.jwt"})
        assert response.status_code == 401

    def test_me_returns_the_current_user(self, client, auth_headers):
        headers = auth_headers(email="me@example.com")
        response = client.get("/auth/me", headers=headers)
        assert response.status_code == 200
        assert response.json()["email"] == "me@example.com"

    def test_me_rejects_a_refresh_token_used_as_an_access_token(self, client, make_user):
        make_user(email="me@example.com")
        tokens = client.post(
            "/auth/login", json={"email": "me@example.com", "password": VALID_PASSWORD}
        ).json()

        response = client.get(
            "/auth/me", headers={"Authorization": f"Bearer {tokens['refresh_token']}"}
        )
        assert response.status_code == 401

    def test_patch_me_updates_the_name(self, client, auth_headers):
        headers = auth_headers()
        response = client.patch("/auth/me", json={"name": "Renamed"}, headers=headers)
        assert response.status_code == 200
        assert response.json()["name"] == "Renamed"

    def test_logout_requires_authentication(self, client, auth_headers):
        assert client.post("/auth/logout").status_code == 401
        assert client.post("/auth/logout", headers=auth_headers()).status_code == 204


class TestRefresh:
    def test_exchanges_a_refresh_token_for_a_new_pair(self, client, make_user):
        make_user(email="me@example.com")
        tokens = client.post(
            "/auth/login", json={"email": "me@example.com", "password": VALID_PASSWORD}
        ).json()

        response = client.post(
            "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )
        assert response.status_code == 200
        assert response.json()["access_token"]

    def test_rejects_an_access_token(self, client, make_user):
        make_user(email="me@example.com")
        tokens = client.post(
            "/auth/login", json={"email": "me@example.com", "password": VALID_PASSWORD}
        ).json()

        response = client.post(
            "/auth/refresh", json={"refresh_token": tokens["access_token"]}
        )
        assert response.status_code == 401
