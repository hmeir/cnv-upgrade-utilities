import json
import logging

import click

from cnv_upgrade_utilities.utils import MINOR_VERSION_TYPE, SOURCE_VERSION_TYPE, UpgradeType, determine_upgrade_type
from utils.constants import CHANNEL_STABLE
from utils.version_explorer import CnvVersionExplorer

LOGGER = logging.getLogger(__name__)


# ============================================================================
# Fetch Strategy Configuration
# ============================================================================
def build_result(upgrade_type: UpgradeType, source_info: dict, target_info: dict) -> dict:
    """Build the result dictionary with source and target info."""
    return {
        "upgrade_type": upgrade_type.value,
        "source": {
            "version": source_info["version"],
            "bundle_version": source_info["bundle_version"],
            "iib": source_info["iib"],
            "channel": source_info["channel"],
        },
        "target": {
            "version": target_info["version"],
            "bundle_version": target_info["bundle_version"],
            "iib": target_info["iib"],
            "channel": target_info["channel"],
        },
    }


def get_z_stream_upgrade_info(explorer: CnvVersionExplorer, source_minor: str, target_minor: str) -> tuple[dict, dict]:
    """
    Get upgrade info for Z-stream upgrade (same minor version).

    Logic:
    1. source: latest stable released to prod
    2. target: latest candidate released to prod
       - If candidate bundle_version matches source's stable, use stable instead
    """
    source_info = explorer.get_latest_released_z_stream_info(minor_version=source_minor, channel=CHANNEL_STABLE)
    target_info = explorer.get_latest_candidate_with_stable_fallback_info(minor_version=target_minor)

    return source_info, target_info


def get_y_stream_upgrade_info(explorer: CnvVersionExplorer, source_minor: str, target_minor: str) -> tuple[dict, dict]:
    """
    Get upgrade info for Y-stream upgrade (target = source + 1).

    Logic:
    1. source: latest Y-1 stable released to prod
    2. target: latest build with stable channel and errata (includes QE builds)

    Note: Y-stream upgrades require the target to have a stable channel.
    """
    source_info = explorer.get_latest_released_z_stream_info(minor_version=source_minor, channel=CHANNEL_STABLE)
    target_info = explorer.get_latest_stable_build_with_errata_info(minor_version=target_minor)

    return source_info, target_info


def get_latest_z_upgrade_info(explorer: CnvVersionExplorer, source_minor: str, target_minor: str) -> tuple[dict, dict]:
    """
    Get upgrade info for latest-z upgrade (source is 4.Y.0).

    Logic:
    1. source: 4.Y.0 release info
    2. target: latest candidate released to prod, pick its stable if available
    """
    source_info = explorer.get_z0_release_info(minor_version=source_minor)
    target_info = explorer.get_latest_candidate_with_stable_fallback_info(minor_version=target_minor)

    return source_info, target_info


def get_eus_upgrade_info(explorer: CnvVersionExplorer, source_minor: str, target_minor: str) -> tuple[dict, dict]:
    """
    Get upgrade info for EUS upgrade (target = source + 2, both even).

    Logic:
    1. source: latest Y stable released to prod
    2. target: latest build with stable channel and errata (includes QE builds)

    Note: EUS upgrades require the target to have a stable channel.
    """
    source_info = explorer.get_latest_released_z_stream_info(minor_version=source_minor, channel=CHANNEL_STABLE)
    target_info = explorer.get_latest_stable_build_with_errata_info(minor_version=target_minor)

    return source_info, target_info


# Map upgrade types to their handler functions
UPGRADE_HANDLERS = {
    UpgradeType.Z_STREAM: get_z_stream_upgrade_info,
    UpgradeType.Y_STREAM: get_y_stream_upgrade_info,
    UpgradeType.LATEST_Z: get_latest_z_upgrade_info,
    UpgradeType.EUS: get_eus_upgrade_info,
}


def get_upgrade_jobs_info(explorer: CnvVersionExplorer, source_version: str, target_version: str) -> dict:
    """
    Get upgrade jobs info for source and target versions.

    Args:
        explorer: CnvVersionExplorer instance
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

    handler = UPGRADE_HANDLERS[upgrade_type]
    source_info, target_info = handler(explorer, source_minor, target_minor)

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
    type=MINOR_VERSION_TYPE,
    help="Target minor version in format 4.Y (e.g., 4.20)",
)
def main(source_version: str, target_version: str):
    with CnvVersionExplorer() as explorer:
        result = get_upgrade_jobs_info(explorer, source_version, target_version)

        click.echo(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
