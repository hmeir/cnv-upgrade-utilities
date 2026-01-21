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
