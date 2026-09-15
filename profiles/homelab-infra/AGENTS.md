# Homelab & Proxmox Profile Guide (`homelab-infra`)

Local guide for the `homelab-infra` processing profile directory.

## 1. Actual Purpose & Domain

Processes developments in home lab infrastructure, Proxmox VE, PDM, LXC containers, GPU passthrough (RTX 5060 Ti), Tailscale mesh networking, Beszel resource monitoring, Caddy reverse proxy, RustDesk, Vaultwarden, and self-hosted AI gateway architectures.

- **Routes Here**: Proxmox VE releases, NVIDIA Linux driver updates, Beszel agent/hub updates, Tailscale features, Caddy server releases, local GPU node setups.
- **Routes Elsewhere**: Public internet censorship and DPI bypass (route to `censorship-watch` or `vpn-engineering`). Speech/audio AI models (route to `speech-ai`). Token frugality algorithms (route to `token-frugality`).

## 2. High-Signal Filters & Focus Areas

- **High Signal (Score 7–10)**: Proxmox/Linux kernel updates, GPU passthrough guides, Beszel updates, critical security advisories for self-hosted services, Tailscale protocol improvements.
- **Low Signal (Score 0–4)**: Smart home consumer gadgets, cloud enterprise press releases without self-hosting utility, sponsored hardware ads.

## 3. Structural Schema & Web Search

- **Content Limits**: `analysis_max_chars`: 4000, `enrichment_max_chars`: 10000, `sampling`: `"prefix"`.
- **Enrichment Blocks**:
  - `summary` (required, primary, tools: `[]`)
  - `infrastructure_impact` (required, tools: `["web_search"]`)
  - `homelab_relevance` (optional, tools: `[]`)

## 4. Focused Verification

```bash
.venv/bin/pytest tests/test_profiles.py -q
```
