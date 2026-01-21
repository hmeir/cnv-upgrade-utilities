"""Common types and utilities shared across CNV upgrade utilities."""

import click

from utils.constants import (
    FULL_VERSION_PATTERN,
    MINOR_VERSION_PATTERN,
    SKIP_Y_STREAM_UPGRADE_MINORS,
    SOURCE_VERSION_PATTERN,
    SUPPORTED_MINORS,
    VALID_CHANNELS,
    UpgradeType,
)

# Re-export constants for backward compatibility
__all__ = [
    "FULL_VERSION_PATTERN",
    "MINOR_VERSION_PATTERN",
    "SOURCE_VERSION_PATTERN",
    "VALID_CHANNELS",
    "SUPPORTED_MINORS",
    "SKIP_Y_STREAM_UPGRADE_MINORS",
    "UpgradeType",
    "FullVersionParamType",
    "MinorVersionParamType",
    "SourceVersionParamType",
    "FULL_VERSION_TYPE",
    "MINOR_VERSION_TYPE",
    "SOURCE_VERSION_TYPE",
    "parse_minor_version",
    "is_eus_version",
    "is_latest_z_source",
    "format_minor_version",
]


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


# Helper functions
def parse_minor_version(version: str) -> int:
    """Extract the minor version number from a 4.Y or 4.Y.z string."""
    return int(version.split(".")[1])


def is_eus_version(minor: int) -> bool:
    """Check if a minor version is EUS-eligible (even number)."""
    return minor % 2 == 0


def is_latest_z_source(source_version: str) -> bool:
    """Check if source version is in 4.Y.0 format (latest-z upgrade)."""
    return source_version.endswith(".0")


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
