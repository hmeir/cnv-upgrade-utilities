import pytest
from factories import make_build_info, make_channel_info, make_released_build, make_successful_build

from cnv_upgrade_utilities.upgrade_jobs_info import (
    _fetch_bundle_source,
    _fetch_bundle_target,
    _fetch_full_source,
    _fetch_full_target,
    _fetch_minor_source,
    _fetch_minor_target,
    _is_initial_release,
    _requires_stable_target,
    fetch_version_info,
    format_upgrade_result,
    get_upgrade_jobs_info,
)
from cnv_upgrade_utilities.upgrade_types import UpgradeType
from utils.models import BuildResult


class TestHelpers:
    @pytest.mark.parametrize(
        ("version", "expected"),
        [
            ("4.20.0", True),
            ("4.20.0.rhel9-1", True),
            ("4.20.1", False),
            ("4.20.3", False),
        ],
    )
    def test_is_initial_release(self, version, expected):
        assert _is_initial_release(version) == expected

    @pytest.mark.parametrize(
        ("upgrade_type", "expected"),
        [
            (UpgradeType.Y_STREAM, True),
            (UpgradeType.EUS, True),
            (UpgradeType.Z_STREAM, False),
            (UpgradeType.LATEST_Z, False),
        ],
    )
    def test_requires_stable_target(self, upgrade_type, expected):
        assert _requires_stable_target(upgrade_type) == expected

    def test_format_upgrade_result(self):
        source = BuildResult(version="4.19.5", bundle_version="4.19.5.rhel9-10", iib="iib:1", channel="stable")
        target = BuildResult(version="4.20.3", bundle_version="4.20.3.rhel9-31", iib="iib:2", channel="stable")
        result = format_upgrade_result(
            upgrade_type=UpgradeType.Y_STREAM,
            source_info=source,
            target_info=target,
        )
        assert result["upgrade_type"] == "y_stream"
        assert result["source"]["version"] == "4.19.5"
        assert result["target"]["version"] == "4.20.3"


class TestFetchBundleTarget:
    def test_stable_channel_found(self, mock_explorer):
        channels = [make_channel_info(channel="stable", iib="iib:1")]
        mock_explorer.get_build_info.return_value = make_build_info(cnv_version="v4.20.3.rhel9-31", channels=channels)
        result = _fetch_bundle_target(mock_explorer, "4.20.3.rhel9-31", UpgradeType.Z_STREAM)
        assert result.channel == "stable"

    def test_z_stream_candidate_fallback(self, mock_explorer):
        channels = [make_channel_info(channel="candidate", iib="iib:2")]
        mock_explorer.get_build_info.return_value = make_build_info(cnv_version="v4.20.3.rhel9-31", channels=channels)
        result = _fetch_bundle_target(mock_explorer, "4.20.3.rhel9-31", UpgradeType.Z_STREAM)
        assert result.channel == "candidate"

    def test_y_stream_no_stable_non_initial_raises(self, mock_explorer):
        channels = [make_channel_info(channel="candidate")]
        mock_explorer.get_build_info.return_value = make_build_info(cnv_version="v4.20.3.rhel9-31", channels=channels)
        with pytest.raises(ValueError, match="does not have a stable channel"):
            _fetch_bundle_target(mock_explorer, "4.20.3.rhel9-31", UpgradeType.Y_STREAM)

    def test_y_stream_initial_release_candidate_ok(self, mock_explorer):
        channels = [make_channel_info(channel="candidate", iib="iib:3")]
        mock_explorer.get_build_info.return_value = make_build_info(cnv_version="v4.20.0.rhel9-1", channels=channels)
        result = _fetch_bundle_target(mock_explorer, "4.20.0.rhel9-1", UpgradeType.Y_STREAM)
        assert result.channel == "candidate"

    def test_no_channels_raises(self, mock_explorer):
        mock_explorer.get_build_info.return_value = make_build_info(cnv_version="v4.20.3.rhel9-31", channels=[])
        with pytest.raises(ValueError, match="No stable or candidate channel"):
            _fetch_bundle_target(mock_explorer, "4.20.3.rhel9-31", UpgradeType.Z_STREAM)


class TestFetchBundleSource:
    def test_happy_path(self, mock_explorer):
        channels = [make_channel_info(channel="stable", released_to_prod=True, iib="iib:1")]
        mock_explorer.get_build_info.return_value = make_build_info(
            cnv_version="v4.19.5.rhel9-10", current_channel="stable", channels=channels
        )
        result = _fetch_bundle_source(mock_explorer, "4.19.5.rhel9-10")
        assert result.version == "4.19.5"
        assert result.channel == "stable"

    def test_non_stable_current_channel_raises(self, mock_explorer):
        mock_explorer.get_build_info.return_value = make_build_info(current_channel="candidate")
        with pytest.raises(ValueError, match="current_channel='candidate'"):
            _fetch_bundle_source(mock_explorer, "4.19.5.rhel9-10")

    def test_not_released_to_prod_raises(self, mock_explorer):
        channels = [make_channel_info(channel="stable", released_to_prod=False)]
        mock_explorer.get_build_info.return_value = make_build_info(current_channel="stable", channels=channels)
        with pytest.raises(ValueError, match="not released to prod"):
            _fetch_bundle_source(mock_explorer, "4.19.5.rhel9-10")


class TestFetchFullTarget:
    def test_stable_stage_found(self, mock_explorer):
        build = make_successful_build(
            cnv_build="v4.20.3.rhel9-31",
            iib="iib:1",
            channel="stable",
            released_to_prod=False,
            in_stage=True,
        )
        mock_explorer.get_successful_builds_by_version.return_value = [build]
        result = _fetch_full_target(mock_explorer, "4.20.3", UpgradeType.Z_STREAM)
        assert result.version == "4.20.3"

    def test_y_stream_no_stable_non_initial_raises(self, mock_explorer):
        mock_explorer.get_successful_builds_by_version.return_value = []
        with pytest.raises(ValueError, match="No stable build in stage"):
            _fetch_full_target(mock_explorer, "4.20.3", UpgradeType.Y_STREAM)

    def test_z_stream_candidate_prod_fallback(self, mock_explorer):
        candidate_build = make_successful_build(
            cnv_build="v4.20.3.rhel9-31",
            iib="iib:2",
            channel="candidate",
            released_to_prod=True,
            in_stage=False,
        )
        mock_explorer.get_successful_builds_by_version.side_effect = [
            [],  # stable stage
            [candidate_build],  # candidate prod
        ]
        result = _fetch_full_target(mock_explorer, "4.20.3", UpgradeType.Z_STREAM)
        assert result.channel == "candidate"

    def test_z_stream_candidate_stage_fallback(self, mock_explorer):
        candidate_build = make_successful_build(
            cnv_build="v4.20.3.rhel9-31",
            iib="iib:3",
            channel="candidate",
            released_to_prod=False,
            in_stage=True,
        )
        mock_explorer.get_successful_builds_by_version.side_effect = [
            [],  # stable stage
            [],  # candidate prod
            [candidate_build],  # candidate stage
        ]
        result = _fetch_full_target(mock_explorer, "4.20.3", UpgradeType.Z_STREAM)
        assert result.channel == "candidate"

    def test_no_builds_raises(self, mock_explorer):
        mock_explorer.get_successful_builds_by_version.return_value = []
        with pytest.raises(ValueError, match="No stable or candidate build"):
            _fetch_full_target(mock_explorer, "4.20.3", UpgradeType.Z_STREAM)


class TestFetchFullSource:
    def test_released_build_found(self, mock_explorer):
        build = make_successful_build(
            cnv_build="v4.19.5.rhel9-10",
            iib="iib:1",
            channel="stable",
            released_to_prod=True,
        )
        mock_explorer.get_successful_builds_by_version.return_value = [build]
        result = _fetch_full_source(mock_explorer, "4.19.5")
        assert result.version == "4.19.5"

    def test_fallback_to_released_builds(self, mock_explorer):
        mock_explorer.get_successful_builds_by_version.return_value = []
        channels = [make_channel_info(channel="stable", released_to_prod=True, iib="iib:2")]
        released_build = make_released_build(csv_version="v4.19.5", version="v4.19.5.rhel9-10", channels=channels)
        mock_explorer.get_released_builds.return_value = [released_build]
        result = _fetch_full_source(mock_explorer, "4.19.5")
        assert result.version == "4.19.5"


class TestFetchMinorTarget:
    def test_stable_stage_new_z_stream(self, mock_explorer):
        channels = [make_channel_info(channel="stable", released_to_prod=False, in_stage=True)]
        build = make_released_build(
            csv_version="v4.20.5",
            version="v4.20.5.rhel9-3",
            current_channel="stable",
            channels=channels,
        )
        mock_explorer.get_released_builds.return_value = [build]
        result = _fetch_minor_target(mock_explorer, "4.20", UpgradeType.Z_STREAM)
        assert result.version == "4.20.5"

    def test_stable_stage_any_y_stream(self, mock_explorer):
        channels = [make_channel_info(channel="stable", released_to_prod=True, in_stage=True)]
        build = make_released_build(
            csv_version="v4.20.3",
            version="v4.20.3.rhel9-31",
            current_channel="stable",
            channels=channels,
        )
        mock_explorer.get_released_builds.return_value = [build]
        result = _fetch_minor_target(mock_explorer, "4.20", UpgradeType.Y_STREAM)
        assert result.version == "4.20.3"

    def test_y_stream_stable_prod_fallback(self, mock_explorer):
        channels_prod = [make_channel_info(channel="stable", released_to_prod=True, in_stage=False)]
        build = make_released_build(
            csv_version="v4.20.3",
            version="v4.20.3.rhel9-31",
            current_channel="stable",
            channels=channels_prod,
        )
        mock_explorer.get_released_builds.return_value = [build]
        result = _fetch_minor_target(mock_explorer, "4.20", UpgradeType.Y_STREAM)
        assert result.version == "4.20.3"

    def test_candidate_fallback(self, mock_explorer):
        channels = [make_channel_info(channel="candidate", released_to_prod=True)]
        build = make_released_build(
            csv_version="v4.20.3",
            version="v4.20.3.rhel9-31",
            current_channel="candidate",
            channels=channels,
        )
        mock_explorer.get_released_builds.return_value = [build]
        result = _fetch_minor_target(mock_explorer, "4.20", UpgradeType.Z_STREAM)
        assert result.channel == "candidate"

    def test_no_builds_raises(self, mock_explorer):
        mock_explorer.get_released_builds.return_value = []
        with pytest.raises(ValueError, match="No released builds found"):
            _fetch_minor_target(mock_explorer, "4.20", UpgradeType.Z_STREAM)

    def test_y_stream_no_stable_non_initial_raises(self, mock_explorer):
        channels = [make_channel_info(channel="candidate", released_to_prod=True)]
        build = make_released_build(
            csv_version="v4.20.3",
            version="v4.20.3.rhel9-31",
            current_channel="candidate",
            channels=channels,
        )
        mock_explorer.get_released_builds.return_value = [build]
        with pytest.raises(ValueError, match="No stable build"):
            _fetch_minor_target(mock_explorer, "4.20", UpgradeType.Y_STREAM)

    def test_stale_stable_stage_skipped(self, mock_explorer):
        stale_channels = [make_channel_info(channel="stable", released_to_prod=False, in_stage=True)]
        stale_build = make_released_build(
            csv_version="v4.20.1",
            version="v4.20.1.rhel9-5",
            current_channel="stable",
            channels=stale_channels,
        )
        latest_channels = [make_channel_info(channel="candidate", released_to_prod=True)]
        latest_build = make_released_build(
            csv_version="v4.20.5",
            version="v4.20.5.rhel9-3",
            current_channel="candidate",
            channels=latest_channels,
        )
        mock_explorer.get_released_builds.return_value = [latest_build, stale_build]
        result = _fetch_minor_target(mock_explorer, "4.20", UpgradeType.Z_STREAM)
        assert result.channel == "candidate"


class TestFetchMinorSource:
    def test_delegates_to_find_released_source(self, mock_explorer):
        channels = [make_channel_info(channel="stable", released_to_prod=True, iib="iib:1")]
        build = make_released_build(csv_version="v4.19.5", version="v4.19.5.rhel9-10", channels=channels)
        mock_explorer.get_released_builds.return_value = [build]
        result = _fetch_minor_source(mock_explorer, "4.19")
        assert result.version == "4.19.5"

    def test_with_exclude_version(self, mock_explorer):
        channels = [make_channel_info(channel="stable", released_to_prod=True, iib="iib:1")]
        build_excluded = make_released_build(csv_version="v4.20.5", channels=channels)
        build_ok = make_released_build(csv_version="v4.20.3", version="v4.20.3.rhel9-31", channels=channels)
        mock_explorer.get_released_builds.return_value = [build_excluded, build_ok]
        result = _fetch_minor_source(mock_explorer, "4.20", exclude_version="4.20.5")
        assert result.version == "4.20.3"


class TestFetchVersionInfo:
    def test_routes_minor_target(self, mock_explorer):
        channels = [make_channel_info(channel="stable", released_to_prod=False, in_stage=True)]
        build = make_released_build(
            csv_version="v4.20.5",
            version="v4.20.5.rhel9-3",
            current_channel="stable",
            channels=channels,
        )
        mock_explorer.get_released_builds.return_value = [build]
        result = fetch_version_info(
            explorer=mock_explorer,
            version="4.20",
            is_source=False,
            upgrade_type=UpgradeType.Z_STREAM,
        )
        assert result.version == "4.20.5"

    def test_routes_full_source(self, mock_explorer):
        build = make_successful_build(
            cnv_build="v4.19.5.rhel9-10",
            iib="iib:1",
            channel="stable",
            released_to_prod=True,
        )
        mock_explorer.get_successful_builds_by_version.return_value = [build]
        result = fetch_version_info(
            explorer=mock_explorer,
            version="4.19.5",
            is_source=True,
            upgrade_type=UpgradeType.Y_STREAM,
        )
        assert result.version == "4.19.5"

    def test_routes_bundle_target(self, mock_explorer):
        channels = [make_channel_info(channel="stable", iib="iib:1")]
        mock_explorer.get_build_info.return_value = make_build_info(
            cnv_version="v4.20.3.rhel9-31",
            channels=channels,
        )
        result = fetch_version_info(
            explorer=mock_explorer,
            version="4.20.3.rhel9-31",
            is_source=False,
            upgrade_type=UpgradeType.Z_STREAM,
        )
        assert result.version == "4.20.3"


class TestGetUpgradeJobsInfo:
    def test_y_stream(self, mock_explorer):
        target_build = make_successful_build(
            cnv_build="v4.20.3.rhel9-31",
            iib="iib:target",
            channel="stable",
            released_to_prod=False,
            in_stage=True,
        )
        source_channels = [make_channel_info(channel="stable", released_to_prod=True, iib="iib:source")]
        source_build = make_released_build(
            csv_version="v4.19.5",
            version="v4.19.5.rhel9-10",
            channels=source_channels,
        )
        mock_explorer.get_successful_builds_by_version.return_value = [target_build]
        mock_explorer.get_released_builds.return_value = [source_build]
        result = get_upgrade_jobs_info(mock_explorer, source_version="4.19", target_version="4.20.3")
        assert result["upgrade_type"] == "y_stream"
        assert result["target"]["version"] == "4.20.3"
        assert result["source"]["version"] == "4.19.5"

    def test_z_stream(self, mock_explorer):
        target_channels = [make_channel_info(channel="stable", released_to_prod=False, in_stage=True)]
        target_build = make_released_build(
            csv_version="v4.20.5",
            version="v4.20.5.rhel9-3",
            current_channel="stable",
            channels=target_channels,
        )
        source_channels = [make_channel_info(channel="stable", released_to_prod=True, iib="iib:source")]
        source_build = make_released_build(
            csv_version="v4.20.3",
            version="v4.20.3.rhel9-31",
            channels=source_channels,
        )
        mock_explorer.get_released_builds.return_value = [target_build, source_build]
        result = get_upgrade_jobs_info(mock_explorer, source_version="4.20", target_version="4.20")
        assert result["upgrade_type"] == "z_stream"

    def test_eus(self, mock_explorer):
        target_build = make_successful_build(
            cnv_build="v4.20.3.rhel9-31",
            iib="iib:target",
            channel="stable",
            released_to_prod=False,
            in_stage=True,
        )
        source_channels = [make_channel_info(channel="stable", released_to_prod=True, iib="iib:source")]
        source_build = make_released_build(
            csv_version="v4.18.10",
            version="v4.18.10.rhel9-5",
            channels=source_channels,
        )
        mock_explorer.get_successful_builds_by_version.return_value = [target_build]
        mock_explorer.get_released_builds.return_value = [source_build]
        result = get_upgrade_jobs_info(mock_explorer, source_version="4.18", target_version="4.20.3")
        assert result["upgrade_type"] == "eus"

    def test_latest_z(self, mock_explorer):
        target_build = make_successful_build(
            cnv_build="v4.20.3.rhel9-31",
            iib="iib:target",
            channel="stable",
            released_to_prod=False,
            in_stage=True,
        )
        source_channels = [make_channel_info(channel="stable", released_to_prod=True, iib="iib:source")]
        source_build = make_released_build(
            csv_version="v4.20.0",
            version="v4.20.0.rhel9-234",
            channels=source_channels,
        )
        mock_explorer.get_successful_builds_by_version.return_value = [target_build]
        mock_explorer.get_released_builds.return_value = [source_build]
        result = get_upgrade_jobs_info(mock_explorer, source_version="4.20.0", target_version="4.20.3")
        assert result["upgrade_type"] == "latest_z"
