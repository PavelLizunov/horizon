# Technology News Profile Guide (`tech-news`)

Local guide for the `tech-news` processing profile directory.

## 1. Actual Purpose & Domain

Processes timely developments in software engineering, artificial intelligence/ML, computer systems, open source projects, developer tooling, and technology industry announcements. Serving as Horizon's default profile (`ProcessingConfig.default_profile: "tech-news"`), it acts as the primary pipeline route for general tech news.

- **Routes Here**: Major software releases, AI model weights/breakthroughs, security advisories, engineering announcements, open-source developments, developer workflows.
- **Routes Elsewhere**: Long-form essays or architectural deep dives without immediate event news (route to `tech-blog`). Financial earnings/stock stories (route to `finance-news`). Video channel content (route to `video`). VPN/proxy protocol engineering (route to `vpn-engineering`).

## 2. High-Signal Filters & Focus Areas

- **High Signal (Score 7–10)**: Paradigm shifts, major open-weights LLM releases, local quantization (GGUF/EXL2), inference optimizations, Spec-Driven Development (SDD) / agentic dev tools, critical vulnerabilities, breakthroughs.
- **Low Signal (Score 0–4)**: Routine minor updates, promotional marketing press releases, hype without technical detail, exaggerated headlines.

## 3. Evidence & Safety Invariants

- **Fact Preservation**: Preserve exact names, version numbers, benchmarks, organization names, dates, compatibility constraints, and reported limitations.
- **Community Discussion Discipline**: Summarize consensus, disagreement, or field reports only when user comments are actually supplied in the source item.
- **Deep Dive Invariant**: Include the `deep_dive` block (4–6 sentences) only for rich, long-form transcript/article inputs. Omit for short news items.

## 4. Structural Schema & Web Search

- **Content Limits**: `analysis_max_chars`: 1000, `enrichment_max_chars`: 8000, `sampling`: `"prefix"`.
- **Enrichment Blocks**:
  - `summary` (required, primary, tools: `[]`): Main body (3–5 complete sentences covering what changed, why it matters, key details).
  - `background` (required, tools: `["web_search"]`): 2–3 sentences on required context/history.
  - `impact` (optional, tools: `["web_search"]`): 1 concise sentence on concrete consequences.
  - `community_discussion` (optional, tools: `[]`): 1–2 sentences summarizing comment consensus/concerns.
  - `deep_dive` (optional, tools: `[]`): 4–6 sentences drilling into detailed mechanisms for rich content.

## 5. Focused Verification

```bash
.venv/bin/pytest tests/test_profiles.py -q
```
