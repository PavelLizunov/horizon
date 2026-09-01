# AGENTS.md — Test Fixtures Guide

This directory contains static, deterministic test fixtures for offline evaluation.

## Fixture Invariants
- **Zero Secrets**: Fixtures MUST NOT contain real API keys, credentials, private session cookies, or sensitive tokens. Use explicit dummy tokens (`test_key_123`, `example.com`).
- **Minimal & Stable**: Keep fixture payloads as minimal as possible while covering required test conditions. Do not add unused fields or bloated payloads.
- **Deterministic & Immutable**: Fixture files are committed to version control and must yield identical test assertions across environments.
- **Schema Validation**: Synthetic fixtures must conform to the relevant Pydantic schema when one exists, or to the explicit test-local evidence/adjudication contract otherwise.

## Active Fixtures Inventory

- `tests/fixtures/verification_adversarial.json`:
  - **Purpose**: Ground-truth adversarial dataset for evaluating claim corroboration and Evidence Ledger adjudication logic.
  - **Used by**: `tests/test_verification_evaluation.py`

## Rules for Adding Fixtures
1. Verify no secret or environment-specific data is present.
2. Format JSON files with standard 2-space indentation.
3. Reference new fixtures from `tests/fixtures/AGENTS.md` and keep them minimal.

## Inheritance
Inherits from `tests/AGENTS.md` and root `AGENTS.md`.
