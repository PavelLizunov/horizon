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
            "date": {"type": "keyword"},
            "language": {"type": "keyword"},
            "profile": {"type": "keyword"},
            "score": {"type": "float"},
        }
    },
}


def build_search_documents(
    view: DailySummaryView, date: str, language: str
) -> List[Dict[str, Any]]:
    """One document per article in the rendered view.

    Consumes the same pure-data seam the Telegram headline builder uses, so
    what is searchable is exactly what was delivered. The document id is the
    issue-scoped page slug — the same derivation the site publisher and the
    headline links use — which makes reindexing idempotent.
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
            documents.append(
                {
                    "id": f"{date}-{language}-{view_item.anchor_id.removeprefix('item-')}",
                    "title": view_item.title,
                    "content": "\n".join(p for p in parts if p),
                    "url": str(item.url),
                    "date": date,
                    "language": language,
                    "profile": item.profile or "unknown",
                    "score": float(view_item.score)
                    if isinstance(view_item.score, (int, float))
                    else None,
                }
            )
    return documents


def build_search_query(query: str, size: int = 30) -> Dict[str, Any]:
    """The query body the search API sends; kept here so tests pin it."""
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
        """Bulk-upsert documents; returns how many were written."""
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
            failed = [
                item.get("index", {}).get("error", {}).get("reason", "?")
                for item in body.get("items", [])
                if item.get("index", {}).get("error")
            ]
            logger.warning("Search bulk had errors: %s", failed[:3])
        return len(documents)
