"""Common types and utilities shared across CNV upgrade utilities."""

import click

from utils.constants import (
    FULL_VERSION_PATTERN,
    MINOR_VERSION_PATTERN,
    SOURCE_VERSION_PATTERN,
    UpgradeType,
)


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
