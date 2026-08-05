"""YouTube channel scraper with transcript ingestion.

Design adapted from bradautomates/claude-video (MIT): new videos are
discovered via the channel RSS feed, subtitles are fetched with yt-dlp
without downloading the video, and VTT cues are cleaned into a
timestamped transcript that becomes the item content.
"""

import asyncio
import base64
import calendar
import gc
import importlib.util
import json
import logging
import os
import re
import shutil
import tempfile
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import List, Optional, Tuple

import feedparser
import httpx

from .base import BaseScraper
from .._file_utils import _atomic_write_text
from ..ai.tokens import record_usage
from ..models import AIConfig, ContentItem, SourceType, VideoChannelConfig, VideoConfig

logger = logging.getLogger(__name__)

YT_CHANNEL_FEED = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

TS_RE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2})[.,](\d{3})\s+-->\s+(\d{2}):(\d{2}):(\d{2})[.,](\d{3})"
)
TAG_RE = re.compile(r"<[^>]+>")
VIDEO_ID_RE = re.compile(r"(?:v=|/shorts/|/live/|youtu\.be/)([0-9A-Za-z_-]{11})")

# live_status values that mean "there is nothing to transcribe yet".
UNREADY_LIVE_STATUS = {"is_upcoming", "is_live"}


@dataclass
class VideoRunStats:
    """Per-run outcome counters.

    The scraper degrades instead of raising, so a broken cookie jar or a
    YouTube change looks exactly like "a quiet week" in the digest. These
    counters make the difference visible — see `summary()` and the WARNING
    emitted by `_log_run_summary`.
    """

    videos: int = 0
    subtitles: int = 0
    asr: int = 0
    vision: int = 0
    description_only: int = 0
    skipped: int = 0
    failed: int = 0
    # yt-dlp calls rejected with "Sign in to confirm you're not a bot". Counted
    # separately because it has exactly one cause and one fix (re-export the
    # cookies), and because it can hit every stage of a single video.
    bot_gated: int = 0

    @property
    def graded(self) -> int:
        """Videos that were actually expected to produce text."""
        return self.videos - self.skipped

    @property
    def with_text(self) -> int:
        return self.subtitles + self.asr + self.vision

    @property
    def transcript_rate(self) -> float:
        return self.with_text / self.graded if self.graded else 1.0

    def summary(self) -> str:
        text = (
            f"{self.videos} videos: {self.subtitles} subtitles, {self.asr} ASR, "
            f"{self.vision} vision, {self.description_only} description-only, "
            f"{self.skipped} skipped, {self.failed} failed"
        )
        if self.bot_gated:
            text += f", {self.bot_gated} bot-gated"
        return text


def _is_bot_gate(error: object) -> bool:
    """Detect YouTube's "Sign in to confirm you're not a bot" rejection.

    This is the single most common way the source dies: cookies expire, every
    yt-dlp call is refused, and every video quietly degrades to description
    only. String matching is fragile in general, but this message has been
    stable for years and the alternative is not noticing for weeks.
    """
    text = str(error).lower()
    return "sign in to confirm" in text or "not a bot" in text


# Bumped when the on-disk shape changes; a mismatch is ignored rather than
# guessed at, so an old sidecar cannot feed garbage into a new pipeline.
INBOX_VERSION = 1


def write_inbox(path: Path, items: List[ContentItem], stats: VideoRunStats) -> None:
    """Persist scraped items for a later pipeline run (sidecar mode).

    Written atomically: the digest job may read this file at any moment, and a
    half-written inbox would look like corruption rather than a missed run.
    """
    payload = {
        "version": INBOX_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stats": asdict(stats),
        "items": [item.model_dump(mode="json") for item in items],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))


def _module_available(name: str) -> bool:
    """Check importability without importing (mlx pulls in Metal on import)."""
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def _video_id_from_url(url: str) -> str:
    """Best-effort video id for watch/shorts/live/youtu.be URLs."""
    match = VIDEO_ID_RE.search(url)
    return match.group(1) if match else url.rstrip("/").rsplit("/", 1)[-1]


def _skip_reason(info: dict, video_cfg: VideoConfig) -> Optional[str]:
    """Return why a video should not become an item, or None to keep it.

    Fails open: missing metadata never skips, so a yt-dlp change that drops a
    field cannot silently empty the digest.
    """
    live_status = info.get("live_status")
    if live_status in UNREADY_LIVE_STATUS:
        return f"live_status={live_status}"
    duration = info.get("duration")
    if (
        video_cfg.min_duration_sec
        and isinstance(duration, (int, float))
        and 0 < duration < video_cfg.min_duration_sec
    ):
        return f"duration {int(duration)}s < min_duration_sec {video_cfg.min_duration_sec}"
    return None


def _sample_frames(frames: List[str], limit: int) -> List[str]:
    """Spread the frame budget over the whole video instead of its opening.

    Storyboards are chronological, so taking the first N grids describes only
    the intro of a long video.
    """
    if limit <= 0:
        return []
    if len(frames) <= limit:
        return frames
    if limit == 1:
        return [frames[0]]
    step = (len(frames) - 1) / (limit - 1)
    return [frames[round(i * step)] for i in range(limit)]


def _to_seconds(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def parse_vtt(path: Path) -> List[dict]:
    """Parse WebVTT into segments; collapses YouTube auto-sub rolling duplicates."""
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()

    segments: List[dict] = []
    i = 0
    while i < len(lines):
        match = TS_RE.match(lines[i])
        if not match:
            i += 1
            continue

        start = _to_seconds(*match.groups()[:4])
        end = _to_seconds(*match.groups()[4:])
        i += 1

        cue_lines: List[str] = []
        while i < len(lines) and lines[i].strip():
            cleaned = TAG_RE.sub("", lines[i]).strip()
            if cleaned:
                cue_lines.append(cleaned)
            i += 1

        cue_text = " ".join(cue_lines).strip()
        if cue_text:
            segments.append(
                {"start": round(start, 2), "end": round(end, 2), "text": cue_text}
            )
        i += 1

    return _dedupe_segments(segments)


def _dedupe_segments(segments: List[dict]) -> List[dict]:
    out: List[dict] = []
    for seg in segments:
        if out and seg["text"] == out[-1]["text"]:
            out[-1]["end"] = seg["end"]
            continue
        if out and seg["text"].startswith(out[-1]["text"] + " "):
            out[-1]["text"] = seg["text"]
            out[-1]["end"] = seg["end"]
            continue
        if out:
            # YouTube auto-subs slide a window: the next cue repeats the tail
            # of the previous one; cut that overlap to save scorer budget.
            trimmed = _trim_overlap(out[-1]["text"], seg["text"])
            if not trimmed:
                out[-1]["end"] = seg["end"]
                continue
            if trimmed != seg["text"]:
                seg = {**seg, "text": trimmed}
        out.append(seg)
    return out


def _trim_overlap(prev_text: str, text: str) -> str:
    limit = min(len(prev_text), len(text))
    for k in range(limit, 0, -1):
        if not prev_text.endswith(text[:k]):
            continue
        # Short coincidental suffix/prefix matches ("st" in "test"/"styled")
        # would otherwise eat real text: require whole-word alignment unless
        # the overlap is long enough to be a real rolling-window repeat (the
        # length check also covers space-less languages like Chinese).
        if k < 6:
            start = len(prev_text) - k
            if start > 0 and prev_text[start - 1] != " ":
                continue
            if k < len(text) and text[k] != " ":
                continue
        return text[k:].lstrip()
    return text


def format_transcript(segments: List[dict]) -> str:
    lines = []
    for seg in segments:
        start = int(seg["start"])
        lines.append(f"[{start // 60:02d}:{start % 60:02d}] {seg['text']}")
    return "\n".join(lines)


def _parse_mhtml_frames(data: bytes) -> List[str]:
    """Extract JPEG storyboard grids from a YouTube .mhtml file.

    yt-dlp writes mhtml parts as raw 8-bit binary (not base64), so parsing
    must stay on bytes; returns base64-encoded JPEG strings.
    """
    match = re.search(rb'boundary="?([^";\r\n]+)"?', data)
    if not match:
        return []
    frames: List[str] = []
    for part in data.split(b"--" + match.group(1)):
        if b"image/jpeg" not in part:
            continue
        body = None
        for sep in (b"\r\n\r\n", b"\n\n"):
            if sep in part:
                body = part.split(sep, 1)[1]
                break
        if body is None:
            continue
        body = body.rstrip(b"\r\n")
        if body[:3] == b"\xff\xd8\xff":  # JPEG SOI
            frames.append(base64.b64encode(body).decode("ascii"))
    return frames


class VideoScraper(BaseScraper):
    """Scraper for YouTube channels: RSS discovery + subtitle transcripts."""

    def __init__(
        self,
        config: VideoConfig,
        http_client: httpx.AsyncClient,
        ai_config: Optional[AIConfig] = None,
    ):
        super().__init__({"video": config}, http_client)
        self._ai_config = ai_config
        self._channel_id_cache: dict[str, Optional[str]] = {}
        self._asr_loaded = False
        self.last_run_stats = VideoRunStats()

    async def fetch(self, since: datetime) -> List[ContentItem]:
        video_cfg: VideoConfig = self.config["video"]
        self.last_run_stats = VideoRunStats()
        if video_cfg.mode == "sidecar":
            # No preflight here on purpose: the digest host is allowed to have
            # no node, no ffmpeg and no mlx — that is the point of the split.
            items = self._read_inbox(since, video_cfg)
            self._log_run_summary(video_cfg)
            return items
        for problem in self._preflight(video_cfg):
            logger.warning("Video preflight: %s", problem)
        items: List[ContentItem] = []
        try:
            for channel in video_cfg.channels:
                if not channel.enabled:
                    continue
                try:
                    async with asyncio.timeout(900):
                        items.extend(
                            await self._fetch_channel(channel, video_cfg, since)
                        )
                except Exception as e:
                    logger.warning("Video channel %s failed: %s", channel.channel, e)
        finally:
            self._release_asr()
            self._log_run_summary(video_cfg)
        return items

    def _read_inbox(self, since: datetime, video_cfg: VideoConfig) -> List[ContentItem]:
        """Load items produced by a previous `horizon-video` run.

        Every failure here returns an empty list rather than raising: a missing
        or broken inbox must cost the digest its video section, not the run.
        """
        path = Path(video_cfg.inbox_file).expanduser()
        if not path.is_file():
            logger.warning(
                "Video sidecar inbox %s does not exist — is the horizon-video job running?",
                path,
            )
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("Video sidecar inbox %s is unreadable: %s", path, e)
            return []
        if not isinstance(payload, dict) or payload.get("version") != INBOX_VERSION:
            logger.warning(
                "Video sidecar inbox %s has version %s, expected %s — ignoring it; "
                "re-run horizon-video after upgrading",
                path,
                payload.get("version") if isinstance(payload, dict) else "?",
                INBOX_VERSION,
            )
            return []

        self._warn_if_stale(payload, path, video_cfg)
        # Carry the sidecar's own counters through, so the degradation warning
        # still reaches the digest log even though the work happened elsewhere.
        known = {f.name for f in fields(VideoRunStats)}
        raw_stats = payload.get("stats")
        if isinstance(raw_stats, dict):
            self.last_run_stats = VideoRunStats(
                **{k: v for k, v in raw_stats.items() if k in known and isinstance(v, int)}
            )

        items: List[ContentItem] = []
        rejected = 0
        for raw in payload.get("items") or []:
            try:
                item = ContentItem.model_validate(raw)
            except Exception:
                rejected += 1
                continue
            if item.published_at >= since:
                items.append(item)
        if rejected:
            logger.warning(
                "Video sidecar inbox %s: %d item(s) failed validation and were dropped",
                path,
                rejected,
            )
        logger.info("Video sidecar: %d item(s) read from %s", len(items), path)
        return items

    @staticmethod
    def _warn_if_stale(payload: dict, path: Path, video_cfg: VideoConfig) -> None:
        """Flag an inbox the sidecar stopped refreshing."""
        if not video_cfg.inbox_max_age_hours:
            return
        try:
            generated = datetime.fromisoformat(payload["generated_at"])
        except Exception:
            logger.warning("Video sidecar inbox %s has no usable generated_at", path)
            return
        if generated.tzinfo is None:
            generated = generated.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - generated
        if age > timedelta(hours=video_cfg.inbox_max_age_hours):
            logger.warning(
                "Video sidecar inbox %s is %.1fh old (limit %dh) — the horizon-video "
                "job has probably stopped running",
                path,
                age.total_seconds() / 3600,
                video_cfg.inbox_max_age_hours,
            )

    def _preflight(self, video_cfg: VideoConfig) -> List[str]:
        """Report missing runtime prerequisites before they cause silent misses.

        Each of these degrades to "no transcript" deep inside yt-dlp or whisper,
        where the cause is unrecoverable from the log line alone.
        """
        problems: List[str] = []
        if not shutil.which("node"):
            problems.append(
                "node is not on PATH — yt-dlp cannot solve the JS challenge, "
                "so audio formats stay hidden and ASR yields nothing"
            )
        for label in ("cookies_file", "audio_cookies_file"):
            path = getattr(video_cfg, label)
            if path and not Path(path).expanduser().is_file():
                problems.append(f"{label} points at a missing file: {path}")
        if video_cfg.asr == "local":
            if not shutil.which("ffmpeg"):
                problems.append(
                    "ffmpeg is not on PATH — mlx-whisper cannot decode audio, ASR will fail"
                )
            if not _module_available("mlx_whisper"):
                problems.append(
                    'mlx-whisper is not installed — ASR disabled (set video.asr to "off" '
                    'to silence, or install the "asr" extra on Apple Silicon)'
                )
        if video_cfg.vision_fallback and self._ai_config is None:
            problems.append(
                "vision_fallback is on but the scraper got no AI config — vision rung disabled"
            )
        return problems

    def _log_run_summary(self, video_cfg: VideoConfig) -> None:
        """Emit the run outcome, loudly when text extraction is degraded."""
        stats = self.last_run_stats
        if not stats.videos and not stats.bot_gated:
            logger.info("Video run: no new videos in window")
            return
        # Three independent triggers. The rate check needs a few videos to mean
        # anything, but total extraction failure and a bot gate are conclusive
        # on their own — a curated channel set often yields only 1-2 videos a
        # day, which would otherwise keep the rate check permanently silent.
        degraded = (
            stats.bot_gated
            or (stats.graded >= 1 and stats.with_text == 0)
            or (
                video_cfg.min_transcript_rate > 0
                and stats.graded >= 3
                and stats.transcript_rate < video_cfg.min_transcript_rate
            )
        )
        if degraded:
            rate = (
                f" (transcript rate {stats.transcript_rate:.0%})" if stats.graded else ""
            )
            logger.warning(
                "Video run degraded — %s%s; %s",
                stats.summary(),
                rate,
                "re-export the YouTube cookies, they are being rejected"
                if stats.bot_gated
                else "check cookie freshness, node on PATH, and the yt-dlp version",
            )
        else:
            logger.info("Video run: %s", stats.summary())

    def _release_asr(self) -> None:
        """Return the memory whisper used once a run is done.

        MLX keeps a Metal buffer pool that outlives the last transcribe() call,
        so without this a run holds whisper's working set through analysis,
        enrichment and digest generation. Measured on an M4 with
        large-v3-turbo: 1540 MB peak, 378 MB after this runs.

        mlx-whisper 0.4.3 reloads the model on every call and memoises nothing,
        so there is usually no model cache to drop; some releases have carried
        an lru_cache on load_model, which is cleared here when present.
        """
        if not self._asr_loaded:
            return
        self._asr_loaded = False
        # The lru_cache has lived in both mlx_whisper.transcribe and
        # mlx_whisper.load_models across releases, and in neither on 0.4.3.
        # Clear whichever exposes it; its absence is normal, not a problem.
        for module_name in ("mlx_whisper.transcribe", "mlx_whisper.load_models"):
            try:
                module = importlib.import_module(module_name)
            except Exception:
                continue
            cache_clear = getattr(
                getattr(module, "load_model", None), "cache_clear", None
            )
            if cache_clear:
                try:
                    cache_clear()
                except Exception as e:  # pragma: no cover - mlx internals
                    logger.debug("mlx-whisper cache_clear failed: %s", e)
        gc.collect()
        try:
            import mlx.core as mx
        except ImportError:  # pragma: no cover - non-Apple-Silicon hosts
            return
        # mx.clear_cache() on MLX >= 0.21, mx.metal.clear_cache() before it.
        # This is the call that actually returns the memory.
        clear = getattr(mx, "clear_cache", None) or getattr(
            getattr(mx, "metal", None), "clear_cache", None
        )
        if clear is None:
            logger.warning(
                "MLX exposes no clear_cache — whisper's buffer pool stays held for "
                "the rest of the run; check the installed mlx version"
            )
            return
        try:
            clear()
        except Exception as e:  # pragma: no cover - mlx internals
            logger.warning("Could not clear the MLX buffer cache: %s", e)

    async def _fetch_channel(
        self, channel: VideoChannelConfig, video_cfg: VideoConfig, since: datetime
    ) -> List[ContentItem]:
        channel_id = await self._resolve_channel_id(channel.channel)
        if not channel_id:
            logger.warning("Could not resolve channel id for %s", channel.channel)
            return []

        feed_url = YT_CHANNEL_FEED.format(channel_id=channel_id)
        response = await self.client.get(feed_url, follow_redirects=True)
        response.raise_for_status()
        feed = feedparser.parse(response.text)

        fresh = []
        for entry in feed.entries:
            published = self._parse_date(entry)
            if not published or published < since:
                continue
            fresh.append((entry, published))
            if len(fresh) >= channel.max_videos:
                break

        items: List[ContentItem] = []
        for entry, published in fresh:
            self.last_run_stats.videos += 1
            try:
                item = await self._build_item(entry, published, channel, video_cfg)
                if item:
                    items.append(item)
            except Exception as e:
                self.last_run_stats.failed += 1
                logger.warning("Video item failed (%s): %s", entry.get("link"), e)
        return items

    async def _resolve_channel_id(self, channel_ref: str) -> Optional[str]:
        if re.fullmatch(r"UC[0-9A-Za-z_-]{22}", channel_ref):
            return channel_ref
        if channel_ref in self._channel_id_cache:
            return self._channel_id_cache[channel_ref]

        def _resolve() -> Optional[str]:
            import yt_dlp

            url = (
                channel_ref
                if channel_ref.startswith("http")
                else f"https://www.youtube.com/{channel_ref}"
            )
            if not url.rstrip("/").endswith(("/videos", "/streams", "/live")):
                url = url.rstrip("/") + "/videos"
            opts = {
                "quiet": True,
                "no_warnings": True,
                "extract_flat": True,
                "skip_download": True,
                "js_runtimes": {"node": {}},
                "remote_components": ["ejs:github"],
                "extractor_args": {
                    "youtube": {"player_client": ["tv", "android"]}
                },
            }
            if self.config["video"].cookies_file:
                opts["cookiefile"] = self.config["video"].cookies_file
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
            return info.get("channel_id") or (
                info.get("id") if str(info.get("id", "")).startswith("UC") else None
            )

        try:
            channel_id = await asyncio.to_thread(_resolve)
        except Exception as e:
            self._note_ytdlp_error("channel resolve", channel_ref, e)
            channel_id = None
        self._channel_id_cache[channel_ref] = channel_id
        return channel_id

    async def _build_item(
        self,
        entry: dict,
        published: datetime,
        channel: VideoChannelConfig,
        video_cfg: VideoConfig,
    ) -> Optional[ContentItem]:
        url = entry.get("link", "")
        title = entry.get("title", "Untitled")
        video_id = entry.get("yt_videoid") or _video_id_from_url(url)
        stats = self.last_run_stats

        transcript, info = await self._fetch_transcript(url, video_cfg)

        skip = _skip_reason(info, video_cfg)
        if skip:
            stats.skipped += 1
            logger.info("Skipping video %s (%s)", url, skip)
            return None

        source = "subtitles" if transcript else None
        if not transcript and video_cfg.asr == "local":
            duration = info.get("duration")
            too_long = (
                video_cfg.asr_max_duration_sec
                and isinstance(duration, (int, float))
                and duration > video_cfg.asr_max_duration_sec
            )
            if too_long:
                logger.info(
                    "Skipping ASR for %s: %ds exceeds asr_max_duration_sec %ds",
                    url,
                    int(duration),
                    video_cfg.asr_max_duration_sec,
                )
            else:
                transcript = await self._asr_local(url)
                if transcript:
                    source = "asr"

        vision_summary = None
        if not transcript and video_cfg.vision_fallback and self._ai_config:
            vision_summary = await self._vision_fallback(url, video_cfg)
            if vision_summary:
                source = "vision"

        description = (info.get("description") or "").strip() or (
            getattr(entry, "media_description", "") or ""
        )

        parts = []
        if description.strip():
            parts.append(description.strip())
        if transcript:
            parts.append("Transcript:\n" + transcript)
        if vision_summary:
            parts.append("Visual summary (AI from storyboard frames):\n" + vision_summary)
        content = "\n\n".join(parts)[: video_cfg.transcript_max_chars]

        if not content:
            stats.failed += 1
            logger.warning("No usable content for %s (no description, transcript or frames)", url)
            return None

        if source == "subtitles":
            stats.subtitles += 1
        elif source == "asr":
            stats.asr += 1
        elif source == "vision":
            stats.vision += 1
        else:
            source = "description"
            stats.description_only += 1

        return ContentItem(
            id=self._generate_id("video", "youtube", video_id),
            source_type=SourceType.VIDEO,
            title=title,
            url=url,
            content=content,
            author=channel.name or channel.channel,
            published_at=published,
            profile=channel.profile,
            metadata={
                "channel": channel.name or channel.channel,
                "category": channel.category,
                "has_transcript": bool(transcript),
                # Which rung of the extraction ladder produced the text; the
                # only way to tell a real transcript from a description in the
                # stored item afterwards.
                "content_source": source,
                "duration": info.get("duration"),
            },
        )

    async def _fetch_transcript(
        self, video_url: str, video_cfg: VideoConfig
    ) -> Tuple[Optional[str], dict]:
        """Return (timestamped transcript, yt-dlp info dict).

        The channel RSS carries only a truncated description and no duration or
        live status; the yt-dlp metadata call we make anyway yields all of it
        for free, so no extra request is needed to filter Shorts and premieres.
        """
        vtt_path, info = await asyncio.to_thread(
            self._download_subtitles,
            video_url,
            video_cfg.subtitle_langs,
            video_cfg.cookies_from_browser,
            video_cfg.cookies_file,
        )
        if not vtt_path:
            return None, info
        try:
            segments = parse_vtt(vtt_path)
            transcript = format_transcript(segments) if segments else None
            return transcript, info
        finally:
            shutil.rmtree(vtt_path.parent, ignore_errors=True)

    def _note_ytdlp_error(self, stage: str, video_url: str, error: object) -> None:
        """Log a yt-dlp failure, naming the cause when it is the bot gate."""
        if _is_bot_gate(error):
            self.last_run_stats.bot_gated += 1
            logger.warning(
                "YouTube rejected the %s request for %s as a bot — the cookies are "
                "no longer valid; re-export them (see docs/video-source.md)",
                stage,
                video_url,
            )
            return
        logger.warning("%s failed for %s: %s", stage.capitalize(), video_url, error)

    def _download_subtitles(
        self,
        video_url: str,
        langs: List[str],
        cookies_browser: Optional[str],
        cookies_file: Optional[str],
    ) -> Tuple[Optional[Path], dict]:
        import yt_dlp

        tmp = Path(tempfile.mkdtemp(prefix="horizon_video_"))
        opts = {
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": langs,
            "subtitlesformat": "vtt",
            "convertsubtitles": "vtt",
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            # Authenticated sessions can land in the SABR-only streaming
            # experiment where no playable format exists; subtitles still work.
            "ignore_no_formats_error": True,
            "outtmpl": str(tmp / "%(id)s.%(ext)s"),
            # tv/android player clients bypass the "confirm you're not a bot"
            # gate that hits datacenter/VPN IPs on the default web client.
            "extractor_args": {
                "youtube": {"player_client": ["tv", "android"]}
            },
        }
        if cookies_browser:
            opts["cookiesfrombrowser"] = (cookies_browser,)
        if cookies_file:
            opts["cookiefile"] = cookies_file
        info: dict = {}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(video_url, download=True) or {}
        except Exception as e:
            self._note_ytdlp_error("subtitle fetch", video_url, e)

        candidates = sorted(tmp.glob("*.vtt"))
        if not candidates:
            shutil.rmtree(tmp, ignore_errors=True)
            return None, info
        preferred = [
            c
            for c in candidates
            if c.name.split(".")[-2].startswith(("en", "ru"))
        ]
        return (preferred[0] if preferred else candidates[0]), info

    async def _asr_local(self, video_url: str) -> Optional[str]:
        """Transcribe video audio locally with mlx-whisper (Apple Silicon)."""
        audio = await asyncio.to_thread(self._download_audio, video_url)
        if not audio:
            return None
        try:
            model = self.config["video"].asr_model
            # Marks the weights as resident so fetch() knows to free them; the
            # model stays cached across videos within one run on purpose.
            self._asr_loaded = True
            return await asyncio.to_thread(self._transcribe, audio, model)
        except ImportError:
            logger.warning("mlx-whisper not installed; skipping local ASR")
            return None
        except Exception as e:
            logger.warning("ASR failed for %s: %s", video_url, e)
            return None
        finally:
            shutil.rmtree(audio.parent, ignore_errors=True)

    def _download_audio(self, video_url: str) -> Optional[Path]:
        """Download audio-only format.

        Uses audio_cookies_file (alt account) when set: the main account may
        be in the SABR experiment that hides audio formats; unauthenticated
        requests hit the bot-gate from datacenter egress.
        """
        import yt_dlp

        tmp = Path(tempfile.mkdtemp(prefix="horizon_asr_"))
        opts = {
            "format": "ba/bestaudio",
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "ignore_no_formats_error": True,
            # Python API does not autodetect JS runtimes; node is required to
            # solve the n-challenge, otherwise audio formats stay SABR-hidden.
            "js_runtimes": {"node": {}},
            "remote_components": ["ejs:github"],
            "outtmpl": str(tmp / "%(id)s.%(ext)s"),
            "extractor_args": {
                # tv_embedded ALONE: it escapes the SABR-only experiment that
                # hides audio formats on datacenter IPs; adding other clients
                # (tv/web) poisons the format merge back to SABR-only.
                "youtube": {"player_client": ["tv_embedded"]}
            },
        }
        audio_cookies = self.config["video"].audio_cookies_file
        if audio_cookies:
            opts["cookiefile"] = audio_cookies
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.extract_info(video_url, download=True)
        except Exception as e:
            self._note_ytdlp_error("audio download", video_url, e)
        audio_exts = {".m4a", ".mp3", ".opus", ".webm", ".aac", ".mp4", ".ogg"}
        files = [f for f in tmp.iterdir() if f.suffix.lower() in audio_exts]
        if not files:
            shutil.rmtree(tmp, ignore_errors=True)
            return None
        return files[0]

    @staticmethod
    def _transcribe(audio_path: Path, model: str) -> Optional[str]:
        import mlx_whisper

        result = mlx_whisper.transcribe(
            str(audio_path),
            path_or_hf_repo=model,
            verbose=False,
        )
        segments = result.get("segments") or []
        lines = []
        for seg in segments:
            start = int(seg.get("start", 0))
            text = (seg.get("text") or "").strip()
            if text:
                lines.append(f"[{start // 60:02d}:{start % 60:02d}] {text}")
        return "\n".join(lines) or (result.get("text") or "").strip() or None

    async def _vision_fallback(
        self, video_url: str, video_cfg: VideoConfig
    ) -> Optional[str]:
        """Summarize video visually when no subtitles exist.

        Downloads the YouTube storyboard (mhtml frame grids, available even
        when video formats are SABR-blocked) and asks the configured vision
        model to describe the content.
        """
        frames = await asyncio.to_thread(self._fetch_storyboard, video_url)
        if not frames:
            return None
        frames = _sample_frames(frames, video_cfg.vision_max_frames)
        try:
            return await self._vision_summarize(frames)
        except Exception as e:
            logger.warning("Vision fallback failed for %s: %s", video_url, e)
            return None

    def _fetch_storyboard(self, video_url: str) -> List[str]:
        """Return storyboard grid images as base64 JPEG strings."""
        import yt_dlp

        tmp = Path(tempfile.mkdtemp(prefix="horizon_sb_"))
        opts = {
            "format": "sb0/sb1",
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "ignore_no_formats_error": True,
            "js_runtimes": {"node": {}},
            "remote_components": ["ejs:github"],
            "outtmpl": str(tmp / "%(id)s.%(ext)s"),
            "extractor_args": {
                "youtube": {"player_client": ["tv", "android"]}
            },
        }
        if self.config["video"].cookies_file:
            opts["cookiefile"] = self.config["video"].cookies_file
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.extract_info(video_url, download=True)
        except Exception as e:
            self._note_ytdlp_error("storyboard download", video_url, e)
        files = sorted(tmp.glob("*.mhtml"))
        frames: List[str] = []
        if files:
            frames = _parse_mhtml_frames(files[0].read_bytes())
        shutil.rmtree(tmp, ignore_errors=True)
        return frames

    async def _vision_summarize(self, frames_b64: List[str]) -> Optional[str]:
        ai = self._ai_config
        api_key = os.environ.get(ai.api_key_env, "")
        if not api_key:
            return None
        base = (ai.base_url or "").rstrip("/")
        content: List[dict] = [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b}"}}
            for b in frames_b64
        ]
        content.append(
            {
                "type": "text",
                "text": (
                    "These are chronological storyboard frame grids from a YouTube "
                    "video. Describe what happens in the video: visible topics, "
                    "on-screen text, scenes and actions. 3-6 sentences."
                ),
            }
        )
        resp = await self.client.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": ai.model,
                "messages": [{"role": "user", "content": content}],
                "max_tokens": 400,
            },
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        usage = data.get("usage") or {}
        record_usage(
            getattr(ai.provider, "value", ai.provider),
            usage.get("prompt_tokens", 0) or 0,
            usage.get("completion_tokens", 0) or 0,
        )
        return (data.get("choices") or [{}])[0].get("message", {}).get("content") or None

    def _parse_date(self, entry: dict) -> Optional[datetime]:
        for field in ["published", "updated", "created"]:
            if f"{field}_parsed" in entry and entry[f"{field}_parsed"]:
                try:
                    return datetime.fromtimestamp(
                        calendar.timegm(entry[f"{field}_parsed"]), tz=timezone.utc
                    )
                except Exception:
                    continue
            if field in entry:
                try:
                    parsed = parsedate_to_datetime(entry[field])
                except Exception:
                    continue
                # A naive datetime here would raise on the `published < since`
                # comparison and take the whole channel down with it.
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed
        return None
