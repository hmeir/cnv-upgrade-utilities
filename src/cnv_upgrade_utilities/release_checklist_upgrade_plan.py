import json
import logging
from dataclasses import asdict, dataclass

import click
from packaging.version import Version

from cnv_upgrade_utilities.utils import (
    FULL_VERSION_TYPE,
    MINOR_VERSION_SEARCH_RANGE,
    get_applicable_upgrade_types,
    get_post_upgrade_suite,
)
from utils.constants import CHANNEL_STABLE, VALID_CHANNELS
from utils.version_explorer import CnvVersionExplorer

LOGGER = logging.getLogger(__name__)


@dataclass
class ReleaseChecklistUpgradeEntry:
    source_version: str | None
    bundle_version: str | None
    iib: str | None
    channel: str | None
    post_upgrade_suite: str

    @classmethod
    def generate_info(cls, build_info: dict, post_upgrade_suite: str) -> "ReleaseChecklistUpgradeEntry":
        """
        Create upgrade entry from build info and post_upgrade_suite.

        Args:
            build_info: Build information dictionary
            post_upgrade_suite: Post-upgrade suite identifier

        Returns:
            ReleaseChecklistUpgradeEntry instance
        """
        return cls(
            source_version=build_info.get("version"),
            bundle_version=build_info.get("bundle_version"),
            iib=build_info.get("iib"),
            channel=build_info.get("channel"),
            post_upgrade_suite=post_upgrade_suite,
        )


def fetch_target_version(explorer: CnvVersionExplorer, target_version: Version) -> dict[str, str]:
    """
    Fetch target version build info. Target must have a stable channel.

    Args:
        explorer: CnvVersionExplorer instance
        target_version: Target version to upgrade to

    Returns:
        Build info dict with version, bundle_version, iib, and channel
    """
    return explorer.get_version_builds_info(
        version=str(target_version),
        stable_required=True,
    )


def fetch_source_version(
    explorer: CnvVersionExplorer, target_version: Version, minor_offset: int | None = None
) -> dict[str, str]:
    """
    Fetch source version build info. Source must be stable and released to prod.

    For LATEST_Z (minor_offset=None): source is 4.Y.0, fetched as a specific version.
    For other upgrade types: source minor is derived from target, searched via version range.

    Args:
        explorer: CnvVersionExplorer instance
        target_version: Target version to upgrade to
        minor_offset: Offset to apply to target minor for source version

    Returns:
        Build info dict with version, bundle_version, iib, and channel
    """
    if minor_offset is None:
        version = f"{target_version.major}.{target_version.minor}.0"
        return explorer.get_version_builds_info(
            version=version,
            stable_required=True,
            require_released_to_prod=True,
        )

    source_minor = f"{target_version.major}.{target_version.minor + minor_offset}"
    if source_minor not in MINOR_VERSION_SEARCH_RANGE:
        raise ValueError(f"No search range configured for minor version {source_minor}")
    start_version, stop_version = MINOR_VERSION_SEARCH_RANGE[source_minor]
    return explorer.get_version_range_builds_info(
        start_version=start_version,
        stop_version=stop_version,
        stable_required=True,
        require_released_to_prod=True,
    )


def get_upgrade_paths_info(explorer: CnvVersionExplorer, target_version: Version) -> dict:
    """
    Get upgrade paths info for a target version.

    Fetches target build info (must be stable), then builds upgrade lanes
    with source versions (must be stable and released to prod).

    Args:
        explorer: CnvVersionExplorer instance
        target_version: Version object to categorize

    Returns:
        Dictionary containing target build info and upgrade configurations
    """
    target_info = fetch_target_version(explorer, target_version)

    upgrade_types = get_applicable_upgrade_types(
        target_minor=target_version.minor,
        target_z=target_version.micro,
    )
    upgrade_lanes = {
        upgrade_type.display_name: asdict(
            ReleaseChecklistUpgradeEntry.generate_info(
                build_info=fetch_source_version(explorer, target_version, upgrade_type.minor_offset),
                post_upgrade_suite=get_post_upgrade_suite(upgrade_type, target_version.micro),
            )
        )
        for upgrade_type in upgrade_types
    }
    return {
        "target_version": str(target_version),
        "target_build_info": target_info,
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
        version_info = get_upgrade_paths_info(explorer, Version(target_version))

        click.echo(json.dumps(version_info, indent=2, default=str))


if __name__ == "__main__":
    main()
