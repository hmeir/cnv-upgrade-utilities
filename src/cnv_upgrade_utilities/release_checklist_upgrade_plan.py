import json
import logging

import click
from packaging.version import Version

from cnv_upgrade_utilities.post_upgrade_suites import get_post_upgrade_suite
from cnv_upgrade_utilities.upgrade_types import get_applicable_upgrade_types
from cnv_upgrade_utilities.version_types import FULL_VERSION_TYPE
from utils.build_helpers import (
    extract_filtered_build_info,
    find_released_source,
    find_stable_stage_build,
)
from utils.constants import CHANNEL_CANDIDATE, CHANNEL_STABLE
from utils.models import BuildResult
from utils.version_explorer import CnvVersionExplorer

LOGGER = logging.getLogger(__name__)


class ReleaseChecklistUpgradeEntry:
    def __init__(
        self,
        source_version: str | None,
        bundle_version: str | None,
        iib: str | None,
        channel: str | None,
        post_upgrade_suite: str,
    ):
        self.source_version = source_version
        self.bundle_version = bundle_version
        self.iib = iib
        self.channel = channel
        self.post_upgrade_suite = post_upgrade_suite

    @classmethod
    def from_build_result(cls, build_result: BuildResult, post_upgrade_suite: str) -> "ReleaseChecklistUpgradeEntry":
        return cls(
            source_version=build_result.version,
            bundle_version=build_result.bundle_version,
            iib=build_result.iib,
            channel=build_result.channel,
            post_upgrade_suite=post_upgrade_suite,
        )

    def to_dict(self) -> dict:
        return {
            "source_version": self.source_version,
            "bundle_version": self.bundle_version,
            "iib": self.iib,
            "channel": self.channel,
            "post_upgrade_suite": self.post_upgrade_suite,
        }


def fetch_target_version(
    explorer: CnvVersionExplorer, target_version: Version, skip_target_check: bool = False
) -> BuildResult:
    """
    Fetch target version build info using GetSuccessfulBuildsByVersion.

    By default, target must be in stable stage but NOT yet released to prod.
    If skip_target_check is True, accepts any stable build (including already released).
    """
    version = str(target_version)

    result = find_stable_stage_build(explorer=explorer, version=version)
    if result:
        return result

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

    builds = explorer.get_successful_builds_by_version(version=version, channel=CHANNEL_STABLE)
    if builds:
        raise ValueError(f"Target version {version} has stable builds but none are in stage (already released to prod)")
    raise ValueError(f"No stable build found for target version {version}")


def fetch_source_version(
    explorer: CnvVersionExplorer, target_version: Version, minor_offset: int | None = None
) -> BuildResult:
    """Fetch source version build info using GetReleasedBuilds."""
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
    """Get upgrade paths info for a target version."""
    target_info = fetch_target_version(
        explorer=explorer, target_version=target_version, skip_target_check=skip_target_check
    )

    upgrade_types = get_applicable_upgrade_types(
        target_minor=target_version.minor,
        target_z=target_version.micro,
    )
    upgrade_lanes = {
        upgrade_type.display_name: ReleaseChecklistUpgradeEntry.from_build_result(
            build_result=fetch_source_version(
                explorer=explorer, target_version=target_version, minor_offset=upgrade_type.minor_offset
            ),
            post_upgrade_suite=get_post_upgrade_suite(upgrade_type=upgrade_type, z=target_version.micro),
        ).to_dict()
        for upgrade_type in upgrade_types
    }
    return {
        "target_version": str(target_version),
        "target_build_info": target_info.model_dump(exclude_none=True),
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
def main(target_version: str, skip_target_check: bool) -> None:
    try:
        with CnvVersionExplorer() as explorer:
            version_info = get_upgrade_paths_info(
                explorer=explorer, target_version=Version(target_version), skip_target_check=skip_target_check
            )

            click.echo(json.dumps(version_info, indent=2, default=str))
    except (ValueError, ConnectionError, TimeoutError) as exc:
        raise SystemExit(f"Error: {exc}") from exc


if __name__ == "__main__":
    main()
