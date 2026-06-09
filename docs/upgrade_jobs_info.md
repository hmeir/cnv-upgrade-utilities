# upgrade_jobs_info

Resolves source and target build information for CNV upgrade job execution. Given a source and target version pair, detects the upgrade type and fetches the corresponding builds from the Version Explorer API.

## Parameters


| Parameter              | Acceptable Formats               | Required                          | Description    |
| ---------------------- | -------------------------------- | --------------------------------- | -------------- |
| `-s, --source-version` | `X.Y`, `X.Y.Z`, `X.Y.Z.rhelR-BN` | Yes (not required with `--gating`) | Source version |
| `-t, --target-version` | `X.Y`, `X.Y.Z`, `X.Y.Z.rhelR-BN` | Yes                               | Target version |
| `--gating`             | Flag                             | No                                | Gating mode: resolve source and target from candidate channel |


Any combination of formats can be used between source and target.

## Resolution Rules

**Source**: resolves to the latest stable build released to production for the source minor version.

**Target**: resolves to the latest build in stage (stable channel preferred, candidate channel as fallback) that has not yet been released to production.

The version format determines the level of resolution:


| Format                        | Resolution                                                  |
| ----------------------------- | ----------------------------------------------------------- |
| **MINOR** (`X.Y`)             | Auto-discovers the best z-stream for both source and target |
| **FULL** (`X.Y.Z`)            | Looks up the specific X.Y.Z version                         |
| **BUNDLE** (`X.Y.Z.rhelR-BN`) | Exact build lookup, no resolution needed                    |


**Upgrade type** is detected automatically from the source and target versions:


| Source  | Target    | Upgrade Type            |
| ------- | --------- | ----------------------- |
| `4.Y`   | `4.Y`     | Z-stream                |
| `4.Y.0` | `4.Y`     | Latest-Z                |
| `4.Y`   | `4.(Y+1)` | Y-stream                |
| `4.Y`   | `4.(Y+2)` | EUS (both must be even) |


**Validation**: the tool rejects same-version upgrades, downgrades, gaps > 2 minor versions, EUS with odd versions, and EOL sources/targets.

### Gating Mode

When `--gating` is passed, the tool resolves builds from the **candidate** channel instead of stable:

- **Source**: latest candidate build released to production
- **Target**: candidate build in stage (not yet released to production)
- Only MINOR format (`X.Y`) is supported
- Only `-t` is required; `-s` is optional (if provided, must be the same minor)

## Examples

MINOR format (auto-resolve z-streams):

```bash
upgrade_jobs_info -s 4.20 -t 4.20          # Z-stream
upgrade_jobs_info -s 4.19 -t 4.20          # Y-stream
upgrade_jobs_info -s 4.18 -t 4.20          # EUS
```

FULL format (specific versions):

```bash
upgrade_jobs_info -s 4.19.15 -t 4.20.1    # Y-stream, specific z-streams
upgrade_jobs_info -s 4.20.0 -t 4.20       # Latest-Z (source must be X.Y.0)
```

BUNDLE format (exact builds):

```bash
upgrade_jobs_info -s 4.20.3.rhel9-31 -t 4.20.5.rhel9-3
```

Gating mode (candidate channel):

```bash
upgrade_jobs_info --gating -t 4.20
```

## Example Output

```json
{
  "upgrade_type": "eus",
  "source": {
    "version": "4.20.15",
    "bundle_version": "4.20.15.rhel9-38",
    "iib": "registry-proxy.engineering.redhat.com/rh-osbs/iib:1149389",
    "channel": "stable",
    "in_stage": true,
    "released_to_prod": true
  },
  "target": {
    "version": "4.22.0",
    "bundle_version": "4.22.0.rhel9-178",
    "iib": "registry-proxy.engineering.redhat.com/rh-osbs/iib:1151490",
    "channel": "stable",
    "in_stage": true,
    "released_to_prod": false
  }
}
```

## Post-Upgrade Testing

After each scheduled upgrade job (Y-stream, Z-stream, EUS), post-upgrade **tier2** tests run on the upgraded cluster. See [Upgrade Strategy](upgrade-strategy.md) for the full testing strategy and suite hierarchy.
