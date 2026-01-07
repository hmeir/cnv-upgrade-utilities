import re
import json
import logging
from enum import Enum

import click
from cnv_upgrade_utilities.version_explorer_utils import (
    get_latest_stable_released_z_stream_info,
    get_latest_candidate_released_z_stream_info,
    get_latest_candidate_with_stable_fallback_info,
    get_version_explorer_url,
)

LOGGER = logging.getLogger(__name__)

MINOR_VERSION_PATTERN = re.compile(r"^4\.(0|[1-9]\d*)$")


class UpgradeType(Enum):
    """Upgrade type enumeration."""
    Z_STREAM = "z_stream"
    Y_STREAM = "y_stream"
    UNSUPPORTED = "unsupported"


class MinorVersionParamType(click.ParamType):
    """Custom click parameter type for minor version validation (4.Y format)."""
    name = "minor_version"

    def convert(self, value, param, ctx):
        if not MINOR_VERSION_PATTERN.match(value):
            self.fail(
                f"Invalid version format: '{value}'. Expected format: 4.Y (e.g., 4.19, 4.20)",
                param,
                ctx,
            )
        return value


MINOR_VERSION_TYPE = MinorVersionParamType()


def parse_minor_version(version: str) -> int:
    """Extract the minor version number from a 4.Y string."""
    return int(version.split(".")[1])


def determine_upgrade_type(source_version: str, target_version: str) -> UpgradeType:
    """Determine the upgrade type based on source and target versions."""
    source_minor = parse_minor_version(source_version)
    target_minor = parse_minor_version(target_version)
    
    version_diff = target_minor - source_minor
    
    if version_diff == 0:
        return UpgradeType.Z_STREAM
    elif version_diff == 1:
        return UpgradeType.Y_STREAM


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


def get_upgrade_jobs_info(source_version: str, target_version: str) -> dict:
    """
    Get upgrade jobs info for source and target versions.

    Args:
        source_version: Source minor version (e.g., "4.19")
        target_version: Target minor version (e.g., "4.20")

    Returns:
        Dictionary containing upgrade type, source and target lane info
    """
    source_minor = f"v{source_version}"
    target_minor = f"v{target_version}"

    upgrade_type = determine_upgrade_type(source_version, target_version)

    if upgrade_type == UpgradeType.Z_STREAM:
        source_info, target_info = get_z_stream_upgrade_info(source_minor, target_minor)
    elif upgrade_type == UpgradeType.Y_STREAM:
        source_info, target_info = get_y_stream_upgrade_info(source_minor, target_minor)
    else:
        raise ValueError(f"Unsupported upgrade: source={source_version}, target={target_version}")

    return build_result(upgrade_type, source_info, target_info)


@click.command(help="Get upgrade jobs info for source and target versions")
@click.option(
    "-s", "--source-version",
    required=True,
    type=MINOR_VERSION_TYPE,
    help="Source minor version in format 4.Y (e.g., 4.19)"
)
@click.option(
    "-t", "--target-version",
    required=True,
    type=MINOR_VERSION_TYPE,
    help="Target minor version in format 4.Y (e.g., 4.20)"
)
def main(source_version: str, target_version: str):
    get_version_explorer_url()  # Validate env var after parsing args so --help works

    result = get_upgrade_jobs_info(source_version, target_version)

    click.echo(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

