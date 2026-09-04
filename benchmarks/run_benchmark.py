"""Reproducible benchmark runner for Horizon core computational workloads.

Measures clean wall-clock execution time across core offline pipelines:
- URL parsing and deduplication (_deduplication_url_key, merge_cross_source_duplicates)
- Category/profile filtering and balanced digest selection
- Content excerpting and comment splitting (split_content, select_content)
- Public URL security validation (validate_http_url)
- Document normalization and evidence snapshot generation (normalize_fetched_document, canonical_url)
"""

import sys
import time
from pathlib import Path
from datetime import datetime, timezone
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
from src.orchestrator import HorizonOrchestrator
from src.processing.content import select_content, split_content
from src.url_security import validate_http_url
from src.verification.evidence import canonical_url, normalize_fetched_document, DocumentFetchOutcome
from src.console_icons import get_icons


def build_workload():
    config = Config.model_validate_json(Path("data/config.example.json").read_text())
    profiles = ProfileRegistry.load(Path("profiles"), "tech-news")

    orch = HorizonOrchestrator.__new__(HorizonOrchestrator)
    orch.config = config
    orch.profiles = profiles
    orch.console = Console(quiet=True)
    orch.icons = get_icons("ascii")

    # Generate deterministic synthetic items
    items = []
    fixed_time = datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
    for i in range(1200):
        item = ContentItem(
            id=f"item-{i}",
            source_type=SourceType.RSS,
            title=f"Test item {i} with some long text to simulate real news items in Horizon digest",
            url=f"https://example.com/news/article-{i % 250}?utm_source=rss&ref={i % 50}",
            published_at=fixed_time,
            content=f"Long article content {i} " * 25 + "--- Top Comments ---\nSome comment " * 8,
            metadata={"category": "tech"},
            profile="tech-news",
            processing=ProcessingResult(
                classification=ClassificationResult(profile="tech-news", method="source_override"),
                analysis=ContentAnalysis(score=float(i % 10), reason="test", summary=f"summary {i}"),
            ),
        )
        items.append(item)

    return orch, items


def run_workload(orch, items, iterations=3):
    start = time.perf_counter()
    now = datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
    for _ in range(iterations):
        # 1. URL deduplication
        merged = orch.merge_cross_source_duplicates(items)

        # 2. Profile filtering and balanced digest
        filtered = [it for it in items if orch.passes_profile_filter(it)]
        balanced = orch.apply_balanced_digest(filtered)

        # 3. Content splitting and sampling
        for it in items:
            parts = split_content(it.content)
            _ = select_content(parts.main, 1000, "head-middle-tail")

        # 4. URL security validation
        for i in range(400):
            validate_http_url(f"https://example{i % 50}.com/path/to/page?query={i}")

        # 5. Document fetch normalization and canonical URL
        for i in range(200):
            canonical_url(f"https://example.com/article/{i % 40}?utm_source=twitter&utm_medium=social#heading")
            raw_html = f"<html><head><title>Title {i}</title><script>alert(1)</script></head><body><h1>Heading</h1><p>Article body paragraph with info {i}.</p></body></html>".encode("utf-8")
            _ = normalize_fetched_document(
                DocumentFetchOutcome(
                    status="fetched",
                    requested_url=f"https://example.com/{i}",
                    final_url=f"https://example.com/{i}",
                    http_status=200,
                    mime_type="text/html",
                    content=raw_html,
                )
            )

    elapsed = time.perf_counter() - start
    return elapsed


def main():
    orch, items = build_workload()
    # Warm-up run
    _ = run_workload(orch, items, iterations=1)

    # Timed run
    elapsed = run_workload(orch, items, iterations=4)
    print(f"{elapsed:.4f}")


if __name__ == "__main__":
    main()
