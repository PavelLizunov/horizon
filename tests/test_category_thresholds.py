"""Tests for category-specific thresholds in profile filtering."""

import pytest
from datetime import datetime, timezone
from rich.console import Console
from src.models import (
    ClassificationResult,
    Config,
    ContentAnalysis,
    ContentItem,
    ProcessingConfig,
    ProcessingResult,
    ProfileSettingsConfig,
    SourceType,
)
from src.orchestrator import HorizonOrchestrator


def _create_item(
    score: float,
    profile: str = "tech-news",
    category: str | None = None,
    tags: list[str] | None = None,
) -> ContentItem:
    item = ContentItem(
        id="test-item-1",
        title="Test Title",
        url="https://example.com/test",
        source_type=SourceType.REDDIT,
        published_at=datetime.now(timezone.utc),
        metadata={"category": category} if category else {},
    )
    item.processing = ProcessingResult(
        classification=ClassificationResult(profile=profile, method="source_override"),
        analysis=ContentAnalysis(
            score=score,
            reason="Test reason",
            summary="Test summary",
            tags=tags or [],
        ),
    )
    return item


def _create_orchestrator(category_thresholds: dict[str, float] | None = None) -> HorizonOrchestrator:
    orchestrator = HorizonOrchestrator.__new__(HorizonOrchestrator)
    orchestrator.config = Config.model_construct(
        processing=ProcessingConfig(
            profile_settings={
                "tech-news": ProfileSettingsConfig(
                    threshold=6.5,
                    category_thresholds=category_thresholds or {},
                )
            }
        )
    )
    orchestrator.console = Console(stderr=True)
    orchestrator.icons = {}
    return orchestrator


def test_category_threshold_overrides_profile_default():
    orchestrator = _create_orchestrator(category_thresholds={"llm": 4.5})

    # General tech-news item with score 5.0 -> fails threshold 6.5
    item_general = _create_item(score=5.0, profile="tech-news")
    assert not orchestrator.passes_profile_filter(item_general)

    # LLM category item with score 5.0 -> passes category threshold 4.5
    item_llm = _create_item(score=5.0, profile="tech-news", category="llm")
    assert orchestrator.passes_profile_filter(item_llm)

    # LLM category item with score 4.0 -> fails category threshold 4.5
    item_llm_low = _create_item(score=4.0, profile="tech-news", category="llm")
    assert not orchestrator.passes_profile_filter(item_llm_low)


def test_category_threshold_inferred_from_ai_tags():
    orchestrator = _create_orchestrator(category_thresholds={"llm": 4.5})

    # Item with no metadata category, but with #large-language-models tag
    item_tagged = _create_item(
        score=5.0,
        profile="tech-news",
        category=None,
        tags=["#large-language-models", "#quantization"],
    )
    assert orchestrator.passes_profile_filter(item_tagged)
    assert item_tagged.metadata.get("category") == "llm"


def test_explicit_threshold_override_takes_precedence():
    orchestrator = _create_orchestrator(category_thresholds={"llm": 4.5})

    # When caller explicitly passes threshold=7.0, it overrides both category and default
    item_llm = _create_item(score=5.0, profile="tech-news", category="llm")
    assert not orchestrator.passes_profile_filter(item_llm, threshold=7.0)


def test_ai_tools_and_sdd_category_inference():
    orchestrator = _create_orchestrator(category_thresholds={"sdd": 4.5, "ai-tools": 4.5})

    # Item with #spec-driven-development tag
    item_sdd = _create_item(
        score=5.0,
        profile="tech-news",
        category=None,
        tags=["#spec-driven-development", "#agentic-coding"],
    )
    assert orchestrator.passes_profile_filter(item_sdd)
    assert item_sdd.metadata.get("category") in ("sdd", "ai-tools")

