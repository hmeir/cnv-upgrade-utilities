"""Post-upgrade test suite mapping and lookup."""

from cnv_upgrade_utilities.upgrade_types import UpgradeType

POST_UPGRADE_SUITE_FULL = "UTS-FULL"
POST_UPGRADE_SUITE_MARKER = "UTS-Marker"
POST_UPGRADE_SUITE_NONE = "NONE"

# upgrade_type -> {z_category -> suite}
# z categories: 0 = major (4.Y.0), 1 = first maintenance (4.Y.1), 2 = subsequent (4.Y.2+)
POST_UPGRADE_SUITE_MAP = {
    UpgradeType.Y_STREAM: {
        0: POST_UPGRADE_SUITE_FULL,
        1: POST_UPGRADE_SUITE_FULL,
        2: POST_UPGRADE_SUITE_MARKER,
    },
    UpgradeType.Z_STREAM: {
        1: POST_UPGRADE_SUITE_MARKER,
        2: POST_UPGRADE_SUITE_NONE,
    },
    UpgradeType.EUS: {
        0: POST_UPGRADE_SUITE_MARKER,
        2: POST_UPGRADE_SUITE_MARKER,
    },
    UpgradeType.LATEST_Z: {
        2: POST_UPGRADE_SUITE_NONE,
    },
}


def get_post_upgrade_suite(upgrade_type: UpgradeType, z: int) -> str:
    """Get post-upgrade suite for an upgrade type and z-stream value."""
    z_category = min(z, 2)
    return POST_UPGRADE_SUITE_MAP.get(upgrade_type, {}).get(z_category, POST_UPGRADE_SUITE_NONE)
