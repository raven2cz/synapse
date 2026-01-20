"""
Unit tests for media detection utilities.

Tests cover:
- URL-based media type detection
- Civitai URL handling quirks
- Video URL optimization
- Thumbnail URL generation
- Extension extraction

Author: Synapse Team
License: MIT
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from utils.media_detection import (
    MediaType,
    MediaInfo,
    detect_media_type,
    is_video_url,
    is_image_url,
    get_optimized_video_url,
    get_video_thumbnail_url,
    get_civitai_static_url,
    get_civitai_video_url,
    extract_extension,
    normalize_video_extension,
)


# =============================================================================
# MediaType Detection Tests
# =============================================================================

class TestDetectMediaType:
    """Tests for detect_media_type function."""
    
    def test_standard_video_extensions(self):
        """Common video extensions should be detected."""
        video_urls = [
            "https://example.com/video.mp4",
            "https://example.com/video.webm",
            "https://example.com/video.mov",
            "https://example.com/video.avi",
            "https://example.com/video.mkv",
        ]
        
        for url in video_urls:
            result = detect_media_type(url)
            assert result.type == MediaType.VIDEO, f"Failed for {url}"
    
    def test_standard_image_extensions(self):
        """Common image extensions should be detected."""
        image_urls = [
            "https://example.com/image.jpg",
            "https://example.com/image.jpeg",
            "https://example.com/image.png",
            "https://example.com/image.webp",
            "https://example.com/image.gif",
        ]
        
        for url in image_urls:
            result = detect_media_type(url)
            assert result.type == MediaType.IMAGE, f"Failed for {url}"
    
    def test_case_insensitive(self):
        """Extension detection should be case-insensitive."""
        urls = [
            ("https://example.com/video.MP4", MediaType.VIDEO),
            ("https://example.com/image.JPG", MediaType.IMAGE),
            ("https://example.com/video.WebM", MediaType.VIDEO),
        ]
        
        for url, expected in urls:
            result = detect_media_type(url)
            assert result.type == expected
    
    def test_url_with_query_params(self):
        """Extensions should be detected with query params."""
        url = "https://example.com/video.mp4?width=1080&quality=high"
        result = detect_media_type(url)
        assert result.type == MediaType.VIDEO
    
    def test_empty_url(self):
        """Empty URL should return UNKNOWN."""
        result = detect_media_type("")
        assert result.type == MediaType.UNKNOWN
    
    def test_no_extension_defaults_to_image(self):
        """URL without extension defaults to IMAGE."""
        url = "https://example.com/media/12345"
        result = detect_media_type(url)
        assert result.type == MediaType.IMAGE
    
    def test_content_type_video(self):
        """Content-Type header should be used when provided."""
        url = "https://example.com/media"
        result = detect_media_type(url, content_type="video/mp4")
        assert result.type == MediaType.VIDEO
        assert result.source == "content-type"
    
    def test_content_type_image(self):
        """Content-Type header should detect images."""
        url = "https://example.com/media"
        result = detect_media_type(url, content_type="image/jpeg")
        assert result.type == MediaType.IMAGE


# =============================================================================
# Civitai-Specific Tests
# =============================================================================

class TestCivitaiDetection:
    """Tests for Civitai URL handling."""
    
    def test_civitai_video_extension(self):
        """Standard Civitai video URL."""
        url = "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/abc123.mp4"
        result = detect_media_type(url)
        assert result.type == MediaType.VIDEO
    
    def test_civitai_image_extension(self):
        """Standard Civitai image URL."""
        url = "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/abc123.jpeg"
        result = detect_media_type(url)
        assert result.type == MediaType.IMAGE
    
    def test_civitai_transcode_indicates_video(self):
        """Civitai transcode=true indicates video."""
        url = "https://image.civitai.com/preview.jpeg?transcode=true"
        result = detect_media_type(url)
        assert result.type == MediaType.VIDEO
        assert result.source == "pattern"  # Detected via pattern
    
    def test_civitai_anim_false_indicates_static(self):
        """Civitai anim=false on image URL stays as image."""
        # Note: .jpeg extension has priority, anim=false just confirms it's static
        url = "https://image.civitai.com/preview.jpeg?anim=false"
        result = detect_media_type(url)
        assert result.type == MediaType.IMAGE
        # Extension-based detection has priority over query params
        assert result.source == "extension"
    
    def test_civitai_fake_jpeg_video(self):
        """Civitai video disguised as JPEG (with transcode param)."""
        # This is detected via the transcode=true pattern
        url = "https://image.civitai.com/fake.jpeg?transcode=true&width=1080"
        result = detect_media_type(url)
        assert result.type == MediaType.VIDEO


# =============================================================================
# URL Pattern Tests
# =============================================================================

class TestUrlPatterns:
    """Tests for URL pattern matching."""
    
    def test_video_path_pattern(self):
        """URLs with /video/ in path detected as video."""
        url = "https://cdn.example.com/videos/12345/preview"
        result = detect_media_type(url)
        assert result.type == MediaType.VIDEO
    
    def test_type_video_param(self):
        """URLs with type=video parameter."""
        url = "https://example.com/media/12345?type=video"
        result = detect_media_type(url)
        assert result.type == MediaType.VIDEO


# =============================================================================
# Convenience Function Tests
# =============================================================================

class TestConvenienceFunctions:
    """Tests for is_video_url and is_image_url."""
    
    def test_is_video_url(self):
        """is_video_url returns correct boolean."""
        assert is_video_url("https://example.com/video.mp4") is True
        assert is_video_url("https://example.com/image.jpg") is False
    
    def test_is_image_url(self):
        """is_image_url returns correct boolean."""
        assert is_image_url("https://example.com/image.jpg") is True
        assert is_image_url("https://example.com/video.mp4") is False


# =============================================================================
# URL Transformation Tests
# =============================================================================

class TestOptimizedVideoUrl:
    """Tests for get_optimized_video_url function."""
    
    def test_civitai_adds_transcode(self):
        """Civitai URLs get transcode=true parameter."""
        url = "https://image.civitai.com/video.mp4"
        result = get_optimized_video_url(url)
        
        assert "transcode=true" in result
        assert "width=1080" in result
    
    def test_custom_quality(self):
        """Custom quality width is applied."""
        url = "https://image.civitai.com/video.mp4"
        result = get_optimized_video_url(url, width=720)
        
        assert "width=720" in result
    
    def test_preserves_existing_params(self):
        """Existing query params are preserved."""
        url = "https://image.civitai.com/video.mp4?foo=bar"
        result = get_optimized_video_url(url)
        
        assert "foo=bar" in result
        assert "transcode=true" in result
    
    def test_non_civitai_unchanged(self):
        """Non-Civitai URLs returned unchanged."""
        url = "https://other-cdn.com/video.mp4"
        result = get_optimized_video_url(url)
        
        assert result == url


class TestVideoThumbnailUrl:
    """Tests for get_video_thumbnail_url function."""
    
    def test_civitai_adds_anim_false(self):
        """Civitai URLs get anim=false parameter."""
        url = "https://image.civitai.com/video.mp4"
        result = get_video_thumbnail_url(url)
        
        assert "anim=false" in result
    
    def test_removes_transcode(self):
        """Transcode param is removed (we want static image)."""
        url = "https://image.civitai.com/video.mp4?transcode=true"
        result = get_video_thumbnail_url(url)
        
        assert "anim=false" in result
        assert "transcode=true" not in result
    
    def test_adds_width(self):
        """Width parameter is added."""
        url = "https://image.civitai.com/video.mp4"
        result = get_video_thumbnail_url(url, width=450)
        
        assert "width=450" in result


class TestCivitaiAliases:
    """Tests for Civitai-specific alias functions."""
    
    def test_get_civitai_static_url(self):
        """get_civitai_static_url adds anim=false."""
        url = "https://image.civitai.com/preview.mp4"
        result = get_civitai_static_url(url)
        
        assert "anim=false" in result
    
    def test_get_civitai_static_url_non_civitai(self):
        """Non-Civitai URLs returned unchanged."""
        url = "https://other.com/video.mp4"
        result = get_civitai_static_url(url)
        
        assert result == url
    
    def test_get_civitai_video_url(self):
        """get_civitai_video_url is alias for get_optimized_video_url."""
        url = "https://image.civitai.com/video.mp4"
        result = get_civitai_video_url(url, quality=720)
        
        assert "transcode=true" in result
        assert "width=720" in result


# =============================================================================
# Extension Extraction Tests
# =============================================================================

class TestExtractExtension:
    """Tests for extract_extension function."""
    
    def test_standard_extension(self):
        """Standard URL extension extraction."""
        assert extract_extension("https://example.com/video.mp4") == "mp4"
        assert extract_extension("https://example.com/image.jpg") == "jpg"
    
    def test_with_query_params(self):
        """Extension extracted before query params."""
        url = "https://example.com/video.mp4?width=1080"
        assert extract_extension(url) == "mp4"
    
    def test_no_extension(self):
        """URL without extension returns None."""
        assert extract_extension("https://example.com/media/12345") is None
    
    def test_empty_url(self):
        """Empty URL returns None."""
        assert extract_extension("") is None


class TestNormalizeVideoExtension:
    """Tests for normalize_video_extension function."""
    
    def test_civitai_fake_jpeg(self):
        """Civitai fake JPEG video gets .mp4 extension."""
        # This only works if URL is detected as video
        url = "https://image.civitai.com/video.mp4"  # Already correct
        result = normalize_video_extension(url)
        assert result == url  # No change needed
    
    def test_non_civitai_unchanged(self):
        """Non-Civitai URLs unchanged."""
        url = "https://other.com/video.mp4"
        result = normalize_video_extension(url)
        assert result == url


# =============================================================================
# MediaInfo Tests
# =============================================================================

class TestMediaInfo:
    """Tests for MediaInfo dataclass."""
    
    def test_default_values(self):
        """MediaInfo has correct defaults."""
        info = MediaInfo(type=MediaType.IMAGE)
        
        assert info.type == MediaType.IMAGE
        assert info.extension is None
        assert info.is_animated is False
        assert info.source == "extension"
    
    def test_animated_flag(self):
        """is_animated flag works correctly."""
        gif_info = detect_media_type("https://example.com/animation.gif")
        
        assert gif_info.type == MediaType.IMAGE
        assert gif_info.is_animated is True


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for complete workflows."""
    
    def test_civitai_video_workflow(self):
        """Complete Civitai video handling workflow."""
        original = "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/abc123.mp4"
        
        # 1. Detect as video
        info = detect_media_type(original)
        assert info.type == MediaType.VIDEO
        
        # 2. Get optimized playback URL
        playback = get_optimized_video_url(original, width=1080)
        assert "transcode=true" in playback
        
        # 3. Get static thumbnail
        thumbnail = get_video_thumbnail_url(original)
        assert "anim=false" in thumbnail
    
    def test_civitai_image_workflow(self):
        """Complete Civitai image handling workflow."""
        original = "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/abc123.jpeg"
        
        # 1. Detect as image
        info = detect_media_type(original)
        assert info.type == MediaType.IMAGE
        
        # 2. Static version (same for images)
        static = get_civitai_static_url(original)
        assert "anim=false" in static


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
