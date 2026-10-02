"""Common shape for every publishing platform.

Each provider differs in almost every detail — PKCE or not, refresh tokens or
not, bytes-upload or fetch-from-URL, synchronous or poll-until-done — so the
base class carves out only what genuinely generalises and leaves the rest to
the subclass.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from apps.api.core.config import settings


class PlatformError(RuntimeError):
    """A provider interaction failed in an expected, reportable way."""


class PlatformNotConfigured(PlatformError):
    """Client id/secret/redirect are missing for this platform."""


class PlatformAuthError(PlatformError):
    """The stored credentials were rejected; the user must reconnect."""


class PublishError(PlatformError):
    """Publishing failed."""


@dataclass
class TokenSet:
    """What a token endpoint gives back."""

    access_token: str
    refresh_token: str | None = None
    expires_at: datetime | None = None
    scope: str | None = None
    token_type: str = "Bearer"
    #: Provider-specific identity discovered during the exchange.
    account_id: str | None = None
    account_name: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class PublishRequest:
    """Everything a provider needs to publish one video."""

    video_url: str | None
    """Publicly reachable URL. Required by providers that fetch the file."""

    file_path: str | None
    """Local path. Required by providers that upload bytes."""

    title: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    privacy: str = "private"

    account_id: str | None = None
    """The provider's own id for the connected account. Instagram addresses
    every publishing call to /{ig-user-id}/..., so it is not optional there."""


@dataclass
class PublishResult:
    post_id: str
    url: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


def generate_pkce_pair() -> tuple[str, str]:
    """Return ``(verifier, challenge)`` for PKCE S256."""
    verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


def expires_at_from(expires_in: Any) -> datetime | None:
    """Convert a provider's ``expires_in`` seconds into an absolute time."""
    try:
        seconds = int(expires_in)
    except (TypeError, ValueError):
        return None
    return datetime.now(timezone.utc) + timedelta(seconds=seconds)


class PlatformClient:
    """Base class for a publishing platform."""

    #: Short key used in URLs and the database.
    name: str = ""
    #: Human-readable label.
    label: str = ""
    #: Scopes requested at authorisation time.
    scopes: tuple[str, ...] = ()
    #: Whether the authorisation flow must use PKCE.
    requires_pkce: bool = False
    #: True when the provider downloads the file from a URL we supply, rather
    #: than accepting the bytes directly.
    needs_public_url: bool = False
    #: True when the provider can also accept the raw bytes. TikTok sets both
    #: flags: it prefers a URL but falls back to a chunked file upload, so a
    #: local render is still publishable. Instagram sets only the first --
    #: for it a missing URL is fatal, and saying so early is the difference
    #: between a clear error and an opaque one from the Graph API.
    can_upload_bytes: bool = True

    authorize_endpoint: str = ""
    token_endpoint: str = ""

    # --- Configuration -------------------------------------------------------

    @property
    def client_id(self) -> str:
        return getattr(settings, f"{self.name.upper()}_CLIENT_ID", "")

    @property
    def client_secret(self) -> str:
        return getattr(settings, f"{self.name.upper()}_CLIENT_SECRET", "")

    @property
    def redirect_uri(self) -> str:
        return getattr(settings, f"{self.name.upper()}_REDIRECT_URI", "")

    def configuration_error(self) -> str | None:
        """Why this platform cannot be used, or None if it is ready."""
        missing = [
            label
            for label, value in (
                (f"{self.name.upper()}_CLIENT_ID", self.client_id),
                (f"{self.name.upper()}_CLIENT_SECRET", self.client_secret),
                (f"{self.name.upper()}_REDIRECT_URI", self.redirect_uri),
            )
            if not value
        ]
        if missing:
            return f"not configured: {', '.join(missing)} must be set"
        return None

    def require_configured(self) -> None:
        problem = self.configuration_error()
        if problem:
            raise PlatformNotConfigured(f"{self.label} is {problem}.")

    # --- OAuth ----------------------------------------------------------------

    def authorize_url(self, state: str, code_challenge: str | None = None) -> str:
        raise NotImplementedError

    async def exchange_code(
        self, code: str, code_verifier: str | None = None
    ) -> TokenSet:
        raise NotImplementedError

    async def refresh(self, refresh_token: str) -> TokenSet:
        raise NotImplementedError

    # --- Publishing --------------------------------------------------------------

    async def publish(self, token: str, request: PublishRequest) -> PublishResult:
        raise NotImplementedError

    # --- Helpers --------------------------------------------------------------------

    def _client(self, **kwargs: Any) -> httpx.AsyncClient:
        kwargs.setdefault("timeout", 60.0)
        return httpx.AsyncClient(**kwargs)

    @staticmethod
    def _raise_for_status(response: httpx.Response, action: str) -> None:
        """Turn an HTTP error into a PlatformError carrying the provider's own
        message, which is far more useful than a bare status code."""
        if response.is_success:
            return

        detail = PlatformClient._error_detail(response)

        if response.status_code in (401, 403):
            raise PlatformAuthError(f"{action} was rejected ({response.status_code}): {detail}")
        raise PlatformError(f"{action} failed ({response.status_code}): {detail}")

    @staticmethod
    def _error_detail(response: httpx.Response) -> str:
        """Pull the most human-readable message out of an error body.

        Providers disagree about where it lives: OAuth endpoints use
        ``error_description``, Meta nests ``error.message``, and some return
        a bare ``error`` string. Checked in that order, falling back to the
        raw body.
        """
        try:
            body = response.json()
        except ValueError:
            return response.text[:400]

        if not isinstance(body, dict):
            return str(body)[:400]

        candidates: list[Any] = [body.get("error_description")]

        error = body.get("error")
        if isinstance(error, dict):
            candidates.append(error.get("message"))
        elif isinstance(error, str):
            candidates.append(error)

        candidates.append(body.get("message"))

        for candidate in candidates:
            if candidate:
                return str(candidate)[:400]
        return str(body)[:400]
