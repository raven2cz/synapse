"""
Integration Tests for DownloadService Consolidation

Tests the interaction between DownloadService and its consumers:
- BlobStore delegates HTTP downloads to DownloadService
- PackService uses DownloadService for preview downloads
- CivitaiClient delegates downloads when DownloadService is provided
- Store wires DownloadService to all consumers correctly
- CivitaiUpdateProvider model cache lifecycle with UpdateService
- Full check-all-updates flow with deduplication

Author: Synapse Team
License: MIT
"""

import hashlib
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, call

from src.store.download_service import DownloadService, DownloadResult, DownloadError
from src.store.download_auth import CivitaiAuthProvider, DownloadAuthProvider
from src.store.blob_store import BlobStore, DownloadError as BlobDownloadError, HashMismatchError
from src.store.civitai_update_provider import CivitaiUpdateProvider


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def civitai_auth():
    """CivitaiAuthProvider with test API key."""
    return CivitaiAuthProvider(api_key="test-key-12345")


@pytest.fixture
def download_service(civitai_auth):
    """DownloadService with Civitai auth."""
    return DownloadService(auth_providers=[civitai_auth])


@pytest.fixture
def temp_store_dir(tmp_path):
    """Create a temporary store directory structure."""
    store_root = tmp_path / "store"
    blobs_dir = store_root / "blobs"
    tmp_dir = store_root / "tmp"
    packs_dir = store_root / "packs"
    blobs_dir.mkdir(parents=True)
    tmp_dir.mkdir(parents=True)
    packs_dir.mkdir(parents=True)
    return store_root


# ============================================================================
# BlobStore + DownloadService Integration
# ============================================================================

class TestBlobStoreDownloadDelegation:
    """Tests that BlobStore correctly delegates HTTP downloads to DownloadService."""

    def test_download_http_delegates_to_service(self, tmp_path):
        """BlobStore._download_http() should call DownloadService.download_to_file()."""
        mock_ds = MagicMock(spec=DownloadService)
        file_content = b"blob content for test"
        sha256 = hashlib.sha256(file_content).hexdigest()
        mock_ds.download_to_file.return_value = DownloadResult(sha256=sha256, size=len(file_content))

        from src.store.layout import StoreLayout
        layout = StoreLayout(tmp_path / "store")
        layout.init_store()

        blob_store = BlobStore(layout, api_key="test-key", download_service=mock_ds)

        # Create a fake part file so finalization works
        part_path = layout.blob_part_path(sha256)
        part_path.parent.mkdir(parents=True, exist_ok=True)
        part_path.write_bytes(file_content)

        result = blob_store._download_http(
            "https://civitai.com/api/download/models/123",
            expected_sha256=sha256,
        )

        # Verify delegation
        mock_ds.download_to_file.assert_called_once()
        call_kwargs = mock_ds.download_to_file.call_args
        assert call_kwargs[0][0] == "https://civitai.com/api/download/models/123"
        assert call_kwargs[1]["expected_sha256"] == sha256
        assert call_kwargs[1]["resume"] is True

        # Verify blob was finalized
        assert result == sha256

    def test_download_http_uses_store_timeout(self, tmp_path):
        """BlobStore should pass self.timeout (not hardcoded 60) to DownloadService."""
        mock_ds = MagicMock(spec=DownloadService)
        sha256 = "a" * 64
        mock_ds.download_to_file.return_value = DownloadResult(sha256=sha256, size=100)

        from src.store.layout import StoreLayout
        layout = StoreLayout(tmp_path / "store")
        layout.init_store()

        blob_store = BlobStore(layout, api_key="test-key", download_service=mock_ds)
        # Default timeout is 300
        assert blob_store.timeout == 300

        # Create part file for finalization
        part_path = layout.blob_part_path(sha256)
        part_path.parent.mkdir(parents=True, exist_ok=True)
        part_path.write_bytes(b"data")

        blob_store._download_http("https://example.com/file", expected_sha256=sha256)

        call_kwargs = mock_ds.download_to_file.call_args[1]
        assert call_kwargs["timeout"] == (15, 300), "Should use self.timeout, not hardcoded 60"

    def test_download_hash_mismatch_raises_blob_error(self, tmp_path):
        """Hash mismatch from DownloadService maps to HashMismatchError."""
        mock_ds = MagicMock(spec=DownloadService)
        mock_ds.download_to_file.side_effect = DownloadError(
            "Hash mismatch for url: expected abc, got def"
        )

        from src.store.layout import StoreLayout
        layout = StoreLayout(tmp_path / "store")
        layout.init_store()

        blob_store = BlobStore(layout, download_service=mock_ds)

        with pytest.raises(HashMismatchError, match="Hash mismatch"):
            blob_store._download_http("https://example.com/file", expected_sha256="abc")

    def test_download_network_error_raises_blob_download_error(self, tmp_path):
        """Network errors from DownloadService map to BlobStore DownloadError."""
        mock_ds = MagicMock(spec=DownloadService)
        mock_ds.download_to_file.side_effect = DownloadError(
            "Download failed for url: Connection refused"
        )

        from src.store.layout import StoreLayout
        layout = StoreLayout(tmp_path / "store")
        layout.init_store()

        blob_store = BlobStore(layout, download_service=mock_ds)

        with pytest.raises(BlobDownloadError, match="Connection refused"):
            blob_store._download_http("https://example.com/file")

    def test_download_without_sha256_uses_temp_path(self, tmp_path):
        """When no expected_sha256, BlobStore should use tmp path for download."""
        mock_ds = MagicMock(spec=DownloadService)
        sha256 = "b" * 64
        mock_ds.download_to_file.return_value = DownloadResult(sha256=sha256, size=50)

        from src.store.layout import StoreLayout
        layout = StoreLayout(tmp_path / "store")
        layout.init_store()

        blob_store = BlobStore(layout, download_service=mock_ds)

        # Create the temp download file at the path DownloadService will use
        call_args = None
        def capture_call(url, dest, **kwargs):
            nonlocal call_args
            call_args = (url, dest)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"test data")
            return DownloadResult(sha256=sha256, size=50)

        mock_ds.download_to_file.side_effect = capture_call

        result = blob_store._download_http("https://example.com/file")

        assert result == sha256
        # The dest path should be in tmp, not in blobs
        assert "tmp" in str(call_args[1]) or "download_" in str(call_args[1].name)


# ============================================================================
# PackService + DownloadService Integration
# ============================================================================

class TestPackServiceDownloadIntegration:
    """Tests PackService preview downloads via DownloadService."""

    def test_pack_service_receives_download_service(self, tmp_path):
        """PackService should store the download service reference."""
        from src.store.layout import StoreLayout
        from src.store.pack_service import PackService

        layout = StoreLayout(tmp_path / "store")
        layout.init_store()

        mock_ds = MagicMock(spec=DownloadService)
        mock_blob_store = MagicMock()

        ps = PackService(layout, mock_blob_store, None, None, download_service=mock_ds)
        assert ps._download_service is mock_ds

    def test_pack_service_without_download_service(self, tmp_path):
        """PackService should work without DownloadService (fallback)."""
        from src.store.layout import StoreLayout
        from src.store.pack_service import PackService

        layout = StoreLayout(tmp_path / "store")
        layout.init_store()

        mock_blob_store = MagicMock()

        ps = PackService(layout, mock_blob_store, None, None)
        assert ps._download_service is None


# ============================================================================
# CivitaiClient + DownloadService Delegation
# ============================================================================

class TestCivitaiClientDelegation:
    """Tests CivitaiClient delegation to DownloadService."""

    def test_download_file_delegates_to_service(self, tmp_path):
        """CivitaiClient.download_file() should delegate when download_service is provided."""
        from src.clients.civitai_client import CivitaiClient

        client = CivitaiClient(api_key="test-key")
        mock_ds = MagicMock(spec=DownloadService)
        mock_ds.download_to_file.return_value = DownloadResult(sha256="abc123", size=1000)

        dest = tmp_path / "model.safetensors"
        result = client.download_file(
            "https://civitai.com/api/download/models/123",
            dest,
            download_service=mock_ds,
        )

        assert result is True
        mock_ds.download_to_file.assert_called_once()

    def test_download_file_returns_false_on_service_error(self, tmp_path):
        """CivitaiClient.download_file() returns False when DownloadService fails."""
        from src.clients.civitai_client import CivitaiClient

        client = CivitaiClient(api_key="test-key")
        mock_ds = MagicMock(spec=DownloadService)
        mock_ds.download_to_file.side_effect = DownloadError("Failed")

        dest = tmp_path / "model.safetensors"
        result = client.download_file(
            "https://civitai.com/api/download/models/123",
            dest,
            download_service=mock_ds,
        )

        assert result is False

    def test_download_preview_delegates_to_service(self, tmp_path):
        """CivitaiClient.download_preview_image() delegates to DownloadService."""
        from src.clients.civitai_client import CivitaiClient
        from src.core.models import PreviewImage

        client = CivitaiClient(api_key="test-key")
        mock_ds = MagicMock(spec=DownloadService)
        mock_ds.download_to_bytes.return_value = b"fake image data"

        preview = PreviewImage(
            filename="preview.jpeg",
            url="https://image.civitai.com/preview.jpeg",
            nsfw=False,
        )
        dest = tmp_path / "preview.jpeg"
        result = client.download_preview_image(preview, dest, download_service=mock_ds)

        assert result is True
        mock_ds.download_to_bytes.assert_called_once_with("https://image.civitai.com/preview.jpeg")
        assert dest.read_bytes() == b"fake image data"


# ============================================================================
# Store Wiring
# ============================================================================

class TestStoreWiring:
    """Tests that Store correctly wires DownloadService to all consumers."""

    def test_store_creates_download_service(self, tmp_path):
        """Store.__init__ should create a DownloadService."""
        from src.store import Store

        store = Store(root=tmp_path / "store", civitai_api_key="test-key-123")
        assert store.download_service is not None
        assert isinstance(store.download_service, DownloadService)

    def test_store_wires_auth_provider(self, tmp_path):
        """Store's DownloadService should have CivitaiAuthProvider."""
        from src.store import Store

        store = Store(root=tmp_path / "store", civitai_api_key="test-key-123")
        providers = store.download_service._auth_providers
        assert len(providers) >= 1
        assert isinstance(providers[0], CivitaiAuthProvider)

    def test_store_passes_service_to_blob_store(self, tmp_path):
        """Store should pass DownloadService to BlobStore."""
        from src.store import Store

        store = Store(root=tmp_path / "store", civitai_api_key="test-key-123")
        assert store.blob_store._download_service is store.download_service

    def test_store_passes_service_to_pack_service(self, tmp_path):
        """Store should pass DownloadService to PackService."""
        from src.store import Store

        store = Store(root=tmp_path / "store", civitai_api_key="test-key-123")
        assert store.pack_service._download_service is store.download_service

    def test_store_without_api_key_still_creates_service(self, tmp_path):
        """Store creates DownloadService even without API key."""
        from src.store import Store

        fake_civitai = MagicMock()
        store = Store(root=tmp_path / "store", civitai_client=fake_civitai)
        assert store.download_service is not None
        # Auth provider should have None key
        assert len(store.download_service._auth_providers) >= 1


# ============================================================================
# CivitaiUpdateProvider Model Cache Integration
# ============================================================================

class TestModelCacheIntegration:
    """Tests CivitaiUpdateProvider model cache with UpdateService lifecycle."""

    def _make_model_data(self, model_id, version_id=100):
        """Create realistic model data for testing."""
        return {
            "id": model_id,
            "name": f"TestModel_{model_id}",
            "modelVersions": [
                {
                    "id": version_id,
                    "name": "v1.0",
                    "baseModel": "SDXL 1.0",
                    "files": [
                        {
                            "id": 200,
                            "name": "model.safetensors",
                            "primary": True,
                            "sizeKB": 1024000,
                            "hashes": {"SHA256": "abcdef1234567890"},
                            "downloadUrl": f"https://civitai.com/api/download/models/{version_id}",
                        }
                    ],
                    "images": [],
                    "trainedWords": ["test_word"],
                }
            ],
        }

    def test_cache_deduplicates_api_calls(self):
        """Same model_id should only call API once."""
        mock_civitai = MagicMock()
        mock_civitai.get_model.return_value = self._make_model_data(12345)

        provider = CivitaiUpdateProvider(mock_civitai)

        # First call should hit API
        result1 = provider.get_model_cached(12345)
        assert mock_civitai.get_model.call_count == 1

        # Second call should hit cache
        result2 = provider.get_model_cached(12345)
        assert mock_civitai.get_model.call_count == 1  # No new call

        # Results should be identical
        assert result1 is result2

    def test_different_models_call_api_separately(self):
        """Different model IDs should each make their own API call."""
        mock_civitai = MagicMock()
        mock_civitai.get_model.side_effect = lambda mid: self._make_model_data(mid)

        provider = CivitaiUpdateProvider(mock_civitai)

        provider.get_model_cached(100)
        provider.get_model_cached(200)
        provider.get_model_cached(100)  # cache hit
        provider.get_model_cached(200)  # cache hit
        provider.get_model_cached(300)

        assert mock_civitai.get_model.call_count == 3

    def test_clear_cache_forces_fresh_calls(self):
        """clear_cache() should force API calls on next access."""
        mock_civitai = MagicMock()
        mock_civitai.get_model.return_value = self._make_model_data(12345)

        provider = CivitaiUpdateProvider(mock_civitai)

        provider.get_model_cached(12345)
        assert mock_civitai.get_model.call_count == 1

        provider.clear_cache()

        provider.get_model_cached(12345)
        assert mock_civitai.get_model.call_count == 2

    def test_check_update_uses_cache(self):
        """check_update() should use cached model data."""
        mock_civitai = MagicMock()
        model_data = self._make_model_data(12345, version_id=100)
        mock_civitai.get_model.return_value = model_data

        provider = CivitaiUpdateProvider(mock_civitai)

        # Pre-populate cache
        provider.get_model_cached(12345)

        # Build dependency that references this model
        from src.store.models import (
            PackDependency, ResolvedDependency, DependencySelector,
            CivitaiSelector, SelectorStrategy, ResolvedArtifact,
            ArtifactProvider, ArtifactIntegrity, ExposeConfig,
        )

        dep = PackDependency(
            id="test-lora",
            kind="lora",
            selector=DependencySelector(
                strategy=SelectorStrategy.CIVITAI_MODEL_LATEST,
                civitai=CivitaiSelector(model_id=12345),
            ),
            expose=ExposeConfig(filename="model.safetensors"),
        )

        current = ResolvedDependency(
            dependency_id="test-lora",
            artifact=ResolvedArtifact(
                kind="lora",
                provider=ArtifactProvider(
                    name="civitai",
                    model_id=12345,
                    version_id=100,  # Same as latest
                    filename="model.safetensors",
                ),
                sha256="abcdef1234567890",
                size_bytes=1024000 * 1024,
            ),
        )

        result = provider.check_update(dep, current)

        # Should use cached data, no new API call
        assert mock_civitai.get_model.call_count == 1
        assert result is not None
        assert result.has_update is False  # Already on latest version


# ============================================================================
# UpdateService + Cache Clearing Lifecycle
# ============================================================================

class TestUpdateServiceCacheLifecycle:
    """Tests that UpdateService properly clears provider caches."""

    def test_check_all_clears_cache_before_and_after(self, tmp_path):
        """check_all_updates() should clear caches before and after the loop."""
        from src.store.layout import StoreLayout
        from src.store.update_service import UpdateService
        from src.store.models import SelectorStrategy

        layout = StoreLayout(tmp_path / "store")
        layout.init_store()

        mock_provider = MagicMock()
        mock_provider.clear_cache = MagicMock()

        mock_blob_store = MagicMock()
        mock_view_builder = MagicMock()

        service = UpdateService(
            layout, mock_blob_store, mock_view_builder,
            providers={SelectorStrategy.CIVITAI_MODEL_LATEST: mock_provider},
        )

        # No packs → empty loop, but cache should still be cleared
        result = service.check_all_updates()

        assert mock_provider.clear_cache.call_count == 2
        assert result == {}

    def test_check_all_clears_cache_even_on_pack_error(self, tmp_path):
        """Cache should be cleared even if individual pack checks fail."""
        from src.store.layout import StoreLayout
        from src.store.update_service import UpdateService
        from src.store.models import SelectorStrategy, Pack, PackSource, AssetKind

        layout = StoreLayout(tmp_path / "store")
        layout.init_store()

        # Create a pack that will cause an error during check
        pack_dir = layout.packs_path / "broken_pack"
        pack_dir.mkdir(parents=True)
        import json
        pack_json = pack_dir / "pack.json"
        pack_json.write_text(json.dumps({
            "name": "broken_pack",
            "pack_type": "lora",
            "dependencies": [],
            "source": {"provider": "civitai", "model_id": 999},
        }))

        mock_provider = MagicMock()
        mock_provider.clear_cache = MagicMock()

        mock_blob_store = MagicMock()
        mock_view_builder = MagicMock()

        service = UpdateService(
            layout, mock_blob_store, mock_view_builder,
            providers={SelectorStrategy.CIVITAI_MODEL_LATEST: mock_provider},
        )

        result = service.check_all_updates()

        # Cache should still be cleared twice (before + after)
        assert mock_provider.clear_cache.call_count == 2


# ============================================================================
# Auth Flow Integration
# ============================================================================

class TestAuthFlowIntegration:
    """Tests auth provider matching and header injection end-to-end."""

    def test_civitai_url_gets_token_in_url(self):
        """Civitai URLs should get ?token= injected into URL."""
        auth = CivitaiAuthProvider(api_key="my-secret-key")
        service = DownloadService(auth_providers=[auth])

        url, headers, matched = service._prepare_auth(
            "https://civitai.com/api/download/models/123"
        )

        assert matched is auth
        assert "token=my-secret-key" in url
        assert headers == {}  # No Bearer header (stripped on redirect)

    def test_civitai_url_replaces_old_token(self):
        """Legacy ?token= should be replaced with fresh API key."""
        auth = CivitaiAuthProvider(api_key="my-secret-key")
        service = DownloadService(auth_providers=[auth])

        url, headers, matched = service._prepare_auth(
            "https://civitai.com/api/download/models/123?token=old-token"
        )

        assert "token=old-token" not in url
        assert "token=my-secret-key" in url

    def test_non_civitai_url_no_auth(self):
        """Non-Civitai URLs should not get auth."""
        auth = CivitaiAuthProvider(api_key="my-secret-key")
        service = DownloadService(auth_providers=[auth])

        url, headers, matched = service._prepare_auth(
            "https://huggingface.co/models/some-model"
        )

        assert matched is None
        assert len(headers) == 0
        assert "token=" not in url

    def test_auth_without_api_key(self):
        """CivitaiAuthProvider without key should match but not inject token."""
        auth = CivitaiAuthProvider(api_key=None)
        service = DownloadService(auth_providers=[auth])

        url, headers, matched = service._prepare_auth(
            "https://civitai.com/api/download/models/123"
        )

        assert matched is auth
        assert headers == {}
        assert "token=" not in url


# ============================================================================
# End-to-End Download Flow (with mocked HTTP)
# ============================================================================

class TestDownloadFlowE2E:
    """Tests complete download flows with mocked HTTP."""

    def test_blob_store_download_and_finalize(self, tmp_path):
        """Full flow: BlobStore → DownloadService → finalize to blob path."""
        from src.store.layout import StoreLayout

        layout = StoreLayout(tmp_path / "store")
        layout.init_store()

        file_content = b"model weights data here"
        sha256 = hashlib.sha256(file_content).hexdigest()

        # Create a real DownloadService
        auth = CivitaiAuthProvider(api_key="test-key")
        ds = DownloadService(auth_providers=[auth])

        blob_store = BlobStore(layout, api_key="test-key", download_service=ds)

        # Mock the HTTP call
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-length": str(len(file_content)), "content-type": "application/octet-stream"}
        mock_response.iter_content.return_value = [file_content]
        mock_response.raise_for_status = MagicMock()

        mock_session = MagicMock()
        mock_session.get.return_value = mock_response
        mock_session.headers = {}

        with patch("src.store.download_service.requests.Session", return_value=mock_session):
            result_sha = blob_store._download_http(
                "https://civitai.com/api/download/models/123",
                expected_sha256=sha256,
            )

        # Verify blob was stored correctly
        assert result_sha == sha256
        blob_path = blob_store.blob_path(sha256)
        assert blob_path.exists()
        assert blob_path.read_bytes() == file_content

        # Verify auth was injected via ?token= in URL (not Authorization header)
        get_call = mock_session.get.call_args
        called_url = get_call[0][0] if get_call[0] else get_call[1].get("url", "")
        assert "token=test-key" in called_url, \
            f"Expected ?token= in download URL, got: {called_url}"

    def test_preview_download_with_auth(self, tmp_path):
        """Preview downloads through DownloadService get auth injection."""
        auth = CivitaiAuthProvider(api_key="nsfw-key")
        ds = DownloadService(auth_providers=[auth])

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"preview image bytes"
        mock_response.headers = {"content-type": "image/jpeg"}
        mock_response.raise_for_status = MagicMock()

        mock_session = MagicMock()
        mock_session.get.return_value = mock_response
        mock_session.headers = {}

        with patch("src.store.download_service.requests.Session", return_value=mock_session):
            data = ds.download_to_bytes(
                "https://image.civitai.com/preview.jpeg"
            )

        assert data == b"preview image bytes"

        # Verify auth was injected via ?token= in URL for Civitai image CDN
        get_call = mock_session.get.call_args
        called_url = get_call[0][0] if get_call[0] else get_call[1].get("url", "")
        assert "token=nsfw-key" in called_url, \
            f"Expected ?token= in download URL, got: {called_url}"
