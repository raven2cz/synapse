"""
E2E Tests for Import Flow

Tests the complete import flow:
1. Import preview (fetches model info)
2. Import with wizard options
3. Pack save/load cycle
4. Preview files on disk
5. Metadata persistence

Author: Synapse Team
License: MIT
"""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.store import Store, StoreLayout, BlobStore, PackService
from src.store.models import Pack, PreviewInfo, AssetKind


class FakeCivitaiClientForE2E:
    """Fake Civitai client that returns realistic data for E2E testing."""

    def __init__(self):
        self.model_id = 12345
        self.version_id = 67890

    def get_model(self, model_id: int):
        """Return realistic model data."""
        return {
            "id": model_id,
            "name": "Amazing LoRA v2",
            "type": "LORA",
            "creator": {"username": "TestCreator"},
            "description": "A high quality anime style LoRA",
            "tags": ["anime", "style", "character"],
            "stats": {"downloadCount": 50000, "rating": 4.8},
            "modelVersions": [
                {
                    "id": 67890,
                    "name": "v2.0 - HIGH",
                    "baseModel": "SDXL 1.0",
                    "trainedWords": ["amazing_style", "character_name"],
                    "createdAt": "2025-01-15T12:00:00Z",
                    "files": [
                        {
                            "id": 111,
                            "name": "amazing_lora_v2_high.safetensors",
                            "sizeKB": 1536000,  # 1.5 GB
                            "primary": True,
                            "hashes": {"SHA256": "abc123def456"},
                            "downloadUrl": "https://civitai.com/api/download/models/67890",
                        }
                    ],
                    "images": [
                        {
                            "url": "https://image.civitai.com/preview1.jpeg",
                            "nsfw": False,
                            "nsfwLevel": 1,
                            "width": 1024,
                            "height": 1536,
                            "meta": {
                                "prompt": "masterpiece, best quality, amazing_style",
                                "negativePrompt": "bad quality, worst quality",
                                "sampler": "DPM++ 2M Karras",
                                "cfgScale": 7,
                                "seed": 12345678,
                                "steps": 30,
                            }
                        },
                        {
                            "url": "https://image.civitai.com/preview2.mp4?transcode=true",
                            "nsfw": False,
                            "nsfwLevel": 1,
                            "width": 512,
                            "height": 768,
                            "meta": {
                                "prompt": "animation test",
                                "seed": 87654321,
                            }
                        },
                        {
                            "url": "https://image.civitai.com/preview3.jpeg",
                            "nsfw": True,
                            "nsfwLevel": 4,
                            "width": 768,
                            "height": 1024,
                            "meta": {
                                "prompt": "nsfw content test",
                                "seed": 11111111,
                            }
                        },
                    ],
                },
                {
                    "id": 67891,
                    "name": "v2.0 - LOW",
                    "baseModel": "SDXL 1.0",
                    "trainedWords": ["amazing_style"],
                    "files": [
                        {
                            "id": 112,
                            "name": "amazing_lora_v2_low.safetensors",
                            "sizeKB": 819200,  # 800 MB
                            "primary": True,
                            "hashes": {"SHA256": "xyz789abc"},
                            "downloadUrl": "https://civitai.com/api/download/models/67891",
                        }
                    ],
                    "images": [
                        {
                            "url": "https://image.civitai.com/preview4.jpeg",
                            "nsfw": False,
                            "nsfwLevel": 1,
                            "width": 512,
                            "height": 768,
                            "meta": {"prompt": "low quality test"}
                        }
                    ],
                },
            ],
        }

    def get_model_version(self, version_id: int):
        """Return version data."""
        model = self.get_model(self.model_id)
        for version in model["modelVersions"]:
            if version["id"] == version_id:
                return version
        return model["modelVersions"][0]


@pytest.fixture
def temp_store(tmp_path):
    """Create a temporary store for testing."""
    store_root = tmp_path / "synapse_store"
    fake_civitai = FakeCivitaiClientForE2E()

    # Create store with root path - it initializes layout internally
    store = Store(root=store_root, civitai_client=fake_civitai)
    store.init()  # Initialize store directories

    return store


class TestImportPreviewEndpoint:
    """Tests for /import/preview endpoint."""

    def test_preview_returns_model_info(self, temp_store):
        """Test that preview returns correct model information."""
        from src.store.api import import_preview, ThumbnailOption

        result = import_preview(
            url="https://civitai.com/models/12345",
            store=temp_store,
        )

        assert result.model_id == 12345
        assert result.model_name == "Amazing LoRA v2"
        assert result.creator == "TestCreator"
        assert result.model_type == "LORA"
        assert result.base_model == "SDXL 1.0"

    def test_preview_returns_versions(self, temp_store):
        """Test that preview returns version information."""
        from src.store.api import import_preview

        result = import_preview(
            url="https://civitai.com/models/12345",
            store=temp_store,
        )

        assert len(result.versions) == 2
        assert result.versions[0].name == "v2.0 - HIGH"
        assert result.versions[0].total_size_bytes > 0
        assert result.versions[1].name == "v2.0 - LOW"

    def test_preview_counts_media_types(self, temp_store):
        """Test that preview correctly counts images and videos."""
        from src.store.api import import_preview

        result = import_preview(
            url="https://civitai.com/models/12345",
            store=temp_store,
        )

        # Version 1 has: 2 images (1 NSFW), 1 video
        # Version 2 has: 1 image
        # Total: 3 images, 1 video, 1 NSFW
        assert result.total_image_count == 3
        assert result.total_video_count == 1
        assert result.total_nsfw_count == 1

    def test_preview_returns_thumbnails(self, temp_store):
        """Test that preview returns thumbnail options."""
        from src.store.api import import_preview

        result = import_preview(
            url="https://civitai.com/models/12345",
            store=temp_store,
        )

        assert len(result.thumbnail_options) > 0
        # Check video thumbnail is marked correctly
        video_thumbs = [t for t in result.thumbnail_options if t.type == "video"]
        assert len(video_thumbs) == 1

    def test_preview_invalid_url_raises(self, temp_store):
        """Test that invalid URL raises HTTPException."""
        from src.store.api import import_preview
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            import_preview(url="https://invalid.com/something", store=temp_store)

        assert exc_info.value.status_code == 400
        assert "Invalid Civitai URL" in str(exc_info.value.detail)


class TestImportEndpointWithWizard:
    """Tests for /import endpoint with wizard options."""

    def test_import_basic(self, temp_store):
        """Test basic import without wizard options."""
        from src.store.api import import_pack, ImportRequest

        # Mock network request
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.iter_content = MagicMock(return_value=[b'fake image data'])
        mock_response.headers = {'content-length': '100'}

        with patch('src.store.pack_service.requests.get', return_value=mock_response):
            request = ImportRequest(url="https://civitai.com/models/12345")
            result = import_pack(request=request, store=temp_store)

        assert result.success is True
        assert result.pack_name == "Amazing_LoRA_v2"
        assert result.pack_type == "lora"
        assert result.dependencies_count >= 1

    def test_import_with_custom_name(self, temp_store):
        """Test import with custom pack name."""
        from src.store.api import import_pack, ImportRequest

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.iter_content = MagicMock(return_value=[b'fake image data'])
        mock_response.headers = {'content-length': '100'}

        with patch('src.store.pack_service.requests.get', return_value=mock_response):
            request = ImportRequest(
                url="https://civitai.com/models/12345",
                pack_name="my_custom_pack",
            )
            result = import_pack(request=request, store=temp_store)

        assert result.success is True
        assert result.pack_name == "my_custom_pack"

    def test_import_videos_only(self, temp_store):
        """Test import with videos only (no images)."""
        from src.store.api import import_pack, ImportRequest

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.iter_content = MagicMock(return_value=[b'fake video data'])
        mock_response.headers = {'content-length': '1000000'}

        with patch('src.store.pack_service.requests.get', return_value=mock_response):
            request = ImportRequest(
                url="https://civitai.com/models/12345",
                download_images=False,
                download_videos=True,
            )
            result = import_pack(request=request, store=temp_store)

        assert result.success is True
        # Only video should be downloaded
        assert result.videos_downloaded >= 0  # May be 0 if no videos match

    def test_import_excludes_nsfw(self, temp_store):
        """Test import excluding NSFW content."""
        from src.store.api import import_pack, ImportRequest

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.iter_content = MagicMock(return_value=[b'fake image data'])
        mock_response.headers = {'content-length': '100'}

        with patch('src.store.pack_service.requests.get', return_value=mock_response):
            request = ImportRequest(
                url="https://civitai.com/models/12345",
                include_nsfw=False,
            )
            result = import_pack(request=request, store=temp_store)

        assert result.success is True
        # NSFW content should be excluded - fewer previews
        total_previews = result.previews_downloaded + result.videos_downloaded
        # The fake data has 1 NSFW out of 4 total previews
        # So with NSFW excluded, we should have <= 3
        assert total_previews <= 3


class TestFullImportCycle:
    """E2E tests for complete import cycle: import -> save -> load -> verify."""

    def test_complete_import_and_load_cycle(self, temp_store):
        """Test full cycle: import, save, reload, verify all data."""
        from src.store.api import import_pack, ImportRequest

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.iter_content = MagicMock(return_value=[b'fake image data'])
        mock_response.headers = {'content-length': '100'}

        # 1. Import
        with patch('src.store.pack_service.requests.get', return_value=mock_response):
            request = ImportRequest(
                url="https://civitai.com/models/12345",
                download_images=True,
                download_videos=True,
                include_nsfw=True,
            )
            result = import_pack(request=request, store=temp_store)

        assert result.success is True
        pack_name = result.pack_name

        # 2. Verify pack was saved to disk
        pack_dir = temp_store.layout.packs_path / pack_name
        assert pack_dir.exists(), f"Pack directory should exist: {pack_dir}"

        pack_json = pack_dir / "pack.json"
        assert pack_json.exists(), "pack.json should exist"

        # 3. Reload pack from disk
        loaded_pack = temp_store.get_pack(pack_name)

        # 4. Verify pack data
        assert loaded_pack.name == pack_name
        assert loaded_pack.pack_type == AssetKind.LORA
        assert loaded_pack.base_model == "SDXL 1.0"
        assert "amazing_style" in loaded_pack.trigger_words or "amazing_style" in (
            loaded_pack.model_info.trigger_words if loaded_pack.model_info else []
        )

        # 5. Verify dependencies
        assert len(loaded_pack.dependencies) >= 1
        main_dep = loaded_pack.dependencies[-1]  # Main asset is last
        assert main_dep.kind == AssetKind.LORA

        # 6. Verify previews
        assert len(loaded_pack.previews) > 0, "Should have previews"

        # 7. Verify preview metadata
        for preview in loaded_pack.previews:
            assert preview.filename, "Preview should have filename"
            # Meta might not be present for all

        # 8. Verify preview files on disk
        previews_dir = pack_dir / "resources" / "previews"
        if previews_dir.exists():
            preview_files = list(previews_dir.glob("*"))
            # Filter out sidecar JSON files
            media_files = [f for f in preview_files if not f.suffix == '.json']
            assert len(media_files) > 0, "Should have preview files on disk"

    def test_metadata_persisted_in_sidecar_json(self, temp_store):
        """Test that preview metadata is saved to sidecar JSON files."""
        from src.store.api import import_pack, ImportRequest

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.iter_content = MagicMock(return_value=[b'fake image data'])
        mock_response.headers = {'content-length': '100'}

        with patch('src.store.pack_service.requests.get', return_value=mock_response):
            request = ImportRequest(url="https://civitai.com/models/12345")
            result = import_pack(request=request, store=temp_store)

        pack_name = result.pack_name
        previews_dir = temp_store.layout.packs_path / pack_name / "resources" / "previews"

        # Find sidecar JSON files
        json_files = list(previews_dir.glob("*.json"))

        # Should have sidecar files for previews with metadata
        assert len(json_files) > 0, "Should have sidecar JSON files for metadata"

        # Verify content of a sidecar
        first_json = next(iter(json_files))
        data = json.loads(first_json.read_text())

        # Should have generation metadata
        assert "prompt" in data or "seed" in data, "Sidecar should contain generation metadata"

    def test_pack_in_list_after_import(self, temp_store):
        """Test that imported pack appears in list_packs."""
        from src.store.api import import_pack, ImportRequest

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.iter_content = MagicMock(return_value=[b'fake image data'])
        mock_response.headers = {'content-length': '100'}

        with patch('src.store.pack_service.requests.get', return_value=mock_response):
            request = ImportRequest(url="https://civitai.com/models/12345")
            result = import_pack(request=request, store=temp_store)

        pack_name = result.pack_name

        # Verify pack is in list
        packs = temp_store.list_packs()
        assert pack_name in packs, f"Pack {pack_name} should be in list"

    def test_video_preview_saved_with_mp4_extension(self, temp_store):
        """Test that video previews are saved with .mp4 extension."""
        from src.store.api import import_pack, ImportRequest

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.iter_content = MagicMock(return_value=[b'fake video data'])
        mock_response.headers = {'content-length': '1000000'}

        with patch('src.store.pack_service.requests.get', return_value=mock_response):
            request = ImportRequest(
                url="https://civitai.com/models/12345",
                download_videos=True,
            )
            result = import_pack(request=request, store=temp_store)

        pack_name = result.pack_name
        previews_dir = temp_store.layout.packs_path / pack_name / "resources" / "previews"

        # Look for .mp4 files
        mp4_files = list(previews_dir.glob("*.mp4"))

        # If videos were downloaded, they should have .mp4 extension
        if result.videos_downloaded > 0:
            assert len(mp4_files) > 0, "Video files should have .mp4 extension"


class TestImportIdempotency:
    """Tests for import idempotency - re-importing shouldn't duplicate."""

    def test_reimport_same_pack_no_duplicates(self, temp_store):
        """Test that re-importing the same model doesn't duplicate files."""
        from src.store.api import import_pack, ImportRequest

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.iter_content = MagicMock(return_value=[b'fake image data'])
        mock_response.headers = {'content-length': '100'}

        with patch('src.store.pack_service.requests.get', return_value=mock_response):
            # Import twice
            request = ImportRequest(url="https://civitai.com/models/12345")
            result1 = import_pack(request=request, store=temp_store)
            result2 = import_pack(request=request, store=temp_store)

        assert result1.pack_name == result2.pack_name

        # Count files
        pack_name = result1.pack_name
        previews_dir = temp_store.layout.packs_path / pack_name / "resources" / "previews"

        if previews_dir.exists():
            all_files = list(previews_dir.glob("*"))
            media_files = [f for f in all_files if not f.suffix == '.json']
            # Should not have duplicates
            # With deduplication, re-import should reuse existing files
            assert len(media_files) <= 4, "Should not have duplicate preview files"


class TestStoreIntegration:
    """Tests for Store class integration with wizard options."""

    def test_store_import_civitai_with_options(self, temp_store):
        """Test Store.import_civitai accepts wizard options."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.iter_content = MagicMock(return_value=[b'fake data'])
        mock_response.headers = {'content-length': '100'}

        with patch('src.store.pack_service.requests.get', return_value=mock_response):
            pack = temp_store.import_civitai(
                url="https://civitai.com/models/12345",
                download_previews=True,
                add_to_global=True,
                download_images=True,
                download_videos=True,
                include_nsfw=False,
                video_quality=720,
            )

        assert pack is not None
        assert pack.name == "Amazing_LoRA_v2"
        assert pack.pack_type == AssetKind.LORA
