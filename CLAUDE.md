# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CNV Upgrade Utilities is a CLI toolset and library for CNV (Container Native Virtualization) upgrade testing and release management. Resolves upgrade paths, fetches build information, and generates release checklists by querying the **Version Explorer API** (RH internal, VPN-only).

Used by: CNV QE team, devops team (via GitLab), and `openshift-virtualization-tests`.

## Architecture

### Package Structure

```
src/cnv_upgrade_utilities/
  release_checklist_upgrade_plan.py  # CLI: upgrade lanes for a target version
  upgrade_jobs_info.py               # CLI: source/target builds for upgrade jobs
  upgrade_types.py                   # UpgradeType enum, SUPPORTED_VERSIONS, EOL_VERSIONS
  version_types.py                   # Version parsing, formats, normalize_csv_version()
  post_upgrade_suites.py             # Post-upgrade test suite mapping
utils/
  version_explorer.py                # CnvVersionExplorer API client (cached, retries)
  build_helpers.py                   # Build resolution and extraction functions
  models.py                          # Pydantic models: ReleasedBuild, SuccessfulBuild, BuildInfo, BuildResult, ChannelInfo
  constants.py                       # CHANNEL_STABLE, CHANNEL_CANDIDATE, DEFAULT_VERSION_EXPLORER_URL
scripts/
  generate_current_testing_paths.py  # Generate upgrade-paths + release-checklist JSON/MD
tests/
  conftest.py                        # mock_explorer fixture, marker auto-deselect hook
  factories.py                       # Factory functions: make_channel_info, make_released_build, etc.
  e2e/
    conftest.py                      # E2E session fixtures: explorer, version_latest_z, path generation
    upgrade_jobs_info/               # E2E tests by version format (minor, full, bundle, mixed)
    release_checklist/               # E2E tests for release_checklist_upgrade_plan
    cli/                             # CLI subprocess error handling tests
    fbc/                             # FBC ground truth verification tests
    cross_validation/                # Cross-validation: FBC vs Version Explorer API
    utils/                           # Test helpers: assertions, expected_lanes, fbc_data, fbc_parser
```

### Import Dependency Graph

```
utils/constants.py (no project imports)
utils/models.py (no project imports)
cnv_upgrade_utilities/version_types.py (no project imports)
utils/version_explorer.py -> utils.constants, utils.models
utils/build_helpers.py -> utils.constants, utils.models, utils.version_explorer
cnv_upgrade_utilities/upgrade_types.py -> version_types
cnv_upgrade_utilities/post_upgrade_suites.py -> upgrade_types
cnv_upgrade_utilities/upgrade_jobs_info.py -> upgrade_types, version_types, utils.build_helpers, utils.constants, utils.models, utils.version_explorer
cnv_upgrade_utilities/release_checklist_upgrade_plan.py -> upgrade_types, version_types, utils.build_helpers, utils.constants, utils.models, utils.version_explorer, post_upgrade_suites
```

Never introduce circular imports. If module A imports from B, B must NOT import from A (directly or transitively).

### Key Abstractions

- **`UpgradeType`** enum — four types (Y_STREAM, Z_STREAM, LATEST_Z, EUS) with `.value`, `.display_name`, `.minor_offset` properties. `is_applicable_for_z()` determines if a type applies for a given target version.
- **Version formats** — MINOR (`4.20`), FULL (`4.20.3`), BUNDLE (`4.20.3.rhel9-31`). Parsed via `detect_version_format()`, individual components via `parse_major_version()`, `parse_minor_version()`, `parse_patch_version()`.
- **`CnvVersionExplorer`** — context manager API client. Three endpoints: `get_released_builds()`, `get_successful_builds_by_version()`, `get_build_info()`. Instance-level cache keyed on `(endpoint, query_string)`.
- **`BuildResult`** — standardized output from all `extract_*` functions. The common currency between internal resolution and CLI output.

## How the Code Flows

### Upgrade type determination
Source + target versions -> `determine_upgrade_type()` -> `UpgradeType`. Checks EOL first, then computes minor version diff. `is_latest_z_source()` detects the `X.Y.0` pattern for latest-z.

### Source resolution
Upgrade type's `minor_offset` -> minor version -> `find_released_source()` -> latest stable build released to prod. For latest-z (offset=None), source is always `X.Y.0`.

### Target resolution
Format-specific fetchers dispatched via `_SOURCE_FETCHERS` / `_TARGET_FETCHERS` dicts in `upgrade_jobs_info.py`. MINOR format uses `MinorTargetCandidates` + `_scan_released_builds()` with complex fallback logic. FULL format uses a 3-step fallback: stable-stage -> candidate-prod -> candidate-stage.

### Release checklist flow
Target version -> `get_applicable_upgrade_types()` based on z-value -> iterate types -> `fetch_source_version()` for each -> `get_post_upgrade_suite()` maps to test suite -> assembled into `upgrade_lanes` dict.

### Gating flow (jobs only)
`--gating` flag bypasses `determine_upgrade_type()`. `get_gating_jobs_info()` fetches `get_released_builds(stage=True)` and scans for candidate-prod (source) and candidate-stage (target). Not part of `UpgradeType` enum — it's a channel override, not a version-diff classification. Output uses `upgrade_type: "gating"`.

### Build extraction
API responses -> `extract_filtered_build_info()` (from SuccessfulBuild), `extract_released_build_info()` (from ReleasedBuild), `extract_from_build_info()` (from BuildInfo) -> all return `BuildResult`.

## Common Pitfalls

- **`csv_version` has `v` prefix, `cnv_build` does not.** Use `normalize_csv_version()` from `version_types.py` in test code. Production code handles this internally in the `extract_*` functions.
- **Bundle suffix stripping** — always use `strip_bundle_suffix()`, never ad-hoc `rsplit("-", 1)[0]`. The production function handles both `.rhel` and `-` suffixes.
- **Channel lifecycle** — `in_stage` and `released_to_prod` can both be `True` simultaneously. A build stays in stage after being released to prod.
- **`SKIP_Y_STREAM_UPGRADE_MINORS`** is computed at import time from `SUPPORTED_VERSIONS` and `EOL_VERSIONS`. No runtime recalculation.
- **`tests/e2e/utils/expected_lanes.py`** intentionally reimplements version logic independently for test verification. Do NOT refactor it to use production code — that defeats its purpose.
- **Factory functions** live in `tests/factories.py`, not `tests/conftest.py`. Use `CHANNEL_STABLE` and `TEST_IIB` constants for defaults.

## Version Management

```python
SUPPORTED_VERSIONS = ["4.12", "4.14", "4.16", "4.17", "4.18", "4.19", "4.20", "4.21", "4.22"]
EOL_VERSIONS = frozenset({"4.13", "4.15"})
```

**When updating versions**: modify `SUPPORTED_VERSIONS` and/or `EOL_VERSIONS` in `upgrade_types.py`. `SKIP_Y_STREAM_UPGRADE_MINORS` recomputes automatically. Then update: README.md supported versions table, this file's version lists.

## Development Workflow

```bash
uv sync --extra dev                          # Install dependencies
pre-commit run --all-files                   # Lint (ruff, flake8, mypy)
uv run pytest                                # Unit tests (offline)
uv run pytest -m e2e --log-cli-level=INFO    # E2E tests (VPN required)
uv run pytest -m "fbc and not e2e"           # FBC tests (public internet)
uv run tox                                   # Full check suite
```

## Workflow Rules

1. **After any code change**: `uv run pytest` — all unit tests must pass
2. **After e2e-related changes** (API client, build helpers, upgrade logic, test fixtures): `uv run pytest -m e2e --log-cli-level=INFO` if on VPN
3. **After changing SUPPORTED_VERSIONS, EOL_VERSIONS, upgrade types, CLI parameters, data models, or test structure**: update this file and README.md
4. **After adding new modules or functions**: update the Package Structure section above
5. **Before committing**: `pre-commit run --all-files`

## Code Style

- Line length: 120 characters
- Python 3.12+ required
- Uses ruff for linting/formatting with flake8 for additional checks
- Double quotes for strings
- No comments unless the WHY is non-obvious

## Documentation

- [Upgrade Strategy](docs/upgrade-strategy.md) — upgrade types, build phases, testing strategy
- [upgrade_jobs_info](docs/upgrade_jobs_info.md) — CLI reference, version formats, resolution strategies
- [release_checklist_upgrade_plan](docs/release_checklist_upgrade_plan.md) — CLI reference, resolution rules, post-upgrade suites
- [Testing](docs/testing.md) — test categories, markers, tox environments, FBC explanation
- [Contributing](docs/contributing.md) — setup, code style, PR requirements
- [Snapshot Generation](scripts/README.md) — `generate_current_testing_paths.py` usage
