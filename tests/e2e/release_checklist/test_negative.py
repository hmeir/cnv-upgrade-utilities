"""E2E tests for release_checklist_upgrade_plan — negative/error scenarios."""

import pytest
from packaging.version import Version

from cnv_upgrade_utilities.release_checklist_upgrade_plan import get_upgrade_paths_info


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
