# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CNV Upgrade Utilities is a CLI toolset and library for CNV (Container Native Virtualization) upgrade testing and release management. It resolves upgrade paths, fetches build information, and generates release checklists by querying the **Version Explorer API** (RH internal, VPN-only).

Used by: CNV QE team, devops team (via GitLab), and `openshift-virtualization-tests`.

## Package Structure

```
src/
  cnv_upgrade_utilities/
    release_checklist_upgrade_plan.py  # CLI: generate upgrade lanes for a target version
    upgrade_jobs_info.py               # CLI: resolve source/target builds for upgrade jobs
    upgrade_types.py                   # UpgradeType enum, SUPPORTED_VERSIONS, EOL_VERSIONS
    version_types.py                   # Version parsing, Click parameter types, VersionFormat enum
    post_upgrade_suites.py             # POST_UPGRADE_SUITE_MAP, get_post_upgrade_suite()
  utils/
    version_explorer.py                # CnvVersionExplorer API client (cached, retries)
    build_helpers.py                   # Build resolution: find_stable_stage_build, find_released_source
    models.py                          # Pydantic models: ReleasedBuild, SuccessfulBuild, BuildInfo, BuildResult, ChannelInfo
    constants.py                       # CHANNEL_STABLE, CHANNEL_CANDIDATE, DEFAULT_VERSION_EXPLORER_URL
scripts/
  generate_upgrade_snapshots.py        # Daily snapshot generation for all supported versions
tests/
  conftest.py                          # Unit test fixtures, mock_explorer, factory functions, marker auto-deselect hook
  e2e/conftest.py                      # E2E fixtures: session-scoped explorer, z-depth probing, path generation
```

## Key Components

### CnvVersionExplorer (`src/utils/version_explorer.py`)

API client for the Version Explorer service. Context manager with connection pooling, instance-level response caching, and retry logic via `TimeoutSampler`.

- `get_released_builds(minor_version, stage)` -> `list[ReleasedBuild]` — endpoint: `GetReleasedBuilds`
- `get_successful_builds_by_version(version, channel, stage, max_entries)` -> `list[SuccessfulBuild]` — endpoint: `GetSuccessfulBuildsByVersion`
- `get_build_info(bundle_version)` -> `BuildInfo` — endpoint: `GetBuildInfo`

Cache is keyed on `(endpoint, query_string)`, lives on the instance, cleared on `close()`. Only successful responses are cached (via `query_with_retry`, not `query`).

Requires `VERSION_EXPLORER_URL` env var (defaults to `http://cnv-version-explorer.apps.cnv2.engineering.redhat.com/`).

### UpgradeType (`src/cnv_upgrade_utilities/upgrade_types.py`)

Enum with four upgrade types:

| Type | Value | Display | Minor Offset | Rule |
|------|-------|---------|-------------|------|
| Y_STREAM | `y_stream` | `Y stream` | -1 | Y-1 must be supported (not EOL) |
| Z_STREAM | `z_stream` | `Z stream` | 0 | z >= 1 |
| LATEST_Z | `latest_z` | `latest z` | None | z >= 2 |
| EUS | `eus` | `EUS` | -2 | Both minors even, Y-2 supported |

Key functions:
- `determine_upgrade_type(source_version, target_version)` -> `UpgradeType`
- `get_applicable_upgrade_types(target_minor, target_z)` -> `list[UpgradeType]`
- `is_eol_version(version)` -> `bool`

### Version Handling (`src/cnv_upgrade_utilities/version_types.py`)

Three version formats (supports major 4 and 5):

| Format | Pattern | Example | Click Type |
|--------|---------|---------|-----------|
| MINOR | `X.Y` | `4.20` | `FLEXIBLE_VERSION_TYPE` |
| FULL | `X.Y.Z` | `4.20.2` | `FULL_VERSION_TYPE` / `FLEXIBLE_VERSION_TYPE` |
| BUNDLE | `X.Y.Z.rhelR-BN` | `4.20.3.rhel9-31` | `FLEXIBLE_VERSION_TYPE` |

Key functions: `detect_version_format()`, `parse_minor_version()`, `parse_patch_version()`, `parse_major_version()`, `format_minor_version()`, `strip_bundle_suffix()`, `is_latest_z_source()`.

### Data Models (`src/utils/models.py`)

All are Pydantic `BaseModel`:
- `ChannelInfo`: channel, iib, released_to_prod, in_stage, fbc_snapshot
- `ReleasedBuild`: csv_version, version, current_channel, channels, replaces, skip_range, build_timestamp
- `SuccessfulBuild`: cnv_build, iib, channel, released_to_prod, in_stage
- `BuildInfo`: cnv_version, current_channel, channels, error
- `BuildResult`: version, bundle_version, iib, channel, in_stage, released_to_prod

### Post-Upgrade Suites (`src/cnv_upgrade_utilities/post_upgrade_suites.py`)

`get_post_upgrade_suite(upgrade_type, z)` returns which test suite to run after an upgrade:

| Upgrade Type | z=0 | z=1 | z>=2 |
|-------------|-----|-----|------|
| Y_STREAM | UTS-FULL | UTS-FULL | UTS-Marker |
| Z_STREAM | - | UTS-Marker | NONE |
| EUS | UTS-Marker | - | - |
| LATEST_Z | - | - | NONE |

### Build Helpers (`src/utils/build_helpers.py`)

Channel checks: `channel_released_to_prod()`, `channel_in_stage()`, `channel_exists()`, `get_channel_info()`.

Build resolution: `find_stable_stage_build(explorer, version)`, `find_released_source(explorer, minor_version, ...)`.

Build extraction: `extract_filtered_build_info()`, `extract_released_build_info()`, `extract_from_build_info()`, `make_build_result()`.

## CLI Commands

### `release_checklist_upgrade_plan -v X.Y.Z [--skip-target-check]`

Entry point: `cnv_upgrade_utilities.release_checklist_upgrade_plan:main`

Core function: `get_upgrade_paths_info(explorer, target_version, skip_target_check)` -> dict with `target_version`, `target_build_info`, `upgrade_lanes`.

### `upgrade_jobs_info -s SOURCE -t TARGET`

Entry point: `cnv_upgrade_utilities.upgrade_jobs_info:main`

Core function: `get_upgrade_jobs_info(explorer, source_version, target_version)` -> dict with `upgrade_type`, `source`, `target`.

Uses format-specific fetchers dispatched via `_SOURCE_FETCHERS` and `_TARGET_FETCHERS` dicts. Complex target resolution for MINOR format uses `MinorTargetCandidates` and `_scan_released_builds()`.

## Version Support

```python
SUPPORTED_VERSIONS = ["4.12", "4.14", "4.16", "4.17", "4.18", "4.19", "4.20", "4.21", "4.22"]
EOL_VERSIONS = frozenset({"4.13", "4.15"})
```

`SKIP_Y_STREAM_UPGRADE_MINORS` is computed at import time — Y-stream is skipped when Y-1 is EOL or unsupported. EUS is skipped when Y-2 is unsupported.

**When updating versions**: modify `SUPPORTED_VERSIONS` and/or `EOL_VERSIONS` in `upgrade_types.py`. `SKIP_Y_STREAM_UPGRADE_MINORS` recomputes automatically. Then update the tables in this file and README.md.

## Development Commands

```bash
# Install dependencies
uv sync --extra dev

# Install as CLI tool
uv tool install .

# Lint and format
uv run ruff check src/ tests/ scripts/
uv run ruff format src/ tests/ scripts/
uv run flake8 src/ tests/ scripts/
uv run mypy

# Pre-commit (runs all linters)
pre-commit run --all-files

# CLI during development
uv run release_checklist_upgrade_plan -v 4.20.2
uv run upgrade_jobs_info -s 4.19 -t 4.20
```

## Running Tests

```bash
# Unit tests (offline, no network)
uv run pytest

# E2E tests (requires VERSION_EXPLORER_URL / VPN)
uv run pytest -m e2e --log-cli-level=INFO

# FBC tests (requires public internet for GitHub clone)
uv run pytest -m "fbc and not e2e" --log-cli-level=INFO

# Cross-validation (requires both API and FBC)
uv run pytest -m "e2e and fbc" --log-cli-level=INFO

# Everything
uv run pytest -m "e2e or fbc" --log-cli-level=INFO
```

E2E/FBC tests are auto-deselected by default (via `pytest_collection_modifyitems` hook in `tests/conftest.py`). Pass `-m e2e` or `-m fbc` to include them. No `-o "addopts="` override needed.

## Test Architecture

**Unit tests** (`tests/test_*.py`): fully mocked via `mock_explorer` fixture (auto-specced `CnvVersionExplorer`). Factory functions: `make_channel_info()`, `make_released_build()`, `make_successful_build()`, `make_build_info()`.

**E2E tests** (`tests/e2e/test_upgrade_paths.py`, `test_release_checklist_e2e.py`): hit live Version Explorer API. Session-scoped `explorer` fixture. Z-depth probing via `_probe_version_z_depth()` cached in module-level dict. Dynamic test path generation from API data.

**FBC tests** (`tests/e2e/test_fbc_upgrade_paths.py`): validate against cnv-fbc GitHub repo (file-based catalog). No API needed.

**FBC verification** (`tests/e2e/test_fbc_verification.py`): detect data drift between Version Explorer API and FBC (stale stage flags, replaces/skipRange mismatches). Marked with both `e2e` and `fbc`.

**Cross-validation** (`tests/e2e/test_cross_validation.py`): compare FBC vs API data. Marked with both `e2e` and `fbc`.

**Markers**: `e2e` (needs API), `fbc` (needs cnv-fbc repo). Configured in `pyproject.toml`.

**Logging**: E2E tests use `logging.getLogger("cnv_e2e")` with `[N/M]` progress counters. Visible with `--log-cli-level=INFO`.

## Tox Environments

| Environment | Description | Network Required |
|------------|-------------|-----------------|
| `lint` | ruff check/format, flake8, mypy | No |
| `py312` | Unit tests + coverage (Python 3.12) | No |
| `py314` | Unit tests + coverage (Python 3.14) | No |
| `security` | bandit, pip-audit | No |
| `fbc` | FBC ground truth verification | Public internet |
| `e2e` | E2E tests against Version Explorer API | VPN (RH network) |
| `generate` | Snapshot generation | VPN (RH network) |
| `coverage` | Coverage report, 80% threshold | No (depends on py312, py314) |

Default envlist: `lint, py312, py314, security, fbc, coverage` (no e2e or generate).

## CI/CD

**GitHub Actions:**
- `pr.yml` — on PRs: lint, unit tests, security, FBC
- `main.yml` — on push to main: same as PR
- `daily.yml` — daily at 06:17 UTC + manual dispatch: FBC verification

**E2E, cross-validation, and snapshot generation cannot run on GitHub Actions** — the Version Explorer API is VPN-only. Run locally with `uv run tox -e e2e` or `uv run tox -e generate`.

## Snapshot Generation

```bash
# Generate snapshot for all versions (output to snapshots/)
uv run python scripts/generate_upgrade_snapshots.py

# Output to stdout
uv run python scripts/generate_upgrade_snapshots.py --stdout

# Subset of versions
uv run python scripts/generate_upgrade_snapshots.py --versions 4.20,4.21

# Via tox
uv run tox -e generate
```

Output JSON includes: `generated_at`, `supported_versions`, `z_depths`, `upgrade_paths`, `release_checklists`, `errors`.

## Code Style

- Line length: 120 characters
- Python 3.12+ required
- Uses ruff for linting/formatting with flake8 for additional checks
- Double quotes for strings
- No comments unless the WHY is non-obvious

## Import Safety

Before adding any new cross-module import, trace the full dependency chain. The import graph is:

```
constants.py (no project imports)
models.py (no project imports)
version_types.py (no project imports)
version_explorer.py -> constants, models
build_helpers.py -> constants, models, version_explorer
upgrade_types.py -> version_types
post_upgrade_suites.py -> upgrade_types
upgrade_jobs_info.py -> upgrade_types, version_types, build_helpers, constants, models, version_explorer
release_checklist_upgrade_plan.py -> upgrade_types, version_types, build_helpers, constants, models, version_explorer, post_upgrade_suites
```

Never introduce circular imports. If module A imports from B, B must NOT import from A (directly or transitively).

## Workflow Rules

After making changes to this repo, follow these steps:

1. **After any code change**: run `uv run pytest` — all unit tests must pass
2. **After e2e-related changes** (API client, build helpers, upgrade logic, test fixtures): run `uv run pytest -m e2e --log-cli-level=INFO` if on VPN
3. **After changing SUPPORTED_VERSIONS, EOL_VERSIONS, upgrade types, CLI parameters, data models, or test structure**: update this file (CLAUDE.md) and README.md to reflect the change
4. **After adding new modules or functions**: add them to the Package Structure section above
5. **Before committing**: run `pre-commit run --all-files`
