"""Password reset endpoints.

Both endpoints answer with an identical, deliberately vague message so the
flow cannot be used to discover which addresses have accounts. The forgot
endpoint is rate limited per client IP; the reset endpoint additionally
validates a signed, single-use token.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator
from typing import Annotated

from apps.api.core.deps import DbSession, client_ip
from apps.api.schemas.auth import COMMON_PASSWORDS, MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH
from apps.api.services import password_reset as reset_service
from apps.api.services.rate_limit import RateLimiter

RawPassword = Annotated[str, StringConstraints(strip_whitespace=False)]


class ForgotPasswordRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=False)

    token: str = Field(min_length=1)
    new_password: RawPassword = Field(
        min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH
    )

    @field_validator("new_password")
    @classmethod
    def _password_strength(cls, value: str) -> str:
        # Same rules as signup, so a reset cannot set a password that signup
        # would have rejected.
        if value.strip() != value:
            raise ValueError("Password must not start or end with whitespace.")
        if value.lower() in COMMON_PASSWORDS:
            raise ValueError("Password is too common.")
        if len(set(value)) < 5:
            raise ValueError("Password must contain at least 5 distinct characters.")
        return value


class PasswordResetAnswered(BaseModel):
    detail: str


router = APIRouter(prefix="/auth", tags=["passwords"])

#: Brute-forcing single-use tokens through this endpoint is pointless (they
#: are 256-bit), but flooding it triggers outbound email, so it is rate
#: limited like login.
password_reset_limiter = RateLimiter(max_attempts=5, window_seconds=900)

_GENERIC_OK = (
    "If that address has an account, a reset link is on its way. "
    "Check your inbox — and your spam folder."
)


@router.post(
    "/forgot-password",
    response_model=PasswordResetAnswered,
    status_code=status.HTTP_200_OK,
)
def forgot_password(
    payload: ForgotPasswordRequest, request: Request, db: DbSession
) -> PasswordResetAnswered:
    ip = client_ip(request)
    if not password_reset_limiter.check(ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many reset requests. Please try again in a few minutes.",
            headers={"Retry-After": str(password_reset_limiter.retry_after(ip))},
        )
    # Every call counts — each one would trigger an outbound email.
    password_reset_limiter.register_failure(ip)

    # The answer is identical whether or not the account exists, so this
    # endpoint cannot be used to enumerate addresses.
    reset_service.request_reset(db, payload.email)
    return PasswordResetAnswered(detail=_GENERIC_OK)


@router.post("/reset-password", response_model=PasswordResetAnswered)
def reset_password(payload: ResetPasswordRequest, db: DbSession) -> PasswordResetAnswered:
    try:
        reset_service.consume_reset(db, payload.token, payload.new_password)
    except reset_service.PasswordResetError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return PasswordResetAnswered(detail="Your password has been updated. You can sign in now.")