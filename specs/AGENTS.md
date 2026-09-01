# Specs Root Guide (`specs/AGENTS.md`)

This directory contains the Spec-Driven Development (SDD) specifications, architectural plans, and task breakdowns for Horizon.

## 1. SDD Structure & Authority Hierarchy

All major features and architectural components in Horizon follow Spec-Driven Development (Constitution §1.1, §11). Each feature directory under `specs/` is organized into a standardized document trio:

1. **`spec.md` (Functional Specification)**:
   - **Authority**: Primary source of truth for feature goals, requirements, data contracts, and user-facing behavior.
   - Defines *WHAT* the feature must achieve and *WHAT* constraints must be satisfied.
2. **`plan.md` (Architecture Plan)**:
   - **Authority**: Source of truth for technical design, component boundaries, execution flow, and testing strategy.
   - Defines *HOW* the requirements in `spec.md` are implemented.
3. **`tasks.md` (Implementation Checklist)**:
   - **Authority**: Executable status record for tracking implementation work.
   - Maps plan requirements into testable, granular items with completion checkboxes (`- [x]` / `- [ ]`).

**Hierarchy Precedence**: `spec.md` > `plan.md` > `tasks.md`. If implementation realities require architectural adjustments, update `spec.md` and `plan.md` before updating `tasks.md` or writing code. Do not rewrite historical specifications without explicit authorization.

## 2. Status Consistency Rules

- **Codebase Synchronization**: The completion state in `tasks.md` (`- [x]`) must accurately reflect verified, committed code and passing offline tests.
- **Synchronous Updates**: When modifying feature scope or design, update `spec.md`, `plan.md`, and `tasks.md` in lockstep.
- **Task Protection**: Do not mark unverified tasks complete or modify completed task statuses without verification.

## 3. Acceptance-Criteria Traceability

- Every functional requirement in `spec.md` must map to technical components in `plan.md` and explicit checklist items in `tasks.md`.
- Acceptance criteria are verified mechanically through offline unit tests under `tests/`.

## 4. Cross-Cutting Invariants

- **Offline Testing Discipline**: The `pytest` suite must pass entirely offline without network access or live API keys (Constitution §2.1).
- **Cost Discipline**: LLM commands incur token costs. Default to offline `pytest`; consult `scripts/AGENTS.md` before any script because several `dev_check_*` commands use live network or paid models. Never run the full pipeline without owner approval (Constitution §2.2).
- **Secret Isolation**: Credentials and cookies must never be committed or logged. Secrets are stored via environment variable references (`api_key_env`) (Constitution §1.5, §5).
- **Evaluator Segregation**: A model must never grade its own generated output (Constitution §2.3).
- **Honest Public Presentation**: Article pages sanitize internal error states and omit usage details. The public checks page currently exposes usage under a tested contract that conflicts with Constitution §1.4; changing it requires an explicit owner decision and synchronized spec/code/test updates.
