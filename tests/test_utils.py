"""Tests for cnv_upgrade_utilities.utils module."""

import pytest

from cnv_upgrade_utilities.utils import (
    FULL_VERSION_PATTERN,
    MINOR_VERSION_PATTERN,
    SOURCE_VERSION_PATTERN,
    UpgradeType,
    VersionFormat,
    detect_version_format,
    determine_upgrade_type,
    is_eus_version,
    is_latest_z_source,
    parse_minor_version,
    parse_patch_version,
)


class TestVersionPatterns:
    """Tests for version regex patterns."""

    @pytest.mark.parametrize("version", ["4.20.0", "4.20.1", "4.20.10", "4.0.0", "4.99.99"])
    def test_full_version_pattern_valid(self, version):
        assert FULL_VERSION_PATTERN.match(version) is not None

    @pytest.mark.parametrize("version", ["4.20", "4.20.0.1", "5.20.0", "4.20.01"])
    def test_full_version_pattern_invalid(self, version):
        assert FULL_VERSION_PATTERN.match(version) is None

    @pytest.mark.parametrize("version", ["4.20", "4.0", "4.99"])
    def test_minor_version_pattern_valid(self, version):
        assert MINOR_VERSION_PATTERN.match(version) is not None

    @pytest.mark.parametrize("version", ["4.20.0", "4", "5.20"])
    def test_minor_version_pattern_invalid(self, version):
        assert MINOR_VERSION_PATTERN.match(version) is None

    @pytest.mark.parametrize("version", ["4.20", "4.20.0", "4.19", "4.19.0"])
    def test_source_version_pattern_valid(self, version):
        assert SOURCE_VERSION_PATTERN.match(version) is not None

    @pytest.mark.parametrize("version", ["4.20.1", "4.20.0.0", "5.20"])
    def test_source_version_pattern_invalid(self, version):
        assert SOURCE_VERSION_PATTERN.match(version) is None


class TestParseMinorVersion:
    """Tests for parse_minor_version function."""

    @pytest.mark.parametrize(
        "version,expected",
        [
            ("4.20", 20),
            ("4.19", 19),
            ("4.20.0", 20),
            ("4.20.5", 20),
            ("4.0", 0),
        ],
    )
    def test_parse_minor_version(self, version, expected):
        assert parse_minor_version(version) == expected


class TestParsePatchVersion:
    """Tests for parse_patch_version function."""

    @pytest.mark.parametrize(
        "version,expected",
        [
            ("4.20.0", 0),
            ("4.20.5", 5),
            ("4.20.10", 10),
            ("4.20", None),
            ("4.19", None),
            ("4.20.3.rhel9-18", 3),  # Bundle version
        ],
    )
    def test_parse_patch_version(self, version, expected):
        assert parse_patch_version(version) == expected


class TestDetectVersionFormat:
    """Tests for detect_version_format function."""

    @pytest.mark.parametrize(
        "version,expected",
        [
            ("4.20", VersionFormat.MINOR),
            ("4.20.0", VersionFormat.FULL),
            ("4.20.5", VersionFormat.FULL),
            ("4.20.3.rhel9-18", VersionFormat.BUNDLE),
        ],
    )
    def test_detect_version_format(self, version, expected):
        assert detect_version_format(version) == expected

    def test_detect_version_format_invalid(self):
        with pytest.raises(ValueError, match="Unrecognized version format"):
            detect_version_format("invalid")


class TestIsLatestZSource:
    """Tests for is_latest_z_source function."""

    @pytest.mark.parametrize(
        "version,expected",
        [
            ("4.20.0", True),
            ("4.19.0", True),
            ("4.20", False),
            ("4.20.1", False),
            ("4.20.0.rhel9-18", False),  # Bundle versions return False
        ],
    )
    def test_is_latest_z_source(self, version, expected):
        assert is_latest_z_source(version) == expected


class TestIsEusVersion:
    """Tests for is_eus_version function."""

    @pytest.mark.parametrize(
        "minor,expected",
        [
            (18, True),
            (20, True),
            (22, True),
            (17, False),
            (19, False),
            (21, False),
        ],
    )
    def test_is_eus_version(self, minor, expected):
        assert is_eus_version(minor) == expected


class TestDetermineUpgradeType:
    """Tests for determine_upgrade_type function."""

    # =========================================================================
    # Valid upgrade scenarios
    # =========================================================================

    @pytest.mark.parametrize(
        "source,target",
        [
            ("4.19", "4.20"),
            ("4.20", "4.21"),
            ("4.18", "4.19"),
        ],
    )
    def test_y_stream_upgrade(self, source, target):
        result = determine_upgrade_type(source, target)
        assert result == UpgradeType.Y_STREAM

    @pytest.mark.parametrize(
        "source,target",
        [
            ("4.20", "4.20"),
            ("4.19", "4.19"),
            ("4.20.1", "4.20.2"),
            ("4.20.1", "4.20"),  # Full to minor is valid Z_STREAM
        ],
    )
    def test_z_stream_upgrade(self, source, target):
        result = determine_upgrade_type(source, target)
        assert result == UpgradeType.Z_STREAM

    @pytest.mark.parametrize(
        "source,target",
        [
            ("4.18", "4.20"),
            ("4.20", "4.22"),
            ("4.16", "4.18"),
        ],
    )
    def test_eus_upgrade(self, source, target):
        result = determine_upgrade_type(source, target)
        assert result == UpgradeType.EUS

    @pytest.mark.parametrize(
        "source,target",
        [
            ("4.20.0", "4.20"),
            ("4.19.0", "4.19"),
            ("4.18.0", "4.18"),
        ],
    )
    def test_latest_z_upgrade(self, source, target):
        result = determine_upgrade_type(source, target)
        assert result == UpgradeType.LATEST_Z

    # =========================================================================
    # Edge case: Same version upgrade (must fail)
    # =========================================================================

    @pytest.mark.parametrize(
        "source,target",
        [
            ("4.20.5", "4.20.5"),
            ("4.19.3", "4.19.3"),
            ("4.20.0", "4.20.0"),  # 4.20.0 -> 4.20.0 is same version, not latest-z
        ],
    )
    def test_same_version_upgrade_fails(self, source, target):
        with pytest.raises(ValueError, match="same version"):
            determine_upgrade_type(source, target)

    # Note: 4.20 -> 4.20 is valid Z_STREAM (lookup for latest), tested above

    # =========================================================================
    # Edge case: Downgrade (must fail)
    # =========================================================================

    @pytest.mark.parametrize(
        "source,target",
        [
            ("4.20.5", "4.20.4"),  # Z-stream downgrade
            ("4.20.5", "4.20.1"),  # Z-stream downgrade
            ("4.20.10", "4.20.2"),  # Z-stream downgrade
        ],
    )
    def test_z_stream_downgrade_fails(self, source, target):
        with pytest.raises(ValueError, match="cannot downgrade within z-stream"):
            determine_upgrade_type(source, target)

    @pytest.mark.parametrize(
        "source,target",
        [
            ("4.21", "4.20"),  # Y-stream downgrade
            ("4.20", "4.19"),  # Y-stream downgrade
            ("4.22", "4.20"),  # Multi-version downgrade
        ],
    )
    def test_y_stream_downgrade_fails(self, source, target):
        with pytest.raises(ValueError, match="cannot downgrade"):
            determine_upgrade_type(source, target)

    # =========================================================================
    # Edge case: Version gap too large (must fail)
    # =========================================================================

    @pytest.mark.parametrize(
        "source,target",
        [
            ("4.18", "4.21"),  # Gap of 3
            ("4.17", "4.20"),  # Gap of 3
            ("4.16", "4.20"),  # Gap of 4
        ],
    )
    def test_version_gap_too_large_fails(self, source, target):
        with pytest.raises(ValueError, match="Unsupported upgrade"):
            determine_upgrade_type(source, target)

    # =========================================================================
    # Edge case: EUS with odd versions (must fail)
    # =========================================================================

    @pytest.mark.parametrize(
        "source,target",
        [
            ("4.17", "4.19"),  # Both odd
            ("4.19", "4.21"),  # Both odd
        ],
    )
    def test_eus_odd_versions_fails(self, source, target):
        with pytest.raises(ValueError, match="EUS upgrade requires both versions to be even"):
            determine_upgrade_type(source, target)

    # =========================================================================
    # Edge case: Latest-z cross-minor (must fail)
    # =========================================================================

    @pytest.mark.parametrize(
        "source,target",
        [
            ("4.19.0", "4.20"),  # Latest-z format but different minor
            ("4.18.0", "4.20"),  # Latest-z format but gap of 2
        ],
    )
    def test_latest_z_cross_minor_fails(self, source, target):
        with pytest.raises(ValueError, match="latest-z upgrade requires same minor version"):
            determine_upgrade_type(source, target)


class TestUpgradeTypeEnum:
    """Tests for UpgradeType enum."""

    def test_upgrade_type_values(self):
        assert UpgradeType.Y_STREAM.value == "y_stream"
        assert UpgradeType.Z_STREAM.value == "z_stream"
        assert UpgradeType.EUS.value == "eus"
        assert UpgradeType.LATEST_Z.value == "latest_z"

    def test_upgrade_type_display_names(self):
        assert UpgradeType.Y_STREAM.display_name == "Y stream"
        assert UpgradeType.Z_STREAM.display_name == "Z stream"
        assert UpgradeType.EUS.display_name == "EUS"
        assert UpgradeType.LATEST_Z.display_name == "latest z"

    def test_upgrade_type_minor_offsets(self):
        assert UpgradeType.Y_STREAM.minor_offset == -1
        assert UpgradeType.Z_STREAM.minor_offset == 0
        assert UpgradeType.EUS.minor_offset == -2
        assert UpgradeType.LATEST_Z.minor_offset is None

    @pytest.mark.parametrize(
        "z,minor,expected",
        [
            (1, 20, True),  # Z >= 1
            (2, 20, True),
            (0, 20, False),  # Z must be >= 1
        ],
    )
    def test_z_stream_is_applicable(self, z, minor, expected):
        assert UpgradeType.Z_STREAM.is_applicable_for_z(z, minor) == expected

    @pytest.mark.parametrize(
        "z,minor,expected",
        [
            (2, 20, True),  # Z >= 2
            (3, 20, True),
            (1, 20, False),  # Z must be >= 2
            (0, 20, False),
        ],
    )
    def test_latest_z_is_applicable(self, z, minor, expected):
        assert UpgradeType.LATEST_Z.is_applicable_for_z(z, minor) == expected

    @pytest.mark.parametrize(
        "z,minor,expected",
        [
            (0, 20, True),  # Z == 0 and even minor
            (0, 18, True),
            (0, 19, False),  # Odd minor
            (1, 20, False),  # Z must be 0
        ],
    )
    def test_eus_is_applicable(self, z, minor, expected):
        assert UpgradeType.EUS.is_applicable_for_z(z, minor) == expected

    @pytest.mark.parametrize(
        "z,minor,expected",
        [
            (0, 20, True),  # Not in SKIP_Y_STREAM_UPGRADE_MINORS
            (0, 19, True),
            (0, 12, False),  # In SKIP_Y_STREAM_UPGRADE_MINORS
            (0, 14, False),  # In SKIP_Y_STREAM_UPGRADE_MINORS
        ],
    )
    def test_y_stream_is_applicable(self, z, minor, expected):
        assert UpgradeType.Y_STREAM.is_applicable_for_z(z, minor) == expected
