# Evidence Ledger Architecture Plan

## 1. Component Boundaries
* `src/verification/`: Evidence Ledger fact-checking engine (`claims.py`, `evidence.py`, `fetch.py`, `ledger.py`, `audit.py`, `incidents.py`, `evaluation.py`). *(Historical paths `src/services/verification.py` and `src/services/verification_evaluator.py` were relocated to `src/verification/` package; see `specs/verification-ledger/AGENTS.md` §1).*
* `src/ai/summarizer.py`: Public markdown badge and footnote markup generator (`verification_site_markup`, `verification_summary_markup`).
* `scripts/dev_verification_status.py`: Offline inspector, token usage accountant, and article page sanitizer.

## 2. Invariants
* Public markdown suppresses operational states such as `check_error` and `not_checked`; healthy but inconclusive results may render conservative `provisional` or `insufficient` coverage labels.
* Evaluator never uses the generation context; operates strictly on reader-facing text and retrieved search results.
* Preserve the unresolved article/checks-page usage split defined in [`spec.md` §3](spec.md#3-open-usage-publication-decision).
