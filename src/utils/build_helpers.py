"""Build resolution helpers for channel checking, info extraction, and source/target lookup."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cnv_upgrade_utilities.version_types import strip_bundle_suffix
from utils.constants import CHANNEL_STABLE
from utils.models import BuildInfo, BuildResult, ChannelInfo, ReleasedBuild, SuccessfulBuild

if TYPE_CHECKING:
    from utils.version_explorer import CnvVersionExplorer


def channel_released_to_prod(channels: list[ChannelInfo], channel: str) -> bool:
    """Check if a specific channel is released to prod."""
    return any(ch.channel == channel and ch.released_to_prod for ch in channels)


def channel_in_stage(channels: list[ChannelInfo], channel: str) -> bool:
    """Check if a specific channel has in_stage=true."""
    return any(ch.channel == channel and ch.in_stage for ch in channels)


def channel_exists(channels: list[ChannelInfo], channel: str) -> bool:
    """Check if a specific channel exists in the channels list."""
    return any(ch.channel == channel for ch in channels)


def get_channel_info(channels: list[ChannelInfo], channel: str) -> ChannelInfo:
    """Find and return the ChannelInfo for a specific channel."""
    for ch in channels:
        if ch.channel == channel:
            return ch
    raise ValueError(f"Channel '{channel}' not found in channels list")


def make_build_result(
    version: str, bundle_version: str, iib: str, channel: str, extra: ChannelInfo | None = None
) -> BuildResult:
    """Build a standardized BuildResult from raw fields."""
    return BuildResult(
        version=version,
        bundle_version=bundle_version,
        iib=iib,
        channel=channel,
        in_stage=extra.in_stage if extra else None,
        released_to_prod=extra.released_to_prod if extra else None,
    )


def extract_filtered_build_info(build: SuccessfulBuild, version: str) -> BuildResult:
    """Extract BuildResult from a GetSuccessfulBuildsByVersion response entry."""
    return BuildResult(
        version=version,
        bundle_version=build.cnv_build.lstrip("v"),
        iib=build.iib,
        channel=build.channel,
        in_stage=build.in_stage,
        released_to_prod=build.released_to_prod,
    )


def extract_released_build_info(build: ReleasedBuild, channel: str) -> BuildResult:
    """Extract BuildResult from a GetReleasedBuilds response entry."""
    channel_info = get_channel_info(channels=build.channels, channel=channel)
    return BuildResult(
        version=build.csv_version.lstrip("v"),
        bundle_version=build.version.lstrip("v"),
        iib=channel_info.iib,
        channel=channel,
        in_stage=channel_info.in_stage,
        released_to_prod=channel_info.released_to_prod,
    )


def extract_from_build_info(build_info: BuildInfo, channel: str) -> BuildResult:
    """Extract BuildResult from a GetBuildInfo response."""
    cnv_version = build_info.cnv_version
    channel_info = get_channel_info(channels=build_info.channels, channel=channel)
    return BuildResult(
        version=strip_bundle_suffix(cnv_version.lstrip("v")),
        bundle_version=cnv_version.lstrip("v"),
        iib=channel_info.iib,
        channel=channel,
        in_stage=channel_info.in_stage,
        released_to_prod=channel_info.released_to_prod,
    )


def find_stable_stage_build(explorer: CnvVersionExplorer, version: str) -> BuildResult | None:
    """Find a stable build in stage (not yet released to prod) for a specific X.Y.Z version."""
    builds = explorer.get_successful_builds_by_version(version=version, channel=CHANNEL_STABLE, stage=True)
    for build in builds:
        if not build.released_to_prod:
            return extract_filtered_build_info(build=build, version=version)
    return None


def find_released_source(
    explorer: CnvVersionExplorer,
    minor_version: str,
    required_csv: str | None = None,
    exclude_csv: str | None = None,
) -> BuildResult:
    """Find the latest stable build released to prod for a minor version."""
    builds = explorer.get_released_builds(minor_version=minor_version, stage=False)
    if not builds:
        raise ValueError(f"No released builds found for {minor_version}")

    for build in builds:
        if required_csv and build.csv_version != required_csv:
            continue
        if exclude_csv and build.csv_version.lstrip("v") == exclude_csv.lstrip("v"):
            continue
        if channel_released_to_prod(channels=build.channels, channel=CHANNEL_STABLE):
            return extract_released_build_info(build=build, channel=CHANNEL_STABLE)

    if required_csv:
        raise ValueError(f"No stable build released to prod found for source version {required_csv.lstrip('v')}")
    raise ValueError(f"No stable build released to prod found for source {minor_version}")
