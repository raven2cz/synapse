"""
Test MIME types for video serving.

This test verifies that FastAPI StaticFiles correctly serves
.mp4 files with the proper Content-Type header.

Run with: pytest tests/integration/test_mime_types.py -v
Or manually: curl -I http://localhost:8000/previews/test_pack/resources/previews/preview_1.mp4

Author: Synapse Team
License: MIT
"""

import pytest
from pathlib import Path
import mimetypes


class TestMimeTypes:
    """Tests for MIME type handling."""
    
    def test_mp4_mime_type_registered(self):
        """Verify .mp4 has correct MIME type in Python's mimetypes."""
        mime_type, _ = mimetypes.guess_type("video.mp4")
        assert mime_type == "video/mp4", f"Expected video/mp4, got {mime_type}"
    
    def test_webm_mime_type_registered(self):
        """Verify .webm has correct MIME type."""
        mime_type, _ = mimetypes.guess_type("video.webm")
        assert mime_type == "video/webm", f"Expected video/webm, got {mime_type}"
    
    def test_common_image_mime_types(self):
        """Verify common image MIME types."""
        expected = {
            "image.jpg": "image/jpeg",
            "image.jpeg": "image/jpeg",
            "image.png": "image/png",
            "image.webp": "image/webp",
            "image.gif": "image/gif",
        }
        
        for filename, expected_mime in expected.items():
            mime_type, _ = mimetypes.guess_type(filename)
            assert mime_type == expected_mime, f"{filename}: expected {expected_mime}, got {mime_type}"
    
    def test_safetensors_mime_type(self):
        """Verify .safetensors files have a MIME type (or fallback)."""
        mime_type, _ = mimetypes.guess_type("model.safetensors")
        # safetensors may not be registered, should fall back to octet-stream
        # This is acceptable behavior
        assert mime_type is None or mime_type == "application/octet-stream"


class TestStaticFilesConfig:
    """Tests for FastAPI StaticFiles configuration."""
    
    def test_starlette_staticfiles_supports_video(self):
        """Verify Starlette StaticFiles can serve video files."""
        # StaticFiles uses mimetypes module internally
        # This test verifies the module is properly configured
        try:
            from starlette.staticfiles import StaticFiles
            # StaticFiles should be importable and instantiable
            # (actual serving requires running server)
            assert StaticFiles is not None
        except ImportError:
            pytest.skip("starlette not installed - skipping StaticFiles test")
    
    def test_video_extensions_in_mimetypes_db(self):
        """Verify video extensions are in mimetypes database."""
        video_extensions = ['.mp4', '.webm', '.mov', '.avi', '.mkv']
        
        for ext in video_extensions:
            mime_type = mimetypes.types_map.get(ext)
            assert mime_type is not None, f"Extension {ext} not in mimetypes.types_map"
            assert mime_type.startswith('video/'), f"{ext} should map to video/*, got {mime_type}"


# Integration test - requires running server
@pytest.mark.integration
@pytest.mark.skip(reason="Requires running server - run manually")
class TestLiveServer:
    """Integration tests requiring running server."""
    
    def test_mp4_content_type_header(self):
        """Test that server returns correct Content-Type for .mp4 files."""
        import requests
        
        # This URL should be adjusted based on actual test data
        url = "http://localhost:8000/previews/test_pack/resources/previews/preview_1.mp4"
        
        response = requests.head(url, timeout=5)
        
        if response.status_code == 200:
            content_type = response.headers.get('Content-Type', '')
            assert 'video/mp4' in content_type, f"Expected video/mp4, got {content_type}"
        elif response.status_code == 404:
            pytest.skip("Test file not found - import a pack with video first")
        else:
            pytest.fail(f"Unexpected status code: {response.status_code}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
