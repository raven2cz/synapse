"""
Test fixtures and helpers for Synapse Store v2 tests.

Provides:
- Deterministic test data generation
- Fake Civitai client for offline testing
- Assertion helpers for blob paths and symlinks
- Snapshot comparison utilities
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock


def compute_sha256_from_content(content: bytes) -> str:
    """Compute SHA256 hash from bytes."""
    return hashlib.sha256(content).hexdigest().lower()


def create_test_blob(content: str = "test content") -> tuple[bytes, str]:
    """
    Create test blob content with deterministic hash.
    
    Returns:
        Tuple of (content_bytes, sha256_hash)
    """
    content_bytes = content.encode("utf-8")
    sha256 = compute_sha256_from_content(content_bytes)
    return content_bytes, sha256


@dataclass
class FakeModelVersion:
    """Fake Civitai model version for testing."""
    id: int
    model_id: int
    name: str = "v1.0"
    base_model: str = "SDXL"
    trained_words: List[str] = field(default_factory=list)
    files: List[Dict[str, Any]] = field(default_factory=list)
    images: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "modelId": self.model_id,
            "name": self.name,
            "baseModel": self.base_model,
            "trainedWords": self.trained_words,
            "files": self.files,
            "images": self.images,
        }


@dataclass
class FakeModel:
    """Fake Civitai model for testing."""
    id: int
    name: str
    type: str = "LORA"
    versions: List[FakeModelVersion] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "modelVersions": [v.to_dict() for v in self.versions],
        }


@dataclass  
class FakeFile:
    """Fake Civitai file for testing."""
    id: int
    name: str
    size_kb: float = 1024.0
    primary: bool = True
    sha256: Optional[str] = None
    download_url: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "sizeKB": self.size_kb,
            "primary": self.primary,
        }
        if self.sha256:
            result["hashes"] = {"SHA256": self.sha256.upper()}
        if self.download_url:
            result["downloadUrl"] = self.download_url
        return result


class _FakeVersionResult:
    """Lightweight wrapper to mimic CivitaiModelVersion for get_model_by_hash."""

    def __init__(self, version: FakeModelVersion, model: FakeModel):
        self.id = version.id
        self.model_id = version.model_id
        self.name = version.name
        self.base_model = version.base_model
        self.files = version.files
        self.images = version.images
        self.trained_words = version.trained_words
        self._model = model

    @property
    def model_name(self) -> str:
        return self._model.name

    @property
    def model_type(self) -> str:
        return self._model.type


class FakeCivitaiClient:
    """
    Fake Civitai client for offline testing.

    Usage:
        client = FakeCivitaiClient()

        # Add fake models
        client.add_model(FakeModel(
            id=12345,
            name="TestModel",
            type="LORA",
            versions=[
                FakeModelVersion(
                    id=67890,
                    model_id=12345,
                    files=[FakeFile(id=11111, name="test.safetensors").to_dict()]
                )
            ]
        ))

        # Use in tests
        model = client.get_model(12345)
    """

    def __init__(self):
        self.models: Dict[int, FakeModel] = {}
        self.versions: Dict[int, FakeModelVersion] = {}
        self.download_handler: Optional[callable] = None

    def add_model(self, model: FakeModel) -> None:
        """Add a fake model."""
        self.models[model.id] = model
        for version in model.versions:
            self.versions[version.id] = version

    def get_model(self, model_id: int) -> Dict[str, Any]:
        """Get model by ID."""
        if model_id not in self.models:
            raise ValueError(f"Model not found: {model_id}")
        return self.models[model_id].to_dict()

    def get_model_version(self, version_id: int) -> Dict[str, Any]:
        """Get model version by ID."""
        if version_id not in self.versions:
            raise ValueError(f"Version not found: {version_id}")
        return self.versions[version_id].to_dict()

    def download_preview_image(self, preview: Any, dest: Path) -> None:
        """Fake preview download."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        # Write a small fake image
        dest.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

    def search_models(
        self,
        query: Optional[str] = None,
        types: Optional[List[str]] = None,
        sort: Optional[str] = None,
        limit: int = 20,
        **kwargs,
    ) -> Dict[str, Any]:
        """Search models by name substring. Returns Civitai API-style response."""
        results = []
        for model in self.models.values():
            # Filter by query (name substring)
            if query and query.lower() not in model.name.lower():
                continue
            # Filter by types
            if types and model.type not in types:
                continue
            results.append(model.to_dict())

        return {
            "items": results[:limit],
            "metadata": {"totalItems": len(results), "currentPage": 1, "pageSize": limit},
        }

    def get_model_by_hash(self, hash_value: str) -> Optional[Any]:
        """Find model version by file hash (SHA256). Returns CivitaiModelVersion-like or None."""
        hash_upper = hash_value.upper()
        for model in self.models.values():
            for version in model.versions:
                for file_dict in version.files:
                    hashes = file_dict.get("hashes", {})
                    if hashes.get("SHA256", "").upper() == hash_upper:
                        # Return a simple object matching CivitaiModelVersion interface
                        return _FakeVersionResult(version, model)
        return None

    def parse_civitai_url(self, url: str) -> tuple:
        """Parse Civitai URL to extract (model_id, version_id)."""
        import re
        from urllib.parse import urlparse, parse_qs

        parsed = urlparse(url)
        path_match = re.match(r'/models/(\d+)', parsed.path)
        if not path_match:
            raise ValueError(f"Invalid Civitai URL: {url}")

        model_id = int(path_match.group(1))
        query_params = parse_qs(parsed.query)
        version_id = None
        if "modelVersionId" in query_params:
            version_id = int(query_params["modelVersionId"][0])

        return model_id, version_id


class TestStoreContext:
    """
    Context manager for creating isolated test stores.
    
    Usage:
        with TestStoreContext() as ctx:
            store = ctx.store
            store.init()
            # ... run tests ...
    """
    
    def __init__(self, civitai_client: Optional[FakeCivitaiClient] = None):
        self.tmpdir: Optional[tempfile.TemporaryDirectory] = None
        self.root: Optional[Path] = None
        self.store: Optional[Any] = None
        self.civitai = civitai_client or FakeCivitaiClient()
    
    def __enter__(self) -> "TestStoreContext":
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        
        # Set environment
        os.environ["SYNAPSE_ROOT"] = str(self.root)
        
        # Import and create store
        from src.store import Store
        self.store = Store(self.root, civitai_client=self.civitai)
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Clean up environment
        if "SYNAPSE_ROOT" in os.environ:
            del os.environ["SYNAPSE_ROOT"]
        
        if self.tmpdir:
            self.tmpdir.cleanup()
        
        return False
    
    def create_blob(self, content: str = "test content") -> str:
        """Create a test blob and return its SHA256."""
        content_bytes, sha256 = create_test_blob(content)
        blob_path = self.store.blob_store.blob_path(sha256)
        blob_path.parent.mkdir(parents=True, exist_ok=True)
        blob_path.write_bytes(content_bytes)
        return sha256


# =============================================================================
# Assertion Helpers
# =============================================================================

def assert_blob_exists(store: Any, sha256: str) -> None:
    """Assert that a blob exists in the store."""
    assert store.blob_store.blob_exists(sha256), f"Blob not found: {sha256}"


def assert_blob_not_exists(store: Any, sha256: str) -> None:
    """Assert that a blob does not exist in the store."""
    assert not store.blob_store.blob_exists(sha256), f"Blob should not exist: {sha256}"


def assert_symlink_points_to(link: Path, target: Path) -> None:
    """Assert that a symlink points to the expected target."""
    assert link.is_symlink(), f"Not a symlink: {link}"
    actual = link.resolve()
    expected = target.resolve()
    assert actual == expected, f"Symlink {link} points to {actual}, expected {expected}"


def assert_active_points_to_profile(store: Any, ui: str, profile_name: str) -> None:
    """Assert that the active symlink for a UI points to the expected profile."""
    active_path = store.layout.view_active_path(ui)
    assert active_path.is_symlink(), f"Active symlink not found: {active_path}"
    target = os.readlink(active_path)
    expected = f"profiles/{profile_name}"
    assert target == expected, f"Active points to {target}, expected {expected}"


def assert_pack_in_profile(store: Any, pack_name: str, profile_name: str) -> None:
    """Assert that a pack is in a profile."""
    profile = store.layout.load_profile(profile_name)
    pack_names = [p.name for p in profile.packs]
    assert pack_name in pack_names, f"Pack {pack_name} not in profile {profile_name}"


def assert_pack_not_in_profile(store: Any, pack_name: str, profile_name: str) -> None:
    """Assert that a pack is not in a profile."""
    profile = store.layout.load_profile(profile_name)
    pack_names = [p.name for p in profile.packs]
    assert pack_name not in pack_names, f"Pack {pack_name} should not be in profile {profile_name}"


# =============================================================================
# Snapshot Utilities
# =============================================================================

def normalize_report(report: Any) -> Dict[str, Any]:
    """
    Normalize a report for snapshot comparison.
    
    Strips timestamps, absolute paths, and other non-deterministic values.
    """
    if hasattr(report, "model_dump"):
        data = report.model_dump()
    elif hasattr(report, "dict"):
        data = report.dict()
    else:
        data = dict(report)
    
    # Remove timestamps
    if "resolved_at" in data:
        data["resolved_at"] = "<timestamp>"
    
    # Normalize paths
    def normalize_value(v: Any) -> Any:
        if isinstance(v, str) and "/" in v and not v.startswith("http"):
            # Might be a path - normalize
            if v.startswith("/home/") or v.startswith("/tmp/"):
                return "<path>"
        return v
    
    def normalize_dict(d: Dict[str, Any]) -> Dict[str, Any]:
        result = {}
        for k, v in d.items():
            if isinstance(v, dict):
                result[k] = normalize_dict(v)
            elif isinstance(v, list):
                result[k] = [normalize_dict(i) if isinstance(i, dict) else normalize_value(i) for i in v]
            else:
                result[k] = normalize_value(v)
        return result
    
    return normalize_dict(data)


def compare_reports(actual: Any, expected: Dict[str, Any]) -> List[str]:
    """
    Compare a report to expected values.
    
    Returns:
        List of differences (empty if equal)
    """
    actual_normalized = normalize_report(actual)
    differences = []
    
    def compare_values(path: str, a: Any, e: Any) -> None:
        if type(a) != type(e):
            differences.append(f"{path}: type mismatch ({type(a).__name__} vs {type(e).__name__})")
        elif isinstance(a, dict) and isinstance(e, dict):
            for k in set(a.keys()) | set(e.keys()):
                if k not in a:
                    differences.append(f"{path}.{k}: missing in actual")
                elif k not in e:
                    differences.append(f"{path}.{k}: unexpected in actual")
                else:
                    compare_values(f"{path}.{k}", a[k], e[k])
        elif isinstance(a, list) and isinstance(e, list):
            if len(a) != len(e):
                differences.append(f"{path}: length mismatch ({len(a)} vs {len(e)})")
            else:
                for i, (av, ev) in enumerate(zip(a, e)):
                    compare_values(f"{path}[{i}]", av, ev)
        elif a != e:
            differences.append(f"{path}: {a!r} != {e!r}")
    
    compare_values("root", actual_normalized, expected)
    return differences


# =============================================================================
# Fixture Builders
# =============================================================================

def build_test_model(
    model_id: int = 12345,
    version_id: int = 67890,
    file_id: int = 11111,
    name: str = "TestModel",
    model_type: str = "LORA",
    file_name: str = "test_model.safetensors",
    sha256: Optional[str] = None,
) -> FakeModel:
    """Build a test model with standard structure."""
    if sha256 is None:
        _, sha256 = create_test_blob(f"model_{model_id}")
    
    return FakeModel(
        id=model_id,
        name=name,
        type=model_type,
        versions=[
            FakeModelVersion(
                id=version_id,
                model_id=model_id,
                name="v1.0",
                base_model="SDXL",
                trained_words=["test", "style"],
                files=[
                    FakeFile(
                        id=file_id,
                        name=file_name,
                        sha256=sha256,
                        download_url=f"file:///fake/models/{file_name}",
                    ).to_dict()
                ],
                images=[
                    {"url": f"https://example.com/preview_{model_id}.jpg"}
                ],
            )
        ],
    )
