# AGENTS.md — Evidence Ledger Documentation Directory (`docs/verification/`) Guide

This file defines local rules for working inside `docs/verification/`. Parent guidelines live in [`docs/AGENTS.md`](../AGENTS.md) and the root [`AGENTS.md`](../../AGENTS.md).

## 1. Documentation Types: Specs vs. Measured Reports

- **Specifications & Methodology (Architectural Truth)**:
  - `methodology.md`: Core verification principles, claim types, and claim-level status vocabulary (`supported_by_evidence`, `contradicted_by_evidence`, `mixed_evidence`).
  - `implementation-spec.md`: System contract, configuration schema, and resource bounds for claim verification.
  - `annotation-decision.md`: Publication decision rules and reader-visible coverage statuses (`complete`, `partial`, `provisional`).
  - `preflight.md`: Baseline pipeline flow and orchestrator integration details.
- **Measured Reports & Historical Records (Observed Data)**:
  - `evaluation-results.md`: Static historical records of offline adversarial regressions (`tests/fixtures/verification_adversarial.json`) and initial shadow-run metrics.
  - **Invariant**: Historical measurement figures are static observations. Do not treat them as configurable specifications or invent new benchmark numbers without executed measurements.

## 2. Public Site Exclusions & Sanitization

- **Site Exclusion**: `docs/verification/` contains internal repository-only manuals and is explicitly excluded from the public MkDocs Material build (`exclude_docs: verification/` in `mkdocs.yml`).
- **Public Status Sanitization**: Internal error, timeout, or unverified operational statuses (`verification_error`, `check_error`, `check_failed`, `not_checked`) must never appear on reader-facing public site pages. Articles with search failures or unverified claims degrade gracefully without scary error banners.
- **Usage-Publication Conflict**: Article banners omit token/cost details, while the current public checks-page generator deliberately calls `render_verification_status(..., include_usage=True)` and tests expect the usage line. This conflicts with the constitution and older specs that describe all estimates as internal. Preserve the current tested contract until the owner explicitly chooses a policy; then update policy docs, code, tests, and changelog together.

## 3. Key Engine & Verification References

- **Engine Code**: `src/verification/` (`claims.py`, `evidence.py`, `fetch.py`, `ledger.py`, `incidents.py`, `evaluation.py`, retained `audit.py`)
- **Offline Evaluation Utility**: `scripts/dev_evaluate_verification.py`
- **Adversarial Test Fixtures**: `tests/fixtures/verification_adversarial.json`
- **Site Exclusions**: `mkdocs.yml` (`exclude_docs`)
