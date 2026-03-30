import json
import logging
from dataclasses import asdict, dataclass

import click
from packaging.version import Version

from cnv_upgrade_utilities.utils import (
    FULL_VERSION_TYPE,
    get_applicable_upgrade_types,
    get_post_upgrade_suite,
)
from utils.version_explorer import (
    CnvVersionExplorer,
    extract_filtered_build_info,
    find_released_source,
    find_stable_stage_build,
)

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


def fetch_target_version(
    explorer: CnvVersionExplorer, target_version: Version, skip_target_check: bool = False
) -> dict[str, str]:
    """
    Fetch target version build info using GetSuccessfulBuildsByVersion.

    By default, target must be in stable stage but NOT yet released to prod.
    If skip_target_check is True, accepts any stable build (including already released).

    Args:
        explorer: CnvVersionExplorer instance
        target_version: Target version to upgrade to
        skip_target_check: If True, skip the stage/prod validation

    Returns:
        Build info dict with version, bundle_version, iib, and channel
    """
    from utils.constants import CHANNEL_CANDIDATE, CHANNEL_STABLE

    version = str(target_version)

    # Try stable stage (not yet released to prod)
    result = find_stable_stage_build(explorer=explorer, version=version)
    if result:
        return result

    # If skip_target_check, accept any build (stable or candidate)
    if skip_target_check:
        for channel in (CHANNEL_STABLE, CHANNEL_CANDIDATE):
            builds = explorer.get_successful_builds_by_version(version=version, channel=channel)
            if builds:
                LOGGER.warning(
                    f"Target version {version} is not in stable stage, "
                    f"using latest {channel} build (--skip-target-check)"
                )
                return extract_filtered_build_info(build=builds[0], version=version)
        raise ValueError(f"No stable or candidate build found for target version {version}")

    # Distinguish between "already released to prod" and "no stable build at all"
    builds = explorer.get_successful_builds_by_version(version=version, channel=CHANNEL_STABLE)
    if builds:
        raise ValueError(f"Target version {version} has stable builds but none are in stage (already released to prod)")
    raise ValueError(f"No stable build found for target version {version}")


def fetch_source_version(
    explorer: CnvVersionExplorer, target_version: Version, minor_offset: int | None = None
) -> dict[str, str]:
    """
    Fetch source version build info using GetReleasedBuilds.

    Source must be stable and released to prod.

    For LATEST_Z (minor_offset=None): find X.Y.0 stable released to prod.
    For Z_STREAM (minor_offset=0): find latest X.Y.Z stable released to prod.
    For Y_STREAM (minor_offset=-1): find latest X.Y-1.Z stable released to prod.
    For EUS (minor_offset=-2): find latest X.Y-2.Z stable released to prod.

    Args:
        explorer: CnvVersionExplorer instance
        target_version: Target version to upgrade to
        minor_offset: Offset to apply to target minor for source version

    Returns:
        Build info dict with version, bundle_version, iib, and channel
    """
    if minor_offset is None:
        source_minor = f"v{target_version.major}.{target_version.minor}"
        required_csv = f"v{target_version.major}.{target_version.minor}.0"
    else:
        source_minor = f"v{target_version.major}.{target_version.minor + minor_offset}"
        required_csv = None

    return find_released_source(
        explorer=explorer,
        minor_version=source_minor,
        required_csv=required_csv,
    )


def get_upgrade_paths_info(
    explorer: CnvVersionExplorer, target_version: Version, skip_target_check: bool = False
) -> dict:
    """
    Get upgrade paths info for a target version.

    Fetches target build info (must be stable), then builds upgrade lanes
    with source versions (must be stable and released to prod).

    Args:
        explorer: CnvVersionExplorer instance
        target_version: Version object to categorize
        skip_target_check: If True, skip target stage/prod validation

    Returns:
        Dictionary containing target build info and upgrade configurations
    """
    target_info = fetch_target_version(
        explorer=explorer, target_version=target_version, skip_target_check=skip_target_check
    )

    upgrade_types = get_applicable_upgrade_types(
        target_minor=target_version.minor,
        target_z=target_version.micro,
    )
    upgrade_lanes = {
        upgrade_type.display_name: asdict(
            ReleaseChecklistUpgradeEntry.generate_info(
                build_info=fetch_source_version(
                    explorer=explorer, target_version=target_version, minor_offset=upgrade_type.minor_offset
                ),
                post_upgrade_suite=get_post_upgrade_suite(upgrade_type=upgrade_type, z=target_version.micro),
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
    "--skip-target-check",
    is_flag=True,
    default=False,
    help="Skip target channel validation. Use when the target build hasn't reached stable stage yet.",
)
def main(target_version: str, skip_target_check: bool):
    with CnvVersionExplorer() as explorer:
        version_info = get_upgrade_paths_info(
            explorer=explorer, target_version=Version(target_version), skip_target_check=skip_target_check
        )

        click.echo(json.dumps(version_info, indent=2, default=str))


if __name__ == "__main__":
    main()
