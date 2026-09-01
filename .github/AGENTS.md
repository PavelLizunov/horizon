# AGENTS.md — GitHub Metadata & Automation Guide

This directory governs GitHub repository configuration, issue/PR templates, and CI/CD workflow definitions.

## Local Ownership
- `.github/pull_request_template.md`: Standard pull request checklist and structure.
- `.github/workflows/`: Active and disabled GitHub Actions workflows (see `.github/workflows/AGENTS.md`).
- `.github/ISSUE_TEMPLATE/`: Structured issue templates (see `.github/ISSUE_TEMPLATE/AGENTS.md`).

## Invariants
- All workflow definitions and templates must be valid YAML or Markdown.
- No real credentials, `.env` variables, or runtime configuration (`data/config.json`) may be committed in `.github/`.
- Subdirectories (`workflows/`, `ISSUE_TEMPLATE/`) inherit these baseline rules and define localized constraints.

## Secret & Permissions Safety
- Never hardcode secrets in workflow files or templates.
- New or edited workflows must use minimal explicit permissions and reference secrets only via `${{ secrets.SECRET_NAME }}`. The existing `tests.yml` still relies on repository-default permissions; see the nested workflow guide.

## Validation
- Validate YAML and Markdown formatting locally.
- Run `pytest` locally to verify the test suite runs cleanly prior to pushing CI changes.
- Check git formatting with `git diff --check -- .github/AGENTS.md`.

## Public API & Documentation Coupling
- Workflow builds (`deploy-docs.yml`) rely on MkDocs configuration (`mkdocs.yml`) and `docs/` content.
- PR templates (`pull_request_template.md`) align contributor changes with Spec-Driven Development (SDD) norms defined in root `AGENTS.md`.

## Inheritance
Inherits root `AGENTS.md`. Nested directories `.github/workflows/` and `.github/ISSUE_TEMPLATE/` contain closest-guide overrides for CI workflows and issue templates respectively.
