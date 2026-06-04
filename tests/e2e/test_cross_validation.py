"""Cross-validation: compare FBC-derived data against Version Explorer API.

Only runs when both FBC repo and Version Explorer API are accessible.
Catches discrepancies between the two data sources.
"""

import tempfile

import pytest

from cnv_upgrade_utilities.upgrade_types import SUPPORTED_VERSIONS
from cnv_upgrade_utilities.version_types import parse_minor_version
from utils.version_explorer import CnvVersionExplorer

from .utils.fbc_data import FbcVersionData, clone_fbc_branch

yaml = pytest.importorskip("yaml", reason="pyyaml required for cross-validation tests")

pytestmark = [pytest.mark.e2e, pytest.mark.fbc]


@pytest.fixture(scope="session")
def cross_validation_data():
    """Set up both FBC and API data sources for comparison."""
    with tempfile.TemporaryDirectory() as tmpdir:
        stage_path = f"{tmpdir}/stage"
        prod_path = f"{tmpdir}/production"
        clone_fbc_branch("stage", stage_path)
        clone_fbc_branch("production", prod_path)
        fbc = FbcVersionData(stage_path, prod_path)

        with CnvVersionExplorer(request_timeout=10, retry_timeout=15) as explorer:
            yield fbc, explorer


@pytest.mark.parametrize("version", SUPPORTED_VERSIONS, ids=SUPPORTED_VERSIONS)
def test_released_versions_match(cross_validation_data, version):
    """Versions that FBC shows as released should also be released in Version Explorer."""
    fbc, explorer = cross_validation_data
    minor = parse_minor_version(version)

    fbc_data = fbc.get_minor_data(minor)
    fbc_released = {
        v for v, info in fbc_data["versions"].items() if info["released_to_prod"] and info["channel"] == "stable"
    }

    api_builds = explorer.get_released_builds(minor_version=f"v4.{minor}", stage=False)
    api_released = {b.csv_version.lstrip("v") for b in api_builds}

    # API should contain the latest released versions from FBC.
    # Older versions may be purged from the API, so we only check the latest few.
    if api_released and fbc_released:
        fbc_latest = max(fbc_released, key=lambda v: int(v.split(".")[2]))
        assert fbc_latest in api_released, f"4.{minor}: FBC latest released {fbc_latest} not found in Version Explorer"


@pytest.mark.parametrize("version", SUPPORTED_VERSIONS, ids=SUPPORTED_VERSIONS)
def test_max_z_consistent(cross_validation_data, version):
    """Max z-stream depth should be consistent between FBC and Version Explorer."""
    fbc, explorer = cross_validation_data
    minor = parse_minor_version(version)

    fbc_max_z = fbc.get_max_z(minor)

    api_builds = explorer.get_released_builds(minor_version=f"v4.{minor}", stage=True)
    api_max_z = -1
    for build in api_builds:
        csv = build.csv_version.lstrip("v")
        parts = csv.split(".")
        if len(parts) >= 3 and csv.startswith(f"4.{minor}."):
            api_max_z = max(api_max_z, int(parts[2]))

    # Allow API to be ahead (more recent data), but not behind
    if fbc_max_z > api_max_z and api_max_z >= 0:
        pytest.fail(
            f"4.{minor}: FBC has max_z={fbc_max_z} but API has max_z={api_max_z}. Version Explorer may be behind FBC."
        )
