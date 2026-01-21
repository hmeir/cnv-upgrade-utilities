import json
import logging
from pathlib import Path

import click
from packaging.version import Version

from cnv_upgrade_utilities.release_checklist_upgrade_plan import get_upgrade_paths_info
from utils.version_explorer import CnvVersionExplorer

LOGGER = logging.getLogger(__name__)

# ============================================================================
# Version Configuration
# ============================================================================
SUPPORTED_MINORS = (12, 14, 16, 17, 18, 19, 20, 21)


def get_latest_target_version_for_minor(explorer: CnvVersionExplorer, minor: int) -> Version:
    """
    Get the latest target version (with errata) for a given minor version.

    Returns the latest build with errata, regardless of channel.

    Args:
        explorer: CnvVersionExplorer instance
        minor: Minor version number (e.g., 20 for 4.20)

    Returns:
        Version object representing the latest build with errata
    """
    minor_version = f"v4.{minor}"
    version_info = explorer.get_latest_build_with_errata_info(minor_version=minor_version)
    return Version(version_info["version"])


def generate_upgrade_plan_for_minor(explorer: CnvVersionExplorer, minor: int) -> dict:
    """
    Generate upgrade plan for a specific minor version.

    Args:
        explorer: CnvVersionExplorer instance
        minor: Minor version number (e.g., 20 for 4.20)

    Returns:
        Dictionary containing the upgrade plan for this minor version
    """
    target_version = get_latest_target_version_for_minor(explorer, minor)
    LOGGER.info(f"Generating upgrade plan for 4.{minor} -> target: {target_version}")

    return get_upgrade_paths_info(explorer, target_version)


def generate_all_upgrade_plans(explorer: CnvVersionExplorer, output_dir: Path) -> dict[str, dict]:
    """
    Generate upgrade plans for all supported versions.

    Args:
        explorer: CnvVersionExplorer instance
        output_dir: Directory to write JSON files to

    Returns:
        Dictionary mapping minor versions to their upgrade plans
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    all_plans = {}

    for minor in SUPPORTED_MINORS:
        try:
            plan = generate_upgrade_plan_for_minor(explorer, minor)
            version_key = f"4.{minor}"
            all_plans[version_key] = plan

            # Write individual JSON file for this version
            output_file = output_dir / f"upgrade_plan_{version_key.replace('.', '_')}.json"
            with open(output_file, "w") as f:
                json.dump(plan, f, indent=2, default=str)

            click.echo(f"Generated upgrade plan for {version_key}: {output_file}")

        except Exception as e:
            LOGGER.error(f"Failed to generate upgrade plan for 4.{minor}: {e}")
            click.echo(f"Error generating plan for 4.{minor}: {e}", err=True)

    return all_plans


@click.command(help="Generate upgrade plans for all supported CNV versions")
@click.option(
    "-o",
    "--output-dir",
    type=click.Path(path_type=Path),
    default=Path("./upgrade_plans"),
    help="Output directory for JSON files (default: ./upgrade_plans)",
)
@click.option("--summary/--no-summary", default=True, help="Also generate a combined summary file (default: enabled)")
def main(output_dir: Path, summary: bool):
    """Generate upgrade plans for all supported CNV versions."""
    with CnvVersionExplorer() as explorer:
        click.echo(f"Generating upgrade plans for supported versions: {', '.join(f'4.{m}' for m in SUPPORTED_MINORS)}")
        click.echo(f"Output directory: {output_dir.absolute()}")
        click.echo()

        all_plans = generate_all_upgrade_plans(explorer, output_dir)

        if summary and all_plans:
            summary_file = output_dir / "all_versions_summary.json"
            with open(summary_file, "w") as f:
                json.dump(all_plans, f, indent=2, default=str)
            click.echo(f"\nGenerated summary file: {summary_file}")

        click.echo(f"\nCompleted: {len(all_plans)}/{len(SUPPORTED_MINORS)} versions processed")


if __name__ == "__main__":
    main()
