"""SSRF-safe HTTP URL validation and request execution."""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urljoin, urlsplit

import httpx


class UnsafeURLError(ValueError):
    """Raised when a URL may target a non-public network resource."""


class URLResolutionError(UnsafeURLError):
    """Raised when a syntactically safe hostname cannot be resolved."""


def validate_http_url(url: str) -> str:
    """Validate the non-network portions of an HTTP(S) URL."""
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise UnsafeURLError(f"Invalid URL: {exc}") from exc

    if parsed.scheme.lower() not in {"http", "https"}:
        raise UnsafeURLError("URL must use http or https")
    if not parsed.hostname:
        raise UnsafeURLError("URL has no hostname")
    if parsed.username is not None or parsed.password is not None:
        raise UnsafeURLError("URL must not contain embedded credentials")
    if port is not None and not 1 <= port <= 65535:
        raise UnsafeURLError("URL port is out of range")

    hostname = parsed.hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise UnsafeURLError("localhost destinations are not allowed")
    return url


async def _resolve_hostname(hostname: str, port: int) -> set[str]:
    try:
        literal = ipaddress.ip_address(hostname)
    except ValueError:
        try:
            results = await asyncio.to_thread(
                socket.getaddrinfo,
                hostname,
                port,
                type=socket.SOCK_STREAM,
            )
        except socket.gaierror as exc:
            raise URLResolutionError(f"Could not resolve hostname: {hostname}") from exc
        return {str(result[4][0]) for result in results}
    return {str(literal)}


async def resolve_public_http_url(url: str) -> tuple[str, ...]:
    """Resolve a URL and return only globally routable destination addresses."""
    validate_http_url(url)
    parsed = urlsplit(url)
    hostname = parsed.hostname or ""
    addresses = await _resolve_hostname(
        hostname.rstrip("."), parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    )
    if not addresses:
        raise UnsafeURLError(f"Hostname resolved to no addresses: {hostname}")

    for address in addresses:
        try:
            ip = ipaddress.ip_address(address.split("%", 1)[0])
        except ValueError as exc:
            raise UnsafeURLError(f"Resolver returned an invalid address: {address}") from exc
        if (
            not ip.is_global
            or ip.is_loopback
            or ip.is_private
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise UnsafeURLError(f"Destination resolves to a non-public address: {address}")
    return tuple(sorted(addresses))


async def validate_public_http_url(url: str) -> str:
    """Resolve a URL hostname and require every result to be globally routable."""
    await resolve_public_http_url(url)
    return url


_REDIRECT_STATUSES = {301, 302, 303, 307, 308}


def _same_origin(url: httpx.URL, other: httpx.URL) -> bool:
    url_port = url.port or (443 if url.scheme == "https" else 80)
    other_port = other.port or (443 if other.scheme == "https" else 80)
    return url.scheme == other.scheme and url.host == other.host and url_port == other_port


def _is_https_upgrade(url: httpx.URL, location: httpx.URL) -> bool:
    url_port = url.port or 80
    loc_port = location.port or 443
    return (
        url.host == location.host
        and url.scheme == "http"
        and url_port == 80
        and location.scheme == "https"
        and loc_port == 443
    )


async def safe_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    max_redirects: int = 10,
    **kwargs,
) -> httpx.Response:
    """Make a request after validating the initial URL and each redirect hop.

    Resolves destination addresses once and connects directly to a validated
    public IP address while preserving the original Host header and TLS SNI,
    closing DNS-rebinding TOCTOU windows.
    """
    current_method = method.upper()
    current_url = url
    current_kwargs = dict(kwargs)
    current_kwargs.pop("follow_redirects", None)
    strip_sensitive_headers = False

    for redirect_count in range(max_redirects + 1):
        addresses = await resolve_public_http_url(current_url)
        original_url = httpx.URL(current_url)

        req_headers = httpx.Headers(current_kwargs.get("headers"))
        req_headers["host"] = original_url.netloc.decode("ascii")

        req_extensions = dict(current_kwargs.get("extensions") or {})
        req_extensions["sni_hostname"] = original_url.raw_host.decode("ascii")

        send_keys = {"stream", "auth"}
        build_kwargs = {
            k: v
            for k, v in current_kwargs.items()
            if k not in send_keys and k not in {"headers", "extensions"}
        }
        send_kwargs = {k: v for k, v in current_kwargs.items() if k in send_keys}

        response: httpx.Response | None = None
        last_exc: Exception | None = None
        for address in addresses:
            target_url = original_url.copy_with(host=address)
            request = client.build_request(
                current_method,
                target_url,
                headers=req_headers,
                extensions=req_extensions,
                **build_kwargs,
            )
            if strip_sensitive_headers:
                for header in ("authorization", "cookie", "proxy-authorization"):
                    request.headers.pop(header, None)
                send_kwargs["auth"] = None
            try:
                response = await client.send(
                    request,
                    follow_redirects=False,
                    **send_kwargs,
                )
                break
            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                last_exc = exc
                continue

        if response is None:
            if last_exc is not None:
                raise last_exc
            raise URLResolutionError(f"Failed to connect to any resolved address for {current_url}")

        if response.status_code not in _REDIRECT_STATUSES:
            return response

        location = response.headers.get("location")
        if not location:
            return response

        if redirect_count == max_redirects:
            raise UnsafeURLError("Too many redirects")

        await response.aclose()

        previous_url = original_url
        next_url = httpx.URL(urljoin(current_url, location))

        next_method = current_method
        if response.status_code == 303 and current_method != "HEAD":
            next_method = "GET"
        elif response.status_code == 302 and current_method != "HEAD":
            next_method = "GET"
        elif response.status_code == 301 and current_method == "POST":
            next_method = "GET"

        if next_method != current_method and next_method == "GET":
            current_method = "GET"
            current_kwargs = {
                k: v
                for k, v in current_kwargs.items()
                if k not in {"content", "data", "files", "json"}
            }
            if "headers" in current_kwargs:
                h = httpx.Headers(current_kwargs["headers"])
                h.pop("content-length", None)
                h.pop("transfer-encoding", None)
                current_kwargs["headers"] = dict(h)

        if not _same_origin(previous_url, next_url) and not _is_https_upgrade(previous_url, next_url):
            strip_sensitive_headers = True
            current_kwargs.pop("auth", None)

        current_url = str(next_url)
        current_kwargs.pop("params", None)

    raise UnsafeURLError("Too many redirects")
