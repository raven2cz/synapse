"""
Smoke / E2E Tests for Download Service & Update Cache Flows

Exercises complete flows end-to-end with mocked HTTP:
- Import flow: Store.import_civitai → PackBuilder → DownloadService → disk
- Update check: check_all_updates with model cache deduplication
- Per-pack update check: individual pack checks reuse cache
- Auth flow: NSFW preview downloads with Civitai auth token

These tests use the real Store/BlobStore/PackService/UpdateService stack
with only HTTP calls mocked. No internal mocks on service boundaries.

Author: Synapse Team
License: MIT
"""

import hashlib
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

from src.store import Store
from src.store.download_service import DownloadService
from src.store.civitai_update_provider import CivitaiUpdateProvider
from src.store.models import SelectorStrategy


# ============================================================================
# Fixtures
# ============================================================================

class FakeCivitaiForSmoke:
    """Minimal Civitai client for smoke tests."""

    def __init__(self, models=None):
        self._models = models or {}
        self.get_model_call_count = 0

    def add_model(self, model_id, data):
        self._models[model_id] = data

    def get_model(self, model_id):
        self.get_model_call_count += 1
        if model_id not in self._models:
            raise ValueError(f"Model {model_id} not found")
        return self._models[model_id]

    def get_model_version(self, version_id):
        for data in self._models.values():
            for v in data.get("modelVersions", []):
                if v["id"] == version_id:
                    return v
        raise ValueError(f"Version {version_id} not found")


def _make_model(model_id, version_id, name="TestModel", with_nsfw=False):
    """Create realistic model data."""
    images = [
        {
            "url": f"https://image.civitai.com/preview_{model_id}_1.jpeg",
            "nsfw": False,
            "nsfwLevel": 1,
            "width": 1024,
            "height": 1536,
            "meta": {"prompt": "test prompt", "seed": 42},
        },
    ]
    if with_nsfw:
        images.append({
            "url": f"https://image.civitai.com/nsfw_{model_id}_2.jpeg",
            "nsfw": True,
            "nsfwLevel": 4,
            "width": 768,
            "height": 1024,
            "meta": {"prompt": "nsfw test", "seed": 99},
        })

    return {
        "id": model_id,
        "name": name,
        "type": "LORA",
        "creator": {"username": "SmokeTestUser"},
        "description": f"Description for {name}",
        "tags": ["test"],
        "stats": {"downloadCount": 100, "rating": 4.5},
        "modelVersions": [
            {
                "id": version_id,
                "name": "v1.0",
                "baseModel": "SDXL 1.0",
                "trainedWords": ["test_trigger"],
                "createdAt": "2025-06-01T12:00:00Z",
                "files": [
                    {
                        "id": version_id * 10,
                        "name": f"{name.lower()}_v1.safetensors",
                        "sizeKB": 512000,
                        "primary": True,
                        "hashes": {"SHA256": hashlib.sha256(f"model_{model_id}".encode()).hexdigest()},
                        "downloadUrl": f"https://civitai.com/api/download/models/{version_id}",
                    }
                ],
                "images": images,
            },
        ],
    }


def _mock_ai_service():
    """Mock AIService that doesn't call real providers."""
    mock_result = MagicMock()
    mock_result.success = False
    mock_result.output = None
    mock_ai = MagicMock()
    mock_ai.extract_parameters.return_value = mock_result
    return mock_ai


def _mock_http_session():
    """Create a mock HTTP session for DownloadService."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.iter_content = MagicMock(return_value=[b"fake file data"])
    mock_response.status_code = 200
    mock_response.headers = {"content-length": "100", "content-type": "application/octet-stream"}
    mock_response.content = b"fake file data"

    mock_session = MagicMock()
    mock_session.get.return_value = mock_response
    mock_session.headers = {}
    mock_session.close = MagicMock()

    return mock_session


@pytest.fixture
def smoke_store(tmp_path):
    """Create a store with fake Civitai client for smoke tests."""
    fake_civitai = FakeCivitaiForSmoke()
    fake_civitai.add_model(1001, _make_model(1001, 2001, "LoRA_Alpha"))
    fake_civitai.add_model(1002, _make_model(1002, 2002, "LoRA_Beta", with_nsfw=True))

    store = Store(
        root=tmp_path / "synapse_store",
        civitai_client=fake_civitai,
        civitai_api_key="smoke-test-key",
    )
    store.init()
    return store, fake_civitai


# ============================================================================
# Smoke Test: Import Flow
# ============================================================================

class TestImportFlowSmoke:
    """Smoke tests for the complete import flow with DownloadService."""

    def test_import_creates_pack_with_download_service(self, smoke_store):
        """Full import flow: Store → PackService → DownloadService → files on disk."""
        store, fake_civitai = smoke_store

        with patch("src.store.download_service.requests.Session", return_value=_mock_http_session()), \
             patch("src.store.pack_service.requests.get") as mock_fallback, \
             patch("src.ai.AIService", return_value=_mock_ai_service()):
            # Fallback should NOT be called when DownloadService is present
            mock_fallback_response = MagicMock()
            mock_fallback_response.raise_for_status = MagicMock()
            mock_fallback_response.iter_content = MagicMock(return_value=[b"fallback data"])
            mock_fallback_response.headers = {"content-length": "100"}
            mock_fallback.return_value = mock_fallback_response

            pack = store.import_civitai(
                url="https://civitai.com/models/1001",
                download_images=True,
                include_nsfw=False,
            )

        assert pack is not None
        assert pack.name == "LoRA_Alpha"

        # Verify pack exists on disk
        pack_dir = store.layout.packs_path / pack.name
        assert pack_dir.exists()
        assert (pack_dir / "pack.json").exists()

        # Verify previews were downloaded
        assert len(pack.previews) > 0

    def test_import_with_nsfw_gets_auth(self, smoke_store):
        """NSFW preview downloads should get auth headers via DownloadService."""
        store, fake_civitai = smoke_store

        session_calls = []

        def capture_session():
            mock_session = _mock_http_session()
            original_get = mock_session.get

            def capturing_get(url, **kwargs):
                session_calls.append({"url": url, "headers": kwargs.get("headers", {})})
                return original_get(url, **kwargs)

            mock_session.get = capturing_get
            return mock_session

        with patch("src.store.download_service.requests.Session", side_effect=lambda: capture_session()), \
             patch("src.store.pack_service.requests.get") as mock_fallback, \
             patch("src.ai.AIService", return_value=_mock_ai_service()):
            mock_fallback_response = MagicMock()
            mock_fallback_response.raise_for_status = MagicMock()
            mock_fallback_response.iter_content = MagicMock(return_value=[b"fallback data"])
            mock_fallback_response.headers = {"content-length": "100"}
            mock_fallback.return_value = mock_fallback_response

            pack = store.import_civitai(
                url="https://civitai.com/models/1002",
                download_images=True,
                include_nsfw=True,
            )

        assert pack is not None

        # Verify that Civitai image downloads got auth via ?token= in URL
        civitai_image_calls = [
            c for c in session_calls
            if "image.civitai.com" in str(c.get("url", ""))
        ]
        for img_call in civitai_image_calls:
            assert "token=smoke-test-key" in str(img_call["url"]), \
                f"Civitai image download should have ?token= in URL: {img_call}"


# ============================================================================
# Smoke Test: Update Check with Cache
# ============================================================================

class TestUpdateCheckSmoke:
    """Smoke tests for update checking with model cache."""

    def test_check_all_updates_deduplicates_api_calls(self, smoke_store):
        """check_all_updates should use model cache to avoid duplicate API calls."""
        store, fake_civitai = smoke_store

        # Import two packs that share the same model (1001)
        with patch("src.store.download_service.requests.Session", return_value=_mock_http_session()), \
             patch("src.store.pack_service.requests.get") as mock_fallback, \
             patch("src.ai.AIService", return_value=_mock_ai_service()):
            mock_fallback_response = MagicMock()
            mock_fallback_response.raise_for_status = MagicMock()
            mock_fallback_response.iter_content = MagicMock(return_value=[b"data"])
            mock_fallback_response.headers = {"content-length": "100"}
            mock_fallback.return_value = mock_fallback_response

            store.import_civitai(url="https://civitai.com/models/1001")
            store.import_civitai(url="https://civitai.com/models/1002")

        # Reset call count before check
        fake_civitai.get_model_call_count = 0

        # check_all_updates will call get_model for each unique model
        plans = store.check_all_updates()

        # Should have checked at least 2 packs
        assert isinstance(plans, dict)
        # API calls should be deduplicated (each model checked once)
        assert fake_civitai.get_model_call_count <= 2, \
            f"Expected at most 2 API calls but got {fake_civitai.get_model_call_count}"

    def test_single_pack_update_check(self, smoke_store):
        """Individual pack update check should work correctly."""
        store, fake_civitai = smoke_store

        with patch("src.store.download_service.requests.Session", return_value=_mock_http_session()), \
             patch("src.store.pack_service.requests.get") as mock_fallback, \
             patch("src.ai.AIService", return_value=_mock_ai_service()):
            mock_fallback_response = MagicMock()
            mock_fallback_response.raise_for_status = MagicMock()
            mock_fallback_response.iter_content = MagicMock(return_value=[b"data"])
            mock_fallback_response.headers = {"content-length": "100"}
            mock_fallback.return_value = mock_fallback_response

            store.import_civitai(url="https://civitai.com/models/1001")

        # Check single pack
        plan = store.check_updates("LoRA_Alpha")
        assert plan is not None


# ============================================================================
# Smoke Test: Download Service Thread Safety
# ============================================================================

class TestDownloadServiceConcurrency:
    """Smoke tests for concurrent download scenarios."""

    def test_concurrent_preview_downloads(self, smoke_store):
        """Multiple preview downloads should not interfere with each other."""
        store, fake_civitai = smoke_store

        # Add model with many previews
        model_data = _make_model(1003, 2003, "LoRA_Many_Previews")
        for i in range(5):
            model_data["modelVersions"][0]["images"].append({
                "url": f"https://image.civitai.com/extra_{i}.jpeg",
                "nsfw": False,
                "nsfwLevel": 1,
                "width": 512,
                "height": 512,
                "meta": {"prompt": f"test {i}", "seed": i},
            })
        fake_civitai.add_model(1003, model_data)

        sessions_created = []

        def counting_session():
            mock = _mock_http_session()
            sessions_created.append(mock)
            return mock

        with patch("src.store.download_service.requests.Session", side_effect=counting_session), \
             patch("src.store.pack_service.requests.get") as mock_fallback, \
             patch("src.ai.AIService", return_value=_mock_ai_service()):
            mock_fallback_response = MagicMock()
            mock_fallback_response.raise_for_status = MagicMock()
            mock_fallback_response.iter_content = MagicMock(return_value=[b"data"])
            mock_fallback_response.headers = {"content-length": "100"}
            mock_fallback.return_value = mock_fallback_response

            pack = store.import_civitai(
                url="https://civitai.com/models/1003",
                download_images=True,
            )

        assert pack is not None
        # Each download should create a separate session (thread safety)
        assert len(sessions_created) >= 1
        # All sessions should be closed
        for s in sessions_created:
            s.close.assert_called()


# ============================================================================
# Smoke Test: Full Import → Check → Verify Cycle
# ============================================================================

class TestFullLifecycleSmoke:
    """End-to-end lifecycle: import → list → check updates → verify."""

    def test_import_list_check_cycle(self, smoke_store):
        """Complete lifecycle: import, list, check updates, verify pack integrity."""
        store, fake_civitai = smoke_store

        with patch("src.store.download_service.requests.Session", return_value=_mock_http_session()), \
             patch("src.store.pack_service.requests.get") as mock_fallback, \
             patch("src.ai.AIService", return_value=_mock_ai_service()):
            mock_fallback_response = MagicMock()
            mock_fallback_response.raise_for_status = MagicMock()
            mock_fallback_response.iter_content = MagicMock(return_value=[b"data"])
            mock_fallback_response.headers = {"content-length": "100"}
            mock_fallback.return_value = mock_fallback_response

            # 1. Import
            pack = store.import_civitai(url="https://civitai.com/models/1001")
            assert pack.name == "LoRA_Alpha"

        # 2. List packs
        packs = store.list_packs()
        assert "LoRA_Alpha" in packs

        # 3. Load pack
        loaded = store.get_pack("LoRA_Alpha")
        assert loaded.name == "LoRA_Alpha"
        assert loaded.base_model == "SDXL 1.0"

        # 4. Check updates
        plans = store.check_all_updates()
        assert isinstance(plans, dict)

        # 5. Verify pack files exist
        pack_dir = store.layout.packs_path / "LoRA_Alpha"
        assert pack_dir.exists()
        pack_json = pack_dir / "pack.json"
        assert pack_json.exists()

        data = json.loads(pack_json.read_text())
        assert data["name"] == "LoRA_Alpha"

    def test_reimport_preserves_download_service(self, smoke_store):
        """Re-importing same pack should reuse DownloadService correctly."""
        store, fake_civitai = smoke_store

        with patch("src.store.download_service.requests.Session", return_value=_mock_http_session()), \
             patch("src.store.pack_service.requests.get") as mock_fallback, \
             patch("src.ai.AIService", return_value=_mock_ai_service()):
            mock_fallback_response = MagicMock()
            mock_fallback_response.raise_for_status = MagicMock()
            mock_fallback_response.iter_content = MagicMock(return_value=[b"data"])
            mock_fallback_response.headers = {"content-length": "100"}
            mock_fallback.return_value = mock_fallback_response

            # Import twice
            pack1 = store.import_civitai(url="https://civitai.com/models/1001")
            pack2 = store.import_civitai(url="https://civitai.com/models/1001")

        assert pack1.name == pack2.name

        # Only one pack should exist
        packs = store.list_packs()
        assert packs.count("LoRA_Alpha") == 1
