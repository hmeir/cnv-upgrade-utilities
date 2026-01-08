import json
import logging
import re
from enum import Enum

import click

from cnv_upgrade_utilities.version_explorer_utils import (
    get_latest_candidate_released_z_stream_info,
    get_latest_candidate_with_stable_fallback_info,
    get_latest_stable_released_z_stream_info,
    get_version_explorer_url,
    get_z0_release_info,
)

LOGGER = logging.getLogger(__name__)

# Matches 4.Y (minor version) or 4.Y.0 (for latest-z)
SOURCE_VERSION_PATTERN = re.compile(r"^4\.(0|[1-9]\d*)(\.0)?$")
TARGET_VERSION_PATTERN = re.compile(r"^4\.(0|[1-9]\d*)$")


class UpgradeType(Enum):
    """Upgrade type enumeration."""

    Z_STREAM = "z_stream"
    Y_STREAM = "y_stream"
    LATEST_Z = "latest_z"
    EUS = "eus"


class SourceVersionParamType(click.ParamType):
    """Custom click parameter type for source version validation (4.Y or 4.Y.0 format)."""

    name = "source_version"

    def convert(self, value, param, ctx):
        if not SOURCE_VERSION_PATTERN.match(value):
            self.fail(
                f"Invalid version format: '{value}'. Expected format: 4.Y (e.g., 4.19) or 4.Y.0 for latest-z",
                param,
                ctx,
            )
        return value


class TargetVersionParamType(click.ParamType):
    """Custom click parameter type for target version validation (4.Y format)."""

    name = "target_version"

    def convert(self, value, param, ctx):
        if not TARGET_VERSION_PATTERN.match(value):
            self.fail(
                f"Invalid version format: '{value}'. Expected format: 4.Y (e.g., 4.20)",
                param,
                ctx,
            )
        return value


SOURCE_VERSION_TYPE = SourceVersionParamType()
TARGET_VERSION_TYPE = TargetVersionParamType()


def is_latest_z_source(source_version: str) -> bool:
    """Check if source version is in 4.Y.0 format (latest-z upgrade)."""
    return source_version.endswith(".0")


def parse_minor_version(version: str) -> int:
    """Extract the minor version number from a 4.Y or 4.Y.0 string."""
    return int(version.split(".")[1])


def is_eus_version(minor: int) -> bool:
    """Check if a minor version is EUS-eligible (even number)."""
    return minor % 2 == 0


def determine_upgrade_type(source_version: str, target_version: str) -> UpgradeType:
    """
    Determine the upgrade type based on source and target versions.

    Supported upgrade types:
    - 4.Y.0 -> 4.Y: latest-z (source must target the same Y)
    - 4.Y -> 4.Y: z-stream
    - 4.Y -> 4.Y+1: y-stream
    - 4.Y -> 4.Y+2: EUS (both Y versions must be even)

    Raises:
        ValueError: If the upgrade is unsupported
    """
    source_minor = parse_minor_version(source_version)
    target_minor = parse_minor_version(target_version)

    # Check for latest-z first (source is 4.Y.0)
    if is_latest_z_source(source_version):
        if source_minor != target_minor:
            raise ValueError(
                f"Unsupported upgrade: latest-z upgrade requires same minor version. "
                f"source={source_version}, target={target_version}"
            )
        return UpgradeType.LATEST_Z

    version_diff = target_minor - source_minor

    if version_diff == 0:
        return UpgradeType.Z_STREAM
    elif version_diff == 1:
        return UpgradeType.Y_STREAM
    elif version_diff == 2:
        if is_eus_version(source_minor) and is_eus_version(target_minor):
            return UpgradeType.EUS
        raise ValueError(
            f"Unsupported upgrade: EUS upgrade requires both versions to be even. "
            f"source={source_version} (minor={source_minor}), target={target_version} (minor={target_minor})"
        )

    raise ValueError(f"Unsupported upgrade: source={source_version}, target={target_version}")


def build_result(upgrade_type: UpgradeType, source_info: dict, target_info: dict) -> dict:
    """Build the result dictionary with source and target info."""
    return {
        "upgrade_type": upgrade_type.value,
        "source": {
            "source_version": source_info["version"],
            "bundle_version": source_info["bundle_version"],
            "iib": source_info["iib"],
            "channel": source_info["channel"],
        },
        "target": {
            "source_version": target_info["version"],
            "bundle_version": target_info["bundle_version"],
            "iib": target_info["iib"],
            "channel": target_info["channel"],
        },
    }


def get_z_stream_upgrade_info(source_minor: str, target_minor: str) -> tuple[dict, dict]:
    """
    Get upgrade info for Z-stream upgrade (same minor version).

    Logic:
    1. source: latest stable released to prod
    2. target: latest candidate released to prod
       - If candidate bundle_version matches source's stable, use stable instead
    """
    source_info = get_latest_stable_released_z_stream_info(minor_version=source_minor)
    target_info = get_latest_candidate_released_z_stream_info(minor_version=target_minor)

    # If target's candidate bundle_version matches source's stable, use stable for target
    if target_info["bundle_version"] == source_info["bundle_version"]:
        target_info = get_latest_stable_released_z_stream_info(minor_version=target_minor)

    return source_info, target_info


def get_y_stream_upgrade_info(source_minor: str, target_minor: str) -> tuple[dict, dict]:
    """
    Get upgrade info for Y-stream upgrade (target = source + 1).

    Logic:
    1. source: latest Y-1 stable released to prod
    2. target: latest candidate released to prod, pick its stable if available
    """
    source_info = get_latest_stable_released_z_stream_info(minor_version=source_minor)
    target_info = get_latest_candidate_with_stable_fallback_info(minor_version=target_minor)

    return source_info, target_info


def get_latest_z_upgrade_info(source_minor: str, target_minor: str) -> tuple[dict, dict]:
    """
    Get upgrade info for latest-z upgrade (source is 4.Y.0).

    Logic:
    1. source: 4.Y.0 release info
    2. target: latest candidate released to prod, pick its stable if available
    """
    source_info = get_z0_release_info(minor_version=source_minor)
    target_info = get_latest_candidate_with_stable_fallback_info(minor_version=target_minor)

    return source_info, target_info


def get_eus_upgrade_info(source_minor: str, target_minor: str) -> tuple[dict, dict]:
    """
    Get upgrade info for EUS upgrade (target = source + 2, both even).

    Logic:
    1. source: latest Y stable released to prod
    2. target: latest candidate released to prod, pick its stable if available
    """
    source_info = get_latest_stable_released_z_stream_info(minor_version=source_minor)
    target_info = get_latest_candidate_with_stable_fallback_info(minor_version=target_minor)

    return source_info, target_info


def get_upgrade_jobs_info(source_version: str, target_version: str) -> dict:
    """
    Get upgrade jobs info for source and target versions.

    Args:
        source_version: Source minor version (e.g., "4.19", "4.20", or "4.20.0" for latest-z)
        target_version: Target minor version (e.g., "4.20")

    Returns:
        Dictionary containing upgrade type, source and target lane info
    """
    upgrade_type = determine_upgrade_type(source_version, target_version)

    # For latest-z, source is 4.Y.0 format - extract minor for API calls
    if upgrade_type == UpgradeType.LATEST_Z:
        # Strip .0 suffix to get minor version
        source_minor_num = source_version.rsplit(".0", 1)[0]
        source_minor = f"v{source_minor_num}"
    else:
        source_minor = f"v{source_version}"

    target_minor = f"v{target_version}"

    if upgrade_type == UpgradeType.Z_STREAM:
        source_info, target_info = get_z_stream_upgrade_info(source_minor, target_minor)
    elif upgrade_type == UpgradeType.Y_STREAM:
        source_info, target_info = get_y_stream_upgrade_info(source_minor, target_minor)
    elif upgrade_type == UpgradeType.LATEST_Z:
        source_info, target_info = get_latest_z_upgrade_info(source_minor, target_minor)
    elif upgrade_type == UpgradeType.EUS:
        source_info, target_info = get_eus_upgrade_info(source_minor, target_minor)

    return build_result(upgrade_type, source_info, target_info)


@click.command(help="Get upgrade jobs info for source and target versions")
@click.option(
    "-s",
    "--source-version",
    required=True,
    type=SOURCE_VERSION_TYPE,
    help="Source version: 4.Y for z/y-stream, or 4.Y.0 for latest-z (e.g., 4.19, 4.20.0)",
)
@click.option(
    "-t",
    "--target-version",
    required=True,
    type=TARGET_VERSION_TYPE,
    help="Target minor version in format 4.Y (e.g., 4.20)",
)
def main(source_version: str, target_version: str):
    get_version_explorer_url()  # Validate env var after parsing args so --help works

    result = get_upgrade_jobs_info(source_version, target_version)

    click.echo(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
