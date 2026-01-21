"""
Constants shared across CNV upgrade utilities.

This module centralizes all constant values used throughout the application,
including channel names, version patterns, supported versions, and API constants.
"""

import re
from enum import Enum

# ============================================================================
# Channel Constants
# ============================================================================
CHANNEL_STABLE = "stable"
CHANNEL_CANDIDATE = "candidate"
VALID_CHANNELS = (CHANNEL_STABLE, CHANNEL_CANDIDATE)

# ============================================================================
# Version Configuration
# ============================================================================
SUPPORTED_MINORS = (12, 14, 16, 17, 18, 19, 20, 21)
SKIP_Y_STREAM_UPGRADE_MINORS = frozenset({12, 14})

# ============================================================================
# Version Regex Patterns
# ============================================================================
FULL_VERSION_PATTERN = re.compile(r"^4\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")  # 4.Y.z
MINOR_VERSION_PATTERN = re.compile(r"^4\.(0|[1-9]\d*)$")  # 4.Y
SOURCE_VERSION_PATTERN = re.compile(r"^4\.(0|[1-9]\d*)(\.0)?$")  # 4.Y or 4.Y.0

# ============================================================================
# Post-Upgrade Suite Constants
# ============================================================================
POST_UPGRADE_SUITE_FULL = "UTS-FULL"
POST_UPGRADE_SUITE_MARKER = "UTS-Marker"
POST_UPGRADE_SUITE_NONE = "NONE"

# Z-stream categories for post-upgrade suite mapping
Z_CATEGORY_ZERO = 0  # Major release (4.Y.0)
Z_CATEGORY_ONE = 1  # First maintenance (4.Y.1)
Z_CATEGORY_TWO_PLUS = 2  # Subsequent maintenance (4.Y.2+)

# ============================================================================
# Build Data Keys
# ============================================================================
BUNDLE_VERSION_KEY_CNV_BUILD = "cnv_build"
BUNDLE_VERSION_KEY_VERSION = "version"

# ============================================================================
# Errata Status Constants
# ============================================================================
ERRATA_STATUS_SHIPPED_LIVE = "SHIPPED_LIVE"
ERRATA_STATUS_TRUE = "true"


# ============================================================================
# Environment Variable Names
# ============================================================================
ENV_VERSION_EXPLORER_URL = "VERSION_EXPLORER_URL"


# ============================================================================
# Upgrade Type Enumeration
# ============================================================================
class UpgradeType(Enum):
    """
    Upgrade type enumeration.

    Attributes:
        value: String identifier (e.g., "y_stream")
        display_name: Human-readable name (e.g., "Y stream")
        minor_offset: Offset for source version calculation (None for latest-z)
    """

    Y_STREAM = ("y_stream", "Y stream", -1)
    Z_STREAM = ("z_stream", "Z stream", 0)
    EUS = ("eus", "EUS", -2)
    LATEST_Z = ("latest_z", "latest z", None)

    def __init__(self, value: str, display_name: str, minor_offset: int | None):
        self._value_ = value
        self.display_name = display_name
        self.minor_offset = minor_offset

    def is_applicable_for_z(self, z: int, minor: int) -> bool:
        """
        Check if this upgrade type applies for a given z-stream and minor version.

        Args:
            z: Z-stream value (e.g., 0, 1, 2)
            minor: Minor version number (e.g., 12, 20)

        Returns:
            True if this upgrade type is applicable
        """
        match self:
            case UpgradeType.Z_STREAM:
                return z >= 1
            case UpgradeType.LATEST_Z:
                return z >= 2
            case UpgradeType.Y_STREAM:
                return minor not in SKIP_Y_STREAM_UPGRADE_MINORS
            case UpgradeType.EUS:
                return z == 0 and minor % 2 == 0
            case _:
                return False


# ============================================================================
# Post-Upgrade Suite Mapping
# ============================================================================

# Static mapping: upgrade_type -> {z_category -> post_upgrade_suite}
# This mapping explicitly defines post-upgrade suite rules based on upgrade type
# and z-stream category, matching the rules documented in README.md
POST_UPGRADE_SUITE_MAP = {
    UpgradeType.Y_STREAM: {
        Z_CATEGORY_ZERO: POST_UPGRADE_SUITE_FULL,  # 4.Y.0 -> UTS-FULL
        Z_CATEGORY_ONE: POST_UPGRADE_SUITE_FULL,  # 4.Y.1 -> UTS-FULL
        Z_CATEGORY_TWO_PLUS: POST_UPGRADE_SUITE_MARKER,  # 4.Y.2+ -> UTS-Marker
    },
    UpgradeType.Z_STREAM: {
        Z_CATEGORY_ONE: POST_UPGRADE_SUITE_MARKER,  # 4.Y.1 -> UTS-Marker
        Z_CATEGORY_TWO_PLUS: POST_UPGRADE_SUITE_NONE,  # 4.Y.2+ -> NONE
    },
    UpgradeType.EUS: {
        Z_CATEGORY_ZERO: POST_UPGRADE_SUITE_MARKER,  # 4.Y.0 -> UTS-Marker
    },
    UpgradeType.LATEST_Z: {
        Z_CATEGORY_TWO_PLUS: POST_UPGRADE_SUITE_NONE,  # 4.Y.2+ -> NONE
    },
}


def normalize_z_category(z: int) -> int:
    """
    Normalize z-stream value to category (0, 1, or 2+).

    Args:
        z: Z-stream value

    Returns:
        Normalized category constant
    """
    if z == 0:
        return Z_CATEGORY_ZERO
    elif z == 1:
        return Z_CATEGORY_ONE
    else:
        return Z_CATEGORY_TWO_PLUS


def get_post_upgrade_suite(upgrade_type: UpgradeType, z: int) -> str:
    """
    Get post-upgrade suite for an upgrade type and z-stream value.

    Uses the static POST_UPGRADE_SUITE_MAP to determine the appropriate
    post-upgrade suite based on upgrade type and z-stream category.

    Args:
        upgrade_type: The upgrade type
        z: Z-stream value (e.g., 0, 1, 2)

    Returns:
        Post-upgrade suite identifier (e.g., "UTS-FULL", "UTS-Marker", "NONE")
    """
    z_category = normalize_z_category(z)
    return POST_UPGRADE_SUITE_MAP.get(upgrade_type, {}).get(z_category, POST_UPGRADE_SUITE_NONE)
