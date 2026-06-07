"""E2E tests for upgrade_jobs_info using FULL version format (4.Y.Z)."""

import logging

import pytest

from cnv_upgrade_utilities.upgrade_jobs_info import get_upgrade_jobs_info

from .conftest import assert_upgrade_result_valid

LOGGER = logging.getLogger("cnv_e2e")


@pytest.mark.e2e
class TestFullFormatPaths:
    """Upgrade paths using FULL version format (4.Y.Z).

    Discovers real version numbers by first resolving via MINOR format,
    then re-tests with the specific X.Y.Z versions returned.
    """

    def test_full_format(self, explorer, same_minor_paths):
        total = len(same_minor_paths)
        for i, (source_version, target_version, upgrade_type) in enumerate(same_minor_paths, 1):
            LOGGER.info("[%d/%d] full_format: %s -> %s (%s)", i, total, source_version, target_version, upgrade_type)
            minor_result = get_upgrade_jobs_info(explorer, source_version=source_version, target_version=target_version)
            source_full = minor_result["source"]["version"]
            target_full = minor_result["target"]["version"]

            if upgrade_type == "latest_z":
                source_full = f"{source_version.rsplit('.', 1)[0]}.0"

            result = get_upgrade_jobs_info(explorer, source_version=source_full, target_version=target_full)
            assert_upgrade_result_valid(result, source_full, target_full, upgrade_type)
