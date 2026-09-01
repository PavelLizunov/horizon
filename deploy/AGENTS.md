# Deployment Agent Guide (`deploy/`)

Local rules and operational context for host deployment, scheduled daily runs, launchd plists, and site publishing. Parent rules in root `AGENTS.md` and operational details in `RUNBOOK.md` apply.

## Local Scope & Architecture

The `deploy/` directory contains host orchestration tools:
- `run-daily.sh`: Master daily execution script invoked by launchd (`com.horizon.digest.plist`).
- `horizon.launchd.example.plist` & `horizon-video.launchd.example.plist`: macOS launchd service templates.
- `audio-server.caddy.example`: Caddy virtual host configuration for static voice asset delivery.
- `search/`: Subdirectory housing the Elasticsearch archive search stack (see `deploy/search/AGENTS.md`).

## Pipeline & Publishing Execution Order

`run-daily.sh` enforces a strict **text-before-narration** publishing sequence:

1. **Pipeline Run**: Executes `.venv/bin/horizon --hours "${HORIZON_HOURS:-24}"`. Telegram notification links go out *during* this step.
2. **Metadata Regeneration**: Rebuilds archive index (`StorageManager.write_site_index()`), verification status (`docs/checks.md`), collection status (`docs/collection.md`), and article verification labels.
3. **First Site Publish (`ship_site`)**: Builds (`mkdocs build`) and streams site files via SSH (`tar czf - . | ssh ...`) *before* starting speech synthesis. This minimizes the period in which Telegram links wait for narration; the current remote replace is not atomic and does not itself guarantee a zero-downtime publish.
4. **Narration Synthesis**: Prepares text and generates voice tracks via `scripts/dev_narrate_article.py`. Passed checks attach audio player markdown (`--attach`).
5. **Second Site Publish (`ship_site`)**: Re-builds and re-ships site to activate audio player components for validated voice tracks.

## Graceful Failure Boundaries

- **Pipeline Failure**: If `.venv/bin/horizon` exits non-zero, `run-daily.sh` logs the failure and aborts site publishing and narration immediately (`exit $pipeline_status`).
- **Metadata Failure**: Failures in index or status page generation log warnings (`index: FAILED`, `verification page: FAILED`) but continue execution to allow site publishing.
- **Site Build / Transfer Failure**: A local `mkdocs build` failure leaves the live site untouched. The current remote command deletes destination contents before extraction, so a stream/extract failure can leave the live tree partial or empty; treat atomic remote publishing as unresolved.
- **Narration Failure**: Narration is non-fatal. If TTS interpreter is missing (`$narrator`), issue directory is absent, or article verification fails during speech synthesis, the script logs a warning and proceeds. The published text site remains available without audio.

## Portability & Security Policy

- **Deployment Values**: Do not add new hardcoded hosts, IPs, user accounts, or secrets. Prefer SSH aliases, placeholders, or environment variables. Existing tracked deployment defaults are operator-owned compatibility values; changing or removing them requires explicit owner review.
- **File Permissions**: `.env` and cookie files in `data/` must be `chmod 600` and kept gitignored.

## Safe Shell Behavior

- **Environment & PATH**: Non-interactive SSH/launchd environments lack default tool paths. `run-daily.sh` explicitly exports `PATH="$HOME/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"`.
- **Ship-Only Mode**: `HORIZON_SHIP_ONLY=1 ./deploy/run-daily.sh` skips fetching, LLM work, and narration, but it still rebuilds and replaces the live remote site. It is a production-mutating operator action, not a safe general-development check.
- **Remote Execution & Quoting**: Avoid complex inline commands or unescaped YouTube URLs (e.g. `watch?v=` glob errors in zsh) over SSH. Transfer scripts via `scp` or use single-line SSH commands with proper shell wrappers (`zsh -lc "..."`).
- **Cost Discipline**: Never invoke `horizon` directly on production without explicit operator confirmation due to LLM token consumption.

## Verification Commands

- Syntax-check daily script: `zsh -n deploy/run-daily.sh`
- Verify git diff for whitespace or trailing formatting errors: `git diff --check -- deploy/AGENTS.md deploy/search/AGENTS.md`
