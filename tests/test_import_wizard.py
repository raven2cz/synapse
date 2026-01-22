"""
Tests for Import Wizard API and Frontend Integration.

Tests cover:
- Utility functions (format_file_size, video detection)
- API models (ImportRequest, ImportResponse, ImportPreviewResponse)
- Frontend component existence
- API endpoint integration

Run with: pytest tests/test_import_wizard.py -v
"""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


# =============================================================================
# Utility Function Tests
# =============================================================================

class TestFileSizeFormatting:
    """Tests for file size formatting utility."""

    def test_format_bytes(self):
        """Format various byte sizes to human readable strings."""
        from src.utils.media_detection import format_file_size

        assert format_file_size(500) == "500 B"
        assert format_file_size(2048) == "2.0 KB"
        assert format_file_size(5 * 1024 * 1024) == "5.0 MB"
        assert format_file_size(2 * 1024 * 1024 * 1024) == "2.00 GB"

    def test_format_edge_cases(self):
        """Test edge cases for file size formatting."""
        from src.utils.media_detection import format_file_size

        assert format_file_size(0) == "0 B"
        assert format_file_size(1023) == "1023 B"
        assert format_file_size(1024) == "1.0 KB"


class TestVideoDetection:
    """Tests for video URL detection using is_video_url."""

    def test_detect_video_extensions(self):
        """Detect video by extension."""
        from src.utils.media_detection import is_video_url

        assert is_video_url("https://example.com/video.mp4") is True
        assert is_video_url("https://example.com/video.webm") is True
        assert is_video_url("https://example.com/video.mov") is True
        assert is_video_url("https://example.com/image.jpg") is False
        assert is_video_url("https://example.com/image.png") is False

    def test_detect_video_transcode(self):
        """Detect video by transcode parameter (Civitai pattern)."""
        from src.utils.media_detection import is_video_url

        # transcode=true indicates video on Civitai
        assert is_video_url("https://image.civitai.com/media.jpeg?transcode=true") is True


# =============================================================================
# API Model Tests
# =============================================================================

class TestImportRequestModel:
    """Tests for ImportRequest Pydantic model."""

    def test_minimal_request(self):
        """Test ImportRequest with minimal required fields."""
        from src.store.api import ImportRequest

        req = ImportRequest(url="https://civitai.com/models/123")
        assert req.url == "https://civitai.com/models/123"
        assert req.download_images is True
        assert req.download_videos is True
        assert req.include_nsfw is True

    def test_full_request(self):
        """Test ImportRequest with all wizard options."""
        from src.store.api import ImportRequest

        req = ImportRequest(
            url="https://civitai.com/models/123",
            version_ids=[456, 789],
            download_images=True,
            download_videos=False,
            include_nsfw=False,
            thumbnail_url="https://img.jpg",
            pack_name="custom-pack",
            download_from_all_versions=True,
        )
        assert req.version_ids == [456, 789]
        assert req.download_videos is False
        assert req.include_nsfw is False
        assert req.thumbnail_url == "https://img.jpg"
        assert req.pack_name == "custom-pack"


class TestImportResponseModel:
    """Tests for ImportResponse Pydantic model."""

    def test_success_response(self):
        """Test successful import response."""
        from src.store.api import ImportResponse

        resp = ImportResponse(
            success=True,
            pack_name="test-pack",
            pack_type="LORA",
            dependencies_count=3,
            previews_downloaded=10,
            message="Successfully imported",
        )
        assert resp.success is True
        assert resp.pack_name == "test-pack"
        assert resp.pack_type == "LORA"
        assert resp.dependencies_count == 3

    def test_response_with_videos(self):
        """Test response with video download count."""
        from src.store.api import ImportResponse

        resp = ImportResponse(
            success=True,
            pack_name="test-pack",
            pack_type="Checkpoint",
            dependencies_count=1,
            previews_downloaded=5,
            videos_downloaded=2,
        )
        assert resp.videos_downloaded == 2


class TestImportPreviewResponse:
    """Tests for ImportPreviewResponse model."""

    def test_preview_response_structure(self):
        """Test response has all required fields."""
        from src.store.api import ImportPreviewResponse, VersionPreviewInfo

        resp = ImportPreviewResponse(
            model_id=12345,
            model_name="Test Model",
            creator="testuser",
            model_type="LORA",
            versions=[
                VersionPreviewInfo(
                    id=1,
                    name="v1.0",
                    base_model="SDXL 1.0",
                    files=[],
                )
            ],
        )

        assert resp.model_id == 12345
        assert resp.model_name == "Test Model"
        assert len(resp.versions) == 1
        assert resp.versions[0].base_model == "SDXL 1.0"


# =============================================================================
# Civitai URL Parsing Tests
# =============================================================================

class TestCivitaiURLParsing:
    """Tests for Civitai URL parsing in CivitaiClient."""

    def test_parse_basic_model_url(self):
        """Parse basic model URL."""
        from src.clients.civitai_client import CivitaiClient

        client = CivitaiClient()

        # Basic URL
        model_id, version_id = client.parse_civitai_url("https://civitai.com/models/12345")
        assert model_id == 12345
        assert version_id is None

        # URL with model name slug
        model_id, version_id = client.parse_civitai_url("https://civitai.com/models/12345/model-name")
        assert model_id == 12345

        # URL with version parameter
        model_id, version_id = client.parse_civitai_url("https://civitai.com/models/12345?modelVersionId=67890")
        assert model_id == 12345
        assert version_id == 67890

    def test_parse_invalid_url(self):
        """Invalid URLs should raise ValueError."""
        from src.clients.civitai_client import CivitaiClient

        client = CivitaiClient()

        # URLs without /models/\d+ pattern should raise ValueError
        with pytest.raises(ValueError):
            client.parse_civitai_url("https://civitai.com/images/123")  # wrong path

        with pytest.raises(ValueError):
            client.parse_civitai_url("not-a-url")  # not a URL

        with pytest.raises(ValueError):
            client.parse_civitai_url("")  # empty string

        with pytest.raises(ValueError):
            client.parse_civitai_url("https://civitai.com/")  # no model path


# =============================================================================
# Frontend Integration Tests
# =============================================================================

class TestFrontendIntegration:
    """Tests for frontend component integration."""

    def test_import_wizard_modal_exists(self):
        """Check ImportWizardModal.tsx exists."""
        modal_path = Path(__file__).parent.parent / "apps" / "web" / "src" / "components" / "ui" / "ImportWizardModal.tsx"

        if not modal_path.exists():
            pytest.skip("ImportWizardModal.tsx not found")

        content = modal_path.read_text()

        # Check key exports
        assert "ImportWizardModal" in content
        assert "ModelVersion" in content or "version" in content.lower()


# =============================================================================
# API Endpoint Integration Tests
# =============================================================================

@pytest.mark.integration
class TestEndpointIntegration:
    """Integration tests requiring running server."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from fastapi.testclient import TestClient
        from apps.api.src.main import app
        return TestClient(app)

    def test_import_preview_endpoint(self, client):
        """Test GET /api/packs/import/preview endpoint."""
        response = client.get(
            "/api/packs/import/preview",
            params={"url": "https://civitai.com/models/12345"}
        )

        # Should return 200 or 404 (model not found) or 500 (API error)
        assert response.status_code in [200, 404, 500]

        if response.status_code == 200:
            data = response.json()
            assert "model_id" in data
            assert "versions" in data

    def test_import_endpoint_with_wizard_params(self, client):
        """Test POST /api/packs/import with wizard params."""
        response = client.post(
            "/api/packs/import",
            json={
                "url": "https://civitai.com/models/12345",
                "version_ids": [67890],
                "download_images": True,
                "download_videos": False,
                "include_nsfw": False,
            }
        )

        # Should return success or error (not crash)
        assert response.status_code in [200, 400, 404, 500]

        data = response.json()
        assert "success" in data or "detail" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
