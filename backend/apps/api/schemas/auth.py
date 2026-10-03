"""Authentication request/response contracts."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator

from apps.api.schemas.user import UserPublic

MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_LENGTH = 256

# Passwords must NOT be whitespace-stripped. Model-level
# `str_strip_whitespace` would silently rewrite the user's secret, so a
# password typed with a trailing space would be stored differently from what
# was entered. Opt the field out explicitly and reject the input instead.
RawPassword = Annotated[str, StringConstraints(strip_whitespace=False)]

COMMON_PASSWORDS = {
    "password123",
    "letmein123",
    "changeme123",
    "qwerty12345",
    "1234567890",
    "adminadmin",
}


class SignupRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    password: RawPassword = Field(
        min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH
    )
    name: str | None = Field(default=None, max_length=120)

    @field_validator("password")
    @classmethod
    def _password_strength(cls, value: str) -> str:
        if value.strip() != value:
            raise ValueError("Password must not start or end with whitespace.")
        if value.lower() in COMMON_PASSWORDS:
            raise ValueError("Password is too common.")
        if len(set(value)) < 5:
            raise ValueError("Password must contain at least 5 distinct characters.")
        return value


class LoginRequest(BaseModel):
    # Email is normalised; the password is passed through untouched so it can
    # be compared byte-for-byte with what signup hashed.
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    password: RawPassword = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserPublic


class ExternalAccessTokenRequest(BaseModel):
    access_token: str = Field(min_length=1)


class ExternalAuthResult(BaseModel):
    authenticated: bool
    requires_email_confirmation: bool = False
    message: str
    tokens: TokenPair | None = None


class AuthProviders(BaseModel):
    supabase_email: bool
    google: bool
    google_authorize_path: str = "/auth/google/authorize"
    detail: dict[str, str | None]
