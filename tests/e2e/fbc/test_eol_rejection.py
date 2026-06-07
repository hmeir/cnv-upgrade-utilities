"""FBC EOL rejection tests: verify EOL versions don't have active upgrade paths."""

import pytest

from cnv_upgrade_utilities.upgrade_types import EOL_VERSIONS, SUPPORTED_VERSIONS


@pytest.mark.fbc
class TestFbcEolRejection:
    """Verify EOL versions don't have active upgrade paths."""

    @pytest.mark.parametrize("version", sorted(EOL_VERSIONS), ids=sorted(EOL_VERSIONS))
    def test_eol_not_in_supported(self, version):
        assert version not in SUPPORTED_VERSIONS, f"EOL version {version} should not be in SUPPORTED_VERSIONS"
