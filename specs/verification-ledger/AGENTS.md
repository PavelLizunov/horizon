# Evidence Ledger & Verification SDD Guide (`specs/verification-ledger/AGENTS.md`)

This directory governs the Evidence Ledger fact-checking engine, claim extraction, search query orchestration, corroboration evaluation, and sanitized public markdown rendering.

## 1. Document Trio Authority & Status

- **`spec.md`**: Defines claim extraction bounds (1–3 factual claims per article), search retrieval, the current six-value serialized `VerificationStatus` vocabulary, and public presentation rules. Historical proposal terms (`supported`, `partially_supported`, `disputed`, `unverified`) remain identified as non-contractual history rather than aliases.
- **`plan.md`**: Component boundaries across `src/verification/{claims,evidence,fetch,ledger,audit,incidents,evaluation}.py`, `src/ai/summarizer.py`, and `scripts/dev_verification_status.py`.
- **`tasks.md`**: Implementation checklist. Changes must stay in sync with `src/verification/`, its orchestrator/summarizer integration, and verification status tooling.
- **Hierarchy & Traceability**: `spec.md` > `plan.md` > `tasks.md`. Claim corroboration specs map directly to verification evaluators and offline unit tests.

## 2. Local Non-Negotiable Invariants

1. **Public Error Sanitization**: Current internal states (`verification_error`, `check_error`, `not_checked`) and legacy/defensive `check_failed` inputs must NEVER be rendered on public site pages or article banners. Readers may see conservative coverage labels, but never operational failure text.
2. **Usage Policy Is Unresolved**: Preserve the tested article/checks-page split described canonically in [`spec.md` §3](spec.md#3-open-usage-publication-decision) until an owner-approved synchronized policy change.
3. **Evaluator Isolation**: The corroboration evaluator operates strictly on reader-facing article text and retrieved search results — it never inherits or accesses the generation prompt context.
4. **Graceful Search Fallback**: Search rate limits, timeouts, or network blocks must not block publication or expose operational errors. Healthy inconclusive checks may still render conservative coverage labels.
