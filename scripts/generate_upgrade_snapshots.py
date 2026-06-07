"""Generate upgrade path and release checklist snapshots for all supported versions."""

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
from cnv_upgrade_utilities.version_types import format_minor_version
from utils.version_explorer import CnvVersionExplorer

LOGGER = logging.getLogger("generate_snapshots")


def probe_z_depths(explorer: CnvVersionExplorer) -> dict[str, int]:
    """Probe Version Explorer to find max z per supported version."""
    depths: dict[str, int] = {}
    total = len(SUPPORTED_VERSIONS)

    for i, version in enumerate(SUPPORTED_VERSIONS, 1):
        minor_version = format_minor_version(version)
        try:
            builds = explorer.get_released_builds(minor_version=minor_version, stage=True)
        except Exception:
            LOGGER.warning("[%d/%d] %s: probe failed", i, total, version)
            depths[version] = -1
            continue

        max_z = -1
        for build in builds:
            csv = build.csv_version.lstrip("v")
            parts = csv.split(".")
            if len(parts) >= 3:
                max_z = max(max_z, int(parts[2]))
        depths[version] = max_z
        LOGGER.info("[%d/%d] %s: max_z=%d", i, total, version, max_z)

    return depths


def generate_upgrade_paths(explorer: CnvVersionExplorer, z_depths: dict[str, int]) -> tuple[list[dict], list[dict]]:
    """Generate upgrade_jobs_info results for all valid upgrade path combinations."""
    results: list[dict] = []
    errors: list[dict] = []

    paths_to_test: list[tuple[str, str, str]] = []
    for version in SUPPORTED_VERSIONS:
        max_z = z_depths.get(version, -1)
        if max_z < 0:
            continue

        if max_z >= 1:
            paths_to_test.append((version, version, "z_stream"))
        if max_z >= 2:
            paths_to_test.append((f"{version}.0", version, "latest_z"))

        v = Version(version)
        source_y = f"{v.major}.{v.minor - 1}"
        if source_y in SUPPORTED_VERSIONS:
            paths_to_test.append((source_y, version, "y_stream"))

        if v.minor % 2 == 0:
            source_eus = f"{v.major}.{v.minor - 2}"
            if source_eus in SUPPORTED_VERSIONS:
                paths_to_test.append((source_eus, version, "eus"))

    total = len(paths_to_test)
    LOGGER.info("Testing %d upgrade paths...", total)

    for i, (source, target, expected_type) in enumerate(paths_to_test, 1):
        label = f"{source} -> {target} ({expected_type})"
        LOGGER.info("[%d/%d] %s", i, total, label)
        try:
            result = get_upgrade_jobs_info(explorer, source_version=source, target_version=target)
            results.append({"path": label, **result})
        except Exception as exc:
            LOGGER.warning("[%d/%d] %s: %s", i, total, label, exc)
            errors.append({"context": f"upgrade_jobs_info {label}", "error": str(exc)})

    return results, errors


def generate_release_checklists(
    explorer: CnvVersionExplorer, z_depths: dict[str, int]
) -> tuple[dict[str, dict], list[dict]]:
    """Generate release checklist results for all supported versions."""
    checklists: dict[str, dict] = {}
    errors: list[dict] = []

    versions_to_check = [(v, z) for v, z in z_depths.items() if z >= 0]
    total = len(versions_to_check)
    LOGGER.info("Generating release checklists for %d versions...", total)

    for i, (version, max_z) in enumerate(versions_to_check, 1):
        target = Version(f"{version}.{max_z}")
        label = str(target)
        LOGGER.info("[%d/%d] release_checklist: %s", i, total, label)
        try:
            result = get_upgrade_paths_info(explorer, target_version=target, skip_target_check=True)
            checklists[label] = result
        except Exception as exc:
            LOGGER.warning("[%d/%d] release_checklist %s: %s", i, total, label, exc)
            errors.append({"context": f"release_checklist {label}", "error": str(exc)})

    return checklists, errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate upgrade path and release checklist snapshots")
    parser.add_argument(
        "--output-dir", type=Path, default=Path("snapshots"), help="Output directory (default: snapshots/)"
    )
    parser.add_argument("--stdout", action="store_true", help="Write to stdout instead of file")
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

    LOGGER.info("Starting snapshot generation for %d supported versions", len(SUPPORTED_VERSIONS))

    with CnvVersionExplorer() as explorer:
        z_depths = probe_z_depths(explorer)

        if args.versions:
            z_depths = {v: z for v, z in z_depths.items() if v in requested}

        upgrade_results, upgrade_errors = generate_upgrade_paths(explorer, z_depths)
        checklists, checklist_errors = generate_release_checklists(explorer, z_depths)

    snapshot = {
        "generated_at": datetime.now(UTC).isoformat(),
        "supported_versions": SUPPORTED_VERSIONS,
        "z_depths": z_depths,
        "upgrade_paths": upgrade_results,
        "release_checklists": checklists,
        "errors": upgrade_errors + checklist_errors,
    }

    output = json.dumps(snapshot, indent=2, default=str)

    if args.stdout:
        sys.stdout.write(output + "\n")
    else:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now(UTC).strftime("%Y-%m-%d")
        output_path = args.output_dir / f"{date_str}.json"
        output_path.write_text(output + "\n")
        LOGGER.info("Snapshot written to %s", output_path)

    error_count = len(snapshot["errors"])
    if error_count:
        LOGGER.warning("%d errors during generation", error_count)
    LOGGER.info("Done: %d upgrade paths, %d checklists", len(upgrade_results), len(checklists))


if __name__ == "__main__":
    main()
