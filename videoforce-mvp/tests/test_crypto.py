"""Encryption of stored secrets and OAuth state."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from apps.api.core.config import settings
from apps.api.services.crypto import (
    DecryptionError,
    decrypt_optional,
    decrypt_token,
    encrypt_optional,
    encrypt_token,
    redact,
    seal_state,
    unseal_state,
)


class TestTokenEncryption:
    def test_round_trip(self):
        assert decrypt_token(encrypt_token("ya29.secret")) == "ya29.secret"

    def test_ciphertext_does_not_contain_the_plaintext(self):
        assert "ya29.secret" not in encrypt_token("ya29.secret")

    def test_encryption_is_not_deterministic(self):
        """Identical tokens must not produce identical ciphertext, or a
        database leak would reveal which users share a credential."""
        assert encrypt_token("same") != encrypt_token("same")

    def test_tampered_ciphertext_is_rejected(self):
        ciphertext = encrypt_token("ya29.secret")
        with pytest.raises(DecryptionError):
            decrypt_token(ciphertext[:-6] + "AAAAAA")

    def test_wrong_key_is_rejected(self, monkeypatch):
        ciphertext = encrypt_token("ya29.secret")
        monkeypatch.setattr(settings, "TOKEN_ENCRYPTION_KEY", "a-different-key")
        with pytest.raises(DecryptionError, match="reconnected"):
            decrypt_token(ciphertext)

    def test_explicit_key_is_preferred_over_secret_key(self, monkeypatch):
        monkeypatch.setattr(settings, "TOKEN_ENCRYPTION_KEY", "explicit-key")
        ciphertext = encrypt_token("token")
        # Changing SECRET_KEY must not strand the token when an explicit
        # encryption key is configured.
        monkeypatch.setattr(settings, "SECRET_KEY", "rotated-secret-key")
        assert decrypt_token(ciphertext) == "token"

    def test_empty_string_round_trips(self):
        """disconnect() stores an encrypted empty string rather than NULL,
        because the column is NOT NULL."""
        assert decrypt_token(encrypt_token("")) == ""

    def test_refuses_to_encrypt_none(self):
        with pytest.raises(ValueError):
            encrypt_token(None)  # type: ignore[arg-type]

    def test_optional_helpers_pass_none_through(self):
        assert encrypt_optional(None) is None
        assert decrypt_optional(None) is None
        assert decrypt_optional(encrypt_optional("v")) == "v"


class TestOAuthState:
    def test_round_trip(self):
        state = seal_state({"user_id": 7, "verifier": "v"})
        assert unseal_state(state, 600)["user_id"] == 7

    def test_verifier_is_not_readable_from_the_state(self):
        """The PKCE verifier travels in the URL, so it must be encrypted and
        not merely signed."""
        assert "super-secret-verifier" not in seal_state(
            {"user_id": 1, "verifier": "super-secret-verifier"}
        )

    def test_expired_state_is_rejected(self):
        state = seal_state({"user_id": 7})
        real = time.time
        with patch("time.time", lambda: real() + 1200):
            with pytest.raises(DecryptionError, match="expired"):
                unseal_state(state, 600)

    def test_tampered_state_is_rejected(self):
        state = seal_state({"user_id": 7})
        with pytest.raises(DecryptionError):
            unseal_state(state[:-6] + "AAAAAA", 600)

    def test_garbage_is_rejected(self):
        with pytest.raises(DecryptionError):
            unseal_state("not-a-token", 600)

    def test_token_key_cannot_decrypt_state(self):
        """Domain separation: the two contexts derive different keys."""
        with pytest.raises(DecryptionError):
            decrypt_token(seal_state({"user_id": 1}))


class TestRedact:
    def test_keeps_only_the_tail(self):
        assert redact("abcdefghij") == "******ghij"

    def test_handles_none_and_short_values(self):
        assert redact(None) == "<none>"
        assert redact("") == "<none>"
        assert redact("ab") == "**"
