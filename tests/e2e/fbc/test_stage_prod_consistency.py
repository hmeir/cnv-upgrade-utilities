"""FBC stage/production consistency tests: verify consistency between FBC branches."""

import pytest

from cnv_upgrade_utilities.upgrade_types import SUPPORTED_VERSIONS
from cnv_upgrade_utilities.version_types import parse_minor_version

yaml = pytest.importorskip("yaml", reason="pyyaml required for FBC tests")


@pytest.mark.fbc
class TestFbcStageProductionConsistency:
    """Verify consistency between FBC stage and production branches."""

    @pytest.mark.parametrize("version", SUPPORTED_VERSIONS, ids=SUPPORTED_VERSIONS)
    def test_production_is_subset_of_stage(self, fbc_data, version):
        """Every version in production/stable should also be in stage/stable."""
        minor = parse_minor_version(version)
        data = fbc_data.get_minor_data(minor)
        for v, info in data["versions"].items():
            if info["released_to_prod"] and info["channel"] == "stable":
                assert info["in_stage"], f"{v}: released to prod but not in stage — data inconsistency"
