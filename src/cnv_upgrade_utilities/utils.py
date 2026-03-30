"""Common types and utilities shared across CNV upgrade utilities."""

import re
from enum import Enum

import click

# ============================================================================
# Version Regex Patterns
# ============================================================================
FULL_VERSION_PATTERN = re.compile(r"^4\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")  # 4.Y.z
MINOR_VERSION_PATTERN = re.compile(r"^4\.(0|[1-9]\d*)$")  # 4.Y
BUNDLE_VERSION_PATTERN = re.compile(r"^4\.(0|[1-9]\d*)\.(0|[1-9]\d*)\.rhel\d+-\d+$")  # 4.Y.Z.rhelR-BN

# Unified pattern accepting all three formats: 4.Y, 4.Y.Z, or 4.Y.Z.rhelR-BN
FLEXIBLE_VERSION_PATTERN = re.compile(
    r"^4\.(0|[1-9]\d*)"  # 4.Y (required base)
    r"(?:\.(0|[1-9]\d*)"  # .Z (optional)
    r"(?:\.rhel\d+-\d+)?)?$"  # .rhelR-BN (optional, only if .Z exists)
)

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
# Version Format Enumeration
# ============================================================================
class VersionFormat(Enum):
    """
    Enum representing different version format types.

    Used to detect and handle the three supported version formats:
    - MINOR: X.Y (e.g., 4.20)
    - FULL: X.Y.Z (e.g., 4.20.3)
    - BUNDLE: X.Y.Z.rhelR-BN (e.g., 4.20.3.rhel9-18)
    """

    MINOR = "minor"
    FULL = "full"
    BUNDLE = "bundle"


def detect_version_format(version: str) -> VersionFormat:
    """
    Detect the format of a version string.

    Args:
        version: Version string to analyze

    Returns:
        VersionFormat enum value

    Raises:
        ValueError: If version format is not recognized
    """
    if BUNDLE_VERSION_PATTERN.match(version):
        return VersionFormat.BUNDLE
    elif FULL_VERSION_PATTERN.match(version):
        return VersionFormat.FULL
    elif MINOR_VERSION_PATTERN.match(version):
        return VersionFormat.MINOR
    else:
        raise ValueError(f"Unrecognized version format: {version}")


# ============================================================================
# Post-Upgrade Suite Mapping
# ============================================================================

# Post-upgrade suite mapping: upgrade_type -> {z_category -> suite}
# z categories: 0 = major (4.Y.0), 1 = first maintenance (4.Y.1), 2 = subsequent (4.Y.2+)
POST_UPGRADE_SUITE_MAP = {
    UpgradeType.Y_STREAM: {
        0: POST_UPGRADE_SUITE_FULL,  # 4.Y.0 -> UTS-FULL
        1: POST_UPGRADE_SUITE_FULL,  # 4.Y.1 -> UTS-FULL
        2: POST_UPGRADE_SUITE_MARKER,  # 4.Y.2+ -> UTS-Marker
    },
    UpgradeType.Z_STREAM: {
        1: POST_UPGRADE_SUITE_MARKER,  # 4.Y.1 -> UTS-Marker
        2: POST_UPGRADE_SUITE_NONE,  # 4.Y.2+ -> NONE
    },
    UpgradeType.EUS: {
        0: POST_UPGRADE_SUITE_MARKER,  # 4.Y.0 -> UTS-Marker
    },
    UpgradeType.LATEST_Z: {
        2: POST_UPGRADE_SUITE_NONE,  # 4.Y.2+ -> NONE
    },
}


def get_post_upgrade_suite(upgrade_type: UpgradeType, z: int) -> str:
    """
    Get post-upgrade suite for an upgrade type and z-stream value.

    Args:
        upgrade_type: The upgrade type
        z: Z-stream value (e.g., 0, 1, 2)

    Returns:
        Post-upgrade suite identifier (e.g., "UTS-FULL", "UTS-Marker", "NONE")
    """
    z_category = min(z, 2)
    return POST_UPGRADE_SUITE_MAP.get(upgrade_type, {}).get(z_category, POST_UPGRADE_SUITE_NONE)


# Click parameter type for version validation
class VersionParamType(click.ParamType):
    """Generic Click parameter type for version validation against a regex pattern."""

    def __init__(self, pattern: re.Pattern, name: str, example: str):
        self.pattern = pattern
        self.name = name
        self.example = example

    def convert(self, value, param, ctx):
        if not self.pattern.match(value):
            self.fail(
                f"Invalid version format: '{value}'. Expected format: {self.example}",
                param,
                ctx,
            )
        return value


# Pre-instantiated param types for convenience
FULL_VERSION_TYPE = VersionParamType(pattern=FULL_VERSION_PATTERN, name="version", example="4.Y.z (e.g., 4.20.2)")
FLEXIBLE_VERSION_TYPE = VersionParamType(
    pattern=FLEXIBLE_VERSION_PATTERN,
    name="flexible_version",
    example="4.Y (e.g., 4.20), 4.Y.Z (e.g., 4.20.3), or 4.Y.Z.rhelR-BN (e.g., 4.20.3.rhel9-18)",
)


# ============================================================================
# Version Helper Functions
# ============================================================================


def parse_minor_version(version: str) -> int:
    """Extract the minor version number from a version string (4.Y or 4.Y.z)."""
    return int(version.split(".")[1])


def parse_patch_version(version: str) -> int | None:
    """
    Extract the patch version number from a full version string (4.Y.z).

    Returns None for minor-only versions (4.Y).

    Args:
        version: Version string (4.Y, 4.Y.z, or 4.Y.z.rhelR-BN format)

    Returns:
        Patch version number or None if not a full version
    """
    version_format = detect_version_format(version)
    if version_format == VersionFormat.BUNDLE:
        # Extract from bundle: 4.20.3.rhel9-18 -> 3
        parts = version.rsplit(".rhel", 1)[0].split(".")
        return int(parts[2]) if len(parts) >= 3 else None
    elif version_format == VersionFormat.FULL:
        parts = version.split(".")
        return int(parts[2])
    return None


def is_latest_z_source(source_version: str) -> bool:
    """
    Check if source version indicates a latest-z upgrade (4.Y.0 format).

    This checks for explicit 4.Y.0 format - minor versions (4.Y) and
    bundle versions (4.Y.0.rhelR-BN) return False.

    Args:
        source_version: Version string to check

    Returns:
        True if version is 4.Y.0 format (latest-z source)
    """
    version_format = detect_version_format(source_version)

    if version_format == VersionFormat.FULL:
        # Check if patch is 0
        parts = source_version.split(".")
        return int(parts[2]) == 0

    return False


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
        ValueError: If the upgrade is unsupported (same version, downgrade, etc.)
    """
    source_minor = parse_minor_version(source_version)
    target_minor = parse_minor_version(target_version)
    source_patch = parse_patch_version(source_version)
    target_patch = parse_patch_version(target_version)

    # Edge case: Exact same version (must fail before any other checks)
    if source_patch is not None and target_patch is not None:
        if source_minor == target_minor and source_patch == target_patch:
            raise ValueError(
                f"Invalid upgrade: source and target are the same version. "
                f"source={source_version}, target={target_version}"
            )

    # Check for latest-z (source is 4.Y.0)
    if is_latest_z_source(source_version):
        if source_minor != target_minor:
            raise ValueError(
                f"Unsupported upgrade: latest-z upgrade requires same minor version. "
                f"source={source_version}, target={target_version}"
            )
        return UpgradeType.LATEST_Z

    version_diff = target_minor - source_minor

    if version_diff == 0:
        # Z-stream downgrade check (e.g., 4.20.5 -> 4.20.4)
        if source_patch is not None and target_patch is not None:
            if source_patch > target_patch:
                raise ValueError(
                    f"Invalid upgrade: cannot downgrade within z-stream. "
                    f"source={source_version}, target={target_version}"
                )
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
    elif version_diff < 0:
        raise ValueError(f"Invalid upgrade: cannot downgrade. source={source_version}, target={target_version}")

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
