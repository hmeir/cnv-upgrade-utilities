import pytest

from cnv_upgrade_utilities.version_types import (
    BUNDLE_VERSION_PATTERN,
    FLEXIBLE_VERSION_PATTERN,
    FULL_VERSION_PATTERN,
    MINOR_VERSION_PATTERN,
    VersionFormat,
    detect_version_format,
    format_minor_version,
    is_latest_z_source,
    parse_major_version,
    parse_minor_version,
    parse_patch_version,
    strip_bundle_suffix,
)


class TestRegexPatterns:
    @pytest.mark.parametrize(
        "version",
        ["4.20.0", "4.20.1", "4.0.0", "4.20.99", "4.100.200", "5.0.0", "5.0.1"],
    )
    def test_full_version_valid(self, version):
        assert FULL_VERSION_PATTERN.match(version)

    @pytest.mark.parametrize(
        "version",
        ["4.20", "4.20.0.rhel9-1", "3.20.0", "v4.20.0", "4.20.01", "4.020.0", "4.20.0.1", "6.0.0"],
    )
    def test_full_version_invalid(self, version):
        assert not FULL_VERSION_PATTERN.match(version)

    @pytest.mark.parametrize(
        "version",
        ["4.20", "4.0", "4.1", "4.100", "5.0", "5.1"],
    )
    def test_minor_version_valid(self, version):
        assert MINOR_VERSION_PATTERN.match(version)

    @pytest.mark.parametrize(
        "version",
        ["4.20.0", "4.020", "3.20", "v4.20", "4.20.0.rhel9-1", "6.0"],
    )
    def test_minor_version_invalid(self, version):
        assert not MINOR_VERSION_PATTERN.match(version)

    @pytest.mark.parametrize(
        "version",
        ["4.20.3.rhel9-31", "4.0.0.rhel8-1", "4.20.99.rhel9-100", "5.0.0.rhel9-1", "4.12.24-22"],
    )
    def test_bundle_version_valid(self, version):
        assert BUNDLE_VERSION_PATTERN.match(version)

    @pytest.mark.parametrize(
        "version",
        ["4.20.3", "4.20", "4.20.3.rhel-1", "4.20.3.rhel91", "v4.20.3.rhel9-31", "6.0.0.rhel9-1"],
    )
    def test_bundle_version_invalid(self, version):
        assert not BUNDLE_VERSION_PATTERN.match(version)

    @pytest.mark.parametrize(
        "version",
        [
            "4.20",
            "4.20.3",
            "4.20.3.rhel9-31",
            "4.0",
            "4.0.0",
            "4.0.0.rhel8-1",
            "5.0",
            "5.0.0",
            "5.0.0.rhel9-1",
            "4.12.24-22",
        ],
    )
    def test_flexible_version_valid(self, version):
        assert FLEXIBLE_VERSION_PATTERN.match(version)

    @pytest.mark.parametrize(
        "version",
        ["3.20", "v4.20", "4.20.3.1", "4.020.3", "6.0"],
    )
    def test_flexible_version_invalid(self, version):
        assert not FLEXIBLE_VERSION_PATTERN.match(version)


class TestStripBundleSuffix:
    @pytest.mark.parametrize(
        ("version", "expected"),
        [
            ("4.20.3.rhel9-31", "4.20.3"),
            ("4.12.24-22", "4.12.24"),
            ("4.20.0.rhel9-234", "4.20.0"),
            ("4.12.0-769", "4.12.0"),
            ("4.20.3", "4.20.3"),
            ("4.20", "4.20"),
        ],
    )
    def test_strip_bundle_suffix(self, version, expected):
        assert strip_bundle_suffix(version) == expected


class TestParseMajorVersion:
    @pytest.mark.parametrize(
        ("version", "expected"),
        [
            ("4.20", 4),
            ("5.0", 5),
            ("4.20.3", 4),
            ("5.0.1", 5),
        ],
    )
    def test_parse_major_version(self, version, expected):
        assert parse_major_version(version) == expected


class TestParseMinorVersion:
    @pytest.mark.parametrize(
        ("version", "expected"),
        [
            ("4.20", 20),
            ("4.0", 0),
            ("4.20.5", 20),
            ("4.100", 100),
            ("4.20.3.rhel9-31", 20),
        ],
    )
    def test_parse_minor_version(self, version, expected):
        assert parse_minor_version(version) == expected


class TestParsePatchVersion:
    @pytest.mark.parametrize(
        ("version", "expected"),
        [
            ("4.20.5", 5),
            ("4.20.0", 0),
            ("4.20.99", 99),
            ("4.20.3.rhel9-31", 3),
            ("4.20.0.rhel9-1", 0),
            ("4.12.24-22", 24),
            ("4.12.0-769", 0),
            ("4.20", None),
            ("4.0", None),
        ],
    )
    def test_parse_patch_version(self, version, expected):
        assert parse_patch_version(version) == expected


class TestDetectVersionFormat:
    @pytest.mark.parametrize(
        ("version", "expected"),
        [
            ("4.20", VersionFormat.MINOR),
            ("4.0", VersionFormat.MINOR),
            ("4.20.3", VersionFormat.FULL),
            ("4.20.0", VersionFormat.FULL),
            ("4.20.3.rhel9-31", VersionFormat.BUNDLE),
        ],
    )
    def test_valid_formats(self, version, expected):
        assert detect_version_format(version) == expected

    @pytest.mark.parametrize("version", ["invalid", "3.20.0", "v4.20.0", ""])
    def test_invalid_format_raises(self, version):
        with pytest.raises(ValueError, match="Unrecognized version format"):
            detect_version_format(version)


class TestIsLatestZSource:
    @pytest.mark.parametrize(
        ("version", "expected"),
        [
            ("4.20.0", True),
            ("4.0.0", True),
            ("4.20.1", False),
            ("4.20", False),
            ("4.20.0.rhel9-1", True),
            ("4.20.1.rhel9-5", False),
        ],
    )
    def test_is_latest_z_source(self, version, expected):
        assert is_latest_z_source(version) == expected


class TestFormatMinorVersion:
    @pytest.mark.parametrize(
        ("version", "prefix", "expected"),
        [
            ("4.20", "v", "v4.20"),
            ("4.20.5", "v", "v4.20"),
            ("4.20.0", "", "4.20"),
            ("4.0", "v", "v4.0"),
        ],
    )
    def test_format_minor_version(self, version, prefix, expected):
        assert format_minor_version(version, prefix=prefix) == expected

    def test_format_minor_version_default_prefix(self):
        assert format_minor_version("4.20") == "v4.20"


class TestVersionFormatEnum:
    def test_values(self):
        assert VersionFormat.MINOR.value == "minor"
        assert VersionFormat.FULL.value == "full"
        assert VersionFormat.BUNDLE.value == "bundle"
