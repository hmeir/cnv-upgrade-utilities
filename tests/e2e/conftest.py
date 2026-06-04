import pytest
from packaging.version import Version

from cnv_upgrade_utilities.upgrade_types import EOL_VERSIONS, SUPPORTED_VERSIONS
from utils.version_explorer import CnvVersionExplorer

_SUPPORTED_SET = frozenset(SUPPORTED_VERSIONS)


def generate_minor_paths() -> list[tuple[str, str, str]]:
    """Generate all valid (source, target, expected_type) tuples from SUPPORTED_VERSIONS."""
    paths = []

    for version in SUPPORTED_VERSIONS:
        paths.append((version, version, "z_stream"))

    for target_version_str in SUPPORTED_VERSIONS:
        target = Version(target_version_str)
        source_version_str = f"{target.major}.{target.minor - 1}"
        if source_version_str in _SUPPORTED_SET:
            paths.append((source_version_str, target_version_str, "y_stream"))

    for target_version_str in SUPPORTED_VERSIONS:
        target = Version(target_version_str)
        if target.minor % 2 != 0:
            continue
        eus_source_minor = target.minor - 2
        if eus_source_minor < 0:
            continue
        eus_source_version = f"{target.major}.{eus_source_minor}"
        if eus_source_version in _SUPPORTED_SET and eus_source_minor % 2 == 0:
            paths.append((eus_source_version, target_version_str, "eus"))

    for version in SUPPORTED_VERSIONS:
        paths.append((f"{version}.0", version, "latest_z"))

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
    pytest.param("4.19.0", "4.20", id="latest-z-cross-minor"),
    *_generate_eol_negative_paths(),
]


@pytest.fixture(scope="session")
def explorer():
    """Real CnvVersionExplorer session for E2E tests. Uses default URL if not overridden."""
    with CnvVersionExplorer() as exp:
        yield exp
