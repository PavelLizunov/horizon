"""Bounded, SSRF-checked evidence document downloads."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urljoin

import httpx

from ..url_security import URLResolutionError, UnsafeURLError, resolve_public_http_url


FetchStatus = Literal[
    "ok",
    "access_denied",
    "not_found",
    "rate_limited",
    "http_error",
    "too_large",
    "unsupported_mime",
    "too_many_redirects",
    "timeout",
    "network_error",
    "security_blocked",
]

DEFAULT_MIME_TYPES = frozenset(
    {"text/html", "application/xhtml+xml", "text/plain", "application/json"}
)
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}


def _sniff_missing_text_mime(content: bytes) -> str | None:
    """Accept headerless text without treating arbitrary binary as evidence."""
    if not content or b"\0" in content:
        return None
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return None
    controls = sum(
        1 for character in text if not character.isprintable() and character not in "\r\n\t"
    )
    if controls / len(text) > 0.01:
        return None
    prefix = text.lstrip().lower()
    if prefix.startswith(("<!doctype html", "<html")):
        return "text/html"
    return "text/plain"


@dataclass(frozen=True)
class DocumentFetchOutcome:
    status: FetchStatus
    requested_url: str
    final_url: str | None = None
    http_status: int | None = None
    mime_type: str | None = None
    content: bytes = b""


def _http_failure(status: int) -> FetchStatus:
    if status in {401, 403}:
        return "access_denied"
    if status in {404, 410}:
        return "not_found"
    if status == 429:
        return "rate_limited"
    return "http_error"


async def fetch_public_document(
    url: str,
    *,
    max_bytes: int = 2 * 1024 * 1024,
    timeout_seconds: float = 30,
    max_redirects: int = 5,
    allowed_mime_types: frozenset[str] = DEFAULT_MIME_TYPES,
    transport: httpx.AsyncBaseTransport | None = None,
) -> DocumentFetchOutcome:
    """Download a public text document without inheriting auth or cookies."""
    if max_bytes < 1:
        raise ValueError("max_bytes must be positive")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    if max_redirects < 0:
        raise ValueError("max_redirects cannot be negative")
    if not allowed_mime_types:
        raise ValueError("allowed_mime_types cannot be empty")

    try:
        async with asyncio.timeout(timeout_seconds):
            return await _fetch_public_document(
                url,
                max_bytes=max_bytes,
                timeout_seconds=timeout_seconds,
                max_redirects=max_redirects,
                allowed_mime_types=allowed_mime_types,
                transport=transport,
            )
    except TimeoutError:
        return DocumentFetchOutcome(status="timeout", requested_url=url)


async def _fetch_public_document(
    url: str,
    *,
    max_bytes: int,
    timeout_seconds: float,
    max_redirects: int,
    allowed_mime_types: frozenset[str],
    transport: httpx.AsyncBaseTransport | None,
) -> DocumentFetchOutcome:
    current_url = url
    headers = {
        "User-Agent": "Horizon-Evidence/1.0",
        "Accept": ", ".join(sorted(allowed_mime_types)),
    }
    for redirect_count in range(max_redirects + 1):
        try:
            addresses = await resolve_public_http_url(current_url)
        except URLResolutionError:
            return DocumentFetchOutcome(
                status="network_error", requested_url=url, final_url=current_url
            )
        except UnsafeURLError:
            return DocumentFetchOutcome(
                status="security_blocked", requested_url=url, final_url=current_url
            )

        # A fresh client per hop prevents cookies and TLS connections from being
        # reused across redirect hosts. The request connects to a validated IP,
        # while Host and TLS SNI retain the original hostname.
        async with httpx.AsyncClient(
            follow_redirects=False,
            timeout=timeout_seconds,
            trust_env=False,
            transport=transport,
            headers=headers,
        ) as client:
            response = None
            connection_failure: FetchStatus = "network_error"
            for address in addresses:
                original_url = httpx.URL(current_url)
                request = client.build_request(
                    "GET",
                    original_url.copy_with(host=address),
                    headers={"Host": original_url.netloc.decode("ascii")},
                    extensions={
                        "sni_hostname": original_url.raw_host.decode("ascii")
                    },
                )
                try:
                    response = await client.send(request, stream=True)
                    break
                except httpx.ConnectTimeout:
                    connection_failure = "timeout"
                except httpx.ConnectError:
                    continue
                except httpx.TimeoutException:
                    return DocumentFetchOutcome(
                        status="timeout", requested_url=url, final_url=current_url
                    )
                except httpx.HTTPError:
                    return DocumentFetchOutcome(
                        status="network_error", requested_url=url, final_url=current_url
                    )

            if response is None:
                return DocumentFetchOutcome(
                    status=connection_failure,
                    requested_url=url,
                    final_url=current_url,
                )

            try:
                if response.status_code in _REDIRECT_STATUSES:
                    location = response.headers.get("location")
                    if not location:
                        return DocumentFetchOutcome(
                            status="http_error",
                            requested_url=url,
                            final_url=current_url,
                            http_status=response.status_code,
                        )
                    if redirect_count == max_redirects:
                        return DocumentFetchOutcome(
                            status="too_many_redirects",
                            requested_url=url,
                            final_url=current_url,
                            http_status=response.status_code,
                        )
                    current_url = urljoin(current_url, location)
                    continue

                if not 200 <= response.status_code < 300 or response.status_code == 206:
                    return DocumentFetchOutcome(
                        status=_http_failure(response.status_code),
                        requested_url=url,
                        final_url=current_url,
                        http_status=response.status_code,
                    )

                content_length = response.headers.get("content-length")
                if content_length:
                    try:
                        if int(content_length) > max_bytes:
                            return DocumentFetchOutcome(
                                status="too_large",
                                requested_url=url,
                                final_url=current_url,
                                http_status=response.status_code,
                            )
                    except ValueError:
                        pass

                mime_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
                if mime_type and mime_type not in allowed_mime_types:
                    return DocumentFetchOutcome(
                        status="unsupported_mime",
                        requested_url=url,
                        final_url=current_url,
                        http_status=response.status_code,
                        mime_type=mime_type or None,
                    )

                chunks = []
                size = 0
                try:
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > max_bytes:
                            return DocumentFetchOutcome(
                                status="too_large",
                                requested_url=url,
                                final_url=current_url,
                                http_status=response.status_code,
                                mime_type=mime_type,
                            )
                        chunks.append(chunk)
                except httpx.TimeoutException:
                    return DocumentFetchOutcome(status="timeout", requested_url=url)
                except httpx.HTTPError:
                    return DocumentFetchOutcome(status="network_error", requested_url=url)

                content = b"".join(chunks)
                if not mime_type:
                    mime_type = _sniff_missing_text_mime(content)
                    if mime_type is None or mime_type not in allowed_mime_types:
                        return DocumentFetchOutcome(
                            status="unsupported_mime",
                            requested_url=url,
                            final_url=current_url,
                            http_status=response.status_code,
                        )

                return DocumentFetchOutcome(
                    status="ok",
                    requested_url=url,
                    final_url=current_url,
                    http_status=response.status_code,
                    mime_type=mime_type,
                    content=content,
                )
            finally:
                await response.aclose()

    return DocumentFetchOutcome(status="too_many_redirects", requested_url=url)
