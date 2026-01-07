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

This makes the `release_checklist_upgrade_plan` command available globally.

### Development installation

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

# Tools & Features

##  Upgrade Release Checklist Generator
**Command:** `release_checklist_upgrade_plan`

* The target channel must be "stable"!  

This tool automates the generation of upgrade paths (lanes) for CNV release checklists. It determines the appropriate source versions and post-upgrade test suites based on the target release version and defined upgrade rules.


The checklist tool categorizes the target version (`4.Y.z`) into three main buckets based on the Z-stream component.

### 1. Major Release (Z = 0)
*Target Pattern: `4.Y.0`*

| Upgrade Type | Source Version | Post-Upgrade Suite | Condition |
|--------------|----------------|-------------------|-----------|
| **Y Stream** | Latest `4.(Y-1).z` | `UTS-FULL` | Always |
| **EUS** | Latest `4.(Y-2).z` | `UTS-Marker` | Only if `Y` is even |

### 2. First Maintenance Release (Z = 1)
*Target Pattern: `4.Y.1`*

| Upgrade Type | Source Version | Post-Upgrade Suite |
|--------------|----------------|-------------------|
| **Y Stream** | Latest `4.(Y-1).z` | `UTS-FULL` |
| **Z Stream** | Latest `4.Y.z` (typically `4.Y.0`) | `UTS-Marker` |

### 3. Maintenance Releases (Z >= 2)
*Target Pattern: `4.Y.2+`*

| Upgrade Type | Source Version | Post-Upgrade Suite |
|--------------|----------------|-------------------|
| **Y Stream** | Latest `4.(Y-1).z` | `UTS-Marker` |
| **Z Stream** | Latest `4.Y.z` | `NONE` |
| **Latest Z** | `4.Y.0` | `NONE` |

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
NOTE: still not fully supported  
You can optionally specify the release channel (default is `stable`):

```bash
release_checklist_upgrade_plan -v 4.20.2 -c stable
```

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
# Next Steps

* Adding logic to pull the required information for scheduled upgrade jobs execution.
* Additional utils inc.
