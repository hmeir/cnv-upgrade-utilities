"""Independent upgrade lane computation for test verification.

This module provides the test's OWN implementation of upgrade lane rules,
separate from the production code. If the production code has a bug that
this implementation doesn't, the test catches it.
"""


def compute_expected_lanes(version_str: str, z: int, supported_versions: list[str]) -> set[str]:
    """Compute expected upgrade lanes for a version at a given z-stream.

    Args:
        version_str: Minor version string (e.g., "4.20")
        z: Z-stream value (0, 1, 2, ...)
        supported_versions: List of supported version strings

    Returns:
        Set of expected lane display names (e.g., {"Y stream", "Z stream", "latest z"})
    """
    major = int(version_str.split(".")[0])
    minor = int(version_str.split(".")[1])
    supported = set(supported_versions)
    lanes: set[str] = set()

    if z >= 1:
        lanes.add("Z stream")
    if z >= 2:
        lanes.add("latest z")

    previous_version = f"{major}.{minor - 1}"
    if previous_version in supported:
        lanes.add("Y stream")

    if minor % 2 == 0:
        eus_source_version = f"{major}.{minor - 2}"
        if eus_source_version in supported and (minor - 2) % 2 == 0:
            if z == 0 or z >= 2:
                lanes.add("EUS")

    return lanes
