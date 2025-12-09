# CNV Upgrade Utilities

This repository contains a collection of utilities designed to assist with CNV (Container Native Virtualization) upgrade testing, release management, and automation.

## Overview

The goal of this project is to provide a central location for scripts and tools that streamline the upgrade validation process for CNV releases. It currently includes tools for generating release checklists and calculating upgrade lanes.

## Tools & Features

### 1. Upgrade Release Checklist Generator
**Script:** `release_checklist_upgrade_lanes.py`

This tool automates the generation of upgrade paths (lanes) for CNV release checklists. It determines the appropriate source versions and post-upgrade test suites based on the target release version and defined upgrade rules.

#### Key Features:
- **Automated Source Version Detection**: Queries an external "Version Explorer" service to find the latest valid source versions.
- **Rule-Based Categorization**: Applies specific logic based on Z-stream versions (0, 1, or 2+) to determine upgrade lanes.
- **EUS Support**: Automatically includes Extended Update Support (EUS) upgrade lanes for even-numbered Y-streams.
- **JSON Output**: Produces machine-readable output suitable for CI/CD pipelines.

---

## Prerequisites

- Python >= 3.12
- Access to the Version Explorer API (for relevant tools).

## Installation

This project uses `uv` for dependency management, but can also be installed via standard pip.

### Using uv (Recommended)

```bash
git clone https://github.com/hmeir/cnv-upgrade-utilities.git
cd cnv-upgrade-utilities
uv sync
```

## Configuration

For tools interacting with the Version Explorer, you must set the `VERSION_EXPLORER_URL` environment variable.

```bash
export VERSION_EXPLORER_URL="http://<your-version-explorer-host>"
```

## Usage

### Using the Release Checklist Tool

Run the script by providing the target version using the `-v` (or `--target-version`) flag.

**Basic Example:**
```bash
uv run python release_checklist_upgrade_lanes.py -v 4.18.0
```

### Specifying a Channel
NOTE: still not fully supported  
You can optionally specify the release channel (default is `stable`):

```bash
uv run python release_checklist_upgrade_lanes.py -v 4.18.0 -c candidate
```

### Sample Output

```json
{
  "target_version": "4.18.0",
  "upgrade_lanes": [
    {
      "type": "Y stream",
      "source_version": "4.17.5",
      "post_upgrade_suite": "FULL"
    },
    {
      "type": "EUS",
      "source_version": "4.16.8",
      "post_upgrade_suite": "PUM"
    }
  ]
}
```

## Upgrade Rules & Logic

The checklist tool categorizes the target version (`4.Y.z`) into three main buckets based on the Z-stream component.

### 1. Major Release (Z = 0)
*Target Pattern: `4.Y.0`*

| Upgrade Type | Source Version | Post-Upgrade Suite | Condition |
|--------------|----------------|-------------------|-----------|
| **Y Stream** | Latest `4.(Y-1).z` | `FULL` | Always |
| **EUS** | Latest `4.(Y-2).z` | `PUM` | Only if `Y` is even |

### 2. First Maintenance Release (Z = 1)
*Target Pattern: `4.Y.1`*

| Upgrade Type | Source Version | Post-Upgrade Suite |
|--------------|----------------|-------------------|
| **Y Stream** | Latest `4.(Y-1).z` | `FULL` |
| **Z Stream** | Latest `4.Y.z` (typically `4.Y.0`) | `PUM` |

### 3. Maintenance Releases (Z >= 2)
*Target Pattern: `4.Y.2+`*

| Upgrade Type | Source Version | Post-Upgrade Suite |
|--------------|----------------|-------------------|
| **Y Stream** | Latest `4.(Y-1).z` | `PUM` |
| **Z Stream** | Latest `4.Y.z` | `NONE` |
| **Latest Z** | `4.Y.0` | `NONE` |

### Key Terms
- **Y Stream**: Upgrading from the previous minor version (e.g., 4.17 -> 4.18).
- **Z Stream**: Upgrading within the same minor version (e.g., 4.18.0 -> 4.18.1).
- **EUS**: Extended Update Support, allowing skipping one minor version (e.g., 4.16 -> 4.18).
- **PUM**: Post Upgrade Marker (a reduced test suite).
- **FULL**: Full test suite.
