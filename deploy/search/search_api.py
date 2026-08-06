"""Read-only search API in front of Elasticsearch.

The browser never talks to Elasticsearch directly: Caddy proxies
/api/search on the digest domain here, and this service is the only
thing allowed to shape a query. It exposes exactly one endpoint;
everything else 404s, so the proxy path cannot be abused to reach
index administration.

Stdlib only; runs in a python:slim container next to Elasticsearch.
"""

import json
import os
import re
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

ES_URL = os.environ.get("ES_URL", "http://es:9200")
ES_INDEX = os.environ.get("ES_INDEX", "horizon-articles")
PORT = int(os.environ.get("PORT", "8788"))
MAX_Q = 200


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
            "highlight": {
                "fields": {"content": {"fragment_size": 220, "number_of_fragments": 2}}
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
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def shape(raw: dict) -> dict:
    hits = []
    for hit in raw.get("hits", {}).get("hits", []):
        source = hit.get("_source", {})
        fragments = hit.get("highlight", {}).get("content", [])
        hits.append(
            {
                "title": source.get("title", ""),
                "url": source.get("url", ""),
                "date": source.get("date", ""),
                "score": source.get("score"),
                "profile": source.get("profile", ""),
                "snippet": " … ".join(fragments),
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
            self._json(shape(es_search(q)))
        except (urllib.error.URLError, OSError, ValueError) as error:
            self._json({"total": 0, "hits": [], "error": str(error)}, status=502)

    def _json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=300")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):  # keep container logs terse
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
