# Scripts

## generate_current_testing_paths.py

Generates upgrade path and release checklist data for every supported version by querying the Version Explorer API. Produces JSON + Markdown files to `current_testing_paths/`.

**Requires** Version Explorer API access (VPN).

### Usage

```bash
# Generate to current_testing_paths/ directory
uv run python scripts/generate_current_testing_paths.py

# Output to stdout (JSON only)
uv run python scripts/generate_current_testing_paths.py --stdout

# Subset of versions
uv run python scripts/generate_current_testing_paths.py --versions 4.20,4.21

# Via tox
uv run tox -e generate
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--output-dir` | `current_testing_paths/` | Output directory |
| `--stdout` | off | Write JSON to stdout instead of files |
| `--versions` | all supported | Comma-separated subset of versions to process |

### Output Files

| File | Content |
|------|---------|
| `upgrade-paths.json` | Version-keyed `upgrade_jobs_info` results with latest z-stream data |
| `upgrade-paths.md` | Markdown table of all upgrade paths per version |
| `release-checklist.json` | Version-keyed `release_checklist_upgrade_plan` results with stage/prod status |
| `release-checklist.md` | Markdown table of release checklists per version |

### How It Works

1. Probes the Version Explorer API to find the highest z-stream release per supported version
2. For each version, generates all applicable upgrade paths (z-stream, latest-z, y-stream, EUS)
3. Calls `upgrade_jobs_info` for each path and `release_checklist_upgrade_plan` for each version
4. Writes results as JSON and Markdown to the output directory
