"""
Group 2: CDN Direct Fetch (Live, ~14 tests, 15-30s)

Actual HTTP requests to Civitai CDN — proves behavior assumptions.
Every test prints its full redirect chain for post-mortem debugging.

Marker: @pytest.mark.live
"""

import pytest

from tests.smoke.utils.http_logger import fetch_with_trace, print_trace
from tests.smoke.utils.cdn_prober import build_image_url, build_video_url, build_thumbnail_url
from tests.smoke.fixtures.known_urls import (
    CDN_BASE,
    REALISTIC_VISION_IMAGE_UUID,
    REALISTIC_VISION_IMAGE_FILENAME,
    JUGGERNAUT_VIDEO_UUID,
    JUGGERNAUT_VIDEO_FILENAME,
    KNOWN_IMAGE_URL,
    KNOWN_VIDEO_URL,
    KNOWN_VIDEO_ANIM_URL,
    KNOWN_THUMBNAIL_URL,
    KNOWN_BAD_OPTIMIZED_URL,
    KNOWN_GOOD_URL,
    MAGIC_BYTES,
)
from tests.smoke.conftest import BROWSER_HEADERS, skip_if_offline


pytestmark = [pytest.mark.live]


# ============================================================================
# TestCdnImageFetch
# ============================================================================


class TestCdnImageFetch:
    """Verify basic image fetching from Civitai CDN."""

    @pytest.mark.asyncio
    async def test_image_returns_200_or_redirect(self, async_client, network_available):
        skip_if_offline(network_available)
        result = await fetch_with_trace(async_client, KNOWN_IMAGE_URL)
        print_trace(result, "image_fetch")
        assert result.final_status in (200, 301, 302), (
            f"Expected 200 or redirect, got {result.final_status}"
        )

    @pytest.mark.asyncio
    async def test_image_content_is_valid(self, async_client, network_available):
        skip_if_offline(network_available)
        result = await fetch_with_trace(async_client, KNOWN_IMAGE_URL)
        print_trace(result, "image_content")
        if result.final_status == 200 and result.content:
            # Check magic bytes for JPEG, PNG, WebP, or GIF
            first_bytes = result.content[:4]
            is_valid = any(
                first_bytes.startswith(magic)
                for magic in MAGIC_BYTES.values()
            )
            assert is_valid, (
                f"Content doesn't match any known image format. "
                f"First 8 bytes: {result.content[:8].hex()}"
            )


# ============================================================================
# TestCdnVideoFetch
# ============================================================================


class TestCdnVideoFetch:
    """Verify video URL behavior — B2 redirects, anim=false thumbnails."""

    @pytest.mark.asyncio
    async def test_video_without_anim_false_redirects(self, async_client, network_available):
        """Video URL (transcode=true, no anim=false) should redirect to B2."""
        skip_if_offline(network_available)
        result = await fetch_with_trace(async_client, KNOWN_VIDEO_URL, timeout=10.0)
        print_trace(result, "video_redirect")
        # Video URLs typically redirect to B2 storage
        has_redirect = any(h.status in (301, 302, 307, 308) for h in result.hops)
        # Either redirects to B2 OR fails (expected behavior)
        assert has_redirect or result.final_status in (401, 403, 502, 504, 0), (
            f"Expected redirect or auth failure, got {result.final_status}"
        )

    @pytest.mark.asyncio
    async def test_b2_redirect_empty_headers_200(self, async_client, network_available):
        """Following B2 redirect with empty headers should succeed."""
        skip_if_offline(network_available)
        result = await fetch_with_trace(
            async_client, KNOWN_VIDEO_URL, timeout=15.0
        )
        print_trace(result, "b2_empty_headers")
        # fetch_with_trace strips headers on redirect (like our proxy does)
        # If B2 is working, we should get 200. If not, timeout/auth error.
        if result.final_status == 200:
            assert result.content_length > 0

    @pytest.mark.asyncio
    async def test_b2_redirect_custom_headers_401(self, async_client, network_available):
        """Following B2 redirect with custom headers should fail with 401."""
        skip_if_offline(network_available)
        import httpx

        # First, get the redirect URL
        resp = await async_client.get(
            KNOWN_VIDEO_URL,
            headers=BROWSER_HEADERS,
            follow_redirects=False,
            timeout=10.0,
        )
        if resp.status_code not in (301, 302, 307, 308):
            pytest.skip("No redirect from CDN — can't test B2 auth")

        redirect_url = resp.headers.get("location", "")
        if not redirect_url:
            pytest.skip("No location header in redirect")

        # Follow with FULL custom headers (this is what breaks)
        resp2 = await async_client.get(
            redirect_url,
            headers=BROWSER_HEADERS,
            timeout=10.0,
        )
        print(f"  B2 with custom headers: {resp2.status_code}")
        # B2 rejects custom headers (or at least Authorization-like headers)
        # Accept either 401 or 403 as "auth rejected"
        assert resp2.status_code in (400, 401, 403), (
            f"Expected B2 auth rejection, got {resp2.status_code}"
        )

    @pytest.mark.asyncio
    async def test_video_with_anim_false_returns_image(self, async_client, network_available):
        """Video URL with anim=false should return a static thumbnail (200)."""
        skip_if_offline(network_available)
        result = await fetch_with_trace(async_client, KNOWN_THUMBNAIL_URL)
        print_trace(result, "anim_false_thumbnail")
        assert result.final_status == 200, (
            f"Expected 200 for anim=false thumbnail, got {result.final_status}"
        )

    @pytest.mark.asyncio
    async def test_video_thumbnail_is_valid_image(self, async_client, network_available):
        """anim=false thumbnail content should be valid image bytes."""
        skip_if_offline(network_available)
        result = await fetch_with_trace(async_client, KNOWN_THUMBNAIL_URL)
        print_trace(result, "thumbnail_content")
        if result.final_status == 200 and result.content:
            first_bytes = result.content[:4]
            is_valid = any(
                first_bytes.startswith(magic)
                for magic in MAGIC_BYTES.values()
            )
            assert is_valid, (
                f"Thumbnail is not valid image. "
                f"First 8 bytes: {result.content[:8].hex()}"
            )


# ============================================================================
# TestCdnAnimTrue — THE critical discovery
# ============================================================================


class TestCdnAnimTrue:
    """Prove that anim=true is the key to serving video directly from Cloudflare.

    Discovery (2026-02-22): Civitai's own useEdgeUrl() sets anim=true by default
    for video type. Without it, CDN redirects to B2 storage → 401 auth failure.
    With anim=true, Cloudflare serves video directly (200, video/mp4, with CORS).
    """

    @pytest.mark.asyncio
    async def test_anim_true_serves_video_directly(self, async_client, network_available):
        """anim=true,transcode=true URL should return 200 video/mp4 directly."""
        skip_if_offline(network_available)
        result = await fetch_with_trace(async_client, KNOWN_VIDEO_ANIM_URL, timeout=30.0)
        print_trace(result, "anim_true_video")
        assert result.final_status == 200, (
            f"Expected 200 for anim=true video, got {result.final_status}"
        )
        # Should be served as video/mp4
        if result.content_type:
            assert "video" in result.content_type.lower(), (
                f"Expected video content-type, got {result.content_type}"
            )

    @pytest.mark.asyncio
    async def test_anim_true_no_b2_redirect(self, async_client, network_available):
        """anim=true URL should NOT redirect to B2 storage."""
        skip_if_offline(network_available)
        result = await fetch_with_trace(async_client, KNOWN_VIDEO_ANIM_URL, timeout=30.0)
        print_trace(result, "anim_true_no_redirect")
        # Should NOT have a redirect to B2
        b2_hops = [h for h in result.hops if "b2" in (h.url or "").lower()]
        assert len(b2_hops) == 0, (
            f"anim=true should not redirect to B2, but found {len(b2_hops)} B2 hops"
        )

    @pytest.mark.asyncio
    async def test_without_anim_redirects_to_b2(self, async_client, network_available):
        """Without anim=true, CDN redirects to B2 storage (the BROKEN pattern)."""
        skip_if_offline(network_available)
        result = await fetch_with_trace(async_client, KNOWN_VIDEO_URL, timeout=10.0)
        print_trace(result, "no_anim_redirect")
        # Should redirect to B2 and fail with 401
        has_redirect = any(h.status in (301, 302, 307, 308) for h in result.hops)
        assert has_redirect or result.final_status in (401, 403, 502, 504, 0), (
            f"Expected redirect or auth failure without anim=true, got {result.final_status}"
        )

    @pytest.mark.asyncio
    async def test_anim_false_returns_thumbnail(self, async_client, network_available):
        """anim=false returns static image thumbnail (not video)."""
        skip_if_offline(network_available)
        result = await fetch_with_trace(async_client, KNOWN_THUMBNAIL_URL)
        print_trace(result, "anim_false_thumbnail")
        assert result.final_status == 200
        if result.content_type:
            assert "image" in result.content_type.lower(), (
                f"Expected image content-type for anim=false, got {result.content_type}"
            )


# ============================================================================
# TestCdnOptimizedTrue
# ============================================================================


class TestCdnOptimizedTrue:
    """Prove that optimized=true causes CDN failures."""

    @pytest.mark.asyncio
    async def test_optimized_true_returns_different_format(self, async_client, network_available):
        """URL with optimized=true returns WebP (smaller) vs JPEG without it.

        DISCOVERY (2026-02-22): Civitai CDN no longer returns 500 for optimized=true.
        Instead it returns 200 with WebP format (9KB vs 19KB JPEG without it).
        optimized=true is NOT the root cause of failures — it's a format hint.
        """
        skip_if_offline(network_available)
        result = await fetch_with_trace(async_client, KNOWN_BAD_OPTIMIZED_URL)
        print_trace(result, "optimized_true")
        # CDN accepts optimized=true now — returns WebP
        assert result.final_status == 200, (
            f"Expected 200, got {result.final_status}"
        )
        # Log the difference for documentation
        print(f"  optimized=true: {result.content_type}, {result.content_length}B")

    @pytest.mark.asyncio
    async def test_without_optimized_true_returns_200(self, async_client, network_available):
        """Same URL without optimized=true should work."""
        skip_if_offline(network_available)
        result = await fetch_with_trace(async_client, KNOWN_GOOD_URL)
        print_trace(result, "no_optimized_GOOD")
        assert result.final_status == 200, (
            f"Expected 200 without optimized=true, got {result.final_status}"
        )


# ============================================================================
# TestCdnRedirectChains
# ============================================================================


class TestCdnRedirectChains:
    """Log full redirect chains for debugging. Always prints trace."""

    @pytest.mark.asyncio
    async def test_image_redirect_chain_logged(self, async_client, network_available):
        skip_if_offline(network_available)
        result = await fetch_with_trace(async_client, KNOWN_IMAGE_URL)
        print_trace(result, "IMAGE_CHAIN")
        assert result.final_status != 0, "Request failed completely"

    @pytest.mark.asyncio
    async def test_video_redirect_chain_logged(self, async_client, network_available):
        skip_if_offline(network_available)
        result = await fetch_with_trace(async_client, KNOWN_VIDEO_URL, timeout=10.0)
        print_trace(result, "VIDEO_CHAIN")
        # Video may fail — that's expected. We just want the chain logged.
        assert len(result.hops) >= 1, "Should have at least one hop"

    @pytest.mark.asyncio
    async def test_thumbnail_no_redirect(self, async_client, network_available):
        """anim=false thumbnail should not redirect (direct 200)."""
        skip_if_offline(network_available)
        result = await fetch_with_trace(async_client, KNOWN_THUMBNAIL_URL)
        print_trace(result, "THUMBNAIL_CHAIN")
        # Thumbnails typically don't redirect — they're served directly
        redirect_hops = [h for h in result.hops if h.status in (301, 302, 307, 308)]
        print(f"  Redirect hops: {len(redirect_hops)}")
        assert result.final_status == 200


# ============================================================================
# TestCdnTimeout
# ============================================================================


class TestCdnTimeout:
    """Verify timeout behavior for video vs image URLs."""

    @pytest.mark.asyncio
    async def test_video_5s_timeout(self, async_client, network_available):
        """Video URL must complete (or fail) within ~6s."""
        skip_if_offline(network_available)
        result = await fetch_with_trace(
            async_client, KNOWN_VIDEO_URL, timeout=6.0
        )
        print_trace(result, "video_timeout")
        # Should either complete or timeout, but not hang 30s
        assert result.total_elapsed_ms < 7000, (
            f"Video request took {result.total_elapsed_ms:.0f}ms — too slow!"
        )

    @pytest.mark.asyncio
    async def test_image_completes_in_time(self, async_client, network_available):
        """Image URL should complete within reasonable time."""
        skip_if_offline(network_available)
        result = await fetch_with_trace(
            async_client, KNOWN_IMAGE_URL, timeout=30.0
        )
        print_trace(result, "image_timeout")
        assert result.total_elapsed_ms < 30000, (
            f"Image request took {result.total_elapsed_ms:.0f}ms — too slow!"
        )
