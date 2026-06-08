import pytest

from cnv_upgrade_utilities.post_upgrade_suites import (
    POST_UPGRADE_SUITE_FULL,
    POST_UPGRADE_SUITE_MARKER,
    POST_UPGRADE_SUITE_NONE,
    get_post_upgrade_suite,
)
from cnv_upgrade_utilities.upgrade_types import UpgradeType


class TestGetPostUpgradeSuite:
    @pytest.mark.parametrize(
        ("upgrade_type", "z", "expected"),
        [
            (UpgradeType.Y_STREAM, 0, POST_UPGRADE_SUITE_FULL),
            (UpgradeType.Y_STREAM, 1, POST_UPGRADE_SUITE_FULL),
            (UpgradeType.Y_STREAM, 2, POST_UPGRADE_SUITE_MARKER),
            (UpgradeType.Y_STREAM, 5, POST_UPGRADE_SUITE_MARKER),
            (UpgradeType.Z_STREAM, 1, POST_UPGRADE_SUITE_MARKER),
            (UpgradeType.Z_STREAM, 2, POST_UPGRADE_SUITE_NONE),
            (UpgradeType.Z_STREAM, 5, POST_UPGRADE_SUITE_NONE),
            (UpgradeType.EUS, 0, POST_UPGRADE_SUITE_MARKER),
            (UpgradeType.EUS, 2, POST_UPGRADE_SUITE_MARKER),
            (UpgradeType.EUS, 5, POST_UPGRADE_SUITE_MARKER),
            (UpgradeType.LATEST_Z, 2, POST_UPGRADE_SUITE_NONE),
            (UpgradeType.LATEST_Z, 5, POST_UPGRADE_SUITE_NONE),
        ],
    )
    def test_post_upgrade_suite(self, upgrade_type, z, expected):
        assert get_post_upgrade_suite(upgrade_type, z) == expected

    def test_unmapped_returns_none_suite(self):
        assert get_post_upgrade_suite(UpgradeType.Z_STREAM, 0) == POST_UPGRADE_SUITE_NONE
