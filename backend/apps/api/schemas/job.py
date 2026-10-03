"""Generation request/response contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from apps.api.schemas.video import VideoJobPublic, VideoPublic

StageName = Literal["script", "voiceover", "assemble"]
ScriptStyle = Literal["short_form", "long_form", "intro"]


class GenerationRequest(BaseModel):
    """Options for a generation run.

    Topic comes from the project, not the request, so a job cannot be pointed
    at content the project does not describe.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    style: ScriptStyle = "short_form"
    duration: int = Field(default=60, ge=5, le=600, description="Target seconds.")
    voice: str = Field(default="lessac", max_length=50)
    stages: list[StageName] | None = Field(
        default=None,
        description=(
            "Pipeline stages to run. Defaults to ['script'], the only stage "
            "this build can complete without extra tooling."
        ),
    )


class GenerationAccepted(BaseModel):
    """202 body: what was created and how to follow it."""

    job: VideoJobPublic
    video: VideoPublic
    stages: list[str]
    poll_url: str


class StageInfo(BaseModel):
    name: str
    description: str
    available: bool
    reason: str | None = Field(
        default=None, description="Why the stage cannot run, when unavailable."
    )


class StockProviderInfo(BaseModel):
    """One stock media source and whether it is usable."""

    name: str
    label: str
    configured: bool
    reason: str | None = None
    supports_video: bool
    supports_images: bool
    watermarked: bool = Field(
        default=False,
        description=(
            "Previews from this provider carry a watermark, so a render "
            "using them is a draft and must not be published."
        ),
    )


class MediaStorageInfo(BaseModel):
    """Where rendered media lives."""

    backend: str = Field(description="'s3' or 'local'.")
    configured: bool
    reason: str | None = None
    public_urls: bool = Field(
        description=(
            "Whether renders get a URL a third party can fetch. Instagram "
            "and TikTok cannot publish without one."
        )
    )
    warning: str | None = Field(
        default=None,
        description="Why a generated URL may not be reachable externally.",
    )


class PipelineStatus(BaseModel):
    """What the deployment can actually do right now."""

    stages: list[StageInfo]
    default_stages: list[str]
    stock_providers: list[StockProviderInfo] = Field(
        default_factory=list,
        description="Footage sources, in the order they are tried.",
    )
    output_format: dict[str, int] = Field(
        default_factory=dict,
        description="Frame size and rate every render is produced at.",
    )
    media_storage: MediaStorageInfo | None = Field(
        default=None,
        description="Where finished renders are kept, and whether they get a URL.",
    )
