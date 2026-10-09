# ARC Raiders Profile Guide (`arc-raiders`)

Local guide for the `arc-raiders` processing profile directory.

## 1. Actual Purpose & Domain

Processes news, announcements, patch notes, updates, leaks, datamines, playtests, and community discussions specifically for the multiplayer PvPvE extraction shooter **ARC Raiders** (developed by Embark Studios).

- **Routes Here**: ARC Raiders Steam updates, Embark Studios announcements, r/ArcRaiders community discoveries and rumors, gaming press coverage of ARC Raiders.
- **Routes Elsewhere**: General AI/coding topics (route to `tech-news` or `agentic-harnesses`), other games (The Finals, etc.).

## 2. High-Signal Filters & Focus Areas

- **High Signal (Score 7–10)**: Major patches, new maps/expeditions, weapon balancing, anti-cheat updates, verified datamines, official release/beta dates.
- **Low Signal (Score 0–4)**: Generic highlight clips, low-effort memes, unverified vague rumors, LFG posts.

## 3. Structural Schema & Web Search

- **Content Limits**: `analysis_max_chars`: 4000, `enrichment_max_chars`: 10000, `sampling`: `"head-middle-tail"`.
- **Enrichment Blocks**:
  - `summary` (required, primary, tools: `[]`)
  - `gameplay_and_mechanics` (required, tools: `["web_search"]`)
  - `release_and_community` (optional, tools: `[]`)

## 4. Focused Verification

```bash
.venv/bin/pytest tests/test_profiles.py -q
```
