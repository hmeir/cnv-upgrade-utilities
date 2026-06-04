"""Upgrade type definitions and determination logic."""

from enum import Enum

from packaging.version import Version

from cnv_upgrade_utilities.version_types import (
    is_latest_z_source,
    parse_minor_version,
    parse_patch_version,
)

SUPPORTED_VERSIONS = [
    "4.12",
    "4.14",
    "4.16",
    "4.17",
    "4.18",
    "4.19",
    "4.20",
    "4.21",
    "4.22",
]

EOL_VERSIONS = frozenset({"4.13", "4.15"})

_SUPPORTED_VERSION_SET = frozenset(SUPPORTED_VERSIONS)


def _compute_skip_y_stream_minors() -> frozenset[int]:
    """Minors where Y-stream upgrade is not applicable (Y-1 is EOL or unsupported)."""
    supported_set = {Version(v) for v in SUPPORTED_VERSIONS}
    eol_set = {Version(v) for v in EOL_VERSIONS}
    skip = set()
    for v_str in SUPPORTED_VERSIONS:
        v = Version(v_str)
        source = Version(f"{v.major}.{v.minor - 1}")
        if source in eol_set or source not in supported_set:
            skip.add(v.minor)
    return frozenset(skip)


SKIP_Y_STREAM_UPGRADE_MINORS = _compute_skip_y_stream_minors()


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
        """Check if this upgrade type applies for a given z-stream and minor version."""
        match self:
            case UpgradeType.Z_STREAM:
                return z >= 1
            case UpgradeType.LATEST_Z:
                return z >= 2
            case UpgradeType.Y_STREAM:
                return minor not in SKIP_Y_STREAM_UPGRADE_MINORS
            case UpgradeType.EUS:
                if z != 0 or minor % 2 != 0:
                    return False
                return f"4.{minor - 2}" in _SUPPORTED_VERSION_SET
            case _:
                return False


def is_eus_version(minor: int) -> bool:
    """Check if a minor version is EUS-eligible (even number)."""
    return minor % 2 == 0


def determine_upgrade_type(source_version: str, target_version: str) -> UpgradeType:
    """
    Determine the upgrade type based on source and target versions.

    Supported upgrade types:
    - 4.Y.0 -> 4.Y: latest-z (source must target the same Y)
    - 4.Y -> 4.Y: z-stream
    - 4.Y -> 4.Y+1: y-stream
    - 4.Y -> 4.Y+2: EUS (both Y versions must be even)

    Raises:
        ValueError: If the upgrade is unsupported (same version, downgrade, etc.)
    """
    source_minor = parse_minor_version(source_version)
    target_minor = parse_minor_version(target_version)
    source_patch = parse_patch_version(source_version)
    target_patch = parse_patch_version(target_version)

    if source_patch is not None and target_patch is not None:
        if source_minor == target_minor and source_patch == target_patch:
            raise ValueError(
                f"Invalid upgrade: source and target are the same version. "
                f"source={source_version}, target={target_version}"
            )

    if is_latest_z_source(source_version):
        if source_minor != target_minor:
            raise ValueError(
                f"Unsupported upgrade: latest-z upgrade requires same minor version. "
                f"source={source_version}, target={target_version}"
            )
        return UpgradeType.LATEST_Z

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
    """Get all applicable upgrade types for a target version."""
    return [upgrade_type for upgrade_type in UpgradeType if upgrade_type.is_applicable_for_z(target_z, target_minor)]
