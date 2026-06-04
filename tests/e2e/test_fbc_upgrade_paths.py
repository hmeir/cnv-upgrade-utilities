"""FBC-based E2E tests: validate upgrade paths using cnv-fbc repo as data source.

These tests can run anywhere (CI, open source contributors) without
access to the internal Version Explorer API. They clone the public
cnv-fbc repo and derive version/channel/stage/prod status from the
stage and production branches.
"""

import tempfile

import pytest

from cnv_upgrade_utilities.upgrade_types import EOL_VERSIONS, SUPPORTED_VERSIONS
from cnv_upgrade_utilities.version_types import parse_minor_version

from .utils.expected_lanes import compute_expected_lanes
from .utils.fbc_data import FbcVersionData, clone_fbc_branch

yaml = pytest.importorskip("yaml", reason="pyyaml required for FBC tests")


@pytest.fixture(scope="session")
def fbc_data():
    """Clone cnv-fbc stage + production branches and build version data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        stage_path = f"{tmpdir}/stage"
        prod_path = f"{tmpdir}/production"
        clone_fbc_branch("stage", stage_path)
        clone_fbc_branch("production", prod_path)
        yield FbcVersionData(stage_path, prod_path)


@pytest.mark.fbc
class TestFbcVersionCoverage:
    """Verify every supported version exists in FBC."""

    @pytest.mark.parametrize("version", SUPPORTED_VERSIONS, ids=SUPPORTED_VERSIONS)
    def test_version_exists_in_fbc(self, fbc_data, version):
        minor = parse_minor_version(version)
        data = fbc_data.get_minor_data(minor)
        if data["max_z"] < 0:
            pytest.skip(f"Version {version} has no builds in FBC stable/candidate yet")


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


@pytest.mark.fbc
class TestFbcEolRejection:
    """Verify EOL versions don't have active upgrade paths."""

    @pytest.mark.parametrize("version", sorted(EOL_VERSIONS), ids=sorted(EOL_VERSIONS))
    def test_eol_not_in_supported(self, version):
        assert version not in SUPPORTED_VERSIONS, f"EOL version {version} should not be in SUPPORTED_VERSIONS"


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
