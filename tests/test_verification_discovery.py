from __future__ import annotations

import asyncio

import httpx
import pytest
from ddgs.exceptions import RatelimitException, TimeoutException as DDGSTimeoutException

from src.processing.tools import WebSearchTool
from src.url_security import URLResolutionError, UnsafeURLError
from src.verification.fetch import fetch_public_document


def _run(coro):
    return asyncio.run(coro)


class _DDGS:
    def __init__(self, result):
        self.result = result

    def text(self, query, *, max_results, backend=None):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class _DDGSByBackend:
    def __init__(self, results):
        self.results = results
        self.backends = []

    def text(self, query, *, max_results, backend=None):
        self.backends.append(backend)
        result = self.results[backend]
        if isinstance(result, Exception):
            raise result
        return result


def test_search_distinguishes_empty_success_from_backend_error(monkeypatch):
    monkeypatch.setattr("src.processing.tools.DDGS", lambda: _DDGS([]))
    empty = _run(WebSearchTool().search("  release notes  "))

    monkeypatch.setattr(
        "src.processing.tools.DDGS", lambda: _DDGS(RatelimitException("busy"))
    )
    failed = _run(WebSearchTool().search("release notes"))

    assert empty.status == "ok"
    assert empty.query == "release notes"
    assert empty.hits == ()
    assert empty.error_code is None
    assert failed.status == "error"
    assert failed.error_code == "rate_limited"


def test_search_reports_typed_timeout_and_invalid_response(monkeypatch):
    monkeypatch.setattr(
        "src.processing.tools.DDGS", lambda: _DDGS(DDGSTimeoutException("slow"))
    )
    timed_out = _run(WebSearchTool().search("release notes"))

    monkeypatch.setattr("src.processing.tools.DDGS", lambda: _DDGS(None))
    invalid = _run(WebSearchTool().search("release notes"))

    assert timed_out.error_code == "timeout"
    assert invalid.error_code == "invalid_response"


def test_search_falls_back_after_automatic_backend_failure(monkeypatch):
    result = [
        {
            "title": "Release",
            "href": "https://example.com/release",
            "body": "Version 2 is available.",
        }
    ]
    ddgs = _DDGSByBackend(
        {
            None: RatelimitException("429"),
            "duckduckgo": result,
        }
    )
    monkeypatch.setattr("src.processing.tools.DDGS", lambda: ddgs)

    outcome = _run(WebSearchTool().search("release notes"))

    assert outcome.status == "ok"
    assert outcome.hits[0].url == "https://example.com/release"
    assert ddgs.backends == [None, "duckduckgo"]


def test_search_treats_backend_no_results_as_healthy_empty(monkeypatch):
    ddgs = _DDGSByBackend(
        {
            None: RuntimeError("upstream HTTP error"),
            "duckduckgo": RuntimeError("No results found."),
            "yahoo": RuntimeError("No results found."),
            "yandex": RuntimeError("No results found."),
        }
    )
    monkeypatch.setattr("src.processing.tools.DDGS", lambda: ddgs)

    outcome = _run(WebSearchTool().search("missing release"))

    assert outcome.status == "ok"
    assert outcome.hits == ()
    assert outcome.error_code is None


def test_search_keeps_total_backend_outage_visible(monkeypatch):
    ddgs = _DDGSByBackend(
        {
            None: RuntimeError("upstream HTTP error"),
            "duckduckgo": RatelimitException("429"),
            "yahoo": DDGSTimeoutException("slow"),
            "yandex": RuntimeError("unavailable"),
        }
    )
    monkeypatch.setattr("src.processing.tools.DDGS", lambda: ddgs)

    outcome = _run(WebSearchTool().search("release notes"))

    assert outcome.status == "error"
    assert outcome.error_code == "timeout"


def test_search_keeps_existing_enrichment_result_shape(monkeypatch):
    raw = [
        {
            "title": "Release",
            "href": "https://example.com/release",
            "body": "Version 2 is available.",
        }
    ]
    monkeypatch.setattr("src.processing.tools.DDGS", lambda: _DDGS(raw))
    tool = WebSearchTool()

    outcome = _run(tool.search("version 2", max_results=6))
    legacy = _run(tool.execute({"query": "version 2"}))

    assert outcome.status == "ok"
    assert outcome.hits[0].rank == 1
    assert outcome.hits[0].discovery_id
    assert outcome.hits[0].discovery_id == _run(
        tool.search("version 2", max_results=6)
    ).hits[0].discovery_id
    assert legacy == [
        {
            "title": "Release",
            "url": "https://example.com/release",
            "text": "Version 2 is available.",
        }
    ]


async def _allow_public(url: str) -> tuple[str, ...]:
    return ("93.184.216.34",)


def test_document_fetch_follows_and_validates_each_redirect(monkeypatch):
    validated = []

    async def validate(url):
        validated.append(url)
        return await _allow_public(url)

    def handler(request: httpx.Request) -> httpx.Response:
        assert "authorization" not in request.headers
        assert "cookie" not in request.headers
        assert request.url.host == "93.184.216.34"
        assert request.headers["host"] == "example.com"
        assert request.extensions["sni_hostname"] == "example.com"
        if request.url.path == "/start":
            return httpx.Response(
                302,
                headers={
                    "location": "/article",
                    "set-cookie": "session=secret; Path=/",
                },
            )
        return httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            content=b"<p>Evidence</p>",
        )

    monkeypatch.setattr("src.verification.fetch.resolve_public_http_url", validate)
    result = _run(
        fetch_public_document(
            "https://example.com/start", transport=httpx.MockTransport(handler)
        )
    )

    assert result.status == "ok"
    assert result.final_url == "https://example.com/article"
    assert result.mime_type == "text/html"
    assert result.content == b"<p>Evidence</p>"
    assert validated == [
        "https://example.com/start",
        "https://example.com/article",
    ]


class _Chunks(httpx.AsyncByteStream):
    async def __aiter__(self):
        yield b"abc"
        yield b"def"


def test_document_fetch_enforces_streamed_size_limit(monkeypatch):
    monkeypatch.setattr(
        "src.verification.fetch.resolve_public_http_url", _allow_public
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/plain"},
            stream=_Chunks(),
        )

    result = _run(
        fetch_public_document(
            "https://example.com/large",
            max_bytes=5,
            transport=httpx.MockTransport(handler),
        )
    )

    assert result.status == "too_large"
    assert result.content == b""


def test_document_fetch_rejects_unsupported_mime(monkeypatch):
    monkeypatch.setattr(
        "src.verification.fetch.resolve_public_http_url", _allow_public
    )
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, headers={"content-type": "image/svg+xml"}, content=b"<svg/>"
        )
    )

    result = _run(
        fetch_public_document("https://example.com/image", transport=transport)
    )

    assert result.status == "unsupported_mime"
    assert result.mime_type == "image/svg+xml"


def test_document_fetch_accepts_headerless_utf8_text(monkeypatch):
    monkeypatch.setattr(
        "src.verification.fetch.resolve_public_http_url", _allow_public
    )
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, content="Release notes\nNew API".encode())
    )

    result = _run(
        fetch_public_document("https://example.com/NEWS", transport=transport)
    )

    assert result.status == "ok"
    assert result.mime_type == "text/plain"
    assert result.content == b"Release notes\nNew API"


def test_document_fetch_rejects_headerless_binary(monkeypatch):
    monkeypatch.setattr(
        "src.verification.fetch.resolve_public_http_url", _allow_public
    )
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, content=b"\x00\x01\x02binary")
    )

    result = _run(
        fetch_public_document("https://example.com/file", transport=transport)
    )

    assert result.status == "unsupported_mime"
    assert result.content == b""


def test_document_fetch_reports_security_and_network_failures(monkeypatch):
    async def reject(url):
        raise UnsafeURLError("private")

    monkeypatch.setattr("src.verification.fetch.resolve_public_http_url", reject)
    blocked = _run(fetch_public_document("https://example.com/private"))

    monkeypatch.setattr(
        "src.verification.fetch.resolve_public_http_url", _allow_public
    )

    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    timed_out = _run(
        fetch_public_document(
            "https://example.com/slow", transport=httpx.MockTransport(timeout)
        )
    )

    assert blocked.status == "security_blocked"
    assert timed_out.status == "timeout"


@pytest.mark.parametrize("status_code", [206, 300, 304])
def test_document_fetch_rejects_non_success_statuses(monkeypatch, status_code):
    monkeypatch.setattr(
        "src.verification.fetch.resolve_public_http_url", _allow_public
    )
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            status_code, headers={"content-type": "text/plain"}, content=b"not evidence"
        )
    )

    result = _run(fetch_public_document("https://example.com/status", transport=transport))

    assert result.status == "http_error"
    assert result.http_status == status_code
    assert result.content == b""


class _MustNotRead(httpx.AsyncByteStream):
    async def __aiter__(self):
        raise AssertionError("oversized response body was read")
        yield b""  # pragma: no cover


def test_document_fetch_rejects_content_length_before_reading(monkeypatch):
    monkeypatch.setattr(
        "src.verification.fetch.resolve_public_http_url", _allow_public
    )
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            headers={"content-type": "text/plain", "content-length": "99"},
            stream=_MustNotRead(),
        )
    )

    result = _run(
        fetch_public_document(
            "https://example.com/large", max_bytes=5, transport=transport
        )
    )

    assert result.status == "too_large"


def test_document_fetch_validates_private_redirect_before_request(monkeypatch):
    calls = []

    async def resolve(url):
        if url.startswith("http://127.0.0.1"):
            raise UnsafeURLError("private")
        return await _allow_public(url)

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(302, headers={"location": "http://127.0.0.1/admin"})

    monkeypatch.setattr("src.verification.fetch.resolve_public_http_url", resolve)
    result = _run(
        fetch_public_document(
            "https://example.com/start", transport=httpx.MockTransport(handler)
        )
    )

    assert result.status == "security_blocked"
    assert result.final_url == "http://127.0.0.1/admin"
    assert len(calls) == 1


def test_document_fetch_distinguishes_dns_failure_and_redirect_errors(monkeypatch):
    async def dns_failure(url):
        raise URLResolutionError("missing")

    monkeypatch.setattr("src.verification.fetch.resolve_public_http_url", dns_failure)
    missing = _run(fetch_public_document("https://missing.example/article"))

    monkeypatch.setattr(
        "src.verification.fetch.resolve_public_http_url", _allow_public
    )
    redirects = httpx.MockTransport(
        lambda request: httpx.Response(302, headers={"location": "/again"})
    )
    too_many = _run(
        fetch_public_document(
            "https://example.com/start", max_redirects=1, transport=redirects
        )
    )
    no_location = _run(
        fetch_public_document(
            "https://example.com/start",
            transport=httpx.MockTransport(lambda request: httpx.Response(302)),
        )
    )

    assert missing.status == "network_error"
    assert missing.final_url == "https://missing.example/article"
    assert too_many.status == "too_many_redirects"
    assert no_location.status == "http_error"


def test_document_fetch_wall_timeout_includes_resolution(monkeypatch):
    async def slow_resolution(url):
        await asyncio.sleep(0.05)
        return await _allow_public(url)

    monkeypatch.setattr(
        "src.verification.fetch.resolve_public_http_url", slow_resolution
    )

    result = _run(
        fetch_public_document(
            "https://example.com/article", timeout_seconds=0.001
        )
    )

    assert result.status == "timeout"
