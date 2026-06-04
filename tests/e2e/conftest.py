import os

import pytest
from packaging.version import Version

from cnv_upgrade_utilities.upgrade_types import SUPPORTED_VERSIONS
from utils.version_explorer import CnvVersionExplorer

_SUPPORTED_SET = frozenset(SUPPORTED_VERSIONS)


def generate_minor_paths() -> list[tuple[str, str, str]]:
    """Generate all valid (source, target, expected_type) tuples from SUPPORTED_VERSIONS."""
    paths = []

    for v_str in SUPPORTED_VERSIONS:
        paths.append((v_str, v_str, "z_stream"))

    for v_str in SUPPORTED_VERSIONS:
        v = Version(v_str)
        source_str = f"{v.major}.{v.minor - 1}"
        if source_str in _SUPPORTED_SET:
            paths.append((source_str, v_str, "y_stream"))

    for v_str in SUPPORTED_VERSIONS:
        v = Version(v_str)
        if v.minor % 2 != 0:
            continue
        source_minor = v.minor - 2
        if source_minor < 0:
            continue
        source_str = f"{v.major}.{source_minor}"
        if source_str in _SUPPORTED_SET and source_minor % 2 == 0:
            paths.append((source_str, v_str, "eus"))

    for v_str in SUPPORTED_VERSIONS:
        paths.append((f"{v_str}.0", v_str, "latest_z"))

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
    pytest.param("4.15", "4.16", id="eol-source"),
    pytest.param("4.12", "4.13", id="eol-target"),
    pytest.param("4.13", "4.13", id="eol-both"),
]


@pytest.fixture(scope="session")
def explorer():
    """Real CnvVersionExplorer session for E2E tests."""
    url = os.environ.get("VERSION_EXPLORER_URL")
    if not url:
        pytest.skip("VERSION_EXPLORER_URL not set")
    with CnvVersionExplorer(url=url) as exp:
        yield exp
