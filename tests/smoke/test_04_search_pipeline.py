"""
Group 4: Search Pipeline (~12 tests, 5-15s)

Validates the data transformation chain. Loads real captured data from
the tRPC fixture file and verifies that the Python port of URL construction
produces correct, optimized=true-free URLs.

Cross-language verification: Python builds the same URLs as TypeScript.
"""

import json
from pathlib import Path
from urllib.parse import unquote

import pytest

from tests.smoke.utils.cdn_prober import (
    CDN_BASE,
    build_image_url,
    build_video_url,
    build_thumbnail_url,
    to_proxy_url,
    detect_media_type,
    is_civitai_cdn_url,
)
from tests.smoke.utils.http_logger import fetch_with_trace, print_trace
from tests.smoke.conftest import skip_if_offline


# ============================================================================
# Load tRPC fixture data
# ============================================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURE_PATH = PROJECT_ROOT / "apps/web/src/__tests__/fixtures/trpc-real-models.json"


@pytest.fixture(scope="module")
def trpc_models():
    """Load the 12 real tRPC models from fixture file."""
    if not FIXTURE_PATH.exists():
        pytest.skip(f"Fixture file not found: {FIXTURE_PATH}")
    with open(FIXTURE_PATH) as f:
        return json.load(f)


def is_video_filename(filename: str | None) -> bool:
    """Check if filename indicates video — matches TS isVideoFilename()."""
    if not filename:
        return False
    import re
    return bool(re.search(r"\.(mp4|webm|mov|avi|mkv)$", filename, re.IGNORECASE))


def transform_preview_py(img: dict) -> dict:
    """
    Python port of transformPreview() from civitaiTransformers.ts.
    Returns dict with url, media_type, thumbnail_url.
    """
    raw_url = img.get("url", "")
    filename = img.get("name")
    img_type = img.get("type")

    # Determine if video (same logic as TS)
    is_video_by_type = img_type == "video"
    is_video_by_filename = is_video_filename(filename)
    is_video_by_url = raw_url.startswith("http") and detect_media_type(raw_url) == "video"
    is_video = is_video_by_type or is_video_by_filename or is_video_by_url

    # Build full URL from UUID if needed
    if raw_url and not raw_url.startswith("http"):
        # UUID → full CDN URL
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

    url = to_proxy_url(original_url)
    media_type = "video" if is_video else "image"
    thumbnail_url = None
    if media_type == "video":
        thumbnail_url = to_proxy_url(
            build_thumbnail_url(
                img.get("url", ""),
                filename or "video.mp4",
            )
        )

    return {
        "url": url,
        "media_type": media_type,
        "thumbnail_url": thumbnail_url,
        "original_url": original_url,
    }


# ============================================================================
# TestTrpcTransformPipeline
# ============================================================================


class TestTrpcTransformPipeline:
    """Validate tRPC → CivitaiModel transformation pipeline."""

    def test_fixture_has_models(self, trpc_models):
        """Fixture file should contain at least 10 models."""
        assert len(trpc_models) >= 10, f"Expected 10+ models, got {len(trpc_models)}"

    def test_all_models_produce_valid_urls(self, trpc_models):
        """All models should produce valid CDN URLs from their images."""
        for model in trpc_models:
            images = model.get("images", [])
            for img in images[:3]:  # First 3 images per model
                result = transform_preview_py(img)
                url = result["url"]
                assert url, f"Empty URL for model {model.get('id')}"
                # URL should be either proxied or a CDN URL
                assert (
                    "/api/browse/image-proxy" in url
                    or "civitai.com" in url
                ), f"Invalid URL: {url}"

    def test_video_preview_detected(self, trpc_models):
        """At least one model should have a video preview."""
        video_count = 0
        for model in trpc_models:
            images = model.get("images", [])
            for img in images:
                result = transform_preview_py(img)
                if result["media_type"] == "video":
                    video_count += 1

        assert video_count > 0, "No video previews found in fixtures"

    def test_video_has_thumbnail_with_anim_false(self, trpc_models):
        """Video previews should have thumbnails with anim=false."""
        for model in trpc_models:
            images = model.get("images", [])
            for img in images:
                result = transform_preview_py(img)
                if result["media_type"] == "video" and result["thumbnail_url"]:
                    # Decode the proxy URL to check the inner URL
                    thumb = result["thumbnail_url"]
                    if "/api/browse/image-proxy?url=" in thumb:
                        inner = unquote(thumb.split("url=")[1])
                    else:
                        inner = thumb
                    assert "anim=false" in inner, (
                        f"Video thumbnail missing anim=false: {inner}"
                    )

    def test_no_url_contains_optimized_true(self, trpc_models):
        """CRITICAL: No transformed URL should contain optimized=true."""
        for model in trpc_models:
            images = model.get("images", [])
            for img in images[:5]:
                result = transform_preview_py(img)
                for key in ("url", "thumbnail_url", "original_url"):
                    val = result.get(key)
                    if val:
                        assert "optimized=true" not in val, (
                            f"optimized=true found in {key}: {val}"
                        )

    def test_all_urls_use_proxy_wrapper(self, trpc_models):
        """All Civitai CDN URLs should be proxy-wrapped."""
        for model in trpc_models:
            images = model.get("images", [])
            for img in images[:3]:
                result = transform_preview_py(img)
                url = result["url"]
                if url:
                    assert "/api/browse/image-proxy" in url, (
                        f"URL not proxied: {url}"
                    )

    def test_proxy_inner_url_is_valid_cdn(self, trpc_models):
        """Inner URL in proxy wrapper should be a valid Civitai CDN URL."""
        for model in trpc_models:
            images = model.get("images", [])
            for img in images[:2]:
                result = transform_preview_py(img)
                url = result["url"]
                if "/api/browse/image-proxy?url=" in url:
                    inner = unquote(url.split("url=")[1])
                    assert is_civitai_cdn_url(inner), (
                        f"Inner URL is not Civitai CDN: {inner}"
                    )


# ============================================================================
# TestMeilisearchTransformPipeline
# ============================================================================


class TestMeilisearchTransformPipeline:
    """Validate Meilisearch → CivitaiModel transformation pipeline."""

    def test_meilisearch_hit_produces_valid_urls(self):
        """Meilisearch hit data should produce valid URLs."""
        # Simulated Meilisearch hit (same structure as real data)
        hit_image = {
            "url": "41ce091f-1006-491f-916d-873a9c80dfde",
            "name": "test.jpg",
            "type": "image",
            "nsfwLevel": 1,
            "width": 512,
            "height": 768,
        }
        result = transform_preview_py(hit_image)
        assert "/api/browse/image-proxy" in result["url"]
        assert result["media_type"] == "image"

    def test_meilisearch_no_optimized_true(self):
        """Meilisearch transformation should not add optimized=true."""
        hit_video = {
            "url": "1dbfbc3e-ffaf-49aa-83e1-38222a6d9a73",
            "name": "video.mp4",
            "type": "video",
            "nsfwLevel": 1,
        }
        result = transform_preview_py(hit_video)
        for key in ("url", "thumbnail_url", "original_url"):
            val = result.get(key)
            if val:
                assert "optimized=true" not in val

    def test_meilisearch_video_has_transcode(self):
        """Meilisearch video should produce URL with transcode=true."""
        hit_video = {
            "url": "1dbfbc3e-ffaf-49aa-83e1-38222a6d9a73",
            "name": "video.mp4",
            "type": "video",
        }
        result = transform_preview_py(hit_video)
        inner = unquote(result["url"].split("url=")[1]) if "url=" in result["url"] else result["url"]
        assert "transcode=true" in inner


# ============================================================================
# TestTransformedUrlsAccessible — needs network
# ============================================================================


class TestTransformedUrlsAccessible:
    """Verify that transformed URLs actually resolve to content."""

    @pytest.mark.asyncio
    @pytest.mark.live
    async def test_first_image_url_fetchable(self, async_client, network_available, trpc_models):
        """First image URL from fixture should be fetchable from CDN."""
        skip_if_offline(network_available)
        # Get first image from first model
        model = trpc_models[0]
        images = model.get("images", [])
        if not images:
            pytest.skip("No images in first model")

        result = transform_preview_py(images[0])
        original = result["original_url"]

        trace = await fetch_with_trace(async_client, original)
        print_trace(trace, "fixture_image")
        assert trace.final_status == 200, (
            f"Fixture image not accessible: {trace.final_status}"
        )

    @pytest.mark.asyncio
    @pytest.mark.live
    async def test_first_thumbnail_url_fetchable(self, async_client, network_available, trpc_models):
        """First video thumbnail from fixture should be fetchable."""
        skip_if_offline(network_available)
        # Find first video in fixtures
        for model in trpc_models:
            images = model.get("images", [])
            for img in images:
                result = transform_preview_py(img)
                if result["media_type"] == "video" and result["thumbnail_url"]:
                    # Extract inner URL from proxy wrapper
                    thumb = result["thumbnail_url"]
                    if "url=" in thumb:
                        inner = unquote(thumb.split("url=")[1])
                    else:
                        inner = thumb

                    trace = await fetch_with_trace(async_client, inner)
                    print_trace(trace, "fixture_thumbnail")
                    assert trace.final_status == 200, (
                        f"Video thumbnail not accessible: {trace.final_status}"
                    )
                    return

        pytest.skip("No video previews in fixtures")
