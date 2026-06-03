"""Pydantic models for Version Explorer API responses and internal data."""

from typing import Any

from pydantic import BaseModel, Field, field_validator


class ChannelInfo(BaseModel):
    """Channel information from API responses."""

    channel: str
    iib: str = ""
    released_to_prod: bool = False
    in_stage: bool = False
    fbc_snapshot: str | None = None


class ReleasedBuild(BaseModel):
    """Single entry from GetReleasedBuilds API response."""

    csv_version: str
    version: str
    current_channel: str | None = None
    channels: list[ChannelInfo] = Field(default_factory=list)
    replaces: str | None = None
    skips: list[str] = Field(default_factory=list)
    skip_range: str | None = Field(None, alias="skipRange")
    build_timestamp: str | None = None

    model_config = {"populate_by_name": True}

    @field_validator("skips", mode="before")
    @classmethod
    def _coerce_skips(cls, v: Any) -> list[str]:
        """API sometimes returns "" or null instead of [] for empty skips."""
        if v is None:
            return []
        if isinstance(v, str):
            return [s for s in v.split(",") if s] if v else []
        if isinstance(v, list):
            return v
        return list(v)


class SuccessfulBuild(BaseModel):
    """Single entry from GetSuccessfulBuildsByVersion API response (channel-filtered)."""

    cnv_build: str
    iib: str = ""
    channel: str = ""
    released_to_prod: bool = False
    in_stage: bool = False


class BuildInfo(BaseModel):
    """Response from GetBuildInfo API endpoint."""

    cnv_version: str
    current_channel: str | None = None
    channels: list[ChannelInfo] = Field(default_factory=list)
    error: str | None = None


class BuildResult(BaseModel):
    """Standardized build info returned by extract/fetch functions."""

    version: str
    bundle_version: str
    iib: str
    channel: str
    in_stage: bool | None = None
    released_to_prod: bool | None = None
