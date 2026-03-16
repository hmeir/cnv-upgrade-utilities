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
    ERRATA_STATUS_FALSE,
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

    def get_successful_builds_by_version(
        self,
        version: str,
        errata_status: str = ERRATA_STATUS_TRUE,
        max_entries: int | None = None,
    ) -> list[dict]:
        """
        Get all successful builds for a version.

        Args:
            version: Version string (e.g., "4.20.3")
            errata_status: Filter by errata status (default: "true")
            max_entries: Maximum number of builds to return (optional)

        Returns:
            List of build dictionaries
        """
        query_string = f"version={version}&errata_status={errata_status}"
        if max_entries is not None:
            query_string += f"&max_entries={max_entries}"
        return self.query_with_retry(
            endpoint="GetSuccessfulBuildsByVersion",
            query_string=query_string,
        )["successful_builds"]

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

    # --- Specific Version Methods ---

    def get_build_info(self, bundle_version: str) -> dict:
        """
        Get build information by bundle version (4.Y.Z.rhelR-BN format).

        Uses the GetBuildInfo API endpoint.

        Args:
            bundle_version: Bundle version string (e.g., "4.20.3.rhel9-31")

        Returns:
            Dictionary with build info including cnv_version, current_channel,
            channels array, and errata_status
        """
        # Prepend 'v' if not present (API expects v4.20.3.rhel9-31)
        version_param = bundle_version if bundle_version.startswith("v") else f"v{bundle_version}"

        return self.query_with_retry(
            endpoint="GetBuildInfo",
            query_string=f"version={version_param}",
        )

    def get_version_builds_info(
        self,
        version: str,
        stable_required: bool,
        require_released_to_prod: bool = False,
    ) -> dict[str, str]:
        """
        Get build info for a specific version (X.Y.Z format).

        Queries up to 20 builds with errata_status=false, then selects the
        best build based on channel requirements.

        Args:
            version: Full version string (e.g., "4.20.3")
            stable_required: Whether stable channel is mandatory
            require_released_to_prod: Whether the stable channel must be released to prod

        Returns:
            Dictionary with version, bundle_version, iib, and channel

        Raises:
            ValueError: If channel requirements are not met
        """
        builds = self.get_successful_builds_by_version(
            version=version, errata_status=ERRATA_STATUS_FALSE, max_entries=20
        )
        return select_build_by_channel(
            builds=builds,
            version=version,
            stable_required=stable_required,
            require_released_to_prod=require_released_to_prod,
        )

    def get_version_range_builds_info(
        self,
        start_version: str,
        stop_version: str,
        stable_required: bool,
        require_released_to_prod: bool = False,
    ) -> dict[str, str]:
        """
        Get build info by searching a range of versions from start down to stop.

        Decrements the patch number from start_version to stop_version (inclusive).
        For each version, queries up to 20 builds with errata_status=false.
        The first version with builds is used, then channel selection is applied.

        Args:
            start_version: Highest version to try (e.g., "4.20.10")
            stop_version: Lowest version to try, inclusive (e.g., "4.20.7")
            stable_required: Whether stable channel is mandatory
            require_released_to_prod: Whether the stable channel must be released to prod

        Returns:
            Dictionary with version, bundle_version, iib, and channel

        Raises:
            ValueError: If no builds found across the entire range, or channel requirements not met
        """
        start_parts = start_version.split(".")
        stop_patch = int(stop_version.split(".")[2])
        base = f"{start_parts[0]}.{start_parts[1]}"
        start_patch = int(start_parts[2])

        for patch in range(start_patch, stop_patch - 1, -1):
            version = f"{base}.{patch}"
            LOGGER.info(f"Trying version {version}...")
            builds = self.get_successful_builds_by_version(
                version=version, errata_status=ERRATA_STATUS_FALSE, max_entries=20
            )
            if not builds:
                LOGGER.info(f"No builds found for version {version}, trying next...")
                continue
            LOGGER.info(f"Found {len(builds)} build(s) for version {version}")
            try:
                return select_build_by_channel(
                    builds=builds,
                    version=version,
                    stable_required=stable_required,
                    require_released_to_prod=require_released_to_prod,
                )
            except ValueError:
                LOGGER.info(f"No matching channel for version {version}, trying next...")

        raise ValueError(f"No builds with matching channel found in version range {start_version} to {stop_version}")

    def get_bundle_version_info(
        self,
        bundle_version: str,
        required_channel: str | None = None,
        prefer_stable: bool = True,
    ) -> dict[str, str]:
        """
        Get build info for a specific bundle version (X.Y.Z.rhelR-BN format).

        Uses GetBuildInfo API and extracts appropriate channel info.

        Args:
            bundle_version: Bundle version string (e.g., "4.20.3.rhel9-31")
            required_channel: If set, require this channel (raise error if not found)
            prefer_stable: If True and required_channel is None, prefer stable over candidate

        Returns:
            Dictionary with version, bundle_version, iib, and channel

        Raises:
            ValueError: If required_channel is specified but not available
        """
        build_info = self.get_build_info(bundle_version)

        # Extract base version from cnv_version (e.g., "v4.20.3.rhel9-31" -> "4.20.3")
        cnv_version = build_info["cnv_version"]
        base_version = cnv_version.lstrip("v").rsplit(".rhel", 1)[0]

        channels = build_info.get("channels", [])

        if required_channel:
            if not channel_exists(channels, required_channel):
                raise ValueError(
                    f"Bundle version {bundle_version} does not have {required_channel} channel "
                    f"required for this upgrade type"
                )
            channel = required_channel
        elif prefer_stable and channel_exists(channels, CHANNEL_STABLE):
            channel = CHANNEL_STABLE
        elif channel_exists(channels, CHANNEL_CANDIDATE):
            channel = CHANNEL_CANDIDATE
        else:
            channel = CHANNEL_STABLE  # Default to stable

        # Find the channel info
        channel_info = next((ch for ch in channels if ch.get("channel") == channel), None)
        if not channel_info:
            raise ValueError(f"Channel {channel} not found in build info for {bundle_version}")

        return {
            "version": base_version,
            "bundle_version": cnv_version.lstrip("v"),
            "iib": channel_info["iib"],
            "channel": channel,
        }


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


def select_build_by_channel(
    builds: list[dict],
    version: str,
    stable_required: bool,
    require_released_to_prod: bool = False,
) -> dict[str, str]:
    """
    Select the best build from a list based on channel requirements.

    Iterates builds looking for a stable channel first. The stable check can
    optionally require the channel to be released to prod (for source versions).

    If no stable channel found:
    - stable_required=True: raises ValueError (Y-stream/EUS targets, all sources)
    - stable_required=False: falls back to the first build with a candidate channel

    Args:
        builds: List of build dictionaries from GetSuccessfulBuildsByVersion
        version: Version string (e.g., "4.20.3") for the result dict
        stable_required: If True, raises ValueError when no stable channel is found
        require_released_to_prod: If True, stable channel must also be released to prod

    Returns:
        Dictionary with version, bundle_version, iib, and channel

    Raises:
        ValueError: If channel requirements are not met
    """
    stable_check = channel_released_to_prod if require_released_to_prod else channel_exists

    for build in builds:
        if stable_check(build.get("channels", []), CHANNEL_STABLE):
            return extract_channel_info(
                build_data=build,
                version=version,
                bundle_version_key=BUNDLE_VERSION_KEY_CNV_BUILD,
                channel=CHANNEL_STABLE,
            )

    if stable_required:
        detail = "released to prod " if require_released_to_prod else ""
        raise ValueError(f"No stable channel {detail}found for version {version}")

    for build in builds:
        if channel_exists(build.get("channels", []), CHANNEL_CANDIDATE):
            return extract_channel_info(
                build_data=build,
                version=version,
                bundle_version_key=BUNDLE_VERSION_KEY_CNV_BUILD,
                channel=CHANNEL_CANDIDATE,
            )

    raise ValueError(f"No stable or candidate channel found for version {version}")


def get_build_info_dict(version: str, channel: str = CHANNEL_STABLE) -> dict[str, str]:
    """Create a simple build info dictionary."""
    return {
        "version": version,
        "channel": channel,
    }
