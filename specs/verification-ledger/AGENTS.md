# Evidence Ledger & Verification SDD Guide (`specs/verification-ledger/AGENTS.md`)

This directory governs the Evidence Ledger fact-checking engine, claim extraction, search query orchestration, corroboration evaluation, and sanitized public markdown rendering.

## 1. Document Trio Authority & Status

- **`spec.md`**: Defines claim extraction bounds (1–3 factual claims per article), search retrieval protocol, older corroboration statuses (`supported`, `partially_supported`, `disputed`, `unverified`), and public presentation rules. The implementation now serializes a different versioned vocabulary (`supported_by_evidence`, `contradicted_by_evidence`, `mixed_evidence`, `insufficient_evidence`, etc.); this contract drift needs an explicit migration decision, not a silent terminology edit.
- **`plan.md`**: Component boundaries across `src/verification/{claims,evidence,fetch,ledger,audit,incidents,evaluation}.py`, `src/ai/summarizer.py`, and `scripts/dev_verification_status.py`.
- **`tasks.md`**: Implementation checklist. Changes must stay in sync with `src/verification/`, its orchestrator/summarizer integration, and verification status tooling.
- **Hierarchy & Traceability**: `spec.md` > `plan.md` > `tasks.md`. Claim corroboration specs map directly to verification evaluators and offline unit tests.

## 2. Local Non-Negotiable Invariants

1. **Public Error Sanitization**: Internal error states (`verification_error`, `check_error`, `check_failed`, `not_checked`) must NEVER be rendered on public site pages or article banners. Readers see corroborated factual notes or nothing.
2. **Usage Policy Is Unresolved**: This spec says token/dollar estimates stay internal and article banners do omit them. However, the current checks-page generator publishes usage with `include_usage=True`, with regression tests and changelog support. Preserve that tested behavior until an owner-approved decision updates this spec, the constitution, implementation, tests, and changelog together.
3. **Evaluator Isolation**: The corroboration evaluator operates strictly on reader-facing article text and retrieved search results — it never inherits or accesses the generation prompt context.
4. **Graceful Search Fallback**: Search rate limits, timeouts, or network blocks must degrade gracefully by omitting uncorroborated claim banners, without blocking or breaking digest article publication.
