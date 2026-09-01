# Censorship Watch Profile Guide (`censorship-watch`)

Local guide for the `censorship-watch` processing profile directory.

## 1. Actual Purpose & Domain

Processes timely technical evidence regarding internet censorship, VPN/protocol blocking, DPI connection resets, active probing, BGP/ASN traffic throttling, app store removals, and regional or national internet shutdowns.

- **Routes Here**: Reproducible measurements, technical field reports (e.g. from 4PDA or forum topics), OONI/RIPE research reports, operator/ASN-specific disruption observations, official maintainer confirmations.
- **Routes Elsewhere**: Protocol engineering changes/release notes without active blocking evidence (route to `vpn-engineering`). Political commentary without network measurements (reject/filter out). Generic VPN marketing or SEO reviews (reject/filter out).

## 2. High-Signal Filters & Hard Calibration Rules

- **High Signal (Score 8–10)**: Reproducible new blocking mechanisms, critical nationwide events, or major protocol disruptions supported by multi-network measurements.
- **Hard Calibration Rules** (Enforced in `analysis.md`):
  - **Single Field Report Cap**: A single uncorroborated field report CANNOT score above **5.9** (must not enter digest default filter threshold).
  - **No Regional Bias**: Russian events receive no automatic credibility boost.
  - **Outage vs Censorship**: A general power/infrastructure outage must never be labeled as targeted VPN blocking.
  - **OONI Signal Handling**: Treat OONI anomalies as preliminary signals, not proof of mechanism.

## 3. Evidence & Safety Invariants

- **Observational Precision**: Must specify place, time, affected ASN/operator, and target protocol/traffic. Explicitly state when any observation parameters are unknown.
- **Safety & Bypass Policy**: NEVER publish bypass instructions, proxy credentials, or unverified operational workarounds.
- **No Manual Verification Banners**: Do NOT add `CONFIRMED` or `PROBABLE` labels in markdown output (the Evidence Ledger engine handles corroboration separately).

## 4. Structural Schema & Web Search

- **Content Limits**: `analysis_max_chars`: 6000, `enrichment_max_chars`: 12000, `sampling`: `"head-middle-tail"`.
- **Enrichment Blocks**:
  - `summary` (required, primary, tools: `[]`): 3–5 sentences stating observed facts, operator/ASN, protocols affected.
  - `alternative_explanation` (optional, tools: `["web_search"]`): Tests whether software bugs, server failures, or UDP degradation explain the issue.
  - `impact` (optional, tools: `[]`): Specifically affected users, networks, or fallback paths.
  - `what_to_watch_next` (optional, tools: `[]`): Missing measurements, packet captures, or OONI tests needed.

## 5. Focused Verification

```bash
.venv/bin/pytest tests/test_profiles.py -q
.venv/bin/pytest tests/test_fourpda.py -q
```
