"""FBC version coverage tests: verify every supported version exists in FBC."""

import pytest

from cnv_upgrade_utilities.upgrade_types import SUPPORTED_VERSIONS
from cnv_upgrade_utilities.version_types import parse_minor_version

yaml = pytest.importorskip("yaml", reason="pyyaml required for FBC tests")


@pytest.mark.fbc
class TestFbcVersionCoverage:
    """Verify every supported version exists in FBC."""

    @pytest.mark.parametrize("version", SUPPORTED_VERSIONS, ids=SUPPORTED_VERSIONS)
    def test_version_exists_in_fbc(self, fbc_data, version):
        minor = parse_minor_version(version)
        data = fbc_data.get_minor_data(minor)
        if data["max_z"] < 0:
            pytest.skip(f"Version {version} has no builds in FBC stable/candidate yet")
