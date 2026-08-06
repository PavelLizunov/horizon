# Deployment

Horizon is a periodic batch job: run it on a schedule, read the digest it writes to
`data/summaries/` (and/or receive it via webhook/email). No daemon, no ports.

## Choosing a Host

| Host | Notes |
|------|-------|
| **macOS (Apple Silicon)** | Best fit: local ASR via mlx-whisper works. launchd template below. |
| **Linux box / VM** | Fine for everything except local ASR — set `video.asr: "off"` and rely on subtitles + vision fallback. Use cron/systemd timer. |
| **GitHub Actions cron** | Works for the pipeline itself (see upstream `daily-summary.yml`), but YouTube cookie handling and local ASR are impractical there. |

YouTube access note: if the host egresses through a datacenter/VPN IP, expect
bot-gate pressure — you will need the `cookies_file` setup described in
`docs/video-source.md`.

## macOS via launchd (reference setup)

1. Install the project once:

   ```bash
   git clone <this-repo> ~/horizon && cd ~/horizon
   uv venv && uv sync                    # adds .venv/bin/horizon
   uv sync --extra asr                   # local ASR, Apple Silicon only
   ```

   Use the `asr` extra rather than `uv pip install mlx-whisper`: a later plain
   `uv sync` prunes anything not in the lockfile, which would remove a
   hand-installed mlx-whisper and turn ASR off without any error — the scraper
   just starts logging "mlx-whisper is not installed" and falls back.

   The extra is marked `darwin`/`arm64` only, so it resolves to nothing on Linux
   or Intel Macs and is safe to leave in place. It pulls a native scientific
   stack (mlx, numba, scipy), plus ~2 GB of model cache on first transcription.

2. Runtime prerequisites on `PATH`:

   | Binary | Needed for | Symptom when missing |
   |--------|-----------|----------------------|
   | `node` | yt-dlp's JS challenge solver | audio formats stay hidden → ASR never gets input |
   | `ffmpeg` | mlx-whisper audio decoding (`asr: "local"` only) | every ASR attempt fails |

   `horizon --source video` logs a `Video preflight:` warning for each of these
   at the start of a run, so check the log before hunting deeper.

3. Create `data/config.json` and `.env` from the examples. If you use YouTube
   cookies, place the exports under `data/` and `chmod 600` them.

4. Install the launchd job from the template:

   ```bash
   sed 's/YOURUSER/yourusername/g' deploy/horizon.launchd.example.plist \
       > ~/Library/LaunchAgents/com.horizon.digest.plist
   launchctl load ~/Library/LaunchAgents/com.horizon.digest.plist
   ```

   The template runs `horizon --hours 24` daily at 17:00 local time. Edit
   `Hour`/`Minute` to match your provider's cheap-token window if it has one.

5. Verify:

   ```bash
   launchctl list | grep horizon               # job registered
   launchctl start com.horizon.digest          # manual trigger
   tail -f ~/horizon/logs/horizon.log          # expect "Horizon completed successfully!"
   ```

   Note: `launchctl start` from a terminal inherits that terminal's environment;
   scheduled runs use only the plist's `EnvironmentVariables`, so make sure `PATH`
   there covers `node` and any other binaries you rely on.

## Splitting the video job off (optional)

With `sources.video.mode: "sidecar"` the YouTube work moves into its own
process and its own schedule, so yt-dlp breakage or a slow ASR pass cannot
delay or destabilise the digest run. Install the second job *before* the digest
job's slot:

```bash
sed 's/YOURUSER/yourusername/g' deploy/horizon-video.launchd.example.plist \
  > ~/Library/LaunchAgents/com.horizon.video.plist
launchctl load ~/Library/LaunchAgents/com.horizon.video.plist
```

The template runs at 16:00, an hour ahead of the 17:00 digest. Only this job
needs `node`, `ffmpeg` and `mlx-whisper` — the digest host just reads
`data/video-inbox.json`. Details and failure behaviour: `docs/video-source.md`.

## Publishing the digest site

The pipeline writes `docs/digest/{date}-{lang}.md` on every run (gitignored —
195 KB/day into git buys nothing). Building and shipping the site is a step
after the run, not part of it.

Install the toolchain as an isolated tool, **not** as a project dependency — it
pulls ~30 transitive packages into a lockfile that is a prime upstream merge
conflict, for something the runtime never imports:

```bash
uv tool install mkdocs-material
```

Then, after each pipeline run:

```bash
cd ~/horizon && mkdocs build && rsync -a --delete site/ USER@HOST:/srv/horizon/
```

Caddy on the target only needs a file server:

```
digest.example.com {
    root * /srv/horizon
    file_server
    try_files {path} {path}/ {path}.html
    encode zstd gzip
}
```

`encode` matters: the built pages are ~86 KB raw and ~23 KB gzipped.

**Do not add this to an existing Caddy that fronts anything sensitive.** A
separate container costs ten minutes and cannot disturb a working configuration.

Known and accepted: a **404 window of a few seconds**. Today's page reaches the
target only after `rsync`, which runs after the digest job has already sent its
Telegram links. Only the current day's link is affected; pulling `mkdocs build`
into the pipeline would couple it to a site toolchain for a few seconds of
polish.

## Linux via cron (sketch)

```cron
0 17 * * * cd $HOME/horizon && .venv/bin/horizon --hours 24 >> logs/horizon.log 2>&1
```

With `video.asr` set to `"off"` unless you wire up a different ASR backend.

## Operations

- **Log file**: `logs/horizon.log` — token usage summary at the end of each run.
- **Output**: `data/summaries/YYYY-MM-DD-*.md` (gitignored state).
- **Cookies expiry**: when subtitle fetches start failing, re-export
  `data/youtube-cookies*.txt` (see `docs/video-source.md`).
- **Updates**: `git pull && uv sync` — no service restart needed; the next
  scheduled run picks up changes. Re-run with `--extra asr` if you use local ASR.
- **Secrets on the host**: `.env` and cookie files should be readable only by the
  service account (`chmod 600`). Never commit them.

### Watching for silent breakage

The video source degrades instead of failing: expired cookies or a YouTube
change produce items with descriptions but no transcripts, which looks like a
quiet week rather than an outage. Two log lines make that visible:

```bash
grep 'Video preflight:'   ~/horizon/logs/horizon.log   # missing node/ffmpeg/cookies/mlx
grep 'Video run'          ~/horizon/logs/horizon.log   # per-run extraction breakdown
```

A healthy run logs `Video run: 9 videos: 7 subtitles, 1 ASR, 0 vision, 0
description-only, 1 skipped, 0 failed`. When the share of videos yielding text
falls below `video.min_transcript_rate` (default 0.5, needs ≥3 graded videos),
the line is promoted to a WARNING containing `Video run degraded` — that is the
alert to act on. Set up whatever notifier you like on that string; the
[weekly check](#weekly-check) below is the manual version.

### Weekly check

```bash
cd ~/horizon
uv run python scripts/dev_check_video_fetch.py   # real fetch + extraction summary
uv sync --upgrade-package yt-dlp                 # YouTube changes often; yt-dlp tracks it
```

### The mac stays awake, or it misses days

`StartCalendarInterval` does **not** replay missed runs: if the machine is
asleep at the scheduled time, that day is simply skipped. For an always-on Mac
mini the simplest fix is to stop it sleeping:

```bash
sudo pmset -a sleep 0 disksleep 0
```

Or, to let it sleep and still wake for the job:

```bash
sudo pmset repeat wakeorpoweron MTWRFSU 16:55:00
```

### Log rotation

`logs/horizon.log` is append-only and never rotated. Add a `newsyslog` rule:

```bash
echo '/Users/YOURUSER/horizon/logs/horizon.log 644 7 5000 * J' \
  | sudo tee /etc/newsyslog.d/horizon.conf
```

(7 generations, rotate past ~5 MB, bzip2-compressed.)
