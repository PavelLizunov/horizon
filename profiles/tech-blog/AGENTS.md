# Technology Blog Profile Guide (`tech-blog`)

Local guide for the `tech-blog` processing profile directory.

## 1. Actual Purpose & Domain

Processes long-form technical writing whose primary value is explanation, architectural reasoning, implementation experience, or durable engineering insight rather than immediate event reporting.

- **Routes Here**: Engineering deep dives, architecture discussions, postmortems, performance investigations, technical tutorials with substantive reasoning, case studies, technical essays.
- **Routes Elsewhere**: Event news, release announcements, press coverage (route to `tech-news`). Video transcripts (route to `video`). API ref docs, thin SEO tutorials, marketing blogs (reject/filter out).

## 2. High-Signal Filters & Rubric Summary

- **High Signal (Score 7–10)**: Original or exceptionally clear technical insights, strong evidence from first-hand engineering experience, concrete performance data, transferable lessons beyond the specific project. Score the text content, not author or company reputation.
- **Low Signal (Score 0–4)**: Repackaged documentation, step lists without tradeoff explanations, unsupported vendor claims, SEO-optimized promotional posts.

## 3. Evidence & Safety Invariants

- **Sampling & Text Budget**: Configured for `sampling: "head-middle-tail"` with higher input character caps (`analysis_max_chars`: 16000, `enrichment_max_chars`: 24000) to preserve long-form article structure.
- **Narrative Integrity**: Retells the post as a connected 5–8 sentence story across blocks (Chinese target ~300–500 characters; English target ~150–250 words; comparable reading length for Russian and other languages). Block titles must be localized to the digest language.
- **Faithful Representation**: Attribute arguments and unverified claims to the author. Preserve baselines, test conditions, tradeoffs, and limitations. Never invent missing details or data.

## 4. Structural Schema & Tools

- **Enrichment Blocks** (All tools: `[]` — pure source synthesis without external web search):
  - `background` (required): Problem/motivation and context (1–2 sentences).
  - `solution` (required): Core technical insight, key mechanisms, and evidence.
  - `takeaway` (required): 1–2 sentence distillation of author's thesis/conclusion.

## 5. Focused Verification

```bash
.venv/bin/pytest tests/test_profiles.py -q
```
