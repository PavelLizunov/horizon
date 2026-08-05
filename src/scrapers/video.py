"""YouTube channel scraper with transcript ingestion.

Design adapted from bradautomates/claude-video (MIT): new videos are
discovered via the channel RSS feed, subtitles are fetched with yt-dlp
without downloading the video, and VTT cues are cleaned into a
timestamped transcript that becomes the item content.
"""

import asyncio
import base64
import calendar
import logging
import os
import re
import shutil
import tempfile
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import List, Optional, Tuple

import feedparser
import httpx

from .base import BaseScraper
from ..ai.tokens import record_usage
from ..models import AIConfig, ContentItem, SourceType, VideoChannelConfig, VideoConfig

logger = logging.getLogger(__name__)

YT_CHANNEL_FEED = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

TS_RE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2})[.,](\d{3})\s+-->\s+(\d{2}):(\d{2}):(\d{2})[.,](\d{3})"
)
TAG_RE = re.compile(r"<[^>]+>")


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

    async def fetch(self, since: datetime) -> List[ContentItem]:
        video_cfg: VideoConfig = self.config["video"]
        items: List[ContentItem] = []
        for channel in video_cfg.channels:
            if not channel.enabled:
                continue
            try:
                async with asyncio.timeout(900):
                    items.extend(await self._fetch_channel(channel, video_cfg, since))
            except Exception as e:
                logger.warning("Video channel %s failed: %s", channel.channel, e)
        return items

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
            try:
                item = await self._build_item(entry, published, channel, video_cfg)
                if item:
                    items.append(item)
            except Exception as e:
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
            logger.warning("Channel resolve failed for %s: %s", channel_ref, e)
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
        video_id = entry.get("yt_videoid") or url.rsplit("=", 1)[-1]

        transcript, full_desc = await self._fetch_transcript(url, video_cfg)
        description = full_desc or (getattr(entry, "media_description", "") or "")

        if not transcript and video_cfg.asr == "local":
            transcript = await self._asr_local(url)

        vision_summary = None
        if not transcript and video_cfg.vision_fallback and self._ai_config:
            vision_summary = await self._vision_fallback(url, video_cfg)

        parts = []
        if description.strip():
            parts.append(description.strip())
        if transcript:
            parts.append("Transcript:\n" + transcript)
        if vision_summary:
            parts.append("Visual summary (AI from storyboard frames):\n" + vision_summary)
        content = "\n\n".join(parts)[: video_cfg.transcript_max_chars]

        if not content:
            return None

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
            },
        )

    async def _fetch_transcript(
        self, video_url: str, video_cfg: VideoConfig
    ) -> Tuple[Optional[str], Optional[str]]:
        """Return (timestamped transcript, full description from yt-dlp).

        The channel RSS only carries a truncated description; the yt-dlp
        metadata call we make anyway yields the full one for free.
        """
        vtt_path, info = await asyncio.to_thread(
            self._download_subtitles,
            video_url,
            video_cfg.subtitle_langs,
            video_cfg.cookies_from_browser,
            video_cfg.cookies_file,
        )
        description = (info.get("description") or "").strip() or None
        if not vtt_path:
            return None, description
        try:
            segments = parse_vtt(vtt_path)
            transcript = format_transcript(segments) if segments else None
            return transcript, description
        finally:
            shutil.rmtree(vtt_path.parent, ignore_errors=True)

    @staticmethod
    def _download_subtitles(
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
            logger.warning("yt-dlp subtitle fetch failed for %s: %s", video_url, e)

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
            logger.warning("Audio download failed for %s: %s", video_url, e)
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
        frames = frames[: video_cfg.vision_max_frames]
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
            logger.warning("Storyboard download failed for %s: %s", video_url, e)
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
                    return parsedate_to_datetime(entry[field])
                except Exception:
                    continue
        return None
