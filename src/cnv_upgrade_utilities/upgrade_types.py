"""Upgrade type definitions and determination logic."""

from enum import Enum

from packaging.version import Version

from cnv_upgrade_utilities.version_types import (
    format_minor_version,
    is_latest_z_source,
    parse_major_version,
    parse_minor_version,
    parse_patch_version,
)

SUPPORTED_VERSIONS = [
    "4.12",
    "4.14",
    "4.16",
    "4.18",
    "4.19",
    "4.20",
    "4.21",
    "4.22",
    "4.23",
    "5.0",
]

EOL_VERSIONS = frozenset({"4.13", "4.15", "4.17"})

_SUPPORTED_VERSION_SET = frozenset(SUPPORTED_VERSIONS)

CROSS_MAJOR_Y_STREAM_SOURCES: dict[str, list[str]] = {
    "5.0": ["4.22"],
}

_BLOCKED_Y_STREAM_TARGETS: frozenset[str] = frozenset()

_NON_EUS_VERSIONS: frozenset[str] = frozenset({"5.0"})


def _compute_skip_y_stream_versions() -> frozenset[str]:
    """Versions where same-major Y-stream upgrade is not applicable."""
    supported_set = {Version(v) for v in SUPPORTED_VERSIONS}
    eol_set = {Version(v) for v in EOL_VERSIONS}
    skip: set[str] = set()
    for v_str in SUPPORTED_VERSIONS:
        if v_str in CROSS_MAJOR_Y_STREAM_SOURCES:
            continue
        if v_str in _BLOCKED_Y_STREAM_TARGETS:
            skip.add(v_str)
            continue
        v = Version(v_str)
        if v.minor == 0:
            skip.add(v_str)
            continue
        source = Version(f"{v.major}.{v.minor - 1}")
        if source in eol_set or source not in supported_set:
            skip.add(v_str)
    return frozenset(skip)


SKIP_Y_STREAM_VERSIONS = _compute_skip_y_stream_versions()


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

    def is_applicable_for_z(self, z: int, minor: int, major: int = 4) -> bool:
        """Check if this upgrade type applies for a given z-stream, minor, and major version."""
        version_str = f"{major}.{minor}"
        match self:
            case UpgradeType.Z_STREAM:
                return z >= 1
            case UpgradeType.LATEST_Z:
                return z >= 2
            case UpgradeType.Y_STREAM:
                if version_str in CROSS_MAJOR_Y_STREAM_SOURCES:
                    return True
                return version_str not in SKIP_Y_STREAM_VERSIONS
            case UpgradeType.EUS:
                if version_str in _NON_EUS_VERSIONS:
                    return False
                if minor % 2 != 0:
                    return False
                if f"{major}.{minor - 2}" not in _SUPPORTED_VERSION_SET:
                    return False
                if z == 0:
                    return True
                return z >= 2
            case _:
                return False


def is_eol_version(version: str) -> bool:
    """Check if a version (X.Y format) is EOL."""
    minor_version = format_minor_version(version, prefix="")
    return minor_version in EOL_VERSIONS


def is_eus_version(minor: int, major: int = 4) -> bool:
    """Check if a version is EUS-eligible (even minor, not in non-EUS set)."""
    if f"{major}.{minor}" in _NON_EUS_VERSIONS:
        return False
    return minor % 2 == 0


def determine_upgrade_type(source_version: str, target_version: str) -> UpgradeType:
    """
    Determine the upgrade type based on source and target versions.

    Supported upgrade types:
    - X.Y.0 -> X.Y: latest-z (source must target the same Y)
    - X.Y -> X.Y: z-stream
    - X.Y -> X.Y+1: y-stream
    - X.Y -> X.Y+2: EUS (both Y versions must be even)
    - Cross-major (e.g., 4.Y -> 5.0): y-stream

    Raises:
        ValueError: If the upgrade is unsupported (same version, downgrade, blocked path, etc.)
    """
    if is_eol_version(source_version):
        raise ValueError(f"Invalid upgrade: source version {source_version} is EOL")
    if is_eol_version(target_version):
        raise ValueError(f"Invalid upgrade: target version {target_version} is EOL")

    source_major = parse_major_version(source_version)
    target_major = parse_major_version(target_version)
    source_minor = parse_minor_version(source_version)
    target_minor = parse_minor_version(target_version)
    source_patch = parse_patch_version(source_version)
    target_patch = parse_patch_version(target_version)

    if source_major != target_major:
        if target_major > source_major:
            return UpgradeType.Y_STREAM
        raise ValueError(f"Invalid upgrade: cannot downgrade. source={source_version}, target={target_version}")

    if source_patch is not None and target_patch is not None:
        if source_minor == target_minor and source_patch == target_patch:
            raise ValueError(
                f"Invalid upgrade: source and target are the same version. "
                f"source={source_version}, target={target_version}"
            )

    if is_latest_z_source(source_version):
        if source_minor == target_minor:
            return UpgradeType.LATEST_Z
        # Source is X.Y.0 but target has different minor — not a latest-z upgrade.
        # Fall through to normal version_diff logic (could be Y-stream or EUS).

    version_diff = target_minor - source_minor

    if version_diff == 0:
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
        if is_eus_version(source_minor, source_major) and is_eus_version(target_minor, target_major):
            return UpgradeType.EUS
        raise ValueError(
            f"Unsupported upgrade: EUS upgrade requires both versions to be even. "
            f"source={source_version} (minor={source_minor}), target={target_version} (minor={target_minor})"
        )
    elif version_diff < 0:
        raise ValueError(f"Invalid upgrade: cannot downgrade. source={source_version}, target={target_version}")

    raise ValueError(f"Unsupported upgrade: source={source_version}, target={target_version}")


def get_applicable_upgrade_types(target_minor: int, target_z: int, target_major: int = 4) -> list[UpgradeType]:
    """Get all applicable upgrade types for a target version."""
    return [
        upgrade_type
        for upgrade_type in UpgradeType
        if upgrade_type.is_applicable_for_z(target_z, target_minor, target_major)
    ]
