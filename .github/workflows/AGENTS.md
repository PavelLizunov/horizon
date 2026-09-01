# AGENTS.md — GitHub Actions Workflows Guide

This directory governs CI/CD automation defined in `.github/workflows/`.

## Local Ownership
- `.github/workflows/tests.yml`: Active CI test workflow ("Tests") triggered on `push` to `main` and `pull_request`.
- `.github/workflows/deploy-docs.yml`: Manual site preview deployment workflow ("Deploy Site Preview") triggered via `workflow_dispatch`.
- `.github/workflows/daily-summary.yml.disabled`: Disabled scheduled workflow template ("Daily Horizon Summary").

## Invariants
- `tests.yml` executes offline `pytest` using Python 3.12 and `pip install ".[dev]"`.
- `deploy-docs.yml` uses `mkdocs build --strict` and `peaceiris/actions-gh-pages@v4` to publish `./site` to the `gh-pages` branch.
- Disabled workflows must retain the `.disabled` extension to prevent unwanted scheduled execution.
- Workflows should explicitly declare least-privilege job-level `permissions:`. `deploy-docs.yml` grants `contents: write`; `tests.yml` currently omits a block and relies on repository defaults, which is a known hardening gap rather than a pattern to copy.

## Secret & Permissions Safety
- Reference secrets only through explicit action inputs or step `env:` entries (for example `github_token: ${{ secrets.GITHUB_TOKEN }}`); never interpolate them into scripts.
- Never echo or log secret values in workflow execution steps.

## Validation
- Test python dependencies and test suite locally:
  ```bash
  pip install -e ".[dev]"
  pytest
  ```
- Test MkDocs preview build locally:
  ```bash
  pip install mkdocs-material
  mkdocs build --strict
  ```
- Run `git diff --check -- .github/workflows/AGENTS.md` to ensure clean formatting.

## Public API & Documentation Coupling
- `tests.yml` validates core codebase changes against `tests/`.
- `deploy-docs.yml` relies on MkDocs configuration (`mkdocs.yml`) and documentation source files under `docs/`.

## Inheritance
Inherits from `.github/AGENTS.md` and root `AGENTS.md`. Overrides parent rules only for workflow-specific execution requirements.
