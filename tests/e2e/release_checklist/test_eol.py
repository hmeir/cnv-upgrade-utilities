"""E2E tests for release_checklist_upgrade_plan — EOL version rejection."""

import pytest
from packaging.version import Version

from cnv_upgrade_utilities.release_checklist_upgrade_plan import get_upgrade_paths_info
from cnv_upgrade_utilities.upgrade_types import EOL_VERSIONS


@pytest.mark.e2e
class TestReleaseChecklistEol:
    """Verify EOL versions are rejected by release checklist."""

    @pytest.mark.parametrize("version", sorted(EOL_VERSIONS), ids=sorted(EOL_VERSIONS))
    def test_eol_version_rejected(self, explorer, version):
        target = Version(f"{version}.1")
        with pytest.raises(ValueError, match="EOL"):
            get_upgrade_paths_info(explorer, target_version=target, skip_target_check=True)
