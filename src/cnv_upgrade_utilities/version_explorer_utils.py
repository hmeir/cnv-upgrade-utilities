import logging
import os
from functools import cache
from typing import Any

import requests
from packaging.version import Version
from requests.exceptions import ConnectionError, HTTPError, Timeout, TooManyRedirects
from timeout_sampler import TimeoutSampler

LOGGER = logging.getLogger(__name__)

TIMEOUT_2MIN = 120
TIMEOUT_30SEC = 30


@cache
def get_version_explorer_url():
    """Get the version explorer URL, cached for reuse."""
    version_explorer_url = os.environ.get("VERSION_EXPLORER_URL")
    if not version_explorer_url:
        raise ValueError("VERSION_EXPLORER_URL environment variable is not set")
    return version_explorer_url


def query_version_explorer(api_end_point: str, query_string: str) -> Any:
    try:
        response = requests.get(
            url=f"{get_version_explorer_url()}/{api_end_point}?{query_string}",
            verify=False,
            timeout=TIMEOUT_30SEC,
        )
        response.raise_for_status()
    except (HTTPError, ConnectionError, Timeout, TooManyRedirects) as ex:
        LOGGER.warning(f"Error occurred: {ex}")
        return None
    return response.json()


def wait_for_version_explorer_response(api_end_point: str, query_string: str) -> Any:
    version_explorer_sampler = TimeoutSampler(
        wait_timeout=TIMEOUT_2MIN,
        sleep=TIMEOUT_30SEC,
        func=query_version_explorer,
        api_end_point=api_end_point,
        query_string=query_string,
        print_log=False,
        print_func_log=False,
    )
    for sample in version_explorer_sampler:
        if sample:
            return sample


def get_upgrade_path(target_version: str, channel: str) -> dict[str, list[dict[str, str | list[str]]]]:
    LOGGER.info(f"Getting upgrade path for target version: {target_version} and channel: {channel}")
    return wait_for_version_explorer_response(
        api_end_point="GetUpgradePath", query_string=f"targetVersion={target_version}&channel={channel}"
    )


def stable_channel_released_to_prod(channels: list[dict[str, str | bool]]) -> bool:
    return any(item.get("channel") == "stable" and item.get("released_to_prod") for item in channels)


def candidate_channel_released_to_prod(channels: list[dict[str, str | bool]]) -> bool:
    return any(item.get("channel") == "candidate" and item.get("released_to_prod") for item in channels)


def extract_channel_info(build_data: dict, version: str, bundle_version_key: str, channel: str) -> dict[str, str]:
    """
    Extract channel information from build data.

    Args:
        build_data: Dictionary containing channels list
        version: Version string to include in result
        bundle_version_key: Key to extract bundle_version from build_data
        channel: Channel to extract (e.g., "stable", "candidate")

    Returns:
        Dictionary with version, bundle_version, iib, and channel
    """
    channel_build = next((build for build in build_data.get("channels", []) if build.get("channel") == channel), {})
    assert channel_build, f"No {channel} build found"
    return {
        "version": version,
        "bundle_version": build_data[bundle_version_key],
        "iib": channel_build["iib"],
        "channel": channel_build["channel"],
    }


def extract_stable_channel_info(build_data: dict, version: str, bundle_version_key: str) -> dict[str, str]:
    """
    Extract stable channel information from build data.

    Args:
        build_data: Dictionary containing channels list
        version: Version string to include in result
        bundle_version_key: Key to extract bundle_version from build_data

    Returns:
        Dictionary with version, bundle_version, iib, and channel
    """
    return extract_channel_info(build_data, version, bundle_version_key, "stable")


def extract_candidate_channel_info(build_data: dict, version: str, bundle_version_key: str) -> dict[str, str]:
    """
    Extract candidate channel information from build data.

    Args:
        build_data: Dictionary containing channels list
        version: Version string to include in result
        bundle_version_key: Key to extract bundle_version from build_data

    Returns:
        Dictionary with version, bundle_version, iib, and channel
    """
    return extract_channel_info(build_data, version, bundle_version_key, "candidate")


def get_latest_stable_released_z_stream_info(minor_version: str) -> dict[str, str] | None:
    builds = wait_for_version_explorer_response(
        api_end_point="GetBuildsWithErrata",
        query_string=f"minor_version={minor_version}",
    )["builds"]

    latest_z_stream = None
    source_build = None
    for build in builds:
        if build["errata_status"] == "SHIPPED_LIVE" and stable_channel_released_to_prod(channels=build["channels"]):
            build_version = Version(version=build["csv_version"])
            if latest_z_stream:
                if build_version > latest_z_stream:
                    latest_z_stream = build_version
                    source_build = build
            else:
                latest_z_stream = build_version
                source_build = build
    assert latest_z_stream and source_build, "No stable latest z stream found"
    return extract_stable_channel_info(
        build_data=source_build, version=source_build["csv_version"], bundle_version_key="version"
    )


def get_latest_candidate_released_z_stream_info(minor_version: str) -> dict[str, str] | None:
    """
    Get the latest candidate channel released z-stream info for a minor version.

    Args:
        minor_version: Minor version string (e.g., "v4.20")

    Returns:
        Dictionary with version, bundle_version, iib, and channel info
    """
    builds = wait_for_version_explorer_response(
        api_end_point="GetBuildsWithErrata",
        query_string=f"minor_version={minor_version}",
    )["builds"]

    latest_z_stream = None
    target_build = None
    for build in builds:
        if candidate_channel_released_to_prod(channels=build["channels"]):
            build_version = Version(version=build["csv_version"])
            if latest_z_stream:
                if build_version > latest_z_stream:
                    latest_z_stream = build_version
                    target_build = build
            else:
                latest_z_stream = build_version
                target_build = build
    assert latest_z_stream and target_build, "No candidate latest z stream found"
    return extract_candidate_channel_info(
        build_data=target_build, version=target_build["csv_version"], bundle_version_key="version"
    )


def get_latest_build_with_errata_info(minor_version: str) -> dict[str, str] | None:
    """
    Get the latest build with errata for a minor version, regardless of channel.

    Returns the build with the highest version number that has errata,
    preferring stable channel if available for that build, otherwise candidate.

    Args:
        minor_version: Minor version string (e.g., "v4.20")

    Returns:
        Dictionary with version, bundle_version, iib, and channel info
    """
    builds = wait_for_version_explorer_response(
        api_end_point="GetBuildsWithErrata",
        query_string=f"minor_version={minor_version}",
    )["builds"]

    latest_z_stream = None
    target_build = None
    for build in builds:
        # Any build with errata (don't filter by channel)
        if build.get("errata_status"):
            build_version = Version(version=build["csv_version"])
            if latest_z_stream is None or build_version > latest_z_stream:
                latest_z_stream = build_version
                target_build = build

    assert latest_z_stream and target_build, "No build with errata found"

    # Prefer stable channel if available, otherwise use candidate
    if stable_channel_released_to_prod(channels=target_build["channels"]):
        return extract_stable_channel_info(
            build_data=target_build, version=target_build["csv_version"], bundle_version_key="version"
        )

    return extract_candidate_channel_info(
        build_data=target_build, version=target_build["csv_version"], bundle_version_key="version"
    )


def get_latest_candidate_with_stable_fallback_info(minor_version: str) -> dict[str, str] | None:
    """
    Get the latest candidate channel released z-stream info, falling back to stable if available.

    For Y-stream upgrades: finds the latest candidate released to prod, then checks if
    that same build also has a stable channel available. If so, returns stable info.

    Args:
        minor_version: Minor version string (e.g., "v4.20")

    Returns:
        Dictionary with version, bundle_version, iib, and channel info
    """
    builds = wait_for_version_explorer_response(
        api_end_point="GetBuildsWithErrata",
        query_string=f"minor_version={minor_version}",
    )["builds"]

    latest_z_stream = None
    target_build = None
    for build in builds:
        if candidate_channel_released_to_prod(channels=build["channels"]):
            build_version = Version(version=build["csv_version"])
            if latest_z_stream:
                if build_version > latest_z_stream:
                    latest_z_stream = build_version
                    target_build = build
            else:
                latest_z_stream = build_version
                target_build = build
    assert latest_z_stream and target_build, "No candidate latest z stream found"

    # Check if this build also has stable channel released to prod
    if stable_channel_released_to_prod(channels=target_build["channels"]):
        return extract_stable_channel_info(
            build_data=target_build, version=target_build["csv_version"], bundle_version_key="version"
        )

    return extract_candidate_channel_info(
        build_data=target_build, version=target_build["csv_version"], bundle_version_key="version"
    )


def get_cnv_info_by_iib(iib: str) -> dict[str, str]:
    build_info = wait_for_version_explorer_response(
        api_end_point="GetBuildByIIB",
        query_string=f"iib_number={iib}",
    )
    return get_build_info_dict(
        version=str(Version(build_info["cnv_version"].split(".rhel9")[0])),
        channel=build_info["channel"],
    )


def get_build_info_by_version(version: str, errata_status: str = "true") -> dict[str, Any]:
    query_string = f"version={version}"
    if errata_status:
        query_string = f"{query_string}&errata_status={errata_status}"
    return wait_for_version_explorer_response(
        api_end_point="GetSuccessfulBuildsByVersion",
        query_string=query_string,
    )


def get_z0_release_info(minor_version: str) -> dict[str, str]:
    """
    Get the 4.Y.0 release info for a minor version (used for latest-z upgrades).

    Args:
        minor_version: Minor version string (e.g., "4.20" or "v4.20")

    Returns:
        Dictionary with version, bundle_version, iib, and channel info
    """
    # Strip 'v' prefix if present
    clean_version = minor_version.lstrip("v")
    version = f"{clean_version}.0"

    build_info = get_build_info_by_version(version=version, errata_status="true")["successful_builds"][0]
    return extract_stable_channel_info(build_data=build_info, version=version, bundle_version_key="cnv_build")


def get_build_info_dict(version: str, channel: str = "stable") -> dict[str, str]:
    return {
        "version": version,
        "channel": channel,
    }
