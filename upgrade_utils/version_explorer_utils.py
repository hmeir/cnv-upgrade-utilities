import os
import requests
from requests.exceptions import HTTPError, ConnectionError, Timeout, TooManyRedirects
from typing import Any
import logging
from timeout_sampler import TimeoutExpiredError, TimeoutSampler, retry
from functools import cache
from packaging.version import Version

LOGGER = logging.getLogger(__name__)

TIMEOUT_2MIN = 120
TIMEOUT_30SEC = 30


@cache
def get_version_explorer_url():
    """Get the version explorer URL, cached for reuse."""
    version_explorer_url = os.environ.get('VERSION_EXPLORER_URL')
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


def get_latest_stable_released_z_stream_info(minor_version: str) -> dict[str, str] | None:
    builds = wait_for_version_explorer_response(
        api_end_point="GetBuildsWithErrata",
        query_string=f"minor_version={minor_version}",
    )["builds"]

    latest_z_stream = None
    for build in builds:
        if build["errata_status"] == "SHIPPED_LIVE" and stable_channel_released_to_prod(channels=build["channels"]):
            build_version = Version(version=build["csv_version"])
            if latest_z_stream:
                if build_version > latest_z_stream:
                    latest_z_stream = build_version
            else:
                latest_z_stream = build_version
    return get_build_info_dict(version=str(latest_z_stream)) if latest_z_stream else None


def get_cnv_info_by_iib(iib: str) -> dict[str, str]:
    build_info = wait_for_version_explorer_response(
        api_end_point="GetBuildByIIB",
        query_string=f"iib_number={iib}",
    )
    return get_build_info_dict(
        version=str(Version(build_info["cnv_version"].split(".rhel9")[0])),
        channel=build_info["channel"],
    )


def get_build_info_dict(version: str, channel: str = "stable") -> dict[str, str]:
    return {
        "version": version,
        "channel": channel,
    }
