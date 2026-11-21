"""Email Service for Notifications."""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def send_email(
    to_email: str,
    subject: str,
    body: str,
) -> bool:
    """Send an email."""
    # In production, use SMTP or SendGrid
    logger.info(f"Sending email to {to_email}: {subject}")
    # Simulate sending
    return True


async def send_password_reset_email(to_email: str, reset_token: str) -> bool:
    """Send password reset email."""
    return await send_email(
        to_email=to_email,
        subject="HydraClip - Password Reset",
        body=f"Reset your password: {reset_token}",
    )


async def send_welcome_email(to_email: str, name: str) -> bool:
    """Send welcome email."""
    return await send_email(
        to_email=to_email,
        subject="Welcome to HydraClip",
        body=f"Welcome {name}! Start creating videos with local AI.",
    )