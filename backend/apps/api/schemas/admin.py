"""Admin contracts: user management, platform stats, settings, audit log."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AdminUserPublic(BaseModel):
    """A user as the admin panel renders it, with usage counts."""

    id: int
    email: str
    name: str | None = None
    role: str
    is_active: bool
    is_verified: bool
    stripe_customer_id: str | None = None
    created_at: datetime | None = None
    project_count: int = 0
    video_count: int = 0
    plan_name: str | None = None


class AdminUserUpdate(BaseModel):
    """Fields an administrator may change on any account."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(default=None, max_length=120)
    role: Literal["USER", "ADMIN"] | None = None
    is_active: bool | None = None
    is_verified: bool | None = None


class AdminSetPlanRequest(BaseModel):
    """Assign a plan directly, without going through Stripe.

    This is the manual override the spec's admin requirements call for: an
    operator grants or revokes a paid plan from the panel.
    """

    plan_id: int


class AdminStats(BaseModel):
    """Top-line platform numbers for the admin overview."""

    users: int
    active_users: int
    projects: int
    videos: int
    completed_videos: int
    failed_videos: int
    active_subscriptions: int
    plan_breakdown: dict[str, int] = Field(
        default_factory=dict,
        description="Active subscriptions per plan name.",
    )


class AdminAuditLogPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    admin_id: int
    action: str
    target_type: str
    target_id: int | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None

    @field_validator("metadata_json", mode="before")
    @classmethod
    def _null_json_is_empty(cls, v: Any) -> Any:
        return {} if v is None else v


class SystemSettingPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    value: str | None = None
    value_type: str
    description: str | None = None
    updated_at: datetime | None = None


class SystemSettingUpsert(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    value: str | None = None
    value_type: Literal["string", "integer", "boolean", "json"] = "string"
    description: str | None = Field(default=None, max_length=500)