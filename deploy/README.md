# Deployment

The Horizon pipeline is a periodic batch job: run it on a schedule, read the digest it
writes to `data/summaries/` (and/or receive it via webhook/email). The core job has no
daemon or listening port; the optional archive-search stack under `deploy/search/` is separate.

The current production topology runs the scheduled pipeline in a dedicated Debian
LXC under `horizon-video.timer` and `horizon-digest.timer`. Elasticsearch and its
read-only Search API remain on a separate Linux guest; the pipeline reaches the
loopback-only writer endpoint through `horizon-search-tunnel.service`. The macOS
launchd setup is preserved as a cold rollback/reference. See
[`specs/linux-production`](../specs/linux-production/spec.md) for the contract.

## Choosing a Host

| Host | Notes |
|------|-------|
| **Debian LXC / Linux box (Current Production)** | Primary production setup using systemd timer/service. Set `sources.video.asr: "off"` and rely on subtitles + vision fallback. Narration is skipped gracefully when the TTS environment is absent. Reaches search via loopback/tunnel and publishes static site over a restricted SSH key. Uses a shared `flock` lockfile to prevent overlapping runs. |
| **macOS (Apple Silicon) (Rollback / Reference)** | Supported rollback/reference setup using launchd. Supports local ASR via `mlx-whisper` (`uv sync --extra asr`) and local narration TTS (`~/tts/.venv`). |
| **GitHub Actions cron** | Can run the pipeline (the tracked `daily-summary.yml.disabled` is only a disabled template), but YouTube cookie handling and local ASR are impractical there. |

YouTube access note: if the host egresses through a datacenter/VPN IP, expect
bot-gate pressure — you will need the `cookies_file` setup described in
[`docs/video-source.md`](../docs/video-source.md).

## Debian LXC via systemd (current production)

1. Create an unprivileged Debian 12 guest and a non-login `horizon` service
   account. The reference layout is `/opt/horizon` for the exact tested checkout,
   `/var/lib/horizon` for its home/SSH identities, and `/var/cache/horizon` for
   the installation cache.
2. Install Python 3.11+, `uv`, Node.js, ffmpeg, Git, zsh, rsync, and the OpenSSH
   client. Run `uv sync --frozen`; do not install the Apple-only `asr` extra.
3. Copy `.env`, gitignored `data/`, generated digest pages, `docs/checks.md`, and
   `docs/collection.md` from the stopped source host. Keep `.env`, live config,
   cookies, and config backups mode `0600`.
4. In `data/config.json`, set `sources.video.asr` to `"off"` and point Search at
   the local tunnel. Video extraction is subtitles first, then configured vision.
5. Install the five systemd unit examples in this directory under their names
   without `.example`. Copy `horizon-runtime.env.example` to
   `/etc/horizon/runtime.env` and replace its placeholders with operator-owned
   values. The timers run video at 16:00 and digest at 17:00 local time with
   `Persistent=true`.
6. Provision two independent SSH identities: a port-restricted Search tunnel and
   a source-restricted, forced-command static publisher. Pin both host keys.
7. If direct YouTube HTTPS is unavailable, an operator may add a mode-`0600`
   `/etc/horizon/video-egress.env` containing standard `HTTP_PROXY`,
   `HTTPS_PROXY`, and loopback-only `NO_PROXY` values. Only
   `horizon-video.service` loads it; do not proxy Search or publishing.
8. Keep narration disabled by setting `HORIZON_TTS_PYTHON=/nonexistent` in the
   runtime environment. Linux has no approved independent Whisper grader yet,
   so text publishes normally without audio.

The video and digest units share `/run/lock/horizon-production.lock`; video
refuses overlap and digest waits for the current video run. Install timers only
after offline tests and one manual production acceptance:

```bash
sudo systemd-analyze verify /etc/systemd/system/horizon-*.service \
  /etc/systemd/system/horizon-*.timer
sudo systemctl enable --now horizon-search-tunnel.service
sudo systemctl enable --now horizon-video.timer horizon-digest.timer
systemctl list-timers 'horizon-*'
```

## macOS via launchd (Rollback / Reference Setup)

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

   An inline full run or `horizon-video --hours 24` logs `Video preflight:` warnings
   for these dependencies. There is no `horizon --source` flag; remember that either
   real collection path may use network/model resources, so prefer offline video tests first.

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
delay or destabilise the digest run. On systemd, enable `horizon-video.timer` (`deploy/horizon-video.timer.example`). On macOS launchd, install the second job *before* the digest job's slot:

```bash
sed 's/YOURUSER/yourusername/g' deploy/horizon-video.launchd.example.plist \
  > ~/Library/LaunchAgents/com.horizon.video.plist
launchctl load ~/Library/LaunchAgents/com.horizon.video.plist
```

The template runs at 16:00, an hour ahead of the 17:00 digest. This job needs
`node` and `ffmpeg`; only the macOS reference runtime additionally uses
`mlx-whisper`. The digest service reads `data/video-inbox.json`. Details and
failure behaviour: [`docs/video-source.md`](../docs/video-source.md).

## Publishing the digest site

The pipeline writes `docs/digest/{date}-{lang}.md` on every run (gitignored —
195 KB/day into git buys nothing). Building and shipping the site is a step
after the run, not part of it.

Install the toolchain as an isolated tool, **not** as a project dependency — it
pulls ~30 transitive packages into a lockfile that is a prime upstream merge
conflict, for something the runtime never imports:

```bash
# mkdocs-material is a theme and ships no executable — the binary comes from
# mkdocs itself. On a host where ~/.local is root-owned, point uv elsewhere.
export XDG_DATA_HOME=$HOME/.uvdata UV_TOOL_BIN_DIR=$HOME/bin
uv tool install mkdocs --with mkdocs-material
```

Then, after each pipeline run:

```bash
cd ~/horizon && .venv/bin/python -c 'from src.storage.manager import StorageManager; StorageManager.write_site_index()' && mkdocs build
cd site && tar czf - . | ssh USER@HOST 'rm -rf /srv/DOMAIN/* && tar xzf - -C /srv/DOMAIN'
```

**Regenerate the index first — this is not optional.** `docs/digest/index.md` is
generated from whatever issues are on disk, but it is also tracked, because a
fresh clone needs it to exist for the build to resolve `nav`. So it carries a
"no issues yet" placeholder, and any git operation on this machine — a pull, a
checkout, a stash — restores that placeholder over the real listing. The
symptom is an archive page that says there are no issues while five sit in
`docs/digest/`, and nothing else looks wrong. It stays that way until the next
pipeline run, because publishing is the only other thing that regenerates it.

`tar` over ssh rather than `rsync`: a minimal ingress container often has no
rsync, and installing packages on the edge proxy to copy static files is a poor
trade. The current replace-all command is **not atomic**: it deletes the live tree
before extraction, and a broken stream can leave the site partial or empty. Treat
release-directory upload plus a final rename/symlink swap as an open hardening task.

Without optional archive search, Caddy on the target only needs a file server:

```
digest.example.com {
    root * /srv/digest.example.com
    encode zstd gzip
    try_files {path} {path}/ {path}.html
    file_server
}
```

`encode` matters: the built pages are ~83 KB raw and ~23 KB gzipped. When
archive search is enabled, place the `/api/search*` handler from
`search/README.md` before this static catch-all and exclude it from static cache
rules. Production ingress also serves the built `/not-found/` page for errors
while preserving the original HTTP status; validate the complete Caddy config
before every reload.

### Public design preview

The repository also has a manual **Deploy Site Preview** GitHub Actions
workflow. It builds the same MkDocs output and publishes it to GitHub Pages.
Use it when the private deployment host is unavailable from the workstation;
the production digest remains the self-hosted site above, because its generated
issues and runtime state never enter Git.

If you already run an ingress that serves static sites, add the site there
rather than standing up a container for it — one more `conf.d/<domain>.caddy`
next to the existing ones is less moving parts than a new host. Two precautions
make that safe: run `caddy validate --config /etc/caddy/Caddyfile --adapter
caddyfile` **before** reloading, and curl the neighbouring sites **after**, so a
mistake surfaces immediately instead of at the next visitor.

Known and accepted: a **404 window of a few seconds**. Today's page reaches the
target only after the first copy, which runs after the digest job has already
sent its Telegram links. `run-daily.sh` deliberately ships the text pages before
narration, then ships again with the audio players. Do not move narration ahead
of the first ship: on 2026-08-10 it stretched this window from seconds to nine
minutes (including a cold model download).

## Systemd timer cutover and rollback

1. Persistently disable and unload any Mac digest/video launchd jobs, check
   cron, and confirm that no Horizon process is running.
2. Stream the final gitignored state and generated site pages to `/opt/horizon`;
   do not copy `.venv`, `site/`, logs, or model caches.
3. Reapply Linux-only settings (`sources.video.asr: "off"` and the loopback
   Search URL), ownership, and file modes.
4. Pass pytest, strict MkDocs build, config validation, Search-tunnel probe,
   video acceptance, and one manual digest acceptance.
5. If today's persistent timer slots have already passed, seed their timer stamp
   before first start so enabling them cannot launch a duplicate catch-up run;
   use the exact command in the [cutover runbook](RUNBOOK.md#cutover-from-mac).
6. Enable both timers and confirm each next trigger is the intended upcoming slot
   (today when it is still ahead, otherwise tomorrow after seeding the stamps).

For rollback, disable **both** Linux timers first and stop any active one-shot.
Copy only newer runtime state back to the preserved Mac checkout, keep the
Mac-specific ASR setting, then run manually or restore both launchd plists.
Never leave Mac and Linux schedulers active together. Keep the Mac intact until
seven consecutive automated Linux runs have succeeded.

## Operations

- **Logs**: Linux production writes the token summary to `journalctl -u horizon-digest.service`; the macOS reference keeps `logs/horizon.log`.
- **Output**: `data/summaries/YYYY-MM-DD-*.md` (gitignored state).
- **Cookies expiry**: when subtitle fetches start failing, re-export
  `data/youtube-cookies*.txt` (see [`docs/video-source.md`](../docs/video-source.md)).
- **Pipeline updates**: deploy an explicitly tested SHA during a disabled-timer
  window. Preserve generated tracked pages before checkout and regenerate them
  before publishing; never run a blind `git pull` or reset on production. One-shot
  services need no restart. Search API updates remain separate artifact deployments
  described in [`search/README.md`](search/README.md).
- **Secrets on the host**: `.env` and cookie files should be readable only by the
  service account (`chmod 600`). Never commit them.

### Watching for silent breakage

The video source degrades instead of failing: expired cookies or a YouTube
change produce items with descriptions but no transcripts, which looks like a
quiet week rather than an outage. Two log lines make that visible:

```bash
journalctl -u horizon-video.service --since today | grep 'Video preflight:'
journalctl -u horizon-video.service --since today | grep 'Video run'
```

A healthy run logs `Video run: 9 videos: 7 subtitles, 0 ASR, 1 vision, 0
description-only, 1 skipped, 0 failed`. When the share of videos yielding text
falls below `sources.video.min_transcript_rate` (default 0.5, needs ≥3 graded videos),
the line is promoted to a WARNING containing `Video run degraded` — that is the
alert to act on. Set up whatever notifier you like on that string; the
[weekly check](#weekly-check) below is the manual version.

### Weekly check

```bash
cd /opt/horizon
.venv/bin/python scripts/dev_check_video_fetch.py   # real fetch, no vision model
```

The command still uses live YouTube/network access. Run it under the same
video-only egress environment when production requires that route. Update
`yt-dlp` only through a reviewed lockfile and exact-SHA deployment, never as an
ad-hoc production upgrade.

### Host uptime and log rotation

Linux LXC production uses systemd timers and journal retention. For an always-on
macOS rollback host, either disable sleep or configure a scheduled wake before
the jobs:

```bash
sudo pmset -a sleep 0 disksleep 0
# Alternative when sleep is desired:
sudo pmset repeat wakeorpoweron MTWRFSU 15:55:00
```

The macOS `logs/horizon.log` file is append-only. Add a `newsyslog` rule such as:

```bash
echo '/Users/YOURUSER/horizon/logs/horizon.log 644 7 5000 * J' \
  | sudo tee /etc/newsyslog.d/horizon.conf
```

That retains seven generations, rotates near 5 MB, and compresses old logs.
