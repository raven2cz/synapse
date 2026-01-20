import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
import json
import shutil
from src.store.pack_service import PackService
from src.store.models import AssetKind

class FakeCivitaiClient:
    def __init__(self):
        self.downloaded_previews = []

    def parse_civitai_url(self, url: str):
        """Parse Civitai URL to extract model_id and version_id."""
        import re
        # Extract model_id from URL like /models/123
        model_match = re.search(r'/models/(\d+)', url)
        model_id = int(model_match.group(1)) if model_match else 123

        # Extract version_id from URL like ?modelVersionId=456
        version_match = re.search(r'modelVersionId=(\d+)', url)
        version_id = int(version_match.group(1)) if version_match else None

        return model_id, version_id

    def get_model(self, model_id):
        # Build images list
        images = []
        for i in range(20):
            images.append({
                "url": f"http://test.com/img_{i}.jpg",
                "nsfw": i % 3 == 0,  # Some NSFW for testing
                "nsfwLevel": 3 if i % 3 == 0 else 1,
                "width": 512,
                "height": 512,
                "meta": {
                    "prompt": f"Test Prompt {i}",
                    "negativePrompt": "bad quality",
                    "sampler": "Euler a",
                    "cfgScale": 7,
                    "seed": 12345 + i,
                    "steps": 30
                }
            })

        return {
            "id": model_id,
            "name": f"TestModel_{model_id}",
            "type": "LORA",
            "modelVersions": [
                {"id": 100, "name": "v1.0", "images": images}  # Include images!
            ]
        }

    def get_model_version(self, version_id):
        images = []
        for i in range(20):
            images.append({
                "url": f"http://test.com/img_{i}.jpg",
                "nsfw": i % 3 == 0,  # Some NSFW for testing
                "nsfwLevel": 3 if i % 3 == 0 else 1,
                "width": 512,
                "height": 512,
                "meta": {
                    "prompt": f"Test Prompt {i}",
                    "negativePrompt": "bad quality",
                    "sampler": "Euler a",
                    "cfgScale": 7,
                    "seed": 12345 + i,
                    "steps": 30
                }
            })
        
        return {
            "id": version_id,
            "name": "v1.0",
            "files": [
                {
                    "id": 999,
                    "name": "model.safetensors",
                    "primary": True,
                    "hashes": {"SHA256": "fake_hash"},
                    "sizeKB": 1024,
                    "downloadUrl": "http://test.com/download"
                }
            ],
            "images": images,
            "trainedWords": ["trigger"]
        }
    
    def download_preview_image(self, img_obj, dest_path):
        # Create a dummy image file
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.touch()
        self.downloaded_previews.append(str(dest_path))

@pytest.fixture
def mock_layout(tmp_path):
    layout = MagicMock()
    layout.root = tmp_path
    
    # Mock pack paths
    def pack_previews_path(name):
        return tmp_path / "packs" / name / "resources" / "previews"
    
    def pack_exists(name):
        return (tmp_path / "packs" / name).exists()

    layout.pack_previews_path.side_effect = pack_previews_path
    layout.pack_exists.side_effect = pack_exists
    
    return layout

@pytest.fixture
def pack_service(mock_layout):
    client = FakeCivitaiClient()
    service = PackService(mock_layout, MagicMock(), civitai_client=client)
    return service

def test_import_civitai_downloads_all_version_images_and_merges_meta(pack_service, mock_layout):
    """Test that import fetches ALL images (mocked 20) and merges metadata into sidecars."""

    # Mock save_pack/lock to do nothing but satisfy calls
    mock_layout.save_pack = MagicMock()
    mock_layout.save_pack_lock = MagicMock()
    mock_layout.load_config = MagicMock()

    # Mock requests.get to return fake image data
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.iter_content = MagicMock(return_value=[b'fake image data'])
    mock_response.headers = {'content-length': '100'}

    with patch('src.store.pack_service.requests.get', return_value=mock_response):
        # Call import with max_previews=100 to ensure we get all 20
        pack = pack_service.import_from_civitai("https://civitai.com/models/123?modelVersionId=100", max_previews=100)

    # Check directory content
    pack_name = pack.name  # import_from_civitai returns Pack object
    previews_dir = mock_layout.root / "packs" / pack_name / "resources" / "previews"

    # 1. Assert we have 20 images
    images = list(previews_dir.glob("*.jpg"))
    assert len(images) == 20, f"Expected 20 images, found {len(images)}"

    # 2. Assert we have 20 sidecar jsons
    jsons = list(previews_dir.glob("*.json"))
    assert len(jsons) == 20, "Expected 20 sidecar JSONs"

    # 3. Verify content of a sidecar
    # Filename strategy might vary, but let's check one
    first_json = next(iter(jsons))
    data = json.loads(first_json.read_text())
    assert "prompt" in data
    assert data["prompt"].startswith("Test Prompt")

def test_import_is_idempotent_no_duplicate_previews(pack_service, mock_layout):
    """Test that re-importing the same model does not duplicate preview files."""

    mock_layout.save_pack = MagicMock()
    mock_layout.save_pack_lock = MagicMock()

    url = "https://civitai.com/models/123?modelVersionId=100"

    # Mock requests.get to return fake image data
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.iter_content = MagicMock(return_value=[b'fake image data'])
    mock_response.headers = {'content-length': '100'}

    with patch('src.store.pack_service.requests.get', return_value=mock_response):
        # Run twice
        pack1 = pack_service.import_from_civitai(url, max_previews=100)
        pack2 = pack_service.import_from_civitai(url, max_previews=100)

    pack_name = pack1.name  # import_from_civitai returns Pack object
    previews_dir = mock_layout.root / "packs" / pack_name / "resources" / "previews"

    # Assert still 20 images, not 40
    images = list(previews_dir.glob("*.jpg"))
    assert len(images) == 20, f"Expected 20 images after double import, found {len(images)}"


def test_pack_previews_include_nsfw_and_meta(pack_service, mock_layout):
    """Test that pack.previews includes correct nsfw flag and meta from Civitai API."""

    mock_layout.save_pack = MagicMock()
    mock_layout.save_pack_lock = MagicMock()
    mock_layout.load_config = MagicMock()

    # Mock requests.get to return fake image data
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.iter_content = MagicMock(return_value=[b'fake image data'])
    mock_response.headers = {'content-length': '100'}

    with patch('src.store.pack_service.requests.get', return_value=mock_response):
        pack = pack_service.import_from_civitai("https://civitai.com/models/123?modelVersionId=100", max_previews=100)

    # Check pack.previews has correct data (import_from_civitai returns Pack object)
    previews = pack.previews
    assert len(previews) == 20, f"Expected 20 previews in pack, found {len(previews)}"

    # Check NSFW flags (every 3rd image should be NSFW: 0, 3, 6, 9, 12, 15, 18)
    nsfw_count = sum(1 for p in previews if p.nsfw)
    assert nsfw_count == 7, f"Expected 7 NSFW previews, found {nsfw_count}"

    # Check meta is included
    for i, preview in enumerate(previews):
        assert preview.meta is not None, f"Preview {i} should have meta"
        assert "prompt" in preview.meta, f"Preview {i} meta should have prompt"


def test_no_api_comfyui_calls_exist_backend():
    """Verify backend doesn't call /api/comfyui endpoints (v2 architecture compliance)."""
    import os
    import subprocess
    
    # Get project root
    script_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.join(script_dir, "..", "..", "src")
    
    # Search for /api/comfyui in Python files
    result = subprocess.run(
        ["grep", "-r", "/api/comfyui", src_dir],
        capture_output=True,
        text=True
    )
    
    # Should not find any matches in src/ (excluding test files)
    matches = [line for line in result.stdout.strip().split('\n') if line and 'test' not in line.lower()]
    assert len(matches) == 0, f"Found /api/comfyui calls in backend:\n{chr(10).join(matches)}"


def test_list_packs_empty_returns_empty_list(mock_layout):
    """Test that list_packs returns empty list when no packs exist."""
    # Configure layout to return empty list
    mock_layout.list_packs = MagicMock(return_value=[])

    service = PackService(mock_layout, MagicMock())

    result = service.list_packs()

    assert result == [], f"Expected empty list, got {result}"
    mock_layout.list_packs.assert_called_once()


def test_list_packs_returns_pack_names(mock_layout):
    """Test that list_packs returns correct pack names from layout."""
    expected_packs = ["pack-a", "pack-b", "pack-c"]
    mock_layout.list_packs = MagicMock(return_value=expected_packs)

    service = PackService(mock_layout, MagicMock())

    result = service.list_packs()

    assert result == expected_packs
    mock_layout.list_packs.assert_called_once()


def test_no_api_comfyui_calls_exist_frontend():
    """Verify frontend uses correct /api/comfyui endpoints (v2 architecture).

    NOTE: /api/comfyui/models/* endpoints ARE valid v2 endpoints for local model scanning.
    This test verifies the endpoints are used correctly, not that they're absent.
    """
    import os
    import subprocess
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    web_src = os.path.join(script_dir, "..", "..", "apps", "web", "src")
    
    if not os.path.exists(web_src):
        pytest.skip("Frontend source not found")
    
    # Search for /api/comfyui in TypeScript/JavaScript files
    result = subprocess.run(
        ["grep", "-r", "/api/comfyui", web_src],
        capture_output=True,
        text=True
    )
    
    matches = result.stdout.strip().split('\n')
    matches = [m for m in matches if m]
    
    # Valid v2 ComfyUI endpoints (local model scanning)
    valid_patterns = [
        "/api/comfyui/models/checkpoints",
        "/api/comfyui/models/loras",
        "/api/comfyui/models/",
        "/api/comfyui/status",
        "/api/comfyui/folders",
    ]
    
    # Filter out valid v2 endpoint calls
    invalid_matches = []
    for m in matches:
        is_valid = any(pattern in m for pattern in valid_patterns)
        if not is_valid and m:
            invalid_matches.append(m)
    
    # All comfyui calls should be valid v2 endpoints
    assert len(invalid_matches) == 0, f"Found invalid /api/comfyui calls:\n{chr(10).join(invalid_matches)}"


# =============================================================================
# Download From All Versions Tests
# =============================================================================

class MultiVersionCivitaiClient:
    """
    Fake Civitai client that returns multiple versions with different images.
    Used to test the download_from_all_versions feature.
    """

    def __init__(self):
        self.downloaded_previews = []

    def get_model(self, model_id):
        """Return model with 3 versions, each with unique images."""
        return {
            "id": model_id,
            "name": f"MultiVersionModel_{model_id}",
            "type": "LORA",
            "modelVersions": [
                {
                    "id": 100,
                    "name": "v1.0",
                    "files": [
                        {
                            "id": 999,
                            "name": "model.safetensors",
                            "primary": True,
                            "hashes": {"SHA256": "fake_hash_v1"},
                            "sizeKB": 1024,
                            "downloadUrl": "http://test.com/download_v1"
                        }
                    ],
                    "images": [
                        {"url": "http://test.com/v1_img1.jpg", "width": 512, "height": 512},
                        {"url": "http://test.com/v1_img2.jpg", "width": 512, "height": 512},
                    ],
                    "trainedWords": ["trigger_v1"]
                },
                {
                    "id": 200,
                    "name": "v2.0",
                    "files": [
                        {
                            "id": 998,
                            "name": "model_v2.safetensors",
                            "primary": True,
                            "hashes": {"SHA256": "fake_hash_v2"},
                            "sizeKB": 2048,
                            "downloadUrl": "http://test.com/download_v2"
                        }
                    ],
                    "images": [
                        {"url": "http://test.com/v2_img1.jpg", "width": 512, "height": 512},
                        {"url": "http://test.com/v2_img2.jpg", "width": 512, "height": 512},
                    ],
                    "trainedWords": ["trigger_v2"]
                },
                {
                    "id": 300,
                    "name": "v3.0",
                    "files": [
                        {
                            "id": 997,
                            "name": "model_v3.safetensors",
                            "primary": True,
                            "hashes": {"SHA256": "fake_hash_v3"},
                            "sizeKB": 512,
                            "downloadUrl": "http://test.com/download_v3"
                        }
                    ],
                    "images": [
                        {"url": "http://test.com/v3_img1.jpg", "width": 512, "height": 512},
                    ],
                    "trainedWords": ["trigger_v3"]
                },
            ]
        }

    def get_model_version(self, version_id):
        """Return detailed version info with images."""
        version_map = {
            100: {
                "id": 100,
                "name": "v1.0",
                "files": [
                    {
                        "id": 999,
                        "name": "model.safetensors",
                        "primary": True,
                        "hashes": {"SHA256": "fake_hash_v1"},
                        "sizeKB": 1024,
                        "downloadUrl": "http://test.com/download_v1"
                    }
                ],
                "images": [
                    {"url": "http://test.com/v1_img1.jpg", "width": 512, "height": 512, "meta": {"prompt": "v1 prompt 1"}},
                    {"url": "http://test.com/v1_img2.jpg", "width": 512, "height": 512, "meta": {"prompt": "v1 prompt 2"}},
                ],
                "trainedWords": ["trigger_v1"]
            },
            200: {
                "id": 200,
                "name": "v2.0",
                "files": [
                    {
                        "id": 998,
                        "name": "model_v2.safetensors",
                        "primary": True,
                        "hashes": {"SHA256": "fake_hash_v2"},
                        "sizeKB": 2048,
                        "downloadUrl": "http://test.com/download_v2"
                    }
                ],
                "images": [
                    {"url": "http://test.com/v2_img1.jpg", "width": 512, "height": 512, "meta": {"prompt": "v2 prompt 1"}},
                    {"url": "http://test.com/v2_img2.jpg", "width": 512, "height": 512, "meta": {"prompt": "v2 prompt 2"}},
                ],
                "trainedWords": ["trigger_v2"]
            },
            300: {
                "id": 300,
                "name": "v3.0",
                "files": [
                    {
                        "id": 997,
                        "name": "model_v3.safetensors",
                        "primary": True,
                        "hashes": {"SHA256": "fake_hash_v3"},
                        "sizeKB": 512,
                        "downloadUrl": "http://test.com/download_v3"
                    }
                ],
                "images": [
                    {"url": "http://test.com/v3_img1.jpg", "width": 512, "height": 512, "meta": {"prompt": "v3 prompt 1"}},
                ],
                "trainedWords": ["trigger_v3"]
            },
        }
        return version_map.get(version_id, version_map[100])


@pytest.fixture
def multi_version_pack_service(mock_layout):
    """Pack service with multi-version mock client."""
    client = MultiVersionCivitaiClient()
    service = PackService(mock_layout, MagicMock(), civitai_client=client)
    return service


def test_download_from_all_versions_true_collects_all_images(multi_version_pack_service, mock_layout):
    """When download_from_all_versions=True, should download images from ALL versions."""
    from src.store.pack_service import PreviewDownloadConfig

    mock_layout.save_pack = MagicMock()
    mock_layout.save_pack_lock = MagicMock()

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.iter_content = MagicMock(return_value=[b'fake image data'])
    mock_response.headers = {'content-length': '100'}

    config = PreviewDownloadConfig(
        download_images=True,
        download_videos=True,
        include_nsfw=True,
        download_from_all_versions=True,  # Download from ALL versions
    )

    with patch('src.store.pack_service.requests.get', return_value=mock_response):
        pack = multi_version_pack_service.import_from_civitai(
            "https://civitai.com/models/123",
            max_previews=100,
            download_config=config,
        )

    # With all versions: v1(2) + v2(2) + v3(1) = 5 images
    assert len(pack.previews) == 5, f"Expected 5 previews from all versions, got {len(pack.previews)}"


def test_download_from_all_versions_false_collects_only_selected_version(multi_version_pack_service, mock_layout):
    """When download_from_all_versions=False, should only download from selected version."""
    from src.store.pack_service import PreviewDownloadConfig

    mock_layout.save_pack = MagicMock()
    mock_layout.save_pack_lock = MagicMock()

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.iter_content = MagicMock(return_value=[b'fake image data'])
    mock_response.headers = {'content-length': '100'}

    config = PreviewDownloadConfig(
        download_images=True,
        download_videos=True,
        include_nsfw=True,
        download_from_all_versions=False,  # Only selected version
    )

    with patch('src.store.pack_service.requests.get', return_value=mock_response):
        # Import specific version 100 (v1.0)
        pack = multi_version_pack_service.import_from_civitai(
            "https://civitai.com/models/123?modelVersionId=100",
            max_previews=100,
            download_config=config,
        )

    # Only v1 has 2 images
    assert len(pack.previews) == 2, f"Expected 2 previews from v1 only, got {len(pack.previews)}"


def test_cover_url_is_stored_in_pack(multi_version_pack_service, mock_layout):
    """Test that cover_url parameter is stored in pack model."""
    from src.store.pack_service import PreviewDownloadConfig

    mock_layout.save_pack = MagicMock()
    mock_layout.save_pack_lock = MagicMock()

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.iter_content = MagicMock(return_value=[b'fake image data'])
    mock_response.headers = {'content-length': '100'}

    config = PreviewDownloadConfig()

    selected_thumbnail = "http://test.com/v1_img2.jpg"

    with patch('src.store.pack_service.requests.get', return_value=mock_response):
        pack = multi_version_pack_service.import_from_civitai(
            "https://civitai.com/models/123",
            max_previews=100,
            download_config=config,
            cover_url=selected_thumbnail,
        )

    # Cover URL should be stored
    assert pack.cover_url == selected_thumbnail, f"Expected cover_url to be '{selected_thumbnail}', got '{pack.cover_url}'"


def test_cover_url_none_by_default(multi_version_pack_service, mock_layout):
    """Test that cover_url is None when not specified."""
    from src.store.pack_service import PreviewDownloadConfig

    mock_layout.save_pack = MagicMock()
    mock_layout.save_pack_lock = MagicMock()

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.iter_content = MagicMock(return_value=[b'fake image data'])
    mock_response.headers = {'content-length': '100'}

    config = PreviewDownloadConfig()

    with patch('src.store.pack_service.requests.get', return_value=mock_response):
        pack = multi_version_pack_service.import_from_civitai(
            "https://civitai.com/models/123",
            max_previews=100,
            download_config=config,
            # No cover_url specified
        )

    assert pack.cover_url is None, f"Expected cover_url to be None, got '{pack.cover_url}'"


# =============================================================================
# Multi-Version Dependency Tests (CRITICAL FEATURE)
# =============================================================================

def test_multi_version_import_creates_multiple_dependencies(multi_version_pack_service, mock_layout):
    """
    CRITICAL: When multiple version_ids are selected, ONE dependency should be
    created for EACH version. This is the core feature of multi-version import.
    """
    from src.store.pack_service import PreviewDownloadConfig

    mock_layout.save_pack = MagicMock()
    mock_layout.save_pack_lock = MagicMock()

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.iter_content = MagicMock(return_value=[b'fake image data'])
    mock_response.headers = {'content-length': '100'}

    config = PreviewDownloadConfig()

    # Select 3 versions (v1.0=100, v2.0=200, v3.0=300)
    selected_version_ids = [100, 200, 300]

    with patch('src.store.pack_service.requests.get', return_value=mock_response):
        pack = multi_version_pack_service.import_from_civitai(
            "https://civitai.com/models/123",
            max_previews=100,
            download_config=config,
            selected_version_ids=selected_version_ids,
        )

    # Should have 3 LORA dependencies (one per version) + possibly base model
    lora_deps = [d for d in pack.dependencies if d.kind.value == 'lora']

    assert len(lora_deps) == 3, f"Expected 3 LORA dependencies for 3 versions, got {len(lora_deps)}"

    # Verify each dependency points to correct version
    version_ids_in_deps = {d.selector.civitai.version_id for d in lora_deps if d.selector.civitai}
    assert version_ids_in_deps == {100, 200, 300}, f"Dependencies don't match selected versions: {version_ids_in_deps}"


def test_multi_version_import_creates_unique_dependency_ids(multi_version_pack_service, mock_layout):
    """Each dependency should have a unique ID."""
    from src.store.pack_service import PreviewDownloadConfig

    mock_layout.save_pack = MagicMock()
    mock_layout.save_pack_lock = MagicMock()

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.iter_content = MagicMock(return_value=[b'fake image data'])
    mock_response.headers = {'content-length': '100'}

    config = PreviewDownloadConfig()

    # Select 2 versions
    selected_version_ids = [100, 200]

    with patch('src.store.pack_service.requests.get', return_value=mock_response):
        pack = multi_version_pack_service.import_from_civitai(
            "https://civitai.com/models/123",
            max_previews=100,
            download_config=config,
            selected_version_ids=selected_version_ids,
        )

    # All dependency IDs should be unique
    dep_ids = [d.id for d in pack.dependencies]
    assert len(dep_ids) == len(set(dep_ids)), f"Duplicate dependency IDs found: {dep_ids}"


def test_single_version_import_creates_single_dependency(multi_version_pack_service, mock_layout):
    """When only one version is selected (or none provided), create single main dependency."""
    from src.store.pack_service import PreviewDownloadConfig

    mock_layout.save_pack = MagicMock()
    mock_layout.save_pack_lock = MagicMock()

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.iter_content = MagicMock(return_value=[b'fake image data'])
    mock_response.headers = {'content-length': '100'}

    config = PreviewDownloadConfig()

    # Single version selected
    selected_version_ids = [100]

    with patch('src.store.pack_service.requests.get', return_value=mock_response):
        pack = multi_version_pack_service.import_from_civitai(
            "https://civitai.com/models/123",
            max_previews=100,
            download_config=config,
            selected_version_ids=selected_version_ids,
        )

    # Should have 1 LORA dependency + possibly base model
    lora_deps = [d for d in pack.dependencies if d.kind.value == 'lora']

    assert len(lora_deps) == 1, f"Expected 1 LORA dependency for single version, got {len(lora_deps)}"
    assert lora_deps[0].id == "main_lora", f"Single version should use 'main_lora' ID, got '{lora_deps[0].id}'"


def test_multi_version_import_without_version_ids_uses_url_version(multi_version_pack_service, mock_layout):
    """When selected_version_ids is None/empty, should use version from URL."""
    from src.store.pack_service import PreviewDownloadConfig

    mock_layout.save_pack = MagicMock()
    mock_layout.save_pack_lock = MagicMock()

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.iter_content = MagicMock(return_value=[b'fake image data'])
    mock_response.headers = {'content-length': '100'}

    config = PreviewDownloadConfig()

    with patch('src.store.pack_service.requests.get', return_value=mock_response):
        # No selected_version_ids - should use version from URL (200)
        pack = multi_version_pack_service.import_from_civitai(
            "https://civitai.com/models/123?modelVersionId=200",
            max_previews=100,
            download_config=config,
            selected_version_ids=None,  # None = use URL version
        )

    lora_deps = [d for d in pack.dependencies if d.kind.value == 'lora']

    assert len(lora_deps) == 1, f"Expected 1 LORA dependency, got {len(lora_deps)}"
    assert lora_deps[0].selector.civitai.version_id == 200, "Should use version 200 from URL"


def test_multi_version_lock_contains_all_resolved_dependencies(multi_version_pack_service, mock_layout):
    """Lock file should contain resolved info for ALL version dependencies."""
    from src.store.pack_service import PreviewDownloadConfig

    saved_lock = None
    def capture_lock(lock):
        nonlocal saved_lock
        saved_lock = lock

    mock_layout.save_pack = MagicMock()
    mock_layout.save_pack_lock = MagicMock(side_effect=capture_lock)

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.iter_content = MagicMock(return_value=[b'fake image data'])
    mock_response.headers = {'content-length': '100'}

    config = PreviewDownloadConfig()

    # Select 2 versions
    selected_version_ids = [100, 300]

    with patch('src.store.pack_service.requests.get', return_value=mock_response):
        pack = multi_version_pack_service.import_from_civitai(
            "https://civitai.com/models/123",
            max_previews=100,
            download_config=config,
            selected_version_ids=selected_version_ids,
        )

    # Lock should be saved
    assert saved_lock is not None, "Lock file should be saved"

    # Lock should have resolved entries for both versions
    resolved_version_ids = {
        r.artifact.provider.version_id
        for r in saved_lock.resolved
        if r.artifact.provider.version_id in [100, 300]
    }
    assert resolved_version_ids == {100, 300}, f"Lock should have both versions resolved: {resolved_version_ids}"

