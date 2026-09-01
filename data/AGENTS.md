# data/AGENTS.md — Local Guide for `data/` Directory

This directory contains configuration templates, domain presets, and runtime state/outputs for Horizon.

## 1. Directory Layout: Tracked vs Gitignored

### Tracked Files (Git Controlled)
- `config.example.json`: Primary configuration template and reference schema.
- `config.github.json`: Alternative example configuration (e.g., CI/GitHub Actions).
- `presets.json`: Domain-specific source bundles (AI/ML, Systems, Security, WebDev, PL, Embedded, DevTools, Science).
- `AGENTS.md`: This directory guide; runtime config loading ignores it.

### Gitignored Live State & Secrets (NEVER Commit, Inspect, or Print)
- **Live Configs & Credentials**: `config.json`, `config.json.*`, `*.bak`, `youtube-cookies*.txt`, `x_cookies_*.json`, `mcp.secrets.json`, `mcp-secrets.json`.
- **Runtime Memory & Tracking**: `seen.json`, `subscribers.json`, `video-inbox.json`, `ab-items.json`, `ab-results.json`, `incidents.json`.
- **Runtime Output Directories**: `summaries/`, `mcp-runs/`, `verification/`, `pronunciation-candidates/`, `pronunciation-reviews/`.

## 2. Hard Invariants & Constraints

1. **Secrets Isolation**: Never place raw API keys, session tokens, or credentials in tracked JSON files. Config files store environment variable names (e.g., `"api_key_env": "OPENAI_API_KEY"`), loaded via `.env`.
2. **Secret Privacy**: Never inspect, print, stage, or commit gitignored secret/state files (`config.json`, `youtube-cookies*.txt`, `.env`).
3. **Config & Model Parity**: `data/config.example.json` must remain valid against `Config` in `src/models.py`. Any new configuration fields or schema changes in `src/models.py` must be mirrored in `config.example.json`.
4. **Valid JSON**: Tracked JSON files must be strictly valid JSON (parseable by standard JSON parsers).

## 3. Schema & API Compatibility

- Pydantic models in `src/models.py` enforce `extra="forbid"` on top-level models (e.g., `Config`, `DigestConfig`). Unrecognized configuration keys cause startup validation failures.
- File paths defined in configs (e.g., `profiles_dir`, `inbox_file`) are relative to the root working directory.

## 4. Verification

Run offline validation of tracked JSON examples against python parsing and `src/models.py`:

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path
from src.models import Config

for name in ("config.example.json", "config.github.json"):
    Config.model_validate(json.loads((Path("data") / name).read_text()))
json.loads(Path("data/presets.json").read_text())
print("All tracked data JSON files validated successfully.")
PY
```
