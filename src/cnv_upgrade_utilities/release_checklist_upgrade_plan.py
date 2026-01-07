import json
import logging
import re
from dataclasses import dataclass
from enum import Enum

import click
from packaging.version import Version

from cnv_upgrade_utilities.version_explorer_utils import (
    extract_stable_channel_info,
    get_build_info_by_version,
    get_latest_stable_released_z_stream_info,
    get_version_explorer_url,
)

LOGGER = logging.getLogger(__name__)

VERSION_PATTERN = re.compile(r"^4\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
VALID_CHANNELS = ("stable", "candidate")
SKIP_Y_STREAM_UPGRADE_MINORS = {12, 14}


class VersionParamType(click.ParamType):
    """Custom click parameter type for version validation."""

    name = "version"

    def convert(self, value, param, ctx):
        if not VERSION_PATTERN.match(value):
            self.fail(
                f"Invalid version format: '{value}'. Expected format: 4.Y.z (e.g., 4.20.2)",
                param,
                ctx,
            )
        return value


VERSION_TYPE = VersionParamType()


class UpgradeType(Enum):
    """Upgrade type enumeration with associated minor version offset."""

    Y_STREAM = ("Y stream", -1)
    Z_STREAM = ("Z stream", 0)
    EUS = ("EUS", -2)
    LATEST_Z = ("latest z", None)

    def __init__(self, display_name: str, minor_offset: int | None):
        self.display_name = display_name
        self.minor_offset = minor_offset


@dataclass
class UpgradeConfig:
    upgrade_type: UpgradeType
    post_upgrade_suite: str


@dataclass
class VersionCategory:
    version_pattern: str
    upgrade_configs: list[UpgradeConfig]


# Data-driven configuration mapping z-stream values to upgrade configurations
VERSION_CATEGORIES = {
    0: VersionCategory(
        version_pattern="4.Y.0",
        upgrade_configs=[
            UpgradeConfig(UpgradeType.Y_STREAM, post_upgrade_suite="UTS-FULL"),
        ],
    ),
    1: VersionCategory(
        version_pattern="4.Y.1",
        upgrade_configs=[
            UpgradeConfig(UpgradeType.Y_STREAM, post_upgrade_suite="UTS-FULL"),
            UpgradeConfig(UpgradeType.Z_STREAM, post_upgrade_suite="UTS-Marker"),
        ],
    ),
}

# Default category for z >= 2
DEFAULT_CATEGORY = VersionCategory(
    version_pattern="4.Y.2+",
    upgrade_configs=[
        UpgradeConfig(UpgradeType.Y_STREAM, post_upgrade_suite="UTS-Marker"),
        UpgradeConfig(UpgradeType.Z_STREAM, post_upgrade_suite="NONE"),
        UpgradeConfig(UpgradeType.LATEST_Z, post_upgrade_suite="NONE"),
    ],
)


def create_upgrade_entry(config: UpgradeConfig, build_info: dict) -> dict:
    """Create upgrade type dictionary entry."""
    return {
        "source_version": build_info.get("version"),
        "bundle_version": build_info.get("bundle_version"),
        "iib": build_info.get("iib"),
        "channel": build_info.get("channel"),
        "post_upgrade_suite": config.post_upgrade_suite,
    }


def fetch_source_version(target_version: Version, minor_offset: int | None = None) -> dict | None:
    """
    Fetch latest stable source version info for given minor offset.

    Args:
        target_version: Target version to upgrade to
        minor_offset: Offset to apply when fetching source version

    Returns:
        Source version info dict if found, None otherwise
    """
    if minor_offset is None:
        version = f"{target_version.major}.{target_version.minor}.0"
        # For "latest z" type, return minimal info
        build_info = get_build_info_by_version(version=version, errata_status="true")["successful_builds"][0]
        source_info = extract_stable_channel_info(
            build_data=build_info, version=version, bundle_version_key="cnv_build"
        )
    else:
        minor = f"v{target_version.major}.{target_version.minor + minor_offset}"
        source_info = get_latest_stable_released_z_stream_info(minor_version=minor)
    return source_info


def categorize_version(target_version: Version) -> dict:
    """
    Categorize version and return upgrade type info.

    Uses data-driven configuration to determine upgrade types based on
    the z-stream value and whether the version is EUS-eligible.

    Args:
        target_version: Version object to categorize

    Returns:
        Dictionary containing target version, version type, and upgrade configurations
    """
    z, y = target_version.micro, target_version.minor

    # Get category configuration
    upgrade_configs = list(VERSION_CATEGORIES.get(z, DEFAULT_CATEGORY).upgrade_configs)

    # Filter out Y_STREAM for specific versions (e.g., 4.12, 4.14)
    if y in SKIP_Y_STREAM_UPGRADE_MINORS:
        upgrade_configs = [config for config in upgrade_configs if config.upgrade_type != UpgradeType.Y_STREAM]

    # Add EUS upgrade for even minor versions at z=0
    if z == 0 and y % 2 == 0:
        upgrade_configs.append(UpgradeConfig(UpgradeType.EUS, post_upgrade_suite="UTS-Marker"))

    # Build upgrade entries with source versions
    upgrade_lanes = {
        config.upgrade_type.display_name: create_upgrade_entry(
            config, fetch_source_version(target_version, config.upgrade_type.minor_offset)
        )
        for config in upgrade_configs
    }
    return {
        "target_version": target_version,
        "upgrade_lanes": upgrade_lanes,
    }


@click.command(help="Upgrade release checklist tool")
@click.option(
    "-v", "--target-version", required=True, type=VERSION_TYPE, help="Target version in format 4.Y.z (e.g., 4.20.2)"
)
@click.option(
    "-c",
    "--channel",
    type=click.Choice(VALID_CHANNELS),
    default="stable",
    help="Release channel: stable or candidate (default: stable)",
)
def main(target_version: str, channel: str):
    get_version_explorer_url()  # Validate env var after parsing args so --help works

    version_info = categorize_version(Version(target_version))

    click.echo(json.dumps(version_info, indent=2, default=str))


if __name__ == "__main__":
    main()
