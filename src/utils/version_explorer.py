"""Version Explorer API client."""

import logging
import os
from typing import Any

import requests
from requests.exceptions import ConnectionError, HTTPError, Timeout, TooManyRedirects
from timeout_sampler import TimeoutSampler

from utils.constants import DEFAULT_VERSION_EXPLORER_URL, ENV_VERSION_EXPLORER_URL
from utils.models import BuildInfo, ReleasedBuild, SuccessfulBuild

LOGGER = logging.getLogger(__name__)

DEFAULT_REQUEST_TIMEOUT = 30
DEFAULT_RETRY_TIMEOUT = 120


class CnvVersionExplorer:
    """
    Client for interacting with the Version Explorer API.

    Provides methods to query build information, upgrade paths, and release data.
    Uses a requests Session for connection pooling and retry logic.

    Usage:
        with CnvVersionExplorer() as explorer:
            builds = explorer.get_released_builds("v4.20")
    """

    def __init__(
        self,
        url: str | None = None,
        request_timeout: int = DEFAULT_REQUEST_TIMEOUT,
        retry_timeout: int = DEFAULT_RETRY_TIMEOUT,
    ):
        self._url = url or os.environ.get(ENV_VERSION_EXPLORER_URL) or DEFAULT_VERSION_EXPLORER_URL
        self.request_timeout = request_timeout
        self.retry_timeout = retry_timeout
        self._session: requests.Session | None = None

    @property
    def url(self) -> str:
        return self._url

    @property
    def session(self) -> requests.Session:
        if self._session is None:
            self._session = requests.Session()
            self._session.verify = False
        return self._session

    def close(self) -> None:
        if self._session is not None:
            self._session.close()
            self._session = None

    def __enter__(self) -> "CnvVersionExplorer":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"CnvVersionExplorer(url='{self._url}')"

    def query(self, endpoint: str, query_string: str) -> Any | None:
        """Execute a single API query."""
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
        """Execute an API query with retry logic."""
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

    def get_released_builds(self, minor_version: str, stage: bool = False) -> list[ReleasedBuild]:
        """Fetch released builds for a minor version."""
        stage_str = "true" if stage else "false"
        raw = self.query_with_retry(
            endpoint="GetReleasedBuilds",
            query_string=f"minor_version={minor_version}&stage={stage_str}",
        )["builds"]
        return [ReleasedBuild.model_validate(b) for b in raw]

    def get_successful_builds_by_version(
        self,
        version: str,
        max_entries: int | None = None,
        channel: str | None = None,
        stage: bool | None = None,
    ) -> list[SuccessfulBuild]:
        """Get successful builds (passed smoke tests) for a specific X.Y.Z version."""
        query_string = f"version={version}"
        if max_entries is not None:
            query_string += f"&max_entries={max_entries}"
        if channel is not None:
            query_string += f"&channel={channel}"
        if stage is not None:
            query_string += f"&stage={'true' if stage else 'false'}"
        raw = self.query_with_retry(
            endpoint="GetSuccessfulBuildsByVersion",
            query_string=query_string,
        )["successful_builds"]
        return [SuccessfulBuild.model_validate(b) for b in raw]

    def get_build_info(self, bundle_version: str) -> BuildInfo:
        """Get build information by bundle version (4.Y.Z.rhelR-BN format)."""
        version_param = bundle_version if bundle_version.startswith("v") else f"v{bundle_version}"
        result = self.query_with_retry(
            endpoint="GetBuildInfo",
            query_string=f"version={version_param}",
        )
        build_info = BuildInfo.model_validate(result)
        if build_info.error:
            raise ValueError(f"Build not found: {bundle_version}. Check if the build exists in CNV Version Explorer.")
        return build_info
