"""FBC channel consistency tests: compare Version Explorer data against cnv-fbc repo."""

import pytest

from cnv_upgrade_utilities.upgrade_types import SUPPORTED_VERSIONS
from cnv_upgrade_utilities.version_types import parse_minor_version

from ..utils.fbc_parser import get_fbc_entry_by_version, get_fbc_versions_in_channel, parse_fbc_graph

yaml = pytest.importorskip("yaml", reason="pyyaml required for FBC tests")

pytestmark = [pytest.mark.fbc, pytest.mark.e2e]


class TestFbcChannelConsistency:
    """Verify that Version Explorer build data matches FBC graph.yaml."""

    @pytest.mark.parametrize("minor", [parse_minor_version(v) for v in SUPPORTED_VERSIONS], ids=SUPPORTED_VERSIONS)
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

    @pytest.mark.parametrize("minor", [parse_minor_version(v) for v in SUPPORTED_VERSIONS], ids=SUPPORTED_VERSIONS)
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
                    f"Build {csv_version}: Version Explorer replaces={ve_replaces} but FBC says replaces={fbc_replaces}"
                )

    @pytest.mark.parametrize("minor", [parse_minor_version(v) for v in SUPPORTED_VERSIONS], ids=SUPPORTED_VERSIONS)
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
