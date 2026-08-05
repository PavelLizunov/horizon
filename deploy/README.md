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
   uv venv && uv pip install -e .        # adds .venv/bin/horizon
   # local ASR (optional, Apple Silicon only):
   uv pip install mlx-whisper
   ```

2. Runtime prerequisites on `PATH`: `node` (yt-dlp JS challenge solver). `ffmpeg`
   is not required for the default flow.

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
- **Updates**: `git pull && uv pip install -e .` — no service restart needed;
  the next scheduled run picks up changes.
- **Secrets on the host**: `.env` and cookie files should be readable only by the
  service account (`chmod 600`). Never commit them.
