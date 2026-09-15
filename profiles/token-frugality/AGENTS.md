# Token Frugality Profile Guide (`token-frugality`)

Local guide for the `token-frugality` processing profile directory.

## 1. Actual Purpose & Domain

Processes technical developments in token economy, prompt caching, KV-cache quantization, Multi-Token Prediction (MTP), speculative decoding, context pruning, anti-slop minimization, and inference serving engine optimizations (vLLM, ExLlamaV3, SGLang, MLX).

- **Routes Here**: Prompt caching methodologies, MTP benchmark results, ExLlamaV3/vLLM KV-cache quantization, model routing cascades, context compression techniques.
- **Routes Elsewhere**: General commercial API announcements (route to `paid-ai-platforms`). Theoretical mathematical AI papers (route to `frontier-research`). Agent coding tools (route to `agentic-harnesses`).

## 2. High-Signal Filters & Focus Areas

- **High Signal (Score 7–10)**: Measured token/cost reductions (>30%), speculative decoding speedups (>1.5x), prompt cache architecture guides, INT4/FP8 KV-cache breakthroughs.
- **Low Signal (Score 0–4)**: Generic prompt engineering tips, unbenchmarked claims, promotional AI tools without metrics.

## 3. Structural Schema & Web Search

- **Content Limits**: `analysis_max_chars`: 5000, `enrichment_max_chars`: 12000, `sampling`: `"head-middle-tail"`.
- **Enrichment Blocks**:
  - `summary` (required, primary, tools: `[]`)
  - `optimization_method` (required, tools: `["web_search"]`)
  - `efficiency_gains` (optional, tools: `[]`)

## 4. Focused Verification

```bash
.venv/bin/pytest tests/test_profiles.py -q
```
