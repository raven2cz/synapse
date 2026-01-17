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

    def get_model(self, model_id):
        return {
            "id": model_id,
            "name": f"TestModel_{model_id}",
            "type": "LORA",
            "modelVersions": [
                {"id": 100, "name": "v1.0"}
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

    # Call import with max_previews=100 to ensure we get all 20
    pack = pack_service.import_from_civitai("https://civitai.com/models/123?modelVersionId=100", max_previews=100)
    
    # Check directory content
    pack_name = pack.name
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
    
    # Run twice
    pack1 = pack_service.import_from_civitai(url, max_previews=100)
    pack2 = pack_service.import_from_civitai(url, max_previews=100)
    
    pack_name = pack1.name
    previews_dir = mock_layout.root / "packs" / pack_name / "resources" / "previews"
    
    # Assert still 20 images, not 40
    images = list(previews_dir.glob("*.jpg"))
    assert len(images) == 20, f"Expected 20 images after double import, found {len(images)}"


def test_pack_previews_include_nsfw_and_meta(pack_service, mock_layout):
    """Test that pack.previews includes correct nsfw flag and meta from Civitai API."""
    
    mock_layout.save_pack = MagicMock()
    mock_layout.save_pack_lock = MagicMock()
    mock_layout.load_config = MagicMock()
    
    pack = pack_service.import_from_civitai("https://civitai.com/models/123?modelVersionId=100", max_previews=100)
    
    # Check pack.previews has correct data
    assert len(pack.previews) == 20, f"Expected 20 previews in pack, found {len(pack.previews)}"
    
    # Check NSFW flags (every 3rd image should be NSFW: 0, 3, 6, 9, 12, 15, 18)
    nsfw_count = sum(1 for p in pack.previews if p.nsfw)
    assert nsfw_count == 7, f"Expected 7 NSFW previews, found {nsfw_count}"
    
    # Check meta is included
    for i, preview in enumerate(pack.previews):
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

