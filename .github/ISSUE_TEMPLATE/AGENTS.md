# AGENTS.md — Issue Templates Guide

This directory governs GitHub issue templates in `.github/ISSUE_TEMPLATE/`.

## Local Ownership
- `.github/ISSUE_TEMPLATE/feature_request.md`: Structured template for proposing project features.

## Invariants
- Template files must use valid Markdown with valid YAML frontmatter header block (`name`, `about`, `title`, `labels`, `assignees`).
- Template body must prompt for clear problem description, proposed solution, alternative considerations, and additional context.

## Secret & Permissions Safety
- Issue templates must never contain API keys, server IP addresses, credentials, or personal system paths.

## Validation
- Inspect frontmatter and markdown rendering locally.
- Run `git diff --check -- .github/ISSUE_TEMPLATE/AGENTS.md` to verify formatting.

## Public API & Documentation Coupling
- Proposed feature requests must align with Spec-Driven Development (SDD) guidelines in root `AGENTS.md` and `specs/`.

## Inheritance
Inherits from `.github/AGENTS.md` and root `AGENTS.md`. Governs local issue template structure and content.
