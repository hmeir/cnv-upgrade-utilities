# Contributing

## Setup

```bash
git clone https://github.com/hmeir/cnv-upgrade-utilities.git
cd cnv-upgrade-utilities
uv sync --extra dev
uv run pre-commit install
```

## Running Checks

Before submitting a PR, all checks must pass:

```bash
# Run all default checks (lint, unit tests, security, FBC, coverage)
uv run tox

# Run E2E tests if on VPN
uv run tox -e e2e

# Run a specific tox environment
uv run tox -e lint
uv run tox -e py312
```

Pre-commit hooks enforce code style (ruff), linting (flake8), and type checking (mypy) on every commit.

## Code Style

- Line length: 120 characters
- Python 3.12+ required
- Double quotes for strings
- No comments unless the WHY is non-obvious
- Uses ruff for linting/formatting with flake8 for additional checks

## PR Requirements

- All unit tests pass (`uv run pytest`)
- All linting passes (`pre-commit run --all-files`)
- E2E tests pass if changes affect API client, build helpers, upgrade logic, or test fixtures
- Update `CLAUDE.md` and `README.md` if changing SUPPORTED_VERSIONS, EOL_VERSIONS, upgrade types, CLI parameters, data models, or test structure
