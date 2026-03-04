"""
Tests for additional preview download (community gallery import).

Tests cover:
- _download_additional_previews handles {url, nsfw} dicts
- nsfw flags are correctly preserved from frontend
- Download failures are handled gracefully
- Community previews get `community_` prefix filenames
- Backward compat: plain string URLs default to nsfw=False
- Import with additional_previews downloads community images with nsfw metadata
"""

import pytest
from unittest.mock import MagicMock, patch
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

    def test_downloads_image_previews_with_nsfw(self, tmp_path):
        """Test that image previews are downloaded with nsfw flags preserved."""
        mock_ds = MagicMock()
        service = self._make_service(tmp_path, download_service=mock_ds)

        previews = [
            {"url": "https://example.com/image1.jpg", "nsfw": False},
            {"url": "https://example.com/image2.png", "nsfw": True},
        ]

        results = service._download_additional_previews(
            pack_name="test-pack",
            previews=previews,
            start_index=0,
        )

        assert len(results) == 2
        assert results[0].filename == "community_1.jpg"
        assert results[0].nsfw is False
        assert results[1].filename == "community_2.png"
        assert results[1].nsfw is True
        assert mock_ds.download_to_file.call_count == 2

    def test_nsfw_flag_preserved_from_frontend(self, tmp_path):
        """CRITICAL: nsfw flags from community gallery must survive the full pipeline."""
        mock_ds = MagicMock()
        service = self._make_service(tmp_path, download_service=mock_ds)

        previews = [
            {"url": "https://example.com/sfw.jpg", "nsfw": False},
            {"url": "https://example.com/nsfw.jpg", "nsfw": True},
            {"url": "https://example.com/also_nsfw.jpg", "nsfw": True},
        ]

        results = service._download_additional_previews(
            pack_name="test-pack", previews=previews
        )

        assert results[0].nsfw is False
        assert results[1].nsfw is True
        assert results[2].nsfw is True

    def test_metadata_preserved_from_frontend(self, tmp_path):
        """Generation metadata (width, height, meta) must survive the pipeline."""
        mock_ds = MagicMock()
        service = self._make_service(tmp_path, download_service=mock_ds)

        meta = {"prompt": "a cat", "seed": 12345, "model": "sdxl"}
        previews = [
            {"url": "https://example.com/img.jpg", "nsfw": False, "width": 512, "height": 768, "meta": meta},
        ]

        results = service._download_additional_previews(
            pack_name="test-pack", previews=previews
        )

        assert results[0].width == 512
        assert results[0].height == 768
        assert results[0].meta == meta
        assert results[0].meta["prompt"] == "a cat"

    def test_metadata_absent_when_not_provided(self, tmp_path):
        """Preview without metadata fields should have None for those fields."""
        mock_ds = MagicMock()
        service = self._make_service(tmp_path, download_service=mock_ds)

        previews = [{"url": "https://example.com/img.jpg", "nsfw": True}]

        results = service._download_additional_previews(
            pack_name="test-pack", previews=previews
        )

        assert results[0].width is None
        assert results[0].height is None
        assert results[0].meta is None
        assert results[0].nsfw is True

    def test_backward_compat_plain_string_defaults_nsfw_false(self, tmp_path):
        """Legacy: plain string URL (not dict) defaults to nsfw=False."""
        mock_ds = MagicMock()
        service = self._make_service(tmp_path, download_service=mock_ds)

        # Simulate legacy format: plain strings instead of dicts
        previews = ["https://example.com/legacy.jpg"]

        results = service._download_additional_previews(
            pack_name="test-pack", previews=previews
        )

        assert len(results) == 1
        assert results[0].nsfw is False
        assert results[0].url == "https://example.com/legacy.jpg"

    def test_community_prefix_with_start_index(self, tmp_path):
        """Test that start_index offsets filenames correctly."""
        mock_ds = MagicMock()
        service = self._make_service(tmp_path, download_service=mock_ds)

        previews = [{"url": "https://example.com/image.jpg", "nsfw": False}]

        results = service._download_additional_previews(
            pack_name="test-pack",
            previews=previews,
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

        previews = [
            {"url": "https://example.com/ok1.jpg", "nsfw": False},
            {"url": "https://example.com/fail.jpg", "nsfw": True},
            {"url": "https://example.com/ok2.jpg", "nsfw": True},
        ]

        results = service._download_additional_previews(
            pack_name="test-pack",
            previews=previews,
        )

        assert len(results) == 2
        assert results[0].filename == "community_1.jpg"
        assert results[1].filename == "community_3.jpg"
        # nsfw preserved even with failures in between
        assert results[0].nsfw is False
        assert results[1].nsfw is True

    def test_empty_previews_returns_empty(self, tmp_path):
        """Test that empty preview list returns empty results."""
        service = self._make_service(tmp_path)

        results = service._download_additional_previews(
            pack_name="test-pack",
            previews=[],
        )

        assert results == []

    def test_skips_empty_url_strings(self, tmp_path):
        """Test that empty URLs in preview list are skipped."""
        mock_ds = MagicMock()
        service = self._make_service(tmp_path, download_service=mock_ds)

        previews = [
            {"url": "", "nsfw": False},
            {"url": "https://example.com/image.jpg", "nsfw": True},
            {"url": "", "nsfw": False},
        ]

        results = service._download_additional_previews(
            pack_name="test-pack",
            previews=previews,
        )

        assert len(results) == 1
        assert results[0].filename == "community_2.jpg"
        assert results[0].nsfw is True

    def test_video_url_gets_mp4_extension(self, tmp_path):
        """Test that video URLs are saved with .mp4 extension."""
        mock_ds = MagicMock()
        service = self._make_service(tmp_path, download_service=mock_ds)

        previews = [{"url": "https://image.civitai.com/preview.mp4?transcode=true", "nsfw": False}]

        results = service._download_additional_previews(
            pack_name="test-pack",
            previews=previews,
        )

        assert len(results) == 1
        assert results[0].filename == "community_1.mp4"
        assert results[0].media_type == "video"
        assert results[0].thumbnail_url is not None

    def test_creates_previews_directory(self, tmp_path):
        """Test that previews directory is created if it doesn't exist."""
        mock_ds = MagicMock()
        service = self._make_service(tmp_path, download_service=mock_ds)

        previews = [{"url": "https://example.com/image.jpg", "nsfw": False}]
        service._download_additional_previews(pack_name="new-pack", previews=previews)

        previews_dir = tmp_path / "state" / "packs" / "new-pack" / "resources" / "previews"
        assert previews_dir.exists()

    def test_fallback_to_requests_when_no_download_service(self, tmp_path):
        """Test direct download when DownloadService is not available."""
        service = self._make_service(tmp_path, download_service=None)

        previews = [{"url": "https://example.com/image.jpg", "nsfw": True}]

        with patch("src.store.pack_service.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.iter_content.return_value = [b"fake image data"]
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            results = service._download_additional_previews(
                pack_name="test-pack", previews=previews
            )

        assert len(results) == 1
        assert results[0].nsfw is True
        mock_get.assert_called_once()


class TestImportRequestAdditionalPreviews:
    """Tests for ImportRequest model with additional_previews."""

    def test_import_request_without_additional_previews(self):
        """Test backward compat: additional_previews defaults to None."""
        from src.store.api import ImportRequest
        req = ImportRequest(url="https://civitai.com/models/123")
        assert req.additional_previews is None
        assert req.additional_preview_urls is None

    def test_import_request_with_additional_previews(self):
        """Test that additional_previews accepts list of {url, nsfw} dicts."""
        from src.store.api import ImportRequest, AdditionalPreview
        previews = [
            {"url": "https://example.com/a.jpg", "nsfw": False},
            {"url": "https://example.com/b.jpg", "nsfw": True},
        ]
        req = ImportRequest(url="https://civitai.com/models/123", additional_previews=previews)
        assert len(req.additional_previews) == 2
        assert isinstance(req.additional_previews[0], AdditionalPreview)
        assert req.additional_previews[1].nsfw is True
        assert req.additional_previews[0].url == "https://example.com/a.jpg"

    def test_import_request_with_metadata(self):
        """Test that additional_previews accepts metadata fields."""
        from src.store.api import ImportRequest
        meta = {"prompt": "a cat", "seed": 12345}
        previews = [
            {"url": "https://example.com/a.jpg", "nsfw": False, "width": 512, "height": 768, "meta": meta},
        ]
        req = ImportRequest(url="https://civitai.com/models/123", additional_previews=previews)
        p = req.additional_previews[0]
        assert p.width == 512
        assert p.height == 768
        assert p.meta == meta

    def test_import_request_legacy_urls_still_accepted(self):
        """Test backward compat: old additional_preview_urls field still works."""
        from src.store.api import ImportRequest
        urls = ["https://example.com/a.jpg", "https://example.com/b.jpg"]
        req = ImportRequest(url="https://civitai.com/models/123", additional_preview_urls=urls)
        assert req.additional_preview_urls == urls

    def test_import_request_with_empty_additional_previews(self):
        """Test that empty list is accepted."""
        from src.store.api import ImportRequest
        req = ImportRequest(url="https://civitai.com/models/123", additional_previews=[])
        assert req.additional_previews == []

    def test_import_request_rejects_too_many_previews(self):
        """Test that more than 200 previews are rejected."""
        from src.store.api import ImportRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ImportRequest(url="https://civitai.com/models/123", additional_previews=[{"url": "https://x.com/i.jpg", "nsfw": False}] * 201)

    def test_import_request_rejects_empty_url(self):
        """Test that empty URL string is rejected by Pydantic."""
        from src.store.api import ImportRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ImportRequest(url="https://civitai.com/models/123", additional_previews=[{"url": "", "nsfw": False}])

    def test_import_request_rejects_oversized_meta(self):
        """Test that meta field larger than 64KB is rejected."""
        from src.store.api import ImportRequest
        from pydantic import ValidationError
        huge_meta = {"data": "x" * 70000}
        with pytest.raises(ValidationError):
            ImportRequest(url="https://civitai.com/models/123", additional_previews=[
                {"url": "https://example.com/a.jpg", "nsfw": False, "meta": huge_meta}
            ])

    def test_import_request_rejects_http_url(self):
        """Test that http:// URLs are rejected (SSRF protection)."""
        from src.store.api import ImportRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError, match="https://"):
            ImportRequest(url="https://civitai.com/models/123", additional_previews=[
                {"url": "http://example.com/a.jpg", "nsfw": False}
            ])

    def test_import_request_rejects_ftp_url(self):
        """Test that non-https schemes are rejected."""
        from src.store.api import ImportRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ImportRequest(url="https://civitai.com/models/123", additional_previews=[
                {"url": "ftp://example.com/a.jpg", "nsfw": False}
            ])

    def test_additional_preview_model_dump(self):
        """Test that AdditionalPreview model_dump works for pack_service."""
        from src.store.api import AdditionalPreview
        p = AdditionalPreview(url="https://example.com/a.jpg", nsfw=True, width=512, height=768)
        d = p.model_dump(exclude_none=True)
        assert d == {"url": "https://example.com/a.jpg", "nsfw": True, "width": 512, "height": 768}
        assert "meta" not in d  # None fields excluded
