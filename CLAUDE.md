# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CNV Upgrade Utilities is a CLI toolset for CNV (Container Native Virtualization) upgrade testing and release management. It provides three main commands for generating upgrade paths, build information, and batch upgrade plans.

## Development Commands

```bash
# Install dependencies
uv sync

# Install as CLI tool
uv tool install .

# Run linting and formatting (via pre-commit)
pre-commit run --all-files

# Run individual linters
uv run ruff check src/
uv run ruff format src/
uv run flake8 src/

# Run a CLI command during development
uv run release_checklist_upgrade_plan -v 4.20.2
uv run upgrade_jobs_info -s 4.19 -t 4.20
```

## Environment Configuration

The tools require `VERSION_EXPLORER_URL` environment variable to be set for API access.

## Architecture

### Package Structure

- `src/cnv_upgrade_utilities/` - Main CLI commands
- `src/utils/` - Shared utilities and API client

### Key Components

**CnvVersionExplorer** (`src/utils/version_explorer.py`): API client for Version Explorer service. Provides methods to query build information, upgrade paths, and release data. Used as context manager with retry logic and connection pooling.

**UpgradeType** (`src/cnv_upgrade_utilities/upgrade_types.py`): Enum defining four upgrade types with their version calculation logic:
- Y_STREAM: minor version +1 (e.g., 4.19 → 4.20), only if Y-1 is supported
- Z_STREAM: same minor, different patch (e.g., 4.20.1 → 4.20.2)
- LATEST_Z: from X.Y.0 to latest X.Y.z
- EUS: minor version +2, both must be even, only if Y-2 is supported

**Post-Upgrade Suite Logic**: The `POST_UPGRADE_SUITE_MAP` in `post_upgrade_suites.py` defines test suite requirements (UTS-FULL, UTS-Marker, NONE) based on upgrade type and z-stream category.

### CLI Commands

1. **release_checklist_upgrade_plan**: Generates upgrade lanes for a target version (format: X.Y.z)
2. **upgrade_jobs_info**: Returns source/target build details for job execution (source: X.Y or X.Y.0, target: X.Y)

### Version Handling

Version formats are validated via Click parameter types (support major 4 and 5):
- `FULL_VERSION_TYPE`: X.Y.z format
- `FLEXIBLE_VERSION_TYPE`: X.Y, X.Y.Z, or X.Y.Z.rhelR-BN format

### Version Support

`SUPPORTED_VERSIONS` lists actively supported versions. `EOL_VERSIONS` lists end-of-life versions (e.g., 4.13, 4.15).

`SKIP_Y_STREAM_UPGRADE_MINORS` is computed from these — Y-stream is skipped when Y-1 is EOL or unsupported. EUS is skipped when Y-2 is unsupported.

## Code Style

- Line length: 120 characters
- Python 3.12+ required
- Uses ruff for linting/formatting with flake8 for additional checks
- Double quotes for strings
