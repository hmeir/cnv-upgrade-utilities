"""E2E tests for supported version coverage."""

import logging

import pytest

from cnv_upgrade_utilities.upgrade_jobs_info import get_upgrade_jobs_info

LOGGER = logging.getLogger("cnv_e2e")


@pytest.mark.e2e
class TestSupportedVersionCoverage:
    """Verify every SUPPORTED_VERSIONS entry with released builds works for Z-stream."""

    def test_z_stream_works(self, explorer, versions_with_z1):
        total = len(versions_with_z1)
        for i, version in enumerate(versions_with_z1, 1):
            LOGGER.info("[%d/%d] z_stream_coverage: %s", i, total, version)
            result = get_upgrade_jobs_info(explorer, source_version=version, target_version=version)
            assert result["upgrade_type"] == "z_stream"
