"""
Tests for Import Wizard API and Frontend Integration.

Run with: pytest tests/test_import_wizard.py -v
"""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


class TestImportWizardURLParsing:
    """Tests for Civitai URL parsing."""
    
    def test_parse_basic_model_url(self):
        """Parse basic model URL."""
        from src.api.IMPORT_WIZARD_ENDPOINTS import parse_civitai_url
        
        assert parse_civitai_url("https://civitai.com/models/12345") == 12345
        assert parse_civitai_url("https://civitai.com/models/12345/model-name") == 12345
        assert parse_civitai_url("https://civitai.com/models/12345?modelVersionId=67890") == 12345
    
    def test_parse_invalid_url(self):
        """Invalid URLs return None."""
        from src.api.IMPORT_WIZARD_ENDPOINTS import parse_civitai_url
        
        assert parse_civitai_url("https://example.com/models/123") is None
        assert parse_civitai_url("not-a-url") is None
        assert parse_civitai_url("") is None


class TestFileSizeFormatting:
    """Tests for file size formatting."""
    
    def test_format_bytes(self):
        """Format various byte sizes."""
        from src.api.IMPORT_WIZARD_ENDPOINTS import format_file_size
        
        assert format_file_size(500) == "500 B"
        assert format_file_size(2048) == "2.0 KB"
        assert format_file_size(5 * 1024 * 1024) == "5.0 MB"
        assert format_file_size(2 * 1024 * 1024 * 1024) == "2.00 GB"


class TestVideoDetection:
    """Tests for video URL detection."""
    
    def test_detect_video_extensions(self):
        """Detect video by extension."""
        from src.api.IMPORT_WIZARD_ENDPOINTS import detect_video_url
        
        assert detect_video_url("https://example.com/video.mp4") is True
        assert detect_video_url("https://example.com/video.webm") is True
        assert detect_video_url("https://example.com/image.jpg") is False
        assert detect_video_url("https://example.com/image.png") is False
    
    def test_detect_video_transcode(self):
        """Detect video by transcode parameter."""
        from src.api.IMPORT_WIZARD_ENDPOINTS import detect_video_url
        
        assert detect_video_url("https://example.com/media?transcode=true") is True
        assert detect_video_url("https://example.com/media?transcode=true&anim=false") is False


class TestWizardModels:
    """Tests for Pydantic models."""
    
    def test_wizard_import_request(self):
        """Test WizardImportRequest model."""
        from src.api.IMPORT_WIZARD_ENDPOINTS import WizardImportRequest
        
        # Minimal request
        req = WizardImportRequest(url="https://civitai.com/models/123")
        assert req.url == "https://civitai.com/models/123"
        assert req.download_images is True
        assert req.download_videos is True
        assert req.include_nsfw is True
        
        # Full request
        req = WizardImportRequest(
            url="https://civitai.com/models/123",
            version_ids=[456, 789],
            download_images=True,
            download_videos=False,
            include_nsfw=False,
            thumbnail_url="https://img.jpg",
        )
        assert req.version_ids == [456, 789]
        assert req.download_videos is False
    
    def test_wizard_import_response(self):
        """Test WizardImportResponse model."""
        from src.api.IMPORT_WIZARD_ENDPOINTS import WizardImportResponse
        
        # Success
        resp = WizardImportResponse(
            success=True,
            pack_name="test-pack",
            message="Success",
        )
        assert resp.success is True
        
        # Failure
        resp = WizardImportResponse(
            success=False,
            errors=["Error 1", "Error 2"],
            message="Failed",
        )
        assert resp.success is False
        assert len(resp.errors) == 2


class TestImportPreviewResponse:
    """Tests for ImportPreviewResponse model."""
    
    def test_preview_response_structure(self):
        """Test response has all required fields."""
        from src.api.IMPORT_WIZARD_ENDPOINTS import ImportPreviewResponse, WizardVersionInfo
        
        resp = ImportPreviewResponse(
            model_id=12345,
            model_name="Test Model",
            creator="testuser",
            model_type="LORA",
            versions=[
                WizardVersionInfo(
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


class TestFrontendIntegration:
    """Tests for frontend integration."""
    
    def test_import_wizard_modal_exists(self):
        """Check ImportWizardModal.tsx exists in the package."""
        modal_path = Path(__file__).parent.parent / "apps" / "web" / "src" / "components" / "ui" / "ImportWizardModal.tsx"
        
        # Note: This test checks the package structure
        # In actual project, this file should exist after installation
        # We skip if file doesn't exist (not installed yet)
        if not modal_path.exists():
            pytest.skip("ImportWizardModal.tsx not installed yet")
        
        content = modal_path.read_text()
        
        # Check key exports
        assert "export interface ImportWizardModalProps" in content
        assert "export interface ModelVersion" in content
        assert "export interface ImportOptions" in content
        assert "export default ImportWizardModal" in content
    
    def test_browse_page_patch_instructions(self):
        """Check BrowsePage patch file has instructions."""
        patch_path = Path(__file__).parent.parent / "apps" / "web" / "src" / "components" / "modules" / "BROWSE_PAGE_PATCH.tsx"
        
        if not patch_path.exists():
            pytest.skip("Patch file not found")
        
        content = patch_path.read_text()
        
        # Check key sections
        assert "STEP 1:" in content
        assert "STEP 2:" in content
        assert "ImportWizardModal" in content
        assert "openImportWizard" in content


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
        # Note: Requires actual Civitai API call
        # Use mock in CI
        response = client.get(
            "/api/packs/import/preview",
            params={"url": "https://civitai.com/models/12345"}
        )
        
        # Should return 200 or 404 (model not found)
        assert response.status_code in [200, 404]
        
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
        assert response.status_code in [200, 400, 404]
        
        data = response.json()
        assert "success" in data or "detail" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
