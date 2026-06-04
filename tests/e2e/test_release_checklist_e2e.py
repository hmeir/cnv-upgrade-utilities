"""E2E tests for release_checklist_upgrade_plan against live Version Explorer API."""

import pytest
from packaging.version import Version

from cnv_upgrade_utilities.release_checklist_upgrade_plan import get_upgrade_paths_info
from cnv_upgrade_utilities.upgrade_types import (
    EOL_VERSIONS,
    SUPPORTED_VERSIONS,
    get_applicable_upgrade_types,
)
from cnv_upgrade_utilities.version_types import parse_minor_version


@pytest.mark.e2e
class TestReleaseChecklistSupported:
    """Verify release checklist returns expected lanes for each supported version."""

    @pytest.mark.parametrize("version", SUPPORTED_VERSIONS, ids=SUPPORTED_VERSIONS)
    def test_upgrade_lanes_match_rules(self, explorer, version):
        """Lanes returned should match exactly what get_applicable_upgrade_types says."""
        minor = parse_minor_version(version)
        target = Version(f"{version}.1")

        try:
            result = get_upgrade_paths_info(explorer, target_version=target, skip_target_check=True)
        except ValueError:
            pytest.skip(f"No builds available for {version}.1")

        expected_types = get_applicable_upgrade_types(target_minor=minor, target_z=1)
        expected_lane_names = {ut.display_name for ut in expected_types}
        actual_lane_names = set(result["upgrade_lanes"].keys())

        assert (
            actual_lane_names == expected_lane_names
        ), f"For {version}.1: expected lanes {expected_lane_names}, got {actual_lane_names}"

        for lane_name, lane_data in result["upgrade_lanes"].items():
            assert lane_data["source_version"], f"Lane '{lane_name}' missing source_version"
            assert lane_data["iib"], f"Lane '{lane_name}' missing iib"
            assert lane_data["channel"], f"Lane '{lane_name}' missing channel"
            assert lane_data["post_upgrade_suite"], f"Lane '{lane_name}' missing post_upgrade_suite"


@pytest.mark.e2e
class TestReleaseChecklistEol:
    """Verify EOL versions are rejected by release checklist."""

    @pytest.mark.parametrize("version", sorted(EOL_VERSIONS), ids=sorted(EOL_VERSIONS))
    def test_eol_version_rejected(self, explorer, version):
        target = Version(f"{version}.1")
        with pytest.raises(ValueError, match="EOL"):
            get_upgrade_paths_info(explorer, target_version=target, skip_target_check=True)
