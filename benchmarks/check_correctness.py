"""Quality and correctness gate for benchmarked routines."""

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from rich.console import Console

from src.models import (
    Config,
    ContentItem,
    SourceType,
    ProcessingResult,
    ClassificationResult,
    ContentAnalysis,
)
from src.processing.profiles import ProfileRegistry
from src.orchestrator import HorizonOrchestrator, _deduplication_url_key
from src.processing.content import select_content, split_content
from src.url_security import validate_http_url
from src.verification.evidence import canonical_url, normalize_fetched_document, DocumentFetchOutcome
from src.console_icons import get_icons


def test_deduplication_correctness():
    config = Config.model_validate_json(Path("data/config.example.json").read_text())
    profiles = ProfileRegistry.load(Path("profiles"), "tech-news")
    orch = HorizonOrchestrator.__new__(HorizonOrchestrator)
    orch.config = config
    orch.profiles = profiles
    orch.console = Console(quiet=True)
    orch.icons = get_icons("ascii")

    fixed_time = datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
    item1 = ContentItem(
        id="item-1",
        source_type=SourceType.RSS,
        title="Title 1",
        url="https://example.com/post?utm_source=feed&id=1",
        published_at=fixed_time,
        content="Short content",
        metadata={"category": "tech", "key1": "val1"},
        profile="tech-news",
    )
    item2 = ContentItem(
        id="item-2",
        source_type=SourceType.GITHUB,
        title="Title 2",
        url="https://example.com/post?id=1",
        published_at=fixed_time,
        content="Much longer content here",
        metadata={"category": "tech", "key2": "val2"},
        profile="tech-news",
    )

    member_map = {}
    merged = orch.merge_cross_source_duplicates([item1, item2], member_map=member_map)
    assert len(merged) == 1, "Duplicate items must be merged"
    assert merged[0].id == "item-2", "Item with richest content must be primary"
    assert merged[0].metadata.get("key1") == "val1", "Metadata must be merged"
    assert merged[0].metadata.get("key2") == "val2", "Metadata must be merged"
    assert "Short content" in (merged[0].content or ""), "Other content must be preserved"
    assert member_map[merged[0].id] == ["item-1", "item-2"]

    # Verify original items are not mutated
    assert item1.content == "Short content"
    assert "key2" not in item1.metadata


def test_url_key_correctness():
    key1 = _deduplication_url_key("https://EXAMPLE.COM:443/test/path/?utm_medium=mail&a=1&utm_source=tw")
    key2 = _deduplication_url_key("https://example.com/test/path?a=1")
    assert key1 == key2, f"URL keys must match: {key1} vs {key2}"


def test_content_selection_correctness():
    raw = "Main text here\n--- Top Comments ---\nComment 1"
    parts = split_content(raw)
    assert parts.main == "Main text here"
    assert parts.comments == "Comment 1"

    text = "A" * 500
    res = select_content(text, 100, "head-middle-tail")
    assert len(res) <= 100
    assert "[Opening excerpt]" in res
    assert "[Middle excerpt]" in res
    assert "[Closing excerpt]" in res


def test_canonical_url_and_normalization():
    norm = canonical_url("https://EXAMPLE.COM:443/test/path?a=1#frag")
    assert norm == "https://example.com/test/path?a=1"
    assert "frag" not in norm

    html = b"<html><head><script>alert(1)</script></head><body><h1>Hello</h1><p>World</p></body></html>"
    outcome = DocumentFetchOutcome(
        status="ok",
        requested_url="https://example.com",
        final_url="https://example.com",
        http_status=200,
        mime_type="text/html",
        content=html,
    )
    doc = normalize_fetched_document(outcome)
    assert doc is not None
    assert "alert" not in doc
    assert "Hello" in doc
    assert "World" in doc


def main():
    test_deduplication_correctness()
    test_url_key_correctness()
    test_content_selection_correctness()
    test_canonical_url_and_normalization()
    print("Quality gate PASSED")


if __name__ == "__main__":
    main()
