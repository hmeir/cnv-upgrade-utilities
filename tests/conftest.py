from unittest.mock import Mock, create_autospec

import pytest

from utils.models import BuildInfo, ChannelInfo, ReleasedBuild, SuccessfulBuild
from utils.version_explorer import CnvVersionExplorer


@pytest.fixture
def mock_explorer():
    """Auto-specced CnvVersionExplorer with no real network calls."""
    explorer = create_autospec(CnvVersionExplorer, instance=True)
    explorer.__enter__ = Mock(return_value=explorer)
    explorer.__exit__ = Mock(return_value=False)
    return explorer


def make_channel_info(
    channel="stable",
    iib="registry-proxy.engineering.redhat.com/rh-osbs/iib:12345",
    released_to_prod=True,
    in_stage=False,
    fbc_snapshot=None,
):
    return ChannelInfo(
        channel=channel,
        iib=iib,
        released_to_prod=released_to_prod,
        in_stage=in_stage,
        fbc_snapshot=fbc_snapshot,
    )


def make_released_build(
    csv_version="v4.20.3",
    version="v4.20.3.rhel9-31",
    current_channel="stable",
    channels=None,
    build_timestamp="2026-01-01T00:00:00Z",
):
    if channels is None:
        channels = [make_channel_info()]
    return ReleasedBuild(
        csv_version=csv_version,
        version=version,
        current_channel=current_channel,
        channels=channels,
        build_timestamp=build_timestamp,
    )


def make_successful_build(
    cnv_build="v4.20.3.rhel9-31",
    iib="registry-proxy.engineering.redhat.com/rh-osbs/iib:12345",
    channel="stable",
    released_to_prod=True,
    in_stage=False,
):
    return SuccessfulBuild(
        cnv_build=cnv_build,
        iib=iib,
        channel=channel,
        released_to_prod=released_to_prod,
        in_stage=in_stage,
    )


def make_build_info(
    cnv_version="v4.20.3.rhel9-31",
    current_channel="stable",
    channels=None,
):
    if channels is None:
        channels = [make_channel_info()]
    return BuildInfo(
        cnv_version=cnv_version,
        current_channel=current_channel,
        channels=channels,
    )
