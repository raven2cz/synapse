"""
Tests for Media Detection Utility

Tests the multi-layer detection strategy for identifying
video vs image content from URLs.
"""

import pytest
from unittest.mock import patch, MagicMock

from src.utils.media_detection import (
    MediaType,
    MediaInfo,
    detect_media_type,
    detect_by_extension,
    detect_by_url_pattern,
    detect_by_content_type,
    is_video_url,
    is_likely_animated,
    get_video_thumbnail_url,
    get_url_extension,
)


class TestGetUrlExtension:
    """Tests for get_url_extension function."""
    
    def test_simple_extension(self):
        assert get_url_extension("https://example.com/file.mp4") == ".mp4"
        assert get_url_extension("https://example.com/image.jpg") == ".jpg"
        assert get_url_extension("https://example.com/file.PNG") == ".png"
    
    def test_extension_with_query_params(self):
        assert get_url_extension("https://example.com/file.mp4?token=abc") == ".mp4"
        assert get_url_extension("https://example.com/image.jpg?width=100&height=100") == ".jpg"
    
    def test_no_extension(self):
        assert get_url_extension("https://example.com/file") is None
        assert get_url_extension("https://example.com/") is None
    
    def test_empty_url(self):
        assert get_url_extension("") is None
        assert get_url_extension(None) is None
    
    def test_civitai_url_pattern(self):
        # Real Civitai URL pattern
        url = "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/abc123/width=450/preview.jpeg"
        assert get_url_extension(url) == ".jpeg"


class TestDetectByExtension:
    """Tests for extension-based detection."""
    
    def test_video_extensions(self):
        assert detect_by_extension("https://example.com/video.mp4") == MediaType.VIDEO
        assert detect_by_extension("https://example.com/video.webm") == MediaType.VIDEO
        assert detect_by_extension("https://example.com/video.mov") == MediaType.VIDEO
        assert detect_by_extension("https://example.com/anim.gif") == MediaType.VIDEO
    
    def test_image_extensions(self):
        assert detect_by_extension("https://example.com/image.jpg") == MediaType.IMAGE
        assert detect_by_extension("https://example.com/image.jpeg") == MediaType.IMAGE
        assert detect_by_extension("https://example.com/image.png") == MediaType.IMAGE
        assert detect_by_extension("https://example.com/image.bmp") == MediaType.IMAGE
    
    def test_unknown_extension(self):
        assert detect_by_extension("https://example.com/file.xyz") == MediaType.UNKNOWN
        assert detect_by_extension("https://example.com/file") == MediaType.UNKNOWN
    
    def test_case_insensitive(self):
        assert detect_by_extension("https://example.com/video.MP4") == MediaType.VIDEO
        assert detect_by_extension("https://example.com/image.JPG") == MediaType.IMAGE


class TestDetectByUrlPattern:
    """Tests for URL pattern-based detection."""
    
    def test_civitai_video_patterns(self):
        # Patterns that should match as video
        assert detect_by_url_pattern("https://civitai.com/videos/something.mp4") == MediaType.VIDEO
        assert detect_by_url_pattern("https://image.civitai.com/video/xyz.mp4") == MediaType.VIDEO
    
    def test_generic_video_patterns(self):
        assert detect_by_url_pattern("https://example.com/path/file.mp4") == MediaType.VIDEO
        assert detect_by_url_pattern("https://example.com/path/file.webm?token=x") == MediaType.VIDEO
    
    def test_non_matching_patterns(self):
        # Regular image URLs should return unknown (not video)
        assert detect_by_url_pattern("https://example.com/image.jpeg") == MediaType.UNKNOWN
        assert detect_by_url_pattern("https://civitai.com/images/abc.jpg") == MediaType.UNKNOWN


class TestDetectByContentType:
    """Tests for Content-Type header detection."""
    
    @patch('src.utils.media_detection.requests')
    def test_video_content_type(self, mock_requests):
        mock_response = MagicMock()
        mock_response.headers = {'Content-Type': 'video/mp4'}
        mock_requests.head.return_value = mock_response
        
        media_type, mime = detect_by_content_type("https://example.com/file")
        assert media_type == MediaType.VIDEO
        assert mime == "video/mp4"
    
    @patch('src.utils.media_detection.requests')
    def test_image_content_type(self, mock_requests):
        mock_response = MagicMock()
        mock_response.headers = {'Content-Type': 'image/jpeg'}
        mock_requests.head.return_value = mock_response
        
        media_type, mime = detect_by_content_type("https://example.com/file")
        assert media_type == MediaType.IMAGE
        assert mime == "image/jpeg"
    
    @patch('src.utils.media_detection.requests')
    def test_gif_returns_unknown(self, mock_requests):
        # GIF can be animated or static, so we return unknown
        mock_response = MagicMock()
        mock_response.headers = {'Content-Type': 'image/gif'}
        mock_requests.head.return_value = mock_response
        
        media_type, mime = detect_by_content_type("https://example.com/file")
        assert media_type == MediaType.UNKNOWN
        assert mime == "image/gif"
    
    @patch('src.utils.media_detection.requests')
    def test_content_type_with_charset(self, mock_requests):
        mock_response = MagicMock()
        mock_response.headers = {'Content-Type': 'video/mp4; charset=utf-8'}
        mock_requests.head.return_value = mock_response
        
        media_type, mime = detect_by_content_type("https://example.com/file")
        assert media_type == MediaType.VIDEO
        assert mime == "video/mp4"
    
    @patch('src.utils.media_detection.requests')
    def test_request_timeout(self, mock_requests):
        import requests as real_requests
        mock_requests.head.side_effect = real_requests.exceptions.Timeout()
        mock_requests.exceptions = real_requests.exceptions
        
        media_type, mime = detect_by_content_type("https://example.com/file")
        assert media_type == MediaType.UNKNOWN
        assert mime is None


class TestDetectMediaType:
    """Tests for the main detect_media_type function."""
    
    def test_detection_by_extension_first(self):
        """Extension check should be tried first and succeed."""
        info = detect_media_type("https://example.com/video.mp4")
        assert info.type == MediaType.VIDEO
        assert info.detection_method == "extension"
    
    def test_detection_by_pattern_second(self):
        """Pattern check should work when extension is ambiguous."""
        # URL ends in .jpeg but has video pattern
        info = detect_media_type("https://civitai.com/video/abc.mp4?fake=true")
        assert info.type == MediaType.VIDEO
    
    def test_fallback_to_unknown(self):
        """Should return unknown if no detection method works."""
        info = detect_media_type("https://example.com/unknown_file", use_head_request=False)
        assert info.type == MediaType.UNKNOWN
        assert info.detection_method == "fallback"
    
    def test_empty_url(self):
        info = detect_media_type("")
        assert info.type == MediaType.UNKNOWN
        assert info.detection_method == "no_url"
    
    @patch('src.utils.media_detection.detect_by_content_type')
    def test_head_request_when_enabled(self, mock_content_type):
        mock_content_type.return_value = (MediaType.VIDEO, "video/mp4")
        
        # URL without recognizable extension/pattern
        info = detect_media_type(
            "https://example.com/blob/abc123",
            use_head_request=True
        )
        assert info.type == MediaType.VIDEO
        mock_content_type.assert_called_once()


class TestIsVideoUrl:
    """Tests for is_video_url helper function."""
    
    def test_video_urls(self):
        assert is_video_url("https://example.com/video.mp4") is True
        assert is_video_url("https://example.com/video.webm") is True
    
    def test_image_urls(self):
        assert is_video_url("https://example.com/image.jpg") is False
        assert is_video_url("https://example.com/image.png") is False
    
    def test_unknown_urls(self):
        assert is_video_url("https://example.com/blob") is False


class TestIsLikelyAnimated:
    """Tests for is_likely_animated helper function."""
    
    def test_gif_is_animated(self):
        assert is_likely_animated("https://example.com/animation.gif") is True
    
    def test_webp_is_animated(self):
        assert is_likely_animated("https://example.com/animation.webp") is True
    
    def test_other_formats_not_animated(self):
        assert is_likely_animated("https://example.com/image.jpg") is False
        assert is_likely_animated("https://example.com/video.mp4") is False


class TestGetVideoThumbnailUrl:
    """Tests for get_video_thumbnail_url function."""
    
    def test_civitai_video_to_image(self):
        url = "https://civitai.com/video/abc123.mp4"
        thumb = get_video_thumbnail_url(url)
        assert thumb == "https://civitai.com/image/abc123.mp4"
    
    def test_civitai_append_param(self):
        url = "https://civitai.com/media/abc123"
        thumb = get_video_thumbnail_url(url)
        assert "thumbnail=true" in thumb
    
    def test_non_civitai_returns_none(self):
        url = "https://example.com/video.mp4"
        thumb = get_video_thumbnail_url(url)
        assert thumb is None
    
    def test_empty_url(self):
        assert get_video_thumbnail_url("") is None
        assert get_video_thumbnail_url(None) is None


class TestCivitaiFakeJpegVideo:
    """
    Tests for detecting Civitai's quirk where videos are served
    with .jpeg extensions.
    """
    
    @patch('src.utils.media_detection.requests')
    def test_detect_jpeg_that_is_actually_video(self, mock_requests):
        """
        Civitai sometimes serves videos as .jpeg files.
        HEAD request should detect the actual Content-Type.
        """
        mock_response = MagicMock()
        mock_response.headers = {'Content-Type': 'video/mp4'}
        mock_requests.head.return_value = mock_response
        
        # URL looks like image but is actually video
        url = "https://image.civitai.com/abc/xyz.jpeg"
        
        # Without HEAD request, would be detected as image
        info_no_head = detect_media_type(url, use_head_request=False)
        assert info_no_head.type == MediaType.IMAGE
        
        # With HEAD request, correctly detected as video
        info_with_head = detect_media_type(url, use_head_request=True)
        assert info_with_head.type == MediaType.VIDEO


class TestMediaInfoSerialization:
    """Tests for MediaInfo serialization."""
    
    def test_to_dict_excludes_none(self):
        info = MediaInfo(type=MediaType.VIDEO, detection_method="extension")
        d = info.to_dict()
        
        assert d["type"] == "video"
        assert d["detection_method"] == "extension"
        assert "mime_type" not in d  # None values excluded
        assert "duration" not in d
    
    def test_to_dict_includes_all_fields(self):
        info = MediaInfo(
            type=MediaType.VIDEO,
            mime_type="video/mp4",
            duration=10.5,
            has_audio=True,
            width=1920,
            height=1080,
            detection_method="content_type",
        )
        d = info.to_dict()
        
        assert d["type"] == "video"
        assert d["mime_type"] == "video/mp4"
        assert d["duration"] == 10.5
        assert d["has_audio"] is True
        assert d["width"] == 1920
        assert d["height"] == 1080
