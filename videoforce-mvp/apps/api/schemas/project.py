"""Project request/response contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Mirrors the comment on Project.status in models/project.py.
ProjectStatus = Literal["pending", "generating", "completed", "failed"]

PROJECT_STATUSES: tuple[str, ...] = ("pending", "generating", "completed", "failed")


class ProjectCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)
    topic: str | None = Field(default=None, max_length=2000)
    settings_json: dict[str, Any] = Field(default_factory=dict)


class ProjectUpdate(BaseModel):
    """Only user-editable fields.

    ``status`` is deliberately absent: it is driven by the generation pipeline,
    not by clients. Allowing it here would let a user mark a failed render
    "completed".
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=1, max_length=200)
    topic: str | None = Field(default=None, max_length=2000)
    settings_json: dict[str, Any] | None = None


class ProjectPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    title: str
    topic: str | None = None
    status: str
    settings_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @field_validator("settings_json", mode="before")
    @classmethod
    def _null_json_is_empty(cls, v: Any) -> Any:
        # The column is nullable and older rows predate the dict default.
        return {} if v is None else v


class ProjectWithCounts(ProjectPublic):
    """Project plus a cheap summary of its videos, for library views."""

    video_count: int = 0
