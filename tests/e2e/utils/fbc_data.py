"""FBC data layer: clone cnv-fbc repo and derive version/channel/stage/prod status."""

from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

from cnv_upgrade_utilities.version_types import parse_patch_version

from .fbc_parser import _extract_version

FBC_REPO_URL = "https://github.com/openshift-cnv/cnv-fbc.git"


def clone_fbc_branch(branch: str, target_dir: str) -> None:
    """Clone a specific branch of cnv-fbc into target_dir."""
    result = subprocess.run(
        ["git", "clone", "--depth", "1", "--branch", branch, FBC_REPO_URL, target_dir],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to clone cnv-fbc branch '{branch}': {result.stderr}")


def _parse_channel_versions(repo_path: str | Path, minor: int, channel: str) -> set[str]:
    """Parse graph.yaml and return all X.Y.Z versions in a channel for a given minor."""
    graph_path = Path(repo_path) / f"v4.{minor}" / "graph.yaml"
    if not graph_path.exists():
        return set()

    with open(graph_path) as f:
        data = yaml.safe_load(f)

    for entry in data.get("entries", []):
        if entry.get("schema") == "olm.channel" and entry.get("name") == channel:
            versions = set()
            for e in entry.get("entries", []):
                version = _extract_version(e.get("name", ""))
                if version and version.startswith(f"4.{minor}."):
                    versions.add(version)
            return versions
    return set()


class FbcVersionData:
    """Holds version data derived from FBC stage and production branches."""

    def __init__(self, stage_path: str, production_path: str):
        self.stage_path = stage_path
        self.production_path = production_path
        self._cache: dict[int, dict] = {}

    def get_minor_data(self, minor: int) -> dict:
        """Get version data for a minor, with caching."""
        if minor not in self._cache:
            self._cache[minor] = self._build_minor_data(minor)
        return self._cache[minor]

    def _build_minor_data(self, minor: int) -> dict:
        """Build version data for a minor by comparing stage vs production."""
        stage_stable = _parse_channel_versions(self.stage_path, minor, "stable")
        prod_stable = _parse_channel_versions(self.production_path, minor, "stable")
        stage_candidate = _parse_channel_versions(self.stage_path, minor, "candidate")
        prod_candidate = _parse_channel_versions(self.production_path, minor, "candidate")

        all_versions = sorted(stage_stable | prod_stable | stage_candidate | prod_candidate)

        versions = {}
        for version in all_versions:
            in_stable = version in stage_stable or version in prod_stable
            released_to_prod = version in prod_stable or version in prod_candidate
            in_stage_only = (version in stage_stable or version in stage_candidate) and not released_to_prod

            channel = "stable" if in_stable else "candidate"
            versions[version] = {
                "version": version,
                "channel": channel,
                "released_to_prod": released_to_prod,
                "in_stage": in_stage_only or released_to_prod,
            }

        return {
            "minor": minor,
            "versions": versions,
            "max_z": max((parse_patch_version(v) for v in all_versions), default=-1),
            "latest_released": self._find_latest(versions, released=True),
            "latest_in_stage": self._find_latest(versions, released=False),
        }

    @staticmethod
    def _find_latest(versions: dict, released: bool) -> str | None:
        """Find latest version matching release status."""
        matching = [
            v
            for v, data in versions.items()
            if (data["released_to_prod"] if released else not data["released_to_prod"]) and data["channel"] == "stable"
        ]
        if not matching:
            return None
        return max(matching, key=parse_patch_version)

    def get_latest_released_stable(self, minor: int) -> str | None:
        """Get latest stable version released to prod for a minor."""
        data = self.get_minor_data(minor)
        return data["latest_released"]

    def get_max_z(self, minor: int) -> int:
        """Get max z-stream value for a minor."""
        data = self.get_minor_data(minor)
        return data["max_z"]
