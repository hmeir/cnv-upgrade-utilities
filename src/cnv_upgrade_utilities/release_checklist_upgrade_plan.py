import json
import logging
from dataclasses import dataclass

import click
from packaging.version import Version

from cnv_upgrade_utilities.utils import FULL_VERSION_TYPE
from utils.constants import (
    BUNDLE_VERSION_KEY_CNV_BUILD,
    CHANNEL_STABLE,
    ERRATA_STATUS_TRUE,
    POST_UPGRADE_SUITE_FULL,
    POST_UPGRADE_SUITE_MARKER,
    POST_UPGRADE_SUITE_NONE,
    SKIP_Y_STREAM_UPGRADE_MINORS,
    VALID_CHANNELS,
    UpgradeType,
)
from utils.version_explorer import CnvVersionExplorer, extract_stable_channel_info

LOGGER = logging.getLogger(__name__)


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
            UpgradeConfig(UpgradeType.Y_STREAM, post_upgrade_suite=POST_UPGRADE_SUITE_FULL),
        ],
    ),
    1: VersionCategory(
        version_pattern="4.Y.1",
        upgrade_configs=[
            UpgradeConfig(UpgradeType.Y_STREAM, post_upgrade_suite=POST_UPGRADE_SUITE_FULL),
            UpgradeConfig(UpgradeType.Z_STREAM, post_upgrade_suite=POST_UPGRADE_SUITE_MARKER),
        ],
    ),
}

# Default category for z >= 2
DEFAULT_CATEGORY = VersionCategory(
    version_pattern="4.Y.2+",
    upgrade_configs=[
        UpgradeConfig(UpgradeType.Y_STREAM, post_upgrade_suite=POST_UPGRADE_SUITE_MARKER),
        UpgradeConfig(UpgradeType.Z_STREAM, post_upgrade_suite=POST_UPGRADE_SUITE_NONE),
        UpgradeConfig(UpgradeType.LATEST_Z, post_upgrade_suite=POST_UPGRADE_SUITE_NONE),
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


def fetch_source_version(
    explorer: CnvVersionExplorer, target_version: Version, minor_offset: int | None = None
) -> dict | None:
    """
    Fetch latest stable source version info for given minor offset.

    Args:
        explorer: CnvVersionExplorer instance
        target_version: Target version to upgrade to
        minor_offset: Offset to apply when fetching source version

    Returns:
        Source version info dict if found, None otherwise
    """
    if minor_offset is None:
        version = f"{target_version.major}.{target_version.minor}.0"
        # For "latest z" type, return minimal info
        build_info = explorer.get_builds_by_version(version=version, errata_status=ERRATA_STATUS_TRUE)[
            "successful_builds"
        ][0]
        source_info = extract_stable_channel_info(
            build_data=build_info, version=version, bundle_version_key=BUNDLE_VERSION_KEY_CNV_BUILD
        )
    else:
        minor = f"v{target_version.major}.{target_version.minor + minor_offset}"
        source_info = explorer.get_latest_stable_released_z_stream_info(minor_version=minor)
    return source_info


def categorize_version(explorer: CnvVersionExplorer, target_version: Version) -> dict:
    """
    Categorize version and return upgrade type info.

    Uses data-driven configuration to determine upgrade types based on
    the z-stream value and whether the version is EUS-eligible.

    Args:
        explorer: CnvVersionExplorer instance
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
        upgrade_configs.append(UpgradeConfig(UpgradeType.EUS, post_upgrade_suite=POST_UPGRADE_SUITE_MARKER))

    # Build upgrade entries with source versions
    upgrade_lanes = {
        config.upgrade_type.display_name: create_upgrade_entry(
            config, fetch_source_version(explorer, target_version, config.upgrade_type.minor_offset)
        )
        for config in upgrade_configs
    }
    return {
        "target_version": target_version,
        "upgrade_lanes": upgrade_lanes,
    }


@click.command(help="Upgrade release checklist tool")
@click.option(
    "-v",
    "--target-version",
    required=True,
    type=FULL_VERSION_TYPE,
    help="Target version in format 4.Y.z (e.g., 4.20.2)",
)
@click.option(
    "-c",
    "--channel",
    type=click.Choice(VALID_CHANNELS),
    default=CHANNEL_STABLE,
    help="Release channel: stable or candidate (default: stable)",
)
def main(target_version: str, channel: str):
    with CnvVersionExplorer() as explorer:
        version_info = categorize_version(explorer, Version(target_version))

        click.echo(json.dumps(version_info, indent=2, default=str))


if __name__ == "__main__":
    main()
