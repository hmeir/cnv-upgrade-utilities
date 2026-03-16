import json
import logging

import click

from cnv_upgrade_utilities.utils import (
    FLEXIBLE_VERSION_TYPE,
    MINOR_VERSION_SEARCH_RANGE,
    UpgradeType,
    VersionFormat,
    detect_version_format,
    determine_upgrade_type,
)
from utils.constants import CHANNEL_STABLE
from utils.version_explorer import CnvVersionExplorer

LOGGER = logging.getLogger(__name__)


# ============================================================================
# Result Building
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


# ============================================================================
# Source Version Fetching
# ============================================================================
def _fetch_source_info(
    explorer: CnvVersionExplorer,
    version: str,
    version_format: VersionFormat,
    upgrade_type: UpgradeType,
) -> dict[str, str]:
    """
    Fetch source version info. Source always requires stable channel released to prod.

    For MINOR and FULL formats, queries GetSuccessfulBuildsByVersion with
    errata_status=false, iterating builds to find a stable channel released to prod.
    BUNDLE format uses GetBuildInfo directly (same as before).

    Args:
        explorer: CnvVersionExplorer instance
        version: Version string in any supported format
        version_format: Detected format of the version
        upgrade_type: The determined upgrade type

    Returns:
        Dictionary with version, bundle_version, iib, and channel
    """
    match version_format:
        case VersionFormat.MINOR:
            if version not in MINOR_VERSION_SEARCH_RANGE:
                raise ValueError(f"No search range configured for minor version {version}")
            start_version, stop_version = MINOR_VERSION_SEARCH_RANGE[version]
            return explorer.get_version_range_builds_info(
                start_version=start_version,
                stop_version=stop_version,
                stable_required=True,
                require_released_to_prod=True,
            )

        case VersionFormat.FULL:
            return explorer.get_version_builds_info(
                version=version,
                stable_required=True,
                require_released_to_prod=True,
            )

        case VersionFormat.BUNDLE:
            return explorer.get_bundle_version_info(
                bundle_version=version,
                required_channel=CHANNEL_STABLE,
                prefer_stable=True,
            )


# ============================================================================
# Target Version Fetching
# ============================================================================
def _fetch_target_info(
    explorer: CnvVersionExplorer,
    version: str,
    version_format: VersionFormat,
    upgrade_type: UpgradeType,
) -> dict[str, str]:
    """
    Fetch target version info.

    Channel logic: Y-stream and EUS upgrades require a stable channel.
    Z-stream and latest-z prefer stable but fall back to candidate.

    For MINOR and FULL formats, queries GetSuccessfulBuildsByVersion with
    errata_status=false, iterating builds to find a stable channel first.
    BUNDLE format uses GetBuildInfo directly (same as before).

    Args:
        explorer: CnvVersionExplorer instance
        version: Version string in any supported format
        version_format: Detected format of the version
        upgrade_type: The determined upgrade type

    Returns:
        Dictionary with version, bundle_version, iib, and channel
    """
    stable_required = upgrade_type in (UpgradeType.Y_STREAM, UpgradeType.EUS)

    match version_format:
        case VersionFormat.MINOR:
            if version not in MINOR_VERSION_SEARCH_RANGE:
                raise ValueError(f"No search range configured for minor version {version}")
            start_version, stop_version = MINOR_VERSION_SEARCH_RANGE[version]
            return explorer.get_version_range_builds_info(
                start_version=start_version,
                stop_version=stop_version,
                stable_required=stable_required,
            )

        case VersionFormat.FULL:
            return explorer.get_version_builds_info(
                version=version,
                stable_required=stable_required,
            )

        case VersionFormat.BUNDLE:
            required_channel = CHANNEL_STABLE if stable_required else None
            return explorer.get_bundle_version_info(
                bundle_version=version,
                required_channel=required_channel,
                prefer_stable=True,
            )


# ============================================================================
# Main Entry Point
# ============================================================================
def fetch_version_info(
    explorer: CnvVersionExplorer,
    version: str,
    is_source: bool,
    upgrade_type: UpgradeType,
) -> dict[str, str]:
    """
    Fetch version info based on version format and upgrade context.

    Routes to _fetch_source_info or _fetch_target_info based on context,
    then to the appropriate fetch method based on detected version format.

    Args:
        explorer: CnvVersionExplorer instance
        version: Version string in any supported format
        is_source: True if this is source version, False for target
        upgrade_type: The determined upgrade type

    Returns:
        Dictionary with version, bundle_version, iib, and channel
    """
    version_format = detect_version_format(version)

    if is_source:
        return _fetch_source_info(explorer, version, version_format, upgrade_type)
    else:
        return _fetch_target_info(explorer, version, version_format, upgrade_type)


def get_upgrade_jobs_info(explorer: CnvVersionExplorer, source_version: str, target_version: str) -> dict:
    """
    Get upgrade jobs info for source and target versions.

    Supports three version formats for both source and target:
    - X.Y (e.g., 4.20): Searches a configured version range for target, fetches latest for source
    - X.Y.Z (e.g., 4.20.3): Uses specific version via GetSuccessfulBuildsByVersion
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
