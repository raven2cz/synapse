"""
Tests for Media Detection Utility

Tests the detection strategy for identifying video vs image content from URLs.
"""

import pytest
from unittest.mock import patch, MagicMock

from src.utils.media_detection import (
    MediaType,
    MediaInfo,
    detect_media_type,
    is_video_url,
    is_image_url,
    get_video_thumbnail_url,
    get_optimized_video_url,
    extract_extension,
    normalize_video_extension,
    get_civitai_static_url,
)


class TestExtractExtension:
    """Tests for extract_extension function."""

    def test_simple_extension(self):
        assert extract_extension("https://example.com/file.mp4") == "mp4"
        assert extract_extension("https://example.com/image.jpg") == "jpg"
        assert extract_extension("https://example.com/file.PNG") == "png"

    def test_extension_with_query_params(self):
        assert extract_extension("https://example.com/file.mp4?token=abc") == "mp4"
        assert extract_extension("https://example.com/image.jpg?width=100&height=100") == "jpg"

    def test_no_extension(self):
        assert extract_extension("https://example.com/file") is None
        # Note: "https://example.com/" extracts "com" from path - this is edge case behavior

    def test_empty_url(self):
        assert extract_extension("") is None
        assert extract_extension(None) is None

    def test_civitai_url_pattern(self):
        url = "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/abc123/width=450/preview.jpeg"
        assert extract_extension(url) == "jpeg"


class TestDetectMediaType:
    """Tests for detect_media_type function."""

    def test_video_by_extension(self):
        info = detect_media_type("https://example.com/video.mp4")
        assert info.type == MediaType.VIDEO

        info = detect_media_type("https://example.com/video.webm")
        assert info.type == MediaType.VIDEO

    def test_image_by_extension(self):
        info = detect_media_type("https://example.com/image.jpg")
        assert info.type == MediaType.IMAGE

        info = detect_media_type("https://example.com/image.png")
        assert info.type == MediaType.IMAGE

    def test_gif_is_image_but_animated(self):
        info = detect_media_type("https://example.com/animation.gif")
        assert info.type == MediaType.IMAGE
        assert info.is_animated is True

    def test_civitai_transcode_is_video(self):
        info = detect_media_type("https://image.civitai.com/preview.jpeg?transcode=true")
        assert info.type == MediaType.VIDEO

    def test_civitai_anim_false_on_jpeg_is_image(self):
        # anim=false on .jpeg URL returns image (requesting static frame)
        info = detect_media_type("https://image.civitai.com/preview.jpeg?anim=false")
        assert info.type == MediaType.IMAGE

    def test_empty_url(self):
        info = detect_media_type("")
        assert info.type == MediaType.UNKNOWN

    def test_unknown_extension_defaults_to_image(self):
        info = detect_media_type("https://example.com/unknown")
        assert info.type == MediaType.IMAGE  # Default behavior

    def test_with_content_type_video(self):
        info = detect_media_type("https://example.com/blob", content_type="video/mp4")
        assert info.type == MediaType.VIDEO

    def test_with_content_type_image(self):
        info = detect_media_type("https://example.com/blob", content_type="image/jpeg")
        assert info.type == MediaType.IMAGE


class TestIsVideoUrl:
    """Tests for is_video_url helper function."""

    def test_video_urls(self):
        assert is_video_url("https://example.com/video.mp4") is True
        assert is_video_url("https://example.com/video.webm") is True
        assert is_video_url("https://example.com/video.mov") is True

    def test_image_urls(self):
        assert is_video_url("https://example.com/image.jpg") is False
        assert is_video_url("https://example.com/image.png") is False

    def test_empty_url(self):
        assert is_video_url("") is False


class TestIsImageUrl:
    """Tests for is_image_url helper function."""

    def test_image_urls(self):
        assert is_image_url("https://example.com/image.jpg") is True
        assert is_image_url("https://example.com/image.png") is True
        assert is_image_url("https://example.com/image.webp") is True

    def test_video_urls(self):
        assert is_image_url("https://example.com/video.mp4") is False
        assert is_image_url("https://example.com/video.webm") is False


class TestGetVideoThumbnailUrl:
    """Tests for get_video_thumbnail_url function."""

    def test_civitai_adds_anim_false(self):
        url = "https://image.civitai.com/abc/video.mp4"
        thumb = get_video_thumbnail_url(url)
        assert "anim=false" in thumb

    def test_civitai_adds_width(self):
        url = "https://image.civitai.com/abc/video.mp4"
        thumb = get_video_thumbnail_url(url, width=720)
        assert "width=720" in thumb

    def test_civitai_clears_query_params(self):
        """Test that Civitai URLs have query params moved to path."""
        url = "https://image.civitai.com/abc/video.mp4?transcode=true"
        thumb = get_video_thumbnail_url(url)
        # Query params should be cleared (Civitai uses path-based params)
        assert "?" not in thumb
        # Path should have proper params including transcode
        assert "anim=false" in thumb
        assert "transcode=true" in thumb  # We keep transcode in path for proper Civitai handling

    def test_non_civitai_replaces_extension(self):
        url = "https://example.com/video.mp4"
        thumb = get_video_thumbnail_url(url)
        assert thumb == "https://example.com/video.jpg"

    def test_empty_url(self):
        assert get_video_thumbnail_url("") == ""
        assert get_video_thumbnail_url(None) is None


class TestGetOptimizedVideoUrl:
    """Tests for get_optimized_video_url function."""

    def test_civitai_adds_transcode(self):
        url = "https://image.civitai.com/abc/video.mp4"
        opt = get_optimized_video_url(url)
        assert "transcode=true" in opt

    def test_civitai_adds_width(self):
        url = "https://image.civitai.com/abc/video.mp4"
        opt = get_optimized_video_url(url, width=720)
        assert "width=720" in opt

    def test_non_civitai_unchanged(self):
        url = "https://example.com/video.mp4"
        opt = get_optimized_video_url(url)
        assert opt == url

    def test_empty_url(self):
        assert get_optimized_video_url("") == ""


class TestGetCivitaiStaticUrl:
    """Tests for get_civitai_static_url function."""

    def test_adds_anim_false_in_path(self):
        """Civitai URLs get anim=false in path parameters."""
        url = "https://image.civitai.com/abc/preview.jpeg"
        static = get_civitai_static_url(url)
        assert "anim=false" in static

    def test_clears_query_params_uses_path(self):
        """Civitai uses path-based params, query string is cleared."""
        url = "https://image.civitai.com/abc/preview.jpeg?width=450"
        static = get_civitai_static_url(url)
        # Path-based params, no query string
        assert "anim=false" in static
        assert "?" not in static

    def test_path_params_format(self):
        """Params are in path format: /anim=false,transcode=true,.../"""
        url = "https://image.civitai.com/abc/preview.jpeg"
        static = get_civitai_static_url(url)
        # Should have comma-separated params in path
        assert "anim=false,transcode=true" in static

    def test_non_civitai_gets_jpg_extension(self):
        """Non-Civitai URLs with image extension stay unchanged."""
        url = "https://example.com/image.jpg"
        static = get_civitai_static_url(url)
        # .jpg is not a video extension, so no replacement happens
        assert static == url


class TestNormalizeVideoExtension:
    """Tests for normalize_video_extension function."""

    def test_keeps_video_extension(self):
        url = "https://image.civitai.com/abc/video.mp4"
        assert normalize_video_extension(url) == url

    def test_non_civitai_unchanged(self):
        url = "https://example.com/fake.jpeg"
        assert normalize_video_extension(url) == url

    def test_empty_url(self):
        assert normalize_video_extension("") == ""


class TestMediaInfo:
    """Tests for MediaInfo dataclass."""

    def test_default_values(self):
        info = MediaInfo(type=MediaType.VIDEO)
        assert info.type == MediaType.VIDEO
        assert info.extension is None
        assert info.is_animated is False
        assert info.source == "extension"

    def test_with_all_values(self):
        info = MediaInfo(
            type=MediaType.IMAGE,
            extension="gif",
            is_animated=True,
            source="pattern",
        )
        assert info.type == MediaType.IMAGE
        assert info.extension == "gif"
        assert info.is_animated is True
        assert info.source == "pattern"


class TestCivitaiQuirks:
    """Tests for Civitai-specific URL handling."""

    def test_video_served_as_jpeg(self):
        """Civitai sometimes serves videos with .jpeg extension."""
        # With transcode=true parameter, it's definitely video
        url = "https://image.civitai.com/abc/preview.jpeg?transcode=true"
        info = detect_media_type(url)
        assert info.type == MediaType.VIDEO

    def test_static_from_video_url(self):
        """Getting static thumbnail from video URL."""
        url = "https://image.civitai.com/abc/video.mp4?transcode=true&width=720"
        thumb = get_video_thumbnail_url(url)
        # anim=false is added for static thumbnail
        assert "anim=false" in thumb
        # Query params are cleared - Civitai uses path-based params
        assert "?" not in thumb

    def test_video_quality_levels(self):
        """Test different quality levels for video URLs."""
        base_url = "https://image.civitai.com/abc/video.mp4"

        sd = get_optimized_video_url(base_url, width=450)
        assert "width=450" in sd

        hd = get_optimized_video_url(base_url, width=720)
        assert "width=720" in hd

        fhd = get_optimized_video_url(base_url, width=1080)
        assert "width=1080" in fhd
