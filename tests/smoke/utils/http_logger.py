"""
HTTP redirect chain tracer for smoke tests.

Every CDN request logs its full redirect chain for post-mortem debugging.
Even passing tests print their trace so we can audit CDN behavior changes.
"""

import time
from dataclasses import dataclass, field

import httpx


@dataclass
class RedirectHop:
    """Single hop in a redirect chain."""
    url: str
    status: int
    headers_sent: dict[str, str]
    headers_received: dict[str, str]
    elapsed_ms: float


@dataclass
class TraceResult:
    """Full result of a traced HTTP request."""
    url: str
    final_url: str
    final_status: int
    content_type: str
    content_length: int
    hops: list[RedirectHop] = field(default_factory=list)
    total_elapsed_ms: float = 0.0
    error: str | None = None
    content: bytes = b""


async def fetch_with_trace(
    client: httpx.AsyncClient,
    url: str,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
    max_redirects: int = 5,
) -> TraceResult:
    """
    Fetch URL with full redirect chain tracing.

    Does NOT auto-follow redirects. Manually follows them to record each hop.
    """
    if headers is None:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
            "Referer": "https://civitai.com/",
        }

    result = TraceResult(
        url=url,
        final_url=url,
        final_status=0,
        content_type="",
        content_length=0,
    )

    current_url = url
    current_headers = headers.copy()
    start = time.monotonic()

    try:
        for i in range(max_redirects + 1):
            hop_start = time.monotonic()
            resp = await client.get(
                current_url,
                headers=current_headers,
                follow_redirects=False,
                timeout=timeout,
            )
            hop_elapsed = (time.monotonic() - hop_start) * 1000

            resp_headers = dict(resp.headers)
            hop = RedirectHop(
                url=current_url,
                status=resp.status_code,
                headers_sent=current_headers.copy(),
                headers_received=resp_headers,
                elapsed_ms=hop_elapsed,
            )
            result.hops.append(hop)

            if resp.status_code in (301, 302, 307, 308):
                redirect_url = resp.headers.get("location", "")
                if not redirect_url:
                    break
                current_url = redirect_url
                # Strip custom headers for external storage (B2, DO Spaces)
                current_headers = {"User-Agent": headers.get("User-Agent", "")}
                continue

            # Final response
            result.final_url = current_url
            result.final_status = resp.status_code
            result.content_type = resp.headers.get("content-type", "")
            result.content = resp.content
            result.content_length = len(resp.content)
            break

    except httpx.TimeoutException:
        result.error = "timeout"
        result.final_status = 0
    except httpx.HTTPError as e:
        result.error = str(e)
        result.final_status = 0

    result.total_elapsed_ms = (time.monotonic() - start) * 1000
    return result


def print_trace(result: TraceResult, label: str = "") -> None:
    """Print formatted trace for test output."""
    prefix = f"[{label}] " if label else ""
    print(f"\n{'='*70}")
    print(f"{prefix}URL: {result.url}")
    print(f"{prefix}Final: {result.final_url}")
    print(f"{prefix}Status: {result.final_status}")
    print(f"{prefix}Content-Type: {result.content_type}")
    print(f"{prefix}Content-Length: {result.content_length}")
    print(f"{prefix}Total: {result.total_elapsed_ms:.0f}ms")

    if result.error:
        print(f"{prefix}ERROR: {result.error}")

    for i, hop in enumerate(result.hops):
        print(f"  Hop {i}: {hop.status} {hop.url[:100]} ({hop.elapsed_ms:.0f}ms)")
        if hop.status in (301, 302, 307, 308):
            loc = hop.headers_received.get("location", "?")
            print(f"         → {loc[:100]}")

    print(f"{'='*70}\n")
