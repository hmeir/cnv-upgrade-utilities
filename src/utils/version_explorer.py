"""Version Explorer API client and utilities."""

import logging
import os
from collections.abc import Callable
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

    # --- API Endpoints ---

    def get_builds_with_errata(self, minor_version: str) -> list[dict]:
        """
        Fetch builds with errata for a minor version.

        Args:
            minor_version: Minor version string (e.g., "v4.20")

        Returns:
            List of build dictionaries
        """
        return self.query_with_retry(
            endpoint="GetBuildsWithErrata",
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
            endpoint="GetBuildByIIB",
            query_string=f"iib_number={iib}",
        )
        return get_build_info_dict(
            version=str(Version(build_info["cnv_version"].split(".rhel9")[0])),
            channel=build_info["channel"],
        )

    def get_builds_by_version(self, version: str, errata_status: str = ERRATA_STATUS_TRUE) -> dict:
        """
        Get successful builds by version.

        Args:
            version: Version string (e.g., "4.20.0")
            errata_status: Filter by errata status (default: "true")

        Returns:
            Dictionary with successful_builds list
        """
        return self.query_with_retry(
            endpoint="GetSuccessfulBuildsByVersion",
            query_string=f"version={version}&errata_status={errata_status}",
        )["successful_builds"][0]

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
            endpoint="GetUpgradePath",
            query_string=f"targetVersion={target_version}&channel={channel}",
        )

    # --- High-Level Methods ---

    def get_latest_released_z_stream_info(self, minor_version: str, channel: str) -> dict[str, str]:
        """
        Get the latest released z-stream info for a minor version and channel.

        Args:
            minor_version: Minor version string (e.g., "v4.20")
            channel: Release channel ("stable" or "candidate")

        Returns:
            Dictionary with version, bundle_version, iib, and channel info

        Note:
            For stable channel: requires SHIPPED_LIVE errata status and stable channel released to prod.
            For candidate channel: only requires candidate channel released to prod.
        """
        builds = self.get_builds_with_errata(minor_version)

        if channel == CHANNEL_STABLE:

            def predicate(b):
                return b["errata_status"] == ERRATA_STATUS_SHIPPED_LIVE and channel_released_to_prod(
                    b["channels"], CHANNEL_STABLE
                )

        else:

            def predicate(b):
                return channel_released_to_prod(b["channels"], channel)

        build = find_latest_build(builds, predicate)
        assert build, f"No {channel} latest z stream found"
        return extract_channel_info(
            build_data=build,
            version=build["csv_version"],
            bundle_version_key=BUNDLE_VERSION_KEY_VERSION,
            channel=channel,
        )

    def get_latest_build_with_errata_info(self, minor_version: str) -> dict[str, str]:
        """
        Get the latest build with errata for a minor version, regardless of channel.

        Returns the build with the highest version number that has errata,
        preferring stable channel if available for that build, otherwise candidate.
        Does not require the channel to be released to prod (picks up QE builds).

        Args:
            minor_version: Minor version string (e.g., "v4.20")

        Returns:
            Dictionary with version, bundle_version, iib, and channel info
        """
        builds = self.get_builds_with_errata(minor_version)
        build = find_latest_build(builds, lambda b: bool(b.get("errata_status")))
        assert build, "No build with errata found"
        return extract_build_info_with_stable_preference(build, require_released=False)

    def get_latest_candidate_with_stable_fallback_info(self, minor_version: str) -> dict[str, str]:
        """
        Get the latest candidate channel released z-stream info, with stable fallback.

        For Y-stream upgrades: finds the latest candidate released to prod, then checks if
        that same build also has a stable channel available. If so, returns stable info.
        If no candidate is released to prod, falls back to latest build with errata (stable).

        Args:
            minor_version: Minor version string (e.g., "v4.20")

        Returns:
            Dictionary with version, bundle_version, iib, and channel info
        """
        builds = self.get_builds_with_errata(minor_version)

        # Try to find latest candidate released to prod
        build = find_latest_build(builds, lambda b: channel_released_to_prod(b["channels"], CHANNEL_CANDIDATE))

        # If no candidate found, fallback to latest build with errata (typically stable on QE)
        if not build:
            build = find_latest_build(builds, lambda b: bool(b.get("errata_status")))
            require_released = False  # For QE builds, don't require released_to_prod
        else:
            require_released = True  # For production candidate builds, check released_to_prod

        assert build, "No candidate or stable build with errata found"
        return extract_build_info_with_stable_preference(build, require_released=require_released)

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
        build_info = self.get_builds_by_version(version=version, errata_status=ERRATA_STATUS_TRUE)
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


def channel_exists(channels: list[dict[str, str | bool]], channel: str) -> bool:
    """Check if a specific channel exists in the channels list."""
    return any(item.get("channel") == channel for item in channels)


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


def extract_build_info_with_stable_preference(build: dict, require_released: bool = True) -> dict[str, str]:
    """
    Extract channel info from a build, preferring stable channel if available.

    Args:
        build: Build dictionary with channels list
        require_released: If True, only consider channels released to prod.
                         If False, just check if channel exists (useful for QE builds with errata)

    Returns:
        Dictionary with version, bundle_version, iib, and channel info
    """
    if require_released:
        channel = CHANNEL_STABLE if channel_released_to_prod(build["channels"], CHANNEL_STABLE) else CHANNEL_CANDIDATE
    else:
        # For builds not yet released, prefer stable if it exists, otherwise candidate
        channel = CHANNEL_STABLE if channel_exists(build["channels"], CHANNEL_STABLE) else CHANNEL_CANDIDATE

    return extract_channel_info(
        build_data=build, version=build["csv_version"], bundle_version_key=BUNDLE_VERSION_KEY_VERSION, channel=channel
    )


def get_build_info_dict(version: str, channel: str = CHANNEL_STABLE) -> dict[str, str]:
    """Create a simple build info dictionary."""
    return {
        "version": version,
        "channel": channel,
    }
