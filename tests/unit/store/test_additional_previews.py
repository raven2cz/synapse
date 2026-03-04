"""
Tests for additional preview URL download (community gallery import).

Tests cover:
- _download_additional_previews handles valid URLs
- _download_additional_previews handles download failures gracefully
- Community previews get `community_` prefix filenames
- Import without additional_preview_urls works as before (backward compat)
- Import with additional_preview_urls downloads community images
- Import with empty additional_preview_urls list = no community downloads
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from pathlib import Path

from src.store.pack_service import PackService
from src.store.models import PreviewInfo


class FakeLayout:
    """Minimal fake layout for testing."""
    def __init__(self, tmp_path: Path):
        self.root = tmp_path
        self._packs_path = tmp_path / "state" / "packs"
        self._packs_path.mkdir(parents=True, exist_ok=True)

    def pack_previews_path(self, pack_name: str) -> Path:
        path = self._packs_path / pack_name / "resources" / "previews"
        return path


class TestDownloadAdditionalPreviews:
    """Tests for PackService._download_additional_previews method."""

    def _make_service(self, tmp_path, download_service=None):
        """Create a PackService with minimal dependencies."""
        layout = FakeLayout(tmp_path)
        service = PackService.__new__(PackService)
        service.layout = layout
        service._download_service = download_service
        return service

    def test_downloads_image_urls(self, tmp_path):
        """Test that image URLs are downloaded with community_ prefix."""
        mock_ds = MagicMock()
        service = self._make_service(tmp_path, download_service=mock_ds)

        urls = [
            "https://example.com/image1.jpg",
            "https://example.com/image2.png",
        ]

        results = service._download_additional_previews(
            pack_name="test-pack",
            urls=urls,
            start_index=0,
        )

        assert len(results) == 2
        assert results[0].filename == "community_1.jpg"
        assert results[1].filename == "community_2.png"
        assert results[0].url == urls[0]
        assert results[1].url == urls[1]
        assert mock_ds.download_to_file.call_count == 2

    def test_community_prefix_with_start_index(self, tmp_path):
        """Test that start_index offsets filenames correctly."""
        mock_ds = MagicMock()
        service = self._make_service(tmp_path, download_service=mock_ds)

        urls = ["https://example.com/image.jpg"]

        results = service._download_additional_previews(
            pack_name="test-pack",
            urls=urls,
            start_index=5,
        )

        assert len(results) == 1
        assert results[0].filename == "community_6.jpg"

    def test_handles_download_failure_gracefully(self, tmp_path):
        """Test that failed downloads are skipped without failing the whole batch."""
        mock_ds = MagicMock()
        mock_ds.download_to_file.side_effect = [
            None,  # First succeeds
            Exception("Network error"),  # Second fails
            None,  # Third succeeds
        ]
        service = self._make_service(tmp_path, download_service=mock_ds)

        urls = [
            "https://example.com/ok1.jpg",
            "https://example.com/fail.jpg",
            "https://example.com/ok2.jpg",
        ]

        results = service._download_additional_previews(
            pack_name="test-pack",
            urls=urls,
        )

        assert len(results) == 2
        assert results[0].filename == "community_1.jpg"
        assert results[1].filename == "community_3.jpg"

    def test_empty_urls_returns_empty(self, tmp_path):
        """Test that empty URL list returns empty results."""
        service = self._make_service(tmp_path)

        results = service._download_additional_previews(
            pack_name="test-pack",
            urls=[],
        )

        assert results == []

    def test_skips_empty_url_strings(self, tmp_path):
        """Test that empty strings in URL list are skipped."""
        mock_ds = MagicMock()
        service = self._make_service(tmp_path, download_service=mock_ds)

        urls = ["", "https://example.com/image.jpg", ""]

        results = service._download_additional_previews(
            pack_name="test-pack",
            urls=urls,
        )

        assert len(results) == 1
        assert results[0].filename == "community_2.jpg"

    def test_video_url_gets_mp4_extension(self, tmp_path):
        """Test that video URLs are saved with .mp4 extension."""
        mock_ds = MagicMock()
        service = self._make_service(tmp_path, download_service=mock_ds)

        urls = ["https://image.civitai.com/preview.mp4?transcode=true"]

        results = service._download_additional_previews(
            pack_name="test-pack",
            urls=urls,
        )

        assert len(results) == 1
        assert results[0].filename == "community_1.mp4"
        assert results[0].media_type == "video"
        assert results[0].thumbnail_url is not None

    def test_creates_previews_directory(self, tmp_path):
        """Test that previews directory is created if it doesn't exist."""
        mock_ds = MagicMock()
        service = self._make_service(tmp_path, download_service=mock_ds)

        urls = ["https://example.com/image.jpg"]
        service._download_additional_previews(pack_name="new-pack", urls=urls)

        previews_dir = tmp_path / "state" / "packs" / "new-pack" / "resources" / "previews"
        assert previews_dir.exists()

    def test_nsfw_defaults_to_false(self, tmp_path):
        """Test that community previews default to nsfw=False."""
        mock_ds = MagicMock()
        service = self._make_service(tmp_path, download_service=mock_ds)

        urls = ["https://example.com/image.jpg"]
        results = service._download_additional_previews(
            pack_name="test-pack", urls=urls
        )

        assert results[0].nsfw is False

    def test_fallback_to_requests_when_no_download_service(self, tmp_path):
        """Test direct download when DownloadService is not available."""
        service = self._make_service(tmp_path, download_service=None)

        urls = ["https://example.com/image.jpg"]

        with patch("src.store.pack_service.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.iter_content.return_value = [b"fake image data"]
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            results = service._download_additional_previews(
                pack_name="test-pack", urls=urls
            )

        assert len(results) == 1
        mock_get.assert_called_once()


class TestImportRequestAdditionalUrls:
    """Tests for ImportRequest model with additional_preview_urls."""

    def test_import_request_without_additional_urls(self):
        """Test backward compat: additional_preview_urls defaults to None."""
        from src.store.api import ImportRequest
        req = ImportRequest(url="https://civitai.com/models/123")
        assert req.additional_preview_urls is None

    def test_import_request_with_additional_urls(self):
        """Test that additional_preview_urls accepts a list of strings."""
        from src.store.api import ImportRequest
        urls = ["https://example.com/a.jpg", "https://example.com/b.jpg"]
        req = ImportRequest(url="https://civitai.com/models/123", additional_preview_urls=urls)
        assert req.additional_preview_urls == urls

    def test_import_request_with_empty_additional_urls(self):
        """Test that empty list is accepted."""
        from src.store.api import ImportRequest
        req = ImportRequest(url="https://civitai.com/models/123", additional_preview_urls=[])
        assert req.additional_preview_urls == []

    def test_import_request_rejects_too_many_urls(self):
        """Test that more than 100 URLs are rejected."""
        from src.store.api import ImportRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ImportRequest(url="https://civitai.com/models/123", additional_preview_urls=["x"] * 101)
