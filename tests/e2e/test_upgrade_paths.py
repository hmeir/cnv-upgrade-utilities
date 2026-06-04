"""Structural E2E tests for upgrade path resolution against live Version Explorer API."""

import pytest

from cnv_upgrade_utilities.upgrade_jobs_info import get_upgrade_jobs_info
from cnv_upgrade_utilities.upgrade_types import SUPPORTED_VERSIONS
from cnv_upgrade_utilities.version_types import parse_minor_version, parse_patch_version

from .conftest import NEGATIVE_PATHS, VERSION_Z_DEPTH, generate_minor_paths


def _path_id(source_version: str, target_version: str, upgrade_type: str) -> str:
    return f"{upgrade_type}:{source_version}->{target_version}"


MINOR_PATHS = [
    pytest.param(
        source_version, target_version, upgrade_type, id=_path_id(source_version, target_version, upgrade_type)
    )
    for source_version, target_version, upgrade_type in generate_minor_paths()
]


def assert_upgrade_result_valid(result: dict, source_version: str, target_version: str, expected_type: str) -> None:
    """Validate structural correctness of an upgrade result."""
    assert result["upgrade_type"] == expected_type

    source_info = result["source"]
    target_info = result["target"]

    assert source_info["channel"] == "stable"
    assert source_info.get("released_to_prod") is True
    assert source_info["version"]
    assert source_info["bundle_version"]
    assert source_info["iib"]

    assert target_info["version"]
    assert target_info["bundle_version"]
    assert target_info["iib"]

    expected_source_minor = parse_minor_version(source_version)
    expected_target_minor = parse_minor_version(target_version)
    assert parse_minor_version(source_info["version"]) == expected_source_minor
    assert parse_minor_version(target_info["version"]) == expected_target_minor

    if expected_type == "z_stream":
        source_patch = parse_patch_version(source_info["version"])
        target_patch = parse_patch_version(target_info["version"])
        assert source_patch is not None and target_patch is not None
        assert (
            target_patch >= source_patch
        ), f"Z-stream target {target_info['version']} should be >= source {source_info['version']}"

    elif expected_type == "latest_z":
        assert source_info["version"].endswith(".0"), f"Latest-Z source should be X.Y.0, got {source_info['version']}"

    elif expected_type in ("y_stream", "eus"):
        assert target_info["channel"] == "stable"


# ============================================================================
# MINOR format tests (4.Y → 4.Y)
# ============================================================================


@pytest.mark.e2e
class TestMinorFormatPaths:
    """Upgrade paths using MINOR version format (4.Y)."""

    @pytest.mark.parametrize(("source_version", "target_version", "expected_type"), MINOR_PATHS)
    def test_minor_format(self, explorer, source_version, target_version, expected_type):
        result = get_upgrade_jobs_info(explorer, source_version=source_version, target_version=target_version)
        assert_upgrade_result_valid(result, source_version, target_version, expected_type)


# ============================================================================
# FULL format tests (4.Y.Z → 4.Y.Z)
# ============================================================================


@pytest.mark.e2e
class TestFullFormatPaths:
    """Upgrade paths using FULL version format (4.Y.Z).

    Discovers real version numbers by first resolving via MINOR format,
    then re-tests with the specific X.Y.Z versions returned.
    """

    @pytest.mark.parametrize(("source_version", "target_version", "expected_type"), MINOR_PATHS)
    def test_full_format(self, explorer, source_version, target_version, expected_type):
        minor_result = get_upgrade_jobs_info(explorer, source_version=source_version, target_version=target_version)
        source_full = minor_result["source"]["version"]
        target_full = minor_result["target"]["version"]

        if expected_type == "latest_z":
            source_full = f"{source_version.rsplit('.', 1)[0]}.0"

        result = get_upgrade_jobs_info(explorer, source_version=source_full, target_version=target_full)
        assert_upgrade_result_valid(result, source_full, target_full, expected_type)


# ============================================================================
# BUNDLE format tests (4.Y.Z.rhelR-BN → 4.Y.Z.rhelR-BN)
# ============================================================================


@pytest.mark.e2e
class TestBundleFormatPaths:
    """Upgrade paths using BUNDLE version format (4.Y.Z.rhelR-BN).

    Discovers real bundle versions by first resolving via MINOR format,
    then re-tests with the exact bundle versions returned.
    """

    @pytest.mark.parametrize(("source_version", "target_version", "expected_type"), MINOR_PATHS)
    def test_bundle_format(self, explorer, source_version, target_version, expected_type):
        minor_result = get_upgrade_jobs_info(explorer, source_version=source_version, target_version=target_version)
        source_bundle = minor_result["source"]["bundle_version"]
        target_bundle = minor_result["target"]["bundle_version"]

        result = get_upgrade_jobs_info(explorer, source_version=source_bundle, target_version=target_bundle)
        assert_upgrade_result_valid(result, source_bundle, target_bundle, expected_type)


# ============================================================================
# Mixed format tests (source and target in different formats)
# ============================================================================


@pytest.mark.e2e
class TestMixedFormatPaths:
    """Upgrade paths with source and target in different version formats."""

    @pytest.mark.parametrize(("source_version", "target_version", "expected_type"), MINOR_PATHS)
    def test_minor_source_full_target(self, explorer, source_version, target_version, expected_type):
        minor_result = get_upgrade_jobs_info(explorer, source_version=source_version, target_version=target_version)
        target_full = minor_result["target"]["version"]
        result = get_upgrade_jobs_info(explorer, source_version=source_version, target_version=target_full)
        assert_upgrade_result_valid(result, source_version, target_full, expected_type)

    @pytest.mark.parametrize(("source_version", "target_version", "expected_type"), MINOR_PATHS)
    def test_full_source_bundle_target(self, explorer, source_version, target_version, expected_type):
        minor_result = get_upgrade_jobs_info(explorer, source_version=source_version, target_version=target_version)
        source_full = minor_result["source"]["version"]
        target_bundle = minor_result["target"]["bundle_version"]

        if expected_type == "latest_z":
            source_full = f"{source_version.rsplit('.', 1)[0]}.0"

        result = get_upgrade_jobs_info(explorer, source_version=source_full, target_version=target_bundle)
        assert_upgrade_result_valid(result, source_full, target_bundle, expected_type)


# ============================================================================
# Supported version coverage smoke test
# ============================================================================


@pytest.mark.e2e
class TestSupportedVersionCoverage:
    """Verify every SUPPORTED_VERSIONS entry with released builds works for Z-stream."""

    @pytest.mark.parametrize(
        "version",
        [v for v in SUPPORTED_VERSIONS if VERSION_Z_DEPTH.get(v, -1) >= 1],
        ids=[v for v in SUPPORTED_VERSIONS if VERSION_Z_DEPTH.get(v, -1) >= 1],
    )
    def test_z_stream_works(self, explorer, version):
        result = get_upgrade_jobs_info(explorer, source_version=version, target_version=version)
        assert result["upgrade_type"] == "z_stream"


# ============================================================================
# Negative tests
# ============================================================================


@pytest.mark.e2e
class TestNegativeUpgradePaths:
    """Validate that invalid upgrade paths raise appropriate errors."""

    @pytest.mark.parametrize(("source_version", "target_version"), NEGATIVE_PATHS)
    def test_invalid_path_raises(self, explorer, source_version, target_version):
        with pytest.raises((ValueError, TimeoutError)):
            get_upgrade_jobs_info(explorer, source_version=source_version, target_version=target_version)
