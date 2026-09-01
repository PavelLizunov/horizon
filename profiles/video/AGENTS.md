# Video Profile Guide (`video`)

Local guide for the `video` processing profile directory.

## 1. Actual Purpose & Domain

Processes YouTube channel videos ingested as subtitle transcripts, local Whisper ASR text, or AI visual summaries from storyboard frames, combined with channel descriptions.

- **Routes Here**: Tech overviews, software releases, live demonstrations, homelab/self-hosting guides, developer tutorials, AI news commentary delivered via video.
- **Routes Elsewhere**: Written news articles/press releases (route to `tech-news`). Long-form written engineering blogs (route to `tech-blog`). Pure vlogs, livestream placeholders, non-informational content (reject/filter out).

## 2. High-Signal Filters & Rubric Summary

- **High Signal (Score 7–10)**: First-look demonstrations of major releases, hands-on tool walkthroughs, homelab setups with concrete configs, deep technical commentary with specific benchmarks/numbers.
- **Low Signal (Score 0–4)**: Pure promotional pitches, clickbait titles without substance, routine shallow news rehash, livestream placeholders.

## 3. Evidence & Safety Invariants

- **Spoken Language Tolerance**: Spoken transcripts are naturally loose and informal. Evaluation scoring MUST judge informational substance (claims, tools, figures, releases) rather than penalizing transcript style or lack of editorial polish.
- **Visual Evidence Integrity**: On-screen text captured in vision fallback summaries counts as valid concrete detail.
- **Text Budget & Sampling**: Configured for `sampling: "head-middle-tail"` (`analysis_max_chars`: 12000, `enrichment_max_chars`: 24000) to capture long video transcripts evenly.
- **Deep Dive Invariant**: Include the `deep_dive` block (4–6 sentences) only when a full transcript is available.

## 4. Structural Schema & Web Search

- **Enrichment Blocks**:
  - `summary` (required, primary, tools: `[]`): 3–5 sentences summarizing topic, demonstrations, tools, versions, and on-screen facts.
  - `background` (required, tools: `["web_search"]`): 2–3 sentences explaining prerequisite concepts or context.
  - `impact` (optional, tools: `["web_search"]`): 1 concise sentence on concrete consequence.
  - `deep_dive` (optional, tools: `[]`): 4–6 sentences drilling into detailed commands, steps, or configs (requires full transcript).

## 5. Focused Verification

```bash
.venv/bin/pytest tests/test_profiles.py -q
.venv/bin/pytest tests/test_video.py -q
```
