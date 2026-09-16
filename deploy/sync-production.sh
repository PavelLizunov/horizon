#!/bin/bash
# ==============================================================================
# deploy/sync-production.sh
#
# One-shot synchronization of code, profiles, config, and credentials
# from this development environment (harness-test) to the production pipeline
# container (LXC 213 on pve-ninitux).
#
# Usage:
#   ./deploy/sync-production.sh [--check-only] [--skip-git]
# ==============================================================================

set -euo pipefail

PROD_NODE="${HORIZON_PROD_NODE:-pve-ninitux}"
PROD_CTID="${HORIZON_PROD_CTID:-213}"
PROD_DIR="/opt/horizon"

log() { printf '\033[1;34m[sync-prod]\033[0m %s\n' "$*"; }
err() { printf '\033[1;31m[sync-prod ERROR]\033[0m %s\n' "$*" >&2; }
ok()  { printf '\033[1;32m[sync-prod SUCCESS]\033[0m %s\n' "$*"; }

# 1. Verification of local state
if [ ! -f "pyproject.toml" ] || [ ! -d "profiles" ]; then
  err "Must be run from the root of the horizon repository."
  exit 1
fi

log "Checking connectivity to Proxmox node $PROD_NODE..."
if ! ssh -o BatchMode=yes -o ConnectTimeout=5 "$PROD_NODE" "true" 2>/dev/null; then
  err "Cannot reach Proxmox node '$PROD_NODE' via SSH. Check ~/.ssh/config and ProxyJump."
  exit 1
fi

log "Verifying LXC container $PROD_CTID status..."
CT_STATUS=$(ssh -o BatchMode=yes "$PROD_NODE" "pct status $PROD_CTID 2>/dev/null | awk '{print \$2}'")
if [ "$CT_STATUS" != "running" ]; then
  err "LXC $PROD_CTID is not running (status: '$CT_STATUS')."
  exit 1
fi

# 2. Git sync to production
if [ "${1:-}" != "--skip-git" ]; then
  log "Synchronizing git repository on LXC $PROD_CTID..."
  ssh -o BatchMode=yes "$PROD_NODE" "pct exec $PROD_CTID -- runuser -u horizon -- sh -c '
    cd $PROD_DIR && \
    git checkout -- docs/checks.md docs/collection.md docs/digest/index.md 2>/dev/null || true && \
    git fetch origin main && \
    git reset --hard origin/main
  '"
  ok "LXC $PROD_CTID git repository updated to latest origin/main."
fi

# 3. Synchronize data/config.json
if [ -f "data/config.json" ]; then
  log "Synchronizing data/config.json to LXC $PROD_CTID..."
  cat "data/config.json" | ssh -o BatchMode=yes "$PROD_NODE" "pct exec $PROD_CTID -- runuser -u horizon -- sh -c 'cat > $PROD_DIR/data/config.json'"
  ok "data/config.json synchronized."
fi

# 4. Synchronize TELEGRAM_WEBHOOK_URL in .env if present
if [ -f ".env" ]; then
  LOCAL_TG_URL=$(grep "^TELEGRAM_WEBHOOK_URL=" .env | cut -d'=' -f2- || true)
  if [ -n "$LOCAL_TG_URL" ]; then
    log "Updating TELEGRAM_WEBHOOK_URL in /opt/horizon/.env..."
    ssh -o BatchMode=yes "$PROD_NODE" "pct exec $PROD_CTID -- runuser -u horizon -- python3 -c '
from pathlib import Path
env_path = Path(\"$PROD_DIR/.env\")
lines = env_path.read_text(encoding=\"utf-8\").splitlines() if env_path.exists() else []
key = \"TELEGRAM_WEBHOOK_URL\"
val = \"$LOCAL_TG_URL\"
replaced = False
for i, line in enumerate(lines):
    if line.startswith(f\"{key}=\"):
        lines[i] = f\"{key}={val}\"
        replaced = True
        break
if not replaced:
    lines.append(f\"{key}={val}\")
env_path.write_text(\"\n\".join(lines) + \"\n\", encoding=\"utf-8\")
'"
    ok "TELEGRAM_WEBHOOK_URL synchronized in production .env."
  fi
fi

# 5. Production validation check
log "Running Pydantic and ProfileRegistry validation on LXC $PROD_CTID..."
ssh -o BatchMode=yes "$PROD_NODE" "pct exec $PROD_CTID -- runuser -u horizon -- $PROD_DIR/.venv/bin/python3 -c '
import json
from pathlib import Path
from src.models import Config
from src.processing.profiles import ProfileRegistry

with open(\"$PROD_DIR/data/config.json\") as f:
    cfg = Config.model_validate(json.load(f))
reg = ProfileRegistry.load(Path(\"$PROD_DIR/profiles\"), default_profile=cfg.processing.default_profile)
reg.validate_source_references(cfg.sources.model_dump())
print(\"  Production profiles count:\", len(reg.ids))
print(\"  Production webhook delivery:\", cfg.webhook.delivery)
print(\"  Production webhook link_base:\", cfg.webhook.link_base)
'"
ok "Production configuration and profile registry are valid!"

# 6. Check timers
log "Active systemd timers on LXC $PROD_CTID:"
ssh -o BatchMode=yes "$PROD_NODE" "pct exec $PROD_CTID -- systemctl list-timers 'horizon-*' --no-pager"

ok "Production synchronization completed successfully!"
