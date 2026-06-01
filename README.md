# CNV Upgrade Utilities

[![CI](https://github.com/hmeir/cnv-upgrade-utilities/actions/workflows/ci.yml/badge.svg)](https://github.com/hmeir/cnv-upgrade-utilities/actions/workflows/ci.yml)

CLI tools for CNV (Container Native Virtualization) upgrade testing and release management.

## Prerequisites

- Python >= 3.12
- Access to the Version Explorer API

## Installation

This project uses `uv` for dependency management.

### Install as a CLI tool (Recommended)

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

### Running Tests

```bash
uv run pytest
```

### Linting, Formatting, and Type Checking

```bash
uv run ruff check src/ tests/
uv run ruff format src/ tests/
uv run mypy
```

## Configuration

Set the `VERSION_EXPLORER_URL` environment variable before using any tool:

```bash
export VERSION_EXPLORER_URL="http://<your-version-explorer-host>"
```

## Key Terms

| Term | Description | Example |
|------|-------------|---------|
| **Y Stream** | Upgrade from the previous minor version | 4.19 -> 4.20 |
| **Z Stream** | Upgrade within the same minor version | 4.20.1 -> 4.20.2 |
| **Latest Z** | Upgrade from the initial release (4.Y.0) to the latest z | 4.20.0 -> 4.20.5 |
| **EUS** | Extended Update Support, skipping one minor version (both must be even) | 4.18 -> 4.20 |
| **UTS-FULL** | Full post-upgrade test suite |  |
| **UTS-Marker** | Reduced post-upgrade test suite (marker-based) |  |

## Tools

### Release Checklist Generator

**Command:** `release_checklist_upgrade_plan`

Generates upgrade lanes for a CNV release checklist. Given a target version, it determines all applicable upgrade paths with their source versions and post-upgrade test suites.

#### Parameters

| Parameter | Format | Required | Description |
|-----------|--------|----------|-------------|
| `-v, --target-version` | `4.Y.Z` | Yes | Target version (e.g., `4.20.2`) |
| `--skip-target-check` | flag | No | Accept target builds already released to prod |

#### Upgrade Rules

The tool determines which upgrade lanes apply based on the target version's Z component:

**Major Release (Z = 0)**

| Upgrade Type | Source | Post-Upgrade Suite | Condition |
|---|---|---|---|
| Y Stream | Latest `4.(Y-1).z` | UTS-FULL | Always |
| EUS | Latest `4.(Y-2).z` | UTS-Marker | Only if Y is even |

**First Maintenance (Z = 1)**

| Upgrade Type | Source | Post-Upgrade Suite |
|---|---|---|
| Y Stream | Latest `4.(Y-1).z` | UTS-FULL |
| Z Stream | Latest `4.Y.z` (typically `4.Y.0`) | UTS-Marker |

**Subsequent Maintenance (Z >= 2)**

| Upgrade Type | Source | Post-Upgrade Suite |
|---|---|---|
| Y Stream | Latest `4.(Y-1).z` | UTS-Marker |
| Z Stream | Latest `4.Y.z` | NONE |
| Latest Z | `4.Y.0` | NONE |

#### Target Resolution

The target must be in stable stage and **not yet released to prod**. If the target build hasn't reached stable stage yet (or is already released), the tool fails with a clear error message. Use `--skip-target-check` to bypass this validation and generate the upgrade paths regardless of the target's channel status.

#### Source Resolution

Each source is resolved as the latest stable build released to prod for the corresponding minor version.

#### Usage

```bash
# Generate checklist for a target version
release_checklist_upgrade_plan -v 4.20.2

# Skip target channel validation (e.g., target not yet in stable stage)
release_checklist_upgrade_plan -v 4.16.33 --skip-target-check
```

#### Example Output

```json
{
  "target_version": "4.20.2",
  "target_build_info": {
    "version": "4.20.2",
    "bundle_version": "4.20.2.rhel9-5",
    "iib": "registry-proxy.engineering.redhat.com/rh-osbs/iib:1091512",
    "channel": "stable"
  },
  "upgrade_lanes": {
    "Y stream": {
      "source_version": "4.19.15",
      "bundle_version": "4.19.15.rhel9-18",
      "iib": "registry-proxy.engineering.redhat.com/rh-osbs/iib:1079024",
      "channel": "stable",
      "post_upgrade_suite": "UTS-Marker"
    },
    "Z stream": {
      "source_version": "4.20.1",
      "bundle_version": "4.20.1.rhel9-13",
      "iib": "registry-proxy.engineering.redhat.com/rh-osbs/iib:1073045",
      "channel": "stable",
      "post_upgrade_suite": "NONE"
    },
    "latest z": {
      "source_version": "4.20.0",
      "bundle_version": "4.20.0.rhel9-234",
      "iib": "registry-proxy.engineering.redhat.com/rh-osbs/iib:1063267",
      "channel": "stable",
      "post_upgrade_suite": "NONE"
    }
  }
}
```

---

### Upgrade Jobs Info

**Command:** `upgrade_jobs_info`

Resolves source and target build information for upgrade job execution. Automatically detects the upgrade type and fetches the appropriate builds.

#### Parameters

| Parameter | Format | Required | Description |
|-----------|--------|----------|-------------|
| `-s, --source-version` | `4.Y`, `4.Y.Z`, or `4.Y.Z.rhelR-BN` | Yes | Source version |
| `-t, --target-version` | `4.Y`, `4.Y.Z`, or `4.Y.Z.rhelR-BN` | Yes | Target version |

#### Version Formats

Both source and target accept three levels of specificity:

| Format | Pattern | Description |
|--------|---------|-------------|
| **Minor** | `4.Y` | Auto-resolves to the best available build for the minor version |
| **Full** | `4.Y.Z` | Resolves to a specific X.Y.Z version |
| **Bundle** | `4.Y.Z.rhelR-BN` | Exact build lookup (e.g., `4.20.3.rhel9-31`) |

#### Upgrade Type Detection

The upgrade type is automatically determined from the source and target versions:

| Source | Target | Upgrade Type |
|--------|--------|--------------|
| `4.Y` | `4.Y` | Z-stream |
| `4.Y` | `4.(Y+1)` | Y-stream |
| `4.Y.0` | `4.Y` | Latest-Z |
| `4.Y` | `4.(Y+2)` | EUS (both must be even) |

#### Validation

The tool rejects invalid upgrade scenarios:

| Scenario | Example | Error |
|----------|---------|-------|
| Same version | `4.20.5 -> 4.20.5` | Cannot upgrade to the same version |
| Z-stream downgrade | `4.20.5 -> 4.20.4` | Cannot downgrade within z-stream |
| Y-stream downgrade | `4.21 -> 4.20` | Cannot downgrade |
| Version gap > 2 | `4.18 -> 4.21` | Unsupported upgrade |
| EUS with odd versions | `4.19 -> 4.21` | EUS requires both versions to be even |
| Latest-Z cross-minor | `4.19.0 -> 4.20` | Latest-Z requires same minor version |

**Note:** `4.20 -> 4.20` (minor format) is a valid Z-stream lookup. Only exact same full versions (e.g., `4.20.5 -> 4.20.5`) are rejected.

#### Usage

```bash
# Z-stream (auto-detect latest versions)
upgrade_jobs_info -s 4.20 -t 4.20

# Y-stream
upgrade_jobs_info -s 4.19 -t 4.20

# EUS
upgrade_jobs_info -s 4.18 -t 4.20

# Latest-Z
upgrade_jobs_info -s 4.20.0 -t 4.20

# Specific versions
upgrade_jobs_info -s 4.19.15 -t 4.20.1

# Specific bundle versions
upgrade_jobs_info -s 4.20.3.rhel9-31 -t 4.20.5.rhel9-3

# Mix formats
upgrade_jobs_info -s 4.20.0 -t 4.20
```

#### Example Output

```bash
upgrade_jobs_info -s 4.20 -t 4.20
```

```json
{
  "upgrade_type": "z_stream",
  "source": {
    "version": "4.20.3",
    "bundle_version": "4.20.3.rhel9-31",
    "iib": "registry-proxy.engineering.redhat.com/rh-osbs/iib:1084676",
    "channel": "stable"
  },
  "target": {
    "version": "4.20.5",
    "bundle_version": "4.20.5.rhel9-3",
    "iib": "registry-proxy.engineering.redhat.com/rh-osbs/iib:1091512",
    "channel": "stable"
  }
}
```

## Contributing

Contributions are welcome! Before submitting a PR:

1. Install dev dependencies: `uv sync --extra dev`
2. Install pre-commit hooks: `uv run pre-commit install`
3. Run tests: `uv run pytest`
4. Run linting: `uv run ruff check src/ tests/`
5. Run type checking: `uv run mypy`

Pre-commit hooks automatically enforce code style (ruff), linting (flake8), and type checking (mypy) on every commit.
