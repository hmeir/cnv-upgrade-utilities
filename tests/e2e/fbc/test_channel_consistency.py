"""FBC channel consistency tests: compare Version Explorer data against cnv-fbc repo.

Separates released versions (constants in graph.yaml) from the latest z-stream
being developed (tracked via updated_image.yaml). Released versions must match
exactly; the latest z-stream is compared against its current FBC channel state.
"""

import logging

import pytest

from cnv_upgrade_utilities.upgrade_types import SUPPORTED_VERSIONS
from cnv_upgrade_utilities.version_types import normalize_csv_version, parse_minor_version

from ..utils.fbc_parser import (
    get_fbc_entry_by_version,
    get_fbc_versions_in_channel,
    parse_fbc_graph,
    parse_updated_image,
)

yaml = pytest.importorskip("yaml", reason="pyyaml required for FBC tests")

pytestmark = [pytest.mark.fbc, pytest.mark.e2e]

LOGGER = logging.getLogger("cnv_e2e")


def _is_latest_z(csv_version: str, updated_image: dict | None) -> bool:
    """Check if a version is the latest z-stream being developed."""
    if not updated_image:
        return False
    return csv_version == updated_image["version"]


class TestFbcChannelConsistency:
    """Verify that Version Explorer build data matches FBC graph.yaml."""

    @pytest.mark.parametrize("minor", [parse_minor_version(v) for v in SUPPORTED_VERSIONS], ids=SUPPORTED_VERSIONS)
    def test_released_builds_exist_in_fbc(self, fbc_explorer, fbc_repo_path, minor):
        """Each released build in Version Explorer should exist in FBC under the same channel."""
        fbc_channels = parse_fbc_graph(fbc_repo_path, minor)
        if not fbc_channels:
            pytest.skip(f"No FBC graph.yaml found for v4.{minor}")

        builds = fbc_explorer.get_released_builds(minor_version=f"v4.{minor}", stage=True)
        if not builds:
            pytest.skip(f"No released builds found for v4.{minor}")

        updated_image = parse_updated_image(fbc_repo_path, minor)

        for build in builds:
            csv_version = normalize_csv_version(build.csv_version)
            channel = build.current_channel
            if not channel or channel not in fbc_channels:
                continue

            if _is_latest_z(csv_version, updated_image):
                fbc_channel = updated_image["channel"]
                fbc_versions = get_fbc_versions_in_channel(fbc_repo_path, minor, fbc_channel)
                assert csv_version in fbc_versions, (
                    f"Latest z-stream {csv_version} not found in FBC under its current channel '{fbc_channel}' "
                    f"(API says channel='{channel}', FBC updated_image says channel='{fbc_channel}')"
                )
                if channel != fbc_channel:
                    LOGGER.info(
                        "v4.%d: %s channel mismatch — API=%s, FBC=%s (expected during promotion)",
                        minor,
                        csv_version,
                        channel,
                        fbc_channel,
                    )
                continue

            fbc_versions = get_fbc_versions_in_channel(fbc_repo_path, minor, channel)
            assert csv_version in fbc_versions, (
                f"Build {csv_version} (channel={channel}) returned by Version Explorer "
                f"but not found in FBC graph.yaml for v4.{minor}/{channel}"
            )

    @pytest.mark.parametrize("minor", [parse_minor_version(v) for v in SUPPORTED_VERSIONS], ids=SUPPORTED_VERSIONS)
    def test_replaces_field_matches_fbc(self, fbc_explorer, fbc_repo_path, minor):
        """The 'replaces' field in Version Explorer should match FBC's candidate channel.

        The API returns replaces/skipRange from the candidate perspective regardless
        of current_channel, so we always compare against FBC's candidate channel.
        """
        fbc_channels = parse_fbc_graph(fbc_repo_path, minor)
        if not fbc_channels or "candidate" not in fbc_channels:
            pytest.skip(f"No candidate channel in FBC graph.yaml for v4.{minor}")

        builds = fbc_explorer.get_released_builds(minor_version=f"v4.{minor}", stage=True)
        if not builds:
            pytest.skip(f"No released builds found for v4.{minor}")

        updated_image = parse_updated_image(fbc_repo_path, minor)
        seen = set()

        for build in builds:
            csv_version = normalize_csv_version(build.csv_version)
            if csv_version in seen:
                continue
            seen.add(csv_version)

            if _is_latest_z(csv_version, updated_image):
                continue

            fbc_entry = get_fbc_entry_by_version(fbc_repo_path, minor, "candidate", csv_version)
            if not fbc_entry:
                continue

            ve_replaces = build.replaces.lstrip("v") if build.replaces else None
            fbc_replaces = fbc_entry["replaces_version"]

            if fbc_replaces and ve_replaces:
                assert ve_replaces == fbc_replaces, (
                    f"Build {csv_version}: Version Explorer replaces={ve_replaces} "
                    f"but FBC candidate says replaces={fbc_replaces}"
                )

    @pytest.mark.parametrize("minor", [parse_minor_version(v) for v in SUPPORTED_VERSIONS], ids=SUPPORTED_VERSIONS)
    def test_skip_range_matches_fbc(self, fbc_explorer, fbc_repo_path, minor):
        """The 'skipRange' field should match FBC's candidate channel.

        The API returns replaces/skipRange from the candidate perspective regardless
        of current_channel, so we always compare against FBC's candidate channel.
        """
        fbc_channels = parse_fbc_graph(fbc_repo_path, minor)
        if not fbc_channels or "candidate" not in fbc_channels:
            pytest.skip(f"No candidate channel in FBC graph.yaml for v4.{minor}")

        builds = fbc_explorer.get_released_builds(minor_version=f"v4.{minor}", stage=True)
        if not builds:
            pytest.skip(f"No released builds found for v4.{minor}")

        updated_image = parse_updated_image(fbc_repo_path, minor)
        seen = set()

        for build in builds:
            csv_version = normalize_csv_version(build.csv_version)
            if csv_version in seen:
                continue
            seen.add(csv_version)

            if _is_latest_z(csv_version, updated_image):
                continue

            fbc_entry = get_fbc_entry_by_version(fbc_repo_path, minor, "candidate", csv_version)
            if not fbc_entry or not fbc_entry["skip_range"]:
                continue

            ve_skip_range = build.skip_range or ""
            fbc_skip_range = fbc_entry["skip_range"]

            if fbc_skip_range:
                assert ve_skip_range == fbc_skip_range, (
                    f"Build {csv_version}: Version Explorer skipRange='{ve_skip_range}' "
                    f"but FBC candidate says skipRange='{fbc_skip_range}'"
                )
