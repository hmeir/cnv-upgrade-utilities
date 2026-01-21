import json
import logging
from dataclasses import asdict, dataclass

import click
from packaging.version import Version

from cnv_upgrade_utilities.utils import FULL_VERSION_TYPE, get_applicable_upgrade_types
from utils.constants import (
    BUNDLE_VERSION_KEY_CNV_BUILD,
    CHANNEL_STABLE,
    ERRATA_STATUS_TRUE,
    VALID_CHANNELS,
    get_post_upgrade_suite,
)
from utils.version_explorer import CnvVersionExplorer, extract_channel_info

LOGGER = logging.getLogger(__name__)


@dataclass
class UpgradeEntry:
    source_version: str | None
    bundle_version: str | None
    iib: str | None
    channel: str | None
    post_upgrade_suite: str


def create_upgrade_entry(build_info: dict, post_upgrade_suite: str) -> UpgradeEntry:
    """Create upgrade entry from build info and post_upgrade_suite."""
    return UpgradeEntry(
        source_version=build_info.get("version"),
        bundle_version=build_info.get("bundle_version"),
        iib=build_info.get("iib"),
        channel=build_info.get("channel"),
        post_upgrade_suite=post_upgrade_suite,
    )


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
        source_info = extract_channel_info(
            build_data=build_info,
            version=version,
            bundle_version_key=BUNDLE_VERSION_KEY_CNV_BUILD,
            channel=CHANNEL_STABLE,
        )
    else:
        minor = f"v{target_version.major}.{target_version.minor + minor_offset}"
        source_info = explorer.get_latest_released_z_stream_info(minor_version=minor, channel=CHANNEL_STABLE)
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
    y, z = target_version.minor, target_version.micro

    # Get all applicable upgrade types for this version
    upgrade_types = get_applicable_upgrade_types(target_minor=y, target_z=z)

    # Build upgrade entries with source versions
    upgrade_lanes = {
        upgrade_type.display_name: asdict(
            create_upgrade_entry(
                build_info=fetch_source_version(explorer, target_version, upgrade_type.minor_offset),
                post_upgrade_suite=get_post_upgrade_suite(upgrade_type, z),
            )
        )
        for upgrade_type in upgrade_types
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
