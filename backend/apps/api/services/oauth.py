"""The authorisation-code flow, from redirect to stored credentials."""

from __future__ import annotations

import logging
import secrets

from sqlalchemy.orm import Session

from apps.api.core.config import settings
from apps.api.models.system import SocialAccount
from apps.api.services.crypto import DecryptionError, seal_state, unseal_state
from apps.api.services.platforms import (
    PlatformClient,
    PlatformError,
    generate_pkce_pair,
    get_platform,
)
from apps.api.services.social_accounts import upsert_account

logger = logging.getLogger(__name__)


class OAuthStateError(RuntimeError):
    """The state parameter was missing, forged, replayed or expired."""


def start_authorization(user_id: int, platform: str) -> tuple[str, str]:
    """Return ``(authorize_url, state)`` for a platform connection.

    The state blob is encrypted rather than signed because it carries the
    PKCE code verifier, which must stay secret from anything that can read
    the redirect URL. It also pins the flow to one user, so a callback
    delivered to a different session cannot attach an account to the wrong
    person.
    """
    client: PlatformClient = get_platform(platform)
    client.require_configured()

    verifier: str | None = None
    challenge: str | None = None
    if client.requires_pkce:
        verifier, challenge = generate_pkce_pair()

    state = seal_state(
        {
            "user_id": user_id,
            "platform": client.name,
            "verifier": verifier,
            "nonce": secrets.token_urlsafe(16),
        }
    )

    return client.authorize_url(state=state, code_challenge=challenge), state


def read_state(state: str, platform: str) -> dict:
    """Decrypt and validate the state returned by the provider."""
    if not state:
        raise OAuthStateError("The provider did not return a state parameter.")

    try:
        payload = unseal_state(state, settings.OAUTH_STATE_TTL_SECONDS)
    except DecryptionError as exc:
        raise OAuthStateError(str(exc)) from exc

    if payload.get("platform") != platform:
        # A state minted for one platform must not be redeemed at another's
        # callback.
        raise OAuthStateError("The OAuth state does not match this platform.")
    if not isinstance(payload.get("user_id"), int):
        raise OAuthStateError("The OAuth state carries no user.")

    return payload


async def complete_authorization(
    db: Session, platform: str, code: str, state: str
) -> SocialAccount:
    """Exchange the authorisation code and store the resulting credentials."""
    payload = read_state(state, platform)
    client = get_platform(platform)
    client.require_configured()

    try:
        token = await client.exchange_code(code, code_verifier=payload.get("verifier"))
    except PlatformError:
        raise
    except Exception as exc:  # noqa: BLE001 - network/parse failures
        raise PlatformError(
            f"Could not complete the {client.label} connection: {exc}"
        ) from exc

    account = upsert_account(
        db, user_id=payload["user_id"], platform=client.name, token=token
    )
    logger.info(
        "Connected %s account %s for user %s",
        client.name,
        account.account_id,
        account.user_id,
    )
    return account
