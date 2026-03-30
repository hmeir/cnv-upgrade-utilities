# upgrade_jobs_info Strategy

## Overview

`upgrade_jobs_info` resolves source and target build information for CNV upgrade jobs. It supports three version input formats and four upgrade types, each with specific rules for which builds are acceptable.

## Upgrade Types

### Latest Z

- **Source**: `X.Y.0` stable build released to prod.
- **Target**: Latest stable stage (not yet released to prod) / candidate prod / candidate stage.

### Z Stream

- **Source**: Latest `X.Y.Z` released to stable prod.
- **Target**: Latest stable stage (not yet released to prod) / candidate prod / candidate stage.

### Y Stream

- **Source**: Latest `X.Y-1.Z` released to stable prod.
- **Target**: **Must** be stable. Prefers stable stage (not yet released to prod), falls back to previous stable prod.

### EUS

- **Source**: Latest `X.Y-2.Z` released to stable prod.
- **Target**: Same rules as Y stream.

## Version Format Strategies

### BUNDLE Format (`X.Y.Z.rhelR-BN`)

Uses the `/GetBuildInfo` API for exact build lookup.

**Target version:**

| Upgrade Type     | Strategy                                                                 |
|------------------|--------------------------------------------------------------------------|
| Z stream         | Try stable channel. If no stable, try candidate. If neither, fail.       |
| Latest Z         | Same as Z stream.                                                        |
| Y stream         | Must have stable. If no stable, fail -- unless it's `X.Y.0`, then take candidate. |
| EUS              | Same as Y stream.                                                        |

**Source version:**

| Upgrade Type     | Strategy                                                                 |
|------------------|--------------------------------------------------------------------------|
| Z stream         | Validate `current_channel=stable` and stable channel `released_to_prod=true`. |
| Latest Z         | Same validation, plus verify it's an `X.Y.0` build.                     |
| Y stream         | Same validation, plus verify it's an `X.Y-1.Z` build.                   |
| EUS              | Same validation, plus verify it's an `X.Y-2.Z` build.                   |

### FULL Format (`X.Y.Z`)

Uses `/GetSuccessfulBuildsByVersion` with `channel` and `stage` filters.

**Target version -- 3-step fallback (Z stream / Latest Z, and `X.Y.0` for Y stream / EUS):**

1. `channel=stable, stage=true` -- take first build NOT already `released_to_prod` (newest stable in stage, not yet on prod).
2. `channel=candidate, stage=false` -- find first with `released_to_prod=true` (candidate already on prod).
3. `channel=candidate, stage=true` -- take first build NOT already `released_to_prod` (candidate in stage, not yet on prod).
4. Fail with error.

For Y stream / EUS with non-`X.Y.0` target: only step 1 applies. Fail if no stable build in stage.

**Source version:**

1. `channel=stable, stage=false` -- find first with `released_to_prod=true`.
2. Fallback: use `/GetReleasedBuilds` for the minor version (`stage=false`), match `csv_version`, verify stable `released_to_prod=true`.
3. Fail with error.

### MINOR Format (`X.Y`)

Uses `/GetReleasedBuilds` API.

**Target version (`stage=true`):**

1. Find latest z with `current_channel=stable` and stable channel `in_stage=true` but NOT `released_to_prod=true`.
2. (Y stream / EUS only) Fall back to latest z with stable channel `released_to_prod=true`. If no stable build found at all, fail.
3. (Z stream / Latest Z only) Find latest z with candidate channel `released_to_prod=true`.
4. (Z stream / Latest Z only) Find latest z with candidate channel `in_stage=true` but NOT `released_to_prod=true`.
5. Fail with error.

**Source version (`stage=false`):**

1. Find latest z with stable channel `released_to_prod=true`, excluding the target version (to avoid source=target in Z-stream).
2. Fail with error.

## Channel Lifecycle

Builds progress through channels in this order:

```
candidate-stage -> candidate-prod -> stable-stage -> stable-prod
```

Note: `in_stage` and `released_to_prod` can **both** be true simultaneously -- a build stays in stage after being released to prod.

## API Response Format Notes

| API                            | Bundle version key | Version prefix | Response structure          |
|--------------------------------|--------------------|----------------|-----------------------------|
| `GetBuildInfo`                 | `cnv_version`      | has `v`        | Nested `channels` array     |
| `GetSuccessfulBuildsByVersion` | `cnv_build`        | no `v`         | Flat (with channel filter) / Nested (without) |
| `GetReleasedBuilds`            | `version`          | has `v`        | Nested `channels` array, `csv_version` has `v` |
