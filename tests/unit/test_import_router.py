"""
Tests for Import API Router.

Tests cover:
- URL parsing
- Preview counting
- Thumbnail collection
- Endpoint responses

Author: Synapse Team
License: MIT
"""

import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from api.import_router import (
    parse_civitai_url,
    count_previews_by_type,
    collect_thumbnail_options,
)


# =============================================================================
# URL Parsing Tests
# =============================================================================

class TestParseCivitaiUrl:
    """Tests for parse_civitai_url function."""
    
    def test_basic_model_url(self):
        """Test parsing basic model URL."""
        url = "https://civitai.com/models/12345"
        assert parse_civitai_url(url) == 12345
    
    def test_model_url_with_name(self):
        """Test parsing model URL with name slug."""
        url = "https://civitai.com/models/12345/amazing-lora-v2"
        assert parse_civitai_url(url) == 12345
    
    def test_model_url_with_version(self):
        """Test parsing model URL with version query param."""
        url = "https://civitai.com/models/12345?modelVersionId=67890"
        assert parse_civitai_url(url) == 12345
    
    def test_invalid_url_returns_none(self):
        """Test that invalid URLs return None."""
        assert parse_civitai_url("https://google.com") is None
        assert parse_civitai_url("not a url") is None
        assert parse_civitai_url("") is None
    
    def test_url_with_www(self):
        """Test URL with www prefix."""
        url = "https://www.civitai.com/models/12345"
        # Should still work - regex matches civitai.com
        assert parse_civitai_url(url) == 12345


# =============================================================================
# Preview Counting Tests
# =============================================================================

class TestCountPreviewsByType:
    """Tests for count_previews_by_type function."""
    
    def test_empty_list(self):
        """Test counting empty list."""
        result = count_previews_by_type([])
        
        assert result["image_count"] == 0
        assert result["video_count"] == 0
        assert result["nsfw_count"] == 0
    
    def test_images_only(self):
        """Test counting images only."""
        images = [
            {"url": "https://example.com/img1.jpg"},
            {"url": "https://example.com/img2.png"},
            {"url": "https://example.com/img3.webp"},
        ]
        
        result = count_previews_by_type(images)
        
        assert result["image_count"] == 3
        assert result["video_count"] == 0
    
    def test_videos_detection(self):
        """Test detecting video URLs."""
        images = [
            {"url": "https://example.com/video1.mp4"},
            {"url": "https://example.com/img1.jpg"},
            {"url": "https://image.civitai.com/preview.mp4"},
        ]
        
        result = count_previews_by_type(images)
        
        assert result["video_count"] == 2
        assert result["image_count"] == 1
    
    def test_nsfw_counting(self):
        """Test counting NSFW items."""
        images = [
            {"url": "https://example.com/img1.jpg", "nsfw": True},
            {"url": "https://example.com/img2.jpg", "nsfw": False},
            {"url": "https://example.com/img3.jpg", "nsfwLevel": 3},  # >=2 is NSFW
        ]
        
        result = count_previews_by_type(images)
        
        assert result["nsfw_count"] == 2
    
    def test_nsfw_filtering(self):
        """Test filtering NSFW when include_nsfw=False."""
        images = [
            {"url": "https://example.com/img1.jpg", "nsfw": True},
            {"url": "https://example.com/img2.jpg", "nsfw": False},
        ]
        
        result = count_previews_by_type(images, include_nsfw=False)
        
        # NSFW item should still be counted in nsfw_count
        # but not in image_count when filtered
        assert result["nsfw_count"] == 1
        assert result["image_count"] == 1  # Only non-NSFW counted


# =============================================================================
# Thumbnail Collection Tests
# =============================================================================

class TestCollectThumbnailOptions:
    """Tests for collect_thumbnail_options function."""
    
    def test_empty_versions(self):
        """Test with empty versions list."""
        result = collect_thumbnail_options([])
        assert result == []
    
    def test_basic_collection(self):
        """Test basic thumbnail collection."""
        versions = [
            {
                "id": 1,
                "images": [
                    {"url": "https://example.com/img1.jpg", "nsfw": False},
                    {"url": "https://example.com/img2.jpg", "nsfw": True},
                ]
            }
        ]
        
        result = collect_thumbnail_options(versions)
        
        assert len(result) == 2
        assert result[0]["url"] == "https://example.com/img1.jpg"
        assert result[0]["version_id"] == 1
        assert result[0]["nsfw"] is False
        assert result[1]["nsfw"] is True
    
    def test_deduplication(self):
        """Test that duplicate URLs are filtered."""
        versions = [
            {
                "id": 1,
                "images": [
                    {"url": "https://example.com/img1.jpg"},
                ]
            },
            {
                "id": 2,
                "images": [
                    {"url": "https://example.com/img1.jpg"},  # Duplicate
                    {"url": "https://example.com/img2.jpg"},
                ]
            }
        ]
        
        result = collect_thumbnail_options(versions)
        
        # Should have only 2 unique URLs
        assert len(result) == 2
        urls = [r["url"] for r in result]
        assert "https://example.com/img1.jpg" in urls
        assert "https://example.com/img2.jpg" in urls
    
    def test_max_thumbnails_limit(self):
        """Test max_thumbnails parameter."""
        versions = [
            {
                "id": 1,
                "images": [
                    {"url": f"https://example.com/img{i}.jpg"}
                    for i in range(30)
                ]
            }
        ]
        
        result = collect_thumbnail_options(versions, max_thumbnails=10)
        
        assert len(result) == 10
    
    def test_video_type_detection(self):
        """Test that video types are correctly detected."""
        versions = [
            {
                "id": 1,
                "images": [
                    {"url": "https://example.com/video.mp4"},
                    {"url": "https://example.com/image.jpg"},
                ]
            }
        ]
        
        result = collect_thumbnail_options(versions)
        
        assert len(result) == 2
        types = {r["url"]: r["type"] for r in result}
        assert types["https://example.com/video.mp4"] == "video"
        assert types["https://example.com/image.jpg"] == "image"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
