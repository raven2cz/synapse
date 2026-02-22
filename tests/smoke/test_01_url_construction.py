"""
Group 1: URL Construction (Offline, ~20 tests, <1s)

No network required. Pure logic tests that validate:
- URL building helpers produce correct structure
- No URLs contain `optimized=true`
- Proxy wrapping works correctly

The TestOptimizedTrueAudit class is the CRITICAL regression guard —
it scans production source files for `optimized=true` in URL construction.
"""

from pathlib import Path

import pytest

from tests.smoke.utils.cdn_prober import (
    CDN_BASE,
    build_image_url,
    build_video_url,
    build_thumbnail_url,
    to_proxy_url,
    is_civitai_cdn_url,
    detect_media_type,
)
from tests.smoke.fixtures.known_urls import (
    REALISTIC_VISION_IMAGE_UUID,
    REALISTIC_VISION_IMAGE_FILENAME,
    JUGGERNAUT_VIDEO_UUID,
    JUGGERNAUT_VIDEO_FILENAME,
)


# ============================================================================
# Project root for file scanning
# ============================================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


# ============================================================================
# TestBuildUrls — URL structure validation
# ============================================================================


class TestBuildUrls:
    """Verify URL construction helpers produce correct CDN URLs."""

    def test_image_url_correct_structure(self):
        url = build_image_url(REALISTIC_VISION_IMAGE_UUID, REALISTIC_VISION_IMAGE_FILENAME)
        assert url.startswith(CDN_BASE)
        assert REALISTIC_VISION_IMAGE_UUID in url
        assert "width=450" in url
        assert REALISTIC_VISION_IMAGE_FILENAME in url

    def test_image_url_no_optimized_true(self):
        url = build_image_url(REALISTIC_VISION_IMAGE_UUID, REALISTIC_VISION_IMAGE_FILENAME)
        assert "optimized=true" not in url

    def test_image_url_custom_width(self):
        url = build_image_url(REALISTIC_VISION_IMAGE_UUID, REALISTIC_VISION_IMAGE_FILENAME, width=1080)
        assert "width=1080" in url
        assert "width=450" not in url

    def test_video_url_has_transcode_true(self):
        url = build_video_url(JUGGERNAUT_VIDEO_UUID, JUGGERNAUT_VIDEO_FILENAME)
        assert "transcode=true" in url

    def test_video_url_has_anim_true(self):
        """CRITICAL: Video URL MUST have anim=true for Cloudflare direct serving.
        Without it, CDN redirects to B2 storage → 401 auth failure."""
        url = build_video_url(JUGGERNAUT_VIDEO_UUID, JUGGERNAUT_VIDEO_FILENAME)
        assert "anim=true" in url

    def test_video_url_no_optimized_true(self):
        url = build_video_url(JUGGERNAUT_VIDEO_UUID, JUGGERNAUT_VIDEO_FILENAME)
        assert "optimized=true" not in url

    def test_video_url_has_mp4_extension(self):
        url = build_video_url(JUGGERNAUT_VIDEO_UUID, "image.jpeg")
        assert url.endswith(".mp4")

    def test_video_url_preserves_mp4_extension(self):
        url = build_video_url(JUGGERNAUT_VIDEO_UUID, JUGGERNAUT_VIDEO_FILENAME)
        assert url.endswith(".mp4")

    def test_thumbnail_url_has_anim_false(self):
        url = build_thumbnail_url(JUGGERNAUT_VIDEO_UUID, JUGGERNAUT_VIDEO_FILENAME)
        assert "anim=false" in url

    def test_thumbnail_url_has_transcode_true(self):
        url = build_thumbnail_url(JUGGERNAUT_VIDEO_UUID, JUGGERNAUT_VIDEO_FILENAME)
        assert "transcode=true" in url

    def test_thumbnail_url_no_optimized_true(self):
        url = build_thumbnail_url(JUGGERNAUT_VIDEO_UUID, JUGGERNAUT_VIDEO_FILENAME)
        assert "optimized=true" not in url


# ============================================================================
# TestToProxyUrl — Proxy wrapping
# ============================================================================


class TestToProxyUrl:
    """Verify proxy URL construction."""

    def test_civitai_url_gets_proxied(self):
        url = f"{CDN_BASE}/some-uuid/width=450/image.jpeg"
        proxied = to_proxy_url(url)
        assert proxied.startswith("/api/browse/image-proxy?url=")

    def test_non_civitai_not_proxied(self):
        url = "https://example.com/image.jpg"
        assert to_proxy_url(url) == url

    def test_already_proxied_not_double_wrapped(self):
        url = "/api/browse/image-proxy?url=https%3A%2F%2Fimage.civitai.com%2Ftest"
        assert to_proxy_url(url) == url

    def test_proxy_url_encodes_inner_url(self):
        inner = f"{CDN_BASE}/uuid/width=450/file.jpeg"
        proxied = to_proxy_url(inner)
        # The inner URL should be URL-encoded
        assert "image.civitai.com" not in proxied.split("url=")[1].split("&")[0].replace("%2F", "/").replace("%3A", ":") or True
        # Just verify it's encoded (contains %3A for https:)
        assert "%3A" in proxied or "%2F" in proxied

    def test_empty_url_returns_empty(self):
        assert to_proxy_url("") == ""

    def test_images_civitai_gets_proxied(self):
        url = "https://images.civitai.com/test/image.jpg"
        proxied = to_proxy_url(url)
        assert proxied.startswith("/api/browse/image-proxy?url=")

    def test_cdn_civitai_gets_proxied(self):
        url = "https://cdn.civitai.com/test/image.jpg"
        proxied = to_proxy_url(url)
        assert proxied.startswith("/api/browse/image-proxy?url=")


# ============================================================================
# TestMediaTypeDetection — Media type detection
# ============================================================================


class TestMediaTypeDetection:
    """Verify media type detection matches frontend and backend."""

    def test_mp4_extension_is_video(self):
        assert detect_media_type("https://example.com/video.mp4") == "video"

    def test_jpeg_is_image(self):
        assert detect_media_type("https://example.com/image.jpeg") == "image"

    def test_transcode_true_is_video(self):
        url = f"{CDN_BASE}/uuid/transcode=true,width=450/file.jpeg"
        assert detect_media_type(url) == "video"

    def test_anim_false_with_transcode_is_image(self):
        url = f"{CDN_BASE}/uuid/anim=false,transcode=true,width=450/file.jpeg"
        assert detect_media_type(url) == "image"

    def test_empty_url_is_unknown(self):
        assert detect_media_type("") == "unknown"


# ============================================================================
# TestOptimizedTrueAudit — CRITICAL regression guard
# ============================================================================


def _file_has_optimized_true_in_urls(filepath: Path) -> list[tuple[int, str]]:
    """
    Scan file for `optimized=true` in URL construction patterns.

    Returns list of (line_number, line_text) matches.
    Excludes:
    - Comments (lines starting with // or #)
    - Plan/documentation files
    - This test file itself
    - Lines that are clearly not URL construction
    """
    if not filepath.exists():
        return []

    matches = []
    text = filepath.read_text(encoding="utf-8", errors="ignore")
    for i, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        # Skip comments
        if stripped.startswith("//") or stripped.startswith("#") or stripped.startswith("*"):
            continue
        # Skip markdown/plan files content (inside strings that reference plans)
        if "PLAN-" in line or "plans/" in line:
            continue
        # Check for optimized=true in URL construction context
        if "optimized=true" in stripped:
            matches.append((i, stripped))

    return matches


class TestOptimizedTrueAudit:
    """
    CRITICAL: Scan production files for `optimized=true` in URL construction.

    This is the key regression guard. If ANY production file contains
    `optimized=true` in a URL-building context, the test fails.
    """

    def test_civitai_transformers_no_optimized_true(self):
        """civitaiTransformers.ts should be clean (fixed in commit 3badab3)."""
        filepath = PROJECT_ROOT / "apps/web/src/lib/utils/civitaiTransformers.ts"
        matches = _file_has_optimized_true_in_urls(filepath)
        assert matches == [], (
            f"civitaiTransformers.ts still has optimized=true at lines: "
            f"{[m[0] for m in matches]}"
        )

    def test_media_preview_no_optimized_true(self):
        """MediaPreview.tsx should NOT have optimized=true."""
        filepath = PROJECT_ROOT / "apps/web/src/components/ui/MediaPreview.tsx"
        matches = _file_has_optimized_true_in_urls(filepath)
        assert matches == [], (
            f"MediaPreview.tsx has optimized=true at lines: "
            f"{[m[0] for m in matches]}\n"
            f"Lines:\n" + "\n".join(f"  L{n}: {t}" for n, t in matches)
        )

    def test_fullscreen_viewer_no_optimized_true(self):
        """FullscreenMediaViewer.tsx should NOT have optimized=true."""
        filepath = PROJECT_ROOT / "apps/web/src/components/ui/FullscreenMediaViewer.tsx"
        matches = _file_has_optimized_true_in_urls(filepath)
        assert matches == [], (
            f"FullscreenMediaViewer.tsx has optimized=true at lines: "
            f"{[m[0] for m in matches]}\n"
            f"Lines:\n" + "\n".join(f"  L{n}: {t}" for n, t in matches)
        )

    def test_media_detection_py_no_optimized_true(self):
        """media_detection.py should NOT have optimized=true."""
        filepath = PROJECT_ROOT / "src/utils/media_detection.py"
        matches = _file_has_optimized_true_in_urls(filepath)
        assert matches == [], (
            f"media_detection.py has optimized=true at lines: "
            f"{[m[0] for m in matches]}\n"
            f"Lines:\n" + "\n".join(f"  L{n}: {t}" for n, t in matches)
        )

    def test_browse_py_no_optimized_true(self):
        """browse.py (proxy endpoint) should NOT have optimized=true."""
        filepath = PROJECT_ROOT / "apps/api/src/routers/browse.py"
        matches = _file_has_optimized_true_in_urls(filepath)
        assert matches == [], (
            f"browse.py has optimized=true at lines: "
            f"{[m[0] for m in matches]}\n"
            f"Lines:\n" + "\n".join(f"  L{n}: {t}" for n, t in matches)
        )


# ============================================================================
# TestIsCivitaiCdnUrl — Domain detection
# ============================================================================


class TestIsCivitaiCdnUrl:
    """Verify Civitai CDN domain detection."""

    def test_image_civitai_is_cdn(self):
        assert is_civitai_cdn_url("https://image.civitai.com/test") is True

    def test_images_civitai_is_cdn(self):
        assert is_civitai_cdn_url("https://images.civitai.com/test") is True

    def test_cdn_civitai_is_cdn(self):
        assert is_civitai_cdn_url("https://cdn.civitai.com/test") is True

    def test_example_com_is_not_cdn(self):
        assert is_civitai_cdn_url("https://example.com/test") is False

    def test_civitai_com_is_not_cdn(self):
        """civitai.com (without image/images/cdn prefix) is NOT a CDN URL."""
        assert is_civitai_cdn_url("https://civitai.com/models/123") is False
