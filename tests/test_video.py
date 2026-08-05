"""Unit tests for the YouTube video scraper (no network, no yt-dlp)."""

from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models import VideoChannelConfig, VideoConfig
from src.scrapers.video import (
    VideoScraper,
    _dedupe_segments,
    _parse_mhtml_frames,
    _trim_overlap,
    format_transcript,
    parse_vtt,
)

_CHANNEL_ID = "UCA" + "a" * 21

_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015"
      xmlns:media="http://search.yahoo.com/mrss/"
      xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>yt:video:abc123def45</id>
    <yt:videoId>abc123def45</yt:videoId>
    <title>Test Video</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=abc123def45"/>
    <author><name>Test Channel</name></author>
    <published>2026-08-01T10:00:00+00:00</published>
    <media:group><media:description>short rss desc</media:description></media:group>
  </entry>
</feed>
"""

_VTT = """WEBVTT
Kind: captions
Language: en

00:00:00.000 --> 00:00:02.000
hello world

00:00:02.000 --> 00:00:04.000
hello world this is a test

00:01:05.500 --> 00:01:07.000
<font color="#FFFFFF">styled cue</font>
"""


def test_trim_overlap_cuts_rolling_window_tail() -> None:
    assert _trim_overlap("hello world", "hello world this is a test") == "this is a test"
    assert _trim_overlap("abc def", "def ghi") == "ghi"


def test_trim_overlap_keeps_text_without_overlap() -> None:
    assert _trim_overlap("abc", "xyz") == "xyz"


def test_dedupe_merges_exact_and_prefix_duplicates() -> None:
    segments = [
        {"start": 0.0, "end": 2.0, "text": "hello world"},
        {"start": 2.0, "end": 4.0, "text": "hello world"},
        {"start": 4.0, "end": 6.0, "text": "hello world this is a test"},
        {"start": 6.0, "end": 8.0, "text": "unrelated"},
    ]
    out = _dedupe_segments(segments)
    assert [s["text"] for s in out] == ["hello world this is a test", "unrelated"]
    assert out[0]["end"] == 6.0


def test_parse_vtt_strips_tags_and_dedupes(tmp_path) -> None:
    vtt = tmp_path / "subs.vtt"
    vtt.write_text(_VTT, encoding="utf-8")
    segments = parse_vtt(vtt)
    assert segments[0]["text"] == "hello world this is a test"
    assert segments[1] == {"start": 65.5, "end": 67.0, "text": "styled cue"}


def test_format_transcript_renders_timestamps() -> None:
    segments = [
        {"start": 0.0, "end": 2.0, "text": "first"},
        {"start": 65.5, "end": 67.0, "text": "second"},
    ]
    assert format_transcript(segments) == "[00:00] first\n[01:05] second"


def test_parse_mhtml_frames_reads_raw_binary_parts() -> None:
    jpeg = b"\xff\xd8\xff\xe0" + b"\x00" * 8 + b"\xff\xd9"
    data = (
        b"Content-Type: multipart/related; boundary=\"xyz\"\r\n\r\n"
        b"--xyz\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
        b"--xyz\r\nContent-Type: text/plain\r\n\r\nnot an image\r\n"
        b"--xyz--\r\n"
    )
    frames = _parse_mhtml_frames(data)
    assert len(frames) == 1
    assert base64.b64decode(frames[0]) == jpeg


def test_parse_mhtml_frames_empty_without_boundary() -> None:
    assert _parse_mhtml_frames(b"no boundary here") == []


def test_channel_id_reference_passes_through_without_ytdlp() -> None:
    scraper = VideoScraper(VideoConfig(), None)
    resolved = asyncio.run(scraper._resolve_channel_id(_CHANNEL_ID))
    assert resolved == _CHANNEL_ID


def test_video_config_defaults() -> None:
    cfg = VideoConfig()
    assert cfg.enabled is False
    assert cfg.asr == "local"
    assert cfg.vision_fallback is True
    assert cfg.subtitle_langs == ["en.*", "ru.*"]


def _make_feed_client(feed_text: str) -> AsyncMock:
    response = MagicMock()
    response.text = feed_text
    response.raise_for_status.return_value = None
    client = AsyncMock()
    client.get.return_value = response
    return client


def _make_scraper(monkeypatch, vtt_path=None) -> VideoScraper:
    config = VideoConfig(
        enabled=True,
        channels=[
            VideoChannelConfig(name="Test Channel", channel=_CHANNEL_ID, max_videos=3)
        ],
    )
    scraper = VideoScraper(config, _make_feed_client(_FEED))

    def fake_download_subtitles(video_url, langs, cookies_browser, cookies_file):
        info = {"description": "full description from yt-dlp"}
        return vtt_path, info

    monkeypatch.setattr(
        VideoScraper, "_download_subtitles", staticmethod(fake_download_subtitles)
    )
    return scraper


@pytest.fixture
def vtt_file(tmp_path):
    path = tmp_path / "abc123def45.vtt"
    path.write_text(_VTT, encoding="utf-8")
    return path


def test_fetch_builds_item_from_rss_and_transcript(monkeypatch, vtt_file) -> None:
    scraper = _make_scraper(monkeypatch, vtt_path=vtt_file)
    since = datetime(2026, 7, 1, tzinfo=timezone.utc)

    items = asyncio.run(scraper.fetch(since))

    assert len(items) == 1
    item = items[0]
    assert item.id == "video:youtube:abc123def45"
    assert item.title == "Test Video"
    assert item.author == "Test Channel"
    assert item.profile is None
    assert item.metadata["has_transcript"] is True
    assert "full description from yt-dlp" in item.content
    assert "Transcript:" in item.content
    assert "[00:00] hello world this is a test" in item.content


def test_fetch_skips_items_before_window(monkeypatch, vtt_file) -> None:
    scraper = _make_scraper(monkeypatch, vtt_path=vtt_file)
    since = datetime(2026, 8, 2, tzinfo=timezone.utc)

    assert asyncio.run(scraper.fetch(since)) == []


def test_fetch_falls_back_to_description_without_transcript(monkeypatch) -> None:
    scraper = _make_scraper(monkeypatch, vtt_path=None)
    since = datetime(2026, 7, 1, tzinfo=timezone.utc)

    items = asyncio.run(scraper.fetch(since))

    assert len(items) == 1
    assert items[0].metadata["has_transcript"] is False
    assert items[0].content == "full description from yt-dlp"


def test_fetch_isolates_channel_failures(monkeypatch, vtt_file) -> None:
    config = VideoConfig(
        enabled=True,
        channels=[
            VideoChannelConfig(name="Broken", channel="UCB" + "b" * 21),
            VideoChannelConfig(name="Test Channel", channel=_CHANNEL_ID),
        ],
    )
    scraper = VideoScraper(config, _make_feed_client(_FEED))

    def fake_download_subtitles(video_url, langs, cookies_browser, cookies_file):
        return vtt_file, {"description": "desc"}

    monkeypatch.setattr(
        VideoScraper, "_download_subtitles", staticmethod(fake_download_subtitles)
    )

    async def fail_resolve(self, channel_ref):
        if channel_ref.startswith("UCB"):
            raise RuntimeError("channel exploded")
        return channel_ref

    monkeypatch.setattr(VideoScraper, "_resolve_channel_id", fail_resolve)

    items = asyncio.run(scraper.fetch(datetime(2026, 7, 1, tzinfo=timezone.utc)))
    assert len(items) == 1
    assert items[0].author == "Test Channel"
