"""
Tests for Import API Models.

Tests cover:
- ImportRequest validation and defaults
- ImportPreviewRequest validation
- ImportPreviewResponse structure
- ImportResult structure
- format_file_size utility

Author: Synapse Team
License: MIT
"""

import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from api.import_models import (
    ImportRequest,
    ImportPreviewRequest,
    ImportPreviewResponse,
    ImportResult,
    VersionPreviewInfo,
    format_file_size,
)


# =============================================================================
# ImportRequest Tests
# =============================================================================

class TestImportRequest:
    """Tests for ImportRequest model."""
    
    def test_minimal_request(self):
        """Test creating request with only required field."""
        request = ImportRequest(url="https://civitai.com/models/12345")
        
        assert request.url == "https://civitai.com/models/12345"
        assert request.version_ids is None
        assert request.download_images is True
        assert request.download_videos is True
        assert request.include_nsfw is True
    
    def test_full_request(self):
        """Test creating request with all fields."""
        request = ImportRequest(
            url="https://civitai.com/models/12345",
            version_ids=[67890, 67891],
            download_images=True,
            download_videos=False,
            include_nsfw=False,
            thumbnail_url="https://example.com/thumb.jpg",
            pack_name="My Custom Pack",
            pack_description="A great pack",
            add_to_global=False,
        )
        
        assert request.url == "https://civitai.com/models/12345"
        assert request.version_ids == [67890, 67891]
        assert request.download_videos is False
        assert request.include_nsfw is False
        assert request.pack_name == "My Custom Pack"
    
    def test_default_values(self):
        """Test that default values are correct."""
        request = ImportRequest(url="https://civitai.com/models/1")
        
        assert request.download_images is True
        assert request.download_videos is True
        assert request.include_nsfw is True
        assert request.download_previews is True  # Legacy
        assert request.add_to_global is True
        assert request.thumbnail_url is None
        assert request.pack_name is None
    
    def test_missing_url_raises(self):
        """Test that missing URL raises validation error."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            ImportRequest()


# =============================================================================
# ImportPreviewRequest Tests
# =============================================================================

class TestImportPreviewRequest:
    """Tests for ImportPreviewRequest model."""
    
    def test_minimal_preview_request(self):
        """Test creating preview request with only URL."""
        request = ImportPreviewRequest(url="https://civitai.com/models/12345")
        
        assert request.url == "https://civitai.com/models/12345"
        assert request.version_ids is None
    
    def test_preview_request_with_versions(self):
        """Test creating preview request with version IDs."""
        request = ImportPreviewRequest(
            url="https://civitai.com/models/12345",
            version_ids=[1, 2, 3],
        )
        
        assert request.version_ids == [1, 2, 3]


# =============================================================================
# ImportPreviewResponse Tests
# =============================================================================

class TestImportPreviewResponse:
    """Tests for ImportPreviewResponse model."""
    
    def test_empty_response(self):
        """Test creating empty preview response."""
        response = ImportPreviewResponse(
            model_id=12345,
            model_name="Test Model",
        )
        
        assert response.model_id == 12345
        assert response.model_name == "Test Model"
        assert response.versions == []
        assert response.total_size_bytes == 0
        assert response.total_size_formatted == "0 B"
    
    def test_full_response(self):
        """Test creating full preview response."""
        response = ImportPreviewResponse(
            model_id=12345,
            model_name="Test Model",
            creator="TestCreator",
            model_type="LORA",
            base_model="SDXL 1.0",
            versions=[
                VersionPreviewInfo(
                    id=1,
                    name="v1.0",
                    base_model="SDXL 1.0",
                    image_count=10,
                    video_count=2,
                    total_size_bytes=1024 * 1024 * 500,  # 500MB
                )
            ],
            total_size_bytes=1024 * 1024 * 500,
            total_size_formatted="500.0 MB",
            total_image_count=10,
            total_video_count=2,
        )
        
        assert len(response.versions) == 1
        assert response.versions[0].name == "v1.0"
        assert response.total_video_count == 2


# =============================================================================
# VersionPreviewInfo Tests
# =============================================================================

class TestVersionPreviewInfo:
    """Tests for VersionPreviewInfo model."""
    
    def test_version_info_defaults(self):
        """Test version info default values."""
        info = VersionPreviewInfo(id=1, name="v1.0")
        
        assert info.id == 1
        assert info.name == "v1.0"
        assert info.base_model is None
        assert info.files == []
        assert info.image_count == 0
        assert info.video_count == 0
        assert info.nsfw_count == 0


# =============================================================================
# ImportResult Tests
# =============================================================================

class TestImportResult:
    """Tests for ImportResult model."""
    
    def test_success_result(self):
        """Test successful import result."""
        result = ImportResult(
            success=True,
            pack_name="MyPack",
            message="Import successful",
            previews_downloaded=15,
            videos_downloaded=3,
        )
        
        assert result.success is True
        assert result.pack_name == "MyPack"
        assert result.previews_downloaded == 15
        assert result.videos_downloaded == 3
    
    def test_failure_result(self):
        """Test failed import result."""
        result = ImportResult(
            success=False,
            errors=["Network error", "Invalid URL"],
            message="Import failed",
        )
        
        assert result.success is False
        assert len(result.errors) == 2
        assert result.pack_name is None


# =============================================================================
# format_file_size Tests
# =============================================================================

class TestFormatFileSize:
    """Tests for format_file_size utility."""
    
    def test_bytes(self):
        """Test formatting bytes."""
        assert format_file_size(0) == "0 B"
        assert format_file_size(512) == "512 B"
        assert format_file_size(1023) == "1023 B"
    
    def test_kilobytes(self):
        """Test formatting kilobytes."""
        assert format_file_size(1024) == "1.0 KB"
        assert format_file_size(1536) == "1.5 KB"
        assert format_file_size(1024 * 500) == "500.0 KB"
    
    def test_megabytes(self):
        """Test formatting megabytes."""
        assert format_file_size(1024 * 1024) == "1.0 MB"
        assert format_file_size(1024 * 1024 * 256) == "256.0 MB"
    
    def test_gigabytes(self):
        """Test formatting gigabytes."""
        assert format_file_size(1024 * 1024 * 1024) == "1.00 GB"
        assert format_file_size(1024 * 1024 * 1024 * 2.5) == "2.50 GB"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
