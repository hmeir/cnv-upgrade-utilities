"""E2E tests for release_checklist_upgrade_plan against live Version Explorer API."""

import pytest
from packaging.version import Version

from cnv_upgrade_utilities.release_checklist_upgrade_plan import get_upgrade_paths_info
from cnv_upgrade_utilities.upgrade_types import EOL_VERSIONS, SUPPORTED_VERSIONS

from .conftest import VERSION_Z_DEPTH
from .utils.expected_lanes import compute_expected_lanes


@pytest.mark.e2e
class TestReleaseChecklistSupported:
    """Verify release checklist returns expected lanes for each supported version."""

    @pytest.mark.parametrize("version", SUPPORTED_VERSIONS, ids=SUPPORTED_VERSIONS)
    def test_upgrade_lanes_match_expected(self, explorer, version):
        """Lanes returned should match independently computed expected lanes."""
        max_z = VERSION_Z_DEPTH.get(version, 0)
        target = Version(f"{version}.{max_z}")

        result = get_upgrade_paths_info(explorer, target_version=target, skip_target_check=True)

        expected_lane_names = compute_expected_lanes(
            version_str=version, z=max_z, supported_versions=SUPPORTED_VERSIONS
        )
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


@pytest.mark.e2e
class TestReleaseChecklistNegative:
    """Verify release checklist handles error scenarios correctly."""

    def test_non_existent_version_raises(self, explorer):
        with pytest.raises(ValueError, match="No stable build found"):
            get_upgrade_paths_info(explorer, target_version=Version("4.16.99"))

    def test_non_existent_minor_raises(self, explorer):
        with pytest.raises((ValueError, TimeoutError)):
            get_upgrade_paths_info(explorer, target_version=Version("4.99.1"))

    def test_already_released_without_flag_raises(self, explorer):
        with pytest.raises(ValueError, match="already released to prod"):
            get_upgrade_paths_info(explorer, target_version=Version("4.16.36"))

    def test_already_released_with_skip_succeeds(self, explorer):
        result = get_upgrade_paths_info(explorer, target_version=Version("4.16.36"), skip_target_check=True)
        assert result["target_version"] == "4.16.36"
        assert "upgrade_lanes" in result

    def test_old_version_with_skip_succeeds(self, explorer):
        result = get_upgrade_paths_info(explorer, target_version=Version("4.12.23"), skip_target_check=True)
        assert result["target_version"] == "4.12.23"
        assert "upgrade_lanes" in result
