#!/bin/zsh
# Daily job: run the pipeline, then build and ship the site.
#
# These were two steps and only the first was scheduled, so the digest ran,
# Telegram headlines went out, and every link 404'd because the site was never
# rebuilt. launchd should call THIS, not `horizon` directly.
#
# Ordering note: the pipeline sends its headlines before this script builds, so
# links are dead for the few seconds the build takes. That window is accepted —
# closing it would mean pulling a site toolchain into the pipeline itself.

set -u
cd "${HORIZON_DIR:-$HOME/horizon}" || exit 1

# launchd gives a non-interactive shell almost no PATH.
export PATH="$HOME/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

log() { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }

log "pipeline: start"
.venv/bin/horizon --hours "${HORIZON_HOURS:-24}"
pipeline_status=$?
log "pipeline: exit $pipeline_status"

# Build and ship even when the pipeline failed partway: it may still have
# published pages before dying, and shipping a stale site helps nobody.
# mkdocs comes from `uv tool install` under ~/bin — deliberately not /tmp,
# which is wiped on reboot.
if [[ ! -x "$HOME/bin/mkdocs" ]]; then
  log "site: SKIPPED — ~/bin/mkdocs missing (uv tool install mkdocs --with mkdocs-material)"
  exit $pipeline_status
fi

log "site: build"
if ! "$HOME/bin/mkdocs" build --quiet; then
  log "site: build FAILED — not shipping, previous site stays up"
  exit 1
fi

: "${HORIZON_SITE_HOST:=root@192.168.0.210}"
: "${HORIZON_SITE_PATH:=/srv/digest.ninitux.com}"

log "site: ship to $HORIZON_SITE_HOST:$HORIZON_SITE_PATH"
# tar over ssh rather than rsync: the ingress container has no rsync, and
# installing packages on an edge proxy to copy static files is a poor trade.
if (cd site && tar czf - .) | ssh -o BatchMode=yes "$HORIZON_SITE_HOST" \
      "rm -rf '$HORIZON_SITE_PATH'/* && tar xzf - -C '$HORIZON_SITE_PATH'"; then
  log "site: shipped"
else
  log "site: ship FAILED — pages built locally but the live site is stale"
  exit 1
fi

exit $pipeline_status
