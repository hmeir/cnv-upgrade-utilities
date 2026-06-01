"""FBC ground truth verification: compare Version Explorer data against cnv-fbc repo."""

import os
import subprocess
import tempfile

import pytest

from utils.version_explorer import CnvVersionExplorer

from .conftest import SUPPORTED_MINORS
from .fbc_parser import get_fbc_entry_by_version, get_fbc_versions_in_channel, parse_fbc_graph

FBC_REPO_URL = "https://github.com/openshift-cnv/cnv-fbc.git"
FBC_BRANCH = "stage"


@pytest.fixture(scope="session")
def fbc_repo_path():
    """Clone or use local cnv-fbc repo."""
    local_path = os.environ.get("CNV_FBC_REPO_PATH")
    if local_path:
        yield local_path
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", FBC_BRANCH, FBC_REPO_URL, tmpdir],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            pytest.skip(f"Failed to clone cnv-fbc: {result.stderr}")
        yield tmpdir


@pytest.fixture(scope="session")
def fbc_explorer():
    """Real CnvVersionExplorer for FBC comparison tests."""
    url = os.environ.get("VERSION_EXPLORER_URL")
    if not url:
        pytest.skip("VERSION_EXPLORER_URL not set")
    with CnvVersionExplorer(url=url) as exp:
        yield exp


@pytest.mark.fbc
class TestFbcChannelConsistency:
    """Verify that Version Explorer build data matches FBC graph.yaml."""

    @pytest.mark.parametrize("minor", SUPPORTED_MINORS)
    def test_released_builds_exist_in_fbc(self, fbc_explorer, fbc_repo_path, minor):
        """Each build returned by Version Explorer should have a corresponding FBC entry."""
        fbc_channels = parse_fbc_graph(fbc_repo_path, minor)
        if not fbc_channels:
            pytest.skip(f"No FBC graph.yaml found for v4.{minor}")

        builds = fbc_explorer.get_released_builds(minor_version=f"v4.{minor}", stage=True)
        if not builds:
            pytest.skip(f"No released builds found for v4.{minor}")

        for build in builds:
            csv_version = build.csv_version.lstrip("v")
            channel = build.current_channel
            if not channel or channel not in fbc_channels:
                continue

            fbc_versions = get_fbc_versions_in_channel(fbc_repo_path, minor, channel)
            assert csv_version in fbc_versions, (
                f"Build {csv_version} (channel={channel}) returned by Version Explorer "
                f"but not found in FBC graph.yaml for v4.{minor}/{channel}"
            )

    @pytest.mark.parametrize("minor", SUPPORTED_MINORS)
    def test_replaces_field_matches_fbc(self, fbc_explorer, fbc_repo_path, minor):
        """The 'replaces' field in Version Explorer should match FBC graph.yaml."""
        fbc_channels = parse_fbc_graph(fbc_repo_path, minor)
        if not fbc_channels:
            pytest.skip(f"No FBC graph.yaml found for v4.{minor}")

        builds = fbc_explorer.get_released_builds(minor_version=f"v4.{minor}", stage=True)
        if not builds:
            pytest.skip(f"No released builds found for v4.{minor}")

        for build in builds:
            csv_version = build.csv_version.lstrip("v")
            channel = build.current_channel
            if not channel or channel not in fbc_channels:
                continue

            fbc_entry = get_fbc_entry_by_version(fbc_repo_path, minor, channel, csv_version)
            if not fbc_entry:
                continue

            ve_replaces = build.replaces.lstrip("v") if build.replaces else None
            fbc_replaces = fbc_entry["replaces_version"]

            if fbc_replaces and ve_replaces:
                assert ve_replaces == fbc_replaces, (
                    f"Build {csv_version}: Version Explorer replaces={ve_replaces} "
                    f"but FBC says replaces={fbc_replaces}"
                )

    @pytest.mark.parametrize("minor", SUPPORTED_MINORS)
    def test_skip_range_matches_fbc(self, fbc_explorer, fbc_repo_path, minor):
        """The 'skipRange' field should match between Version Explorer and FBC."""
        fbc_channels = parse_fbc_graph(fbc_repo_path, minor)
        if not fbc_channels:
            pytest.skip(f"No FBC graph.yaml found for v4.{minor}")

        builds = fbc_explorer.get_released_builds(minor_version=f"v4.{minor}", stage=True)
        if not builds:
            pytest.skip(f"No released builds found for v4.{minor}")

        for build in builds:
            csv_version = build.csv_version.lstrip("v")
            channel = build.current_channel
            if not channel or channel not in fbc_channels:
                continue

            fbc_entry = get_fbc_entry_by_version(fbc_repo_path, minor, channel, csv_version)
            if not fbc_entry or not fbc_entry["skip_range"]:
                continue

            ve_skip_range = build.skip_range or ""
            fbc_skip_range = fbc_entry["skip_range"]

            if fbc_skip_range:
                assert ve_skip_range == fbc_skip_range, (
                    f"Build {csv_version}: Version Explorer skipRange='{ve_skip_range}' "
                    f"but FBC says skipRange='{fbc_skip_range}'"
                )


@pytest.mark.fbc
class TestFbcStaleStageDetection:
    """Detect stale in_stage flags by comparing against FBC version ordering."""

    @pytest.mark.parametrize("minor", SUPPORTED_MINORS)
    def test_no_stale_in_stage_in_stable_channel(self, fbc_explorer, fbc_repo_path, minor):
        """
        If a build is in_stage=True for stable channel, no newer z-stream
        in the same stable channel should already be released_to_prod=True.
        """
        fbc_stable_versions = get_fbc_versions_in_channel(fbc_repo_path, minor, "stable")
        if not fbc_stable_versions:
            pytest.skip(f"No stable channel in FBC for v4.{minor}")

        builds = fbc_explorer.get_released_builds(minor_version=f"v4.{minor}", stage=True)
        if not builds:
            pytest.skip(f"No released builds found for v4.{minor}")

        stage_builds = []
        prod_versions = set()

        for build in builds:
            csv_version = build.csv_version.lstrip("v")
            for ch in build.channels:
                if ch.channel != "stable":
                    continue
                if ch.in_stage and not ch.released_to_prod:
                    stage_builds.append(csv_version)
                if ch.released_to_prod:
                    prod_versions.add(csv_version)

        for stage_version in stage_builds:
            stage_parts = stage_version.split(".")
            stage_z = int(stage_parts[2]) if len(stage_parts) >= 3 else 0

            for prod_version in prod_versions:
                prod_parts = prod_version.split(".")
                prod_z = int(prod_parts[2]) if len(prod_parts) >= 3 else 0

                if prod_z > stage_z:
                    pytest.fail(
                        f"v4.{minor}: Stale in_stage detected — {stage_version} is marked "
                        f"in_stage=True but {prod_version} (z={prod_z}) is already released to prod. "
                        f"This is a Version Explorer data quality issue."
                    )
