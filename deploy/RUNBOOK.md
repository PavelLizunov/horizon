# Runbook — Operating the Production Hosts

This runbook covers an installed Horizon pipeline guest. Setup details are in
[README.md](README.md); the architecture contract is in
[`specs/linux-production`](../specs/linux-production/spec.md).

> Keep real hostnames, guest IDs, addresses, accounts, key fingerprints, proxy
> endpoints, and credentials in operator configuration—not this public file.

## Access and layout

Define a trusted SSH alias for the Proxmox node and keep the guest ID in your
local shell. The pipeline guest does not need an inbound SSH server:

```bash
export HORIZON_CTID='operator-owned-value'
ssh prod-node "pct exec $HORIZON_CTID -- systemctl is-system-running"
```

| Component | Production location |
|---|---|
| Exact Git checkout and gitignored state | `/opt/horizon` |
| Python entry points | `/opt/horizon/.venv/bin/` |
| Service home and outbound SSH identities | `/var/lib/horizon` |
| Installation cache | `/var/cache/horizon/uv` |
| Non-secret digest environment | `/etc/horizon/runtime.env` |
| Optional video-only proxy environment | `/etc/horizon/video-egress.env` |
| Logs | systemd journal |
| Shared execution lock | `/run/lock/horizon-production.lock` |

Elasticsearch and the public Search API run on a separate guest. The pipeline
gets only a restricted SSH forward to Elasticsearch loopback. Site publishing
uses a different forced-command identity.

## Routine status

```bash
ssh prod-node "pct exec $HORIZON_CTID -- systemctl status \
  horizon-search-tunnel.service horizon-video.timer horizon-digest.timer"
ssh prod-node "pct exec $HORIZON_CTID -- systemctl list-timers 'horizon-*'"
ssh prod-node "pct exec $HORIZON_CTID -- journalctl \
  -u horizon-digest.service -n 100 --no-pager"
```

A healthy installation has an active Search tunnel, inactive/exited one-shot
services between runs, and both timers waiting for their next daily slot.

## Manual acceptance or recovery run

`horizon` is a paid LLM workload. Obtain operator approval before starting the
digest service. The systemd unit supplies the same sandbox, environment, limits,
and lock used by the timer:

```bash
ssh prod-node "pct exec $HORIZON_CTID -- systemctl start horizon-video.service"
ssh prod-node "pct exec $HORIZON_CTID -- systemctl start horizon-digest.service"
```

Do not invoke the underlying Python command concurrently. Video refuses an
occupied shared lock; digest waits up to one hour for video to finish.

Watch progress without exposing secret files or full response bodies:

```bash
ssh prod-node "pct exec $HORIZON_CTID -- journalctl \
  -u horizon-video.service -f"
ssh prod-node "pct exec $HORIZON_CTID -- journalctl \
  -u horizon-digest.service -f"
```

Acceptance requires:

- service result `success` and exit status 0;
- a video summary showing zero ASR on Linux and at least one subtitles/vision
  extraction when videos are present;
- successful collection and AI analysis when new items exist;
- Search indexing and webhook delivery without fatal errors;
- both the site root and new issue returning HTTP 200;
- no model-gateway request errors;
- guest disk and memory below their limits.

## Linux-specific behavior

- `sources.video.asr` is `"off"`; extraction is subtitles then the configured
  vision model.
- Direct YouTube may be unavailable from the guest. Only the video service may
  load an explicitly approved HTTP CONNECT environment. Do not add proxy values
  to the digest, tunnel, SSH config, shell profile, or global system files.
- Narration is intentionally skipped through `HORIZON_TTS_PYTHON=/nonexistent`.
  The text site remains complete; audio returns only after an independent Linux
  grader is approved.
- `.env`, `data/config.json`, cookie jars, config backups, and private SSH keys
  are mode `0600` and never printed or committed.

## Site-only publication

`HORIZON_SHIP_ONLY=1 deploy/run-daily.sh` skips collection, AI work, and
narration, but **does replace the live site**. Use it only as an approved
production action. The destination identity is forced to a static publisher
that rejects unsafe tar members and normalizes directories to `0755` and files
to `0644`.

After any publish, verify the root and current issue through the live ingress.
A local `mkdocs build` alone does not prove publication.

## Video diagnostics

The source degrades rather than aborting. Inspect these lines first:

```bash
ssh prod-node "pct exec $HORIZON_CTID -- journalctl \
  -u horizon-video.service --since today --no-pager" \
  | grep -E 'Video preflight:|Video run'
```

`Video run degraded`, bot-gate warnings, or repeated subtitle failures require
checking cookies and the approved video egress. A bounded parser/fetch check is
networked even when it does not call the vision model:

```bash
ssh prod-node "pct exec $HORIZON_CTID -- runuser -u horizon -- \
  sh -lc 'cd /opt/horizon && .venv/bin/python scripts/dev_check_video_fetch.py'"
```

`yt-dlp` may rewrite its cookie jar. Preserve an operator-side source export and
keep every deployed cookie file mode `0600`.

## Cutover from Mac

1. Persistently disable and unload both Mac launchd labels, verify no Horizon
   cron entry exists, and confirm no pipeline process is active.
2. Copy `.env`, gitignored `data/`, generated digest pages, checks, and collection
   pages over an SSH tar stream. Do not copy virtual environments, `site/`, logs,
   or model caches.
3. Restore service ownership and secret/public file modes.
4. Reapply Linux-only ASR and Search settings.
5. Pass pytest, strict MkDocs build, config validation, Search probe, bounded
   gateway smoke, video acceptance, and manual digest acceptance.
6. If today's timer slots have passed, seed their persistent timestamps before
   first start to prevent an immediate duplicate catch-up run:

   ```bash
   ssh prod-node "pct exec $HORIZON_CTID -- touch \
     /var/lib/systemd/timers/stamp-horizon-video.timer \
     /var/lib/systemd/timers/stamp-horizon-digest.timer"
   ```

7. Enable both timers and verify the reported next trigger.

## Rollback to Mac

1. Disable **both** Linux timers before touching Mac scheduling.
2. Stop or wait for any active Linux one-shot.
3. Copy only newer summaries, verification state, generated pages, and other
   mutable runtime state back to the preserved Mac checkout.
4. Keep/reapply the Mac-specific `asr: "local"` setting if local ASR is desired.
5. Run manually or reinstall the tracked digest/video launchd templates.
6. Verify exactly one scheduler is active.

Do not delete the Mac checkout, credentials, TTS environment, or caches until
seven consecutive automated Linux runs have succeeded and the operator approves
cleanup.

## Deploying a code change

Production runs an exact tested SHA, not an opportunistic `git pull`. Test the
candidate revision offline first, disable both timers, confirm no active run,
preserve generated tracked pages, then check out the approved SHA and run
`uv sync --frozen`. Regenerate status/index pages before publishing. Never reset
a dirty production tree blindly.

Search API releases are independent: deploy only the exact committed Search API
artifact and restart only its proxy service. Do not restart Elasticsearch or run
the paid digest for an API-only change.

## Minimal verification commands

```bash
zsh -n deploy/run-daily.sh
uv run --frozen --extra dev pytest -q
uv sync --frozen  # restore the runtime-only environment
mkdocs build --strict
systemd-analyze verify /etc/systemd/system/horizon-*.service \
  /etc/systemd/system/horizon-*.timer
```
