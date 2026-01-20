"""
Tests for Pack Summary thumbnail_type extension.

Author: Synapse Team
License: MIT
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from api.pack_summary_ext import (
    PackSummaryExtended,
    determine_thumbnail_type,
    extend_pack_summary_response,
)


class TestDetermineThumbnailType:
    """Tests for determine_thumbnail_type function."""
    
    def test_image_extension(self):
        """Image extensions return 'image'."""
        assert determine_thumbnail_type("https://example.com/thumb.jpg") == 'image'
        assert determine_thumbnail_type("https://example.com/thumb.png") == 'image'
        assert determine_thumbnail_type("https://example.com/thumb.webp") == 'image'
    
    def test_video_extension(self):
        """Video extensions return 'video'."""
        assert determine_thumbnail_type("https://example.com/thumb.mp4") == 'video'
        assert determine_thumbnail_type("https://example.com/thumb.webm") == 'video'
        assert determine_thumbnail_type("https://example.com/thumb.mov") == 'video'
    
    def test_transcode_pattern(self):
        """Civitai transcode=true indicates video."""
        url = "https://image.civitai.com/preview.jpeg?transcode=true"
        assert determine_thumbnail_type(url) == 'video'
    
    def test_none_url(self):
        """None URL defaults to 'image'."""
        assert determine_thumbnail_type(None) == 'image'
    
    def test_preview_list_fallback(self):
        """Check preview list when URL is ambiguous."""
        # Dict-style preview
        previews = [{'media_type': 'video', 'url': 'https://example.com/vid.mp4'}]
        assert determine_thumbnail_type("https://example.com/thumb.jpeg", previews) == 'video'
    
    def test_no_extension_defaults_to_image(self):
        """URLs without clear extension default to 'image'."""
        assert determine_thumbnail_type("https://example.com/media/12345") == 'image'


class TestExtendPackSummaryResponse:
    """Tests for extend_pack_summary_response function."""
    
    def test_adds_thumbnail_type(self):
        """Should add thumbnail_type to pack data."""
        pack_data = {
            'name': 'Test Pack',
            'thumbnail': 'https://example.com/thumb.jpg'
        }
        
        result = extend_pack_summary_response(pack_data)
        
        assert 'thumbnail_type' in result
        assert result['thumbnail_type'] == 'image'
    
    def test_video_thumbnail(self):
        """Should detect video thumbnail."""
        pack_data = {
            'name': 'Test Pack',
            'thumbnail': 'https://example.com/thumb.mp4'
        }
        
        result = extend_pack_summary_response(pack_data)
        
        assert result['thumbnail_type'] == 'video'
    
    def test_with_previews(self):
        """Should use previews when available."""
        pack_data = {
            'name': 'Test Pack',
            'thumbnail': 'https://example.com/thumb.jpeg'
        }
        previews = [{'media_type': 'video'}]
        
        result = extend_pack_summary_response(pack_data, previews)
        
        assert result['thumbnail_type'] == 'video'


class TestPackSummaryExtended:
    """Tests for PackSummaryExtended model."""
    
    def test_default_thumbnail_type(self):
        """Default thumbnail_type should be 'image'."""
        summary = PackSummaryExtended(name="Test")
        assert summary.thumbnail_type == 'image'
    
    def test_video_thumbnail_type(self):
        """Can set thumbnail_type to 'video'."""
        summary = PackSummaryExtended(name="Test", thumbnail_type='video')
        assert summary.thumbnail_type == 'video'
    
    def test_all_fields(self):
        """All fields work correctly."""
        summary = PackSummaryExtended(
            name="Test Pack",
            version="2.0",
            thumbnail="https://example.com/thumb.mp4",
            thumbnail_type='video',
            model_type='LORA',
            base_model='SDXL 1.0',
        )
        
        assert summary.name == "Test Pack"
        assert summary.thumbnail_type == 'video'
        assert summary.model_type == 'LORA'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
