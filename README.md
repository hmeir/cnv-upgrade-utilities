# CNV Upgrade Utilities

[![Main](https://github.com/hmeir/cnv-upgrade-utilities/actions/workflows/main.yml/badge.svg)](https://github.com/hmeir/cnv-upgrade-utilities/actions/workflows/main.yml)

CLI tools and library for CNV (Container Native Virtualization) upgrade testing and release management. Resolves upgrade paths, fetches build information, and generates release checklists by querying the Version Explorer API.

Used by: CNV QE team, devops team (via GitLab), and `openshift-virtualization-tests`.

## Prerequisites

- Python >= 3.12
- [uv](https://docs.astral.sh/uv/) for dependency management
- Access to the Version Explorer API (RH network / VPN) for E2E tests and snapshot generation

## Installation

### As a CLI tool (Recommended)

```bash
git clone https://github.com/hmeir/cnv-upgrade-utilities.git
cd cnv-upgrade-utilities
uv tool install .
```

This makes the following commands available globally:
- `release_checklist_upgrade_plan`
- `upgrade_jobs_info`

### Development installation

```bash
git clone https://github.com/hmeir/cnv-upgrade-utilities.git
cd cnv-upgrade-utilities
uv sync --extra dev
```

## Configuration

| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `VERSION_EXPLORER_URL` | Version Explorer API base URL | Internal RH instance |

## Supported Versions

| Supported | EOL (not tested) |
|---|---|
| 4.12, 4.14, 4.16, 4.17, 4.18, 4.19, 4.20, 4.21, 4.22 | 4.13, 4.15 |

See [Upgrade Strategy](docs/upgrade-strategy.md) for how versions, upgrade types, and testing strategy work together.

## Tools

### Release Checklist Generator

Generates upgrade lanes for a CNV release checklist. Given a target version, determines all applicable upgrade paths with their source versions and post-upgrade test suites.

```bash
release_checklist_upgrade_plan -v 4.20.2
release_checklist_upgrade_plan -v 4.16.33 --skip-target-check
```

See [release_checklist_upgrade_plan reference](docs/release_checklist_upgrade_plan.md).

### Upgrade Jobs Info

Resolves source and target build information for upgrade job execution. Accepts minor (`4.20`), full (`4.20.3`), or bundle (`4.20.3.rhel9-31`) version formats.

```bash
upgrade_jobs_info -s 4.19 -t 4.20          # Y-stream
upgrade_jobs_info -s 4.20 -t 4.20          # Z-stream
upgrade_jobs_info -s 4.18 -t 4.20          # EUS
upgrade_jobs_info -s 4.20.0 -t 4.20        # Latest-Z
```

See [upgrade_jobs_info reference](docs/upgrade_jobs_info.md).

### Snapshot Generation

Generates upgrade path and release checklist data for every supported version. See [scripts/README.md](scripts/README.md).

## Running Tests

```bash
uv run pytest                                # Unit tests (offline)
uv run pytest -m e2e --log-cli-level=INFO    # E2E tests (VPN)
uv run tox                                   # Full check suite
```

See [Testing](docs/testing.md) for test categories, markers, and tox environments.

## Documentation

- [Upgrade Strategy](docs/upgrade-strategy.md) -- upgrade types, build phases, testing strategy
- [upgrade_jobs_info](docs/upgrade_jobs_info.md) -- CLI reference, version formats, resolution strategies
- [release_checklist_upgrade_plan](docs/release_checklist_upgrade_plan.md) -- CLI reference, resolution rules, post-upgrade suites
- [Testing](docs/testing.md) -- test categories, markers, tox environments, FBC explanation
- [Contributing](docs/contributing.md) -- setup, code style, PR requirements
- [Snapshot Generation](scripts/README.md) -- `generate_current_testing_paths.py` usage
