import pytest
from factories import make_channel_info, make_released_build, make_successful_build

from utils.build_helpers import (
    channel_exists,
    channel_in_stage,
    channel_released_to_prod,
    extract_filtered_build_info,
    extract_from_build_info,
    extract_released_build_info,
    find_released_source,
    find_stable_stage_build,
    get_channel_info,
    make_build_result,
)
from utils.models import BuildResult


class TestChannelReleasedToProd:
    def test_released(self):
        channels = [make_channel_info(channel="stable", released_to_prod=True)]
        assert channel_released_to_prod(channels, "stable") is True

    def test_not_released(self):
        channels = [make_channel_info(channel="stable", released_to_prod=False)]
        assert channel_released_to_prod(channels, "stable") is False

    def test_channel_not_found(self):
        channels = [make_channel_info(channel="candidate", released_to_prod=True)]
        assert channel_released_to_prod(channels, "stable") is False

    def test_empty_channels(self):
        assert channel_released_to_prod([], "stable") is False


class TestChannelInStage:
    def test_in_stage(self):
        channels = [make_channel_info(channel="stable", in_stage=True)]
        assert channel_in_stage(channels, "stable") is True

    def test_not_in_stage(self):
        channels = [make_channel_info(channel="stable", in_stage=False)]
        assert channel_in_stage(channels, "stable") is False

    def test_channel_not_found(self):
        channels = [make_channel_info(channel="candidate")]
        assert channel_in_stage(channels, "stable") is False


class TestChannelExists:
    def test_exists(self):
        channels = [make_channel_info(channel="stable")]
        assert channel_exists(channels, "stable") is True

    def test_not_exists(self):
        channels = [make_channel_info(channel="candidate")]
        assert channel_exists(channels, "stable") is False

    def test_empty(self):
        assert channel_exists([], "stable") is False


class TestMakeBuildResult:
    def test_basic(self):
        result = make_build_result(
            version="4.20.3",
            bundle_version="4.20.3.rhel9-31",
            iib="registry/iib:123",
            channel="stable",
        )
        assert isinstance(result, BuildResult)
        assert result.version == "4.20.3"
        assert result.bundle_version == "4.20.3.rhel9-31"
        assert result.iib == "registry/iib:123"
        assert result.channel == "stable"

    def test_with_extra(self):
        extra = make_channel_info(in_stage=True, released_to_prod=False)
        result = make_build_result(
            version="4.20.3",
            bundle_version="4.20.3.rhel9-31",
            iib="registry/iib:123",
            channel="stable",
            extra=extra,
        )
        assert result.in_stage is True
        assert result.released_to_prod is False

    def test_without_extra(self):
        result = make_build_result(
            version="4.20.3",
            bundle_version="4.20.3.rhel9-31",
            iib="registry/iib:123",
            channel="stable",
        )
        assert result.in_stage is None
        assert result.released_to_prod is None


class TestExtractFilteredBuildInfo:
    def test_extract(self):
        build = make_successful_build(
            cnv_build="v4.20.3.rhel9-31",
            iib="registry/iib:123",
            channel="stable",
            released_to_prod=True,
            in_stage=False,
        )
        result = extract_filtered_build_info(build=build, version="4.20.3")
        assert result.version == "4.20.3"
        assert result.bundle_version == "4.20.3.rhel9-31"
        assert result.iib == "registry/iib:123"
        assert result.channel == "stable"

    def test_strips_v_prefix(self):
        build = make_successful_build(cnv_build="v4.20.3.rhel9-31")
        result = extract_filtered_build_info(build=build, version="4.20.3")
        assert result.bundle_version == "4.20.3.rhel9-31"


class TestExtractReleasedBuildInfo:
    def test_extract(self):
        channels = [make_channel_info(channel="stable", iib="registry/iib:456")]
        build = make_released_build(
            csv_version="v4.20.3",
            version="v4.20.3.rhel9-31",
            channels=channels,
        )
        result = extract_released_build_info(build=build, channel="stable")
        assert result.version == "4.20.3"
        assert result.bundle_version == "4.20.3.rhel9-31"
        assert result.iib == "registry/iib:456"
        assert result.channel == "stable"


class TestExtractBuildInfoResult:
    def test_extract(self):
        from factories import make_build_info

        channels = [make_channel_info(channel="stable", iib="registry/iib:789")]
        bi = make_build_info(cnv_version="v4.20.3.rhel9-31", channels=channels)
        result = extract_from_build_info(build_info=bi, channel="stable")
        assert result.version == "4.20.3"
        assert result.bundle_version == "4.20.3.rhel9-31"
        assert result.iib == "registry/iib:789"

    def test_strips_v_prefix_and_rhel_suffix(self):
        from factories import make_build_info

        channels = [make_channel_info(channel="stable")]
        bi = make_build_info(cnv_version="v4.20.0.rhel9-234", channels=channels)
        result = extract_from_build_info(build_info=bi, channel="stable")
        assert result.version == "4.20.0"
        assert result.bundle_version == "4.20.0.rhel9-234"


class TestGetChannelInfo:
    def test_found(self):
        channels = [
            make_channel_info(channel="candidate", iib="iib:1"),
            make_channel_info(channel="stable", iib="iib:2"),
        ]
        result = get_channel_info(channels=channels, channel="stable")
        assert result.iib == "iib:2"

    def test_not_found_raises(self):
        channels = [make_channel_info(channel="candidate")]
        with pytest.raises(ValueError, match="Channel 'stable' not found"):
            get_channel_info(channels=channels, channel="stable")


class TestFindStableStageBuild:
    def test_found_not_released(self, mock_explorer):
        build = make_successful_build(
            cnv_build="v4.20.3.rhel9-31",
            iib="registry/iib:123",
            channel="stable",
            released_to_prod=False,
            in_stage=True,
        )
        mock_explorer.get_successful_builds_by_version.return_value = [build]
        result = find_stable_stage_build(explorer=mock_explorer, version="4.20.3")
        assert result is not None
        assert result.version == "4.20.3"

    def test_all_released_to_prod_returns_none(self, mock_explorer):
        build = make_successful_build(released_to_prod=True)
        mock_explorer.get_successful_builds_by_version.return_value = [build]
        result = find_stable_stage_build(explorer=mock_explorer, version="4.20.3")
        assert result is None

    def test_no_builds_returns_none(self, mock_explorer):
        mock_explorer.get_successful_builds_by_version.return_value = []
        result = find_stable_stage_build(explorer=mock_explorer, version="4.20.3")
        assert result is None


class TestFindReleasedSource:
    def test_found_stable_prod(self, mock_explorer):
        channels = [make_channel_info(channel="stable", released_to_prod=True, iib="iib:1")]
        build = make_released_build(csv_version="v4.20.3", version="v4.20.3.rhel9-31", channels=channels)
        mock_explorer.get_released_builds.return_value = [build]
        result = find_released_source(explorer=mock_explorer, minor_version="v4.20")
        assert result.version == "4.20.3"

    def test_with_required_csv_match(self, mock_explorer):
        channels = [make_channel_info(channel="stable", released_to_prod=True)]
        build = make_released_build(csv_version="v4.20.0", channels=channels)
        mock_explorer.get_released_builds.return_value = [build]
        result = find_released_source(explorer=mock_explorer, minor_version="v4.20", required_csv="v4.20.0")
        assert result.version == "4.20.0"

    def test_with_required_csv_no_match_raises(self, mock_explorer):
        channels = [make_channel_info(channel="stable", released_to_prod=True)]
        build = make_released_build(csv_version="v4.20.3", channels=channels)
        mock_explorer.get_released_builds.return_value = [build]
        with pytest.raises(ValueError, match="No stable build released to prod found for source version"):
            find_released_source(explorer=mock_explorer, minor_version="v4.20", required_csv="v4.20.0")

    def test_with_exclude_csv(self, mock_explorer):
        channels = [make_channel_info(channel="stable", released_to_prod=True)]
        build_excluded = make_released_build(csv_version="v4.20.5", channels=channels)
        build_ok = make_released_build(csv_version="v4.20.3", version="v4.20.3.rhel9-31", channels=channels)
        mock_explorer.get_released_builds.return_value = [build_excluded, build_ok]
        result = find_released_source(explorer=mock_explorer, minor_version="v4.20", exclude_csv="4.20.5")
        assert result.version == "4.20.3"

    def test_no_builds_raises(self, mock_explorer):
        mock_explorer.get_released_builds.return_value = []
        with pytest.raises(ValueError, match="No released builds found"):
            find_released_source(explorer=mock_explorer, minor_version="v4.20")

    def test_no_stable_prod_raises(self, mock_explorer):
        channels = [make_channel_info(channel="stable", released_to_prod=False)]
        build = make_released_build(channels=channels)
        mock_explorer.get_released_builds.return_value = [build]
        with pytest.raises(ValueError, match="No stable build released to prod"):
            find_released_source(explorer=mock_explorer, minor_version="v4.20")
