"""
Synapse Store v2 - Test Helpers

Provides utilities for testing:
- Fake Civitai client
- Fixture builders
- Assertions
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import MagicMock


# =============================================================================
# Fake Civitai Client
# =============================================================================

class FakeCivitaiClient:
    """
    Fake Civitai client for testing without network calls.
    
    Configure with model/version data, then use in place of real client.
    """
    
    def __init__(self):
        self.models: Dict[int, Dict[str, Any]] = {}
        self.versions: Dict[int, Dict[str, Any]] = {}
        self.downloaded: List[Tuple[str, Path]] = []
    
    def add_model(
        self,
        model_id: int,
        name: str = "Test Model",
        model_type: str = "LORA",
        versions: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Add a fake model."""
        self.models[model_id] = {
            "id": model_id,
            "name": name,
            "type": model_type,
            "modelVersions": versions or [],
        }
    
    def add_version(
        self,
        version_id: int,
        model_id: int,
        name: str = "v1.0",
        base_model: str = "SDXL",
        files: Optional[List[Dict[str, Any]]] = None,
        images: Optional[List[Dict[str, Any]]] = None,
        trained_words: Optional[List[str]] = None,
    ) -> None:
        """Add a fake version."""
        version_data = {
            "id": version_id,
            "modelId": model_id,
            "name": name,
            "baseModel": base_model,
            "files": files or [],
            "images": images or [],
            "trainedWords": trained_words or [],
        }
        self.versions[version_id] = version_data
        
        # Add to model's versions if model exists
        if model_id in self.models:
            # Insert at beginning (latest first)
            self.models[model_id]["modelVersions"].insert(0, version_data)
    
    def add_file(
        self,
        version_id: int,
        file_id: int,
        name: str = "model.safetensors",
        size_kb: int = 1024,
        sha256: Optional[str] = None,
        primary: bool = True,
    ) -> None:
        """Add a fake file to a version."""
        if version_id not in self.versions:
            raise ValueError(f"Version {version_id} not found")
        
        file_data = {
            "id": file_id,
            "name": name,
            "sizeKB": size_kb,
            "primary": primary,
            "downloadUrl": f"https://civitai.com/api/download/models/{version_id}?type=Model&format=SafeTensor",
            "hashes": {
                "SHA256": sha256 or self._generate_hash(f"file_{file_id}"),
            },
        }
        self.versions[version_id]["files"].append(file_data)
        
        # Update model's versions too
        model_id = self.versions[version_id]["modelId"]
        if model_id in self.models:
            for v in self.models[model_id]["modelVersions"]:
                if v["id"] == version_id:
                    v["files"].append(file_data)
                    break
    
    def get_model(self, model_id: int) -> Dict[str, Any]:
        """Get model data."""
        if model_id not in self.models:
            raise ValueError(f"Model {model_id} not found")
        return self.models[model_id]
    
    def get_model_version(self, version_id: int) -> Dict[str, Any]:
        """Get version data."""
        if version_id not in self.versions:
            raise ValueError(f"Version {version_id} not found")
        return self.versions[version_id]
    
    def download_preview_image(self, image: Any, dest: Path) -> None:
        """Fake download preview image."""
        self.downloaded.append((getattr(image, "url", str(image)), dest))
        # Create a fake image file
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"FAKE_IMAGE_DATA")
    
    @staticmethod
    def _generate_hash(seed: str) -> str:
        """Generate deterministic hash from seed."""
        return hashlib.sha256(seed.encode()).hexdigest()


# =============================================================================
# Fixture Builders
# =============================================================================

def create_fake_blob(
    content: Optional[bytes] = None,
    size: int = 1024,
    seed: Optional[str] = None,
) -> Tuple[bytes, str]:
    """
    Create fake blob content with deterministic hash.
    
    Args:
        content: Specific content, or None to generate
        size: Size of generated content
        seed: Seed for deterministic generation
    
    Returns:
        Tuple of (content_bytes, sha256_hex)
    """
    if content is None:
        if seed is not None:
            # Deterministic content from seed
            import random
            rng = random.Random(seed)
            content = bytes([rng.randint(0, 255) for _ in range(size)])
        else:
            content = os.urandom(size)
    
    sha256 = hashlib.sha256(content).hexdigest()
    return content, sha256


def create_test_pack_json(
    name: str = "TestPack",
    pack_type: str = "lora",
    model_id: int = 12345,
    version_id: int = 67890,
    file_id: int = 11111,
    sha256: str = "abc123",
    expose_filename: str = "test_model.safetensors",
    base_model: Optional[str] = "SDXL",
) -> Dict[str, Any]:
    """Create a test pack.json structure."""
    dependencies = [
        {
            "id": f"main_{pack_type}",
            "kind": pack_type,
            "required": True,
            "selector": {
                "strategy": "civitai_model_latest",
                "civitai": {
                    "model_id": model_id,
                    "version_id": version_id,
                    "file_id": file_id,
                },
            },
            "update_policy": {"mode": "follow_latest"},
            "expose": {
                "filename": expose_filename,
                "trigger_words": [],
            },
        }
    ]
    
    if base_model:
        dependencies.insert(0, {
            "id": "base_checkpoint",
            "kind": "checkpoint",
            "required": False,
            "selector": {
                "strategy": "base_model_hint",
                "base_model": base_model,
            },
            "update_policy": {"mode": "pinned"},
            "expose": {
                "filename": f"{base_model}.safetensors",
            },
        })
    
    return {
        "schema": "synapse.pack.v2",
        "name": name,
        "pack_type": pack_type,
        "source": {
            "provider": "civitai",
            "model_id": model_id,
            "version_id": version_id,
            "url": f"https://civitai.com/models/{model_id}",
        },
        "dependencies": dependencies,
        "resources": {
            "previews_keep_in_git": True,
            "workflows_keep_in_git": True,
        },
    }


def create_test_lock_json(
    pack_name: str = "TestPack",
    dependencies: Optional[List[Dict[str, Any]]] = None,
    unresolved: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Create a test lock.json structure."""
    if dependencies is None:
        dependencies = [
            {
                "dependency_id": "main_lora",
                "artifact": {
                    "kind": "lora",
                    "sha256": "abc123def456",
                    "size_bytes": 1024000,
                    "provider": {
                        "name": "civitai",
                        "model_id": 12345,
                        "version_id": 67890,
                        "file_id": 11111,
                    },
                    "download": {
                        "urls": ["https://civitai.com/api/download/models/67890"],
                    },
                    "integrity": {
                        "sha256_verified": True,
                    },
                },
            }
        ]
    
    return {
        "schema": "synapse.lock.v2",
        "pack": pack_name,
        "resolved_at": "2024-01-01T00:00:00Z",
        "resolved": dependencies,
        "unresolved": unresolved or [],
    }


def create_test_profile_json(
    name: str = "global",
    packs: Optional[List[str]] = None,
    conflict_mode: str = "last_wins",
) -> Dict[str, Any]:
    """Create a test profile.json structure."""
    return {
        "schema": "synapse.profile.v1",
        "name": name,
        "conflicts": {"mode": conflict_mode},
        "packs": [{"name": p} for p in (packs or [])],
    }


# =============================================================================
# Assertions
# =============================================================================

def assert_blob_exists(layout, sha256: str) -> None:
    """Assert that a blob exists in the store."""
    blob_path = layout.blob_path(sha256)
    assert blob_path.exists(), f"Blob {sha256[:12]}... not found at {blob_path}"


def assert_blob_not_exists(layout, sha256: str) -> None:
    """Assert that a blob does not exist in the store."""
    blob_path = layout.blob_path(sha256)
    assert not blob_path.exists(), f"Blob {sha256[:12]}... unexpectedly exists at {blob_path}"


def assert_symlink_points_to(link_path: Path, target_path: Path) -> None:
    """Assert that a symlink points to expected target."""
    assert link_path.is_symlink(), f"{link_path} is not a symlink"
    actual_target = link_path.resolve()
    expected_target = target_path.resolve()
    assert actual_target == expected_target, (
        f"Symlink {link_path} points to {actual_target}, expected {expected_target}"
    )


def assert_active_profile(layout, ui: str, expected_profile: str) -> None:
    """Assert that the active profile for a UI is as expected."""
    active_path = layout.view_active_path(ui)
    assert active_path.is_symlink(), f"Active symlink not found for {ui}"
    
    target = os.readlink(active_path)
    parts = Path(target).parts
    assert len(parts) >= 2, f"Invalid active symlink target: {target}"
    assert parts[0] == "profiles", f"Active symlink should point to profiles/, got: {target}"
    assert parts[1] == expected_profile, (
        f"Active profile is {parts[1]}, expected {expected_profile}"
    )


def assert_pack_in_profile(layout, profile_name: str, pack_name: str) -> None:
    """Assert that a pack is in a profile."""
    profile = layout.load_profile(profile_name)
    pack_names = profile.get_pack_names()
    assert pack_name in pack_names, (
        f"Pack {pack_name} not in profile {profile_name}. Packs: {pack_names}"
    )


def assert_json_valid(path: Path) -> Dict[str, Any]:
    """Assert that a file contains valid JSON and return it."""
    assert path.exists(), f"File not found: {path}"
    with open(path) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            raise AssertionError(f"Invalid JSON in {path}: {e}")


# =============================================================================
# Test Context Manager
# =============================================================================

class TempStore:
    """
    Context manager for creating a temporary store for testing.
    
    Usage:
        with TempStore() as store:
            store.init()
            # ... test operations
    """
    
    def __init__(self, auto_init: bool = True):
        self.auto_init = auto_init
        self._tmpdir: Optional[tempfile.TemporaryDirectory] = None
        self._store: Optional[Any] = None
    
    def __enter__(self):
        from src.store import Store
        
        self._tmpdir = tempfile.TemporaryDirectory()
        root = Path(self._tmpdir.name)
        
        self._store = Store(root=root)
        
        if self.auto_init:
            self._store.init()
        
        return self._store
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._tmpdir:
            self._tmpdir.cleanup()
        return False
    
    @property
    def root(self) -> Path:
        """Get the temporary root directory."""
        if self._tmpdir:
            return Path(self._tmpdir.name)
        raise RuntimeError("TempStore not entered")


# =============================================================================
# Snapshot Helpers
# =============================================================================

def normalize_report(report: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize a report for snapshot comparison.
    
    Removes non-deterministic fields like timestamps and absolute paths.
    """
    result = report.copy()
    
    # Remove timestamps
    for key in ["resolved_at", "created_at", "updated_at"]:
        if key in result:
            result[key] = "<TIMESTAMP>"
    
    # Normalize paths
    def normalize_paths(obj):
        if isinstance(obj, dict):
            return {k: normalize_paths(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [normalize_paths(v) for v in obj]
        elif isinstance(obj, str):
            # Replace absolute paths with placeholders
            if obj.startswith("/") and ("synapse" in obj.lower() or "tmp" in obj.lower()):
                return "<PATH>"
            return obj
        return obj
    
    return normalize_paths(result)
