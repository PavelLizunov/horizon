# Evidence Ledger Architecture Plan

## 1. Component Boundaries
* `src/services/verification.py`: Verification runner, claim batching, and search query orchestrator.
* `src/services/verification_evaluator.py`: AI evaluator prompt formatters and response parser.
* `src/ai/summarizer.py`: Public markdown badge and footnote markup generator (`verification_site_markup`, `verification_summary_markup`).
* `scripts/dev_verification_status.py`: Offline inspector, token usage accountant, and article page sanitizer.

## 2. Invariants
* Public markdown banners are never emitted for `check_error`, `not_checked`, or uncorroborated items.
* Evaluator never uses the generation context; operates strictly on reader-facing text and retrieved search results.
