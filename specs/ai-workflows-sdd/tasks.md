# AI Workflows & SDD Tasks & Implementation Checklist

- [x] Implement category-specific threshold overrides in `src/models.py` and `src/orchestrator.py`.
- [x] Add tag classification mapping for SDD, agentic workflows, and vibe coding in `src/orchestrator.py`.
- [x] Update `profiles/tech-news/analysis.md` scoring prompt with guidelines for SDD and AI engineering methodologies.
- [x] Add the `ai-tools-workflows` group to tracked `data/config.example.json`. Live `data/config.json` remains untracked operator state and is not asserted by this checklist.
- [x] Add test coverage for category threshold overrides (`tests/test_category_thresholds.py`).
