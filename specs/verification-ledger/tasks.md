# Evidence Ledger Tasks & Implementation Checklist

- [x] Implement claim extraction and search orchestration (`src/services/verification.py`).
- [x] Implement independent corroboration evaluator (`src/services/verification_evaluator.py`).
- [x] Implement token and cost accounting in verification ledger (`data/verification/runs/`).
- [x] Sanitize public article pages: strip failed verification banners, empty sections, and dollar estimates.
- [x] Add verification documentation under `docs/verification/` and `docs/checks.md`.
- [x] Add automated unit tests for verification serialization and markup rendering.
