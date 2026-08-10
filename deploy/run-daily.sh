#!/bin/zsh
# Daily job: run the pipeline, narrate what it published, then build and ship.
#
# These were two steps and only the first was scheduled, so the digest ran,
# Telegram headlines went out, and every link 404'd because the site was never
# rebuilt. launchd should call THIS, not `horizon` directly.
#
# Ordering matters in one place: narration edits the published markdown to add
# the player, so it has to finish before mkdocs reads those files. Everything
# after the pipeline is best-effort — a failure there leaves a readable digest
# rather than none.
#
# Ordering note: the pipeline sends its headlines before this script builds, so
# links are dead for the few seconds the build takes. That window is accepted —
# closing it would mean pulling a site toolchain into the pipeline itself.
# Narration adds about twenty seconds per article to that window.

set -u
cd "${HORIZON_DIR:-$HOME/horizon}" || exit 1

# launchd gives a non-interactive shell almost no PATH.
export PATH="$HOME/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

log() { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }

log "pipeline: start"
.venv/bin/horizon --hours "${HORIZON_HOURS:-24}"
pipeline_status=$?
log "pipeline: exit $pipeline_status"

# The archive index is generated from the issues on disk, and it is also tracked
# so a fresh clone can build. Any git operation on this machine restores the
# "no issues yet" placeholder over the real listing, and nothing looks wrong
# until someone opens the archive. Regenerate before every build.
log "index: regenerate"
.venv/bin/python -c \
  'from src.storage.manager import StorageManager; StorageManager.write_site_index()' \
  || log "index: FAILED — the archive page may list nothing"

# Narration. Two interpreters on purpose: preparing the text needs the project's
# dependencies, and TeraTTSv2 needs onnxruntime and transformers, which live in
# a venv of their own and have no business in this one.
#
# Never fatal. A day without audio is a day with a readable digest; a day with
# no digest because the speech model failed is not a trade worth making.
issue=$(ls -1 docs/digest 2>/dev/null | grep -E '^[0-9]{4}-[0-9]{2}-[0-9]{2}-' | sort | tail -1)
narrator="${HORIZON_TTS_PYTHON:-$HOME/tts/.venv/bin/python}"
if [[ -z "$issue" ]]; then
  log "narration: SKIPPED — no issue directory in docs/digest"
elif [[ ! -x "$narrator" ]]; then
  log "narration: SKIPPED — no interpreter at $narrator"
else
  work="${TMPDIR:-/tmp}/horizon-narration"
  rm -rf "$work" && mkdir -p "$work"
  log "narration: $issue"
  if .venv/bin/python scripts/dev_narrate_article.py --issue "$issue" \
        --write-all "$work" >/dev/null; then
    # --attach edits the published pages, so this has to finish before mkdocs
    # reads them. An article that fails its check is left unlinked rather than
    # published, and that exit code is reported, not obeyed.
    "$narrator" scripts/dev_narrate_article.py --speak-dir "$work" --attach \
      || log "narration: some articles did not pass their check and were not linked"
  else
    log "narration: FAILED to prepare text — pages keep whatever audio they had"
  fi
  rm -rf "$work"
fi

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
