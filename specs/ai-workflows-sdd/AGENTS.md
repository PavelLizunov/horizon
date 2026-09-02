# AI Workflows & SDD Guide (`specs/ai-workflows-sdd/AGENTS.md`)

This directory governs profile-driven scoring, category classification for AI engineering, Spec-Driven Development (SDD), agentic systems, and category threshold overrides.

## 1. Document Trio Authority & Status

- **`spec.md`**: Defines category threshold overrides (`category_thresholds`), editorial category groupings (`ai-tools-workflows`, `llm`, `ru-censorship`, `vpn-engine`), tag taxonomy, and target quality expectations.
- **`plan.md`**: Architecture for classification Pass 1 (`analyzer.py`), threshold filtering (`passes_profile_filter()`), balanced digest grouping (`apply_balanced_digest`), and enrichment Pass 2 (`enricher.py`).
- **`tasks.md`**: Implementation checklist. Changes must stay in sync with `src/models.py`, `src/orchestrator.py`, `src/ai/analyzer.py`, `profiles/tech-news/`, and `data/config.example.json`.
- **Hierarchy & Traceability**: `spec.md` > `plan.md` > `tasks.md`. Category thresholds and tag classifications map directly to `orchestrator.py` routing logic and offline tests.

## 2. Local Non-Negotiable Invariants

1. **Category Threshold Routing**: `src/orchestrator.py:passes_profile_filter()` evaluates a category-specific override (e.g. `sdd`, `ai-tools`, or `ai-workflows` at `4.5`) before the profile threshold. The schema default is `None` (fail open), `spec.md` records a historical `tech-news: 6.5` target, and `data/config.example.json` demonstrates `7.0`; each operator's runtime config is operationally authoritative.
2. **Measurement Over Assertion**: Classification prompts and threshold changes must be backed by measured token impact and offline test assertions (`tests/test_category_thresholds.py`).
3. **Digest Volume & Cost Discipline**: Item selection and token spend are controlled via category thresholds, `digest.max_items`, and `category_groups` limits in `apply_balanced_digest()`.
