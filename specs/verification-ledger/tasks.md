# Evidence Ledger Tasks & Implementation Checklist

- [x] Implement claim extraction and search orchestration (`src/verification/claims.py`, `evidence.py`, `fetch.py`; formerly `src/services/verification.py`).
- [x] Implement independent corroboration evaluation in `src/verification/evidence.py` and its offline adversarial harness in `src/verification/evaluation.py` (formerly `src/services/verification_evaluator.py`).
- [x] Implement token and cost accounting in verification ledger (`data/verification/runs/`).
- [x] Sanitize public article pages: strip failed verification banners, empty sections, and dollar estimates.
- [x] Add verification documentation under `docs/verification/` and `docs/checks.md`.
- [x] Add automated unit tests for verification serialization and markup rendering.
