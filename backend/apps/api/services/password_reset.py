"""Password reset: issue a single-use token, deliver it, consume it.

The token is a stateless signed JWT (``type=password_reset``, one-hour TTL),
so issuing needs no schema change. Single-use enforcement rides the existing
``system_settings`` key/value table: consuming a token records
``pwd_reset_used:<jti>`` there, and a replay of the same link is rejected. A
dedicated table would be a schema change this phase deliberately avoids —
the same reasoning that left ``platform_tokens`` unwritten in the OAuth phase.

Delivery uses the SMTP settings from ``.env``. The compose stack ships
MailHog, so local links land in an inbox UI; when SMTP looks unconfigured
(the placeholder default host), the link is logged instead so the flow stays
testable end to end without an inbox.
"""

from __future__ import annotations

import logging
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.core.config import settings
from apps.api.models import SystemSetting, User
from apps.api.services.auth import (
    TokenError,
    create_password_reset_token,
    decode_token,
    hash_password,
)

logger = logging.getLogger(__name__)

#: How long a reset link stays valid.
RESET_TOKEN_TTL_SECONDS = 3600

_USED_KEY_PREFIX = "pwd_reset_used:"


class PasswordResetError(RuntimeError):
    """The reset token is invalid, expired or already used."""


def reset_url_for(token: str) -> str:
    base = (settings.APP_URL or "http://localhost:3000").rstrip("/")
    return f"{base}/auth/reset?token={token}"


def send_reset_email(email: str, token: str) -> None:
    """Deliver the reset link, or log it when SMTP is not configured."""
    url = reset_url_for(token)
    host = (settings.SMTP_HOST or "").strip()
    configured = bool(host) and "example.com" not in host
    if not configured:
        logger.warning(
            "SMTP is not configured; password-reset link for %s: %s", email, url
        )
        return

    message = EmailMessage()
    message["Subject"] = "Reset your HydraClip password"
    message["From"] = settings.SMTP_FROM
    message["To"] = email
    message.set_content(
        "A password reset was requested for your HydraClip account.\n\n"
        f"Open this link to choose a new password (valid for "
        f"{RESET_TOKEN_TTL_SECONDS // 60} minutes):\n\n{url}\n\n"
        "If you did not request this, you can safely ignore this email."
    )
    try:
        with smtplib.SMTP(host, settings.SMTP_PORT, timeout=10) as smtp:
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                smtp.starttls()
                smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            smtp.send_message(message)
    except OSError as exc:
        # Delivery problems never leak whether an account exists: by the time
        # this runs, the endpoint has already answered with a generic 200.
        logger.error("Could not send the password-reset email: %s", exc)


def request_reset(db: Session, email: str) -> str | None:
    """Create and deliver a reset token for ``email``.

    Returns the raw token — so tests (and log-only dev mode) can drive the
    flow without an inbox — or ``None`` when the address is unknown. Callers
    must answer identically either way so the endpoint cannot be used to
    enumerate accounts.
    """
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None or not user.is_active:
        return None

    token = create_password_reset_token(user.id, RESET_TOKEN_TTL_SECONDS)
    send_reset_email(user.email, token)
    return token


def _used_key(jti: str) -> str:
    return f"{_USED_KEY_PREFIX}{jti}"


def consume_reset(db: Session, token: str, new_password: str) -> User:
    """Validate the token, mark it used, and set the new password."""
    try:
        payload = decode_token(token, expected_type="password_reset")
    except TokenError as exc:
        raise PasswordResetError(str(exc)) from exc

    jti = str(payload.get("jti") or "")
    if not jti:
        raise PasswordResetError("Reset token is invalid.")

    key = _used_key(jti)
    if db.scalar(select(SystemSetting.id).where(SystemSetting.key == key)) is not None:
        raise PasswordResetError("This reset link has already been used.")

    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise PasswordResetError("Reset token is invalid.") from exc

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise PasswordResetError("Reset token is invalid.")

    user.password_hash = hash_password(new_password)
    db.add(
        SystemSetting(
            key=key,
            value=datetime.now(timezone.utc).isoformat(),
            value_type="string",
            description="Consumed single-use password-reset token.",
        )
    )
    db.commit()
    return user