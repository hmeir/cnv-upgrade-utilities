"""Generate current testing paths for upgrade_jobs_info and release_checklist_upgrade_plan."""

import argparse
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

from packaging.version import Version

from cnv_upgrade_utilities.release_checklist_upgrade_plan import get_upgrade_paths_info
from cnv_upgrade_utilities.upgrade_jobs_info import get_upgrade_jobs_info
from cnv_upgrade_utilities.upgrade_types import SUPPORTED_VERSIONS
from cnv_upgrade_utilities.version_types import format_minor_version, normalize_csv_version, parse_patch_version
from utils.version_explorer import CnvVersionExplorer

LOGGER = logging.getLogger("generate_current_testing_paths")


def probe_latest_z(explorer: CnvVersionExplorer) -> dict[str, int]:
    """Probe Version Explorer to find the highest z-stream release per supported version."""
    latest_z: dict[str, int] = {}
    total = len(SUPPORTED_VERSIONS)

    for i, version in enumerate(SUPPORTED_VERSIONS, 1):
        minor_version = format_minor_version(version)
        try:
            builds = explorer.get_released_builds(minor_version=minor_version, stage=True)
        except Exception:
            LOGGER.warning("[%d/%d] %s: probe failed", i, total, version)
            latest_z[version] = -1
            continue

        max_z = -1
        for build in builds:
            patch = parse_patch_version(normalize_csv_version(build.csv_version))
            if patch is not None:
                max_z = max(max_z, patch)
        latest_z[version] = max_z
        LOGGER.info("[%d/%d] %s: latest_z=%d", i, total, version, max_z)

    return latest_z


def _build_upgrade_paths_for_version(version: str, max_z: int) -> list[tuple[str, str, str]]:
    """Build the list of (source, target, upgrade_type) for a single version."""
    paths: list[tuple[str, str, str]] = []
    if max_z >= 1:
        paths.append((version, version, "z_stream"))
    if max_z >= 2:
        paths.append((f"{version}.0", version, "latest_z"))

    v = Version(version)
    source_y = f"{v.major}.{v.minor - 1}"
    if source_y in SUPPORTED_VERSIONS:
        paths.append((source_y, version, "y_stream"))

    if v.minor % 2 == 0:
        source_eus = f"{v.major}.{v.minor - 2}"
        if source_eus in SUPPORTED_VERSIONS:
            paths.append((source_eus, version, "eus"))

    return paths


def generate_upgrade_paths(
    explorer: CnvVersionExplorer, latest_z: dict[str, int]
) -> tuple[dict[str, dict], list[dict]]:
    """Generate version-keyed upgrade_jobs_info results."""
    versions: dict[str, dict] = {}
    errors: list[dict] = []

    all_paths: list[tuple[str, str, str, str]] = []
    for version in SUPPORTED_VERSIONS:
        max_z = latest_z.get(version, -1)
        if max_z < 0:
            continue
        for source, target, upgrade_type in _build_upgrade_paths_for_version(version, max_z):
            all_paths.append((version, source, target, upgrade_type))

    total = len(all_paths)
    LOGGER.info("Testing %d upgrade paths...", total)

    for i, (version, source, target, upgrade_type) in enumerate(all_paths, 1):
        label = f"{source} -> {target} ({upgrade_type})"
        LOGGER.info("[%d/%d] %s", i, total, label)
        try:
            result = get_upgrade_jobs_info(explorer, source_version=source, target_version=target)
            if version not in versions:
                versions[version] = {"latest_z": latest_z[version], "upgrade_paths": {}}
            versions[version]["upgrade_paths"][upgrade_type] = {
                "source": result["source"],
                "target": result["target"],
            }
        except Exception as exc:
            LOGGER.warning("[%d/%d] %s: %s", i, total, label, exc)
            errors.append({"context": f"upgrade_jobs_info {label}", "error": str(exc)})

    return versions, errors


def generate_release_checklists(
    explorer: CnvVersionExplorer, latest_z: dict[str, int]
) -> tuple[dict[str, dict], list[dict]]:
    """Generate version-keyed release checklist results."""
    versions: dict[str, dict] = {}
    errors: list[dict] = []

    versions_to_check = [(v, z) for v, z in latest_z.items() if z >= 0]
    total = len(versions_to_check)
    LOGGER.info("Generating release checklists for %d versions...", total)

    for i, (version, max_z) in enumerate(versions_to_check, 1):
        target = Version(f"{version}.{max_z}")
        label = str(target)
        LOGGER.info("[%d/%d] release_checklist: %s", i, total, label)
        try:
            result = get_upgrade_paths_info(explorer, target_version=target, skip_target_check=True)
            versions[version] = result
        except Exception as exc:
            LOGGER.warning("[%d/%d] release_checklist %s: %s", i, total, label, exc)
            errors.append({"context": f"release_checklist {label}", "error": str(exc)})

    return versions, errors


def _format_upgrade_paths_md(generated_at: str, versions: dict[str, dict], latest_z: dict[str, int]) -> str:
    """Generate the upgrade-paths.md content."""
    total_paths = sum(len(v.get("upgrade_paths", {})) for v in versions.values())
    lines = [
        "# Upgrade Paths",
        "",
        f"Generated: {generated_at} | Versions: {len(versions)} | Paths: {total_paths}",
        "",
    ]

    for version in sorted(versions.keys(), key=Version):
        data = versions[version]
        max_z = data.get("latest_z", latest_z.get(version, -1))
        paths = data.get("upgrade_paths", {})

        lines.append(f"## {version} (latest z: {max_z})")
        lines.append("")

        if not paths:
            lines.append("No upgrade paths (latest_z < 1).")
            lines.append("")
            continue

        lines.append("| Type | Source | Target | Channel |")
        lines.append("|------|--------|--------|---------|")
        for upgrade_type, path_data in paths.items():
            source_ver = path_data["source"]["version"]
            target_ver = path_data["target"]["version"]
            channel = path_data["target"].get("channel", "")
            lines.append(f"| {upgrade_type} | {source_ver} | {target_ver} | {channel} |")
        lines.append("")

    return "\n".join(lines)


def _format_release_checklist_md(generated_at: str, versions: dict[str, dict]) -> str:
    """Generate the release-checklist.md content."""
    lines = [
        "# Release Checklist",
        "",
        f"Generated: {generated_at} | Versions: {len(versions)}",
        "",
    ]

    for version in sorted(versions.keys(), key=Version):
        data = versions[version]
        target_ver = data["target_version"]
        target_build = data["target_build_info"]
        lanes = data.get("upgrade_lanes", {})

        bundle = target_build.get("bundle_version", "")
        channel = target_build.get("channel", "")
        in_stage = target_build.get("in_stage", False)
        released = target_build.get("released_to_prod", False)

        stage_str = "**in stage**" if in_stage else "not in stage"
        prod_str = "**released to prod**" if released else "not released to prod"

        lines.append(f"## {version} -> {target_ver}")
        lines.append("")
        lines.append(f"**Target**: {target_ver} ({bundle}) | channel: {channel} | {stage_str} | {prod_str}")
        lines.append("")

        if lanes:
            lines.append("| Lane | Source | IIB | Channel | Post-Upgrade Suite |")
            lines.append("|------|--------|-----|---------|-------------------|")
            for lane_name, lane_data in lanes.items():
                source = lane_data.get("source_version", "")
                iib = lane_data.get("iib", "")
                if "iib:" in iib:
                    iib = "iib:" + iib.split("iib:")[-1]
                ch = lane_data.get("channel", "")
                suite = lane_data.get("post_upgrade_suite", "")
                lines.append(f"| {lane_name} | {source} | {iib} | {ch} | {suite} |")
            lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate current testing paths for upgrade and release checklist")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("current_testing_paths"),
        help="Output directory (default: current_testing_paths/)",
    )
    parser.add_argument("--stdout", action="store_true", help="Write JSON to stdout instead of files")
    parser.add_argument(
        "--versions", type=str, default=None, help="Comma-separated subset of versions to process (default: all)"
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s", datefmt="%H:%M:%S")

    if args.versions:
        requested = [v.strip() for v in args.versions.split(",")]
        invalid = [v for v in requested if v not in SUPPORTED_VERSIONS]
        if invalid:
            parser.error(f"Unknown versions: {', '.join(invalid)}. Valid: {', '.join(SUPPORTED_VERSIONS)}")

    LOGGER.info("Starting generation for %d supported versions", len(SUPPORTED_VERSIONS))

    with CnvVersionExplorer() as explorer:
        latest_z = probe_latest_z(explorer)

        if args.versions:
            latest_z = {v: z for v, z in latest_z.items() if v in requested}

        upgrade_versions, upgrade_errors = generate_upgrade_paths(explorer, latest_z)
        checklist_versions, checklist_errors = generate_release_checklists(explorer, latest_z)

    generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    upgrade_paths_json = {
        "generated_at": generated_at,
        "supported_versions": SUPPORTED_VERSIONS,
        "latest_z": latest_z,
        "versions": upgrade_versions,
        "errors": upgrade_errors,
    }

    release_checklist_json = {
        "generated_at": generated_at,
        "supported_versions": SUPPORTED_VERSIONS,
        "versions": checklist_versions,
        "errors": checklist_errors,
    }

    if args.stdout:
        sys.stdout.write("=== upgrade-paths.json ===\n")
        sys.stdout.write(json.dumps(upgrade_paths_json, indent=2, default=str) + "\n")
        sys.stdout.write("\n=== release-checklist.json ===\n")
        sys.stdout.write(json.dumps(release_checklist_json, indent=2, default=str) + "\n")
    else:
        args.output_dir.mkdir(parents=True, exist_ok=True)

        upgrade_json_path = args.output_dir / "upgrade-paths.json"
        upgrade_json_path.write_text(json.dumps(upgrade_paths_json, indent=2, default=str) + "\n")

        checklist_json_path = args.output_dir / "release-checklist.json"
        checklist_json_path.write_text(json.dumps(release_checklist_json, indent=2, default=str) + "\n")

        upgrade_md_path = args.output_dir / "upgrade-paths.md"
        upgrade_md_path.write_text(_format_upgrade_paths_md(generated_at, upgrade_versions, latest_z) + "\n")

        checklist_md_path = args.output_dir / "release-checklist.md"
        checklist_md_path.write_text(_format_release_checklist_md(generated_at, checklist_versions) + "\n")

        LOGGER.info(
            "Written to %s: upgrade-paths.json, upgrade-paths.md, release-checklist.json, release-checklist.md",
            args.output_dir,
        )

    total_errors = len(upgrade_errors) + len(checklist_errors)
    if total_errors:
        LOGGER.warning("%d errors during generation", total_errors)
    total_paths = sum(len(v.get("upgrade_paths", {})) for v in upgrade_versions.values())
    LOGGER.info("Done: %d upgrade paths, %d checklists", total_paths, len(checklist_versions))


if __name__ == "__main__":
    main()
