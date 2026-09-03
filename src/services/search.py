"""Archive search indexing backed by Elasticsearch.

The pipeline indexes every delivered article once per run; a thin read-only
API (deploy/search/search_api.py) shapes queries for the site's search page,
which reaches Elasticsearch only through a Caddy-proxied path. Elasticsearch
itself never faces the browser.
"""

import json
import logging
from typing import Any, Dict, List, Optional

import httpx

from ..ai.summarizer import DailySummaryView
from ..models import SearchConfig

logger = logging.getLogger(__name__)

# Single node, no replicas: this is a personal archive, not a cluster.
# The russian analyzer stems both title and content, so "квантизация"
# matches "квантования" without query-time tricks.
INDEX_BODY: Dict[str, Any] = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {"analyzer": {"default": {"type": "russian"}}},
    },
    "mappings": {
        "properties": {
            "id": {"type": "keyword"},
            "title": {"type": "text"},
            "content": {"type": "text"},
            "url": {"type": "keyword"},
            "page": {"type": "keyword"},
            "date": {"type": "keyword"},
            "language": {"type": "keyword"},
            "profile": {"type": "keyword"},
            "score": {"type": "float"},
        }
    },
}


def build_search_documents(
    view: DailySummaryView, date: str, language: str, page_base: str
) -> List[Dict[str, Any]]:
    """One document per article in the rendered view.

    Consumes the same pure-data seam the Telegram headline builder uses, so
    what is searchable is exactly what was delivered. The document id is the
    issue-scoped page slug — the same derivation the site publisher and the
    headline links use — which makes reindexing idempotent. `page` is where
    the site serves the article; `url` stays the original source.
    """
    documents: List[Dict[str, Any]] = []
    for group in view.groups:
        for view_item in group.items:
            item = view_item.item
            artifact = item.processing.artifacts.get(language) if item.processing else None
            parts: List[str] = []
            if artifact:
                for block in artifact.blocks:
                    parts.append(block.content)
            elif item.processing and item.processing.analysis:
                parts.append(item.processing.analysis.summary)
            slug = view_item.anchor_id.removeprefix("item-")
            resolved_profile = (
                item.processing.classification.profile if item.processing else item.profile
            )
            documents.append(
                {
                    "id": f"{date}-{language}-{slug}",
                    "title": view_item.title,
                    "content": "\n".join(p for p in parts if p),
                    "url": str(item.url),
                    "page": f"{page_base}/{date}-{language}/{slug}/",
                    "date": date,
                    "language": language,
                    "profile": resolved_profile or item.profile or "unknown",
                    "score": float(view_item.score)
                    if isinstance(view_item.score, (int, float))
                    else None,
                }
            )
    return documents


def build_search_query(query: str, size: int = 30) -> Dict[str, Any]:
    """Build the library-side reference query pinned by offline tests.

    The deployed stdlib proxy owns an independent live query shape with title
    highlighting and sentinel tags; this helper is not called on that path.
    """
    return {
        "query": {
            "multi_match": {
                "query": query,
                "fields": ["title^3", "content"],
                "type": "best_fields",
            }
        },
        "highlight": {
            "fields": {"content": {"fragment_size": 220, "number_of_fragments": 2}}
        },
        "size": size,
        "sort": [{"_score": {"order": "desc"}}, {"date": {"order": "desc"}}],
    }


class SearchIndexer:
    """Minimal Elasticsearch writer over httpx; no client library needed."""

    def __init__(
        self, config: SearchConfig, client: Optional[httpx.AsyncClient] = None
    ) -> None:
        self.config = config
        self._client = client
        self._owns_client = client is None

    async def __aenter__(self) -> "SearchIndexer":
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self.config.url, timeout=30)
        return self

    async def __aexit__(self, *exc_info) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        assert self._client is not None, "SearchIndexer used outside its context"
        return self._client

    async def ensure_index(self) -> None:
        index = self.config.index
        if (await self.client.head(f"/{index}")).status_code == 404:
            response = await self.client.put(f"/{index}", json=INDEX_BODY)
            response.raise_for_status()
            logger.info("Created search index %s", index)

    async def index_documents(self, documents: List[Dict[str, Any]]) -> int:
        """Bulk-upsert documents; raise if Elasticsearch rejects any document."""
        if not documents:
            return 0
        lines: List[str] = []
        for doc in documents:
            lines.append(json.dumps({"index": {"_id": doc["id"]}}))
            lines.append(json.dumps(doc, ensure_ascii=False))
        response = await self.client.post(
            f"/{self.config.index}/_bulk",
            content="\n".join(lines) + "\n",
            headers={"Content-Type": "application/x-ndjson"},
        )
        response.raise_for_status()
        body = response.json()
        if body.get("errors"):
            failures = [
                item.get("index", {}).get("error", {}).get("reason", "unknown error")
                for item in body.get("items", [])
                if item.get("index", {}).get("error")
            ]
            raise RuntimeError(f"Search bulk indexing failed: {failures[:3]}")
        return len(documents)

    async def replace_issue_documents(
        self,
        documents: List[Dict[str, Any]],
        *,
        date: str,
        language: str,
    ) -> int:
        """Index the current issue and delete older documents no longer present."""
        if not date or not language:
            raise ValueError("date and language must be non-empty")
        if any(
            doc.get("date") != date or doc.get("language") != language
            for doc in documents
        ):
            raise ValueError("all documents must match the issue date and language")

        indexed = await self.index_documents(documents)
        bool_clause: Dict[str, Any] = {
            "filter": [
                {"term": {"date": date}},
                {"term": {"language": language}},
            ]
        }
        if documents:
            bool_clause["must_not"] = [
                {"terms": {"id": [doc["id"] for doc in documents]}}
            ]

        response = await self.client.post(
            f"/{self.config.index}/_delete_by_query",
            json={"query": {"bool": bool_clause}},
        )
        response.raise_for_status()
        failures = response.json().get("failures") or []
        if failures:
            raise RuntimeError(f"Search stale-document cleanup failed: {failures[:3]}")
        return indexed
