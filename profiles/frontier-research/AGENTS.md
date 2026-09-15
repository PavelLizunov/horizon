# Frontier AI Research Profile Guide (`frontier-research`)

Local guide for the `frontier-research` processing profile directory.

## 1. Actual Purpose & Domain

Processes scientific research, arXiv preprints, foundational model architecture papers, reasoning breakthroughs (test-time compute scaling, GRPO, verification loops), attention mechanisms (MLA, linear attention), and synthetic data distillation.

- **Routes Here**: DeepSeek-R1 / OpenAI o1/o3 algorithmic papers, GRPO implementations, MLA attention compression papers, Mamba 2/SSM research, self-play post-training.
- **Routes Elsewhere**: Agent coding tools and runtimes (route to `agentic-harnesses`). Commercial API pricing and quotas (route to `paid-ai-platforms`). Practical token reduction and prompt caching (route to `token-frugality`).

## 2. High-Signal Filters & Focus Areas

- **High Signal (Score 7–10)**: Novel training paradigms (RL with verifiable rewards), architectural improvements reducing memory/compute, mathematical explanations of reasoning emergence, open-weight reasoning releases.
- **Low Signal (Score 0–4)**: Derivative preprints without code/ablations, repetitive prompt engineering papers, speculative commentary.

## 3. Structural Schema & Web Search

- **Content Limits**: `analysis_max_chars`: 6000, `enrichment_max_chars`: 16000, `sampling`: `"head-middle-tail"`.
- **Enrichment Blocks**:
  - `summary` (required, primary, tools: `[]`)
  - `core_mechanism` (required, tools: `["web_search"]`)
  - `practical_implications` (optional, tools: `[]`)

## 4. Focused Verification

```bash
.venv/bin/pytest tests/test_profiles.py -q
```
