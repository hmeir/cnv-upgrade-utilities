import pytest

from cnv_upgrade_utilities.upgrade_types import (
    EOL_VERSIONS,
    SKIP_Y_STREAM_UPGRADE_MINORS,
    SUPPORTED_VERSIONS,
    UpgradeType,
    determine_upgrade_type,
    get_applicable_upgrade_types,
    is_eol_version,
    is_eus_version,
)


class TestIsEusVersion:
    @pytest.mark.parametrize(
        ("minor", "expected"),
        [
            (18, True),
            (20, True),
            (0, True),
            (19, False),
            (21, False),
        ],
    )
    def test_is_eus_version(self, minor, expected):
        assert is_eus_version(minor) == expected


class TestUpgradeTypeIsApplicableForZ:
    @pytest.mark.parametrize(
        ("upgrade_type", "z", "minor", "expected"),
        [
            (UpgradeType.Z_STREAM, 0, 20, False),
            (UpgradeType.Z_STREAM, 1, 20, True),
            (UpgradeType.Z_STREAM, 5, 20, True),
            (UpgradeType.LATEST_Z, 0, 20, False),
            (UpgradeType.LATEST_Z, 1, 20, False),
            (UpgradeType.LATEST_Z, 2, 20, True),
            (UpgradeType.LATEST_Z, 5, 20, True),
            (UpgradeType.Y_STREAM, 0, 20, True),
            (UpgradeType.Y_STREAM, 1, 20, True),
            (UpgradeType.Y_STREAM, 0, 12, False),
            (UpgradeType.Y_STREAM, 0, 14, False),
            (UpgradeType.Y_STREAM, 0, 16, False),
            (UpgradeType.EUS, 0, 20, True),
            (UpgradeType.EUS, 0, 18, True),
            (UpgradeType.EUS, 0, 19, False),
            (UpgradeType.EUS, 1, 20, False),
            (UpgradeType.EUS, 0, 12, False),
            (UpgradeType.EUS, 0, 14, True),
            (UpgradeType.EUS, 0, 16, True),
        ],
    )
    def test_is_applicable_for_z(self, upgrade_type, z, minor, expected):
        assert upgrade_type.is_applicable_for_z(z, minor) == expected


class TestDetermineUpgradeType:
    @pytest.mark.parametrize(
        ("source", "target", "expected"),
        [
            ("4.19", "4.20", UpgradeType.Y_STREAM),
            ("4.0", "4.1", UpgradeType.Y_STREAM),
            ("4.20", "4.20", UpgradeType.Z_STREAM),
            ("4.20.1", "4.20.5", UpgradeType.Z_STREAM),
            ("4.18", "4.20", UpgradeType.EUS),
            ("4.20", "4.22", UpgradeType.EUS),
            ("4.20.0", "4.20", UpgradeType.LATEST_Z),
            ("4.20.0", "4.20.5", UpgradeType.LATEST_Z),
        ],
    )
    def test_valid_upgrades(self, source, target, expected):
        assert determine_upgrade_type(source, target) == expected

    def test_same_full_version_raises(self):
        with pytest.raises(ValueError, match="same version"):
            determine_upgrade_type("4.20.5", "4.20.5")

    def test_z_stream_downgrade_raises(self):
        with pytest.raises(ValueError, match="cannot downgrade within z-stream"):
            determine_upgrade_type("4.20.5", "4.20.4")

    def test_y_stream_downgrade_raises(self):
        with pytest.raises(ValueError, match="cannot downgrade"):
            determine_upgrade_type("4.21", "4.20")

    def test_eus_odd_versions_raises(self):
        with pytest.raises(ValueError, match="EUS upgrade requires both versions to be even"):
            determine_upgrade_type("4.19", "4.21")

    def test_latest_z_cross_minor_raises(self):
        # 4.19.0 → 4.20 is a valid Y-stream upgrade (source happens to be .0)
        assert determine_upgrade_type("4.19.0", "4.20") == UpgradeType.Y_STREAM

    def test_unsupported_gap_raises(self):
        with pytest.raises(ValueError, match="Unsupported upgrade"):
            determine_upgrade_type("4.18", "4.21")

    def test_large_gap_raises(self):
        with pytest.raises(ValueError, match="Unsupported upgrade"):
            determine_upgrade_type("4.16", "4.20")

    def test_eol_source_raises(self):
        with pytest.raises(ValueError, match="EOL"):
            determine_upgrade_type("4.15", "4.16")

    def test_eol_target_raises(self):
        with pytest.raises(ValueError, match="EOL"):
            determine_upgrade_type("4.12", "4.13")

    def test_eol_both_raises(self):
        with pytest.raises(ValueError, match="EOL"):
            determine_upgrade_type("4.13", "4.13")

    def test_cross_major_upgrade(self):
        assert determine_upgrade_type("4.22", "5.0") == UpgradeType.Y_STREAM

    def test_cross_major_downgrade_raises(self):
        with pytest.raises(ValueError, match="cannot downgrade"):
            determine_upgrade_type("5.0", "4.22")

    def test_dot_zero_source_cross_minor_is_eus(self):
        assert determine_upgrade_type("4.16.0", "4.18") == UpgradeType.EUS

    def test_dot_zero_source_cross_minor_is_y_stream(self):
        assert determine_upgrade_type("4.16.0", "4.17") == UpgradeType.Y_STREAM

    def test_dot_zero_bundle_cross_minor_is_eus(self):
        assert determine_upgrade_type("4.16.0.rhel9-2746", "4.18") == UpgradeType.EUS


class TestIsEolVersion:
    @pytest.mark.parametrize(
        ("version", "expected"),
        [
            ("4.13", True),
            ("4.15", True),
            ("4.13.5", True),
            ("4.15.10", True),
            ("4.12", False),
            ("4.16", False),
            ("4.20", False),
        ],
    )
    def test_is_eol_version(self, version, expected):
        assert is_eol_version(version) == expected


class TestGetApplicableUpgradeTypes:
    def test_z0_even_minor(self):
        result = get_applicable_upgrade_types(target_minor=20, target_z=0)
        assert UpgradeType.Y_STREAM in result
        assert UpgradeType.EUS in result
        assert UpgradeType.Z_STREAM not in result
        assert UpgradeType.LATEST_Z not in result

    def test_z1(self):
        result = get_applicable_upgrade_types(target_minor=20, target_z=1)
        assert UpgradeType.Y_STREAM in result
        assert UpgradeType.Z_STREAM in result
        assert UpgradeType.EUS not in result
        assert UpgradeType.LATEST_Z not in result

    def test_z2_plus(self):
        result = get_applicable_upgrade_types(target_minor=20, target_z=3)
        assert UpgradeType.Y_STREAM in result
        assert UpgradeType.Z_STREAM in result
        assert UpgradeType.LATEST_Z in result
        assert UpgradeType.EUS not in result

    def test_z0_odd_minor(self):
        result = get_applicable_upgrade_types(target_minor=21, target_z=0)
        assert UpgradeType.Y_STREAM in result
        assert UpgradeType.EUS not in result

    def test_skip_minor_y_stream(self):
        for minor in SKIP_Y_STREAM_UPGRADE_MINORS:
            result = get_applicable_upgrade_types(target_minor=minor, target_z=0)
            assert UpgradeType.Y_STREAM not in result

    def test_4_12_no_y_stream_no_eus(self):
        result = get_applicable_upgrade_types(target_minor=12, target_z=0)
        assert UpgradeType.Y_STREAM not in result
        assert UpgradeType.EUS not in result

    def test_4_14_no_y_stream_yes_eus(self):
        result = get_applicable_upgrade_types(target_minor=14, target_z=0)
        assert UpgradeType.Y_STREAM not in result
        assert UpgradeType.EUS in result

    def test_4_16_no_y_stream_yes_eus(self):
        result = get_applicable_upgrade_types(target_minor=16, target_z=0)
        assert UpgradeType.Y_STREAM not in result
        assert UpgradeType.EUS in result

    def test_4_17_yes_y_stream_no_eus(self):
        result = get_applicable_upgrade_types(target_minor=17, target_z=0)
        assert UpgradeType.Y_STREAM in result
        assert UpgradeType.EUS not in result


class TestUpgradeTypeAttributes:
    def test_y_stream_attributes(self):
        assert UpgradeType.Y_STREAM.value == "y_stream"
        assert UpgradeType.Y_STREAM.display_name == "Y stream"
        assert UpgradeType.Y_STREAM.minor_offset == -1

    def test_z_stream_attributes(self):
        assert UpgradeType.Z_STREAM.value == "z_stream"
        assert UpgradeType.Z_STREAM.minor_offset == 0

    def test_eus_attributes(self):
        assert UpgradeType.EUS.value == "eus"
        assert UpgradeType.EUS.minor_offset == -2

    def test_latest_z_attributes(self):
        assert UpgradeType.LATEST_Z.value == "latest_z"
        assert UpgradeType.LATEST_Z.minor_offset is None


class TestVersionConstants:
    def test_supported_versions_match_expected(self):
        expected = ["4.12", "4.14", "4.16", "4.17", "4.18", "4.19", "4.20", "4.21", "4.22"]
        assert SUPPORTED_VERSIONS == expected

    def test_eol_versions_match_expected(self):
        expected = {"4.13", "4.15"}
        assert EOL_VERSIONS == expected

    def test_no_overlap_supported_and_eol(self):
        assert not set(SUPPORTED_VERSIONS) & EOL_VERSIONS

    def test_skip_y_stream_minors_match_expected(self):
        expected = frozenset({12, 14, 16})
        assert SKIP_Y_STREAM_UPGRADE_MINORS == expected
