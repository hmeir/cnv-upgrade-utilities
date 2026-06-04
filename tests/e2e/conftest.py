import pytest
from packaging.version import Version

from cnv_upgrade_utilities.upgrade_types import EOL_VERSIONS, SUPPORTED_VERSIONS
from cnv_upgrade_utilities.version_types import format_minor_version
from utils.version_explorer import CnvVersionExplorer

from .utils.expected_lanes import compute_expected_lanes

_SUPPORTED_SET = frozenset(SUPPORTED_VERSIONS)


def _probe_version_z_depth() -> dict[str, int]:
    """Probe Version Explorer at collection time to find max released z per version."""
    depth = {}
    with CnvVersionExplorer() as explorer:
        for version in SUPPORTED_VERSIONS:
            minor_version = format_minor_version(version)
            builds = explorer.get_released_builds(minor_version=minor_version, stage=True)
            max_z = -1
            for build in builds:
                csv = build.csv_version.lstrip("v")
                parts = csv.split(".")
                if len(parts) >= 3:
                    max_z = max(max_z, int(parts[2]))
            depth[version] = max_z
    return depth


VERSION_Z_DEPTH = _probe_version_z_depth()


def generate_minor_paths() -> list[tuple[str, str, str]]:
    """Generate valid (source, target, expected_type) tuples based on actual API data."""
    paths = []

    for version in SUPPORTED_VERSIONS:
        max_z = VERSION_Z_DEPTH.get(version, -1)
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


def _generate_eol_negative_paths() -> list:
    """Auto-generate negative tests for every EOL version."""
    paths = []
    for eol_version in sorted(EOL_VERSIONS):
        paths.append(pytest.param(eol_version, eol_version, id=f"eol-z-stream-{eol_version}"))
        for supported_version in SUPPORTED_VERSIONS:
            if Version(supported_version) > Version(eol_version):
                paths.append(
                    pytest.param(eol_version, supported_version, id=f"eol-source-{eol_version}->{supported_version}")
                )
                break
        for supported_version in reversed(SUPPORTED_VERSIONS):
            if Version(supported_version) < Version(eol_version):
                paths.append(
                    pytest.param(supported_version, eol_version, id=f"eol-target-{supported_version}->{eol_version}")
                )
                break
    return paths


NEGATIVE_PATHS = [
    pytest.param("4.16.0", "4.16.99", id="non-existent-target-version"),
    pytest.param("4.99", "4.99", id="non-existent-minor"),
    pytest.param("4.20", "4.19", id="downgrade-minor"),
    pytest.param("4.20.5", "4.20.4", id="downgrade-z-stream"),
    pytest.param("4.16", "4.19", id="unsupported-gap"),
    pytest.param("4.17", "4.19", id="odd-eus"),
    pytest.param("4.20.5", "4.20.5", id="same-version"),
    *_generate_eol_negative_paths(),
]


@pytest.fixture(scope="session")
def explorer():
    """Real CnvVersionExplorer session for E2E tests. Uses default URL if not overridden."""
    with CnvVersionExplorer() as exp:
        yield exp
