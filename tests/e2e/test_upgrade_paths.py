"""Structural E2E tests for upgrade path resolution against live Version Explorer API."""

import pytest

from cnv_upgrade_utilities.upgrade_jobs_info import get_upgrade_jobs_info
from cnv_upgrade_utilities.version_types import parse_minor_version, parse_patch_version

from .conftest import NEGATIVE_PATHS, generate_minor_paths


def _path_id(source: str, target: str, upgrade_type: str) -> str:
    return f"{upgrade_type}:{source}->{target}"


MINOR_PATHS = [pytest.param(s, t, ut, id=_path_id(s, t, ut)) for s, t, ut in generate_minor_paths()]


def _assert_common(result, source, target, expected_type):
    """Assertions common to all upgrade types and formats."""
    assert result["upgrade_type"] == expected_type

    src = result["source"]
    tgt = result["target"]

    assert src["channel"] == "stable"
    assert src.get("released_to_prod") is True
    assert src["version"]
    assert src["bundle_version"]
    assert src["iib"]

    assert tgt["version"]
    assert tgt["bundle_version"]
    assert tgt["iib"]

    source_minor = parse_minor_version(source)
    target_minor = parse_minor_version(target)
    assert parse_minor_version(src["version"]) == source_minor
    assert parse_minor_version(tgt["version"]) == target_minor

    if expected_type == "z_stream":
        src_z = parse_patch_version(src["version"])
        tgt_z = parse_patch_version(tgt["version"])
        assert src_z is not None and tgt_z is not None
        assert tgt_z >= src_z, f"Z-stream target {tgt['version']} should be >= source {src['version']}"

    elif expected_type == "latest_z":
        assert src["version"].endswith(".0"), f"Latest-Z source should be X.Y.0, got {src['version']}"

    elif expected_type in ("y_stream", "eus"):
        assert tgt["channel"] == "stable"
        assert tgt.get("released_to_prod") is True


# ============================================================================
# MINOR format tests (4.Y → 4.Y)
# ============================================================================


@pytest.mark.e2e
class TestMinorFormatPaths:
    """Upgrade paths using MINOR version format (4.Y)."""

    @pytest.mark.parametrize(("source", "target", "expected_type"), MINOR_PATHS)
    def test_minor_format(self, explorer, source, target, expected_type):
        result = get_upgrade_jobs_info(explorer, source_version=source, target_version=target)
        _assert_common(result, source, target, expected_type)


# ============================================================================
# FULL format tests (4.Y.Z → 4.Y.Z)
# ============================================================================


@pytest.mark.e2e
class TestFullFormatPaths:
    """
    Upgrade paths using FULL version format (4.Y.Z).

    Discovers real version numbers by first resolving via MINOR format,
    then re-tests with the specific X.Y.Z versions returned.
    """

    @pytest.mark.parametrize(("source", "target", "expected_type"), MINOR_PATHS)
    def test_full_format(self, explorer, source, target, expected_type):
        minor_result = get_upgrade_jobs_info(explorer, source_version=source, target_version=target)
        src_full = minor_result["source"]["version"]
        tgt_full = minor_result["target"]["version"]

        if expected_type == "latest_z":
            # Latest-Z source must be 4.Y.0 in FULL format
            src_full = f"4.{parse_minor_version(source)}.0"

        result = get_upgrade_jobs_info(explorer, source_version=src_full, target_version=tgt_full)
        _assert_common(result, src_full, tgt_full, expected_type)


# ============================================================================
# BUNDLE format tests (4.Y.Z.rhelR-BN → 4.Y.Z.rhelR-BN)
# ============================================================================


@pytest.mark.e2e
class TestBundleFormatPaths:
    """
    Upgrade paths using BUNDLE version format (4.Y.Z.rhelR-BN).

    Discovers real bundle versions by first resolving via MINOR format,
    then re-tests with the exact bundle versions returned.
    """

    @pytest.mark.parametrize(("source", "target", "expected_type"), MINOR_PATHS)
    def test_bundle_format(self, explorer, source, target, expected_type):
        minor_result = get_upgrade_jobs_info(explorer, source_version=source, target_version=target)
        src_bundle = minor_result["source"]["bundle_version"]
        tgt_bundle = minor_result["target"]["bundle_version"]

        result = get_upgrade_jobs_info(explorer, source_version=src_bundle, target_version=tgt_bundle)
        _assert_common(result, src_bundle, tgt_bundle, expected_type)


# ============================================================================
# Mixed format tests (source and target in different formats)
# ============================================================================


@pytest.mark.e2e
class TestMixedFormatPaths:
    """Upgrade paths with source and target in different version formats."""

    @pytest.mark.parametrize(("source", "target", "expected_type"), MINOR_PATHS)
    def test_minor_source_full_target(self, explorer, source, target, expected_type):
        """Source as MINOR, target as FULL."""
        minor_result = get_upgrade_jobs_info(explorer, source_version=source, target_version=target)
        tgt_full = minor_result["target"]["version"]
        result = get_upgrade_jobs_info(explorer, source_version=source, target_version=tgt_full)
        _assert_common(result, source, tgt_full, expected_type)

    @pytest.mark.parametrize(("source", "target", "expected_type"), MINOR_PATHS)
    def test_full_source_bundle_target(self, explorer, source, target, expected_type):
        """Source as FULL, target as BUNDLE."""
        minor_result = get_upgrade_jobs_info(explorer, source_version=source, target_version=target)
        src_full = minor_result["source"]["version"]
        tgt_bundle = minor_result["target"]["bundle_version"]

        if expected_type == "latest_z":
            src_full = f"4.{parse_minor_version(source)}.0"

        result = get_upgrade_jobs_info(explorer, source_version=src_full, target_version=tgt_bundle)
        _assert_common(result, src_full, tgt_bundle, expected_type)


# ============================================================================
# Negative tests
# ============================================================================


@pytest.mark.e2e
class TestNegativeUpgradePaths:
    """Validate that invalid upgrade paths raise appropriate errors."""

    @pytest.mark.parametrize(("source", "target"), NEGATIVE_PATHS)
    def test_invalid_path_raises(self, explorer, source, target):
        with pytest.raises((ValueError, TimeoutError)):
            get_upgrade_jobs_info(explorer, source_version=source, target_version=target)
