"""E2E tests for upgrade_jobs_info using MINOR version format (4.Y)."""

import logging

import pytest

from cnv_upgrade_utilities.upgrade_jobs_info import get_upgrade_jobs_info

from .conftest import assert_upgrade_result_valid

LOGGER = logging.getLogger("cnv_e2e")


@pytest.mark.e2e
class TestMinorFormatPaths:
    """Upgrade paths using MINOR version format (4.Y)."""

    def test_minor_format(self, explorer, minor_paths):
        total = len(minor_paths)
        for i, (source_version, target_version, upgrade_type) in enumerate(minor_paths, 1):
            LOGGER.info("[%d/%d] minor_format: %s -> %s (%s)", i, total, source_version, target_version, upgrade_type)
            result = get_upgrade_jobs_info(explorer, source_version=source_version, target_version=target_version)
            assert_upgrade_result_valid(result, source_version, target_version, upgrade_type)
