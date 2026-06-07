"""E2E tests for upgrade_jobs_info using BUNDLE version format (4.Y.Z.rhelR-BN)."""

import logging

import pytest

from cnv_upgrade_utilities.upgrade_jobs_info import get_upgrade_jobs_info

from .conftest import assert_upgrade_result_valid

LOGGER = logging.getLogger("cnv_e2e")


@pytest.mark.e2e
class TestBundleFormatPaths:
    """Upgrade paths using BUNDLE version format (4.Y.Z.rhelR-BN).

    Discovers real bundle versions by first resolving via MINOR format,
    then re-tests with the exact bundle versions returned.
    """

    def test_bundle_format(self, explorer, same_minor_paths):
        total = len(same_minor_paths)
        for i, (source_version, target_version, upgrade_type) in enumerate(same_minor_paths, 1):
            LOGGER.info("[%d/%d] bundle_format: %s -> %s (%s)", i, total, source_version, target_version, upgrade_type)
            minor_result = get_upgrade_jobs_info(explorer, source_version=source_version, target_version=target_version)
            source_bundle = minor_result["source"]["bundle_version"]
            target_bundle = minor_result["target"]["bundle_version"]

            result = get_upgrade_jobs_info(explorer, source_version=source_bundle, target_version=target_bundle)
            assert_upgrade_result_valid(result, source_bundle, target_bundle, upgrade_type)
