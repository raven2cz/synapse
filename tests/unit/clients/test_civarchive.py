
import pytest
from unittest.mock import MagicMock, patch
from apps.api.src.routers.browse import (
    _extract_civitai_id_from_civarchive,
    _fetch_civitai_model_for_civarchive,
    CivArchiveResult
)

# Sample HTML with __NEXT_DATA__
SAMPLE_HTML_NEXT_DATA = """
<html>
<body>
<script id="__NEXT_DATA__" type="application/json">
{
  "props": {
    "pageProps": {
      "model": {
        "id": 123,
        "civitai_model_id": "456",
        "name": "Test Model",
        "version": {
          "id": 789,
          "civitai_model_id": "1001"
        }
      }
    }
  }
}
</script>
</body>
</html>
"""

# Sample HTML with fallback link
SAMPLE_HTML_FALLBACK = """
<html>
<body>
<a href="https://civitai.com/models/9999">Link to Civitai</a>
</body>
</html>
"""

def test_extract_civitai_id_primary():
    """Test extraction from __NEXT_DATA__ (primary path)."""
    with patch("requests.Session") as mock_session_class:
        mock_resp = MagicMock()
        mock_resp.text = SAMPLE_HTML_NEXT_DATA
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()

        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        mock_session.headers = MagicMock()
        mock_session_class.return_value = mock_session

        # Should prefer version.civitai_model_id if present
        model_id = _extract_civitai_id_from_civarchive("http://example.com")
        assert model_id == 1001

def test_extract_civitai_id_fallback():
    """Test extraction from Civitai link in HTML."""
    with patch("requests.Session") as mock_session_class:
        mock_resp = MagicMock()
        mock_resp.text = SAMPLE_HTML_FALLBACK
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()

        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        mock_session.headers = MagicMock()
        mock_session_class.return_value = mock_session

        model_id = _extract_civitai_id_from_civarchive("http://example.com")
        assert model_id == 9999

def test_fetch_civitai_model_video_detection():
    """Test that videos are correctly detected as media_type='video'."""
    client = MagicMock()
    
    # Mock Civitai model response with a video
    client.get_model.return_value = {
        "id": 123,
        "name": "Video Model",
        "type": "Checkpoint",
        "nsfw": False,
        "modelVersions": [{
            "id": 10,
            "name": "v1.0",
            "baseModel": "SDXL",
            "downloadUrl": "http://download",
            "files": [{"primary": True, "name": "model.safetensors", "sizeKB": 1024}],
            "images": [
                {
                    "url": "http://image.civitai.com/video.mp4",
                    "nsfwLevel": 1,
                    "width": 1024,
                    "height": 1024
                },
                {
                    "url": "http://image.civitai.com/image.jpg",
                    "nsfwLevel": 1,
                    "width": 512,
                    "height": 512
                }
            ]
        }],
        "stats": {"downloadCount": 100}
    }
    
    # Mock media detection
    with patch("apps.api.src.routers.browse.detect_media_type") as mock_detect:
        # First call is video, second is image
        mock_video = MagicMock()
        mock_video.type.value = "video"
        
        mock_image = MagicMock()
        mock_image.type.value = "image"
        
        mock_detect.side_effect = [mock_video, mock_image]
        
        with patch("apps.api.src.routers.browse.get_video_thumbnail_url") as mock_thumb:
            mock_thumb.return_value = "http://thumb.jpg"
            
            result = _fetch_civitai_model_for_civarchive(123, "http://civarchive", client)
            
            assert result is not None
            assert len(result.previews) == 2
            
            # Check first preview (video)
            assert result.previews[0].media_type == "video"
            assert result.previews[0].thumbnail_url == "http://thumb.jpg"
            
            # Check second preview (image)
            assert result.previews[1].media_type == "image"
            assert result.previews[1].thumbnail_url is None
