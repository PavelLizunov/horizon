# AI Workflows & SDD Architecture Plan

## 1. Evaluation & Routing Flow
1. **Pass 1 (Classification & Scoring)**: `src/ai/analyzer.py` runs prompt `profiles/<profile>/analysis.md` to assign a score (0–10), category tag, and relevance rationale.
2. **Threshold Evaluation**: `src/processing/profiles.py:passes_profile_filter()` checks `category_thresholds` dictionary before comparing against default profile threshold.
3. **Digest Balancing**: `src/orchestrator.py:apply_balanced_digest()` groups selected items by `category_groups` limits (e.g. up to 4 items for `ai-tools-workflows`, 6 for `llm`).
4. **Pass 2 (Enrichment)**: `src/ai/enricher.py` runs `profiles/<profile>/enrichment.md` with search tools.
