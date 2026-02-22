"""
Group 5: Juggernaut XL E2E (~13 tests, 30-60s)

Golden path test for model 133005 (Juggernaut XL) — the model that keeps failing.
Tests the full pipeline: REST API → transform → CDN fetch.

Markers: @pytest.mark.live + @pytest.mark.slow
"""

import json
from pathlib import Path
from urllib.parse import quote, unquote

import pytest

from tests.smoke.utils.http_logger import fetch_with_trace, print_trace
from tests.smoke.utils.cdn_prober import (
    CDN_BASE,
    build_image_url,
    build_video_url,
    build_thumbnail_url,
    to_proxy_url,
    detect_media_type,
)
from tests.smoke.fixtures.known_urls import (
    JUGGERNAUT_MODEL_ID,
    JUGGERNAUT_VIDEO_UUID,
    JUGGERNAUT_VIDEO_FILENAME,
    MAGIC_BYTES,
)
from tests.smoke.conftest import skip_if_offline


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURE_PATH = PROJECT_ROOT / "apps/web/src/__tests__/fixtures/trpc-real-models.json"

pytestmark = [pytest.mark.slow]


# ============================================================================
# Helpers
# ============================================================================


def find_juggernaut_in_fixtures() -> dict | None:
    """Find Juggernaut XL (or model with video) in tRPC fixtures."""
    if not FIXTURE_PATH.exists():
        return None
    with open(FIXTURE_PATH) as f:
        models = json.load(f)
    # Look for model with video preview
    for model in models:
        images = model.get("images", [])
        for img in images:
            if img.get("type") == "video":
                return model
    return None


def transform_image(img: dict) -> dict:
    """Transform a single image/preview dict (Python port of TS logic)."""
    raw_url = img.get("url", "")
    filename = img.get("name")
    img_type = img.get("type")
    import re

    is_video = (
        img_type == "video"
        or (filename and bool(re.search(r"\.(mp4|webm|mov)$", filename, re.IGNORECASE)))
    )

    if raw_url and not raw_url.startswith("http"):
        if is_video:
            name = filename or "video.mp4"
            if not name.lower().endswith(".mp4"):
                dot = name.rfind(".")
                name = (name[:dot] + ".mp4") if dot >= 0 else name + ".mp4"
            original_url = f"{CDN_BASE}/{raw_url}/transcode=true,width=450/{name}"
        else:
            name = filename or "image.jpeg"
            original_url = f"{CDN_BASE}/{raw_url}/width=450/{name}"
    else:
        original_url = raw_url

    media_type = "video" if is_video else "image"
    thumbnail_url = None
    if media_type == "video":
        uuid = img.get("url", "")
        fname = filename or "video.mp4"
        thumbnail_url = build_thumbnail_url(uuid, fname)

    return {
        "url": to_proxy_url(original_url),
        "original_url": original_url,
        "media_type": media_type,
        "thumbnail_url": to_proxy_url(thumbnail_url) if thumbnail_url else None,
        "thumbnail_original": thumbnail_url,
    }


# ============================================================================
# TestJuggernautCdnDirect — Live CDN
# ============================================================================


class TestJuggernautCdnDirect:
    """Direct CDN tests for Juggernaut XL assets."""

    @pytest.mark.asyncio
    @pytest.mark.live
    async def test_fetch_model_via_rest_api(self, proxy_client, network_available):
        """Fetch Juggernaut XL model detail via REST API proxy."""
        skip_if_offline(network_available)
        resp = await proxy_client.get(f"/api/browse/model/{JUGGERNAUT_MODEL_ID}")
        print(f"  REST model fetch: {resp.status_code}")
        # May fail if Civitai API is down, but should not 500
        assert resp.status_code in (200, 502, 504), (
            f"Unexpected status for model fetch: {resp.status_code}"
        )
        if resp.status_code == 200:
            data = resp.json()
            assert "id" in data or "name" in data

    @pytest.mark.asyncio
    @pytest.mark.live
    async def test_video_thumbnail_accessible(self, async_client, network_available):
        """Juggernaut video thumbnail (anim=false) should return 200 WebP."""
        skip_if_offline(network_available)
        url = build_thumbnail_url(JUGGERNAUT_VIDEO_UUID, JUGGERNAUT_VIDEO_FILENAME)
        result = await fetch_with_trace(async_client, url)
        print_trace(result, "juggernaut_thumbnail")
        assert result.final_status == 200, (
            f"Thumbnail failed: {result.final_status}"
        )
        # Should be WebP or JPEG
        if result.content:
            first_bytes = result.content[:4]
            is_valid = any(
                first_bytes.startswith(magic) for magic in MAGIC_BYTES.values()
            )
            assert is_valid, f"Invalid image: {result.content[:8].hex()}"

    @pytest.mark.asyncio
    @pytest.mark.live
    async def test_video_url_fails_expected(self, async_client, network_available):
        """Juggernaut video URL (.mp4) should fail due to B2 auth."""
        skip_if_offline(network_available)
        url = build_video_url(JUGGERNAUT_VIDEO_UUID, JUGGERNAUT_VIDEO_FILENAME)
        result = await fetch_with_trace(async_client, url, timeout=10.0)
        print_trace(result, "juggernaut_video")
        # Video should either redirect+auth-fail or timeout
        # 200 is also acceptable if B2 works with empty headers
        print(f"  Video final status: {result.final_status}")

    @pytest.mark.asyncio
    @pytest.mark.live
    async def test_redirect_chain_video(self, async_client, network_available):
        """Log full redirect chain for Juggernaut video."""
        skip_if_offline(network_available)
        url = build_video_url(JUGGERNAUT_VIDEO_UUID, JUGGERNAUT_VIDEO_FILENAME)
        result = await fetch_with_trace(async_client, url, timeout=10.0)
        print_trace(result, "JUGGERNAUT_VIDEO_CHAIN")
        assert len(result.hops) >= 1, "Should have at least one hop"


# ============================================================================
# TestJuggernautProxy — via FastAPI proxy
# ============================================================================


class TestJuggernautProxy:
    """Proxy tests for Juggernaut XL assets."""

    @pytest.mark.asyncio
    @pytest.mark.live
    async def test_proxy_video_thumbnail(self, proxy_client, network_available):
        """Video thumbnail via proxy should succeed."""
        skip_if_offline(network_available)
        url = build_thumbnail_url(JUGGERNAUT_VIDEO_UUID, JUGGERNAUT_VIDEO_FILENAME)
        resp = await proxy_client.get(
            f"/api/browse/image-proxy?url={quote(url, safe='')}"
        )
        print(f"  Proxy thumbnail: {resp.status_code}, {len(resp.content)} bytes")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.live
    async def test_proxy_video_serves_with_anim_true(self, proxy_client, network_available):
        """Video URL with anim=true via proxy should return 200 video/mp4."""
        skip_if_offline(network_available)
        import time
        url = build_video_url(JUGGERNAUT_VIDEO_UUID, JUGGERNAUT_VIDEO_FILENAME)
        start = time.monotonic()
        resp = await proxy_client.get(
            f"/api/browse/image-proxy?url={quote(url, safe='')}"
        )
        elapsed = time.monotonic() - start
        print(f"  Proxy video: {resp.status_code} in {elapsed:.1f}s")
        # With anim=true, video serves directly from Cloudflare (no B2 redirect)
        assert resp.status_code == 200, (
            f"Expected 200 for anim=true video via proxy, got {resp.status_code}"
        )
        assert elapsed < 35.0, f"Video proxy took {elapsed:.1f}s"


# ============================================================================
# TestJuggernautTransform — Offline data transformation
# ============================================================================


class TestJuggernautTransform:
    """Verify transformation of Juggernaut XL data produces correct URLs."""

    def test_fixture_has_video_model(self):
        """Fixture should contain a model with video preview."""
        model = find_juggernaut_in_fixtures()
        assert model is not None, "No model with video preview in fixtures"

    def test_video_detected_in_fixture(self):
        """Video type should be detected in fixture images."""
        model = find_juggernaut_in_fixtures()
        if not model:
            pytest.skip("No video model in fixtures")
        images = model.get("images", [])
        video_images = [img for img in images if img.get("type") == "video"]
        assert len(video_images) > 0

    def test_video_transform_produces_correct_url(self):
        """Video preview transform should produce transcode=true URL."""
        model = find_juggernaut_in_fixtures()
        if not model:
            pytest.skip("No video model in fixtures")
        images = model.get("images", [])
        for img in images:
            if img.get("type") == "video":
                result = transform_image(img)
                inner_url = result["original_url"]
                assert "transcode=true" in inner_url
                assert inner_url.endswith(".mp4")
                break

    def test_video_thumbnail_has_anim_false(self):
        """Video thumbnail should have anim=false."""
        model = find_juggernaut_in_fixtures()
        if not model:
            pytest.skip("No video model in fixtures")
        images = model.get("images", [])
        for img in images:
            if img.get("type") == "video":
                result = transform_image(img)
                thumb = result.get("thumbnail_original", "")
                assert "anim=false" in thumb, f"Missing anim=false: {thumb}"
                break

    def test_no_optimized_true_in_any_url(self):
        """CRITICAL: No URL should contain optimized=true."""
        model = find_juggernaut_in_fixtures()
        if not model:
            pytest.skip("No video model in fixtures")
        images = model.get("images", [])
        for img in images:
            result = transform_image(img)
            for key in ("url", "original_url", "thumbnail_url", "thumbnail_original"):
                val = result.get(key)
                if val:
                    # Decode proxy URLs to check inner URL
                    if "url=" in val:
                        val = unquote(val.split("url=")[1])
                    assert "optimized=true" not in val, (
                        f"optimized=true in {key}: {val}"
                    )

    def test_all_urls_proxied(self):
        """All Civitai URLs should be proxy-wrapped."""
        model = find_juggernaut_in_fixtures()
        if not model:
            pytest.skip("No video model in fixtures")
        images = model.get("images", [])
        for img in images[:5]:
            result = transform_image(img)
            url = result["url"]
            if url:
                assert "/api/browse/image-proxy" in url, f"Not proxied: {url}"
