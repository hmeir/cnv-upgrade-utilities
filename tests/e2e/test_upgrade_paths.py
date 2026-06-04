"""Structural E2E tests for upgrade path resolution against live Version Explorer API."""

import pytest

from cnv_upgrade_utilities.upgrade_jobs_info import get_upgrade_jobs_info
from cnv_upgrade_utilities.upgrade_types import SUPPORTED_VERSIONS
from cnv_upgrade_utilities.version_types import parse_minor_version, parse_patch_version

from .conftest import NEGATIVE_PATHS, generate_minor_paths, get_version_z_depth


def _path_id(source_version: str, target_version: str, upgrade_type: str) -> str:
    return f"{upgrade_type}:{source_version}->{target_version}"


_ALL_MINOR_PATHS = generate_minor_paths()

MINOR_PATHS = [
    pytest.param(
        source_version, target_version, upgrade_type, id=_path_id(source_version, target_version, upgrade_type)
    )
    for source_version, target_version, upgrade_type in _ALL_MINOR_PATHS
]

SAME_MINOR_PATHS = [
    pytest.param(
        source_version, target_version, upgrade_type, id=_path_id(source_version, target_version, upgrade_type)
    )
    for source_version, target_version, upgrade_type in _ALL_MINOR_PATHS
    if upgrade_type in ("z_stream", "latest_z")
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

    @pytest.mark.parametrize(("source_version", "target_version", "expected_type"), SAME_MINOR_PATHS)
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

    @pytest.mark.parametrize(("source_version", "target_version", "expected_type"), SAME_MINOR_PATHS)
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

    @pytest.mark.parametrize(("source_version", "target_version", "expected_type"), SAME_MINOR_PATHS)
    def test_minor_source_full_target(self, explorer, source_version, target_version, expected_type):
        minor_result = get_upgrade_jobs_info(explorer, source_version=source_version, target_version=target_version)
        target_full = minor_result["target"]["version"]
        result = get_upgrade_jobs_info(explorer, source_version=source_version, target_version=target_full)
        assert_upgrade_result_valid(result, source_version, target_full, expected_type)

    @pytest.mark.parametrize(("source_version", "target_version", "expected_type"), SAME_MINOR_PATHS)
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
        [v for v in SUPPORTED_VERSIONS if get_version_z_depth().get(v, -1) >= 1],
        ids=[v for v in SUPPORTED_VERSIONS if get_version_z_depth().get(v, -1) >= 1],
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
        """4.19.0 → 4.20 is a valid Y-stream (source .0 doesn't force latest-z when minors differ)."""
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
        """4.22 → 5.0 should produce clean error, not KeyError crash."""
        with pytest.raises(ValueError, match="No released builds found|No stable"):
            get_upgrade_jobs_info(explorer, source_version="4.22", target_version="5.0")


@pytest.mark.e2e
class TestCLIErrorHandling:
    """Verify CLI commands produce clean errors (no Python tracebacks)."""

    @pytest.mark.parametrize(
        ("args", "expected_error"),
        [
            (["-s", "4.20", "-t", "4.19"], "Error:"),
            (["-s", "4.15", "-t", "4.16"], "Error:"),
            (["-s", "4.20.5", "-t", "4.20.5"], "Error:"),
        ],
        ids=["downgrade", "eol-source", "same-version"],
    )
    def test_upgrade_jobs_info_clean_error(self, args, expected_error):
        import subprocess

        result = subprocess.run(
            ["uv", "run", "upgrade_jobs_info", *args],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 1
        assert expected_error in result.stderr
        assert "Traceback" not in result.stderr

    @pytest.mark.parametrize(
        ("args", "expected_error"),
        [
            (["-v", "4.16.99"], "Error:"),
            (["-v", "4.13.5", "--skip-target-check"], "Error:"),
        ],
        ids=["non-existent-version", "eol-version"],
    )
    def test_release_checklist_clean_error(self, args, expected_error):
        import subprocess

        result = subprocess.run(
            ["uv", "run", "release_checklist_upgrade_plan", *args],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 1
        assert expected_error in result.stderr
        assert "Traceback" not in result.stderr
