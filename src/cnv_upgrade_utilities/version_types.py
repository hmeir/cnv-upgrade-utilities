"""Version format types, patterns, parsing, and Click parameter types."""

import re
from enum import Enum

import click

# ============================================================================
# Version Regex Patterns
# ============================================================================
FULL_VERSION_PATTERN = re.compile(r"^[45]\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
MINOR_VERSION_PATTERN = re.compile(r"^[45]\.(0|[1-9]\d*)$")
BUNDLE_VERSION_PATTERN = re.compile(r"^[45]\.(0|[1-9]\d*)\.(0|[1-9]\d*)\.rhel\d+-\d+$")

FLEXIBLE_VERSION_PATTERN = re.compile(r"^[45]\.(0|[1-9]\d*)" r"(?:\.(0|[1-9]\d*)" r"(?:\.rhel\d+-\d+)?)?$")


# ============================================================================
# Version Format Enumeration
# ============================================================================
class VersionFormat(Enum):
    """
    Enum representing different version format types.

    - MINOR: X.Y (e.g., 4.20)
    - FULL: X.Y.Z (e.g., 4.20.3)
    - BUNDLE: X.Y.Z.rhelR-BN (e.g., 4.20.3.rhel9-18)
    """

    MINOR = "minor"
    FULL = "full"
    BUNDLE = "bundle"


def detect_version_format(version: str) -> VersionFormat:
    """Detect the format of a version string."""
    if BUNDLE_VERSION_PATTERN.match(version):
        return VersionFormat.BUNDLE
    elif FULL_VERSION_PATTERN.match(version):
        return VersionFormat.FULL
    elif MINOR_VERSION_PATTERN.match(version):
        return VersionFormat.MINOR
    else:
        raise ValueError(f"Unrecognized version format: {version}")


# ============================================================================
# Click Parameter Types
# ============================================================================
class VersionParamType(click.ParamType):
    """Generic Click parameter type for version validation against a regex pattern."""

    def __init__(self, pattern: re.Pattern, name: str, example: str):
        self.pattern = pattern
        self.name = name
        self.example = example

    def convert(self, value: str, param: click.Parameter | None, ctx: click.Context | None) -> str:
        if not self.pattern.match(value):
            self.fail(
                f"Invalid version format: '{value}'. Expected format: {self.example}",
                param,
                ctx,
            )
        return value


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
    """
    version_format = detect_version_format(version)
    if version_format == VersionFormat.BUNDLE:
        parts = version.rsplit(".rhel", 1)[0].split(".")
        return int(parts[2]) if len(parts) >= 3 else None
    elif version_format == VersionFormat.FULL:
        parts = version.split(".")
        return int(parts[2])
    return None


def is_latest_z_source(source_version: str) -> bool:
    """Check if source version indicates a latest-z upgrade (explicit 4.Y.0 format)."""
    version_format = detect_version_format(source_version)
    if version_format == VersionFormat.FULL:
        parts = source_version.split(".")
        return int(parts[2]) == 0
    return False


def format_minor_version(version: str, prefix: str = "v") -> str:
    """Format a version string to minor version format (e.g., 'v4.20')."""
    parts = version.split(".")
    return f"{prefix}{parts[0]}.{parts[1]}"
