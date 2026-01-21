"""
Constants shared across CNV upgrade utilities.

This module centralizes constant values used across multiple modules,
including channel names and API constants.
"""

# ============================================================================
# Channel Constants
# ============================================================================
CHANNEL_STABLE = "stable"
CHANNEL_CANDIDATE = "candidate"
VALID_CHANNELS = (CHANNEL_STABLE, CHANNEL_CANDIDATE)

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
