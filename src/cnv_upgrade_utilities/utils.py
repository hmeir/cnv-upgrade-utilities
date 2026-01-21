"""Common types and utilities shared across CNV upgrade utilities."""

import re
from enum import Enum

import click

# ============================================================================
# Version Regex Patterns
# ============================================================================
FULL_VERSION_PATTERN = re.compile(r"^4\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")  # 4.Y.z
MINOR_VERSION_PATTERN = re.compile(r"^4\.(0|[1-9]\d*)$")  # 4.Y
SOURCE_VERSION_PATTERN = re.compile(r"^4\.(0|[1-9]\d*)(\.0)?$")  # 4.Y or 4.Y.0

# ============================================================================
# Version Configuration
# ============================================================================
SKIP_Y_STREAM_UPGRADE_MINORS = frozenset({12, 14})

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


# Click parameter types for version validation
class FullVersionParamType(click.ParamType):
    """Click parameter type for full version validation (4.Y.z format)."""

    name = "version"

    def convert(self, value, param, ctx):
        if not FULL_VERSION_PATTERN.match(value):
            self.fail(
                f"Invalid version format: '{value}'. Expected format: 4.Y.z (e.g., 4.20.2)",
                param,
                ctx,
            )
        return value


class MinorVersionParamType(click.ParamType):
    """Click parameter type for minor version validation (4.Y format)."""

    name = "minor_version"

    def convert(self, value, param, ctx):
        if not MINOR_VERSION_PATTERN.match(value):
            self.fail(
                f"Invalid version format: '{value}'. Expected format: 4.Y (e.g., 4.20)",
                param,
                ctx,
            )
        return value


class SourceVersionParamType(click.ParamType):
    """Click parameter type for source version validation (4.Y or 4.Y.0 format)."""

    name = "source_version"

    def convert(self, value, param, ctx):
        if not SOURCE_VERSION_PATTERN.match(value):
            self.fail(
                f"Invalid version format: '{value}'. Expected format: 4.Y (e.g., 4.19) or 4.Y.0 for latest-z",
                param,
                ctx,
            )
        return value


# Pre-instantiated param types for convenience
FULL_VERSION_TYPE = FullVersionParamType()
MINOR_VERSION_TYPE = MinorVersionParamType()
SOURCE_VERSION_TYPE = SourceVersionParamType()


# ============================================================================
# Version Helper Functions
# ============================================================================


def parse_minor_version(version: str) -> int:
    """Extract the minor version number from a version string (4.Y or 4.Y.z)."""
    return int(version.split(".")[1])


def is_latest_z_source(source_version: str) -> bool:
    """Check if source version is in 4.Y.0 format (latest-z upgrade)."""
    return source_version.endswith(".0")


def is_eus_version(minor: int) -> bool:
    """Check if a minor version is EUS-eligible (even number)."""
    return minor % 2 == 0


def format_minor_version(version: str, prefix: str = "v") -> str:
    """
    Format a version string to minor version format with optional prefix.

    Args:
        version: Version string (e.g., "4.20", "4.20.0", "4.20.1")
        prefix: Prefix to add (default: "v")

    Returns:
        Formatted minor version (e.g., "v4.20")
    """
    parts = version.split(".")
    return f"{prefix}{parts[0]}.{parts[1]}"


def determine_upgrade_type(source_version: str, target_version: str) -> UpgradeType:
    """
    Determine the upgrade type based on source and target versions.

    Supported upgrade types:
    - 4.Y.0 -> 4.Y: latest-z (source must target the same Y)
    - 4.Y -> 4.Y: z-stream
    - 4.Y -> 4.Y+1: y-stream
    - 4.Y -> 4.Y+2: EUS (both Y versions must be even)

    Args:
        source_version: Source version (e.g., "4.19", "4.20", or "4.20.0" for latest-z)
        target_version: Target version (e.g., "4.20")

    Returns:
        UpgradeType enum value

    Raises:
        ValueError: If the upgrade is unsupported
    """
    source_minor = parse_minor_version(source_version)
    target_minor = parse_minor_version(target_version)

    # Check for latest-z first (source is 4.Y.0)
    if is_latest_z_source(source_version):
        if source_minor != target_minor:
            raise ValueError(
                f"Unsupported upgrade: latest-z upgrade requires same minor version. "
                f"source={source_version}, target={target_version}"
            )
        return UpgradeType.LATEST_Z

    version_diff = target_minor - source_minor

    if version_diff == 0:
        return UpgradeType.Z_STREAM
    elif version_diff == 1:
        return UpgradeType.Y_STREAM
    elif version_diff == 2:
        if is_eus_version(source_minor) and is_eus_version(target_minor):
            return UpgradeType.EUS
        raise ValueError(
            f"Unsupported upgrade: EUS upgrade requires both versions to be even. "
            f"source={source_version} (minor={source_minor}), target={target_version} (minor={target_minor})"
        )

    raise ValueError(f"Unsupported upgrade: source={source_version}, target={target_version}")


def get_applicable_upgrade_types(target_minor: int, target_z: int) -> list[UpgradeType]:
    """
    Get all applicable upgrade types for a target version.

    Args:
        target_minor: Target minor version number (e.g., 20)
        target_z: Target z-stream value (e.g., 0, 1, 2)

    Returns:
        List of applicable UpgradeType enum values
    """
    return [upgrade_type for upgrade_type in UpgradeType if upgrade_type.is_applicable_for_z(target_z, target_minor)]
