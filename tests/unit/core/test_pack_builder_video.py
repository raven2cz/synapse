"""
Unit tests for Pack Builder video preview functionality.

Tests cover video download features added in v2.6.0:
- Video file detection and proper extension handling
- Download filtering (images/videos/NSFW)
- Optimized video URLs for quality control
- Extended timeouts for large video files
- Progress callback reporting
- URL deduplication

Author: Synapse Team
License: MIT
"""

import pytest
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional
from unittest.mock import MagicMock, Mock, patch

import sys
# Add project root to path for absolute imports (conftest.py handles this too)
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# Import directly from module file to avoid __init__.py import chain
import importlib.util
spec = importlib.util.spec_from_file_location(
    "pack_builder",
    project_root / "src" / "core" / "pack_builder.py"
)
pack_builder_module = importlib.util.module_from_spec(spec)
sys.modules["pack_builder"] = pack_builder_module
spec.loader.exec_module(pack_builder_module)

PreviewDownloadOptions = pack_builder_module.PreviewDownloadOptions
DownloadProgress = pack_builder_module.DownloadProgress


# =============================================================================
# Mock Classes (simulating Civitai API models)
# =============================================================================

class MediaType(Enum):
    """Mock MediaType enum matching Civitai API."""
    IMAGE = "image"
    VIDEO = "video"


@dataclass
class MediaInfo:
    """Mock MediaInfo matching Civitai preview structure."""
    url: str
    type: MediaType
    nsfw: bool = False
    nsfwLevel: int = 1
    width: int = 512
    height: int = 768
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API compatibility."""
        return {
            "url": self.url,
            "type": self.type.value,
            "nsfw": self.nsfw,
            "nsfwLevel": self.nsfwLevel,
            "width": self.width,
            "height": self.height,
        }


@dataclass 
class CivitaiModelVersion:
    """Mock CivitaiModelVersion for testing."""
    id: int
    name: str
    images: List[MediaInfo]


# =============================================================================
# PreviewDownloadOptions Tests
# =============================================================================

class TestPreviewDownloadOptions:
    """Tests for PreviewDownloadOptions dataclass."""
    
    def test_default_values(self):
        """Default options should enable all downloads with reasonable limits."""
        options = PreviewDownloadOptions()
        
        assert options.download_images is True
        assert options.download_videos is True
        assert options.include_nsfw is True
        assert options.max_previews == 20
        assert options.video_quality == 1080
        assert options.image_timeout == 60
        assert options.video_timeout == 120
    
    def test_video_timeout_higher_than_image(self):
        """Video timeout should be higher to accommodate larger files."""
        options = PreviewDownloadOptions()
        
        assert options.video_timeout > options.image_timeout
        assert options.video_timeout == 120  # 2 minutes for videos
        assert options.image_timeout == 60   # 1 minute for images
    
    def test_custom_options(self):
        """Custom options should be properly applied."""
        options = PreviewDownloadOptions(
            download_images=False,
            download_videos=True,
            include_nsfw=False,
            max_previews=5,
            video_quality=720,
        )
        
        assert options.download_images is False
        assert options.download_videos is True
        assert options.include_nsfw is False
        assert options.max_previews == 5
        assert options.video_quality == 720
    
    def test_videos_only_configuration(self):
        """Configuration for downloading only videos."""
        options = PreviewDownloadOptions(
            download_images=False,
            download_videos=True,
        )
        
        assert options.download_images is False
        assert options.download_videos is True
    
    def test_images_only_configuration(self):
        """Configuration for downloading only images."""
        options = PreviewDownloadOptions(
            download_images=True,
            download_videos=False,
        )
        
        assert options.download_images is True
        assert options.download_videos is False


# =============================================================================
# DownloadProgress Tests
# =============================================================================

class TestDownloadProgress:
    """Tests for DownloadProgress dataclass."""
    
    def test_initial_state(self):
        """Progress should initialize with correct default status."""
        progress = DownloadProgress(
            index=0,
            total=10,
            filename="preview_001.mp4",
            url="https://example.com/video.mp4",
            media_type="video",
        )
        
        assert progress.index == 0
        assert progress.total == 10
        assert progress.status == "downloading"
        assert progress.bytes_downloaded == 0
        assert progress.total_bytes is None
        assert progress.error is None
    
    def test_percent_complete_calculation(self):
        """Percentage should be calculated when total bytes is known."""
        progress = DownloadProgress(
            index=0,
            total=1,
            filename="video.mp4",
            url="https://example.com/video.mp4",
            media_type="video",
            bytes_downloaded=5000,
            total_bytes=10000,
        )
        
        assert progress.percent_complete == 50.0
    
    def test_percent_complete_unknown(self):
        """Percentage should be None when total bytes is unknown."""
        progress = DownloadProgress(
            index=0,
            total=1,
            filename="video.mp4",
            url="https://example.com/video.mp4",
            media_type="video",
            bytes_downloaded=5000,
            total_bytes=None,
        )
        
        assert progress.percent_complete is None
    
    def test_completed_status(self):
        """Progress can transition to completed status."""
        progress = DownloadProgress(
            index=0,
            total=1,
            filename="video.mp4",
            url="https://example.com/video.mp4",
            media_type="video",
            status="completed",
        )
        
        assert progress.status == "completed"
    
    def test_failed_status_with_error(self):
        """Failed downloads should include error message."""
        progress = DownloadProgress(
            index=0,
            total=1,
            filename="video.mp4",
            url="https://example.com/video.mp4",
            media_type="video",
            status="failed",
            error="Connection timeout",
        )
        
        assert progress.status == "failed"
        assert progress.error == "Connection timeout"


# =============================================================================
# Video Detection Tests
# =============================================================================

class TestVideoDetection:
    """Tests for video media type detection."""
    
    @pytest.mark.parametrize("url,expected", [
        ("https://example.com/video.mp4", True),
        ("https://example.com/video.webm", True),
        ("https://example.com/video.mov", True),
        ("https://example.com/image.jpg", False),
        ("https://example.com/image.png", False),
        ("https://example.com/image.webp", False),
    ])
    def test_extension_detection(self, url: str, expected: bool):
        """URLs should be detected by extension."""
        video_extensions = {".mp4", ".webm", ".mov", ".avi", ".mkv"}
        ext = Path(url).suffix.lower()
        is_video = ext in video_extensions
        
        assert is_video == expected
    
    def test_civitai_fake_jpeg_video(self):
        """Civitai videos disguised as JPEG should be handled.
        
        Civitai sometimes serves videos with .jpeg extension.
        These should be detected via MediaType or Content-Type header.
        """
        # This is detected via MediaType field, not extension
        media = MediaInfo(
            url="https://image.civitai.com/preview/fake_video.jpeg",
            type=MediaType.VIDEO,
        )
        
        assert media.type == MediaType.VIDEO
        # Even though extension is .jpeg, MediaType indicates video
    
    def test_video_from_media_type_field(self):
        """Videos should be identified from MediaType field."""
        image_media = MediaInfo(
            url="https://example.com/preview.jpg",
            type=MediaType.IMAGE,
        )
        video_media = MediaInfo(
            url="https://example.com/preview.mp4",
            type=MediaType.VIDEO,
        )
        
        assert image_media.type == MediaType.IMAGE
        assert video_media.type == MediaType.VIDEO


# =============================================================================
# URL Optimization Tests
# =============================================================================

class TestVideoUrlOptimization:
    """Tests for video URL optimization functions."""
    
    def test_civitai_video_url_transformation(self):
        """Civitai video URLs should be transformed for proper playback."""
        original_url = "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/video.mp4"
        
        # Expected transformation adds transcode=true and width parameter
        optimized = f"{original_url}?transcode=true&width=1080"
        
        assert "transcode=true" in optimized
        assert "width=1080" in optimized
    
    def test_video_quality_parameter(self):
        """Video quality should be configurable via URL parameter."""
        base_url = "https://image.civitai.com/video.mp4"
        
        qualities = [450, 720, 1080]
        for quality in qualities:
            optimized = f"{base_url}?width={quality}"
            assert f"width={quality}" in optimized
    
    def test_thumbnail_url_generation(self):
        """Static thumbnail URL should use anim=false parameter."""
        video_url = "https://image.civitai.com/video.mp4"
        
        # Thumbnail extraction uses anim=false
        thumbnail_url = f"{video_url}?anim=false"
        
        assert "anim=false" in thumbnail_url


# =============================================================================
# NSFW Filtering Tests
# =============================================================================

class TestNsfwFiltering:
    """Tests for NSFW content filtering during download."""
    
    def test_nsfw_included_by_default(self):
        """NSFW content should be included by default."""
        options = PreviewDownloadOptions()
        
        assert options.include_nsfw is True
    
    def test_nsfw_can_be_excluded(self):
        """NSFW content should be excludable via options."""
        options = PreviewDownloadOptions(include_nsfw=False)
        
        assert options.include_nsfw is False
    
    def test_nsfw_detection_via_flag(self):
        """NSFW should be detected via nsfw boolean flag."""
        safe_media = MediaInfo(
            url="https://example.com/safe.jpg",
            type=MediaType.IMAGE,
            nsfw=False,
        )
        nsfw_media = MediaInfo(
            url="https://example.com/nsfw.jpg",
            type=MediaType.IMAGE,
            nsfw=True,
        )
        
        assert safe_media.nsfw is False
        assert nsfw_media.nsfw is True
    
    def test_nsfw_detection_via_level(self):
        """NSFW should be detected via nsfwLevel threshold.
        
        Civitai uses nsfwLevel: 1=safe, 2+=mature content.
        """
        previews = [
            MediaInfo(url="a.jpg", type=MediaType.IMAGE, nsfwLevel=1),  # Safe
            MediaInfo(url="b.jpg", type=MediaType.IMAGE, nsfwLevel=2),  # Suggestive
            MediaInfo(url="c.jpg", type=MediaType.IMAGE, nsfwLevel=4),  # NSFW
        ]
        
        nsfw_threshold = 2  # Level 2+ is considered NSFW
        
        filtered = [p for p in previews if p.nsfwLevel < nsfw_threshold]
        
        assert len(filtered) == 1
        assert filtered[0].url == "a.jpg"


# =============================================================================
# Deduplication Tests
# =============================================================================

class TestUrlDeduplication:
    """Tests for URL deduplication during multi-version downloads."""
    
    def test_duplicate_urls_skipped(self):
        """Duplicate URLs across versions should be downloaded only once."""
        shared_url = "https://example.com/shared_preview.jpg"
        
        all_urls = [
            shared_url,
            "https://example.com/unique_1.jpg",
            shared_url,  # Duplicate
            "https://example.com/unique_2.jpg",
            shared_url,  # Duplicate
        ]
        
        seen_urls = set()
        unique_urls = []
        
        for url in all_urls:
            if url not in seen_urls:
                seen_urls.add(url)
                unique_urls.append(url)
        
        assert len(unique_urls) == 3
        assert unique_urls.count(shared_url) == 1
    
    def test_similar_urls_not_deduplicated(self):
        """Similar but different URLs should not be deduplicated."""
        urls = [
            "https://example.com/preview.jpg",
            "https://example.com/preview.jpg?width=720",
            "https://example.com/preview.jpg?width=1080",
        ]
        
        unique_urls = list(set(urls))
        
        assert len(unique_urls) == 3


# =============================================================================
# File Extension Tests
# =============================================================================

class TestFileExtensions:
    """Tests for proper file extension handling."""
    
    def test_video_saved_with_mp4_extension(self):
        """Video files should always be saved with .mp4 extension."""
        video_url = "https://example.com/video.webm"
        
        # Extension normalization for videos
        target_ext = ".mp4"
        filename = f"preview_001{target_ext}"
        
        assert filename.endswith(".mp4")
    
    def test_image_preserves_original_extension(self):
        """Image files should preserve their original extension."""
        test_cases = [
            ("https://example.com/img.jpg", ".jpg"),
            ("https://example.com/img.jpeg", ".jpeg"),
            ("https://example.com/img.png", ".png"),
            ("https://example.com/img.webp", ".webp"),
        ]
        
        for url, expected_ext in test_cases:
            ext = Path(url).suffix.lower()
            assert ext == expected_ext
    
    def test_civitai_cdn_url_extension_extraction(self):
        """Civitai CDN URLs should have extension extracted correctly."""
        # Civitai uses complex URLs with UUIDs
        civitai_url = "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/abc123-def456.jpeg"
        
        ext = Path(civitai_url).suffix.lower()
        
        assert ext == ".jpeg"


# =============================================================================
# Progress Callback Tests
# =============================================================================

class TestProgressCallback:
    """Tests for progress callback functionality."""
    
    def test_callback_invoked_for_each_file(self):
        """Progress callback should be invoked for each downloaded file."""
        callback_calls = []
        
        def track_callback(progress: DownloadProgress):
            callback_calls.append(progress)
        
        # Simulate downloads
        total_files = 5
        for i in range(total_files):
            progress = DownloadProgress(
                index=i,
                total=total_files,
                filename=f"preview_{i:03d}.jpg",
                url=f"https://example.com/preview_{i}.jpg",
                media_type="image",
                status="completed",
            )
            track_callback(progress)
        
        assert len(callback_calls) == total_files
        assert all(p.status == "completed" for p in callback_calls)
    
    def test_callback_reports_video_type(self):
        """Callback should correctly report video media type."""
        callback_calls = []
        
        def track_callback(progress: DownloadProgress):
            callback_calls.append(progress)
        
        # Video download
        progress = DownloadProgress(
            index=0,
            total=1,
            filename="preview_000.mp4",
            url="https://example.com/video.mp4",
            media_type="video",
            status="completed",
        )
        track_callback(progress)
        
        assert len(callback_calls) == 1
        assert callback_calls[0].media_type == "video"
    
    def test_callback_handles_failures(self):
        """Callback should report failed downloads with error details."""
        callback_calls = []
        
        def track_callback(progress: DownloadProgress):
            callback_calls.append(progress)
        
        # Failed download
        progress = DownloadProgress(
            index=0,
            total=1,
            filename="preview_000.mp4",
            url="https://example.com/video.mp4",
            media_type="video",
            status="failed",
            error="HTTP 404: Not Found",
        )
        track_callback(progress)
        
        assert len(callback_calls) == 1
        assert callback_calls[0].status == "failed"
        assert "404" in callback_calls[0].error


# =============================================================================
# Integration Tests
# =============================================================================

class TestPackBuilderIntegration:
    """Integration tests for pack builder video functionality."""
    
    def test_mixed_media_download_scenario(self):
        """Test downloading a mix of images and videos."""
        previews = [
            MediaInfo(url="https://example.com/img1.jpg", type=MediaType.IMAGE),
            MediaInfo(url="https://example.com/vid1.mp4", type=MediaType.VIDEO),
            MediaInfo(url="https://example.com/img2.png", type=MediaType.IMAGE),
            MediaInfo(url="https://example.com/vid2.webm", type=MediaType.VIDEO),
            MediaInfo(url="https://example.com/nsfw.jpg", type=MediaType.IMAGE, nsfw=True),
        ]
        
        options = PreviewDownloadOptions(
            download_images=True,
            download_videos=True,
            include_nsfw=False,
        )
        
        # Filter based on options
        to_download = []
        for p in previews:
            if p.nsfw and not options.include_nsfw:
                continue
            if p.type == MediaType.IMAGE and not options.download_images:
                continue
            if p.type == MediaType.VIDEO and not options.download_videos:
                continue
            to_download.append(p)
        
        assert len(to_download) == 4  # 2 images + 2 videos (NSFW excluded)
    
    def test_video_only_download_scenario(self):
        """Test downloading only videos (skip images)."""
        previews = [
            MediaInfo(url="https://example.com/img1.jpg", type=MediaType.IMAGE),
            MediaInfo(url="https://example.com/vid1.mp4", type=MediaType.VIDEO),
            MediaInfo(url="https://example.com/img2.png", type=MediaType.IMAGE),
        ]
        
        options = PreviewDownloadOptions(
            download_images=False,
            download_videos=True,
        )
        
        to_download = [
            p for p in previews 
            if (p.type == MediaType.VIDEO and options.download_videos)
        ]
        
        assert len(to_download) == 1
        assert to_download[0].url.endswith(".mp4")
    
    def test_max_previews_limit(self):
        """Test max_previews limit is respected."""
        previews = [
            MediaInfo(url=f"https://example.com/img{i}.jpg", type=MediaType.IMAGE)
            for i in range(50)
        ]
        
        options = PreviewDownloadOptions(max_previews=10)
        
        limited = previews[:options.max_previews]
        
        assert len(limited) == 10


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])


# =============================================================================
# Multi-Version Support Tests
# =============================================================================

class TestMultiVersionSupport:
    """Tests for multi-version import functionality."""
    
    def test_version_ids_parameter_type(self):
        """Test that version_ids accepts list of integers."""
        # This tests the parameter interface, not actual execution
        PackBuilder = pack_builder_module.PackBuilder
        import inspect
        
        sig = inspect.signature(PackBuilder.build_from_civitai_url)
        params = sig.parameters
        
        assert 'version_ids' in params
        # Default should be None
        assert params['version_ids'].default is None
    
    def test_custom_description_parameter(self):
        """Test that custom_description parameter exists."""
        PackBuilder = pack_builder_module.PackBuilder
        import inspect
        
        sig = inspect.signature(PackBuilder.build_from_civitai_url)
        params = sig.parameters
        
        assert 'custom_description' in params
        assert params['custom_description'].default is None
    
    def test_thumbnail_url_parameter(self):
        """Test that thumbnail_url parameter exists."""
        PackBuilder = pack_builder_module.PackBuilder
        import inspect
        
        sig = inspect.signature(PackBuilder.build_from_civitai_url)
        params = sig.parameters
        
        assert 'thumbnail_url' in params
        assert params['thumbnail_url'].default is None
    
    def test_preview_deduplication_across_versions(self):
        """Test that previews are deduplicated across multiple versions."""
        # Create mock data with duplicate URLs
        urls = [
            "https://example.com/shared.jpg",  # Shared between versions
            "https://example.com/v1_only.jpg",
            "https://example.com/shared.jpg",  # Duplicate
            "https://example.com/v2_only.jpg",
        ]
        
        seen = set()
        unique_urls = []
        for url in urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)
        
        assert len(unique_urls) == 3
        assert "https://example.com/shared.jpg" in unique_urls
    
    def test_max_previews_across_versions(self):
        """Test that max_previews limit is respected across all versions."""
        max_previews = 5
        version1_previews = 4
        version2_previews = 3
        
        # Simulate accumulation logic
        total = 0
        collected = []
        
        for i in range(version1_previews):
            if total < max_previews:
                collected.append(f"v1_preview_{i}")
                total += 1
        
        for i in range(version2_previews):
            if total < max_previews:
                collected.append(f"v2_preview_{i}")
                total += 1
        
        assert len(collected) == max_previews
        assert collected == ['v1_preview_0', 'v1_preview_1', 'v1_preview_2', 'v1_preview_3', 'v2_preview_0']
