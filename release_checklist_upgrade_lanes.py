import argparse
import re
import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from packaging.version import Version
from upgrade_utils.version_explorer_utils import get_latest_stable_released_z_stream_info, get_version_explorer_url

LOGGER = logging.getLogger(__name__)

VERSION_PATTERN = re.compile(r"^4\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
VALID_CHANNELS = ("stable", "candidate")
SKIP_Y_STREAM_UPGRADE_MINORS = {12, 14}


def validate_version(version: str) -> str:
    """Validate that version matches the 4.Y.z format."""
    if not VERSION_PATTERN.match(version):
        raise argparse.ArgumentTypeError(
            f"Invalid version format: '{version}'. Expected format: 4.Y.z (e.g., 4.20.2)"
        )
    return version


def parse_args() -> argparse.Namespace:
    """Parse and validate command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Upgrade release checklist tool"
    )
    parser.add_argument(
        "-v", "--target-version",
        type=validate_version,
        required=True,
        help="Target version in format 4.Y.z (e.g., 4.20.2)"
    )
    parser.add_argument(
        "-c", "--channel",
        choices=VALID_CHANNELS,
        default="stable",
        help="Release channel: stable or candidate (default: stable)"
    )
    return parser.parse_args()


class UpgradeType(Enum):
    """Upgrade type enumeration with associated minor version offset."""
    Y_STREAM = ("Y stream", -1)
    Z_STREAM = ("Z stream", 0)
    EUS = ("EUS", -2)
    LATEST_Z = ("latest z", None)
    
    def __init__(self, display_name: str, minor_offset: Optional[int]):
        self.display_name = display_name
        self.minor_offset = minor_offset


@dataclass
class UpgradeConfig:
    upgrade_type: UpgradeType
    post_upgrade_suite: str


@dataclass
class VersionCategory:
    version_pattern: str
    upgrade_configs: list[UpgradeConfig]


# Data-driven configuration mapping z-stream values to upgrade configurations
VERSION_CATEGORIES = {
    0: VersionCategory(
        version_pattern="4.Y.0",
        upgrade_configs=[
            UpgradeConfig(UpgradeType.Y_STREAM, post_upgrade_suite="FULL"),
        ]
    ),
    1: VersionCategory(
        version_pattern="4.Y.1",
        upgrade_configs=[
            UpgradeConfig(UpgradeType.Y_STREAM, post_upgrade_suite="FULL"),
            UpgradeConfig(UpgradeType.Z_STREAM, post_upgrade_suite="PUM"),
        ]
    ),
}

# Default category for z >= 2
DEFAULT_CATEGORY = VersionCategory(
    version_pattern="4.Y.2+",
    upgrade_configs=[
        UpgradeConfig(UpgradeType.Y_STREAM, post_upgrade_suite="PUM"),
        UpgradeConfig(UpgradeType.Z_STREAM, post_upgrade_suite="NONE"),
        UpgradeConfig(UpgradeType.LATEST_Z, post_upgrade_suite="NONE"),
    ]
)


def create_upgrade_entry(config: UpgradeConfig, source_version: Optional[str] = None) -> dict:
    """Create upgrade type dictionary entry."""
    return {
        "type": config.upgrade_type.display_name,
        "source_version": source_version,
        "post_upgrade_suite": config.post_upgrade_suite,
    }


def fetch_source_version(target_version: Version, minor_offset: int) -> Optional[str]:
    """
    Fetch latest stable source version for given minor offset.
    
    Args:
        target_version: Target version to upgrade to
        minor_offset: Offset to apply when fetching source version
        
    Returns:
        Source version string if found, None otherwise
    """
    if minor_offset is None:
        return f"v{target_version.major}.{target_version.minor}.0"
    minor = f"v{target_version.major}.{target_version.minor + minor_offset}"
    source_info = get_latest_stable_released_z_stream_info(minor_version=minor)
    return source_info.get("version") if source_info else None


def categorize_version(target_version: Version) -> dict:
    """
    Categorize version and return upgrade type info.
    
    Uses data-driven configuration to determine upgrade types based on
    the z-stream value and whether the version is EUS-eligible.
    
    Args:
        target_version: Version object to categorize
        
    Returns:
        Dictionary containing target version, version type, and upgrade configurations
    """
    z, y = target_version.micro, target_version.minor
    
    # Get category configuration
    upgrade_configs = list(VERSION_CATEGORIES.get(z, DEFAULT_CATEGORY).upgrade_configs)

    # Filter out Y_STREAM for specific versions (e.g., 4.12, 4.14)
    if y in SKIP_Y_STREAM_UPGRADE_MINORS:
        upgrade_configs = [
            config for config in upgrade_configs 
            if config.upgrade_type != UpgradeType.Y_STREAM
        ]
    
    # Add EUS upgrade for even minor versions at z=0
    if z == 0 and y % 2 == 0:
        upgrade_configs.append(
            UpgradeConfig(UpgradeType.EUS, post_upgrade_suite="PUM")
        )
    
    # Build upgrade entries with source versions
    upgrade_lanes = [
        create_upgrade_entry(config, fetch_source_version(target_version, config.upgrade_type.minor_offset))
        for config in upgrade_configs
    ]
    return {
        "target_version": target_version,
        "upgrade_lanes": upgrade_lanes,
    }


def main():
    get_version_explorer_url()
    args = parse_args()
    
    version_info = categorize_version(Version(args.target_version))
    
    print(json.dumps(version_info, indent=2, default=str))

if __name__ == "__main__":
    main()
