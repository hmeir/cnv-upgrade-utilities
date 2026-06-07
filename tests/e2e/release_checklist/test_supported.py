"""E2E tests for release_checklist_upgrade_plan — supported versions."""

import pytest
from packaging.version import Version

from cnv_upgrade_utilities.release_checklist_upgrade_plan import get_upgrade_paths_info
from cnv_upgrade_utilities.upgrade_types import SUPPORTED_VERSIONS

from ..utils.expected_lanes import compute_expected_lanes


@pytest.mark.e2e
class TestReleaseChecklistSupported:
    """Verify release checklist returns expected lanes for each supported version."""

    @pytest.mark.parametrize("version", SUPPORTED_VERSIONS, ids=SUPPORTED_VERSIONS)
    def test_upgrade_lanes_match_expected(self, explorer, version, version_latest_z):
        """Lanes returned should match independently computed expected lanes."""
        max_z = version_latest_z.get(version, 0)
        target = Version(f"{version}.{max_z}")

        result = get_upgrade_paths_info(explorer, target_version=target, skip_target_check=True)

        expected_lane_names = compute_expected_lanes(
            version_str=version, z=max_z, supported_versions=SUPPORTED_VERSIONS
        )
        actual_lane_names = set(result["upgrade_lanes"].keys())

        assert actual_lane_names == expected_lane_names, (
            f"For {version}.1: expected lanes {expected_lane_names}, got {actual_lane_names}"
        )

        for lane_name, lane_data in result["upgrade_lanes"].items():
            assert lane_data["source_version"], f"Lane '{lane_name}' missing source_version"
            assert lane_data["iib"], f"Lane '{lane_name}' missing iib"
            assert lane_data["channel"], f"Lane '{lane_name}' missing channel"
            assert lane_data["post_upgrade_suite"], f"Lane '{lane_name}' missing post_upgrade_suite"
