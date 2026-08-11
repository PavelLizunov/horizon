"""Built-in tools available to enrichment blocks."""

import asyncio
from dataclasses import dataclass
import hashlib
import logging
from typing import Any, Literal

from ddgs import DDGS
from ddgs.exceptions import RatelimitException, TimeoutException as DDGSTimeoutException

logger = logging.getLogger(__name__)

SearchErrorCode = Literal["unavailable", "rate_limited", "timeout", "invalid_response"]


@dataclass(frozen=True)
class SearchHit:
    discovery_id: str
    rank: int
    title: str
    url: str
    snippet: str

    def as_tool_result(self) -> dict[str, str]:
        """Keep the existing enrichment tool shape stable."""
        return {"title": self.title, "url": self.url, "text": self.snippet}


@dataclass(frozen=True)
class SearchOutcome:
    query: str
    status: Literal["ok", "error"]
    hits: tuple[SearchHit, ...] = ()
    error_code: SearchErrorCode | None = None


@dataclass(frozen=True)
class ToolResult:
    request_id: str
    block_id: str
    tool: str
    results: list[dict[str, str]]


class WebSearchTool:
    name = "web_search"
    _fallback_backends = ("duckduckgo", "yahoo", "yandex")

    async def search(self, query: str, *, max_results: int = 3) -> SearchOutcome:
        """Search without conflating a healthy empty result with an outage."""
        query = query.strip()
        if not query:
            raise ValueError("web_search requires a non-empty query")
        if max_results < 1:
            raise ValueError("max_results must be positive")

        search = DDGS().text
        errors: list[SearchErrorCode] = []
        saw_empty_response = False

        for backend in (None, *self._fallback_backends):
            kwargs: dict[str, Any] = {"max_results": max_results}
            if backend is not None:
                kwargs["backend"] = backend
            try:
                raw = await asyncio.to_thread(search, query, **kwargs)
            except Exception as exc:
                message = str(exc).lower()
                if "no results found" in message:
                    saw_empty_response = True
                    continue
                errors.append(self._error_code(exc))
                continue

            if not isinstance(raw, list) or any(
                not isinstance(result, dict) for result in raw
            ):
                return SearchOutcome(
                    query=query, status="error", error_code="invalid_response"
                )
            if not raw:
                return SearchOutcome(query=query, status="ok")

            hits = []
            for rank, result in enumerate(raw, start=1):
                url = result.get("href")
                if not isinstance(url, str) or not url.strip():
                    continue
                discovery_id = hashlib.sha256(
                    f"{query}\0{url.strip()}".encode("utf-8")
                ).hexdigest()
                hits.append(
                    SearchHit(
                        discovery_id=discovery_id,
                        rank=rank,
                        title=str(result.get("title", "")),
                        url=url.strip(),
                        snippet=str(result.get("body", "")),
                    )
                )
            return SearchOutcome(query=query, status="ok", hits=tuple(hits))

        if saw_empty_response:
            return SearchOutcome(query=query, status="ok")

        error_code = self._combined_error_code(errors)
        logger.warning(
            "web_search failed for %r on automatic and fallback backends: %s",
            query,
            ", ".join(errors) or "unavailable",
        )
        return SearchOutcome(query=query, status="error", error_code=error_code)

    @staticmethod
    def _error_code(exc: Exception) -> SearchErrorCode:
        message = str(exc).lower()
        if isinstance(
            exc, (DDGSTimeoutException, TimeoutError, asyncio.TimeoutError)
        ) or "timeout" in message:
            return "timeout"
        if (
            isinstance(exc, RatelimitException)
            or "429" in message
            or "rate limit" in message
        ):
            return "rate_limited"
        return "unavailable"

    @staticmethod
    def _combined_error_code(errors: list[SearchErrorCode]) -> SearchErrorCode:
        for code in ("timeout", "rate_limited", "unavailable"):
            if code in errors:
                return code
        return "unavailable"

    async def execute(self, arguments: dict[str, Any]) -> list[dict[str, str]]:
        query = arguments.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("web_search requires a non-empty query")
        outcome = await self.search(query)
        if outcome.status == "error":
            return []
        return [hit.as_tool_result() for hit in outcome.hits]


class ToolRegistry:
    """Small allowlisted registry for executable profile tools."""

    def __init__(self):
        self._tools = {WebSearchTool.name: WebSearchTool()}

    @property
    def names(self) -> set[str]:
        return set(self._tools)

    async def execute(
        self,
        request_id: str,
        block_id: str,
        tool: str,
        arguments: dict[str, Any],
    ) -> ToolResult:
        try:
            implementation = self._tools[tool]
        except KeyError as exc:
            raise ValueError(f"Unknown enrichment tool: {tool}") from exc
        return ToolResult(
            request_id=request_id,
            block_id=block_id,
            tool=tool,
            results=await implementation.execute(arguments),
        )
