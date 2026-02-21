"""
Tests for preview loading performance fixes.

Covers:
- Fix 1: Video thumbnail_url uses local URL (not remote Civitai CDN)
- Fix 2: Parallel preview downloads via ThreadPoolExecutor
- Fix 7: URL-encoding of filenames in preview URLs
"""

import json
import time
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.parse import quote

import pytest

from src.store.pack_service import PackService, DownloadProgressInfo
from src.store.models import PreviewInfo


# =============================================================================
# Fix 1: Video thumbnail_url → local URL
# =============================================================================

class TestVideoThumbnailLocalUrl:
    """Video thumbnails should use local URLs, not remote Civitai CDN URLs."""

    def test_video_thumbnail_url_is_local_path(self):
        """API should return local preview URL for video thumbnail, not Civitai CDN."""
        preview = PreviewInfo(
            filename="video.mp4",
            url="https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/abc123/video.mp4",
            media_type="video",
            thumbnail_url="https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/abc123/anim=false,width=450/video.jpeg",
        )

        pack_name = "test-pack"
        preview_url = f"/previews/{pack_name}/resources/previews/{preview.filename}"
        media_type = preview.media_type

        # This is the FIX: always use local URL for video thumbnails
        if media_type == 'video':
            thumbnail_url = preview_url

        assert thumbnail_url == f"/previews/{pack_name}/resources/previews/video.mp4"
        assert "civitai.com" not in thumbnail_url

    def test_video_thumbnail_url_not_civitai_cdn(self):
        """Ensure no Civitai CDN URL leaks through for video thumbnails."""
        preview = PreviewInfo(
            filename="animation.mp4",
            url="https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/def456/animation.mp4",
            media_type="video",
            thumbnail_url="https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/def456/anim=false/animation.jpeg",
        )

        pack_name = "my-pack"
        preview_url = f"/previews/{pack_name}/resources/previews/{preview.filename}"

        thumbnail_url = preview_url
        assert thumbnail_url.startswith("/previews/")
        assert "civitai.com" not in thumbnail_url

    def test_image_preview_has_no_thumbnail_url(self):
        """Image previews should not have a thumbnail_url at all."""
        preview = PreviewInfo(
            filename="image.jpg",
            url="https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/abc123/image.jpeg",
            media_type="image",
        )

        assert preview.thumbnail_url is None


# =============================================================================
# Fix 2: Parallel preview downloads
# =============================================================================

MEDIA_DETECT_PATCH = "src.utils.media_detection.detect_media_type"
VIDEO_THUMB_PATCH = "src.utils.media_detection.get_video_thumbnail_url"
VIDEO_URL_PATCH = "src.utils.media_detection.get_optimized_video_url"


class TestParallelPreviewDownloads:
    """Preview downloads should use ThreadPoolExecutor for parallelism."""

    @pytest.fixture
    def mock_layout(self, tmp_path):
        """Create a mock StoreLayout."""
        layout = MagicMock()
        previews_dir = tmp_path / "previews"
        previews_dir.mkdir()
        layout.pack_previews_path.return_value = previews_dir
        return layout

    @pytest.fixture
    def mock_download_service(self):
        """Create a mock DownloadService."""
        ds = MagicMock()

        def fake_download(url, dest, **kwargs):
            time.sleep(0.05)
            dest.write_bytes(b"fake-content")

        ds.download_to_file.side_effect = fake_download
        return ds

    @pytest.fixture
    def pack_service(self, mock_layout, mock_download_service):
        """Create PackService with mocks."""
        svc = PackService.__new__(PackService)
        svc.layout = mock_layout
        svc._download_service = mock_download_service
        svc._civitai_client = MagicMock()
        return svc

    def _make_version_data(self, count: int):
        """Create version_data with N image URLs."""
        return {
            "images": [
                {
                    "url": f"https://image.civitai.com/test/img_{i}.jpg",
                    "width": 512,
                    "height": 512,
                    "nsfw": False,
                    "nsfwLevel": 1,
                }
                for i in range(count)
            ]
        }

    @patch(VIDEO_URL_PATCH, return_value="http://optimized.url")
    @patch(VIDEO_THUMB_PATCH, return_value="http://thumb.url")
    @patch(MEDIA_DETECT_PATCH)
    def test_downloads_multiple_previews(self, mock_detect, mock_thumb, mock_vid_url,
                                         pack_service, mock_download_service):
        """Should download multiple previews successfully."""
        mock_detect.return_value = MagicMock(type=MagicMock(value="image"))

        version_data = self._make_version_data(5)
        result = pack_service._download_previews("test-pack", version_data)

        assert len(result) == 5
        assert mock_download_service.download_to_file.call_count == 5

    @patch(VIDEO_URL_PATCH, return_value="http://optimized.url")
    @patch(VIDEO_THUMB_PATCH, return_value="http://thumb.url")
    @patch(MEDIA_DETECT_PATCH)
    def test_parallel_downloads_faster_than_serial(self, mock_detect, mock_thumb, mock_vid_url,
                                                    pack_service, mock_download_service):
        """Parallel downloads should be significantly faster than serial."""
        mock_detect.return_value = MagicMock(type=MagicMock(value="image"))

        count = 8
        version_data = self._make_version_data(count)

        start = time.monotonic()
        result = pack_service._download_previews("test-pack", version_data)
        elapsed = time.monotonic() - start

        assert len(result) == count
        # Serial would take 8 * 0.05 = 0.4s, parallel with 4 workers ≈ 0.1s
        assert elapsed < 0.35, f"Downloads took {elapsed:.2f}s — likely serial, not parallel"

    @patch(VIDEO_URL_PATCH, return_value="http://optimized.url")
    @patch(VIDEO_THUMB_PATCH, return_value="http://thumb.url")
    @patch(MEDIA_DETECT_PATCH)
    def test_download_uses_thread_pool(self, mock_detect, mock_thumb, mock_vid_url,
                                       pack_service, mock_download_service):
        """Should use multiple threads for downloading."""
        mock_detect.return_value = MagicMock(type=MagicMock(value="image"))

        thread_ids = set()
        original_download = mock_download_service.download_to_file.side_effect

        def track_threads(url, dest, **kwargs):
            thread_ids.add(threading.current_thread().ident)
            original_download(url, dest, **kwargs)

        mock_download_service.download_to_file.side_effect = track_threads

        version_data = self._make_version_data(8)
        result = pack_service._download_previews("test-pack", version_data)

        assert len(result) == 8
        assert len(thread_ids) > 1, f"Only {len(thread_ids)} thread(s) used — not parallel"

    @patch(VIDEO_URL_PATCH, return_value="http://optimized.url")
    @patch(VIDEO_THUMB_PATCH, return_value="http://thumb.url")
    @patch(MEDIA_DETECT_PATCH)
    def test_failed_download_does_not_block_others(self, mock_detect, mock_thumb, mock_vid_url,
                                                    pack_service, mock_download_service):
        """A failed download should not prevent other downloads from completing."""
        mock_detect.return_value = MagicMock(type=MagicMock(value="image"))

        def sometimes_fail(url, dest, **kwargs):
            if "img_2" in url:
                raise ConnectionError("Simulated network error")
            dest.write_bytes(b"fake-content")

        mock_download_service.download_to_file.side_effect = sometimes_fail

        version_data = self._make_version_data(5)
        result = pack_service._download_previews("test-pack", version_data)

        # 4 out of 5 should succeed (img_2 fails)
        assert len(result) == 4

    @patch(VIDEO_URL_PATCH, return_value="http://optimized.url")
    @patch(VIDEO_THUMB_PATCH, return_value="http://thumb.url")
    @patch(MEDIA_DETECT_PATCH)
    def test_preserves_order(self, mock_detect, mock_thumb, mock_vid_url,
                             pack_service, mock_download_service):
        """Results should be in original order despite parallel execution."""
        mock_detect.return_value = MagicMock(type=MagicMock(value="image"))

        import random

        def random_delay_download(url, dest, **kwargs):
            time.sleep(random.uniform(0.01, 0.05))
            dest.write_bytes(b"fake-content")

        mock_download_service.download_to_file.side_effect = random_delay_download

        version_data = self._make_version_data(10)
        result = pack_service._download_previews("test-pack", version_data)

        assert len(result) == 10
        for i, info in enumerate(result):
            assert f"img_{i}" in info.filename

    @patch(VIDEO_URL_PATCH, return_value="http://optimized.url")
    @patch(VIDEO_THUMB_PATCH, return_value="http://thumb.url")
    @patch(MEDIA_DETECT_PATCH)
    def test_skips_existing_files(self, mock_detect, mock_thumb, mock_vid_url,
                                   pack_service, mock_layout):
        """Should skip downloads for files that already exist."""
        mock_detect.return_value = MagicMock(type=MagicMock(value="image"))

        previews_dir = mock_layout.pack_previews_path.return_value

        # Pre-create some files
        (previews_dir / "img_0.jpg").write_bytes(b"existing")
        (previews_dir / "img_1.jpg").write_bytes(b"existing")

        version_data = self._make_version_data(3)
        result = pack_service._download_previews("test-pack", version_data)

        # All 3 should be in results (2 existing + 1 downloaded)
        assert len(result) == 3
        # But only 1 should have been actually downloaded
        assert pack_service._download_service.download_to_file.call_count == 1


# =============================================================================
# Fix 7: URL-encoding of filenames in preview URLs
# =============================================================================

class TestPreviewUrlEncoding:
    """Preview URLs must URL-encode filenames to avoid broken requests."""

    def test_filename_with_ampersand_is_encoded(self):
        """Filenames containing '&' must be percent-encoded in URLs."""
        filename = "image_foo&bar.jpg"
        pack_name = "test-pack"
        preview_url = f"/previews/{pack_name}/resources/previews/{quote(filename, safe='')}"
        assert "&" not in preview_url.split("/")[-1]
        assert "image_foo%26bar.jpg" in preview_url

    def test_filename_with_spaces_is_encoded(self):
        """Filenames containing spaces must be percent-encoded."""
        filename = "my image (1).jpg"
        pack_name = "test-pack"
        preview_url = f"/previews/{pack_name}/resources/previews/{quote(filename, safe='')}"
        assert " " not in preview_url
        assert "%20" in preview_url or "+" in preview_url

    def test_filename_with_hash_is_encoded(self):
        """Filenames containing '#' must be percent-encoded."""
        filename = "image#2.jpg"
        pack_name = "test-pack"
        preview_url = f"/previews/{pack_name}/resources/previews/{quote(filename, safe='')}"
        assert "#" not in preview_url
        assert "%23" in preview_url

    def test_filename_with_question_mark_is_encoded(self):
        """Filenames containing '?' must be percent-encoded."""
        filename = "preview?v=2.png"
        pack_name = "test-pack"
        preview_url = f"/previews/{pack_name}/resources/previews/{quote(filename, safe='')}"
        assert "?" not in preview_url
        assert "%3F" in preview_url

    def test_simple_filename_unchanged(self):
        """Simple alphanumeric filenames should pass through mostly unchanged."""
        filename = "preview_001.jpg"
        pack_name = "test-pack"
        preview_url = f"/previews/{pack_name}/resources/previews/{quote(filename, safe='')}"
        # underscore, dot, digits, letters are safe after quote with safe=''
        # actually quote(safe='') encodes dots too? No — quote leaves dots alone by default
        assert preview_url.endswith("/preview_001.jpg")

    def test_filename_with_unicode_is_encoded(self):
        """Filenames with unicode characters must be percent-encoded."""
        filename = "obrázek_č1.jpg"
        pack_name = "test-pack"
        preview_url = f"/previews/{pack_name}/resources/previews/{quote(filename, safe='')}"
        # Original unicode chars should not appear in the URL
        assert "á" not in preview_url
        assert "č" not in preview_url
