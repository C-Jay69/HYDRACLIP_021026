"""Schemas for connected accounts, scheduling and published posts."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from apps.api.services.platforms import SUPPORTED_PLATFORMS

SCHEDULE_STATUSES = ("pending", "running", "completed", "cancelled", "failed")


class PlatformInfo(BaseModel):
    """What the UI needs to render the 'connect an account' list."""

    name: str
    label: str
    configured: bool
    requires_public_url: bool
    scopes: list[str]
    detail: str | None = Field(
        default=None, description="Why the platform is unavailable, if it is."
    )


class SocialAccountPublic(BaseModel):
    """A connected account. Never carries token material."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    platform: str
    account_name: str
    account_id: str | None = None
    scope: str | None = None
    is_active: bool
    expires_at: datetime | None = None
    last_error: str | None = None
    connected_at: datetime | None = None


class AuthorizeUrl(BaseModel):
    platform: str
    authorize_url: str


class ScheduleCreate(BaseModel):
    video_id: int
    platform: str
    scheduled_at: datetime
    timezone: str = "UTC"
    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    tags: list[str] = Field(default_factory=list)
    privacy: str = "private"

    @field_validator("platform")
    @classmethod
    def _known_platform(cls, value: str) -> str:
        normalised = value.strip().lower()
        if normalised not in SUPPORTED_PLATFORMS:
            raise ValueError(
                f"platform must be one of {', '.join(SUPPORTED_PLATFORMS)}."
            )
        return normalised

    @field_validator("privacy")
    @classmethod
    def _known_privacy(cls, value: str) -> str:
        normalised = value.strip().lower()
        if normalised not in ("public", "unlisted", "private"):
            raise ValueError("privacy must be one of public, unlisted, private.")
        return normalised

    @field_validator("tags")
    @classmethod
    def _sane_tags(cls, value: list[str]) -> list[str]:
        cleaned = [t.strip().lstrip("#") for t in value if t and t.strip()]
        if len(cleaned) > 30:
            raise ValueError("at most 30 tags are allowed.")
        return cleaned


class SchedulePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    video_id: int
    platform: str
    scheduled_at: datetime
    timezone: str
    status: str
    platform_post_id: str | None = None
    platform_url: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PublishedPostPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    video_id: int
    schedule_id: int | None = None
    platform: str
    platform_post_id: str | None = None
    platform_url: str | None = None
    title: str | None = None
    status: str
    published_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime | None = None
