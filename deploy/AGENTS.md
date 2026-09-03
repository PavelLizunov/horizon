# Deployment Agent Guide (`deploy/`)

Local rules and operational context for host deployment, scheduled daily runs, systemd service/timer units, launchd plists, and site publishing. Parent rules in root `AGENTS.md` and operational details in `RUNBOOK.md` apply.

## Local Scope & Architecture

The `deploy/` directory contains host orchestration tools:
- `run-daily.sh`: Master daily execution script invoked by systemd (`horizon-digest.service`) or launchd (`com.horizon.digest.plist`).
- `horizon-digest.service.example` & `horizon-digest.timer.example`: Systemd unit templates for current Debian LXC production topology.
- `horizon.launchd.example.plist` & `horizon-video.launchd.example.plist`: macOS launchd service templates for rollback/reference topology.
- `audio-server.caddy.example`: Caddy virtual host configuration for static voice asset delivery.
- `search/`: Search API artifact plus a reference Docker Compose stack. Current production keeps the artifact (`horizon-search-api.service`) and Elasticsearch (`horizon-elasticsearch.service`) on a separate Debian guest; see `deploy/search/AGENTS.md` and `specs/linux-production`.

## Pipeline & Publishing Execution Order

`run-daily.sh` enforces a strict **text-before-narration** publishing sequence:

1. **Pipeline Run**: Executes `.venv/bin/horizon --hours "${HORIZON_HOURS:-24}"`. Telegram notification links go out *during* this step.
2. **Metadata Regeneration**: Rebuilds archive index (`StorageManager.write_site_index()`), verification status (`docs/checks.md`), collection status (`docs/collection.md`), and article verification labels.
3. **First Site Publish (`ship_site`)**: Builds (`mkdocs build`) and streams site files via SSH (`tar czf - . | ssh ...`) using a restricted SSH publisher key *before* starting speech synthesis. This minimizes the period in which Telegram links wait for narration; the current remote replace is not atomic and does not itself guarantee a zero-downtime publish.
4. **Narration Synthesis**: Prepares text and attempts voice tracks via `scripts/dev_narrate_article.py` when configured. Debian production points the optional interpreter at a non-existent path because no independent Linux Whisper grader is approved. Passed checks on supported runtimes attach audio player markdown (`--attach`).
5. **Second Site Publish (`ship_site`)**: Re-builds and re-ships site to activate audio player components for validated voice tracks (if narration produced assets).

## Operational Constraints (Linux Production Path)

- **ASR Off**: Debian LXC production sets `sources.video.asr: "off"`. Audio transcript extraction relies on subtitles (yt-dlp) and vision fallback.
- **Narration Skipped**: Debian production has no approved independent Whisper grader; narration logs as skipped/non-fatal and text publishing succeeds without audio assets.
- **Shared Flock Lock**: Both one-shot units use `/run/lock/horizon-production.lock`; video refuses overlap and digest waits for an active video run.
- **Video-only Egress**: An operator-approved proxy environment may be loaded only by `horizon-video.service`; Search, publishing, and the digest service stay direct.
- **Restricted SSH Publisher & Search Tunnel**: Ingress publishing and Search forwarding use separate, least-privilege identities with pinned host keys. Elasticsearch remains on its separate guest.
- **Timer Cutover & State Transfer**: Disable the source scheduler and confirm no active process before transferring gitignored state/generated pages and enabling the target timers.
- **Verification & Rollback**: Verify both timers and their service journals. Rollback disables both Linux timers before any Mac manual run or launchd job is restored.

## Graceful Failure Boundaries

- **Pipeline Failure**: If `.venv/bin/horizon` exits non-zero, `run-daily.sh` logs the failure and aborts site publishing and narration immediately (`exit $pipeline_status`).
- **Metadata Failure**: Failures in index or status page generation log warnings (`index: FAILED`, `verification page: FAILED`) but continue execution to allow site publishing.
- **Site Build / Transfer Failure**: A local `mkdocs build` failure leaves the live site untouched. The current remote command deletes destination contents before extraction, so a stream/extract failure can leave the live tree partial or empty; treat atomic remote publishing as unresolved.
- **Narration Failure / Skip**: Narration is non-fatal. If TTS interpreter is missing (`$narrator`), issue directory is absent, or article verification fails during speech synthesis, the script logs a warning and proceeds. The published text site remains available without audio.
- **Search Separation**: Search API-only changes deploy the exact committed artifact to the Linux guest and restart only `horizon-search-api.service`; Elasticsearch and the paid pipeline remain untouched.

## Portability & Security Policy

- **Deployment Values**: Do not add new hardcoded hosts, IPs, user accounts, or secrets. Prefer SSH aliases (`prod-linux`, `prod-mac`), placeholders, or environment variables. Existing tracked deployment defaults are operator-owned compatibility values; changing or removing them requires explicit owner review.
- **File Permissions**: `.env` and cookie files in `data/` must be `chmod 600` and kept gitignored.

## Safe Shell Behavior

- **Environment & PATH**: Non-interactive SSH/systemd environments lack default tool paths. `run-daily.sh` explicitly exports `PATH="$HOME/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"`.
- **Ship-Only Mode**: `HORIZON_SHIP_ONLY=1 ./deploy/run-daily.sh` skips fetching, LLM work, and narration, but it still rebuilds and replaces the live remote site. It is a production-mutating operator action, not a safe general-development check.
- **Remote Execution & Quoting**: Avoid complex inline commands or unescaped YouTube URLs (e.g. `watch?v=` glob errors in zsh/bash) over SSH. Transfer scripts via `scp` or use single-line SSH commands with proper shell wrappers (`bash -lc "..."`).
- **Cost Discipline**: Never invoke `horizon` directly on production without explicit operator confirmation due to LLM token consumption.

## Verification Commands

- Syntax-check daily script: `zsh -n deploy/run-daily.sh`
- Verify example units: copy them without `.example` into a temporary directory and run `systemd-analyze verify`.
- Verify changed documentation/templates: `git diff --check -- deploy`.
