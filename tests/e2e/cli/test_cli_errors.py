"""E2E tests for CLI error handling — both commands produce clean errors."""

import subprocess

import pytest


@pytest.mark.e2e
class TestCLIErrorHandling:
    """Verify CLI commands produce clean errors (no Python tracebacks)."""

    @pytest.mark.parametrize(
        ("args", "expected_error"),
        [
            (["-s", "4.20", "-t", "4.19"], "Error:"),
            (["-s", "4.15", "-t", "4.16"], "Error:"),
            (["-s", "4.20.5", "-t", "4.20.5"], "Error:"),
        ],
        ids=["downgrade", "eol-source", "same-version"],
    )
    def test_upgrade_jobs_info_clean_error(self, args, expected_error):
        result = subprocess.run(
            ["uv", "run", "upgrade_jobs_info", *args],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 1
        assert expected_error in result.stderr
        assert "Traceback" not in result.stderr

    @pytest.mark.parametrize(
        ("args", "expected_error"),
        [
            (["-v", "4.16.99"], "Error:"),
            (["-v", "4.13.5", "--skip-target-check"], "Error:"),
        ],
        ids=["non-existent-version", "eol-version"],
    )
    def test_release_checklist_clean_error(self, args, expected_error):
        result = subprocess.run(
            ["uv", "run", "release_checklist_upgrade_plan", *args],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 1
        assert expected_error in result.stderr
        assert "Traceback" not in result.stderr
