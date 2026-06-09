import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest
from packaging.version import Version

from cnv_upgrade_utilities.upgrade_types import EOL_VERSIONS, SUPPORTED_VERSIONS
from cnv_upgrade_utilities.version_types import format_minor_version, normalize_csv_version, parse_patch_version
from utils.version_explorer import CnvVersionExplorer

from .utils.expected_lanes import compute_expected_lanes

LOGGER = logging.getLogger("cnv_e2e")

_SUPPORTED_SET = frozenset(SUPPORTED_VERSIONS)

_UPGRADE_PATHS_JSON = Path(__file__).resolve().parents[2] / "current_testing_paths" / "upgrade-paths.json"


def _probe_latest_z(explorer: CnvVersionExplorer) -> dict[str, int]:
    """Probe Version Explorer for the latest z-stream per supported version."""
    latest_z: dict[str, int] = {}
    total = len(SUPPORTED_VERSIONS)
    LOGGER.info("Probing Version Explorer for latest_z of %d supported versions...", total)
    for i, version in enumerate(SUPPORTED_VERSIONS, 1):
        minor_version = format_minor_version(version)
        try:
            builds = explorer.get_released_builds(minor_version=minor_version, stage=True)
        except Exception:
            latest_z[version] = -1
            LOGGER.info("[%d/%d] %s: probe failed", i, total, version)
            continue
        max_z = -1
        for build in builds:
            patch = parse_patch_version(normalize_csv_version(build.csv_version))
            if patch is not None:
                max_z = max(max_z, patch)
        latest_z[version] = max_z
        LOGGER.info("[%d/%d] %s: max_z=%d", i, total, version, max_z)
    return latest_z


def _update_json_if_changed(latest_z: dict[str, int]) -> None:
    """Update upgrade-paths.json only if latest_z values actually changed."""
    if _UPGRADE_PATHS_JSON.exists():
        data = json.loads(_UPGRADE_PATHS_JSON.read_text())
        if data.get("latest_z") == latest_z:
            LOGGER.info("latest_z unchanged, keeping existing %s", _UPGRADE_PATHS_JSON.name)
            return
    else:
        data = {"supported_versions": SUPPORTED_VERSIONS}

    data["latest_z"] = latest_z
    data["generated_at"] = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    _UPGRADE_PATHS_JSON.parent.mkdir(parents=True, exist_ok=True)
    _UPGRADE_PATHS_JSON.write_text(json.dumps(data, indent=2, default=str) + "\n")
    LOGGER.info("Updated %s with fresh latest_z", _UPGRADE_PATHS_JSON.name)


def _generate_minor_paths(version_latest_z: dict[str, int]) -> list[tuple[str, str, str]]:
    """Generate valid (source, target, expected_type) tuples based on actual API data."""
    paths = []

    for version in SUPPORTED_VERSIONS:
        max_z = version_latest_z.get(version, -1)
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

    LOGGER.info("Generated %d upgrade paths from API data", len(paths))
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
def version_latest_z(explorer):
    """Probe Version Explorer for fresh latest_z, update JSON if changed."""
    latest_z = _probe_latest_z(explorer)
    _update_json_if_changed(latest_z)
    return latest_z


@pytest.fixture(scope="session")
def minor_paths(version_latest_z: dict[str, int]) -> list[tuple[str, str, str]]:
    """All valid upgrade paths derived from live API data."""
    return _generate_minor_paths(version_latest_z)


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
    eol_paths = _generate_eol_negative_paths()
    LOGGER.info(
        "Generated %d negative paths (%d static + %d EOL)", len(static) + len(eol_paths), len(static), len(eol_paths)
    )
    return static + eol_paths


@pytest.fixture(scope="session")
def versions_with_z1(version_latest_z: dict[str, int]) -> list[str]:
    """Supported versions that have at least z=1 released."""
    return [v for v in SUPPORTED_VERSIONS if version_latest_z.get(v, -1) >= 1]
