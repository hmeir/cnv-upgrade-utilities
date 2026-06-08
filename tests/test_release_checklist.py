import pytest
from factories import make_channel_info, make_released_build, make_successful_build
from packaging.version import Version

from cnv_upgrade_utilities.post_upgrade_suites import POST_UPGRADE_SUITE_MARKER, POST_UPGRADE_SUITE_NONE
from cnv_upgrade_utilities.release_checklist_upgrade_plan import (
    ReleaseChecklistUpgradeEntry,
    fetch_source_version,
    fetch_target_version,
    get_upgrade_paths_info,
)
from utils.models import BuildResult


class TestReleaseChecklistUpgradeEntry:
    def test_from_build_result(self):
        br = BuildResult(
            version="4.19.5",
            bundle_version="4.19.5.rhel9-10",
            iib="iib:1",
            channel="stable",
        )
        entry = ReleaseChecklistUpgradeEntry.from_build_result(br, "UTS-FULL")
        assert entry.source_version == "4.19.5"
        assert entry.bundle_version == "4.19.5.rhel9-10"
        assert entry.iib == "iib:1"
        assert entry.channel == "stable"
        assert entry.post_upgrade_suite == "UTS-FULL"

    def test_to_dict(self):
        entry = ReleaseChecklistUpgradeEntry(
            source_version="4.19.5",
            bundle_version="4.19.5.rhel9-10",
            iib="iib:1",
            channel="stable",
            post_upgrade_suite="UTS-FULL",
        )
        d = entry.to_dict()
        assert d["source_version"] == "4.19.5"
        assert d["post_upgrade_suite"] == "UTS-FULL"


class TestFetchTargetVersion:
    def test_stable_stage_found(self, mock_explorer):
        build = make_successful_build(
            cnv_build="v4.20.3.rhel9-31",
            iib="iib:1",
            channel="stable",
            released_to_prod=False,
            in_stage=True,
        )
        mock_explorer.get_successful_builds_by_version.return_value = [build]
        result = fetch_target_version(mock_explorer, Version("4.20.3"))
        assert result.version == "4.20.3"

    def test_already_released_raises(self, mock_explorer):
        released_build = make_successful_build(released_to_prod=True, in_stage=True)
        stable_build = make_successful_build(released_to_prod=True, in_stage=False)
        mock_explorer.get_successful_builds_by_version.side_effect = [
            [released_build],  # stable + stage (all released)
            [stable_build],  # stable (has builds but none in stage)
        ]
        with pytest.raises(ValueError, match="already released to prod"):
            fetch_target_version(mock_explorer, Version("4.20.3"))

    def test_no_builds_raises(self, mock_explorer):
        mock_explorer.get_successful_builds_by_version.side_effect = [
            [],  # stable + stage
            [],  # stable (no builds at all)
        ]
        with pytest.raises(ValueError, match="No stable build found"):
            fetch_target_version(mock_explorer, Version("4.20.3"))

    def test_skip_target_check_stable(self, mock_explorer):
        build = make_successful_build(
            cnv_build="v4.20.3.rhel9-31",
            iib="iib:1",
            channel="stable",
            released_to_prod=True,
            in_stage=False,
        )
        mock_explorer.get_successful_builds_by_version.side_effect = [
            [make_successful_build(released_to_prod=True)],  # stable + stage (all released)
            [build],  # stable fallback
        ]
        result = fetch_target_version(mock_explorer, Version("4.20.3"), skip_target_check=True)
        assert result.version == "4.20.3"

    def test_skip_target_check_candidate(self, mock_explorer):
        candidate_build = make_successful_build(
            cnv_build="v4.20.3.rhel9-31",
            iib="iib:2",
            channel="candidate",
        )
        mock_explorer.get_successful_builds_by_version.side_effect = [
            [make_successful_build(released_to_prod=True)],  # stable + stage (all released)
            [],  # stable (empty)
            [candidate_build],  # candidate
        ]
        result = fetch_target_version(mock_explorer, Version("4.20.3"), skip_target_check=True)
        assert result.channel == "candidate"


class TestFetchSourceVersion:
    def test_y_stream_offset(self, mock_explorer):
        channels = [make_channel_info(channel="stable", released_to_prod=True, iib="iib:1")]
        build = make_released_build(csv_version="v4.19.5", version="v4.19.5.rhel9-10", channels=channels)
        mock_explorer.get_released_builds.return_value = [build]
        result = fetch_source_version(mock_explorer, Version("4.20.3"), minor_offset=-1)
        assert result.version == "4.19.5"
        mock_explorer.get_released_builds.assert_called_once_with(minor_version="v4.19", stage=False)

    def test_eus_offset(self, mock_explorer):
        channels = [make_channel_info(channel="stable", released_to_prod=True, iib="iib:1")]
        build = make_released_build(csv_version="v4.18.10", version="v4.18.10.rhel9-5", channels=channels)
        mock_explorer.get_released_builds.return_value = [build]
        result = fetch_source_version(mock_explorer, Version("4.20.3"), minor_offset=-2)
        assert result.version == "4.18.10"
        mock_explorer.get_released_builds.assert_called_once_with(minor_version="v4.18", stage=False)

    def test_z_stream_offset(self, mock_explorer):
        channels = [make_channel_info(channel="stable", released_to_prod=True, iib="iib:1")]
        build = make_released_build(csv_version="v4.20.1", version="v4.20.1.rhel9-13", channels=channels)
        mock_explorer.get_released_builds.return_value = [build]
        result = fetch_source_version(mock_explorer, Version("4.20.3"), minor_offset=0)
        assert result.version == "4.20.1"

    def test_latest_z_none_offset(self, mock_explorer):
        channels = [make_channel_info(channel="stable", released_to_prod=True, iib="iib:1")]
        build = make_released_build(csv_version="v4.20.0", version="v4.20.0.rhel9-234", channels=channels)
        mock_explorer.get_released_builds.return_value = [build]
        result = fetch_source_version(mock_explorer, Version("4.20.3"), minor_offset=None)
        assert result.version == "4.20.0"


class TestGetUpgradePathsInfo:
    def _setup_mocks(self, mock_explorer, target_version="4.20.2"):
        target_build = make_successful_build(
            cnv_build=f"v{target_version}.rhel9-5",
            iib="iib:target",
            channel="stable",
            released_to_prod=False,
            in_stage=True,
        )
        mock_explorer.get_successful_builds_by_version.return_value = [target_build]

        y_channels = [make_channel_info(channel="stable", released_to_prod=True, iib="iib:y")]
        z_channels = [make_channel_info(channel="stable", released_to_prod=True, iib="iib:z")]
        lz_channels = [make_channel_info(channel="stable", released_to_prod=True, iib="iib:lz")]

        y_build = make_released_build(csv_version="v4.19.5", version="v4.19.5.rhel9-10", channels=y_channels)
        z_build = make_released_build(csv_version="v4.20.1", version="v4.20.1.rhel9-13", channels=z_channels)
        lz_build = make_released_build(csv_version="v4.20.0", version="v4.20.0.rhel9-234", channels=lz_channels)

        def released_builds_side_effect(minor_version, stage=False):
            if minor_version == "v4.19":
                return [y_build]
            elif minor_version == "v4.20":
                return [z_build, lz_build]
            return []

        mock_explorer.get_released_builds.side_effect = released_builds_side_effect

    def test_z2_has_y_z_latest_z(self, mock_explorer):
        self._setup_mocks(mock_explorer)
        result = get_upgrade_paths_info(mock_explorer, Version("4.20.2"))
        lanes = result["upgrade_lanes"]
        assert "Y stream" in lanes
        assert "Z stream" in lanes
        assert "latest z" in lanes
        assert result["target_version"] == "4.20.2"

    def test_z0_even_has_y_eus(self, mock_explorer):
        target_build = make_successful_build(
            cnv_build="v4.20.0.rhel9-234",
            iib="iib:target",
            channel="stable",
            released_to_prod=False,
            in_stage=True,
        )
        mock_explorer.get_successful_builds_by_version.return_value = [target_build]

        y_channels = [make_channel_info(channel="stable", released_to_prod=True, iib="iib:y")]
        eus_channels = [make_channel_info(channel="stable", released_to_prod=True, iib="iib:eus")]
        y_build = make_released_build(csv_version="v4.19.5", version="v4.19.5.rhel9-10", channels=y_channels)
        eus_build = make_released_build(csv_version="v4.18.10", version="v4.18.10.rhel9-5", channels=eus_channels)

        def released_builds_side_effect(minor_version, stage=False):
            if minor_version == "v4.19":
                return [y_build]
            elif minor_version == "v4.18":
                return [eus_build]
            return []

        mock_explorer.get_released_builds.side_effect = released_builds_side_effect
        result = get_upgrade_paths_info(mock_explorer, Version("4.20.0"))
        lanes = result["upgrade_lanes"]
        assert "Y stream" in lanes
        assert "EUS" in lanes
        assert "Z stream" not in lanes

    def test_z2_skip_y_stream_has_eus(self, mock_explorer):
        target_build = make_successful_build(
            cnv_build="v4.16.5.rhel9-10",
            iib="iib:target",
            channel="stable",
            released_to_prod=False,
            in_stage=True,
        )
        mock_explorer.get_successful_builds_by_version.return_value = [target_build]

        eus_channels = [make_channel_info(channel="stable", released_to_prod=True, iib="iib:eus")]
        z_channels = [make_channel_info(channel="stable", released_to_prod=True, iib="iib:z")]
        lz_channels = [make_channel_info(channel="stable", released_to_prod=True, iib="iib:lz")]
        eus_build = make_released_build(csv_version="v4.14.8", version="v4.14.8.rhel9-5", channels=eus_channels)
        z_build = make_released_build(csv_version="v4.16.4", version="v4.16.4.rhel9-3", channels=z_channels)
        lz_build = make_released_build(csv_version="v4.16.0", version="v4.16.0.rhel9-100", channels=lz_channels)

        def released_builds_side_effect(minor_version, stage=False):
            if minor_version == "v4.14":
                return [eus_build]
            elif minor_version == "v4.16":
                return [z_build, lz_build]
            return []

        mock_explorer.get_released_builds.side_effect = released_builds_side_effect
        result = get_upgrade_paths_info(mock_explorer, Version("4.16.5"))
        lanes = result["upgrade_lanes"]
        assert "Y stream" not in lanes
        assert "EUS" in lanes
        assert "Z stream" in lanes
        assert "latest z" in lanes
        assert lanes["EUS"]["post_upgrade_suite"] == POST_UPGRADE_SUITE_MARKER

    def test_post_upgrade_suites_correct(self, mock_explorer):
        self._setup_mocks(mock_explorer)
        result = get_upgrade_paths_info(mock_explorer, Version("4.20.2"))
        lanes = result["upgrade_lanes"]
        assert lanes["Y stream"]["post_upgrade_suite"] == POST_UPGRADE_SUITE_MARKER
        assert lanes["Z stream"]["post_upgrade_suite"] == POST_UPGRADE_SUITE_NONE
        assert lanes["latest z"]["post_upgrade_suite"] == POST_UPGRADE_SUITE_NONE
