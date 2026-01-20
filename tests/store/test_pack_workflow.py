
import pytest
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.store.models import (
    Pack, AssetKind, PackSource, ProviderName, PackDependency,
    DependencySelector, SelectorStrategy, UpdatePolicy, ExposeConfig,
    PackResources, PreviewInfo
)
from src.store import PackService, StoreLayout, BlobStore

@pytest.fixture
def mock_layout(tmp_path):
    layout = StoreLayout(root=tmp_path / "synapse_root")
    layout.init_store()
    return layout

@pytest.fixture
def mock_blob_store(mock_layout):
    return BlobStore(mock_layout)

@pytest.fixture
def pack_service(mock_layout, mock_blob_store):
    return PackService(mock_layout, mock_blob_store, civitai_client=MagicMock())

def test_e2e_resolve_install_flow(pack_service, mock_layout, mock_blob_store):
    """
    Test 1: One E2E test in backend:
    simulate pack needing base model -> call resolve endpoint -> then install
    assert lock updated + blob present
    """
    # 1. Setup: Create a pack with a dependency
    pack_name = "test_pack_workflow"
    dep_id = "main_checkpoint"
    
    # Mock download to avoid network calls
    with patch("src.store.pack_service.PackService._resolve_url") as mock_resolve, \
         patch("src.store.pack_service.PackService._download_previews", return_value=[]):
        
        # Setup mock resolution return
        from src.store.models import ResolvedArtifact, ArtifactProvider, ArtifactDownload, ArtifactIntegrity
        mock_resolve.return_value = ResolvedArtifact(
            kind=AssetKind.CHECKPOINT,
            sha256="test_sha256_hash_123",
            size_bytes=1024,
            provider=ArtifactProvider(name=ProviderName.URL),
            download=ArtifactDownload(urls=["http://example.com/model.safetensors"]),
            integrity=ArtifactIntegrity(sha256_verified=True)
        )

        pack = Pack(
            name=pack_name,
            pack_type=AssetKind.CHECKPOINT,
            source=PackSource(provider=ProviderName.URL, url="http://example.com"),
            dependencies=[
                PackDependency(
                    id=dep_id,
                    kind=AssetKind.CHECKPOINT,
                    required=True,
                    selector=DependencySelector(
                        strategy=SelectorStrategy.URL_DOWNLOAD,
                        url="http://example.com/model.safetensors"
                    ),
                    update_policy=UpdatePolicy(),
                    expose=ExposeConfig(filename="model.safetensors")
                )
            ]
        )
        mock_layout.save_pack(pack)
        
        # 2. Resolve
        lock = pack_service.resolve_pack(pack_name)
        
        # Assert lock is updated and resolved
        assert lock.pack == pack_name
        assert len(lock.resolved) == 1
        assert lock.resolved[0].dependency_id == dep_id
        assert lock.resolved[0].artifact.sha256 == "test_sha256_hash_123"
        
        # 3. Install
        # Mock blob store download
        mock_blob_store.download = MagicMock(return_value="test_sha256_hash_123")
        mock_blob_store.blob_exists = MagicMock(return_value=False)
        
        installed_hashes = pack_service.install_pack(pack_name)
        
        # 4. Assert blob present (simulated via mock check)
        assert "test_sha256_hash_123" in installed_hashes
        mock_blob_store.download.assert_called_once()


def test_metadata_persistence_in_pack_json(pack_service, mock_layout):
    """
    Test 3: Canonical meta: verify pack.json contains previews[].meta
    """
    pack_name = "test_pack_meta"
    
    # Mock Civitai client response
    version_data = {
        "images": [
            {
                "url": "http://example.com/image1.jpg",
                "nsfw": False,
                "width": 512,
                "height": 512,
                "meta": {"prompt": "masterpiece, best quality", "cfg": 7}
            }
        ],
        "files": [{"name": "test.safetensors", "id": 1}],
        "id": 100
    }
    
    # Mock requests.get to return fake image data
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.iter_content = MagicMock(return_value=[b'fake image data'])
    mock_response.headers = {'content-length': '100'}

    # Mock the internal helpers to focus on import logic
    with patch("src.store.pack_service.PackService.parse_civitai_url", return_value=(123, 456)), \
         patch("src.store.pack_service.PackService._sanitize_pack_name", return_value=pack_name), \
         patch("src.store.pack_service.PackService._create_initial_lock"), \
         patch("src.store.pack_service.requests.get", return_value=mock_response):

        # Mock save_pack_lock to avoid serialization of MagicMock lock
        mock_layout.save_pack_lock = MagicMock()

        pack_service.civitai.get_model = MagicMock(return_value={"name": "Test Model", "type": "Checkpoint"})
        pack_service.civitai.get_model_version = MagicMock(return_value=version_data)

        # Run import
        pack = pack_service.import_from_civitai("https://civitai.com/models/123", download_previews=True)
        
        # reload pack from disk to verify persistence
        saved_pack = mock_layout.load_pack(pack_name)
        
        # Assertions
        assert len(saved_pack.previews) == 1
        assert saved_pack.previews[0].filename == "image1.jpg"
        assert saved_pack.previews[0].meta is not None
        assert saved_pack.previews[0].meta["prompt"] == "masterpiece, best quality"
