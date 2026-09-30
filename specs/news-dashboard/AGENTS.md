# News Dashboard SDD Guide

Parent `specs/AGENTS.md` and the root guide apply.

- `spec.md` defines proposed dashboard behavior and the additive public catalog v1.
  `plan.md` owns build/UI integration; `tasks.md` tracks verified implementation.
- Implementation and one production rollout were approved and completed; evidence
  is in `visual-rollout.md`. New live mutations require fresh task scope; no service
  restart is implicitly authorized.
- Preserve published article/issue URLs and search API contracts. Reuse current
  scores/classification and the existing pure archive parser; never fabricate
  scores/source labels or silently truncate old articles.
- V1 covers are trusted deterministic SVG templates. No generative model/service
  is needed; adding one changes scope.
- Rebuild metadata with every site build, including ship-only narration refresh.
  Catalog audio readiness must follow an attached validated player, not loose files.
- No private archive/config, reasoning, cost, token or operational verification
  state belongs in generated public catalog data or tracked task artifacts.
- Verify native MkDocs hooks in the separate site interpreter, direct-link history,
  instant navigation, no-JS links, and storage-failure degradation. Keep completed
  task statuses consistent with committed tests and observed build/browser evidence.
