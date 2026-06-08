"""Shared assertion helpers for E2E tests."""

from cnv_upgrade_utilities.version_types import parse_minor_version, parse_patch_version


def assert_upgrade_result_valid(result: dict, source_version: str, target_version: str, expected_type: str) -> None:
    """Validate structural correctness of an upgrade result."""
    assert result["upgrade_type"] == expected_type

    source_info = result["source"]
    target_info = result["target"]

    assert source_info["channel"] == "stable"
    assert source_info.get("released_to_prod") is True
    assert source_info["version"]
    assert source_info["bundle_version"]
    assert source_info["iib"]

    assert target_info["version"]
    assert target_info["bundle_version"]
    assert target_info["iib"]

    expected_source_minor = parse_minor_version(source_version)
    expected_target_minor = parse_minor_version(target_version)
    assert parse_minor_version(source_info["version"]) == expected_source_minor
    assert parse_minor_version(target_info["version"]) == expected_target_minor

    if expected_type == "z_stream":
        source_patch = parse_patch_version(source_info["version"])
        target_patch = parse_patch_version(target_info["version"])
        assert source_patch is not None and target_patch is not None
        assert target_patch >= source_patch, (
            f"Z-stream target {target_info['version']} should be >= source {source_info['version']}"
        )

    elif expected_type == "latest_z":
        assert source_info["version"].endswith(".0"), f"Latest-Z source should be X.Y.0, got {source_info['version']}"

    elif expected_type in ("y_stream", "eus"):
        assert target_info["channel"] == "stable"
