# CNV Upgrade Strategy

## Overview

This doc summerizing our upgrade testing strategy.

Upgrade testing is split into two complementary tracks:

- **Scheduled CI jobs** run continuously on PSI clusters, catching regressions early across a configurable set of upgrade paths. testing also candidates.
- **Release checklist testing** runs on bare metal (BM) clusters when a specific build reaches stable-stage, gating the release with targeted upgrade validation and post-upgrade test suites.

Together, scheduled jobs provide breadth and early feedback, while the release checklist provides depth and serves as the final gate before a build is released to production.

## Build Phases

Every CNV build progresses through a four-phase release pipeline:


| Phase           | Channel   | Description                                              |
| :-------------: | :-------: | -------------------------------------------------------- |
| candidate-stage | candidate | Build is staged for internal candidate channel testing   |
| candidate-prod  | candidate | Build is released to the candidate channel in production |
| stable-stage    | stable    | Build is staged for stable channel testing               |
| stable-prod     | stable    | Build is released to the stable channel in production    |


For upgrade testing:

- **Source builds** must be on the stable channel and released to production (stable-prod).
- **Target builds** for release checklist testing should be on the stable channel, staged but not yet released to production (stable-stage).

## Supported Upgrade Types

| Upgrade Type | Source → Target   | Description                                                         |
| :----------: | :---------------: | ------------------------------------------------------------------- |
| Y-stream     | `4.Y` → `4.(Y+1)` | Upgrade to the next minor version                                   |
| Z-stream     | `4.Y.Z` → `4.Y.(Z+1)`     | Upgrade within the same minor version (z-stream)                    |
| Latest-Z     | `4.Y.0` → `4.Y.(latest)`   | Upgrade from the GA build to the latest z-stream in the same minor |
| EUS          | `4.Y` → `4.(Y+2)` | Skip one minor version; both source and target minors must be even  |

## Supported Versions and End-of-Life


| Supported                                            | EOL (not tested) |
| :--------------------------------------------------: | :--------------: |
| 4.12, 4.14, 4.16, 4.17, 4.18, 4.19, 4.20, 4.21, 4.22 | 4.13, 4.15       |


**EOL impact:**

- **Y-stream is skipped** when the predecessor is EOL or unsupported (e.g., 4.16 skips Y-stream because 4.15 is EOL).
- **EUS fills the gap** where applicable (e.g., 4.14 to 4.16 EUS replaces the missing 4.15 to 4.16 Y-stream).
- **Z-stream and Latest-Z are unaffected** since both source and target are the same minor version.

## Testing Strategy by Z-level

Each z-level determines which upgrade types are tested and what post-upgrade suites run on each track:

- **Scheduled CI (PSI)**: runs upgrade paths from a configurable map, triggered by cron and events. The `upgrade_jobs_info` tool resolves builds.
- **Release Checklist (BM)**: runs when a target build reaches stable-stage. The `release_checklist_upgrade_plan` tool generates the test plan.

**Major Release (z = 0)**


| Upgrade Type | Condition                | Scheduled CI       | Release Checklist (BM) |
| :----------: | :----------------------: | :----------------: | :--------------------: |
| Y-stream     | Always                   | post upgrade tier2 | UTS-FULL               |
| EUS          | Both even, Y-2 supported | post upgrade tier2 | UTS-Marker             |


**First Maintenance Release (z = 1)**


| Upgrade Type | Condition                | Scheduled CI       | Release Checklist (BM) |
| :----------: | :----------------------: | :----------------: | :--------------------: |
| Y-stream     | Always                   | post upgrade tier2 | UTS-FULL               |
| Z-stream     | Always                   | post upgrade tier2 | UTS-Marker             |
| EUS          | Both even, Y-2 supported | post upgrade tier2 | --                     |


**Subsequent Maintenance Releases (z >= 2)**


| Upgrade Type | Condition                | Scheduled CI       | Release Checklist (BM)                   |
| :----------: | :----------------------: | :----------------: | :--------------------------------------: |
| Y-stream     | Y-1 supported            | post upgrade tier2 | UTS-Marker                               |
| Z-stream     | Always                   | post upgrade tier2 | NONE                                     |
| Latest-Z     | Always                   | --                 | NONE                                     |
| EUS          | Both even, Y-2 supported | post upgrade tier2 | UTS-Marker if Y-1 EOL. Otherwise - NONE. |


When Y-stream is not applicable (predecessor is EOL), EUS fills its role as the cross-version upgrade path with UTS-Marker testing on the release checklist.

## Upgrade Rules Matrix

Which upgrade types apply to each supported version (at z >= 2, where all applicable types are active):


| Target | Y-stream | Z-stream | Latest-Z | EUS |
| :----: | :------: | :------: | :------: | :-: |
| 4.12   | --       | yes      | yes      | --  |
| 4.14   | --       | yes      | yes      | yes |
| 4.16   | --       | yes      | yes      | yes |
| 4.17   | yes      | yes      | yes      | --  |
| 4.18   | yes      | yes      | yes      | yes |
| 4.19   | yes      | yes      | yes      | --  |
| 4.20   | yes      | yes      | yes      | yes |
| 4.21   | yes      | yes      | yes      | --  |
| 4.22   | yes      | yes      | yes      | yes |


Notes:

- 4.12: no Y-stream (4.11 not supported), no EUS (4.10 not supported)
- 4.14: no Y-stream (4.13 is EOL), EUS from 4.12 fills the cross-version gap
- 4.16: no Y-stream (4.15 is EOL), EUS from 4.14 fills the cross-version gap
- EUS only between even-numbered versions
- Z-stream and Latest-Z require z >= 1 and z >= 2 respectively

## Post-Upgrade Test Suites

Post-upgrade testing uses different scopes depending on the testing track:


| Suite          | Scope                                                                          | Used By           |
| :------------: | :----------------------------------------------------------------------------: | :---------------: |
| **tier2**      | Post-upgrade tests from openshift-virtualization-tests (`post_upgrade` marker) | Scheduled CI jobs |
| **UTS-Marker** | Broader suite: tier1 + post-upgrade tier2 + tier3 + more                       | Release checklist |
| **UTS-FULL**   | Comprehensive suite covering the complete set of upgrade validation tests      | Release checklist |


UTS-Marker and UTS-FULL are supersets of tier2 -- tier2 is always included when either runs.

## Current Testing Paths

The `current_testing_paths/` directory contains live, generated data for all supported versions:


| File                        | Source                           | Content                                                                         |
| :-------------------------: | :------------------------------: | :-----------------------------------------------------------------------------: |
| `upgrade-paths.json/md`     | `upgrade_jobs_info`              | Scheduled job upgrade paths -- source/target versions and channels              |
| `release-checklist.json/md` | `release_checklist_upgrade_plan` | Release gate data -- target build details, source IIBs, and post-upgrade suites |
