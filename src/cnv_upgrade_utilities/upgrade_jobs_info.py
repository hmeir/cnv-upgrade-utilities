import json
import logging

import click

from cnv_upgrade_utilities.utils import (
    FLEXIBLE_VERSION_TYPE,
    UpgradeType,
    VersionFormat,
    detect_version_format,
    determine_upgrade_type,
    format_minor_version,
)
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


# Map upgrade types to their handler functions (for MINOR format - fetch latest)
UPGRADE_HANDLERS = {
    UpgradeType.Z_STREAM: get_z_stream_upgrade_info,
    UpgradeType.Y_STREAM: get_y_stream_upgrade_info,
    UpgradeType.LATEST_Z: get_latest_z_upgrade_info,
    UpgradeType.EUS: get_eus_upgrade_info,
}


# ============================================================================
# Version Info Fetching
# ============================================================================
def get_channel_requirements(upgrade_type: UpgradeType, is_source: bool) -> tuple[str | None, bool]:
    """
    Get channel requirements based on upgrade type and source/target context.

    Args:
        upgrade_type: The upgrade type
        is_source: True if fetching source version, False for target

    Returns:
        Tuple of (required_channel, prefer_stable):
        - required_channel: Channel that must exist (error if missing), or None
        - prefer_stable: If True, prefer stable over candidate when no requirement
    """
    if is_source:
        # Source always requires stable channel
        return CHANNEL_STABLE, True

    # Target channel requirements depend on upgrade type
    if upgrade_type in (UpgradeType.Y_STREAM, UpgradeType.EUS):
        # Y-stream and EUS require stable channel for target
        return CHANNEL_STABLE, True
    else:
        # Z-stream and latest-z prefer candidate, fallback to stable
        return None, True


def fetch_version_info(
    explorer: CnvVersionExplorer,
    version: str,
    is_source: bool,
    upgrade_type: UpgradeType,
) -> dict[str, str]:
    """
    Fetch version info based on version format and upgrade context.

    Routes to appropriate fetch method based on detected version format:
    - MINOR (4.Y): Uses existing handlers to fetch latest
    - FULL (4.Y.Z): Uses get_specific_version_info with channel filtering
    - BUNDLE (4.Y.Z.rhelR-BN): Uses get_bundle_version_info with channel filtering

    Args:
        explorer: CnvVersionExplorer instance
        version: Version string in any supported format
        is_source: True if this is source version, False for target
        upgrade_type: The determined upgrade type

    Returns:
        Dictionary with version, bundle_version, iib, and channel
    """
    version_format = detect_version_format(version)
    required_channel, prefer_stable = get_channel_requirements(upgrade_type, is_source)

    match version_format:
        case VersionFormat.MINOR:
            # Use existing logic to fetch latest
            return _fetch_latest_version_info(explorer, version, is_source, upgrade_type)

        case VersionFormat.FULL:
            # Specific version - use get_specific_version_info
            return explorer.get_specific_version_info(
                version=version,
                required_channel=required_channel,
                prefer_stable=prefer_stable,
            )

        case VersionFormat.BUNDLE:
            # Bundle version - use get_bundle_version_info
            return explorer.get_bundle_version_info(
                bundle_version=version,
                required_channel=required_channel,
                prefer_stable=prefer_stable,
            )


def _fetch_latest_version_info(
    explorer: CnvVersionExplorer,
    version: str,
    is_source: bool,
    upgrade_type: UpgradeType,
) -> dict[str, str]:
    """
    Fetch latest version info for minor version format (existing behavior).

    This preserves the existing logic for X.Y format versions.

    Args:
        explorer: CnvVersionExplorer instance
        version: Minor version string (e.g., "4.20")
        is_source: True if fetching source, False for target
        upgrade_type: The upgrade type

    Returns:
        Dictionary with version, bundle_version, iib, and channel
    """
    minor_version = format_minor_version(version)

    if is_source:
        if upgrade_type == UpgradeType.LATEST_Z:
            # Source for latest-z is 4.Y.0
            return explorer.get_z0_release_info(minor_version=minor_version)
        else:
            # All other sources: latest stable released to prod
            return explorer.get_latest_released_z_stream_info(
                minor_version=minor_version,
                channel=CHANNEL_STABLE,
            )
    else:
        # Target version
        if upgrade_type in (UpgradeType.Z_STREAM, UpgradeType.LATEST_Z):
            return explorer.get_latest_candidate_with_stable_fallback_info(minor_version=minor_version)
        else:
            # Y_STREAM and EUS require stable
            return explorer.get_latest_stable_build_with_errata_info(minor_version=minor_version)


def get_upgrade_jobs_info(explorer: CnvVersionExplorer, source_version: str, target_version: str) -> dict:
    """
    Get upgrade jobs info for source and target versions.

    Supports three version formats for both source and target:
    - X.Y (e.g., 4.20): Fetches latest version matching the criteria
    - X.Y.Z (e.g., 4.20.3): Uses specific version via get_builds_by_version
    - X.Y.Z.rhelR-BN (e.g., 4.20.3.rhel9-18): Uses specific bundle version via GetBuildInfo

    Args:
        explorer: CnvVersionExplorer instance
        source_version: Source version in any supported format
        target_version: Target version in any supported format

    Returns:
        Dictionary containing upgrade type, source and target lane info
    """
    upgrade_type = determine_upgrade_type(source_version, target_version)

    source_info = fetch_version_info(
        explorer=explorer,
        version=source_version,
        is_source=True,
        upgrade_type=upgrade_type,
    )

    target_info = fetch_version_info(
        explorer=explorer,
        version=target_version,
        is_source=False,
        upgrade_type=upgrade_type,
    )

    return build_result(upgrade_type, source_info, target_info)


@click.command(help="Get upgrade jobs info for source and target versions")
@click.option(
    "-s",
    "--source-version",
    required=True,
    type=FLEXIBLE_VERSION_TYPE,
    help="Source version: 4.Y, 4.Y.Z, or 4.Y.Z.rhelR-BN (e.g., 4.19, 4.20.3, 4.20.3.rhel9-18)",
)
@click.option(
    "-t",
    "--target-version",
    required=True,
    type=FLEXIBLE_VERSION_TYPE,
    help="Target version: 4.Y, 4.Y.Z, or 4.Y.Z.rhelR-BN (e.g., 4.20, 4.20.5, 4.20.5.rhel9-3)",
)
def main(source_version: str, target_version: str):
    with CnvVersionExplorer() as explorer:
        result = get_upgrade_jobs_info(explorer, source_version, target_version)

        click.echo(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
