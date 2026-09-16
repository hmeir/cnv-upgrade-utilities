from unittest.mock import Mock

import pytest

from utils.constants import DEFAULT_VERSION_EXPLORER_URL, ENV_VERSION_EXPLORER_URL
from utils.version_explorer import CnvVersionExplorer

BASE_URL = "http://cnv-version-explorer.apps.cnv2.engineering.redhat.com"


class TestUrlNormalization:
    @pytest.mark.parametrize("url", [BASE_URL, f"{BASE_URL}/"])
    def test_constructor_url_normalized(self, url):
        with CnvVersionExplorer(url=url) as explorer:
            assert explorer.url == BASE_URL

    @pytest.mark.parametrize("env_url", [BASE_URL, f"{BASE_URL}/"])
    def test_env_var_url_normalized(self, monkeypatch, env_url):
        monkeypatch.setenv(ENV_VERSION_EXPLORER_URL, env_url)
        with CnvVersionExplorer() as explorer:
            assert explorer.url == BASE_URL

    def test_default_url_has_no_trailing_slash(self):
        assert not DEFAULT_VERSION_EXPLORER_URL.endswith("/")

    @pytest.mark.parametrize("url", [BASE_URL, f"{BASE_URL}/"])
    def test_query_joins_endpoint_with_single_slash(self, url):
        mock_session = Mock()
        mock_response = Mock()
        mock_response.json.return_value = {"ok": True}
        mock_session.get.return_value = mock_response

        with CnvVersionExplorer(url=url) as explorer:
            explorer._session = mock_session
            result = explorer.query("GetReleasedBuilds", "minor_version=v4.22&stage=false")

        mock_session.get.assert_called_once()
        assert mock_session.get.call_args.kwargs["url"] == (
            f"{BASE_URL}/GetReleasedBuilds?minor_version=v4.22&stage=false"
        )
        assert result == {"ok": True}
