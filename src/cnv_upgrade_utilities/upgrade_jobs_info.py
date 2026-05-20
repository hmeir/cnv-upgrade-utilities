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
from utils.constants import CHANNEL_CANDIDATE, CHANNEL_STABLE
from utils.version_explorer import (
    CnvVersionExplorer,
    channel_exists,
    channel_in_stage,
    channel_released_to_prod,
    extract_build_info_result,
    extract_filtered_build_info,
    extract_released_build_info,
    find_released_source,
    find_stable_stage_build,
)

LOGGER = logging.getLogger(__name__)


# ============================================================================
# Helpers
# ============================================================================


def _is_initial_release(version: str) -> bool:
    """Check if a version string represents an initial release (X.Y.0)."""
    parts = version.rsplit(".rhel", 1)[0].split(".")
    return len(parts) >= 3 and parts[2] == "0"


def _requires_stable_target(upgrade_type: UpgradeType) -> bool:
    """Y-stream and EUS upgrades require a stable channel for the target."""
    return upgrade_type in (UpgradeType.Y_STREAM, UpgradeType.EUS)


def build_result(upgrade_type: UpgradeType, source_info: dict, target_info: dict) -> dict:
    """Build the result dictionary with source and target info."""
    return {
        "upgrade_type": upgrade_type.value,
        "source": source_info,
        "target": target_info,
    }


# ============================================================================
# BUNDLE format (GetBuildInfo) — exact build lookup by X.Y.Z.rhelR-BN
# ============================================================================


def _fetch_bundle_target(explorer: CnvVersionExplorer, version: str, upgrade_type: UpgradeType) -> dict[str, str]:
    """
    Fetch target build info for BUNDLE format using GetBuildInfo.

    Z stream / Latest Z: Try stable, fallback to candidate.
    Y stream / EUS: Require stable. Allow candidate fallback only for X.Y.0 builds.
    """
    build_info = explorer.get_build_info(bundle_version=version)
    channels = build_info.get("channels", [])
    cnv_version = build_info["cnv_version"]
    base_version = cnv_version.lstrip("v").rsplit(".rhel", 1)[0]

    if channel_exists(channels=channels, channel=CHANNEL_STABLE):
        return extract_build_info_result(build_info=build_info, channel=CHANNEL_STABLE)

    if _requires_stable_target(upgrade_type=upgrade_type) and not _is_initial_release(version=base_version):
        raise ValueError(
            f"Target bundle version {version} does not have a stable channel, "
            f"required for {upgrade_type.display_name} upgrade"
        )

    if channel_exists(channels=channels, channel=CHANNEL_CANDIDATE):
        return extract_build_info_result(build_info=build_info, channel=CHANNEL_CANDIDATE)

    raise ValueError(f"No stable or candidate channel found for target bundle version {version}")


def _fetch_bundle_source(explorer: CnvVersionExplorer, version: str, **_kwargs) -> dict[str, str]:
    """
    Fetch source build info for BUNDLE format using GetBuildInfo.

    Source must have current_channel=stable and stable channel released to prod.
    """
    build_info = explorer.get_build_info(bundle_version=version)

    current_channel = build_info.get("current_channel")
    if current_channel != CHANNEL_STABLE:
        raise ValueError(f"Source bundle version {version} has current_channel='{current_channel}', expected 'stable'")

    channels = build_info.get("channels", [])
    if not channel_released_to_prod(channels=channels, channel=CHANNEL_STABLE):
        raise ValueError(f"Source bundle version {version} stable channel is not released to prod")

    return extract_build_info_result(build_info=build_info, channel=CHANNEL_STABLE)


# ============================================================================
# FULL format (GetSuccessfulBuildsByVersion) — query by X.Y.Z
# ============================================================================


def _fetch_full_target(explorer: CnvVersionExplorer, version: str, upgrade_type: UpgradeType) -> dict[str, str]:
    """
    Fetch target build info for FULL format using GetSuccessfulBuildsByVersion.

    3-step fallback for Z stream / Latest Z (and X.Y.0 for Y stream / EUS):
      1. stable + stage=true (newest build in stable stage)
      2. candidate + stage=false, verify released_to_prod (candidate already on prod)
      3. candidate + stage=true (candidate in stage)

    Y stream / EUS (non-X.Y.0): only step 1 (stable stage), fail if not found.
    """
    # Step 1: Try stable + stage (but not already released to prod)
    result = find_stable_stage_build(explorer=explorer, version=version)
    if result:
        return result

    # For Y stream / EUS with non-X.Y.0, stable is mandatory
    if _requires_stable_target(upgrade_type=upgrade_type) and not _is_initial_release(version=version):
        raise ValueError(
            f"No stable build in stage found for target version {version}, "
            f"required for {upgrade_type.display_name} upgrade"
        )

    # Step 2: Try candidate + prod (not in stage, released to prod)
    builds = explorer.get_successful_builds_by_version(version=version, channel=CHANNEL_CANDIDATE, stage=False)
    for build in builds:
        if build.get("released_to_prod"):
            return extract_filtered_build_info(build=build, version=version)

    # Step 3: Try candidate + stage (not already released to prod)
    builds = explorer.get_successful_builds_by_version(version=version, channel=CHANNEL_CANDIDATE, stage=True)
    for build in builds:
        if not build.get("released_to_prod"):
            return extract_filtered_build_info(build=build, version=version)

    raise ValueError(f"No stable or candidate build found for target version {version}")


def _fetch_full_source(explorer: CnvVersionExplorer, version: str, **_kwargs) -> dict[str, str]:
    """
    Fetch source build info for FULL format using GetSuccessfulBuildsByVersion.

    Looks for a build with stable channel released to prod (stage=false).
    Falls back to GetReleasedBuilds if the default 5 entries don't include
    the released-to-prod build.
    """
    builds = explorer.get_successful_builds_by_version(version=version, channel=CHANNEL_STABLE, stage=False)
    for build in builds:
        if build.get("released_to_prod"):
            return extract_filtered_build_info(build=build, version=version)

    LOGGER.info(
        f"No stable released-to-prod build found in GetSuccessfulBuildsByVersion for {version}, "
        f"trying GetReleasedBuilds"
    )
    return find_released_source(
        explorer=explorer,
        minor_version=format_minor_version(version=version),
        required_csv=f"v{version}",
    )


# ============================================================================
# MINOR format (GetReleasedBuilds) — scan all z-streams for X.Y
# ============================================================================


def _fetch_minor_target(explorer: CnvVersionExplorer, version: str, upgrade_type: UpgradeType) -> dict[str, str]:
    """
    Fetch target build info for MINOR format using GetReleasedBuilds.

    Scans released builds (including stage) to find the best target:

    Z stream / Latest Z:
      1. Latest z with current_channel=stable AND stable channel in_stage=true
      2. Fallback: latest z with candidate channel released_to_prod=true
      3. Fallback: latest z with candidate channel in_stage=true

    Y stream / EUS:
      1. Latest z with current_channel=stable AND stable channel in_stage=true
      2. Fallback: latest z with stable channel released_to_prod=true (previous stable)
      3. Fallback (X.Y.0 only): candidate prod, then candidate stage
      4. Fail
    """
    minor_version = format_minor_version(version=version)
    builds = explorer.get_released_builds(minor_version=minor_version, stage=True)
    if not builds:
        raise ValueError(f"No released builds found for {minor_version}")

    stable_only = _requires_stable_target(upgrade_type=upgrade_type)

    # Single pass: collect best candidate per priority tier
    stable_stage = None  # Step 1: stable in stage, not released to prod
    stable_prod = None  # Y/EUS fallback: stable released to prod
    candidate_prod = None  # Step 2: candidate released to prod (Z/Latest-Z only)
    candidate_stage = None  # Step 3: candidate in stage (Z/Latest-Z only)

    for build in builds:
        channels = build.get("channels", [])
        stable_on_prod = channel_released_to_prod(channels=channels, channel=CHANNEL_STABLE)

        if not stable_stage and build.get("current_channel") == CHANNEL_STABLE:
            if channel_in_stage(channels=channels, channel=CHANNEL_STABLE) and not stable_on_prod:
                stable_stage = build

        if not stable_prod and stable_on_prod:
            stable_prod = build

        if not stable_on_prod:
            if not candidate_prod and channel_released_to_prod(channels=channels, channel=CHANNEL_CANDIDATE):
                candidate_prod = build
            if not candidate_stage and channel_in_stage(channels=channels, channel=CHANNEL_CANDIDATE):
                candidate_stage = build

    # Step 1: stable stage (not yet released to prod) — all upgrade types
    if stable_stage:
        return extract_released_build_info(build=stable_stage, channel=CHANNEL_STABLE)

    # Y stream / EUS: fallback to previous stable (released to prod)
    if stable_only:
        if stable_prod:
            return extract_released_build_info(build=stable_prod, channel=CHANNEL_STABLE)
        # Allow candidate fallback for X.Y.0 (new minor with no stable builds yet)
        latest_csv = builds[0].get("csv_version", "").lstrip("v")
        if not _is_initial_release(version=latest_csv):
            raise ValueError(
                f"No stable build (stage or prod) found for {minor_version}, "
                f"required for {upgrade_type.display_name} upgrade"
            )
        # Fall through to candidate steps below

    # Step 2: candidate released to prod
    if candidate_prod:
        return extract_released_build_info(build=candidate_prod, channel=CHANNEL_CANDIDATE)

    # Step 3: candidate in stage
    if candidate_stage:
        return extract_released_build_info(build=candidate_stage, channel=CHANNEL_CANDIDATE)

    raise ValueError(f"No suitable target build found for {minor_version}")


def _fetch_minor_source(
    explorer: CnvVersionExplorer, version: str, exclude_version: str | None = None
) -> dict[str, str]:
    """
    Fetch source build info for MINOR format using GetReleasedBuilds.

    Finds the latest z-stream with stable channel released to prod.
    Skips builds matching exclude_version (used to avoid source=target in Z-stream).
    """
    return find_released_source(
        explorer=explorer,
        minor_version=format_minor_version(version=version),
        exclude_csv=exclude_version,
    )


# ============================================================================
# Dispatch
# ============================================================================
_SOURCE_FETCHERS = {
    VersionFormat.MINOR: _fetch_minor_source,
    VersionFormat.FULL: _fetch_full_source,
    VersionFormat.BUNDLE: _fetch_bundle_source,
}

_TARGET_FETCHERS = {
    VersionFormat.MINOR: _fetch_minor_target,
    VersionFormat.FULL: _fetch_full_target,
    VersionFormat.BUNDLE: _fetch_bundle_target,
}


def fetch_version_info(
    explorer: CnvVersionExplorer,
    version: str,
    is_source: bool,
    upgrade_type: UpgradeType,
    exclude_version: str | None = None,
) -> dict[str, str]:
    """
    Fetch version info based on version format and upgrade context.

    Routes to the appropriate format-specific fetcher based on detected version format
    and whether this is a source or target version.

    Args:
        explorer: CnvVersionExplorer instance
        version: Version string in any supported format
        is_source: True if this is source version, False for target
        upgrade_type: The determined upgrade type
        exclude_version: Version to exclude from results (used to avoid source=target)

    Returns:
        Dictionary with version, bundle_version, iib, and channel
    """
    version_format = detect_version_format(version=version)
    fetchers = _SOURCE_FETCHERS if is_source else _TARGET_FETCHERS
    fetcher = fetchers[version_format]

    if is_source:
        return fetcher(explorer=explorer, version=version, exclude_version=exclude_version)
    else:
        return fetcher(explorer=explorer, version=version, upgrade_type=upgrade_type)


# ============================================================================
# Main
# ============================================================================


def get_upgrade_jobs_info(explorer: CnvVersionExplorer, source_version: str, target_version: str) -> dict:
    """
    Get upgrade jobs info for source and target versions.

    Supports three version formats for both source and target:
    - X.Y (e.g., 4.20): Uses GetReleasedBuilds to find the best build
    - X.Y.Z (e.g., 4.20.3): Uses GetSuccessfulBuildsByVersion with channel/stage filters
    - X.Y.Z.rhelR-BN (e.g., 4.20.3.rhel9-18): Uses GetBuildInfo for exact build lookup

    Args:
        explorer: CnvVersionExplorer instance
        source_version: Source version in any supported format
        target_version: Target version in any supported format

    Returns:
        Dictionary containing upgrade type, source and target lane info
    """
    upgrade_type = determine_upgrade_type(source_version=source_version, target_version=target_version)

    # Fetch target first so we can exclude it from source (avoids source=target in Z-stream)
    target_info = fetch_version_info(
        explorer=explorer,
        version=target_version,
        is_source=False,
        upgrade_type=upgrade_type,
    )

    source_info = fetch_version_info(
        explorer=explorer,
        version=source_version,
        is_source=True,
        upgrade_type=upgrade_type,
        exclude_version=target_info["version"],
    )

    return build_result(upgrade_type=upgrade_type, source_info=source_info, target_info=target_info)


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
    try:
        with CnvVersionExplorer() as explorer:
            result = get_upgrade_jobs_info(explorer=explorer, source_version=source_version, target_version=target_version)
            click.echo(json.dumps(result, indent=2))
    except (ValueError, ConnectionError, TimeoutError) as exc:
        raise SystemExit(f"Error: {exc}")


if __name__ == "__main__":
    main()
