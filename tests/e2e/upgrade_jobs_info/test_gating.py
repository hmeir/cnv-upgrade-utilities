"""E2E tests for upgrade_jobs_info gating mode (candidate channel)."""

import logging

import pytest

from cnv_upgrade_utilities.upgrade_jobs_info import get_gating_jobs_info
from cnv_upgrade_utilities.upgrade_types import SUPPORTED_VERSIONS
from cnv_upgrade_utilities.version_types import parse_minor_version

LOGGER = logging.getLogger("cnv_e2e")


def _assert_gating_result_valid(result: dict, target_version: str) -> None:
    """Validate structural correctness of a gating result."""
    assert result["upgrade_type"] == "gating"

    source_info = result["source"]
    target_info = result["target"]

    assert source_info["channel"] == "candidate"
    assert source_info.get("released_to_prod") is True
    assert source_info["version"]
    assert source_info["bundle_version"]
    assert source_info["iib"]

    assert target_info["channel"] == "candidate"
    assert target_info.get("in_stage") is True
    assert target_info["version"]
    assert target_info["bundle_version"]
    assert target_info["iib"]

    expected_minor = parse_minor_version(target_version)
    assert parse_minor_version(source_info["version"]) == expected_minor
    assert parse_minor_version(target_info["version"]) == expected_minor

    assert source_info["version"] != target_info["version"], "Source and target should be different builds"


@pytest.mark.e2e
class TestGating:
    """Gating mode: candidate-prod source -> candidate-stage target."""

    def test_gating(self, explorer):
        tested = 0
        total = len(SUPPORTED_VERSIONS)
        for i, version in enumerate(SUPPORTED_VERSIONS, 1):
            LOGGER.info("[%d/%d] gating: %s", i, total, version)
            try:
                result = get_gating_jobs_info(explorer, target_version=version)
            except ValueError as exc:
                LOGGER.info("[%d/%d] gating: %s — skipped (%s)", i, total, version, exc)
                continue
            _assert_gating_result_valid(result, version)
            LOGGER.info(
                "[%d/%d] gating: %s — source=%s, target=%s",
                i,
                total,
                version,
                result["source"]["version"],
                result["target"]["version"],
            )
            tested += 1

        if tested == 0:
            pytest.skip("No supported version had candidate builds available for gating")
