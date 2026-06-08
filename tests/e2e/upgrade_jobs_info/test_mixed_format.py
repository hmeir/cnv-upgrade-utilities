"""E2E tests for upgrade_jobs_info using mixed version formats."""

import logging

import pytest

from cnv_upgrade_utilities.upgrade_jobs_info import get_upgrade_jobs_info

from ..utils.assertions import assert_upgrade_result_valid

LOGGER = logging.getLogger("cnv_e2e")


@pytest.mark.e2e
class TestMixedFormatPaths:
    """Upgrade paths with source and target in different version formats."""

    def test_minor_source_full_target(self, explorer, same_minor_paths):
        total = len(same_minor_paths)
        for i, (source_version, target_version, upgrade_type) in enumerate(same_minor_paths, 1):
            LOGGER.info("[%d/%d] minor->full: %s -> %s (%s)", i, total, source_version, target_version, upgrade_type)
            minor_result = get_upgrade_jobs_info(explorer, source_version=source_version, target_version=target_version)
            target_full = minor_result["target"]["version"]
            result = get_upgrade_jobs_info(explorer, source_version=source_version, target_version=target_full)
            assert_upgrade_result_valid(result, source_version, target_full, upgrade_type)

    def test_full_source_bundle_target(self, explorer, same_minor_paths):
        total = len(same_minor_paths)
        for i, (source_version, target_version, upgrade_type) in enumerate(same_minor_paths, 1):
            LOGGER.info("[%d/%d] full->bundle: %s -> %s (%s)", i, total, source_version, target_version, upgrade_type)
            minor_result = get_upgrade_jobs_info(explorer, source_version=source_version, target_version=target_version)
            source_full = minor_result["source"]["version"]
            target_bundle = minor_result["target"]["bundle_version"]

            if upgrade_type == "latest_z":
                source_full = f"{source_version.rsplit('.', 1)[0]}.0"

            result = get_upgrade_jobs_info(explorer, source_version=source_full, target_version=target_bundle)
            assert_upgrade_result_valid(result, source_full, target_bundle, upgrade_type)
