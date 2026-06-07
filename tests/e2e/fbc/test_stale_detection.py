"""FBC stale stage detection tests: detect stale in_stage flags."""

import pytest

from cnv_upgrade_utilities.upgrade_types import SUPPORTED_VERSIONS
from cnv_upgrade_utilities.version_types import parse_minor_version

from ..utils.fbc_parser import get_fbc_versions_in_channel

yaml = pytest.importorskip("yaml", reason="pyyaml required for FBC tests")

pytestmark = [pytest.mark.fbc, pytest.mark.e2e]


class TestFbcStaleStageDetection:
    """Detect stale in_stage flags by comparing against FBC version ordering."""

    @pytest.mark.parametrize("minor", [parse_minor_version(v) for v in SUPPORTED_VERSIONS], ids=SUPPORTED_VERSIONS)
    def test_no_stale_in_stage_in_stable_channel(self, fbc_explorer, fbc_repo_path, minor):
        """
        If a build is in_stage=True for stable channel, no newer z-stream
        in the same stable channel should already be released_to_prod=True.
        """
        fbc_stable_versions = get_fbc_versions_in_channel(fbc_repo_path, minor, "stable")
        if not fbc_stable_versions:
            pytest.skip(f"No stable channel in FBC for v4.{minor}")

        builds = fbc_explorer.get_released_builds(minor_version=f"v4.{minor}", stage=True)
        if not builds:
            pytest.skip(f"No released builds found for v4.{minor}")

        stage_builds = []
        prod_versions = set()

        for build in builds:
            csv_version = build.csv_version.lstrip("v")
            for ch in build.channels:
                if ch.channel != "stable":
                    continue
                if ch.in_stage and not ch.released_to_prod:
                    stage_builds.append(csv_version)
                if ch.released_to_prod:
                    prod_versions.add(csv_version)

        for stage_version in stage_builds:
            stage_parts = stage_version.split(".")
            stage_z = int(stage_parts[2]) if len(stage_parts) >= 3 else 0

            for prod_version in prod_versions:
                prod_parts = prod_version.split(".")
                prod_z = int(prod_parts[2]) if len(prod_parts) >= 3 else 0

                if prod_z > stage_z:
                    pytest.fail(
                        f"v4.{minor}: Stale in_stage detected — {stage_version} is marked "
                        f"in_stage=True but {prod_version} (z={prod_z}) is already released to prod. "
                        f"This is a Version Explorer data quality issue."
                    )
