"""
Tests for StoreLayout

Tests the v2 storage layout management.
"""

import json
import tempfile
from pathlib import Path

import pytest

from src.store.layout import (
    PackNotFoundError,
    ProfileNotFoundError,
    StoreLayout,
    StoreNotInitializedError,
)
from src.store.models import (
    Pack,
    PackDependency,
    PackLock,
    PackSource,
    Profile,
    ProviderName,
    AssetKind,
    DependencySelector,
    SelectorStrategy,
    ExposeConfig,
)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def layout(temp_dir):
    """Create a StoreLayout with temp directory."""
    return StoreLayout(temp_dir)


class TestStoreLayoutInit:
    """Tests for store initialization."""
    
    def test_not_initialized_initially(self, layout):
        """Store should not be initialized by default."""
        assert not layout.is_initialized()
    
    def test_init_creates_directories(self, layout):
        """Init should create required directories."""
        layout.init_store()
        
        assert layout.state_path.exists()
        assert layout.data_path.exists()
        assert layout.packs_path.exists()
        assert layout.profiles_path.exists()
        assert layout.blobs_path.exists()
        assert layout.views_path.exists()
    
    def test_init_creates_config(self, layout):
        """Init should create config.json."""
        layout.init_store()
        
        assert layout.config_path.exists()
        config = layout.load_config()
        assert config.defaults.ui_set == "local"
    
    def test_init_creates_global_profile(self, layout):
        """Init should create global profile."""
        layout.init_store()
        
        assert layout.profile_exists("global")
        profile = layout.load_profile("global")
        assert profile.name == "global"
    
    def test_init_creates_runtime(self, layout):
        """Init should create runtime.json."""
        layout.init_store()
        
        assert layout.runtime_path.exists()
        runtime = layout.load_runtime()
        assert "comfyui" in runtime.ui


class TestPackOperations:
    """Tests for pack CRUD operations."""
    
    def test_list_packs_empty(self, layout):
        """List packs should return empty list initially."""
        layout.init_store()
        assert layout.list_packs() == []
    
    def test_save_and_load_pack(self, layout):
        """Should save and load pack correctly."""
        layout.init_store()
        
        pack = Pack(
            name="TestPack",
            pack_type=AssetKind.LORA,
            source=PackSource(
                provider=ProviderName.CIVITAI,
                model_id=12345,
            ),
            dependencies=[
                PackDependency(
                    id="main_lora",
                    kind=AssetKind.LORA,
                    selector=DependencySelector(strategy=SelectorStrategy.CIVITAI_FILE),
                    expose=ExposeConfig(filename="test.safetensors"),
                )
            ],
        )
        
        layout.save_pack(pack)
        
        assert layout.pack_exists("TestPack")
        assert "TestPack" in layout.list_packs()
        
        loaded = layout.load_pack("TestPack")
        assert loaded.name == "TestPack"
        assert loaded.pack_type == AssetKind.LORA
        assert len(loaded.dependencies) == 1
    
    def test_load_nonexistent_pack_raises(self, layout):
        """Loading nonexistent pack should raise."""
        layout.init_store()
        
        with pytest.raises(PackNotFoundError):
            layout.load_pack("NonExistent")
    
    def test_delete_pack(self, layout):
        """Should delete pack and its files."""
        layout.init_store()
        
        pack = Pack(
            name="ToDelete",
            pack_type=AssetKind.LORA,
            source=PackSource(provider=ProviderName.LOCAL),
            dependencies=[],
        )
        layout.save_pack(pack)
        
        assert layout.pack_exists("ToDelete")
        
        result = layout.delete_pack("ToDelete")
        
        assert result is True
        assert not layout.pack_exists("ToDelete")
    
    def test_save_and_load_pack_lock(self, layout):
        """Should save and load pack lock correctly."""
        layout.init_store()
        
        # Create pack first
        pack = Pack(
            name="TestPack",
            pack_type=AssetKind.LORA,
            source=PackSource(provider=ProviderName.LOCAL),
            dependencies=[],
        )
        layout.save_pack(pack)
        
        lock = PackLock(
            pack="TestPack",
            resolved=[],
            unresolved=[],
        )
        
        layout.save_pack_lock(lock)
        
        loaded = layout.load_pack_lock("TestPack")
        assert loaded is not None
        assert loaded.pack == "TestPack"


class TestProfileOperations:
    """Tests for profile operations."""
    
    def test_list_profiles_after_init(self, layout):
        """Should have global profile after init."""
        layout.init_store()
        
        profiles = layout.list_profiles()
        assert "global" in profiles
    
    def test_save_and_load_profile(self, layout):
        """Should save and load profile correctly."""
        layout.init_store()
        
        profile = Profile(name="work__TestPack")
        layout.save_profile(profile)
        
        assert layout.profile_exists("work__TestPack")
        
        loaded = layout.load_profile("work__TestPack")
        assert loaded.name == "work__TestPack"
    
    def test_cannot_delete_global_profile(self, layout):
        """Should not allow deleting global profile."""
        layout.init_store()
        
        with pytest.raises(Exception):
            layout.delete_profile("global")
    
    def test_delete_work_profile(self, layout):
        """Should allow deleting work profiles."""
        layout.init_store()
        
        profile = Profile(name="work__Test")
        layout.save_profile(profile)
        
        result = layout.delete_profile("work__Test")
        
        assert result is True
        assert not layout.profile_exists("work__Test")


class TestPathMethods:
    """Tests for path calculation methods."""
    
    def test_blob_path(self, layout):
        """Blob path should use first 2 chars as prefix."""
        sha256 = "abc123def456"
        path = layout.blob_path(sha256)
        
        assert path.name == sha256  # filename is full hash
        assert path.parent.name == "ab"  # parent is 2-char prefix
    
    def test_view_paths(self, layout):
        """View paths should be structured correctly."""
        ui_path = layout.view_ui_path("comfyui")
        assert ui_path.name == "comfyui"
        
        profile_path = layout.view_profile_path("comfyui", "global")
        assert profile_path.name == "global"
        assert profile_path.parent.name == "profiles"
        
        active_path = layout.view_active_path("comfyui")
        assert active_path.name == "active"


class TestJsonIO:
    """Tests for JSON I/O operations."""
    
    def test_write_json_atomic(self, layout, temp_dir):
        """JSON write should be atomic."""
        layout.init_store()
        
        test_file = temp_dir / "test.json"
        data = {"key": "value", "number": 42}
        
        layout.write_json(test_file, data)
        
        assert test_file.exists()
        
        # Check content
        with open(test_file) as f:
            loaded = json.load(f)
        
        assert loaded == data
    
    def test_write_json_canonical_format(self, layout, temp_dir):
        """JSON should be written with canonical formatting."""
        layout.init_store()
        
        test_file = temp_dir / "test.json"
        data = {"z": 1, "a": 2}  # Unsorted
        
        layout.write_json(test_file, data)
        
        with open(test_file) as f:
            content = f.read()
        
        # Should be sorted and indented
        assert '"a":' in content
        assert '"z":' in content
        assert content.index('"a"') < content.index('"z"')  # a before z
        assert content.endswith("\n")  # Trailing newline
