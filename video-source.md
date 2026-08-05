---
layout: default
title: Video Source (YouTube)
---

# Video Source (YouTube)

The video source ingests videos from curated YouTube channels and turns them into
text items the regular pipeline can score, enrich, and digest. Design adapted from
[bradautomates/claude-video](https://github.com/bradautomates/claude-video) (MIT).

- **Code**: `src/scrapers/video.py`
- **Config models**: `VideoConfig` / `VideoChannelConfig` in `src/models.py`
- **Profile**: `profiles/video/`
- **Tests**: `tests/test_video.py` (offline)

## Pipeline

```
channels (config)
  └─ resolve channel id (UC... passthrough, else yt-dlp lookup)
      └─ channel RSS feed  →  new videos within the time window
          └─ per video, first content rung that works wins:
              1. subtitles            (yt-dlp, no video download)
              2. local ASR            (download audio → mlx-whisper)   [asr: "local"]
              3. vision fallback      (storyboard frames → vision LLM) [vision_fallback: true]
          └─ ContentItem (transcript + full description as content)
```

Item content = full video description + timestamped transcript (or visual summary),
truncated to `transcript_max_chars`. Items route to the profile set per channel
(default `video`).

## Configuration

`sources.video` (see `data/config.example.json` for a full example):

| Field | Default | Meaning |
|-------|---------|---------|
| `enabled` | `false` | Master switch |
| `channels` | `[]` | List of channel entries (see below) |
| `subtitle_langs` | `["en.*", "ru.*"]` | yt-dlp subtitle language patterns |
| `transcript_max_chars` | `12000` | Content cap per item |
| `cookies_from_browser` | `null` | Browser name to read cookies from (fragile on modern Chromium — prefer files) |
| `cookies_file` | `null` | Netscape `cookies.txt` export used for subtitles/storyboards/channel resolution |
| `audio_cookies_file` | `null` | Separate cookies export used **only** for audio downloads (see SABR below) |
| `vision_fallback` | `true` | Summarize storyboard frames when no transcript exists |
| `vision_max_frames` | `8` | Max storyboard grids sent to the vision model |
| `asr` | `"local"` | `"local"` = mlx-whisper on Apple Silicon; `"off"` = skip ASR |
| `asr_model` | `mlx-community/whisper-large-v3-turbo` | HuggingFace repo for mlx-whisper |

Channel entry:

```json
{
  "name": "Fireship",            // display name (optional)
  "channel": "@Fireship",        // @handle, channel URL, or UC... id (fastest, no lookup)
  "enabled": true,
  "max_videos": 3,               // per run, per channel
  "category": "dev",             // optional digest grouping tag
  "profile": "video"             // profile route
}
```

Prefer explicit `UC...` channel ids: they skip the yt-dlp channel-resolution call
entirely. Find the id on the channel's About page or in the RSS URL.

## Scoring Long Transcripts

The analyzer sees at most the profile's `content.analysis_max_chars` characters.
Transcripts easily exceed that, so `profiles/video/profile.json` sets:

```json
"content": {
  "analysis_max_chars": 12000,
  "enrichment_max_chars": 24000,
  "sampling": "head-middle-tail"
}
```

Without `head-middle-tail` sampling the scorer only reads the intro and underrates
videos whose substance starts later. Keep this block when copying the profile.

The `video` profile threshold is intentionally lower than news profiles (5.0):
channels are pre-curated, and the scorer is naturally strict about conversational
transcript style.

## YouTube Anti-Bot Gotchas (read before debugging)

YouTube gates non-residential IPs (VPS, VPN egress) behind "Sign in to confirm
you're not a bot". Every workaround below exists because the naive approach failed;
do not remove them while "cleaning up".

1. **Player clients.** Subtitles/storyboards use `player_client: ["tv", "android"]`
   which usually passes the gate. Channel resolution uses the same pair.

2. **SABR experiment.** Some (account, IP) pairs land in a streaming experiment
   that hides all audio formats. Two consequences:
   - Audio downloads use `player_client: ["tv_embedded"]` **alone** — adding any
     second client poisons the format merge back to SABR-only.
   - If the main account is in the experiment, export cookies from a *different*
     Google account and point `audio_cookies_file` at them.

3. **JS challenge.** Audio extraction requires yt-dlp's JS runtime support:
   `js_runtimes={"node": {}}` (a dict, not a list — the Python API does not
   autodetect runtimes) and `remote_components: ["ejs:github"]`. `node` must be on
   PATH. Without these, audio formats stay hidden even with good cookies.

4. **Cookies.** Modern Chromium encrypts cookies with app-bound DPAPI keys that
   yt-dlp cannot read, so `cookies_from_browser` usually fails on Windows. Export a
   Netscape-format `cookies.txt` with a browser extension instead and use
   `cookies_file`. Cookies expire — re-export when subtitle fetches start failing
   with bot-gate errors. Store cookie files `chmod 600`, never commit them.

5. **Storyboards survive everything.** Even when all playable formats are blocked,
   the `sb0` storyboard usually downloads. yt-dlp writes mhtml parts as **raw
   binary, not base64** — parsing must operate on bytes (`_parse_mhtml_frames`).

6. **Vision models cannot fetch YouTube URLs.** DashScope-family backends fail to
   download remote videos/images from YouTube. Frames are sent as base64 data URIs.

## ASR Notes

- `mlx-whisper` runs on Apple Silicon only; on other platforms set `asr: "off"`
  (cloud ASR is not wired up: it needs a provider endpoint with an ASR model).
- Model downloads on first use (~2 GB cache). Language is auto-detected.
- A 20-minute video transcribes in roughly a minute on an M4.

## Debugging Scripts

All run from the repo root with a valid `data/config.json` + `.env`:

```bash
python scripts/dev_check_video_fetch.py     # full fetch() over all enabled channels
python scripts/dev_check_one_video.py URL   # subtitles → vision fallback for one video
python scripts/dev_check_asr.py             # audio download + mlx-whisper on a fixed video
python scripts/dev_check_video_score.py     # run one video through the LLM scorer
```

Typical failure triage:

| Symptom | Likely cause |
|---------|--------------|
| "Sign in to confirm you're not a bot" | expired/absent cookies, or datacenter IP without cookies |
| audio download produces no files | SABR experiment — try `audio_cookies_file` from another account |
| `Channel resolve failed` | handle changed / yt-dlp outdated — pin `UC...` id instead |
| subtitles fine but content looks like intro only | missing `content` block in the profile (§Scoring) |
| `mlx-whisper not installed` | expected off Apple Silicon — set `asr: "off"` |
