# CNV Upgrade Utilities

This repository contains a collection of utilities designed to assist with CNV (Container Native Virtualization) upgrade testing, release management, and automation.

## Prerequisites

- Python >= 3.12
- Access to the Version Explorer API (for relevant tools).

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
- `all_versions_upgrade_plan`

### Development installation

```bash
git clone https://github.com/hmeir/cnv-upgrade-utilities.git
cd cnv-upgrade-utilities
uv sync --extra dev
```

### Linting and Formatting

```bash
# Run linter
uv run ruff check src/ tests/

# Run formatter
uv run ruff format src/ tests/
```

## Configuration

For tools interacting with the Version Explorer, you must set the `VERSION_EXPLORER_URL` environment variable.

```bash
export VERSION_EXPLORER_URL="http://<your-version-explorer-host>"
```

# Tools & Features

## Upgrade Release Checklist Generator

**Command:** `release_checklist_upgrade_plan`

- The target channel must be "stable"!

This tool automates the generation of upgrade paths (lanes) for CNV release checklists. It determines the appropriate source versions and post-upgrade test suites based on the target release version and defined upgrade rules.

The checklist tool categorizes the target version (`4.Y.z`) into three main buckets based on the Z-stream component.

### 1. Major Release (Z = 0)

*Target Pattern: `4.Y.0*`


| Upgrade Type | Source Version     | Post-Upgrade Suite | Condition           |
| ------------ | ------------------ | ------------------ | ------------------- |
| **Y Stream** | Latest `4.(Y-1).z` | `UTS-FULL`         | Always              |
| **EUS**      | Latest `4.(Y-2).z` | `UTS-Marker`       | Only if `Y` is even |


### 2. First Maintenance Release (Z = 1)

*Target Pattern: `4.Y.1*`


| Upgrade Type | Source Version                     | Post-Upgrade Suite |
| ------------ | ---------------------------------- | ------------------ |
| **Y Stream** | Latest `4.(Y-1).z`                 | `UTS-FULL`         |
| **Z Stream** | Latest `4.Y.z` (typically `4.Y.0`) | `UTS-Marker`       |


### 3. Maintenance Releases (Z >= 2)

*Target Pattern: `4.Y.2+*`


| Upgrade Type | Source Version     | Post-Upgrade Suite |
| ------------ | ------------------ | ------------------ |
| **Y Stream** | Latest `4.(Y-1).z` | `UTS-Marker`       |
| **Z Stream** | Latest `4.Y.z`     | `NONE`             |
| **Latest Z** | `4.Y.0`            | `NONE`             |


### Key Terms

- **Y Stream**: Upgrading from the previous minor version (e.g., 4.19 -> 4.20).
- **Z Stream**: Upgrading within the same minor version (e.g., 4.20.0 -> 4.20.1).
- **Latest Z**: Upgradeing within the same minor version, from 4.Y.0 (e.g 4.20.0 -> 4.20.2)
- **EUS**: Extended Update Support, allowing skipping one minor version (e.g., 4.18 -> 4.20).
- **UTS-FULL**: Full test suite.
- **UTS-Marker**: Post Upgrade Marker (a reduced test suite).

## Using the Release Checklist Tool

Run the command by providing the target version using the `-v` (or `--target-version`) flag.

**Basic Example:**

```bash
release_checklist_upgrade_plan -v 4.20.2
```

### Specifying a Channel

You can optionally specify the release channel (default is `stable`):

```bash
release_checklist_upgrade_plan -v 4.20.2 -c stable
# or
release_checklist_upgrade_plan -v 4.20.2 -c candidate
```

**Note:** Only `stable` channel is fully supported at this time.

### Sample Output

```json
{
  "target_version": "4.20.2",
  "upgrade_lanes": {
    "Y stream": {
      "source_version": "v4.19.15",
      "bundle_version": "v4.19.15.rhel9-18",
      "iib": "registry-proxy.engineering.redhat.com/rh-osbs/iib:1079024",
      "channel": "stable",
      "post_upgrade_suite": "UTS-Marker"
    },
    "Z stream": {
      "source_version": "v4.20.1",
      "bundle_version": "v4.20.1.rhel9-13",
      "iib": "registry-proxy.engineering.redhat.com/rh-osbs/iib:1073045",
      "channel": "stable",
      "post_upgrade_suite": "NONE"
    },
    "latest z": {
      "source_version": "4.20.0",
      "bundle_version": "v4.20.0.rhel9-234",
      "iib": "registry-proxy.engineering.redhat.com/rh-osbs/iib:1063267",
      "channel": "stable",
      "post_upgrade_suite": "NONE"
    }
  }
}
```

## Upgrade Jobs Info Tool

**Command:** `upgrade_jobs_info`

This tool provides source and target build information for scheduled upgrade job execution. Unlike the release checklist tool which determines upgrade lanes from a target version, this tool takes both source and target versions and returns the specific build details needed for job execution.

### Parameters


| Parameter              | Format           | Required | Description                                                             |
| ---------------------- | ---------------- | -------- | ----------------------------------------------------------------------- |
| `-s, --source-version` | `4.Y` or `4.Y.0` | Yes      | Source version. Use `4.Y` for z/y-stream upgrades, `4.Y.0` for latest-z |
| `-t, --target-version` | `4.Y`            | Yes      | Target minor version                                                    |


### Parameter Constraints

- For **latest-z** upgrades, source must end with `.0` and have the same Y as target
- For **EUS** upgrades, both source and target minor versions must be even numbers

### Upgrade Validation

The tool validates upgrade paths and rejects invalid upgrade scenarios with clear error messages:


| Invalid Scenario          | Example           | Error                                 |
| ------------------------- | ----------------- | ------------------------------------- |
| **Same version**          | `4.20.5 → 4.20.5` | Cannot upgrade to the same version    |
| **Z-stream downgrade**    | `4.20.5 → 4.20.4` | Cannot downgrade within z-stream      |
| **Y-stream downgrade**    | `4.21 → 4.20`     | Cannot downgrade                      |
| **Version gap > 2**       | `4.18 → 4.21`     | Unsupported upgrade (gap of 3)        |
| **EUS with odd versions** | `4.19 → 4.21`     | EUS requires both versions to be even |
| **Latest-z cross-minor**  | `4.19.0 → 4.20`   | Latest-z requires same minor version  |


**Note:** `4.20 → 4.20` (minor format) is a valid Z-stream lookup. Only exact same full versions (e.g., `4.20.5 → 4.20.5`) are rejected.

### Upgrade Type Detection Strategy

The tool automatically determines the upgrade type based on the source and target versions:


| Source  | Target    | Upgrade Type | Description                      |
| ------- | --------- | ------------ | -------------------------------- |
| `4.Y`   | `4.Y`     | Z-stream     | Same minor version               |
| `4.Y`   | `4.(Y+1)` | Y-stream     | One minor version difference     |
| `4.Y.0` | `4.Y`     | Latest-Z     | Source is .0 release, same minor |
| `4.Y`   | `4.(Y+2)` | EUS          | Two minor versions, both even    |


### Fetch Strategy by Upgrade Type

Each upgrade type uses a specific strategy to fetch source and target build information:


| Upgrade Type | Source Fetch                       | Target Fetch                                                         |
| ------------ | ---------------------------------- | -------------------------------------------------------------------- |
| **Z-stream** | Latest stable released to prod     | Latest candidate (or latest stable in QE)                            |
| **Y-stream** | Latest Y-1 stable released to prod | Latest build with **stable channel** and errata (includes QE builds) |
| **Latest-Z** | 4.Y.0 release info                 | Latest candidate (or latest stable in QE)                            |
| **EUS**      | Latest Y stable released to prod   | Latest build with **stable channel** and errata (includes QE builds) |


**Note:** Y-stream and EUS upgrades require the target to have a stable channel. Z-stream and Latest-Z upgrades can use either candidate or stable channels.

### Usage Examples

```bash
# Z-stream upgrade (4.20 -> 4.20)
upgrade_jobs_info -s 4.20 -t 4.20

# Y-stream upgrade (4.19 -> 4.20)
upgrade_jobs_info -s 4.19 -t 4.20

# Latest-Z upgrade (4.20.0 -> 4.20)
upgrade_jobs_info -s 4.20.0 -t 4.20

# EUS upgrade (4.18 -> 4.20)
upgrade_jobs_info -s 4.18 -t 4.20
```

### Sample Output

For a Z-stream upgrade command:

```bash
upgrade_jobs_info -s 4.20 -t 4.20
```

Output:

```json
{
  "upgrade_type": "z_stream",
  "source": {
    "version": "v4.20.3",
    "bundle_version": "v4.20.3.rhel9-31",
    "iib": "registry-proxy.engineering.redhat.com/rh-osbs/iib:1084676",
    "channel": "stable"
  },
  "target": {
    "version": "v4.20.5",
    "bundle_version": "v4.20.5.rhel9-3",
    "iib": "registry-proxy.engineering.redhat.com/rh-osbs/iib:1091512",
    "channel": "candidate"
  }
}
```

## All Versions Upgrade Plan Tool

**Command:** `all_versions_upgrade_plan`

This tool batch generates upgrade plans for all supported CNV minor versions. It outputs individual JSON files per version and an optional combined summary file.

### Parameters


| Parameter                | Default           | Description                     |
| ------------------------ | ----------------- | ------------------------------- |
| `-o, --output-dir`       | `./upgrade_plans` | Output directory for JSON files |
| `--summary/--no-summary` | `--summary`       | Generate combined summary file  |


### Supported Versions

The tool generates upgrade plans for the following CNV versions:

- 4.12, 4.14, 4.16, 4.17, 4.18, 4.19, 4.20, 4.21

### Strategy

1. For each supported minor version, query the latest build with errata
2. Use that version as the target and generate upgrade paths (same logic as `release_checklist_upgrade_plan`)
3. Write individual JSON files: `upgrade_plan_4_X.json`
4. Optionally write combined summary: `all_versions_summary.json`

### Usage Examples

```bash
# Generate plans to default directory
all_versions_upgrade_plan

# Specify custom output directory
all_versions_upgrade_plan -o /tmp/my_plans

# Skip summary file
all_versions_upgrade_plan --no-summary
```

### Sample Output

The tool creates the following files in the output directory:

```
upgrade_plans/
├── upgrade_plan_4_12.json
├── upgrade_plan_4_14.json
├── upgrade_plan_4_16.json
├── upgrade_plan_4_17.json
├── upgrade_plan_4_18.json
├── upgrade_plan_4_19.json
├── upgrade_plan_4_20.json
├── upgrade_plan_4_21.json
└── all_versions_summary.json  (optional)
```

Each individual file contains the same structure as the output from `release_checklist_upgrade_plan` for that specific version.

# Contributing

Contributions are welcome! Please ensure:

1. Code follows the project's style guidelines (enforced via `ruff` and `flake8`)
