"""Version Explorer API client and utilities."""

import logging
import os
from typing import Any

import requests
from requests.exceptions import ConnectionError, HTTPError, Timeout, TooManyRedirects
from timeout_sampler import TimeoutSampler

from utils.constants import CHANNEL_STABLE, ENV_VERSION_EXPLORER_URL

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
            builds = explorer.get_released_builds("v4.20")

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
            endpoint: API endpoint name (e.g., "GetReleasedBuilds")
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

    def get_released_builds(self, minor_version: str, stage: bool = False) -> list[dict]:
        """
        Fetch released builds for a minor version.

        Returns all X.Y.Z builds that are either released to prod or in stage.
        - stage=False: returns only builds released to prod (candidate/stable channels
          with released_to_prod=true).
        - stage=True: also includes builds currently in stage (candidate/stable channels
          with in_stage=true), i.e. builds that are candidates for release but not yet on prod.

        A build's channel can have both in_stage and released_to_prod as true simultaneously.

        Args:
            minor_version: Minor version string (e.g., "v4.20" or "4.20")
            stage: If True, include builds in stage in addition to prod builds.
                   If False, only return builds released to prod.

        Returns:
            List of build dictionaries, each containing version, csv_version,
            current_channel, channels (with iib, fbc_snapshot, released_to_prod,
            in_stage info), replaces, skips, skipRange, and build_timestamp.
        """
        stage_str = "true" if stage else "false"
        return self.query_with_retry(
            endpoint="GetReleasedBuilds",
            query_string=f"minor_version={minor_version}&stage={stage_str}",
        )["builds"]

    def get_successful_builds_by_version(
        self,
        version: str,
        max_entries: int | None = None,
        channel: str | None = None,
        stage: bool | None = None,
    ) -> list[dict]:
        """
        Get successful builds (passed smoke tests) for a specific X.Y.Z version.

        Returns the latest builds that passed smoke tests for the given version.
        Results can be filtered by channel and/or stage status.

        Args:
            version: Version string (e.g., "4.21.3")
            max_entries: Maximum number of builds to return (default: 5 on server side)
            channel: Filter by channel - "stable", "candidate", "nightly",
                     "dev-preview", or None for all channels
            stage: If True, only return builds in stage. If False, only builds
                   not in stage. If None, no stage filtering.

        Returns:
            List of build dictionaries that passed smoke tests
        """
        query_string = f"version={version}"
        if max_entries is not None:
            query_string += f"&max_entries={max_entries}"
        if channel is not None:
            query_string += f"&channel={channel}"
        if stage is not None:
            query_string += f"&stage={'true' if stage else 'false'}"
        return self.query_with_retry(
            endpoint="GetSuccessfulBuildsByVersion",
            query_string=query_string,
        )["successful_builds"]

    def get_build_info(self, bundle_version: str) -> dict:
        """
        Get build information by bundle version (4.Y.Z.rhelR-BN format).

        Uses the GetBuildInfo API endpoint.

        Args:
            bundle_version: Bundle version string (e.g., "4.20.3.rhel9-31")

        Returns:
            Dictionary with build info including cnv_version, current_channel,
            and channels array

        Raises:
            ValueError: If the build is not found in Version Explorer
        """
        version_param = bundle_version if bundle_version.startswith("v") else f"v{bundle_version}"
        result = self.query_with_retry(
            endpoint="GetBuildInfo",
            query_string=f"version={version_param}",
        )
        if "error" in result:
            raise ValueError(f"Build not found: {bundle_version}. Check if the build exists in CNV Version Explorer.")
        return result


# --- Helper functions (stateless, no API dependency) ---


def channel_released_to_prod(channels: list[dict[str, str | bool]], channel: str) -> bool:
    """Check if a specific channel is released to prod."""
    return any(item.get("channel") == channel and item.get("released_to_prod") for item in channels)


def channel_in_stage(channels: list[dict[str, str | bool]], channel: str) -> bool:
    """Check if a specific channel has in_stage=true (may also be released to prod)."""
    return any(item.get("channel") == channel and item.get("in_stage") for item in channels)


def channel_exists(channels: list[dict[str, str | bool]], channel: str) -> bool:
    """Check if a specific channel exists in the channels list."""
    return any(item.get("channel") == channel for item in channels)


def build_info_dict(
    version: str, bundle_version: str, iib: str, channel: str, extra: dict | None = None
) -> dict[str, str]:
    """
    Build a standardized build info result dictionary.

    Args:
        version: X.Y.Z version string (without 'v' prefix)
        bundle_version: Full bundle version (e.g., "4.21.2.rhel9-23", without 'v' prefix)
        iib: IIB registry URL
        channel: Channel name (e.g., "stable", "candidate")
        extra: Optional dict to pull in_stage and released_to_prod from

    Returns:
        Dictionary with version, bundle_version, iib, channel, and optionally
        in_stage and released_to_prod
    """
    result = {
        "version": version,
        "bundle_version": bundle_version,
        "iib": iib,
        "channel": channel,
    }
    if extra:
        if "in_stage" in extra:
            result["in_stage"] = extra["in_stage"]
        if "released_to_prod" in extra:
            result["released_to_prod"] = extra["released_to_prod"]
    return result


def extract_filtered_build_info(build: dict, version: str) -> dict[str, str]:
    """
    Extract build info from a GetSuccessfulBuildsByVersion response entry
    when a channel filter was used (flat response with no nested 'channels' array).
    """
    return build_info_dict(
        version=version,
        bundle_version=build["cnv_build"].lstrip("v"),
        iib=build["iib"],
        channel=build["channel"],
        extra=build,
    )


def extract_released_build_info(build: dict, channel: str) -> dict[str, str]:
    """
    Extract build info from a GetReleasedBuilds response entry.

    Uses 'csv_version' for X.Y.Z and 'version' for the full bundle version,
    both with 'v' prefix in the API response.
    """
    channel_info = get_channel_info(channels=build.get("channels", []), channel=channel)
    return build_info_dict(
        version=build["csv_version"].lstrip("v"),
        bundle_version=build["version"].lstrip("v"),
        iib=channel_info["iib"],
        channel=channel,
        extra=channel_info,
    )


def extract_build_info_result(build_info: dict, channel: str) -> dict[str, str]:
    """
    Extract build info from a GetBuildInfo response.

    Uses 'cnv_version' for the full bundle version (e.g., "v4.21.2.rhel9-23").
    """
    cnv_version = build_info["cnv_version"]
    channel_info = get_channel_info(channels=build_info.get("channels", []), channel=channel)
    return build_info_dict(
        version=cnv_version.lstrip("v").rsplit(".rhel", 1)[0],
        bundle_version=cnv_version.lstrip("v"),
        iib=channel_info["iib"],
        channel=channel,
        extra=channel_info,
    )


def find_stable_stage_build(explorer: "CnvVersionExplorer", version: str) -> dict[str, str] | None:
    """
    Find a stable build in stage (not yet released to prod) for a specific X.Y.Z version.

    Uses GetSuccessfulBuildsByVersion with channel=stable, stage=true, then filters
    out builds already released to prod.

    Returns:
        Build info dict, or None if no matching build found.
    """

    builds = explorer.get_successful_builds_by_version(version=version, channel=CHANNEL_STABLE, stage=True)
    for build in builds:
        if not build.get("released_to_prod"):
            return extract_filtered_build_info(build=build, version=version)
    return None


def find_released_source(
    explorer: "CnvVersionExplorer",
    minor_version: str,
    required_csv: str | None = None,
    exclude_csv: str | None = None,
) -> dict[str, str]:
    """
    Find the latest stable build released to prod for a minor version.

    Uses GetReleasedBuilds with stage=false, iterates to find the first build
    with stable channel released to prod.

    Args:
        explorer: CnvVersionExplorer instance
        minor_version: v-prefixed minor version (e.g., "v4.20")
        required_csv: If set, only match builds with this csv_version (e.g., "v4.20.0" for Latest-Z)
        exclude_csv: If set, skip builds matching this csv_version (e.g., to avoid source=target)

    Returns:
        Build info dict with version, bundle_version, iib, and channel

    Raises:
        ValueError: If no matching build found
    """
    builds = explorer.get_released_builds(minor_version=minor_version, stage=False)
    if not builds:
        raise ValueError(f"No released builds found for {minor_version}")

    for build in builds:
        csv_version = build.get("csv_version", "")
        if required_csv and csv_version != required_csv:
            continue
        if exclude_csv and csv_version.lstrip("v") == exclude_csv.lstrip("v"):
            continue
        channels = build.get("channels", [])
        if channel_released_to_prod(channels=channels, channel=CHANNEL_STABLE):
            return extract_released_build_info(build=build, channel=CHANNEL_STABLE)

    if required_csv:
        raise ValueError(f"No stable build released to prod found for source version {required_csv.lstrip('v')}")
    raise ValueError(f"No stable build released to prod found for source {minor_version}")


def get_channel_info(channels: list[dict[str, str | bool]], channel: str) -> dict[str, str | bool]:
    """
    Find and return the channel info dict for a specific channel.

    Args:
        channels: List of channel dictionaries
        channel: Channel name to find (e.g., "stable", "candidate")

    Returns:
        The channel info dictionary

    Raises:
        ValueError: If the channel is not found
    """
    for ch in channels:
        if ch.get("channel") == channel:
            return ch
    raise ValueError(f"Channel '{channel}' not found in channels list")
