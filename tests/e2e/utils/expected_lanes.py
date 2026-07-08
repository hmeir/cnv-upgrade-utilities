"""Independent upgrade lane computation for test verification.

This module provides the test's OWN implementation of upgrade lane rules,
separate from the production code. If the production code has a bug that
this implementation doesn't, the test catches it.
"""

_TEST_CROSS_MAJOR_Y_SOURCES: dict[str, list[str]] = {
    "5.0": ["4.22"],
}
_TEST_BLOCKED_Y_TARGETS: frozenset[str] = frozenset()
_TEST_NON_EUS: frozenset[str] = frozenset({"5.0"})


def compute_expected_lanes(version_str: str, z: int, supported_versions: list[str]) -> set[str]:
    """Compute expected upgrade lanes for a version at a given z-stream.

    Args:
        version_str: Minor version string (e.g., "4.20", "5.0")
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

    cross_major_sources = _TEST_CROSS_MAJOR_Y_SOURCES.get(version_str, [])
    if cross_major_sources:
        for src in cross_major_sources:
            if src in supported:
                lanes.add(f"Y stream ({src})")
    elif version_str not in _TEST_BLOCKED_Y_TARGETS:
        previous_version = f"{major}.{minor - 1}"
        if previous_version in supported:
            lanes.add("Y stream")

    if version_str not in _TEST_NON_EUS and minor % 2 == 0:
        eus_source_version = f"{major}.{minor - 2}"
        if eus_source_version in supported and (minor - 2) % 2 == 0:
            if z == 0 or z >= 2:
                lanes.add("EUS")

    return lanes
