import os

import pytest

from cnv_upgrade_utilities.upgrade_types import SKIP_Y_STREAM_UPGRADE_MINORS
from utils.version_explorer import CnvVersionExplorer

SUPPORTED_MINORS = [12, 14, 16, 17, 18, 19, 20, 21, 22]


def generate_minor_paths() -> list[tuple[str, str, str]]:
    """Generate all valid MINOR-format (source, target, expected_type) tuples."""
    paths = []

    for minor in SUPPORTED_MINORS:
        paths.append((f"4.{minor}", f"4.{minor}", "z_stream"))

    for i, minor in enumerate(SUPPORTED_MINORS[:-1]):
        next_minor = SUPPORTED_MINORS[i + 1]
        if minor not in SKIP_Y_STREAM_UPGRADE_MINORS:
            paths.append((f"4.{minor}", f"4.{next_minor}", "y_stream"))

    for i, minor in enumerate(SUPPORTED_MINORS):
        if minor % 2 != 0:
            continue
        for j in range(i + 1, len(SUPPORTED_MINORS)):
            target_minor = SUPPORTED_MINORS[j]
            if target_minor == minor + 2 and target_minor % 2 == 0:
                paths.append((f"4.{minor}", f"4.{target_minor}", "eus"))

    for minor in SUPPORTED_MINORS:
        paths.append((f"4.{minor}.0", f"4.{minor}", "latest_z"))

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
]


@pytest.fixture(scope="session")
def explorer():
    """Real CnvVersionExplorer session for E2E tests."""
    url = os.environ.get("VERSION_EXPLORER_URL")
    if not url:
        pytest.skip("VERSION_EXPLORER_URL not set")
    with CnvVersionExplorer(url=url) as exp:
        yield exp
