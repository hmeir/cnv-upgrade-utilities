"""E2E tests for negative upgrade paths and error messages."""

import logging

import pytest

from cnv_upgrade_utilities.upgrade_jobs_info import get_upgrade_jobs_info

LOGGER = logging.getLogger("cnv_e2e")


@pytest.mark.e2e
class TestNegativeUpgradePaths:
    """Validate that invalid upgrade paths raise appropriate errors."""

    def test_invalid_path_raises(self, explorer, negative_paths):
        total = len(negative_paths)
        for i, (source_version, target_version) in enumerate(negative_paths, 1):
            LOGGER.info("[%d/%d] negative: %s -> %s", i, total, source_version, target_version)
            with pytest.raises((ValueError, TimeoutError)):
                get_upgrade_jobs_info(explorer, source_version=source_version, target_version=target_version)


@pytest.mark.e2e
class TestNegativeWithErrorMessages:
    """Verify specific error messages for each failure scenario."""

    def test_downgrade_minor_error_message(self, explorer):
        with pytest.raises(ValueError, match="cannot downgrade"):
            get_upgrade_jobs_info(explorer, source_version="4.20", target_version="4.19")

    def test_downgrade_z_stream_error_message(self, explorer):
        with pytest.raises(ValueError, match="cannot downgrade within z-stream"):
            get_upgrade_jobs_info(explorer, source_version="4.20.5", target_version="4.20.4")

    def test_same_version_error_message(self, explorer):
        with pytest.raises(ValueError, match="same version"):
            get_upgrade_jobs_info(explorer, source_version="4.20.5", target_version="4.20.5")

    def test_unsupported_gap_error_message(self, explorer):
        with pytest.raises(ValueError, match="Unsupported upgrade"):
            get_upgrade_jobs_info(explorer, source_version="4.16", target_version="4.19")

    def test_odd_eus_error_message(self, explorer):
        with pytest.raises(ValueError, match="EUS upgrade requires both versions to be even"):
            get_upgrade_jobs_info(explorer, source_version="4.17", target_version="4.19")

    def test_dot_zero_cross_minor_is_y_stream(self, explorer):
        """4.19.0 -> 4.20 is a valid Y-stream (source .0 doesn't force latest-z when minors differ)."""
        result = get_upgrade_jobs_info(explorer, source_version="4.19.0", target_version="4.20")
        assert result["upgrade_type"] == "y_stream"

    def test_eol_source_error_message(self, explorer):
        with pytest.raises(ValueError, match="EOL"):
            get_upgrade_jobs_info(explorer, source_version="4.15", target_version="4.16")

    def test_eol_target_error_message(self, explorer):
        with pytest.raises(ValueError, match="EOL"):
            get_upgrade_jobs_info(explorer, source_version="4.12", target_version="4.13")

    def test_non_existent_full_target_error_message(self, explorer):
        with pytest.raises(ValueError, match="No stable"):
            get_upgrade_jobs_info(explorer, source_version="4.16.0", target_version="4.16.99")

    def test_cross_major_downgrade_error_message(self, explorer):
        with pytest.raises(ValueError, match="cannot downgrade"):
            get_upgrade_jobs_info(explorer, source_version="5.0", target_version="4.22")

    def test_cross_major_non_existent_target_clean_error(self, explorer):
        """4.22 -> 5.0 should produce clean error, not KeyError crash."""
        with pytest.raises(ValueError, match="No released builds found|No stable"):
            get_upgrade_jobs_info(explorer, source_version="4.22", target_version="5.0")
