"""FBC test fixtures — shared across all FBC tests."""

import os
import subprocess
import tempfile

import pytest

from utils.version_explorer import CnvVersionExplorer

from ..utils.fbc_data import FBC_REPO_URL, FbcVersionData, clone_fbc_branch

FBC_BRANCH = "stage"


@pytest.fixture(scope="session")
def fbc_data():
    """Clone cnv-fbc stage + production branches and build version data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        stage_path = f"{tmpdir}/stage"
        prod_path = f"{tmpdir}/production"
        clone_fbc_branch("stage", stage_path)
        clone_fbc_branch("production", prod_path)
        yield FbcVersionData(stage_path, prod_path)


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
    """Real CnvVersionExplorer for FBC comparison tests. Uses default URL if not overridden."""
    with CnvVersionExplorer() as exp:
        yield exp
