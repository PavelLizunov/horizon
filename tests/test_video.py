"""Unit tests for the YouTube video scraper (no network, no yt-dlp)."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import sys
import types
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models import ContentItem, SourceType, VideoChannelConfig, VideoConfig
from src.scrapers import video as video_module
from src.scrapers.video import (
    VideoRunStats,
    VideoScraper,
    _dedupe_segments,
    _is_bot_gate,
    _parse_mhtml_frames,
    _sample_frames,
    _skip_reason,
    _trim_overlap,
    _video_id_from_url,
    format_transcript,
    parse_vtt,
    write_inbox,
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


def _make_scraper(monkeypatch, vtt_path=None, info=None, **cfg_kwargs) -> VideoScraper:
    # asr defaults to "local"; leaving it on would send the no-transcript tests
    # into a real yt-dlp audio download. Tests that exercise ASR opt back in.
    cfg_kwargs.setdefault("asr", "off")
    config = VideoConfig(
        enabled=True,
        channels=[
            VideoChannelConfig(name="Test Channel", channel=_CHANNEL_ID, max_videos=3)
        ],
        **cfg_kwargs,
    )
    scraper = VideoScraper(config, _make_feed_client(_FEED))
    payload = {"description": "full description from yt-dlp"} if info is None else info

    def fake_download_subtitles(self, video_url, langs, cookies_browser, cookies_file):
        return vtt_path, dict(payload)

    monkeypatch.setattr(VideoScraper, "_download_subtitles", fake_download_subtitles)
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

    def fake_download_subtitles(self, video_url, langs, cookies_browser, cookies_file):
        return vtt_file, {"description": "desc"}

    monkeypatch.setattr(VideoScraper, "_download_subtitles", fake_download_subtitles)

    async def fail_resolve(self, channel_ref):
        if channel_ref.startswith("UCB"):
            raise RuntimeError("channel exploded")
        return channel_ref

    monkeypatch.setattr(VideoScraper, "_resolve_channel_id", fail_resolve)

    items = asyncio.run(scraper.fetch(datetime(2026, 7, 1, tzinfo=timezone.utc)))
    assert len(items) == 1
    assert items[0].author == "Test Channel"


# --- edge cases: what arrives from a real channel feed -----------------------


def test_sample_frames_spreads_over_the_whole_storyboard() -> None:
    frames = [str(i) for i in range(20)]
    picked = _sample_frames(frames, 4)
    # First and last grid must be present, otherwise a long video is described
    # from its intro alone.
    assert picked[0] == "0" and picked[-1] == "19"
    assert picked == ["0", "6", "13", "19"]


def test_sample_frames_handles_small_and_degenerate_budgets() -> None:
    assert _sample_frames(["a", "b"], 8) == ["a", "b"]
    assert _sample_frames(["a", "b", "c"], 1) == ["a"]
    assert _sample_frames(["a", "b", "c"], 0) == []
    assert _sample_frames([], 4) == []


def test_skip_reason_filters_shorts_and_premieres() -> None:
    cfg = VideoConfig()
    assert _skip_reason({"duration": 45}, cfg) is not None
    assert _skip_reason({"live_status": "is_upcoming"}, cfg) is not None
    assert _skip_reason({"live_status": "is_live"}, cfg) is not None


def test_skip_reason_fails_open_on_missing_metadata() -> None:
    cfg = VideoConfig()
    # A yt-dlp change that drops these fields must not empty the digest.
    assert _skip_reason({}, cfg) is None
    assert _skip_reason({"duration": None}, cfg) is None
    assert _skip_reason({"duration": 0}, cfg) is None
    # Finished livestream VODs are ordinary videos.
    assert _skip_reason({"live_status": "was_live", "duration": 900}, cfg) is None
    assert _skip_reason({"duration": 45}, VideoConfig(min_duration_sec=0)) is None


def test_video_id_from_url_covers_youtube_url_shapes() -> None:
    assert _video_id_from_url("https://www.youtube.com/watch?v=abc123def45") == "abc123def45"
    assert _video_id_from_url("https://www.youtube.com/shorts/abc123def45") == "abc123def45"
    assert _video_id_from_url("https://youtu.be/abc123def45") == "abc123def45"


def test_fetch_skips_shorts_without_building_items(monkeypatch, vtt_file) -> None:
    scraper = _make_scraper(
        monkeypatch, vtt_path=vtt_file, info={"description": "d", "duration": 45}
    )

    items = asyncio.run(scraper.fetch(datetime(2026, 7, 1, tzinfo=timezone.utc)))

    assert items == []
    assert scraper.last_run_stats.skipped == 1
    assert scraper.last_run_stats.videos == 1


def test_fetch_skips_asr_for_overlong_videos(monkeypatch) -> None:
    scraper = _make_scraper(
        monkeypatch,
        vtt_path=None,
        info={"description": "d", "duration": 9000},
        asr="local",
    )
    called = []

    async def fake_asr(self, url):
        called.append(url)
        return "should not happen"

    monkeypatch.setattr(VideoScraper, "_asr_local", fake_asr)

    items = asyncio.run(scraper.fetch(datetime(2026, 7, 1, tzinfo=timezone.utc)))

    assert called == []
    assert items[0].metadata["content_source"] == "description"
    assert scraper.last_run_stats.description_only == 1


def test_fetch_uses_asr_when_subtitles_are_missing(monkeypatch) -> None:
    scraper = _make_scraper(
        monkeypatch, vtt_path=None, info={"description": "d", "duration": 600}, asr="local"
    )

    async def fake_asr(self, url):
        return "[00:00] spoken words"

    monkeypatch.setattr(VideoScraper, "_asr_local", fake_asr)

    items = asyncio.run(scraper.fetch(datetime(2026, 7, 1, tzinfo=timezone.utc)))

    assert "[00:00] spoken words" in items[0].content
    assert items[0].metadata["content_source"] == "asr"
    assert scraper.last_run_stats.asr == 1


def test_parse_date_normalizes_naive_timestamps() -> None:
    scraper = VideoScraper(VideoConfig(), None)
    # RFC-2822 without a zone: comparing this against an aware `since` would
    # raise and take the whole channel down.
    parsed = scraper._parse_date({"published": "Sat, 01 Aug 2026 10:00:00"})
    assert parsed is not None and parsed.tzinfo is not None
    assert parsed > datetime(2026, 7, 1, tzinfo=timezone.utc)


# --- observability: the run must not degrade silently ------------------------


def test_preflight_reports_missing_runtime_dependencies(monkeypatch) -> None:
    monkeypatch.setattr(video_module.shutil, "which", lambda name: None)
    monkeypatch.setattr(video_module, "_module_available", lambda name: False)
    scraper = VideoScraper(VideoConfig(asr="local", vision_fallback=True), None)

    problems = " | ".join(scraper._preflight(scraper.config["video"]))

    assert "node" in problems
    assert "ffmpeg" in problems
    assert "mlx-whisper" in problems
    assert "vision_fallback" in problems


def test_preflight_flags_missing_cookie_files(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(video_module.shutil, "which", lambda name: "/usr/bin/" + name)
    monkeypatch.setattr(video_module, "_module_available", lambda name: True)
    present = tmp_path / "cookies.txt"
    present.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
    config = VideoConfig(
        asr="local",
        vision_fallback=False,
        cookies_file=str(present),
        audio_cookies_file=str(tmp_path / "gone.txt"),
    )
    scraper = VideoScraper(config, None)

    problems = scraper._preflight(config)

    assert len(problems) == 1
    assert "audio_cookies_file" in problems[0]


def test_preflight_is_quiet_on_a_healthy_box(monkeypatch) -> None:
    monkeypatch.setattr(video_module.shutil, "which", lambda name: "/usr/bin/" + name)
    monkeypatch.setattr(video_module, "_module_available", lambda name: True)
    scraper = VideoScraper(VideoConfig(asr="local", vision_fallback=False), None)

    assert scraper._preflight(scraper.config["video"]) == []


def test_run_summary_warns_when_transcript_rate_collapses(caplog) -> None:
    scraper = VideoScraper(VideoConfig(min_transcript_rate=0.5), None)
    scraper.last_run_stats = VideoRunStats(videos=4, subtitles=1, description_only=3)

    with caplog.at_level(logging.WARNING, logger="src.scrapers.video"):
        scraper._log_run_summary(scraper.config["video"])

    assert "degraded" in caplog.text
    assert "transcript rate 25%" in caplog.text


def test_run_summary_stays_quiet_when_healthy(caplog) -> None:
    scraper = VideoScraper(VideoConfig(min_transcript_rate=0.5), None)
    scraper.last_run_stats = VideoRunStats(videos=4, subtitles=3, description_only=1)

    with caplog.at_level(logging.WARNING, logger="src.scrapers.video"):
        scraper._log_run_summary(scraper.config["video"])

    assert caplog.text == ""


def test_run_summary_ignores_tiny_samples(caplog) -> None:
    scraper = VideoScraper(VideoConfig(min_transcript_rate=0.5), None)
    # One bad video out of two is noise — as long as the other one worked.
    scraper.last_run_stats = VideoRunStats(videos=2, subtitles=1, description_only=1)

    with caplog.at_level(logging.WARNING, logger="src.scrapers.video"):
        scraper._log_run_summary(scraper.config["video"])

    assert caplog.text == ""


def test_run_summary_warns_when_nothing_yielded_text(caplog) -> None:
    scraper = VideoScraper(VideoConfig(min_transcript_rate=0.5), None)
    # Observed in production: a curated channel set yields 1-2 videos a day, so
    # the >=3 rate check never fires. Zero extraction is conclusive on its own.
    scraper.last_run_stats = VideoRunStats(videos=1, description_only=1)

    with caplog.at_level(logging.WARNING, logger="src.scrapers.video"):
        scraper._log_run_summary(scraper.config["video"])

    assert "degraded" in caplog.text


def test_is_bot_gate_matches_youtubes_wording() -> None:
    assert _is_bot_gate("ERROR: [youtube] X: Sign in to confirm you're not a bot.")
    assert _is_bot_gate("Sign in to confirm you’re not a bot")  # curly apostrophe
    assert not _is_bot_gate("HTTP Error 429: Too Many Requests")


def test_note_ytdlp_error_names_the_bot_gate(caplog) -> None:
    scraper = VideoScraper(VideoConfig(), None)

    with caplog.at_level(logging.WARNING, logger="src.scrapers.video"):
        scraper._note_ytdlp_error(
            "audio download", "https://youtu.be/x", "Sign in to confirm you're not a bot"
        )

    assert scraper.last_run_stats.bot_gated == 1
    assert "re-export" in caplog.text


def test_note_ytdlp_error_passes_other_failures_through(caplog) -> None:
    scraper = VideoScraper(VideoConfig(), None)

    with caplog.at_level(logging.WARNING, logger="src.scrapers.video"):
        scraper._note_ytdlp_error("audio download", "https://youtu.be/x", "boom")

    assert scraper.last_run_stats.bot_gated == 0
    assert "boom" in caplog.text


def test_run_summary_escalates_a_bot_gate_regardless_of_sample_size(caplog) -> None:
    scraper = VideoScraper(VideoConfig(), None)
    scraper.last_run_stats = VideoRunStats(videos=1, description_only=1, bot_gated=3)

    with caplog.at_level(logging.WARNING, logger="src.scrapers.video"):
        scraper._log_run_summary(scraper.config["video"])

    assert "re-export the YouTube cookies" in caplog.text
    assert "3 bot-gated" in caplog.text


def test_run_summary_reports_a_bot_gate_with_no_videos_at_all(caplog) -> None:
    # Channel resolution itself can be gated, leaving zero videos to count.
    scraper = VideoScraper(VideoConfig(), None)
    scraper.last_run_stats = VideoRunStats(bot_gated=4)

    with caplog.at_level(logging.WARNING, logger="src.scrapers.video"):
        scraper._log_run_summary(scraper.config["video"])

    assert "degraded" in caplog.text


def test_run_summary_excludes_skipped_videos_from_the_rate() -> None:
    stats = VideoRunStats(videos=5, subtitles=2, skipped=3)
    # Skipped Shorts must not count as failures to extract text.
    assert stats.graded == 2
    assert stats.transcript_rate == 1.0


def test_fetch_records_stats_and_content_source(monkeypatch, vtt_file) -> None:
    scraper = _make_scraper(monkeypatch, vtt_path=vtt_file)

    items = asyncio.run(scraper.fetch(datetime(2026, 7, 1, tzinfo=timezone.utc)))

    stats = scraper.last_run_stats
    assert (stats.videos, stats.subtitles, stats.failed) == (1, 1, 0)
    assert items[0].metadata["content_source"] == "subtitles"
    assert "1 subtitles" in stats.summary()


# --- ASR memory: whisper must not stay resident after the run ----------------


def _install_fake_mlx(monkeypatch, cache_home: str = "mlx_whisper.load_models") -> dict:
    """Stand in for mlx-whisper/mlx so the release path runs without Metal.

    `cache_home` picks which module exposes the lru_cache: mlx-whisper has
    moved it between `transcribe` and `load_models` across releases.
    """
    calls = {"cache_clear": 0, "clear_cache": 0}
    mlx_whisper = types.ModuleType("mlx_whisper")
    modules = {"mlx_whisper": mlx_whisper}

    for name in ("mlx_whisper.transcribe", "mlx_whisper.load_models"):
        submodule = types.ModuleType(name)
        submodule.load_model = MagicMock()
        if name == cache_home:
            submodule.load_model.cache_clear = lambda: calls.__setitem__(
                "cache_clear", calls["cache_clear"] + 1
            )
        else:
            del submodule.load_model.cache_clear
        setattr(mlx_whisper, name.rsplit(".", 1)[1], submodule)
        modules[name] = submodule

    mlx = types.ModuleType("mlx")
    mlx_core = types.ModuleType("mlx.core")
    mlx_core.clear_cache = lambda: calls.__setitem__(
        "clear_cache", calls["clear_cache"] + 1
    )
    mlx.core = mlx_core
    modules["mlx"] = mlx
    modules["mlx.core"] = mlx_core

    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)
    return calls


@pytest.mark.parametrize(
    "cache_home", ["mlx_whisper.transcribe", "mlx_whisper.load_models"]
)
def test_release_asr_frees_model_and_buffers(monkeypatch, cache_home) -> None:
    calls = _install_fake_mlx(monkeypatch, cache_home)
    scraper = VideoScraper(VideoConfig(), None)
    scraper._asr_loaded = True

    scraper._release_asr()

    assert calls == {"cache_clear": 1, "clear_cache": 1}
    assert scraper._asr_loaded is False


def test_release_asr_is_a_noop_when_never_transcribed(monkeypatch) -> None:
    calls = _install_fake_mlx(monkeypatch)
    scraper = VideoScraper(VideoConfig(), None)

    scraper._release_asr()

    # Loading mlx just to free nothing would cost seconds and import Metal.
    assert calls == {"cache_clear": 0, "clear_cache": 0}


def _sidecar_item(video_id: str = "abc123def45", published=None) -> ContentItem:
    return ContentItem(
        id=f"video:youtube:{video_id}",
        source_type=SourceType.VIDEO,
        title="Sidecar Video",
        url=f"https://www.youtube.com/watch?v={video_id}",
        content="Transcript:\n[00:00] hello",
        author="Test Channel",
        published_at=published or datetime(2026, 8, 1, 10, tzinfo=timezone.utc),
        metadata={"channel": "Test Channel", "content_source": "subtitles"},
    )


def _sidecar_scraper(inbox, **cfg_kwargs) -> VideoScraper:
    config = VideoConfig(
        enabled=True, mode="sidecar", inbox_file=str(inbox), **cfg_kwargs
    )
    return VideoScraper(config, None)


def test_sidecar_round_trip_preserves_items_and_stats(tmp_path) -> None:
    inbox = tmp_path / "video-inbox.json"
    stats = VideoRunStats(videos=2, subtitles=2)
    write_inbox(inbox, [_sidecar_item()], stats)

    scraper = _sidecar_scraper(inbox)
    items = asyncio.run(scraper.fetch(datetime(2026, 7, 1, tzinfo=timezone.utc)))

    assert len(items) == 1
    assert items[0].id == "video:youtube:abc123def45"
    assert items[0].metadata["content_source"] == "subtitles"
    # The sidecar's health numbers must survive into the digest run.
    assert scraper.last_run_stats.subtitles == 2


def test_sidecar_write_is_atomic(tmp_path) -> None:
    inbox = tmp_path / "nested" / "video-inbox.json"
    write_inbox(inbox, [_sidecar_item()], VideoRunStats(videos=1, subtitles=1))

    assert inbox.is_file()
    # No temporary leftovers a reader could trip over.
    assert [p.name for p in inbox.parent.iterdir()] == ["video-inbox.json"]


def test_sidecar_applies_the_time_window(tmp_path) -> None:
    inbox = tmp_path / "video-inbox.json"
    write_inbox(
        inbox,
        [
            _sidecar_item("old11111111", datetime(2026, 6, 1, tzinfo=timezone.utc)),
            _sidecar_item("new11111111", datetime(2026, 8, 1, tzinfo=timezone.utc)),
        ],
        VideoRunStats(videos=2, subtitles=2),
    )

    scraper = _sidecar_scraper(inbox)
    items = asyncio.run(scraper.fetch(datetime(2026, 7, 1, tzinfo=timezone.utc)))

    assert [i.id for i in items] == ["video:youtube:new11111111"]


def test_sidecar_missing_inbox_degrades_with_a_warning(tmp_path, caplog) -> None:
    scraper = _sidecar_scraper(tmp_path / "absent.json")

    with caplog.at_level(logging.WARNING, logger="src.scrapers.video"):
        items = asyncio.run(scraper.fetch(datetime(2026, 7, 1, tzinfo=timezone.utc)))

    assert items == []
    assert "does not exist" in caplog.text


def test_sidecar_corrupt_inbox_degrades_with_a_warning(tmp_path, caplog) -> None:
    inbox = tmp_path / "video-inbox.json"
    inbox.write_text("{not json", encoding="utf-8")
    scraper = _sidecar_scraper(inbox)

    with caplog.at_level(logging.WARNING, logger="src.scrapers.video"):
        items = asyncio.run(scraper.fetch(datetime(2026, 7, 1, tzinfo=timezone.utc)))

    assert items == []
    assert "unreadable" in caplog.text


def test_sidecar_rejects_a_foreign_schema_version(tmp_path, caplog) -> None:
    inbox = tmp_path / "video-inbox.json"
    inbox.write_text(json.dumps({"version": 99, "items": []}), encoding="utf-8")
    scraper = _sidecar_scraper(inbox)

    with caplog.at_level(logging.WARNING, logger="src.scrapers.video"):
        items = asyncio.run(scraper.fetch(datetime(2026, 7, 1, tzinfo=timezone.utc)))

    assert items == []
    assert "version 99" in caplog.text


def test_sidecar_drops_bad_items_but_keeps_the_batch(tmp_path, caplog) -> None:
    inbox = tmp_path / "video-inbox.json"
    write_inbox(inbox, [_sidecar_item()], VideoRunStats(videos=1, subtitles=1))
    payload = json.loads(inbox.read_text(encoding="utf-8"))
    payload["items"].append({"id": "broken", "title": "no url or source_type"})
    inbox.write_text(json.dumps(payload), encoding="utf-8")
    scraper = _sidecar_scraper(inbox)

    with caplog.at_level(logging.WARNING, logger="src.scrapers.video"):
        items = asyncio.run(scraper.fetch(datetime(2026, 7, 1, tzinfo=timezone.utc)))

    # One poisoned row must not cost the whole video section.
    assert len(items) == 1
    assert "failed validation" in caplog.text


def test_sidecar_warns_when_the_inbox_goes_stale(tmp_path, caplog) -> None:
    inbox = tmp_path / "video-inbox.json"
    write_inbox(inbox, [_sidecar_item()], VideoRunStats(videos=1, subtitles=1))
    payload = json.loads(inbox.read_text(encoding="utf-8"))
    payload["generated_at"] = (
        datetime.now(timezone.utc) - timedelta(hours=100)
    ).isoformat()
    inbox.write_text(json.dumps(payload), encoding="utf-8")
    scraper = _sidecar_scraper(inbox, inbox_max_age_hours=48)

    with caplog.at_level(logging.WARNING, logger="src.scrapers.video"):
        items = asyncio.run(scraper.fetch(datetime(2026, 7, 1, tzinfo=timezone.utc)))

    assert "stopped running" in caplog.text
    # Stale beats empty: seen.json already drops anything a run consumed.
    assert len(items) == 1


def test_sidecar_mode_never_touches_ytdlp(tmp_path, monkeypatch) -> None:
    inbox = tmp_path / "video-inbox.json"
    write_inbox(inbox, [_sidecar_item()], VideoRunStats(videos=1, subtitles=1))

    def explode(*args, **kwargs):
        raise AssertionError("sidecar mode must not scrape")

    monkeypatch.setattr(VideoScraper, "_download_subtitles", explode)
    monkeypatch.setattr(VideoScraper, "_fetch_channel", explode)
    config = VideoConfig(
        enabled=True,
        mode="sidecar",
        inbox_file=str(inbox),
        channels=[VideoChannelConfig(channel=_CHANNEL_ID)],
    )
    scraper = VideoScraper(config, None)

    assert len(asyncio.run(scraper.fetch(datetime(2026, 7, 1, tzinfo=timezone.utc)))) == 1


def test_sidecar_mode_skips_preflight(monkeypatch, tmp_path, caplog) -> None:
    # The digest host is allowed to have no node/ffmpeg/mlx at all.
    monkeypatch.setattr(video_module.shutil, "which", lambda name: None)
    monkeypatch.setattr(video_module, "_module_available", lambda name: False)
    inbox = tmp_path / "video-inbox.json"
    write_inbox(inbox, [_sidecar_item()], VideoRunStats(videos=1, subtitles=1))
    scraper = _sidecar_scraper(inbox, asr="local")

    with caplog.at_level(logging.WARNING, logger="src.scrapers.video"):
        asyncio.run(scraper.fetch(datetime(2026, 7, 1, tzinfo=timezone.utc)))

    assert "preflight" not in caplog.text


def test_release_asr_warns_when_the_cache_cannot_be_found(monkeypatch, caplog) -> None:
    for name in ("mlx_whisper", "mlx_whisper.transcribe", "mlx_whisper.load_models"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    scraper = VideoScraper(VideoConfig(), None)
    scraper._asr_loaded = True

    with caplog.at_level(logging.WARNING, logger="src.scrapers.video"):
        scraper._release_asr()  # must not raise off Apple Silicon

    # Silence here would mean 1.6 GB leaking with nothing in the log to explain it.
    assert "mlx-whisper" in caplog.text
    assert scraper._asr_loaded is False


def test_fetch_releases_asr_even_when_a_channel_explodes(monkeypatch) -> None:
    calls = _install_fake_mlx(monkeypatch)
    scraper = _make_scraper(monkeypatch, vtt_path=None, asr="local")
    scraper._asr_loaded = True

    async def boom(self, channel_ref):
        raise RuntimeError("channel exploded")

    monkeypatch.setattr(VideoScraper, "_resolve_channel_id", boom)

    asyncio.run(scraper.fetch(datetime(2026, 7, 1, tzinfo=timezone.utc)))

    assert calls["cache_clear"] == 1
