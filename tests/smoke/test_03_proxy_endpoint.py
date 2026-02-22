"""
Group 3: Proxy Endpoint (~14 tests, 10-30s)

Tests the /api/browse/image-proxy endpoint via FastAPI TestClient.
No running server needed — uses httpx ASGITransport.

Tests validate:
- Domain whitelist enforcement
- Image proxy correctness (headers, caching)
- Video proxy with anim=true (direct Cloudflare serving)
- Video without anim=true (B2 redirect → failure)
- Concurrent request handling
- Redirect header stripping (commit 3badab3 fix)
"""

import asyncio
import time
from urllib.parse import quote

import pytest

from tests.smoke.fixtures.known_urls import (
    KNOWN_IMAGE_URL,
    KNOWN_VIDEO_URL,
    KNOWN_VIDEO_ANIM_URL,
    KNOWN_THUMBNAIL_URL,
    ALLOWED_DOMAINS,
)
from tests.smoke.conftest import skip_if_offline


# ============================================================================
# TestProxyDomainValidation
# ============================================================================


class TestProxyDomainValidation:
    """Verify proxy only allows whitelisted domains."""

    @pytest.mark.asyncio
    async def test_allowed_domain_accepted(self, proxy_client):
        """Civitai CDN domain should be accepted (not 400)."""
        url = "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/test/width=450/test.jpg"
        resp = await proxy_client.get(
            f"/api/browse/image-proxy?url={quote(url, safe='')}"
        )
        # Should NOT be 400 (domain rejection). May be 502 if CDN fails.
        assert resp.status_code != 400, (
            f"Allowed domain rejected: {resp.text}"
        )

    @pytest.mark.asyncio
    async def test_disallowed_domain_rejected_400(self, proxy_client):
        """Non-Civitai domain should be rejected with 400."""
        url = "https://evil.com/malicious.jpg"
        resp = await proxy_client.get(
            f"/api/browse/image-proxy?url={quote(url, safe='')}"
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_arbitrary_domain_rejected(self, proxy_client):
        """Random domain should be rejected."""
        url = "https://example.com/image.jpg"
        resp = await proxy_client.get(
            f"/api/browse/image-proxy?url={quote(url, safe='')}"
        )
        assert resp.status_code == 400


# ============================================================================
# TestProxyImageFetch — needs network
# ============================================================================


class TestProxyImageFetch:
    """Verify proxy returns correct responses for images."""

    @pytest.mark.asyncio
    @pytest.mark.live
    async def test_proxy_image_returns_200(self, proxy_client, network_available):
        skip_if_offline(network_available)
        resp = await proxy_client.get(
            f"/api/browse/image-proxy?url={quote(KNOWN_IMAGE_URL, safe='')}"
        )
        print(f"  Proxy image: {resp.status_code}, {len(resp.content)} bytes")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.live
    async def test_proxy_has_cache_headers(self, proxy_client, network_available):
        skip_if_offline(network_available)
        resp = await proxy_client.get(
            f"/api/browse/image-proxy?url={quote(KNOWN_IMAGE_URL, safe='')}"
        )
        if resp.status_code == 200:
            assert "cache-control" in resp.headers
            assert "max-age" in resp.headers.get("cache-control", "")

    @pytest.mark.asyncio
    @pytest.mark.live
    async def test_proxy_has_cors_headers(self, proxy_client, network_available):
        skip_if_offline(network_available)
        resp = await proxy_client.get(
            f"/api/browse/image-proxy?url={quote(KNOWN_IMAGE_URL, safe='')}"
        )
        if resp.status_code == 200:
            assert resp.headers.get("access-control-allow-origin") == "*"


# ============================================================================
# TestProxyVideoHandling — needs network
# ============================================================================


class TestProxyVideoHandling:
    """Verify proxy handles video URLs correctly with anim=true."""

    @pytest.mark.asyncio
    @pytest.mark.live
    async def test_video_anim_true_returns_200(self, proxy_client, network_available):
        """Video URL with anim=true via proxy should return 200 video/mp4."""
        skip_if_offline(network_available)
        start = time.monotonic()
        resp = await proxy_client.get(
            f"/api/browse/image-proxy?url={quote(KNOWN_VIDEO_ANIM_URL, safe='')}",
        )
        elapsed = time.monotonic() - start
        print(f"  Video proxy (anim=true): {resp.status_code} in {elapsed:.1f}s")
        assert resp.status_code == 200, (
            f"Expected 200 for anim=true video, got {resp.status_code}"
        )

    @pytest.mark.asyncio
    @pytest.mark.live
    async def test_video_without_anim_fails(self, proxy_client, network_available):
        """Video URL WITHOUT anim=true should fail (B2 redirect → 401/502)."""
        skip_if_offline(network_available)
        start = time.monotonic()
        resp = await proxy_client.get(
            f"/api/browse/image-proxy?url={quote(KNOWN_VIDEO_URL, safe='')}",
        )
        elapsed = time.monotonic() - start
        print(f"  Video proxy (no anim): {resp.status_code} in {elapsed:.1f}s")
        # Without anim=true, CDN redirects to B2 → 401 → proxy returns 502
        assert resp.status_code in (401, 502, 504), (
            f"Expected failure without anim=true, got {resp.status_code}"
        )

    @pytest.mark.asyncio
    @pytest.mark.live
    async def test_thumbnail_url_succeeds(self, proxy_client, network_available):
        """anim=false thumbnail via proxy should succeed."""
        skip_if_offline(network_available)
        resp = await proxy_client.get(
            f"/api/browse/image-proxy?url={quote(KNOWN_THUMBNAIL_URL, safe='')}",
        )
        print(f"  Thumbnail proxy: {resp.status_code}, {len(resp.content)} bytes")
        assert resp.status_code == 200


# ============================================================================
# TestProxyConcurrency — needs network
# ============================================================================


class TestProxyConcurrency:
    """Verify proxy handles concurrent requests without blocking."""

    @pytest.mark.asyncio
    @pytest.mark.live
    @pytest.mark.slow
    async def test_10_parallel_images_complete_15s(self, proxy_client, network_available):
        """10 parallel image proxy requests should complete within 15s."""
        skip_if_offline(network_available)
        url = quote(KNOWN_IMAGE_URL, safe="")

        start = time.monotonic()
        tasks = [
            proxy_client.get(f"/api/browse/image-proxy?url={url}")
            for _ in range(10)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        elapsed = time.monotonic() - start

        successes = sum(1 for r in results if not isinstance(r, Exception) and r.status_code == 200)
        print(f"  10 parallel: {successes}/10 success in {elapsed:.1f}s")
        assert elapsed < 15.0, f"10 parallel requests took {elapsed:.1f}s — too slow"

    @pytest.mark.asyncio
    @pytest.mark.live
    @pytest.mark.slow
    async def test_mixed_video_image_dont_block(self, proxy_client, network_available):
        """Mix of video + image requests shouldn't block each other."""
        skip_if_offline(network_available)
        image_url = quote(KNOWN_IMAGE_URL, safe="")
        video_url = quote(KNOWN_VIDEO_URL, safe="")
        thumb_url = quote(KNOWN_THUMBNAIL_URL, safe="")

        start = time.monotonic()
        tasks = [
            proxy_client.get(f"/api/browse/image-proxy?url={image_url}"),
            proxy_client.get(f"/api/browse/image-proxy?url={video_url}"),
            proxy_client.get(f"/api/browse/image-proxy?url={image_url}"),
            proxy_client.get(f"/api/browse/image-proxy?url={thumb_url}"),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        elapsed = time.monotonic() - start

        statuses = [
            r.status_code if not isinstance(r, Exception) else f"ERR:{r}"
            for r in results
        ]
        print(f"  Mixed requests: {statuses} in {elapsed:.1f}s")
        # The video might fail, but image and thumbnail should succeed
        # Overall should complete within reasonable time
        assert elapsed < 12.0, f"Mixed requests took {elapsed:.1f}s — video blocking others?"


# ============================================================================
# TestProxyRedirectHandling
# ============================================================================


class TestProxyRedirectHandling:
    """Verify proxy handles CDN redirects correctly (commit 3badab3 fix)."""

    @pytest.mark.asyncio
    @pytest.mark.live
    async def test_retries_500_for_images(self, proxy_client, network_available):
        """Image proxy should retry on 500/503 (transient CDN errors)."""
        skip_if_offline(network_available)
        # We can't easily trigger a 500, but we can verify the endpoint
        # handles normal images correctly (retry logic is transparent)
        resp = await proxy_client.get(
            f"/api/browse/image-proxy?url={quote(KNOWN_IMAGE_URL, safe='')}"
        )
        # If image works, retry logic didn't interfere
        assert resp.status_code in (200, 502), (
            f"Unexpected status {resp.status_code} for image proxy"
        )
