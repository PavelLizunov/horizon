from pathlib import Path
from datetime import datetime, timezone

from src.ai.prompting.classification import classification_user_prompt
from src.ai.prompting.enrichment import (
    artifact_prompt,
    block_prompt,
    item_context,
    tool_planning_prompt,
)
from src.models import (
    ClassificationResult,
    ContentAnalysis,
    ContentItem,
    ProcessingResult,
    SourceType,
)
from src.processing import ProfileRegistry
from src.processing.content import COMMENTS_MARKER


PROFILES = ProfileRegistry.load(
    Path(__file__).resolve().parents[1] / "profiles", "tech-news"
)


def test_tool_planning_excludes_profile_writing_policy():
    profile = PROFILES.get("tech-news")
    blocks = profile.definition.enrichment.blocks

    planning = tool_planning_prompt(blocks)
    artifact = artifact_prompt(profile, "en", blocks)
    block = block_prompt(profile, "en", blocks[0], include_header=True)

    assert profile.enrichment_prompt not in planning
    assert profile.enrichment_prompt in artifact
    assert profile.enrichment_prompt in block
    assert all(configured.id in planning for configured in blocks)
    assert "Block `background` is required" in planning


def test_enrichment_context_uses_profile_content_budget():
    profile = PROFILES.get("tech-blog")
    item = ContentItem(
        id="rss:test:blog",
        source_type=SourceType.RSS,
        title="Long article",
        url="https://example.com/blog",
        published_at=datetime.now(timezone.utc),
        profile="tech-blog",
        content="OPENING" + "A" * 25000 + "MIDDLE" + "B" * 25000 + "ENDING",
        processing=ProcessingResult(
            classification=ClassificationResult(
                profile="tech-blog", method="source_override"
            ),
            analysis=ContentAnalysis(
                score=8,
                reason="Deep article",
                summary="A long argument",
            ),
        ),
    )

    context = item_context(item, profile, include_content=True)

    assert "[Opening excerpt]" in context
    assert "[Middle excerpt]" in context
    assert "[Closing excerpt]" in context
    assert "OPENING" in context
    assert "MIDDLE" in context
    assert "ENDING" in context


def _make_discussion_item(content: str) -> ContentItem:
    return ContentItem(
        id="reddit:test:thread",
        source_type=SourceType.REDDIT,
        title="A discussion thread",
        url="https://example.com/thread",
        published_at=datetime.now(timezone.utc),
        profile="tech-news",
        content=content,
        processing=ProcessingResult(
            classification=ClassificationResult(
                profile="tech-news", method="source_override"
            ),
            analysis=ContentAnalysis(score=7, reason="Busy thread", summary="A thread"),
        ),
    )


def test_enrichment_comment_budget_is_profile_configurable(monkeypatch):
    profile = PROFILES.get("tech-news")
    item = _make_discussion_item("Post body." + COMMENTS_MARKER + "c" * 6000)

    context = item_context(item, profile, include_content=True)
    # Default preserves the previously hardcoded 2000-character cap.
    assert len(_comments_section(context)) == 2000

    monkeypatch.setattr(
        profile.definition.content, "enrichment_comments_max_chars", 5000
    )
    context = item_context(item, profile, include_content=True)
    assert len(_comments_section(context)) == 5000


def test_classification_prompt_uses_profile_routing_budget(monkeypatch):
    item = _make_discussion_item("x" * 6000)

    prompt = classification_user_prompt(item, PROFILES)
    # Default preserves the previously hardcoded 2000-character cap.
    assert len(_excerpt(prompt)) == 2000

    monkeypatch.setattr(
        PROFILES.get(PROFILES.default_profile).definition.content,
        "classification_max_chars",
        4500,
    )
    assert len(_excerpt(classification_user_prompt(item, PROFILES))) == 4500


def _comments_section(context: str) -> str:
    return context.split("# Community comments\n\n", 1)[1].split("\n", 1)[0]


def _excerpt(prompt: str) -> str:
    return prompt.split("Excerpt: ", 1)[1].split("\n", 1)[0]
