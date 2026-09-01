# Financial News Profile Guide (`finance-news`)

Local guide for the `finance-news` processing profile directory.

## 1. Actual Purpose & Domain

Processes news where money, financial markets, companies, macroeconomics, or economic policy are the primary topic, rather than technology implementation itself.

- **Routes Here**: Macroeconomic data, monetary/fiscal policy, stock/bond market moves, inflation, earnings reports, corporate funding, M&A, valuations, financial regulation, industry policy with material economic consequences.
- **Routes Elsewhere**: Product releases, software updates, technical security incidents, engineering developments (route to `tech-news`). Complete technical essays/case studies (route to `tech-blog`).

## 2. High-Signal Filters & Rubric Summary

- **High Signal (Score 7–10)**: Systemic policy shifts, severe market disruptions, landmark regulations, major earnings surprises, significant funding/acquisition activity.
- **Low Signal (Score 0–4)**: Routine price movements without context, expected results, small transactions, unsupported forecasts, generic personal-finance advice, promotional investment pitch material.

## 3. Evidence & Safety Invariants

- **Numeric & Baseline Integrity**: Preserve currencies, units, fiscal or calendar periods, and comparison baselines. Never omit baseline figures when available; never present percentage moves without starting values.
- **Fact vs Opinion Distinction**: Distinguish reported actual results from forecasts, analyst estimates, proposals, or allegations. Always attribute company claims and forecasts to their source.
- **Safety Boundaries**: Never calculate missing financial values, infer causation from correlation, give investment advice, recommend trades, or predict price movements.

## 4. Structural Schema & Web Search

- **Content Limits**: `analysis_max_chars`: 4000, `enrichment_max_chars`: 8000, `sampling`: `"prefix"`.
- **Enrichment Blocks**:
  - `summary` (required, primary, tools: `[]`): 1–2 short sentences with event and key financial figure.
  - `background` (required, tools: `["web_search"]`): 1–2 sentences explaining prior context or institutional mechanism.
  - `impact` (optional, tools: `["web_search"]`): 1 short sentence on direct economic impact on specific groups/markets.

## 5. Focused Verification

```bash
.venv/bin/pytest tests/test_profiles.py -q
```
