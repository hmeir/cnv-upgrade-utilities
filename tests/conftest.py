from unittest.mock import Mock, create_autospec

import pytest

from utils.version_explorer import CnvVersionExplorer

_EXTERNAL_MARKERS = {"e2e", "fbc"}


def pytest_collection_modifyitems(config, items):
    """Auto-deselect e2e/fbc tests unless explicitly requested via -m."""
    marker_expr = config.getoption("-m", default="")
    if any(m in marker_expr for m in _EXTERNAL_MARKERS):
        return
    items[:] = [item for item in items if not (_EXTERNAL_MARKERS & {m.name for m in item.iter_markers()})]


@pytest.fixture
def mock_explorer():
    """Auto-specced CnvVersionExplorer with no real network calls."""
    explorer = create_autospec(CnvVersionExplorer, instance=True)
    explorer.__enter__ = Mock(return_value=explorer)
    explorer.__exit__ = Mock(return_value=False)
    return explorer
