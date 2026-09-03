"""Offline tests for the Elasticsearch archive indexer."""

import asyncio
import json
from datetime import datetime, timezone

import httpx
import pytest

from src.ai.summarizer import DailySummarizer
from src.models import (
    ClassificationResult,
    ContentAnalysis,
    ContentArtifact,
    ContentBlock,
    ContentItem,
    ProcessingResult,
    SearchConfig,
    SourceType,
)
from src.services.search import (
    SearchIndexer,
    build_search_documents,
    build_search_query,
)


def _run(coro):
    return asyncio.run(coro)


def _item(idx: int) -> ContentItem:
    return ContentItem(
        id=f"rss:item-{idx}",
        source_type=SourceType.RSS,
        title=f"Important Item {idx}",
        url=f"https://example.com/items/{idx}",
        content="content",
        author="tester",
        published_at=datetime(2026, 8, 6, 8, 0, tzinfo=timezone.utc),
        profile="tech-news",
        processing=ProcessingResult(
            classification=ClassificationResult(
                profile="tech-news", method="source_override"
            ),
            analysis=ContentAnalysis(
                score=8.0, reason="test", summary=f"Summary {idx}.", tags=["AI"]
            ),
            artifacts={
                "ru": ContentArtifact(
                    language="ru",
                    title=f"Important Item {idx}",
                    blocks=[
                        ContentBlock(
                            id="lead", title="Суть", content=f"Текст статьи {idx}.", primary=True
                        ),
                        ContentBlock(id="ctx", title="Контекст", content="Контекст."),
                    ],
                )
            },
        ),
    )


def _view(items):
    return DailySummarizer().build_view(items, "ru")


def test_documents_carry_the_page_slug_as_id():
    # The id is the same slug the site publisher and the headline links use,
    # so reindexing a run overwrites exactly its own pages.
    documents = build_search_documents(
        _view([_item(1)]), "2026-08-06", "ru", "https://digest.ninitux.com/digest"
    )

    assert len(documents) == 1
    doc = documents[0]
    anchor = DailySummarizer._item_anchor("tech-news", 1)
    assert doc["id"] == f"2026-08-06-ru-{anchor.removeprefix('item-')}"
    assert doc["title"] == "Important Item 1"
    assert doc["url"] == "https://example.com/items/1"
    assert doc["score"] == 8.0
    assert doc["profile"] == "tech-news"
    assert "Текст статьи 1." in doc["content"]
    assert "Контекст." in doc["content"]


def test_documents_fall_back_to_the_analysis_summary_without_artifact():
    item = _item(1)
    item.processing.artifacts.clear()
    documents = build_search_documents(
        _view([item]), "2026-08-06", "ru", "https://digest.ninitux.com/digest"
    )

    assert documents[0]["content"] == "Summary 1."


def test_documents_link_the_site_page_not_just_the_source():
    # Reader complaint: a search hit must open our article page; the source
    # stays as the secondary "original" link.
    documents = build_search_documents(
        _view([_item(1)]), "2026-08-06", "ru", "https://digest.ninitux.com/digest"
    )

    doc = documents[0]
    slug = DailySummarizer._item_anchor("tech-news", 1).removeprefix("item-")
    assert doc["page"] == f"https://digest.ninitux.com/digest/2026-08-06-ru/{slug}/"
    assert doc["url"] == "https://example.com/items/1"


def test_search_query_boosts_titles_and_highlights_content():
    query = build_search_query("квантизация")

    match = query["query"]["multi_match"]
    assert match["query"] == "квантизация"
    assert "title^3" in match["fields"]
    assert query["highlight"]["fields"]["content"]["fragment_size"] == 220


def _mock_transport(handler):
    requests = []

    def transport(request):
        requests.append(request)
        return handler(request)

    return httpx.MockTransport(transport), requests


def _replace_issue(transport, documents):
    async def run():
        async with httpx.AsyncClient(
            transport=transport, base_url="http://es.test"
        ) as client:
            return await SearchIndexer(
                SearchConfig(enabled=True, url="http://es.test"), client
            ).replace_issue_documents(
                documents, date="2026-08-06", language="ru"
            )

    return _run(run())


def test_ensure_index_creates_only_when_missing():
    state = {"heads": 0}

    def handler(request):
        if request.method == "HEAD":
            state["heads"] += 1
            return httpx.Response(404 if state["heads"] == 1 else 200)
        assert request.method == "PUT"
        body = json.loads(request.content)
        assert body["settings"]["analysis"]["analyzer"]["default"]["type"] == "russian"
        return httpx.Response(200, json={"acknowledged": True})

    transport, requests = _mock_transport(handler)
    config = SearchConfig(enabled=True, url="http://es.test")

    async def run():
        async with SearchIndexer(
            config,
            client=httpx.AsyncClient(transport=transport, base_url="http://es.test"),
        ) as indexer:
            await indexer.ensure_index()
            await indexer.ensure_index()

    _run(run())
    methods = [r.method for r in requests]
    # One PUT for the missing index; the second ensure sees it exists.
    assert methods.count("PUT") == 1
    assert state["heads"] == 2


def test_bulk_index_sends_ndjson_with_per_doc_ids():
    def handler(request):
        if request.method == "POST":
            assert request.url.path == "/horizon-articles/_bulk"
            lines = request.content.decode("utf-8").strip().split("\n")
            assert len(lines) == 2
            action = json.loads(lines[0])
            assert action["index"]["_id"]
            assert "application/x-ndjson" in request.headers["content-type"]
            return httpx.Response(200, json={"errors": False, "items": []})
        return httpx.Response(200)

    transport, _ = _mock_transport(handler)
    config = SearchConfig(enabled=True, url="http://es.test")
    documents = build_search_documents(
        _view([_item(1)]), "2026-08-06", "ru", "https://digest.ninitux.com/digest"
    )

    async def run():
        async with SearchIndexer(config, client=httpx.AsyncClient(transport=transport, base_url="http://es.test")) as indexer:
            return await indexer.index_documents(documents)

    assert _run(run()) == 1


def test_issue_replacement_aborts_cleanup_on_partial_bulk_failure():
    response = {
        "errors": True,
        "items": [{"index": {"error": {"reason": "mapper parsing"}}}],
    }
    transport, requests = _mock_transport(
        lambda request: httpx.Response(200, json=response)
    )
    documents = build_search_documents(
        _view([_item(1)]), "2026-08-06", "ru", "https://example.test"
    )

    with pytest.raises(RuntimeError, match="mapper parsing"):
        _replace_issue(transport, documents)

    assert [request.url.path for request in requests] == [
        "/horizon-articles/_bulk"
    ]


def test_config_example_stays_valid_with_search_section():
    # SearchConfig defaults must keep data/config.example.json loadable.
    config = SearchConfig()
    assert config.enabled is False
    assert config.index == "horizon-articles"


_OLD_FORMAT = (
    "# Digest Ninitux - 2026-08-06\n\n---\n\n"
    '<a id="item-tech-news-1"></a>\n'
    "### [Заголовок один](https://example.com/one) ⭐️ 9.0/10\n\n"
    "Лид-абзац про квантизацию.\n\n"
    "rss · tester · Aug 5, 16:05\n\n"
    "**「Контекст」** Текст контекста.\n\n"
    "<details><summary>References</summary>\n<ul>\n<li><a href=\"https://x.y\">X</a></li>\n</ul>\n</details>\n\n"
    "**Tags**: `#ai`\n\n"
    '<a id="item-tech-blog-2"></a>\n'
    "### [Заголовок два](https://example.com/two) ⭐️ 6.0/10\n\n"
    "Лид-абзац два.\n"
)


def test_archive_parser_splits_the_old_combined_format():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.dev_reindex_archive import parse_summary

    documents = parse_summary(_OLD_FORMAT, "2026-08-06", "ru")

    assert [d["id"] for d in documents] == [
        "2026-08-06-ru-tech-news-1",
        "2026-08-06-ru-tech-blog-2",
    ]
    first = documents[0]
    assert first["title"] == "Заголовок один"
    assert first["url"] == "https://example.com/one"
    assert first["score"] == 9.0
    assert first["profile"] == "tech-news"
    # References markup and tags must not leak into the searchable text.
    assert "References" not in first["content"]
    assert "#ai" not in first["content"]
    assert "квантизацию" in first["content"]
    assert "Контекст: Текст контекста." in first["content"]
    # Rendered-page chrome is noise in snippets: no heading line, no byline.
    assert "###" not in first["content"]
    assert "rss ·" not in first["content"]
    # The hit opens our article page; the source is secondary.
    assert first["page"] == "https://digest.ninitux.com/digest/2026-08-06-ru/tech-news-1/"


def test_documents_use_resolved_classification_profile():
    item = _item(1)
    # Requested profile is general, but resolved classification profile is resolved-tech
    item.profile = "general"
    item.processing.classification = ClassificationResult(
        profile="resolved-tech", method="source_override"
    )
    docs = build_search_documents(
        _view([item]), "2026-08-06", "ru", "https://digest.ninitux.com/digest"
    )
    assert docs[0]["profile"] == "resolved-tech"


def test_issue_replacement_rejects_documents_from_another_issue():
    async def run():
        async with httpx.AsyncClient() as client:
            indexer = SearchIndexer(SearchConfig(), client=client)
            await indexer.replace_issue_documents(
                [{"id": "other", "date": "2026-08-05", "language": "ru"}],
                date="2026-08-06",
                language="ru",
            )

    with pytest.raises(ValueError, match="must match"):
        _run(run())


def test_replace_issue_documents_deletes_only_stale_documents():
    def handler(request):
        if request.url.path.endswith("_bulk"):
            return httpx.Response(200, json={"errors": False})
        return httpx.Response(200, json={"failures": []})

    transport, requests = _mock_transport(handler)
    documents = build_search_documents(
        _view([_item(1), _item(2)]), "2026-08-06", "ru", "https://example.test"
    )

    assert _replace_issue(transport, documents) == 2
    assert [request.url.path for request in requests] == [
        "/horizon-articles/_bulk",
        "/horizon-articles/_delete_by_query",
    ]
    query = json.loads(requests[1].content)["query"]["bool"]
    assert query["filter"] == [
        {"term": {"date": "2026-08-06"}},
        {"term": {"language": "ru"}},
    ]
    assert query["must_not"] == [
        {"terms": {"id": [document["id"] for document in documents]}}
    ]


def test_replace_issue_documents_prunes_whole_issue_for_empty_current_set():
    transport, requests = _mock_transport(
        lambda request: httpx.Response(200, json={"failures": []})
    )

    assert _replace_issue(transport, []) == 0
    assert [request.url.path for request in requests] == [
        "/horizon-articles/_delete_by_query"
    ]
    query = json.loads(requests[0].content)["query"]["bool"]
    assert query["filter"] == [
        {"term": {"date": "2026-08-06"}},
        {"term": {"language": "ru"}},
    ]
    assert "must_not" not in query

