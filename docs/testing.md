# Testing

## Test Categories

| Category | Description | Network |
|----------|-------------|---------|
| **Unit** | Fully mocked tests for all production logic. No network calls. | None |
| **E2E** | Hit the live Version Explorer API to validate real upgrade path resolution. | VPN |
| **FBC** | Validate upgrade rules against the cnv-fbc GitHub repo (file-based catalog). | Public internet |
| **Cross-validation** | Compare FBC data against Version Explorer API for consistency. | VPN + public internet |
| **CLI** | Subprocess tests verifying both CLI commands produce clean errors. | VPN |

## How to Run

```bash
# Unit tests (offline)
uv run pytest

# E2E tests (requires VPN)
uv run pytest -m e2e --log-cli-level=INFO

# FBC ground truth verification (requires public internet)
uv run pytest -m "fbc and not e2e" --log-cli-level=INFO

# Cross-validation: FBC vs API (requires both)
uv run pytest -m "e2e and fbc" --log-cli-level=INFO

# All E2E + FBC tests
uv run pytest -m "e2e or fbc" --log-cli-level=INFO
```

Via tox:

```bash
uv run tox                # Default envlist (no e2e)
uv run tox -e e2e         # E2E tests
uv run tox -e fbc         # FBC tests
```

## Markers

Two custom markers are defined in `pyproject.toml`: `e2e` (needs Version Explorer API / VPN) and `fbc` (needs cnv-fbc GitHub repo / public internet).

By default, `uv run pytest` runs only unit tests. E2E and FBC tests are automatically deselected unless you explicitly pass `-m e2e` or `-m fbc`. No `-o "addopts="` override needed.

## FBC (File-Based Catalog)

[cnv-fbc](https://github.com/openshift-cnv/cnv-fbc) is the file-based catalog for OpenShift Virtualization -- a Git repository with `stage` and `production` branches containing OLM channel definitions, version entries, and upgrade edges.

FBC is the upstream source of truth for what versions exist in what channels and what upgrade paths are valid. The Version Explorer API is the primary data source for this project's CLI tools, but validating against FBC catches:

- Drift between API data and actual catalog state
- Bugs in upgrade lane computation logic
- Stale stage/prod flags that no longer reflect reality
- Missing or unexpected versions in channels

The FBC tests cover: version coverage, upgrade lanes, channel consistency, stage/prod consistency, stale detection, and EOL rejection.

## Tox Environments

| Environment | Description | Network | In default envlist |
|------------|-------------|---------|-------------------|
| `lint` | ruff check/format, flake8, mypy | None | Yes |
| `py312` | Unit tests + coverage (Python 3.12) | None | Yes |
| `py314` | Unit tests + coverage (Python 3.14) | None | Yes |
| `security` | bandit, pip-audit | None | Yes |
| `fbc` | FBC ground truth verification | Public internet | Yes |
| `e2e` | E2E tests against Version Explorer API | VPN | No |
| `generate` | Generate current testing paths snapshots | VPN | No |
| `coverage` | Coverage report, 80% threshold | None | Yes |

E2E, cross-validation, and snapshot generation cannot run on GitHub Actions because the Version Explorer API is VPN-only.

## Logging

E2E tests include `[N/M]` progress counters during multi-version probing. To see them:

```bash
uv run pytest -m e2e --log-cli-level=INFO
```
