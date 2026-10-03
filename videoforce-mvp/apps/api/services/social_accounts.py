"""Storage and lifecycle for connected publishing accounts.

``social_accounts`` is the single source of truth for platform credentials.
Everything that needs a usable access token should call
:func:`ensure_fresh_token` rather than reading the column directly, because a
stored token is only valid until ``expires_at`` — X's last about two hours.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.core.config import settings
from apps.api.models.system import SocialAccount
from apps.api.services.crypto import (
    DecryptionError,
    decrypt_optional,
    decrypt_token,
    encrypt_optional,
    encrypt_token,
)
from apps.api.services.platforms import PlatformAuthError, TokenSet, get_platform

logger = logging.getLogger(__name__)


class AccountError(RuntimeError):
    """A connected account cannot be used."""


class ReconnectRequired(AccountError):
    """The account's credentials are dead; the user must re-authorise."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(value: datetime | None) -> datetime | None:
    """SQLite hands back naive datetimes; treat those as UTC.

    Comparing a naive datetime to an aware one raises, which would turn a
    routine expiry check into a 500.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


# --- Reads ---------------------------------------------------------------------


def list_accounts(db: Session, user_id: int) -> list[SocialAccount]:
    return list(
        db.scalars(
            select(SocialAccount)
            .where(SocialAccount.user_id == user_id)
            .order_by(SocialAccount.platform, SocialAccount.id)
        )
    )


def get_account(db: Session, user_id: int, account_id: int) -> SocialAccount | None:
    return db.scalars(
        select(SocialAccount).where(
            SocialAccount.id == account_id, SocialAccount.user_id == user_id
        )
    ).first()


def find_for_platform(
    db: Session, user_id: int, platform: str
) -> SocialAccount | None:
    """The active account a scheduled post should publish through."""
    return db.scalars(
        select(SocialAccount)
        .where(
            SocialAccount.user_id == user_id,
            SocialAccount.platform == platform,
            SocialAccount.is_active.is_(True),
        )
        .order_by(SocialAccount.id)
    ).first()


# --- Writes --------------------------------------------------------------------


def upsert_account(
    db: Session, user_id: int, platform: str, token: TokenSet
) -> SocialAccount:
    """Store freshly issued credentials, reusing the row if one exists.

    Reconnecting an account the user already has must not create a second
    row, otherwise publishing would pick between two rows with no way to know
    which token is live.
    """
    if token.account_id:
        # A known identity matches on that identity alone. Falling back to
        # "any account on this platform" here would let a second channel
        # silently overwrite the first.
        existing = db.scalars(
            select(SocialAccount).where(
                SocialAccount.user_id == user_id,
                SocialAccount.platform == platform,
                SocialAccount.account_id == token.account_id,
            )
        ).first()
    else:
        # No identity from the provider, so the best we can do is reuse the
        # single account already connected for this platform.
        existing = db.scalars(
            select(SocialAccount)
            .where(
                SocialAccount.user_id == user_id,
                SocialAccount.platform == platform,
            )
            .order_by(SocialAccount.id)
        ).first()

    account = existing or SocialAccount(user_id=user_id, platform=platform)

    account.account_id = token.account_id or account.account_id
    account.account_name = (
        token.account_name or account.account_name or f"{platform} account"
    )
    account.access_token_encrypted = encrypt_token(token.access_token)
    # A provider that does not reissue a refresh token must not blank the one
    # already stored, or the connection dies at the next expiry.
    if token.refresh_token:
        account.refresh_token_encrypted = encrypt_token(token.refresh_token)
    account.token_type = token.token_type or "Bearer"
    account.scope = token.scope
    account.expires_at = _strip_tz(token.expires_at)
    account.is_active = True
    account.last_error = None
    if existing is None:
        account.connected_at = _strip_tz(_utcnow())
        db.add(account)

    db.commit()
    db.refresh(account)
    return account


def _strip_tz(value: datetime | None) -> datetime | None:
    """Store naive UTC, matching every other datetime column in the schema."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def disconnect(db: Session, account: SocialAccount) -> None:
    """Forget the credentials but keep the row for post history.

    The tokens are cleared rather than merely flagged inactive, so a
    disconnect genuinely removes the secret from the database.
    """
    account.is_active = False
    account.access_token_encrypted = encrypt_token("")
    account.refresh_token_encrypted = None
    account.expires_at = None
    account.last_error = None
    db.commit()


def mark_failed(db: Session, account: SocialAccount, reason: str) -> None:
    account.is_active = False
    account.last_error = reason[:1000]
    db.commit()


# --- Token freshness --------------------------------------------------------------


def is_expiring(account: SocialAccount, leeway: int | None = None) -> bool:
    expires_at = _as_aware(account.expires_at)
    if expires_at is None:
        return False
    leeway = settings.TOKEN_REFRESH_LEEWAY_SECONDS if leeway is None else leeway
    return expires_at <= _utcnow() + timedelta(seconds=leeway)


async def ensure_fresh_token(db: Session, account: SocialAccount) -> str:
    """Return a usable access token, refreshing it first if it is about to die.

    Raises :class:`ReconnectRequired` when the credentials cannot be revived,
    which callers should surface to the user rather than retry.
    """
    if not account.is_active:
        raise ReconnectRequired(
            f"The {account.platform} account '{account.account_name}' is "
            f"disconnected. Reconnect it before publishing."
        )

    try:
        access_token = decrypt_token(account.access_token_encrypted)
        refresh_token = decrypt_optional(account.refresh_token_encrypted)
    except DecryptionError as exc:
        mark_failed(db, account, str(exc))
        raise ReconnectRequired(str(exc)) from exc

    if not is_expiring(account):
        return access_token

    client = get_platform(account.platform)

    # Instagram has no refresh token: a long-lived token refreshes itself,
    # so the access token is its own refresh credential.
    credential = refresh_token or (
        access_token if account.platform == "instagram" else None
    )
    if not credential:
        reason = (
            f"The {account.platform} token expired and no refresh token was "
            f"stored, so it cannot be renewed. Reconnect the account."
        )
        mark_failed(db, account, reason)
        raise ReconnectRequired(reason)

    try:
        refreshed = await client.refresh(credential)
    except PlatformAuthError as exc:
        reason = f"{account.platform} rejected the refresh token: {exc}"
        mark_failed(db, account, reason)
        raise ReconnectRequired(reason) from exc
    except Exception as exc:  # noqa: BLE001 - transient provider/network errors
        logger.warning(
            "Token refresh for %s account %s failed: %s",
            account.platform,
            account.id,
            exc,
        )
        raise AccountError(
            f"Could not refresh the {account.platform} token: {exc}"
        ) from exc

    account.access_token_encrypted = encrypt_token(refreshed.access_token)
    if refreshed.refresh_token:
        account.refresh_token_encrypted = encrypt_optional(refreshed.refresh_token)
    account.expires_at = _strip_tz(refreshed.expires_at)
    account.last_error = None
    db.commit()

    logger.info(
        "Refreshed the %s token for account %s", account.platform, account.id
    )
    return refreshed.access_token
