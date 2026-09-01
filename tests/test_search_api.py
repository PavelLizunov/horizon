"""Offline contract tests for the public archive search proxy."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import http.client
import json
import socket
import threading
from urllib.parse import quote_plus
from unittest.mock import MagicMock, patch

import pytest

from deploy.search import search_api


EMPTY_RESULT = {"hits": {"total": {"value": 0}, "hits": []}}


@contextmanager
def running_server(
    search,
    *,
    max_concurrency: int = 4,
    request_timeout: float = 1,
    server_class=search_api.SearchHTTPServer,
):
    with patch.object(search_api, "es_search", search):
        server = server_class(
            ("127.0.0.1", 0),
            search_api.Handler,
            max_concurrency=max_concurrency,
            request_timeout=request_timeout,
        )
        thread = threading.Thread(
            target=server.serve_forever,
            kwargs={"poll_interval": 0.01},
            daemon=True,
        )
        thread.start()
        try:
            yield server
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


def request(server, path: str, method: str = "GET"):
    host, port = server.server_address
    connection = http.client.HTTPConnection(host, port, timeout=2)
    try:
        connection.request(method, path)
        response = connection.getresponse()
        body = response.read()
        headers = {name.lower(): value for name, value in response.getheaders()}
        return response.status, headers, body
    finally:
        connection.close()


def test_success_contract_and_aliases_are_preserved():
    queries = []
    raw = {
        "hits": {
            "total": {"value": 1},
            "hits": [
                {
                    "_source": {
                        "title": "Fallback title",
                        "url": "https://example.com/source",
                        "page": "/digest/2026-09-01-ru/story/",
                        "date": "2026-09-01",
                        "score": 9.2,
                        "profile": "tech-news",
                    },
                    "highlight": {
                        "title": ["\u0001Matched\u0002 title"],
                        "content": ["first", "second"],
                    },
                }
            ],
        }
    }

    def search(query):
        queries.append(query)
        return raw

    with running_server(search) as server:
        for endpoint in ("/search", "/api/search"):
            status, headers, body = request(server, f"{endpoint}?q=test")
            payload = json.loads(body)
            assert status == 200
            assert headers["cache-control"] == "public, max-age=300"
            assert payload["total"] == 1
            assert payload["hits"][0] == {
                "title": "\u0001Matched\u0002 title",
                "url": "https://example.com/source",
                "page": "/digest/2026-09-01-ru/story/",
                "date": "2026-09-01",
                "score": 9.2,
                "profile": "tech-news",
                "snippet": "first … second",
            }

    assert queries == ["test", "test"]


def test_query_normalization_limit_and_short_query_behavior():
    queries = []

    def search(query):
        queries.append(query)
        return EMPTY_RESULT

    with running_server(search) as server:
        status, headers, body = request(server, "/api/search?q=x")
        assert status == 200
        assert headers["cache-control"] == "public, max-age=300"
        assert json.loads(body) == {"total": 0, "hits": []}

        normalized = quote_plus("  alpha   beta  ")
        assert request(server, f"/api/search?q={normalized}")[0] == 200
        assert request(server, f"/api/search?q={'z' * 205}")[0] == 200

    assert queries == ["alpha beta", "z" * search_api.MAX_Q]


def test_backend_errors_are_sanitized_and_never_cached():
    leaked = "http://es.internal:9200/_search?token=secret"

    def fail(_query):
        raise RuntimeError(leaked)

    with running_server(fail) as server:
        status, headers, body = request(server, "/api/search?q=test")

    payload = json.loads(body)
    assert status == 502
    assert headers["cache-control"] == "no-store"
    assert payload == {
        "total": 0,
        "hits": [],
        "error": "Search backend unavailable",
        "error_code": "backend_unavailable",
    }
    assert leaked.encode() not in body


def test_every_non_success_response_is_no_store():
    with running_server(lambda _query: EMPTY_RESULT) as server:
        missing = request(server, "/missing")
        unsupported = request(server, "/api/search", method="POST")

    assert missing[0] == 404
    assert missing[1]["cache-control"] == "no-store"
    assert unsupported[0] == 501
    assert unsupported[1]["cache-control"] == "no-store"


def test_elasticsearch_request_keeps_fixed_size_and_configured_timeout():
    response = MagicMock()
    response.__enter__.return_value.read.return_value = b'{"hits": {"hits": []}}'
    with patch.object(search_api.urllib.request, "urlopen", return_value=response) as urlopen:
        search_api.es_search("query")

    outbound = urlopen.call_args.args[0]
    body = json.loads(outbound.data)
    assert body["size"] == 30
    assert urlopen.call_args.kwargs["timeout"] == search_api.REQUEST_TIMEOUT


def test_server_rejects_invalid_resource_limits():
    with pytest.raises(ValueError, match="max_concurrency"):
        search_api.SearchHTTPServer(("127.0.0.1", 0), max_concurrency=0)
    with pytest.raises(ValueError, match="request_timeout"):
        search_api.SearchHTTPServer(("127.0.0.1", 0), request_timeout=float("nan"))


def test_active_searches_never_exceed_concurrency_limit():
    lock = threading.Lock()
    release = threading.Event()
    two_started = threading.Event()
    third_started = threading.Event()
    active = 0
    maximum = 0

    def search(_query):
        nonlocal active, maximum
        with lock:
            active += 1
            maximum = max(maximum, active)
            if active == 2:
                two_started.set()
            if active > 2:
                third_started.set()
        try:
            assert release.wait(timeout=2)
            return EMPTY_RESULT
        finally:
            with lock:
                active -= 1

    with running_server(search, max_concurrency=2, request_timeout=2) as server:
        host, port = server.server_address
        ready = threading.Barrier(5)

        def client():
            connection = http.client.HTTPConnection(host, port, timeout=3)
            connection.connect()
            ready.wait(timeout=2)
            try:
                connection.request("GET", "/api/search?q=test")
                response = connection.getresponse()
                response.read()
                return response.status
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(client) for _ in range(4)]
            ready.wait(timeout=2)
            try:
                assert two_started.wait(timeout=1)
                assert not third_started.wait(timeout=0.2)
            finally:
                release.set()
            assert [future.result(timeout=2) for future in futures] == [200] * 4

    assert maximum == 2


def test_slow_client_timeout_releases_the_only_worker():
    class ObservedServer(search_api.SearchHTTPServer):
        def __init__(self, *args, **kwargs):
            self.worker_started = threading.Event()
            super().__init__(*args, **kwargs)

        def process_request_thread(self, request_socket, client_address):
            self.worker_started.set()
            super().process_request_thread(request_socket, client_address)

    with running_server(
        lambda _query: EMPTY_RESULT,
        max_concurrency=1,
        request_timeout=0.1,
        server_class=ObservedServer,
    ) as server:
        slow = socket.create_connection(server.server_address, timeout=1)
        try:
            slow.sendall(b"GET /api/search HTTP/1.1\r\nHost: localhost")
            assert server.worker_started.wait(timeout=1)
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(request, server, "/api/search?q=test")
                assert future.result(timeout=2)[0] == 200
        finally:
            slow.close()
