import pytest
from packaging.version import Version

from cnv_upgrade_utilities.upgrade_types import EOL_VERSIONS, SUPPORTED_VERSIONS
from cnv_upgrade_utilities.version_types import format_minor_version
from utils.version_explorer import CnvVersionExplorer

from .utils.expected_lanes import compute_expected_lanes

_SUPPORTED_SET = frozenset(SUPPORTED_VERSIONS)

_version_z_depth_cache: dict[str, int] | None = None


def _probe_version_z_depth() -> dict[str, int]:
    """Probe Version Explorer to find max z per version. Cached after first call."""
    global _version_z_depth_cache
    if _version_z_depth_cache is not None:
        return _version_z_depth_cache

    depth = {}
    try:
        with CnvVersionExplorer(request_timeout=5, retry_timeout=10) as explorer:
            for version in SUPPORTED_VERSIONS:
                minor_version = format_minor_version(version)
                try:
                    builds = explorer.get_released_builds(minor_version=minor_version, stage=True)
                except Exception:
                    depth[version] = -1
                    continue
                max_z = -1
                for build in builds:
                    csv = build.csv_version.lstrip("v")
                    parts = csv.split(".")
                    if len(parts) >= 3:
                        max_z = max(max_z, int(parts[2]))
                depth[version] = max_z
    except Exception:
        for version in SUPPORTED_VERSIONS:
            depth.setdefault(version, -1)

    _version_z_depth_cache = depth
    return depth


def get_version_z_depth() -> dict[str, int]:
    """Get cached version z-depth map. Probes API on first call."""
    return _probe_version_z_depth()


def _generate_minor_paths(version_z_depth: dict[str, int]) -> list[tuple[str, str, str]]:
    """Generate valid (source, target, expected_type) tuples based on actual API data."""
    paths = []

    for version in SUPPORTED_VERSIONS:
        max_z = version_z_depth.get(version, -1)
        if max_z < 0:
            continue

        expected = compute_expected_lanes(version, z=max_z, supported_versions=SUPPORTED_VERSIONS)

        if "Z stream" in expected:
            paths.append((version, version, "z_stream"))

        if "latest z" in expected:
            paths.append((f"{version}.0", version, "latest_z"))

        if "Y stream" in expected:
            target = Version(version)
            source_version = f"{target.major}.{target.minor - 1}"
            paths.append((source_version, version, "y_stream"))

        if "EUS" in expected:
            target = Version(version)
            eus_source = f"{target.major}.{target.minor - 2}"
            paths.append((eus_source, version, "eus"))

    return paths


def _generate_eol_negative_paths() -> list[tuple[str, str]]:
    """Auto-generate negative tests for every EOL version."""
    paths = []
    for eol_version in sorted(EOL_VERSIONS):
        paths.append((eol_version, eol_version))
        for supported_version in SUPPORTED_VERSIONS:
            if Version(supported_version) > Version(eol_version):
                paths.append((eol_version, supported_version))
                break
        for supported_version in reversed(SUPPORTED_VERSIONS):
            if Version(supported_version) < Version(eol_version):
                paths.append((supported_version, eol_version))
                break
    return paths


@pytest.fixture(scope="session")
def explorer():
    """Real CnvVersionExplorer session for E2E tests. Uses default URL if not overridden."""
    with CnvVersionExplorer() as exp:
        yield exp


@pytest.fixture(scope="session")
def version_z_depth():
    """Lazily probe Version Explorer for z-depth data. Only runs when e2e tests execute."""
    return get_version_z_depth()


@pytest.fixture(scope="session")
def minor_paths(version_z_depth: dict[str, int]) -> list[tuple[str, str, str]]:
    """All valid upgrade paths derived from live API data."""
    return _generate_minor_paths(version_z_depth)


@pytest.fixture(scope="session")
def same_minor_paths(minor_paths: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
    """Upgrade paths within the same minor version (z_stream, latest_z)."""
    return [p for p in minor_paths if p[2] in ("z_stream", "latest_z")]


@pytest.fixture(scope="session")
def negative_paths() -> list[tuple[str, str]]:
    """Invalid upgrade paths that should raise errors."""
    static = [
        ("4.16.0", "4.16.99"),
        ("4.99", "4.99"),
        ("4.20", "4.19"),
        ("4.20.5", "4.20.4"),
        ("4.16", "4.19"),
        ("4.17", "4.19"),
        ("4.20.5", "4.20.5"),
    ]
    return static + _generate_eol_negative_paths()


@pytest.fixture(scope="session")
def versions_with_z1(version_z_depth: dict[str, int]) -> list[str]:
    """Supported versions that have at least z=1 released."""
    return [v for v in SUPPORTED_VERSIONS if version_z_depth.get(v, -1) >= 1]
