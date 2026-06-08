"""Parser for cnv-fbc graph.yaml files to extract OLM channel data."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from cnv_upgrade_utilities.version_types import strip_bundle_suffix


def parse_fbc_graph(repo_path: str | Path, minor: int) -> dict[str, list[dict]]:
    """
    Parse graph.yaml for a minor version and return channel entries.

    Returns:
        Dict mapping channel name -> list of entries, each with:
        - name: operator version name (e.g., "kubevirt-hyperconverged-operator.v4.20.3")
        - version: extracted version string (e.g., "4.20.3")
        - replaces: what this version replaces (e.g., "kubevirt-hyperconverged-operator.v4.20.2")
        - replaces_version: extracted version from replaces (e.g., "4.20.2")
        - skip_range: skipRange string (e.g., ">=4.20.0 <4.20.3")
        - skips: list of skipped versions
    """
    graph_path = Path(repo_path) / f"v4.{minor}" / "graph.yaml"
    if not graph_path.exists():
        return {}

    with open(graph_path) as f:
        data = yaml.safe_load(f)

    channels: dict[str, list[dict]] = {}
    entries_list = data.get("entries", [])

    for entry in entries_list:
        if entry.get("schema") != "olm.channel":
            continue

        channel_name = entry.get("name", "")
        channel_entries = []

        for e in entry.get("entries", []):
            name = e.get("name", "")
            version = _extract_version(name)
            replaces = e.get("replaces", "")
            channel_entries.append(
                {
                    "name": name,
                    "version": version,
                    "replaces": replaces,
                    "replaces_version": _extract_version(replaces) if replaces else None,
                    "skip_range": e.get("skipRange", ""),
                    "skips": e.get("skips", []),
                }
            )

        channels[channel_name] = channel_entries

    return channels


def _extract_version(operator_name: str) -> str | None:
    """Extract version from operator name like 'kubevirt-hyperconverged-operator.v4.20.3'."""
    match = re.search(r"\.v?(\d+\.\d+\.\d+)$", operator_name)
    return match.group(1) if match else None


def get_fbc_versions_in_channel(repo_path: str | Path, minor: int, channel: str) -> list[str]:
    """Get all version strings present in a channel for a given minor."""
    channels = parse_fbc_graph(repo_path, minor)
    entries = channels.get(channel, [])
    return [e["version"] for e in entries if e["version"]]


def get_fbc_latest_version_in_channel(repo_path: str | Path, minor: int, channel: str) -> str | None:
    """Get the latest (last entry) version in a channel for a given minor."""
    versions = get_fbc_versions_in_channel(repo_path, minor, channel)
    return versions[-1] if versions else None


def parse_updated_image(repo_path: str | Path, minor: int) -> dict | None:
    """Parse updated_image.yaml to get the latest z-stream's current channel and build."""
    path = Path(repo_path) / f"v4.{minor}" / "updated_image.yaml"
    if not path.exists():
        return None
    with open(path) as f:
        data = yaml.safe_load(f)
    bundle_version = data.get("hco-bundle-version", "").lstrip("v")
    version = strip_bundle_suffix(bundle_version)
    return {
        "channel": data.get("channel"),
        "version": version,
        "bundle_version": bundle_version,
    }


def get_fbc_entry_by_version(repo_path: str | Path, minor: int, channel: str, version: str) -> dict | None:
    """Find a specific entry in a channel by version string."""
    channels = parse_fbc_graph(repo_path, minor)
    for entry in channels.get(channel, []):
        if entry["version"] == version:
            return entry
    return None
