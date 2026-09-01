"""Read-only search API in front of Elasticsearch.

The browser never talks to Elasticsearch directly: Caddy proxies
/api/search on the digest domain here, and this service is the only
thing allowed to shape a query. It exposes exactly one endpoint;
everything else 404s, so the proxy path cannot be abused to reach
index administration.

Stdlib only; runs in a python:slim container next to Elasticsearch.
"""

import json
import logging
import math
import os
import re
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

ES_URL = os.environ.get("ES_URL", "http://es:9200")
ES_INDEX = os.environ.get("ES_INDEX", "horizon-articles")
PORT = int(os.environ.get("PORT", "8788"))
MAX_Q = 200
MAX_CONCURRENCY = int(os.environ.get("SEARCH_MAX_CONCURRENCY", "8"))
REQUEST_TIMEOUT = float(os.environ.get("SEARCH_REQUEST_TIMEOUT", "15"))

if MAX_CONCURRENCY < 1:
    raise ValueError("SEARCH_MAX_CONCURRENCY must be a positive integer")
if not math.isfinite(REQUEST_TIMEOUT) or REQUEST_TIMEOUT <= 0:
    raise ValueError("SEARCH_REQUEST_TIMEOUT must be a positive number")

logger = logging.getLogger(__name__)

# U+0001/U+0002 cannot occur in digest text and pass through HTML escaping
# unchanged, which is what makes them usable as highlight markers.
HL_OPEN = "\u0001"
HL_CLOSE = "\u0002"


def es_search(query: str) -> dict:
    body = json.dumps(
        {
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["title^3", "content"],
                    "type": "best_fields",
                }
            },
            # Highlight markers are two control characters, not `<em>`. The
            # browser has to escape this text before inserting it — it is model
            # output over scraped content — and escaping turned Elasticsearch's
            # default tags into visible "<em>" in every snippet. Sentinels
            # survive escaping untouched and the page swaps them for <mark>
            # afterwards, so the highlighting is the analyser's (which knows
            # Russian morphology) without ever injecting markup from the index.
            "highlight": {
                "pre_tags": [HL_OPEN],
                "post_tags": [HL_CLOSE],
                "fields": {
                    "title": {"number_of_fragments": 0},
                    "content": {"fragment_size": 220, "number_of_fragments": 2},
                },
            },
            "size": 30,
            "sort": [{"_score": {"order": "desc"}}, {"date": {"order": "desc"}}],
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{ES_URL}/{ES_INDEX}/_search",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8"))


def balance_highlights(text: str) -> str:
    """Repair highlight markers split across a fragment boundary.

    Elasticsearch cuts fragments to a character window, not to tag boundaries,
    so a fragment can open a highlight it never closes, or begin with a close
    that was opened in text that got trimmed away. Measured on the live index:
    4 of 30 snippets for "модель" came back unbalanced. Passed through as-is,
    an unclosed marker makes one `<mark>` swallow the rest of the snippet —
    a whole paragraph rendered as a match.

    Nested openers are dropped too, so the output is a flat, balanced sequence
    whatever the highlighter emits.
    """
    out = []
    inside = False
    for char in text:
        if char == HL_OPEN:
            if inside:
                continue
            inside = True
        elif char == HL_CLOSE:
            if not inside:
                continue
            inside = False
        out.append(char)
    if inside:
        out.append(HL_CLOSE)
    return "".join(out)


def shape(raw: dict) -> dict:
    hits = []
    for hit in raw.get("hits", {}).get("hits", []):
        source = hit.get("_source", {})
        highlight = hit.get("highlight", {})
        fragments = highlight.get("content", [])
        titles = highlight.get("title", [])
        hits.append(
            {
                "title": balance_highlights(
                    titles[0] if titles else source.get("title", "")
                ),
                "url": source.get("url", ""),
                "page": source.get("page", ""),
                "date": source.get("date", ""),
                "score": source.get("score"),
                "profile": source.get("profile", ""),
                # Per fragment, before joining. Balancing the joined string
                # instead lets a marker opened at the end of one fragment run
                # across the " … " seam and close inside the next, which put a
                # 160-character <mark> on the page.
                "snippet": " … ".join(balance_highlights(f) for f in fragments),
            }
        )
    return {"total": raw.get("hits", {}).get("total", {}).get("value", len(hits)), "hits": hits}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 — http.server naming
        parsed = urlsplit(self.path)
        if parsed.path not in ("/search", "/api/search"):
            self.send_error(404)
            return
        q = parse_qs(parsed.query).get("q", [""])[0].strip()
        q = re.sub(r"\s+", " ", q)[:MAX_Q]
        if len(q) < 2:
            self._json({"total": 0, "hits": []})
            return
        try:
            payload = shape(es_search(q))
        except Exception:
            logger.exception("Search backend request failed")
            self._json(
                {
                    "total": 0,
                    "hits": [],
                    "error": "Search backend unavailable",
                    "error_code": "backend_unavailable",
                },
                status=502,
            )
            return
        self._json(payload)

    def send_response_only(self, code, message=None):
        self._response_status = code
        super().send_response_only(code, message)

    def end_headers(self):
        status = getattr(self, "_response_status", 500)
        cache_control = (
            "public, max-age=300" if 200 <= status < 300 else "no-store"
        )
        self.send_header("Cache-Control", cache_control)
        super().end_headers()

    def _json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):  # keep container logs terse
        pass


class SearchHTTPServer(ThreadingHTTPServer):
    """Threaded HTTP server with bounded workers and client socket timeouts."""

    def __init__(
        self,
        server_address,
        handler_class=Handler,
        *,
        max_concurrency: int = MAX_CONCURRENCY,
        request_timeout: float = REQUEST_TIMEOUT,
    ):
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be positive")
        if not math.isfinite(request_timeout) or request_timeout <= 0:
            raise ValueError("request_timeout must be positive")
        self.request_timeout = request_timeout
        self._request_slots = threading.BoundedSemaphore(max_concurrency)
        super().__init__(server_address, handler_class)

    def get_request(self):
        request, client_address = super().get_request()
        request.settimeout(self.request_timeout)
        return request, client_address

    def process_request(self, request, client_address):
        self._request_slots.acquire()
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._request_slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._request_slots.release()


if __name__ == "__main__":
    with SearchHTTPServer(("0.0.0.0", PORT)) as server:
        server.serve_forever()
