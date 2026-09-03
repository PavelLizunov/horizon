from __future__ import annotations

import asyncio
import socket
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.url_security import (
    URLResolutionError,
    UnsafeURLError,
    safe_request,
    validate_public_http_url,
)


def _run(coro):
    return asyncio.run(coro)


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://10.0.0.1/",
        "http://169.254.169.254/",
        "http://0.0.0.0/",
        "http://224.0.0.1/",
        "http://192.0.2.1/",
        "http://[::1]/",
        "http://[fc00::1]/",
        "http://[fe80::1]/",
        "http://[::]/",
        "http://[ff02::1]/",
        "http://[2001:db8::1]/",
    ],
)
def test_rejects_non_public_ip_destinations(url):
    with pytest.raises(UnsafeURLError, match="non-public"):
        _run(validate_public_http_url(url))


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/",
        "https://service.localhost./hook",
        "ftp://example.com/file",
        "https://user:secret@example.com/hook",
    ],
)
def test_rejects_unsafe_url_forms(url):
    with pytest.raises(UnsafeURLError):
        _run(validate_public_http_url(url))


def test_rejects_hostname_when_any_resolved_ip_is_private():
    with patch(
        "src.url_security._resolve_hostname",
        new=AsyncMock(return_value={"93.184.216.34", "10.0.0.2"}),
    ):
        with pytest.raises(UnsafeURLError, match="10.0.0.2"):
            _run(validate_public_http_url("https://example.com/hook"))


def test_accepts_public_ipv4_and_ipv6_dns_answers():
    with patch(
        "src.url_security._resolve_hostname",
        new=AsyncMock(return_value={"93.184.216.34", "2606:2800:220:1:248:1893:25c8:1946"}),
    ):
        assert _run(validate_public_http_url("https://example.com/hook"))


def test_dns_failure_has_distinct_error_type():
    with patch("src.url_security.socket.getaddrinfo", side_effect=socket.gaierror):
        with pytest.raises(URLResolutionError, match="Could not resolve"):
            _run(validate_public_http_url("https://missing.example/hook"))


def test_public_relative_redirect_is_followed():
    paths = []

    async def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path == "/start":
            return httpx.Response(301, headers={"location": "/next"}, request=request)
        return httpx.Response(200, request=request)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with patch(
                "src.url_security._resolve_hostname",
                new=AsyncMock(return_value={"93.184.216.34"}),
            ):
                return await safe_request(client, "GET", "https://example.com/start")

    assert _run(run()).status_code == 200
    assert paths == ["/start", "/next"]


def test_safe_request_observed_mock_transport_proves_ip_destination_host_and_sni():
    observed_requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        observed_requests.append(request)
        return httpx.Response(200, text="success", request=request)

    async def run():
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            with patch(
                "src.url_security._resolve_hostname",
                new=AsyncMock(return_value={"93.184.216.34"}),
            ):
                return await safe_request(
                    client, "GET", "https://example.com:8443/test-endpoint?q=foo"
                )

    response = _run(run())
    assert response.status_code == 200
    assert len(observed_requests) == 1
    req = observed_requests[0]
    # Proves IP destination
    assert req.url == httpx.URL("https://93.184.216.34:8443/test-endpoint?q=foo")
    assert req.url.host == "93.184.216.34"
    assert req.url.port == 8443
    # Proves original Host header
    assert req.headers["host"] == "example.com:8443"
    # Proves original TLS SNI
    assert req.extensions.get("sni_hostname") == "example.com"


def test_safe_request_tries_multiple_public_addresses_on_connect_failure():
    observed_requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        observed_requests.append(request)
        if request.url.host == "93.184.216.34":
            raise httpx.ConnectError("Connection to first IP failed", request=request)
        return httpx.Response(200, text="success from second IP", request=request)

    async def run():
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            with patch(
                "src.url_security._resolve_hostname",
                new=AsyncMock(return_value={"93.184.216.34", "93.184.216.35"}),
            ):
                return await safe_request(client, "GET", "https://example.com/multi")

    response = _run(run())
    assert response.status_code == 200
    assert response.text == "success from second IP"
    assert len(observed_requests) == 2
    assert observed_requests[0].url.host == "93.184.216.34"
    assert observed_requests[1].url.host == "93.184.216.35"
    assert observed_requests[1].headers["host"] == "example.com"
    assert observed_requests[1].extensions.get("sni_hostname") == "example.com"


def test_safe_request_revalidates_redirect_and_blocks_private_ip():
    observed_requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        observed_requests.append(request)
        return httpx.Response(
            302, headers={"location": "http://127.0.0.1/admin"}, request=request
        )

    async def run():
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            with patch(
                "src.url_security._resolve_hostname",
                new=AsyncMock(side_effect=[{"93.184.216.34"}, {"127.0.0.1"}]),
            ):
                await safe_request(client, "GET", "https://example.com/start")

    with pytest.raises(UnsafeURLError, match="non-public"):
        _run(run())

    assert len(observed_requests) == 1
    assert observed_requests[0].url.host == "93.184.216.34"


@pytest.mark.parametrize(
    ("status_code", "initial_method", "expected_method", "expect_body"),
    [
        (301, "POST", "GET", False),
        (302, "POST", "GET", False),
        (303, "POST", "GET", False),
        (307, "POST", "POST", True),
        (308, "POST", "POST", True),
    ],
)
def test_safe_request_redirect_method_and_body_semantics(
    status_code, initial_method, expected_method, expect_body
):
    observed_requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        observed_requests.append(request)
        if len(observed_requests) == 1:
            return httpx.Response(
                status_code,
                headers={"location": "https://target.example.org/destination"},
                request=request,
            )
        return httpx.Response(200, text="ok", request=request)

    async def run():
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(
            transport=transport,
            headers={"Authorization": "Bearer secret"},
        ) as client:
            with patch(
                "src.url_security._resolve_hostname",
                new=AsyncMock(side_effect=[{"93.184.216.34"}, {"104.16.132.229"}]),
            ):
                return await safe_request(
                    client,
                    initial_method,
                    "https://example.com/source",
                    content=b"test-body-content",
                    headers={"Content-Type": "text/plain"},
                )

    resp = _run(run())
    assert resp.status_code == 200
    assert len(observed_requests) == 2

    # Initial request
    req1 = observed_requests[0]
    assert req1.method == initial_method
    assert req1.url.host == "93.184.216.34"
    assert req1.headers["host"] == "example.com"
    assert req1.extensions.get("sni_hostname") == "example.com"
    assert req1.content == b"test-body-content"
    assert req1.headers.get("authorization") == "Bearer secret"

    # Redirected request
    req2 = observed_requests[1]
    assert req2.method == expected_method
    assert req2.url.host == "104.16.132.229"
    assert req2.headers["host"] == "target.example.org"
    assert req2.extensions.get("sni_hostname") == "target.example.org"
    # Cross-origin redirect drops authorization
    assert "authorization" not in req2.headers
    if expect_body:
        assert req2.content == b"test-body-content"
    else:
        assert req2.content == b""
