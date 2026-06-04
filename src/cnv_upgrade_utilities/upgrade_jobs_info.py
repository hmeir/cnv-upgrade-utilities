import json
import logging

import click
from packaging.version import Version
from pydantic import BaseModel

from cnv_upgrade_utilities.upgrade_types import UpgradeType, determine_upgrade_type
from cnv_upgrade_utilities.version_types import (
    FLEXIBLE_VERSION_TYPE,
    VersionFormat,
    detect_version_format,
    format_minor_version,
    strip_bundle_suffix,
)
from utils.build_helpers import (
    channel_exists,
    channel_in_stage,
    channel_released_to_prod,
    extract_filtered_build_info,
    extract_from_build_info,
    extract_released_build_info,
    find_released_source,
    find_stable_stage_build,
)
from utils.constants import CHANNEL_CANDIDATE, CHANNEL_STABLE
from utils.models import BuildResult, ReleasedBuild
from utils.version_explorer import CnvVersionExplorer

LOGGER = logging.getLogger(__name__)


# ============================================================================
# Helpers
# ============================================================================


def _is_initial_release(version: str) -> bool:
    """Check if a version string represents an initial release (X.Y.0)."""
    parts = strip_bundle_suffix(version).split(".")
    return len(parts) >= 3 and parts[2] == "0"


def _requires_stable_target(upgrade_type: UpgradeType) -> bool:
    """Y-stream and EUS upgrades require a stable channel for the target."""
    return upgrade_type in (UpgradeType.Y_STREAM, UpgradeType.EUS)


def _csv_version(build: ReleasedBuild) -> Version:
    return Version(build.csv_version.lstrip("v"))


def _keep_newer_build(current: ReleasedBuild | None, candidate: ReleasedBuild) -> ReleasedBuild:
    if current is None or _csv_version(candidate) > _csv_version(current):
        return candidate
    return current


def format_upgrade_result(upgrade_type: UpgradeType, source_info: BuildResult, target_info: BuildResult) -> dict:
    """Assemble the final upgrade result dict from typed source and target info."""
    return {
        "upgrade_type": upgrade_type.value,
        "source": source_info.model_dump(exclude_none=True),
        "target": target_info.model_dump(exclude_none=True),
    }


# ============================================================================
# BUNDLE format (GetBuildInfo) — exact build lookup by X.Y.Z.rhelR-BN
# ============================================================================


def _fetch_bundle_target(explorer: CnvVersionExplorer, version: str, upgrade_type: UpgradeType) -> BuildResult:
    """
    Fetch target build info for BUNDLE format using GetBuildInfo.

    Z stream / Latest Z: Try stable, fallback to candidate.
    Y stream / EUS: Require stable. Allow candidate fallback only for X.Y.0 builds.
    """
    build_info = explorer.get_build_info(bundle_version=version)
    channels = build_info.channels
    cnv_version = build_info.cnv_version
    base_version = strip_bundle_suffix(cnv_version.lstrip("v"))

    if channel_exists(channels=channels, channel=CHANNEL_STABLE):
        return extract_from_build_info(build_info=build_info, channel=CHANNEL_STABLE)

    if _requires_stable_target(upgrade_type=upgrade_type) and not _is_initial_release(version=base_version):
        raise ValueError(
            f"Target bundle version {version} does not have a stable channel, "
            f"required for {upgrade_type.display_name} upgrade"
        )

    if channel_exists(channels=channels, channel=CHANNEL_CANDIDATE):
        return extract_from_build_info(build_info=build_info, channel=CHANNEL_CANDIDATE)

    raise ValueError(f"No stable or candidate channel found for target bundle version {version}")


def _fetch_bundle_source(explorer: CnvVersionExplorer, version: str, exclude_version: str | None = None) -> BuildResult:
    """
    Fetch source build info for BUNDLE format using GetBuildInfo.

    Source must have current_channel=stable and stable channel released to prod.
    """
    build_info = explorer.get_build_info(bundle_version=version)

    current_channel = build_info.current_channel
    if current_channel != CHANNEL_STABLE:
        raise ValueError(f"Source bundle version {version} has current_channel='{current_channel}', expected 'stable'")

    channels = build_info.channels
    if not channel_released_to_prod(channels=channels, channel=CHANNEL_STABLE):
        raise ValueError(f"Source bundle version {version} stable channel is not released to prod")

    return extract_from_build_info(build_info=build_info, channel=CHANNEL_STABLE)


# ============================================================================
# FULL format (GetSuccessfulBuildsByVersion) — query by X.Y.Z
# ============================================================================


def _fetch_full_target(explorer: CnvVersionExplorer, version: str, upgrade_type: UpgradeType) -> BuildResult:
    """
    Fetch target build info for FULL format using GetSuccessfulBuildsByVersion.

    3-step fallback for Z stream / Latest Z (and X.Y.0 for Y stream / EUS):
      1. stable + stage=true (newest build in stable stage)
      2. candidate + stage=false, verify released_to_prod (candidate already on prod)
      3. candidate + stage=true (candidate in stage)

    Y stream / EUS (non-X.Y.0): only step 1 (stable stage), fail if not found.
    """
    result = find_stable_stage_build(explorer=explorer, version=version)
    if result:
        return result

    if _requires_stable_target(upgrade_type=upgrade_type) and not _is_initial_release(version=version):
        raise ValueError(
            f"No stable build in stage found for target version {version}, "
            f"required for {upgrade_type.display_name} upgrade"
        )

    builds = explorer.get_successful_builds_by_version(version=version, channel=CHANNEL_CANDIDATE, stage=False)
    for build in builds:
        if build.released_to_prod:
            return extract_filtered_build_info(build=build, version=version)

    builds = explorer.get_successful_builds_by_version(version=version, channel=CHANNEL_CANDIDATE, stage=True)
    for build in builds:
        if not build.released_to_prod:
            return extract_filtered_build_info(build=build, version=version)

    raise ValueError(f"No stable or candidate build found for target version {version}")


def _fetch_full_source(explorer: CnvVersionExplorer, version: str, exclude_version: str | None = None) -> BuildResult:
    """
    Fetch source build info for FULL format using GetSuccessfulBuildsByVersion.

    Looks for a build with stable channel released to prod (stage=false).
    Falls back to GetReleasedBuilds if the default 5 entries don't include
    the released-to-prod build.
    """
    builds = explorer.get_successful_builds_by_version(version=version, channel=CHANNEL_STABLE, stage=False)
    for build in builds:
        if build.released_to_prod:
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


class MinorTargetCandidates(BaseModel):
    """Best candidates found per priority tier when scanning released builds."""

    stable_stage_new: ReleasedBuild | None = None
    stable_stage_any: ReleasedBuild | None = None
    stable_prod: ReleasedBuild | None = None
    candidate_prod: ReleasedBuild | None = None
    candidate_stage: ReleasedBuild | None = None

    model_config = {"arbitrary_types_allowed": True}


def _scan_released_builds(builds: list[ReleasedBuild]) -> MinorTargetCandidates:
    """Scan released builds and collect the best candidate per priority tier."""
    candidates = MinorTargetCandidates()

    for build in builds:
        channels = build.channels
        stable_on_prod = channel_released_to_prod(channels=channels, channel=CHANNEL_STABLE)
        stable_in_stage = channel_in_stage(channels=channels, channel=CHANNEL_STABLE)

        if build.current_channel == CHANNEL_STABLE and stable_in_stage:
            candidates.stable_stage_any = _keep_newer_build(current=candidates.stable_stage_any, candidate=build)
            if not stable_on_prod:
                candidates.stable_stage_new = _keep_newer_build(current=candidates.stable_stage_new, candidate=build)

        if stable_on_prod and not stable_in_stage:
            candidates.stable_prod = _keep_newer_build(current=candidates.stable_prod, candidate=build)

        if not stable_on_prod:
            if channel_released_to_prod(channels=channels, channel=CHANNEL_CANDIDATE):
                candidates.candidate_prod = _keep_newer_build(current=candidates.candidate_prod, candidate=build)
            if channel_in_stage(channels=channels, channel=CHANNEL_CANDIDATE):
                candidates.candidate_stage = _keep_newer_build(current=candidates.candidate_stage, candidate=build)

    return candidates


def _resolve_minor_target(
    candidates: MinorTargetCandidates,
    builds: list[ReleasedBuild],
    stable_only: bool,
    upgrade_type: UpgradeType,
    minor_version: str,
) -> BuildResult:
    """Resolve the best target from scanned candidates based on upgrade type priority."""
    if stable_only:
        if candidates.stable_stage_any:
            return extract_released_build_info(build=candidates.stable_stage_any, channel=CHANNEL_STABLE)
    else:
        if candidates.stable_stage_new:
            latest_z = _csv_version(builds[0]).micro
            stage_z = _csv_version(candidates.stable_stage_new).micro
            if latest_z - stage_z < 2:
                return extract_released_build_info(build=candidates.stable_stage_new, channel=CHANNEL_STABLE)

    if stable_only:
        if candidates.stable_prod:
            return extract_released_build_info(build=candidates.stable_prod, channel=CHANNEL_STABLE)
        latest_csv = builds[0].csv_version.lstrip("v")
        if not _is_initial_release(version=latest_csv):
            raise ValueError(
                f"No stable build (stage or prod) found for {minor_version}, "
                f"required for {upgrade_type.display_name} upgrade"
            )

    best_candidate = (
        _keep_newer_build(current=candidates.candidate_prod, candidate=candidates.candidate_stage)
        if candidates.candidate_stage
        else candidates.candidate_prod
    )
    if best_candidate:
        return extract_released_build_info(build=best_candidate, channel=CHANNEL_CANDIDATE)

    raise ValueError(f"No suitable target build found for {minor_version}")


def _fetch_minor_target(explorer: CnvVersionExplorer, version: str, upgrade_type: UpgradeType) -> BuildResult:
    """Fetch target build info for MINOR format using GetReleasedBuilds."""
    minor_version = format_minor_version(version=version)
    builds = explorer.get_released_builds(minor_version=minor_version, stage=True)
    if not builds:
        raise ValueError(f"No released builds found for {minor_version}")

    candidates = _scan_released_builds(builds)
    stable_only = _requires_stable_target(upgrade_type=upgrade_type)
    return _resolve_minor_target(candidates, builds, stable_only, upgrade_type, minor_version)


def _fetch_minor_source(explorer: CnvVersionExplorer, version: str, exclude_version: str | None = None) -> BuildResult:
    """Fetch source build info for MINOR format using GetReleasedBuilds."""
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
) -> BuildResult:
    """Fetch version info based on version format and upgrade context."""
    version_format = detect_version_format(version=version)

    if is_source:
        fetcher = _SOURCE_FETCHERS[version_format]
        return fetcher(explorer=explorer, version=version, exclude_version=exclude_version)
    else:
        target_fetcher = _TARGET_FETCHERS[version_format]
        return target_fetcher(explorer=explorer, version=version, upgrade_type=upgrade_type)


# ============================================================================
# Main
# ============================================================================


def get_upgrade_jobs_info(explorer: CnvVersionExplorer, source_version: str, target_version: str) -> dict:
    """Get upgrade jobs info for source and target versions."""
    upgrade_type = determine_upgrade_type(source_version=source_version, target_version=target_version)

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
        exclude_version=target_info.version,
    )

    return format_upgrade_result(upgrade_type=upgrade_type, source_info=source_info, target_info=target_info)


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
def main(source_version: str, target_version: str) -> None:
    try:
        with CnvVersionExplorer() as explorer:
            result = get_upgrade_jobs_info(
                explorer=explorer, source_version=source_version, target_version=target_version
            )
            click.echo(json.dumps(result, indent=2))
    except (ValueError, ConnectionError, TimeoutError) as exc:
        raise SystemExit(f"Error: {exc}") from exc


if __name__ == "__main__":
    main()
