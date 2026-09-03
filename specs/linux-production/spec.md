# Linux Production Migration Specification

## Objective

Move the scheduled Horizon workload off the macOS worker and into a dedicated,
unprivileged Debian 12 LXC without changing Horizon's public API or committing
runtime state. Keep the Mac as a cold rollback until the Linux schedule has seven
consecutive successful runs.

## Requirements

### REQ-01 — Dedicated Linux guest

The pipeline runs in a dedicated Debian 12 LXC with 2 vCPU, 4 GiB RAM, 1 GiB
swap, and a 32 GiB root disk. Python 3.11+, Node.js, ffmpeg, Git, OpenSSH client,
rsync, zsh, and `uv` are installed; ASR and narration model caches are not.

### REQ-02 — Native scheduling and exclusion

`horizon-video.timer` runs at 16:00 local time and `horizon-digest.timer` at
17:00. Both are persistent and their services share one `flock`, so video,
digest, and manual invocations cannot overlap.

### REQ-03 — Exact code revision

Production uses an explicitly tested `origin/main` commit under `/opt/horizon`.
Expected generated pages and gitignored runtime files may change; unreviewed
source-code changes may not.

### REQ-04 — Runtime state and secrets

The migrated `.env`, `data/`, generated digest pages, checks page, and collection
page remain under the production checkout because existing code resolves them
there. They stay outside Git commits. `.env`, live config, cookies, and config
backups are mode `0600`; the service account owns the runtime tree.

### REQ-05 — One active scheduler

The Mac must have no active launchd/cron Horizon job and no running pipeline
before Linux timers are enabled. Its Horizon scheduler labels remain disabled
across login/reboot while rollback plist files are retained. Rollback disables
Linux timers before any Mac job or manual run is restored.

### REQ-06 — Search isolation

Elasticsearch and its public read proxy remain on the separate search guest.
Elasticsearch remains loopback-only; `horizon-search-tunnel.service` exposes it
only as `127.0.0.1:9200` inside the pipeline guest through a port-restricted SSH
identity with strict host-key checking.

### REQ-07 — Restricted static publishing

`run-daily.sh` keeps its tar-over-SSH protocol but authenticates as a dedicated
publisher. The ingress identity is source-restricted and forced to a static-site
helper that rejects unsafe archive members, normalizes public file modes, and
can replace only the digest document root.

### REQ-08 — Linux video ladder

Linux sets `sources.video.asr` to `"off"`: subtitles remain first, then the
configured vision model handles storyboard frames. Failure remains visible in
the video-run summary but never aborts the digest.

### REQ-09 — Video-only egress

When direct YouTube HTTPS is unavailable, only `horizon-video.service` may load
an operator-approved HTTP CONNECT environment. Digest, SSH publication, and the
loopback search path remain direct; proxy configuration and endpoints stay
operator-local and untracked.

### REQ-10 — Narration deferral

Linux explicitly points the optional narration interpreter at a non-existent
path. Text is published normally; audio remains disabled until Linux synthesis
has an independent, verified Whisper-compatible grader.

### REQ-11 — Cold rollback window

The complete Mac checkout, runtime state, virtual environments, and credentials
remain untouched for at least seven successful automated Linux runs. Cache or
credential cleanup requires a separate operator decision.
