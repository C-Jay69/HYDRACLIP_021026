"""Unit tests for password hashing and JWT handling."""

from __future__ import annotations

import time

import pytest

from apps.api.services.auth import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_differs_from_the_plaintext(self):
        assert hash_password("hunter2hunter2") != "hunter2hunter2"

    def test_hashes_are_salted(self):
        assert hash_password("same-password") != hash_password("same-password")

    def test_verifies_a_correct_password(self):
        assert verify_password("s3cret-passphrase", hash_password("s3cret-passphrase"))

    def test_rejects_an_incorrect_password(self):
        assert not verify_password("wrong", hash_password("s3cret-passphrase"))

    def test_rejects_an_empty_password(self):
        with pytest.raises(ValueError):
            hash_password("")

    def test_handles_a_malformed_stored_hash_without_raising(self):
        assert verify_password("anything", "not-a-bcrypt-hash") is False

    def test_does_not_truncate_at_bcrypt_72_byte_limit(self):
        """bcrypt alone ignores everything past 72 bytes.

        Two passwords sharing a 72-byte prefix must not be interchangeable.
        """
        base = "A" * 72
        stored = hash_password(base + "-tail-one")

        assert verify_password(base + "-tail-one", stored)
        assert not verify_password(base + "-tail-two", stored)

    def test_supports_multibyte_passwords(self):
        password = "contraseña-mañana-日本語-🎬"
        assert verify_password(password, hash_password(password))


class TestTokens:
    def test_access_token_round_trips(self):
        token = create_access_token(42, extra_claims={"role": "ADMIN"})
        claims = decode_token(token, expected_type="access")
        assert claims["sub"] == "42"
        assert claims["role"] == "ADMIN"

    def test_refresh_token_is_typed(self):
        claims = decode_token(create_refresh_token(7), expected_type="refresh")
        assert claims["type"] == "refresh"

    def test_wrong_type_is_rejected(self):
        with pytest.raises(TokenError):
            decode_token(create_access_token(1), expected_type="refresh")

    def test_tampered_token_is_rejected(self):
        token = create_access_token(1)
        head, payload, signature = token.split(".")
        with pytest.raises(TokenError):
            decode_token(f"{head}.{payload}.{signature[:-3]}xyz")

    def test_expired_token_is_rejected(self):
        token = create_access_token(1, expires_in=-1)
        time.sleep(0.01)
        with pytest.raises(TokenError):
            decode_token(token)

    def test_garbage_is_rejected(self):
        with pytest.raises(TokenError):
            decode_token("clearly-not-a-jwt")

    def test_tokens_are_unique_per_issue(self):
        assert create_access_token(1) != create_access_token(1)
