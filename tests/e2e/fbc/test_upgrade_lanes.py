"""FBC upgrade lane tests: verify upgrade lanes match expected rules using FBC data."""

import pytest

from cnv_upgrade_utilities.upgrade_types import SUPPORTED_VERSIONS
from cnv_upgrade_utilities.version_types import parse_minor_version

from ..utils.expected_lanes import compute_expected_lanes

yaml = pytest.importorskip("yaml", reason="pyyaml required for FBC tests")


@pytest.mark.fbc
class TestFbcUpgradeLanes:
    """Verify upgrade lanes match expected rules using FBC data."""

    @pytest.mark.parametrize("version", SUPPORTED_VERSIONS, ids=SUPPORTED_VERSIONS)
    def test_lanes_at_max_z(self, fbc_data, version):
        """Verify expected upgrade lanes exist at the max available z for each version."""
        minor = parse_minor_version(version)
        data = fbc_data.get_minor_data(minor)
        max_z = data["max_z"]
        if max_z < 0:
            pytest.skip(f"No builds in FBC for {version}")

        expected = compute_expected_lanes(version, z=max_z, supported_versions=SUPPORTED_VERSIONS)

        # Verify source builds exist for each expected lane
        if "Z stream" in expected:
            assert data["latest_released"] is not None, (
                f"{version}: Z-stream expected but no released stable build in FBC"
            )

        if "Y stream" in expected:
            source_minor = minor - 1
            source_data = fbc_data.get_minor_data(source_minor)
            assert source_data["latest_released"] is not None, (
                f"{version}: Y-stream expected but no released stable build for 4.{source_minor}"
            )

        if "EUS" in expected:
            source_minor = minor - 2
            source_data = fbc_data.get_minor_data(source_minor)
            assert source_data["latest_released"] is not None, (
                f"{version}: EUS expected but no released stable build for 4.{source_minor}"
            )

        if "latest z" in expected:
            if f"4.{minor}.0" not in data["versions"]:
                pytest.skip(f"{version}: 4.{minor}.0 not in FBC graph (initial release not in channel entries)")
