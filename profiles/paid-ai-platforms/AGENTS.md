# Paid AI Platforms Profile Guide (`paid-ai-platforms`)

Local guide for the `paid-ai-platforms` processing profile directory.

## 1. Actual Purpose & Domain

Processes news and updates on commercial AI platforms, paid frontier APIs, token pricing structures, prompt caching discounts, subscription plans (ChatGPT, Claude, Google Antigravity, Codex), API rate limits (RPM/TPM), and gateway reverse-engineering/proxying infrastructure.

- **Routes Here**: API pricing changes, token rate cuts, tier/quota policy updates, subscription model shifts, benchmark comparisons (Artificial Analysis), AI gateway authentication and rate-limiting shifts.
- **Routes Elsewhere**: Pure open-weights models and local inference (route to `homelab-infra` or `frontier-research`). Agent harness runtimes and dev tools (route to `agentic-harnesses`). Frugality and KV-cache compression techniques (route to `token-frugality`).

## 2. High-Signal Filters & Focus Areas

- **High Signal (Score 7–10)**: Published price reductions, prompt caching cost shifts, batch API discount terms, tier progression changes, new paid model API availability.
- **Low Signal (Score 0–4)**: Corporate PR without pricing or technical specs, speculative rumors, affiliate promotions.

## 3. Structural Schema & Web Search

- **Content Limits**: `analysis_max_chars`: 4000, `enrichment_max_chars`: 10000, `sampling`: `"prefix"`.
- **Enrichment Blocks**:
  - `summary` (required, primary, tools: `[]`)
  - `pricing_and_quotas` (required, tools: `["web_search"]`)
  - `infrastructure_impact` (optional, tools: `["web_search"]`)

## 4. Focused Verification

```bash
.venv/bin/pytest tests/test_profiles.py -q
```
