# VPN Engineering Profile Guide (`vpn-engineering`)

Local guide for the `vpn-engineering` processing profile directory.

## 1. Actual Purpose & Domain

Processes timely engineering developments in VPN, proxy, traffic obfuscation, tunneling, censorship circumvention, and related networking projects.

- **Routes Here**: Substantial releases, new protocols/transports, breaking config changes, deprecations, security advisories, supply-chain incidents, active probing countermeasures, DNS/TUN/routing changes, platform compatibility updates, client removals from official distribution channels.
- **Routes Elsewhere**: Active censorship blocking incidents/field reports (route to `censorship-watch`). Generic VPN reviews, rankings, affiliate spam, discount codes, user connectivity complaints (reject/filter out).

## 2. High-Signal Filters & Rubric Summary

- **High Signal (Score 7–10)**: Critical vulnerabilities, supply-chain security incidents, major new transport/masking mechanisms, breaking migrations, verified detection resistance changes, major stable project releases.
- **Low Signal (Score 0–4)**: Routine bug fixes, configuration recipes, generic privacy advice, affiliate SEO lists, unsupported vendor claims of total DPI invisibility.

## 3. Evidence & Safety Invariants

- **Upstream Verification Discipline**: Prefer maintainer release notes, official advisories, commits, and reproducible research over vendor announcements or hype.
- **No Unsubstantiated Bypass Claims**: Never claim a tool bypasses censorship unless the source evidence specifies exact network conditions, region, operator, and date.
- **No Manual Verification Banners**: Do NOT add manual verification labels in markdown text (managed by Evidence Ledger).

## 4. Structural Schema & Web Search

- **Content Limits**: `analysis_max_chars`: 5000, `enrichment_max_chars`: 10000, `sampling`: `"head-middle-tail"`.
- **Enrichment Blocks**:
  - `summary` (required, primary, tools: `[]`): 3–5 sentences explaining exact changes, version/platform, constraints, and operational importance.
  - `impact` (optional, tools: `["web_search"]`): Concrete migration, security, or interoperability consequences.
  - `what_to_watch_next` (optional, tools: `[]`): Next release, measurement, or platform tests needed to settle uncertainty.

## 5. Focused Verification

```bash
.venv/bin/pytest tests/test_profiles.py -q
```
