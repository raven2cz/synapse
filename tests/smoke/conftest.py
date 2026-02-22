"""
Shared fixtures and configuration for CDN/proxy smoke tests.

Markers:
  - @pytest.mark.live: hits Civitai CDN (skip if network unavailable)
  - @pytest.mark.proxy: needs proxy TestClient
  - @pytest.mark.smoke: auto-applied to all tests/smoke/

Fixtures:
  - async_client: httpx.AsyncClient, no auto-follow, browser UA
  - proxy_client: httpx.AsyncClient with ASGITransport → FastAPI app
  - network_available: checks CDN reachability, skips if offline
"""

import asyncio

import httpx
import pytest
import pytest_asyncio


# ============================================================================
# Async event loop (session-scoped)
# ============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create a session-scoped event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# Network check
# ============================================================================

@pytest.fixture(scope="session")
def network_available():
    """Check if Civitai CDN is reachable. Skip test if offline."""
    try:
        with httpx.Client(timeout=5) as client:
            resp = client.head("https://image.civitai.com", follow_redirects=True)
            return resp.status_code < 500
    except (httpx.HTTPError, httpx.TimeoutException):
        return False


def skip_if_offline(network_available):
    """Helper to skip live tests when offline."""
    if not network_available:
        pytest.skip("Network unavailable — skipping live CDN test")


# ============================================================================
# HTTP Clients
# ============================================================================

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://civitai.com/",
}


@pytest_asyncio.fixture
async def async_client():
    """Async HTTP client for CDN requests — no auto-follow redirects."""
    async with httpx.AsyncClient(
        follow_redirects=False,
        timeout=30.0,
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=5),
    ) as client:
        yield client


@pytest_asyncio.fixture
async def proxy_client():
    """Async HTTP client connected to FastAPI app via ASGITransport."""
    from apps.api.src.main import app, lifespan

    # Manually trigger lifespan to create http_client on app.state
    async with lifespan(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
            timeout=30.0,
        ) as client:
            yield client
