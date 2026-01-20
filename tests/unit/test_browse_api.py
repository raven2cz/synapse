"""
Tests for Browse API - URL integrity verification.

These tests ensure that preview URLs from Civitai API are passed through
correctly without truncation or corruption.
"""

import pytest
from unittest.mock import MagicMock, patch
import re


# ============================================================================
# Mock Civitai API responses with real URL patterns
# ============================================================================

MOCK_CIVITAI_IMAGE_URL = "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/8af8c0e7-2f7a-4c4d-8e7f-1234567890ab/width=450/image.jpeg"
MOCK_CIVITAI_VIDEO_URL = "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/9bf9d1f8-3a8b-5d5e-9f8a-234567890abc/anim=true,transcode=true/video.jpeg"

MOCK_MODEL_DATA = {
    "id": 12345,
    "name": "Test Model",
    "description": "A test model for URL integrity verification",
    "type": "LORA",
    "nsfw": False,
    "tags": ["test", "lora"],
    "creator": {"username": "testuser"},
    "stats": {
        "downloadCount": 1000,
        "favoriteCount": 100,
        "rating": 4.5,
        "thumbsUpCount": 50,
    },
    "modelVersions": [
        {
            "id": 67890,
            "name": "v1.0",
            "baseModel": "SDXL 1.0",
            "trainedWords": ["trigger"],
            "publishedAt": "2024-01-01T00:00:00Z",
            "files": [
                {
                    "id": 111,
                    "name": "model.safetensors",
                    "sizeKB": 1024000,
                    "downloadUrl": "https://civitai.com/api/download/models/67890",
                    "hashes": {
                        "AutoV2": "ABC123DEF0",
                        "SHA256": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
                    },
                }
            ],
            "images": [
                {
                    "url": MOCK_CIVITAI_IMAGE_URL,
                    "nsfw": False,
                    "nsfwLevel": 1,
                    "width": 1024,
                    "height": 1536,
                    "meta": {
                        "prompt": "masterpiece, best quality, test prompt",
                        "negativePrompt": "bad quality",
                        "sampler": "Euler a",
                        "cfgScale": 7,
                        "steps": 30,
                        "seed": 12345,
                    },
                },
                {
                    "url": MOCK_CIVITAI_VIDEO_URL,
                    "nsfw": False,
                    "nsfwLevel": 1,
                    "width": 512,
                    "height": 768,
                    "meta": {
                        "prompt": "video test prompt",
                    },
                },
            ],
        }
    ],
}


MOCK_SEARCH_RESPONSE = {
    "items": [MOCK_MODEL_DATA],
    "metadata": {
        "totalItems": 1,
        "currentPage": 1,
        "pageSize": 20,
        "totalPages": 1,
        "nextCursor": None,
    },
}


# ============================================================================
# URL Integrity Tests
# ============================================================================

def test_civitai_url_pattern_integrity():
    """Verify our mock URLs match real Civitai URL patterns."""
    # Real Civitai URLs contain UUID-like patterns
    uuid_pattern = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"

    assert re.search(uuid_pattern, MOCK_CIVITAI_IMAGE_URL), "Mock image URL should contain UUID"
    assert re.search(uuid_pattern, MOCK_CIVITAI_VIDEO_URL), "Mock video URL should contain UUID"

    # URLs should be complete (not truncated)
    assert len(MOCK_CIVITAI_IMAGE_URL) > 80, "Image URL should be substantial length"
    assert len(MOCK_CIVITAI_VIDEO_URL) > 80, "Video URL should be substantial length"


def test_model_preview_url_not_truncated():
    """Test that create_model_preview preserves full URL."""
    # Import the function we're testing
    import sys
    from pathlib import Path

    # Add project root to path
    project_root = Path(__file__).parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from apps.api.src.routers.browse import create_model_preview

    img_data = {
        "url": MOCK_CIVITAI_IMAGE_URL,
        "nsfw": False,
        "nsfwLevel": 1,
        "width": 1024,
        "height": 1536,
    }

    preview = create_model_preview(img_data)

    # URL should be preserved exactly
    assert preview.url == MOCK_CIVITAI_IMAGE_URL, f"URL was modified: {preview.url}"
    assert len(preview.url) == len(MOCK_CIVITAI_IMAGE_URL), "URL length changed"

    # Check for common truncation patterns
    assert not preview.url.endswith("/8"), "URL appears truncated (ends with /8)"
    assert "image.jpeg" in preview.url, "URL missing filename"


def test_model_preview_video_url_not_truncated():
    """Test that video URLs are preserved correctly."""
    import sys
    from pathlib import Path

    project_root = Path(__file__).parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from apps.api.src.routers.browse import create_model_preview

    img_data = {
        "url": MOCK_CIVITAI_VIDEO_URL,
        "nsfw": False,
        "nsfwLevel": 1,
        "width": 512,
        "height": 768,
    }

    preview = create_model_preview(img_data)

    # URL should be preserved
    assert preview.url == MOCK_CIVITAI_VIDEO_URL, f"URL was modified: {preview.url}"

    # Media type should be detected
    assert preview.media_type in ["video", "image"], f"Invalid media_type: {preview.media_type}"

    # Thumbnail URL should also be present for videos
    if preview.media_type == "video":
        assert preview.thumbnail_url is not None, "Video should have thumbnail URL"


def test_convert_model_to_result_preserves_urls():
    """Test that _convert_model_to_result preserves all preview URLs."""
    import sys
    from pathlib import Path

    project_root = Path(__file__).parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from apps.api.src.routers.browse import _convert_model_to_result

    result = _convert_model_to_result(MOCK_MODEL_DATA)

    assert result is not None, "Result should not be None"
    assert len(result.previews) > 0, "Should have previews"

    # Check each preview URL
    for i, preview in enumerate(result.previews):
        assert preview.url, f"Preview {i} has empty URL"
        assert len(preview.url) > 50, f"Preview {i} URL appears truncated: {preview.url}"

        # Check for truncation pattern: URL ending with just a few characters after /
        if "image.civitai.com" in preview.url:
            parts = preview.url.split("/")
            last_part = parts[-1].split("?")[0]  # Get filename before any query params
            assert len(last_part) > 5, f"Preview {i} URL filename appears truncated: {last_part}"


def test_search_results_url_integrity():
    """Test that search endpoint returns complete URLs (mock test)."""
    import sys
    from pathlib import Path

    project_root = Path(__file__).parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from apps.api.src.routers.browse import _convert_model_to_result

    # Simulate processing search results
    for model_data in MOCK_SEARCH_RESPONSE["items"]:
        result = _convert_model_to_result(model_data)

        if result and result.previews:
            for preview in result.previews:
                # URL should be complete
                assert preview.url, "Preview URL should not be empty"

                # Check it's a valid civitai URL
                if "civitai.com" in preview.url:
                    # Should contain UUID pattern
                    uuid_pattern = r"[0-9a-f]{8}-[0-9a-f]{4}"
                    assert re.search(uuid_pattern, preview.url), f"URL missing UUID: {preview.url}"


def test_url_not_truncated_after_serialization():
    """Test that URLs survive Pydantic model serialization."""
    import sys
    from pathlib import Path

    project_root = Path(__file__).parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from apps.api.src.routers.browse import ModelPreview

    # Create a preview with full URL
    preview = ModelPreview(
        url=MOCK_CIVITAI_IMAGE_URL,
        nsfw=False,
        width=1024,
        height=1536,
        media_type="image",
    )

    # Serialize to dict
    preview_dict = preview.model_dump()

    # URL should be preserved
    assert preview_dict["url"] == MOCK_CIVITAI_IMAGE_URL

    # Serialize to JSON and back
    import json
    json_str = json.dumps(preview_dict)
    parsed = json.loads(json_str)

    assert parsed["url"] == MOCK_CIVITAI_IMAGE_URL, "URL changed after JSON roundtrip"


# ============================================================================
# CivArchive URL Tests
# ============================================================================

def test_civarchive_result_preserves_preview_urls():
    """Test that CivArchive results also preserve preview URLs."""
    import sys
    from pathlib import Path

    project_root = Path(__file__).parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from apps.api.src.routers.browse import CivArchiveResult, ModelPreview

    # Create CivArchive result with previews
    previews = [
        ModelPreview(
            url=MOCK_CIVITAI_IMAGE_URL,
            nsfw=False,
            media_type="image",
        ),
        ModelPreview(
            url=MOCK_CIVITAI_VIDEO_URL,
            nsfw=False,
            media_type="video",
        ),
    ]

    result = CivArchiveResult(
        model_id=12345,
        model_name="Test Model",
        previews=previews,
    )

    # Check URLs are preserved
    assert len(result.previews) == 2
    assert result.previews[0].url == MOCK_CIVITAI_IMAGE_URL
    assert result.previews[1].url == MOCK_CIVITAI_VIDEO_URL

    # Serialize and verify
    result_dict = result.model_dump()
    assert result_dict["previews"][0]["url"] == MOCK_CIVITAI_IMAGE_URL


# ============================================================================
# Integration test with mocked Civitai client
# ============================================================================

def test_search_endpoint_url_integrity():
    """Integration test for search endpoint URL handling.

    Tests that _convert_model_to_result correctly preserves URLs when
    processing search results - this is the core function called by the endpoint.
    """
    import sys
    from pathlib import Path

    project_root = Path(__file__).parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from apps.api.src.routers.browse import _convert_model_to_result

    # Process mock search results through the same function the endpoint uses
    for model_data in MOCK_SEARCH_RESPONSE["items"]:
        result = _convert_model_to_result(model_data)

        assert result is not None, "Result should not be None"
        assert len(result.previews) > 0, "Should have previews"

        for preview in result.previews:
            assert preview.url, "Preview URL should not be empty"
            assert len(preview.url) > 50, f"URL appears truncated: {preview.url}"

            # Should be a complete civitai URL
            if "civitai.com" in preview.url:
                assert re.search(r"[0-9a-f]{8}", preview.url), f"URL missing UUID: {preview.url}"


def test_get_model_endpoint_url_integrity():
    """Integration test for model detail endpoint URL handling."""
    import asyncio
    import sys
    from pathlib import Path

    project_root = Path(__file__).parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    mock_client = MagicMock()
    mock_client.get_model.return_value = MOCK_MODEL_DATA

    mock_config = MagicMock()
    mock_config.api.civitai_token = "test_token"

    with patch("apps.api.src.routers.browse.get_config", return_value=mock_config), \
         patch("apps.api.src.routers.browse.CivitaiClient", return_value=mock_client):

        from apps.api.src.routers.browse import get_model

        result = asyncio.get_event_loop().run_until_complete(get_model(model_id=12345))

        assert len(result.previews) > 0, "Should have previews"

        for preview in result.previews:
            assert preview.url, "Preview URL should not be empty"
            assert len(preview.url) > 50, f"URL appears truncated: {preview.url}"


# ============================================================================
# Regression tests for specific bug patterns
# ============================================================================

def test_url_not_truncated_at_uuid_start():
    """
    Regression test for bug where URLs were truncated after first UUID character.

    Bug pattern: https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/8
    Should be:   https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/8af8c0e7-2f7a-4c4d-8e7f-1234567890ab/...
    """
    import sys
    from pathlib import Path

    project_root = Path(__file__).parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from apps.api.src.routers.browse import create_model_preview

    # Test various URL patterns that could trigger truncation
    test_urls = [
        "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/8af8c0e7-2f7a-4c4d-8e7f-1234567890ab/width=450/image.jpeg",
        "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/a1234567-b234-c345-d456-e56789012345/original=true/preview.png",
        "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/00000000-0000-0000-0000-000000000000/anim=true/video.jpeg",
    ]

    for url in test_urls:
        preview = create_model_preview({"url": url, "nsfw": False})

        # URL should be completely preserved
        assert preview.url == url, f"URL was modified from {url} to {preview.url}"

        # Check for truncation at UUID boundary
        if "/xG1nkqKTMzGDvpLrqFT7WA/" in preview.url:
            # Extract the part after the bucket ID
            parts = preview.url.split("/xG1nkqKTMzGDvpLrqFT7WA/")
            if len(parts) > 1:
                after_bucket = parts[1]
                # Should not be just a single character
                assert len(after_bucket) > 10, f"URL truncated after bucket ID: {preview.url}"


def test_empty_url_handled_gracefully():
    """Test that empty URLs don't cause errors."""
    import sys
    from pathlib import Path

    project_root = Path(__file__).parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from apps.api.src.routers.browse import create_model_preview

    preview = create_model_preview({"url": "", "nsfw": False})
    assert preview.url == ""

    preview = create_model_preview({"nsfw": False})
    assert preview.url == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
