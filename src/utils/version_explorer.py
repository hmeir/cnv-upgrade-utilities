"""Version Explorer API client and utilities."""

import logging
import os
from collections.abc import Callable
from enum import Enum
from typing import Any

import requests
from packaging.version import Version
from requests.exceptions import ConnectionError, HTTPError, Timeout, TooManyRedirects
from timeout_sampler import TimeoutSampler

from utils.constants import (
    BUNDLE_VERSION_KEY_CNV_BUILD,
    BUNDLE_VERSION_KEY_VERSION,
    CHANNEL_CANDIDATE,
    CHANNEL_STABLE,
    ENDPOINT_GET_BUILD_BY_IIB,
    ENDPOINT_GET_BUILDS_WITH_ERRATA,
    ENDPOINT_GET_SUCCESSFUL_BUILDS_BY_VERSION,
    ENDPOINT_GET_UPGRADE_PATH,
    ENV_VERSION_EXPLORER_URL,
    ERRATA_STATUS_SHIPPED_LIVE,
    ERRATA_STATUS_TRUE,
)

LOGGER = logging.getLogger(__name__)

# Default timeout values
DEFAULT_REQUEST_TIMEOUT = 30
DEFAULT_RETRY_TIMEOUT = 120


class CnvVersionExplorer:
    """
    Client for interacting with the Version Explorer API.

    Provides methods to query build information, upgrade paths, and release data.
    Uses a requests Session for connection pooling and retry logic.

    Usage:
        # With explicit URL
        explorer = CnvVersionExplorer(url="https://version-explorer.example.com")

        # From environment variable
        explorer = CnvVersionExplorer()

        # As context manager (recommended)
        with CnvVersionExplorer() as explorer:
            builds = explorer.get_builds_with_errata("v4.20")

    Attributes:
        url: The Version Explorer API base URL
        request_timeout: Timeout for individual requests (seconds)
        retry_timeout: Total timeout for retry attempts (seconds)
    """

    class APIEndpoints(Enum):
        GET_BUILDS_WITH_ERRATA = "GetBuildsWithErrata"
        GET_BUILD_BY_IIB = "GetBuildByIIB"
        GET_SUCCESSFUL_BUILDS_BY_VERSION = "GetSuccessfulBuildsByVersion"
        GET_UPGRADE_PATH = "GetUpgradePath"

        def __str__(self) -> str:
            return self.value

    def __init__(
        self,
        url: str | None = None,
        request_timeout: int = DEFAULT_REQUEST_TIMEOUT,
        retry_timeout: int = DEFAULT_RETRY_TIMEOUT,
    ):
        """
        Initialize the Version Explorer client.

        Args:
            url: API base URL. If not provided, reads from VERSION_EXPLORER_URL env var.
            request_timeout: Timeout for individual HTTP requests (default: 30s)
            retry_timeout: Total timeout for retry attempts (default: 120s)

        Raises:
            ValueError: If URL is not provided and VERSION_EXPLORER_URL is not set
        """
        self._url = url or os.environ.get(ENV_VERSION_EXPLORER_URL)
        if not self._url:
            raise ValueError("URL must be provided or VERSION_EXPLORER_URL environment variable must be set")
        self.request_timeout = request_timeout
        self.retry_timeout = retry_timeout
        self._session: requests.Session | None = None

    @property
    def url(self) -> str:
        """The Version Explorer API base URL."""
        return self._url

    @property
    def session(self) -> requests.Session:
        """Lazily initialized requests session with connection pooling."""
        if self._session is None:
            self._session = requests.Session()
            self._session.verify = False
        return self._session

    def close(self) -> None:
        """Close the underlying HTTP session."""
        if self._session is not None:
            self._session.close()
            self._session = None

    def __enter__(self) -> "CnvVersionExplorer":
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"CnvVersionExplorer(url='{self._url}')"

    # --- Core API Methods ---

    def query(self, endpoint: str, query_string: str) -> Any | None:
        """
        Execute a single API query.

        Args:
            endpoint: API endpoint name (e.g., "GetBuildsWithErrata")
            query_string: Query string parameters

        Returns:
            JSON response or None if request failed
        """
        try:
            response = self.session.get(
                url=f"{self._url}/{endpoint}?{query_string}",
                timeout=self.request_timeout,
            )
            response.raise_for_status()
            return response.json()
        except (HTTPError, ConnectionError, Timeout, TooManyRedirects) as ex:
            LOGGER.warning(f"API request failed: {ex}")
            return None

    def query_with_retry(self, endpoint: str, query_string: str) -> Any:
        """
        Execute an API query with retry logic.

        Retries until a successful response or timeout is reached.

        Args:
            endpoint: API endpoint name
            query_string: Query string parameters

        Returns:
            JSON response

        Raises:
            TimeoutError: If no successful response within retry_timeout
        """
        sampler = TimeoutSampler(
            wait_timeout=self.retry_timeout,
            sleep=self.request_timeout,
            func=self.query,
            endpoint=endpoint,
            query_string=query_string,
            print_log=False,
            print_func_log=False,
        )
        for sample in sampler:
            if sample:
                return sample

    # --- Build Query Methods ---

    def get_builds_with_errata(self, minor_version: str) -> list[dict]:
        """
        Fetch builds with errata for a minor version.

        Args:
            minor_version: Minor version string (e.g., "v4.20")

        Returns:
            List of build dictionaries
        """
        return self.query_with_retry(
            endpoint=ENDPOINT_GET_BUILDS_WITH_ERRATA,
            query_string=f"minor_version={minor_version}",
        )["builds"]

    def get_build_by_iib(self, iib: str) -> dict:
        """
        Get build information by IIB number.

        Args:
            iib: IIB number string

        Returns:
            Build info dictionary with version and channel
        """
        build_info = self.query_with_retry(
            endpoint=ENDPOINT_GET_BUILD_BY_IIB,
            query_string=f"iib_number={iib}",
        )
        return get_build_info_dict(
            version=str(Version(build_info["cnv_version"].split(".rhel9")[0])),
            channel=build_info["channel"],
        )

    def get_builds_by_version(self, version: str, errata_status: str = ERRATA_STATUS_TRUE) -> dict[str, Any]:
        """
        Get successful builds by version.

        Args:
            version: Version string (e.g., "4.20.0")
            errata_status: Filter by errata status (default: "true")

        Returns:
            Dictionary with successful_builds list
        """
        return self.query_with_retry(
            endpoint=ENDPOINT_GET_SUCCESSFUL_BUILDS_BY_VERSION,
            query_string=f"version={version}&errata_status={errata_status}",
        )

    def get_upgrade_path(self, target_version: str, channel: str) -> dict[str, list[dict[str, str | list[str]]]]:
        """
        Get upgrade path for a target version and channel.

        Args:
            target_version: Target version string
            channel: Release channel ("stable" or "candidate")

        Returns:
            Dictionary containing upgrade path information
        """
        LOGGER.info(f"Getting upgrade path for target version: {target_version} and channel: {channel}")
        return self.query_with_retry(
            endpoint=ENDPOINT_GET_UPGRADE_PATH,
            query_string=f"targetVersion={target_version}&channel={channel}",
        )

    # --- High-Level Query Methods ---

    def get_latest_stable_released_z_stream_info(self, minor_version: str) -> dict[str, str]:
        """
        Get the latest stable channel released z-stream info for a minor version.

        Args:
            minor_version: Minor version string (e.g., "v4.20")

        Returns:
            Dictionary with version, bundle_version, iib, and channel info
        """
        builds = self.get_builds_with_errata(minor_version)
        build = find_latest_build(
            builds,
            lambda b: b["errata_status"] == ERRATA_STATUS_SHIPPED_LIVE
            and stable_channel_released_to_prod(b["channels"]),
        )
        assert build, "No stable latest z stream found"
        return extract_channel_info(
            build_data=build,
            version=build["csv_version"],
            bundle_version_key=BUNDLE_VERSION_KEY_VERSION,
            channel=CHANNEL_STABLE,
        )

    def get_latest_candidate_released_z_stream_info(self, minor_version: str) -> dict[str, str]:
        """
        Get the latest candidate channel released z-stream info for a minor version.

        Args:
            minor_version: Minor version string (e.g., "v4.20")

        Returns:
            Dictionary with version, bundle_version, iib, and channel info
        """
        builds = self.get_builds_with_errata(minor_version)
        build = find_latest_build(builds, lambda b: candidate_channel_released_to_prod(b["channels"]))
        assert build, "No candidate latest z stream found"
        return extract_channel_info(
            build_data=build,
            version=build["csv_version"],
            bundle_version_key=BUNDLE_VERSION_KEY_VERSION,
            channel=CHANNEL_CANDIDATE,
        )

    def get_latest_build_with_errata_info(self, minor_version: str) -> dict[str, str]:
        """
        Get the latest build with errata for a minor version, regardless of channel.

        Returns the build with the highest version number that has errata,
        preferring stable channel if available for that build, otherwise candidate.

        Args:
            minor_version: Minor version string (e.g., "v4.20")

        Returns:
            Dictionary with version, bundle_version, iib, and channel info
        """
        builds = self.get_builds_with_errata(minor_version)
        build = find_latest_build(builds, lambda b: bool(b.get("errata_status")))
        assert build, "No build with errata found"
        return extract_build_info_with_stable_preference(build)

    def get_latest_candidate_with_stable_fallback_info(self, minor_version: str) -> dict[str, str]:
        """
        Get the latest candidate channel released z-stream info, with stable fallback.

        For Y-stream upgrades: finds the latest candidate released to prod, then checks if
        that same build also has a stable channel available. If so, returns stable info.

        Args:
            minor_version: Minor version string (e.g., "v4.20")

        Returns:
            Dictionary with version, bundle_version, iib, and channel info
        """
        builds = self.get_builds_with_errata(minor_version)
        build = find_latest_build(builds, lambda b: candidate_channel_released_to_prod(b["channels"]))
        assert build, "No candidate latest z stream found"
        return extract_build_info_with_stable_preference(build)

    def get_z0_release_info(self, minor_version: str) -> dict[str, str]:
        """
        Get the 4.Y.0 release info for a minor version (used for latest-z upgrades).

        Args:
            minor_version: Minor version string (e.g., "4.20" or "v4.20")

        Returns:
            Dictionary with version, bundle_version, iib, and channel info
        """
        clean_version = minor_version.lstrip("v")
        version = f"{clean_version}.0"
        build_info = self.get_builds_by_version(version=version, errata_status=ERRATA_STATUS_TRUE)["successful_builds"][
            0
        ]
        return extract_channel_info(
            build_data=build_info,
            version=version,
            bundle_version_key=BUNDLE_VERSION_KEY_CNV_BUILD,
            channel=CHANNEL_STABLE,
        )


# --- Helper functions (stateless, no API dependency) ---


def channel_released_to_prod(channels: list[dict[str, str | bool]], channel: str) -> bool:
    """Check if a specific channel is released to prod."""
    return any(item.get("channel") == channel and item.get("released_to_prod") for item in channels)


def stable_channel_released_to_prod(channels: list[dict[str, str | bool]]) -> bool:
    """Check if stable channel is released to prod."""
    return channel_released_to_prod(channels, CHANNEL_STABLE)


def candidate_channel_released_to_prod(channels: list[dict[str, str | bool]]) -> bool:
    """Check if candidate channel is released to prod."""
    return channel_released_to_prod(channels, CHANNEL_CANDIDATE)


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
    """Extract stable channel information from build data."""
    return extract_channel_info(build_data, version, bundle_version_key, CHANNEL_STABLE)


def extract_candidate_channel_info(build_data: dict, version: str, bundle_version_key: str) -> dict[str, str]:
    """Extract candidate channel information from build data."""
    return extract_channel_info(build_data, version, bundle_version_key, CHANNEL_CANDIDATE)


def find_latest_build(builds: list[dict], predicate: Callable[[dict], bool]) -> dict | None:
    """
    Find the build with the highest version that matches the predicate.

    Args:
        builds: List of build dictionaries
        predicate: Function that returns True for builds to consider

    Returns:
        The build with the highest csv_version matching the predicate, or None
    """
    latest_version = None
    latest_build = None
    for build in builds:
        if predicate(build):
            build_version = Version(version=build["csv_version"])
            if latest_version is None or build_version > latest_version:
                latest_version = build_version
                latest_build = build
    return latest_build


def extract_build_info_with_stable_preference(build: dict) -> dict[str, str]:
    """
    Extract channel info from a build, preferring stable channel if available.

    Args:
        build: Build dictionary with channels list

    Returns:
        Dictionary with version, bundle_version, iib, and channel info
    """
    channel = CHANNEL_STABLE if stable_channel_released_to_prod(build["channels"]) else CHANNEL_CANDIDATE
    return extract_channel_info(
        build_data=build, version=build["csv_version"], bundle_version_key=BUNDLE_VERSION_KEY_VERSION, channel=channel
    )


def get_build_info_dict(version: str, channel: str = CHANNEL_STABLE) -> dict[str, str]:
    """Create a simple build info dictionary."""
    return {
        "version": version,
        "channel": channel,
    }
