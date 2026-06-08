# release_checklist_upgrade_plan

Generates upgrade lanes for a CNV release checklist. Given a target version, determines all applicable upgrade paths with their source versions, build info, and post-upgrade test suites.

## Parameters


| Parameter              | Acceptable Formats | Required | Description                                                                                                               |
| ---------------------- | ------------------ | -------- | ------------------------------------------------------------------------------------------------------------------------- |
| `-v, --target-version` | `X.Y.Z`            | Yes      | Target version (e.g., `4.20.2`)                                                                                           |
| `--skip-target-check`  | flag               | No       | Skip target channel validation. Use when the target build hasn't reached stable-stage yet or is already released to prod. |


Which upgrade lanes apply and which post-upgrade suites run depends on the target's patch level (z). See [Upgrade Strategy](upgrade-strategy.md) for the full rules and z-level tables.

## Resolution Rules

**Target**: must be in the stable channel, staged but not yet released to production. If the target hasn't reached stable-stage or is already released, the tool fails with an error. Use `--skip-target-check` to bypass this and accept any available build.

**Source**: resolves to the latest stable build released to production for the corresponding minor version. For Latest-Z, the source is always the `X.Y.0` GA build.

## Examples

```bash
# Subsequent maintenance — generates Y-stream + Z-stream + Latest-Z lanes
release_checklist_upgrade_plan -v 4.20.2

# Major release — generates Y-stream + EUS lanes (4.20 is even)
release_checklist_upgrade_plan -v 4.20.0

# Skip target validation (e.g., target already released to prod)
release_checklist_upgrade_plan -v 4.16.33 --skip-target-check
```

## Example Output

```json
{
  "target_version": "4.20.15",
  "target_build_info": {
    "version": "4.20.15",
    "bundle_version": "4.20.15.rhel9-38",
    "iib": "registry-proxy.engineering.redhat.com/rh-osbs/iib:1149389",
    "channel": "stable",
    "in_stage": true,
    "released_to_prod": true
  },
  "upgrade_lanes": {
    "Y stream": {
      "source_version": "4.19.25",
      "bundle_version": "4.19.25.rhel9-42",
      "iib": "registry-proxy.engineering.redhat.com/rh-osbs/iib:1149390",
      "channel": "stable",
      "post_upgrade_suite": "UTS-Marker"
    },
    "Z stream": {
      "source_version": "4.20.14",
      "bundle_version": "4.20.14.rhel9-16",
      "iib": "registry-proxy.engineering.redhat.com/rh-osbs/iib:1139072",
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

## Post-Upgrade Test Suites

- **UTS-FULL**: comprehensive suite covering the complete set of upgrade validation tests.
- **UTS-Marker**: includes tier1 + post-upgrade tier2 + tier3 and more. Broader than tier2 alone.
- **NONE**: no post-upgrade suite. The upgrade itself is tested, but post-upgrade functional verification is skipped.

See [Upgrade Strategy](upgrade-strategy.md) for the full suite hierarchy and how release checklist testing relates to scheduled CI jobs.
