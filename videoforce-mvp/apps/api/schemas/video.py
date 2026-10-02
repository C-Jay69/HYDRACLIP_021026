"""Video and video-job contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

VideoStatus = Literal["pending", "generating", "completed", "failed"]
VIDEO_STATUSES: tuple[str, ...] = ("pending", "generating", "completed", "failed")

JobType = Literal["generate", "publish", "regenerate"]


class VideoPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    user_id: int
    status: str
    storage_key: str | None = None
    script_text: str | None = None
    error_message: str | None = None
    duration_seconds: int | None = None
    resolution: str | None = None
    format: str | None = None
    generation_params_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @field_validator("generation_params_json", mode="before")
    @classmethod
    def _null_json_is_empty(cls, v: Any) -> Any:
        return {} if v is None else v


class VideoUpdate(BaseModel):
    """User-editable video fields.

    The script is editable so a creator can correct the AI draft before the
    render runs. Status, storage key and error message are pipeline-owned.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    script_text: str | None = Field(default=None, max_length=50_000)


class VideoJobPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    video_id: int
    job_type: str
    status: str
    celery_task_id: str | None = Field(
        default=None,
        description="Worker task id, for correlating a stuck job with flower.",
    )
    progress_pct: int = 0
    error_message: str | None = None

    @field_validator("progress_pct", mode="before")
    @classmethod
    def _null_progress_is_zero(cls, v: Any) -> Any:
        return 0 if v is None else v
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None


class QuotaStatus(BaseModel):
    """Where the caller stands against their monthly video allowance."""

    plan_name: str
    limit_monthly: int = Field(description="0 means unlimited.")
    used: int
    in_flight: int = Field(
        default=0, description="Accepted generations still running; these hold a slot."
    )
    remaining: int | None = Field(description="null when the plan is unlimited.")
    unlimited: bool
    period_start: datetime
    period_end: datetime
