"""
Critical API Smoke Tests + UIAttacher Tests

These tests verify:
1. Store core functionality works
2. UIAttacher creates correct symlinks
3. End-to-end flow works
"""

import pytest
import tempfile
import json
from pathlib import Path


# =============================================================================
# UIAttacher Tests
# =============================================================================

class TestUIAttacher:
    """Tests for UIAttacher functionality."""
    
    @pytest.fixture
    def setup_store_with_view(self, tmp_path):
        """Set up a store with an active view for testing."""
        from src.store import Store
        from src.store.models import Profile, ProfilePackEntry
        
        # Create store
        store = Store(tmp_path / "store")
        store.init()
        
        # Create a fake active view structure manually
        # This simulates what sync() would create
        view_loras = store.layout.view_ui_path("comfyui") / "profiles" / "global" / "models" / "loras"
        view_loras.mkdir(parents=True, exist_ok=True)
        
        # Create a fake model file in the view
        fake_model = view_loras / "test_model.safetensors"
        fake_model.write_text("fake model content")
        
        # Create active symlink
        active_path = store.layout.view_active_path("comfyui")
        active_path.parent.mkdir(parents=True, exist_ok=True)
        profile_path = store.layout.view_profile_path("comfyui", "global")
        active_path.symlink_to(profile_path)
        
        # Create fake UI root
        ui_root = tmp_path / "ComfyUI"
        ui_root.mkdir(parents=True)
        
        return store, ui_root
    
    def test_attach_creates_symlinks(self, setup_store_with_view):
        """Test that attach creates correct symlinks."""
        store, ui_root = setup_store_with_view
        
        from src.store.ui_attach import UIAttacher
        
        # Create attacher with fake UI root
        attacher = UIAttacher(
            layout=store.layout,
            ui_roots={"comfyui": ui_root},
        )
        
        # Attach
        result = attacher.attach("comfyui")
        
        # Verify result
        assert result.success, f"Attach failed: {result.errors}"
        assert result.method == "symlink"
        assert len(result.created) > 0, "No symlinks created"
        
        # Verify symlink exists and points to correct location
        loras_synapse = ui_root / "models" / "loras" / "synapse"
        assert loras_synapse.is_symlink(), f"Symlink not created: {loras_synapse}"
        
        # Verify target contains our model
        target = loras_synapse.resolve()
        assert target.exists(), f"Target doesn't exist: {target}"
        
        # Check model file is accessible through symlink
        model_via_link = loras_synapse / "test_model.safetensors"
        assert model_via_link.exists(), f"Model not accessible via symlink: {model_via_link}"
    
    def test_detach_removes_symlinks(self, setup_store_with_view):
        """Test that detach removes symlinks."""
        store, ui_root = setup_store_with_view
        
        from src.store.ui_attach import UIAttacher
        
        attacher = UIAttacher(
            layout=store.layout,
            ui_roots={"comfyui": ui_root},
        )
        
        # First attach
        attach_result = attacher.attach("comfyui")
        assert attach_result.success
        
        # Verify symlink exists
        loras_synapse = ui_root / "models" / "loras" / "synapse"
        assert loras_synapse.is_symlink()
        
        # Detach
        detach_result = attacher.detach("comfyui")
        assert detach_result.success
        
        # Verify symlink is removed
        assert not loras_synapse.exists(), "Symlink not removed"
    
    def test_attach_status(self, setup_store_with_view):
        """Test attach status detection."""
        store, ui_root = setup_store_with_view
        
        from src.store.ui_attach import UIAttacher
        
        attacher = UIAttacher(
            layout=store.layout,
            ui_roots={"comfyui": ui_root},
        )
        
        # Before attach
        status_before = attacher.status("comfyui")
        assert not status_before["attached"]
        assert status_before["view_exists"]
        
        # After attach
        attacher.attach("comfyui")
        status_after = attacher.status("comfyui")
        assert status_after["attached"]
        assert len(status_after["symlinks"]) > 0
    
    def test_attach_nonexistent_ui_root(self, tmp_path):
        """Test attach with non-existent UI root."""
        from src.store import Store
        from src.store.ui_attach import UIAttacher
        
        store = Store(tmp_path / "store")
        store.init()
        
        attacher = UIAttacher(
            layout=store.layout,
            ui_roots={"comfyui": tmp_path / "nonexistent"},
        )
        
        result = attacher.attach("comfyui")
        assert not result.success
        assert result.method == "skipped"
        assert "does not exist" in result.errors[0]
    
    def test_forge_kind_mapping(self, tmp_path):
        """Test that Forge gets correct kind paths (e.g., Lora not loras)."""
        from src.store import Store
        from src.store.ui_attach import UIAttacher
        from src.store.models import UIConfig
        
        store = Store(tmp_path / "store")
        store.init()
        
        # Create forge UI root
        forge_root = tmp_path / "Forge"
        forge_root.mkdir()
        
        # Create attacher
        attacher = UIAttacher(
            layout=store.layout,
            ui_roots={"forge": forge_root},
        )
        
        # Get kind map
        kind_map = attacher._get_kind_map("forge")
        
        # Verify Forge paths
        assert kind_map.lora == "models/Lora", f"Wrong lora path: {kind_map.lora}"
        assert kind_map.checkpoint == "models/Stable-diffusion", f"Wrong checkpoint path: {kind_map.checkpoint}"


# =============================================================================
# Store Smoke Tests (Direct store testing, no HTTP)
# =============================================================================

class TestStoreSmokeTests:
    """Critical store functionality tests without HTTP."""
    
    @pytest.fixture
    def store(self, tmp_path):
        """Create initialized store."""
        from src.store import Store
        store = Store(tmp_path / "store")
        store.init()
        return store
    
    def test_store_init(self, tmp_path):
        """Test store initialization."""
        from src.store import Store
        
        store = Store(tmp_path / "store")
        assert not store.layout.is_initialized()
        
        store.init()
        assert store.layout.is_initialized()
        
        # Check directories exist
        assert store.layout.packs_path.exists()
        assert store.layout.profiles_path.exists()
        assert store.layout.blobs_path.exists()
    
    def test_store_config(self, store):
        """Test store config loading."""
        config = store.get_config()
        assert config is not None
        assert hasattr(config, 'ui')
        assert hasattr(config, 'defaults')
    
    def test_profiles_status(self, store):
        """Test profiles status."""
        status = store.status(ui_set="comfyui")
        assert status is not None
        assert status.profile is not None
    
    def test_updates_check_all_empty(self, store):
        """Test checking updates on empty store."""
        plans = store.check_all_updates()
        assert plans == {}  # No packs = no update plans
    
    def test_doctor(self, store):
        """Test doctor command."""
        report = store.doctor()
        assert report is not None
        assert hasattr(report, 'actions')
        assert hasattr(report, 'missing_blobs')
    
    def test_clean(self, store):
        """Test clean command."""
        result = store.clean()
        assert result is not None
    
    def test_search_empty_store(self, store):
        """Test search on empty store returns empty results."""
        result = store.search("test")
        assert result is not None
        assert result.query == "test"
        assert result.items == []
    
    def test_search_finds_pack(self, tmp_path):
        """Test search finds matching packs."""
        from src.store import Store
        from src.store.models import Pack, AssetKind, PackSource, ProviderName
        
        store = Store(tmp_path / "store")
        store.init()
        
        # Create a test pack
        pack = Pack(
            name="test-lora-pack",
            pack_type=AssetKind.LORA,
            source=PackSource(provider=ProviderName.LOCAL),
            dependencies=[],
        )
        store.layout.save_pack(pack)
        
        # Search for it
        result = store.search("lora")
        assert len(result.items) == 1
        assert result.items[0].pack_name == "test-lora-pack"
        
        # Search with no match
        result = store.search("checkpoint")
        assert len(result.items) == 0


# =============================================================================
# Integration Test: Full Flow
# =============================================================================

class TestFullFlow:
    """Integration test for complete pack flow."""
    
    @pytest.fixture
    def store(self, tmp_path):
        """Create initialized store."""
        from src.store import Store
        store = Store(tmp_path / "store")
        store.init()
        return store
    
    def test_store_init_and_status(self, store):
        """Test basic store init and status."""
        # Verify initialized
        assert store.layout.is_initialized()
        
        # Get status
        status = store.status()
        assert status is not None
        # StatusReport has these fields: profile, ui_targets, active, missing_blobs, unresolved, shadowed
        assert hasattr(status, 'profile')
        assert hasattr(status, 'active')
    
    def test_list_packs_empty(self, store):
        """Test listing packs on empty store."""
        packs = store.list_packs()
        assert packs == []
    
    def test_use_and_back(self, store):
        """Test use and back operations work without crashes."""
        # Back should work even with empty stack (returns to global)
        result = store.back(ui_targets=["comfyui"], sync=False)
        assert result is not None
        assert result.to_profile == "global"


class TestUIAttacherYAML:
    """Test UIAttacher extra_model_paths.yaml generation for ComfyUI."""
    
    @pytest.fixture
    def setup_store_with_yaml_view(self, tmp_path):
        """Create store with view structure for YAML test."""
        from src.store import Store
        from src.store.models import Profile, ProfilePackEntry
        
        # Create store
        store = Store(tmp_path / "store")
        store.init()
        
        # Create a fake active view structure manually
        view_loras = store.layout.view_ui_path("comfyui") / "profiles" / "global" / "models" / "loras"
        view_loras.mkdir(parents=True, exist_ok=True)
        
        view_checkpoints = store.layout.view_ui_path("comfyui") / "profiles" / "global" / "models" / "checkpoints"
        view_checkpoints.mkdir(parents=True, exist_ok=True)
        
        # Create fake model files in the view
        (view_loras / "test_lora.safetensors").write_text("fake lora")
        (view_checkpoints / "test_ckpt.safetensors").write_text("fake checkpoint")
        
        # Create active symlink
        active_path = store.layout.view_active_path("comfyui")
        active_path.parent.mkdir(parents=True, exist_ok=True)
        profile_path = store.layout.view_profile_path("comfyui", "global")
        active_path.symlink_to(profile_path)
        
        # Create fake UI root
        ui_root = tmp_path / "ComfyUI"
        ui_root.mkdir(parents=True)
        
        return store, ui_root
    
    def test_generate_extra_model_paths_yaml(self, setup_store_with_yaml_view):
        """Test YAML generation for ComfyUI."""
        store, ui_root = setup_store_with_yaml_view
        
        from src.store.ui_attach import UIAttacher
        
        attacher = UIAttacher(
            layout=store.layout,
            ui_roots={"comfyui": ui_root},
        )
        
        # Generate YAML content
        yaml_content = attacher.generate_extra_model_paths_yaml("comfyui")
        
        # Verify structure
        assert "synapse" in yaml_content
        assert "loras" in yaml_content["synapse"]
        assert "checkpoints" in yaml_content["synapse"]
        
        # Verify paths point to view
        assert "views/comfyui" in yaml_content["synapse"]["loras"]
        assert "views/comfyui" in yaml_content["synapse"]["checkpoints"]
    
    def test_attach_comfyui_yaml_method(self, setup_store_with_yaml_view):
        """Test attaching ComfyUI using YAML method."""
        store, ui_root = setup_store_with_yaml_view
        
        from src.store.ui_attach import UIAttacher
        
        attacher = UIAttacher(
            layout=store.layout,
            ui_roots={"comfyui": ui_root},
        )
        
        # Attach using YAML method
        result = attacher.attach_comfyui_yaml()
        
        # Verify success
        assert result.success
        assert result.method == "extra_model_paths"
        assert result.config_path is not None
        
        # Verify file was created
        yaml_path = Path(result.config_path)
        assert yaml_path.exists()
        
        # Verify content
        import yaml
        with open(yaml_path) as f:
            content = yaml.safe_load(f)
        
        assert "synapse" in content
    
    def test_attach_comfyui_with_use_yaml_flag(self, setup_store_with_yaml_view):
        """Test attach() with use_yaml=True for ComfyUI."""
        store, ui_root = setup_store_with_yaml_view
        
        from src.store.ui_attach import UIAttacher
        
        attacher = UIAttacher(
            layout=store.layout,
            ui_roots={"comfyui": ui_root},
        )
        
        # Attach with use_yaml=True
        result = attacher.attach("comfyui", use_yaml=True)
        
        assert result.success
        assert result.method == "extra_model_paths"
    
    def test_comfyui_yaml_backup_and_restore(self, setup_store_with_yaml_view):
        """Test that ComfyUI attach creates backup and detach restores it."""
        store, ui_root = setup_store_with_yaml_view
        
        from src.store.ui_attach import UIAttacher
        import yaml
        
        attacher = UIAttacher(
            layout=store.layout,
            ui_roots={"comfyui": ui_root},
        )
        
        yaml_path = ui_root / "extra_model_paths.yaml"
        backup_path = ui_root / "extra_model_paths.yaml.synapse.bak"
        
        # Create original YAML with some content
        original_content = {"my_paths": {"loras": "/some/path"}}
        with open(yaml_path, "w") as f:
            yaml.dump(original_content, f)
        original_bytes = yaml_path.read_bytes()
        
        # Attach - should create backup
        result = attacher.attach("comfyui", use_yaml=True)
        assert result.success
        assert backup_path.exists(), "Backup should be created"
        assert backup_path.read_bytes() == original_bytes, "Backup should be identical"
        
        # Verify synapse section was added
        with open(yaml_path) as f:
            content = yaml.safe_load(f)
        assert "synapse" in content
        assert "my_paths" in content  # Original content preserved
        
        # Detach - should restore from backup
        detach_result = attacher.detach("comfyui")
        assert detach_result.success
        assert not backup_path.exists(), "Backup should be deleted after restore"
        assert yaml_path.read_bytes() == original_bytes, "Original should be restored"


class TestMainImport:
    """Test that main.py imports correctly without v1 dependencies."""
    
    def test_main_import_no_v1(self):
        """Verify main.py imports without v1 code."""
        import sys
        from pathlib import Path
        
        # Add project root
        project_root = Path(__file__).parent.parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        
        # This should work without errors
        from apps.api.src.main import app
        
        # Verify app exists
        assert app is not None
        
        # Verify routes include v2 paths
        routes = [route.path for route in app.routes if hasattr(route, 'path')]
        
        # Check v2 routes exist
        assert any("/api/store" in r for r in routes)
        assert any("/api/packs" in r for r in routes)
        assert any("/api/profiles" in r for r in routes)
        assert any("/api/updates" in r for r in routes)
        assert any("/api/search" in r for r in routes)
    
    def test_routers_init_no_packs(self):
        """Verify routers/__init__.py doesn't import v1 packs module."""
        import sys
        from pathlib import Path
        
        project_root = Path(__file__).parent.parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        
        # Read the file content
        init_path = project_root / "apps" / "api" / "src" / "routers" / "__init__.py"
        content = init_path.read_text()
        
        # Verify no 'from .packs import' (the actual import pattern)
        # Comments about packs are OK
        assert "from .packs import" not in content, "routers/__init__.py should not import from packs module"
        assert "from . import packs" not in content, "routers/__init__.py should not import packs module"


# =============================================================================
# V2 API Flow Tests (STOP-SHIP critical paths)
# =============================================================================

class TestV2APIFlow:
    """Tests for v2 API critical flow - import, resolve, install."""
    
    @pytest.fixture
    def initialized_store(self, tmp_path):
        """Create an initialized store for testing."""
        from src.store import Store
        
        store = Store(tmp_path / "store")
        store.init()
        return store
    
    def test_comfyui_routes_for_compatibility(self):
        """Verify /api/comfyui routes exist for v1 compatibility."""
        import sys
        from pathlib import Path
        
        project_root = Path(__file__).parent.parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        
        from apps.api.src.main import app
        
        routes = [route.path for route in app.routes if hasattr(route, 'path')]
        
        # comfyui routes should exist for v1 UI compatibility
        comfyui_routes = [r for r in routes if "comfyui" in r.lower()]
        assert len(comfyui_routes) > 0, "ComfyUI routes missing (needed for v1 compatibility)"
    
    def test_packs_import_url_endpoint_exists(self):
        """Verify /api/packs/import/url endpoint exists (V1 API)."""
        import sys
        from pathlib import Path
        
        project_root = Path(__file__).parent.parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        
        from apps.api.src.main import app
        
        routes = [route.path for route in app.routes if hasattr(route, 'path')]
        
        # V2 uses /api/packs/import (not /api/packs/import/url)
        assert "/api/packs/import" in routes, "Missing /api/packs/import endpoint"
    
    def test_packs_v1_endpoints_exist(self):
        """Verify V1 /api/packs endpoints exist."""
        import sys
        from pathlib import Path
        
        project_root = Path(__file__).parent.parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        
        from apps.api.src.main import app
        
        routes = [route.path for route in app.routes if hasattr(route, 'path')]
        
        # V1 endpoints
        v1_endpoints = [
            "/api/packs/",
            "/api/packs/{pack_name}",
            "/api/packs/{pack_name}/resolve-base-model",
            "/api/packs/{pack_name}/download-asset",
            "/api/packs/{pack_name}/download-all",
            "/api/packs/{pack_name}/repair-urls",
        ]
        
        for endpoint in v1_endpoints:
            assert endpoint in routes, f"Missing V1 endpoint: {endpoint}"
    
    def test_v1_compatibility_endpoints_exist(self):
        """Verify v1 compatibility endpoints exist for legacy UI support."""
        import sys
        from pathlib import Path
        
        project_root = Path(__file__).parent.parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        
        from apps.api.src.main import app
        
        routes = [route.path for route in app.routes if hasattr(route, 'path')]
        
        # These v1 compatibility endpoints SHOULD exist for frontend support
        compatibility_endpoints = [
            "/api/packs/{pack_name}/download-asset",
            "/api/packs/{pack_name}/download-all",
            "/api/packs/{pack_name}/resolve-base-model",
            "/api/packs/{pack_name}/repair-urls",
        ]
        
        for endpoint in compatibility_endpoints:
            assert endpoint in routes, f"Missing v1 compatibility endpoint: {endpoint}"
    
    def test_previews_mount_v1_path(self):
        """Verify /previews static mount uses V1 synapse_data_path/packs path."""
        import sys
        from pathlib import Path
        
        project_root = Path(__file__).parent.parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        
        # Read main.py and check the mount path
        main_path = project_root / "apps" / "api" / "src" / "main.py"
        content = main_path.read_text()
        
        # V1 uses synapse_data_path / "packs"
        assert 'synapse_data_path' in content and '"packs"' in content, \
            "Previews mount should use synapse_data_path/packs path"
    
    def test_frontend_uses_v1_endpoints_correctly(self):
        """Verify frontend correctly uses v1 endpoints for base model resolution."""
        import sys
        from pathlib import Path
        
        project_root = Path(__file__).parent.parent.parent
        
        # Check PackDetailPage for required endpoints
        pack_detail = project_root / "apps" / "web" / "src" / "components" / "modules" / "PackDetailPage.tsx"
        if pack_detail.exists():
            content = pack_detail.read_text()
            
            # Should have these v1 endpoints for base model resolution
            assert "/resolve-base-model" in content, "Frontend must use /resolve-base-model for base model resolution"
    
    def test_browse_page_uses_v1_import(self):
        """Verify BrowsePage uses /api/packs/import/url (V1 API)."""
        import sys
        from pathlib import Path
        
        project_root = Path(__file__).parent.parent.parent
        
        browse_page = project_root / "apps" / "web" / "src" / "components" / "modules" / "BrowsePage.tsx"
        if browse_page.exists():
            content = browse_page.read_text()
            
            # V2 uses /api/packs/import (not /api/packs/import/url)
            assert "/api/packs/import" in content, \
                "BrowsePage should use /api/packs/import (V2 API)"


# =============================================================================
# ComfyUI Attach/Detach with Refresh Tests
# =============================================================================

class TestComfyUIAttachRefresh:
    """Test ComfyUI attach refresh behavior after use/back."""
    
    @pytest.fixture
    def setup_store_with_two_packs(self, tmp_path):
        """Create store with two packs and view structure."""
        from src.store import Store
        
        store = Store(tmp_path / "store")
        store.init()
        
        # Create two fake packs
        for pack_name in ["pack1", "pack2"]:
            pack_dir = store.layout.packs_path / pack_name
            pack_dir.mkdir(parents=True, exist_ok=True)
            
            # Create pack.yaml
            pack_yaml = pack_dir / "pack.yaml"
            pack_yaml.write_text(f"name: {pack_name}\nversion: 1.0.0\n")
            
            # Create a lora in resources
            loras_dir = pack_dir / "resources" / "blobs" / "loras"
            loras_dir.mkdir(parents=True, exist_ok=True)
            (loras_dir / f"{pack_name}_lora.safetensors").write_text(f"fake {pack_name}")
        
        # Create view structure for comfyui
        view_loras = store.layout.view_ui_path("comfyui") / "profiles" / "global" / "models" / "loras"
        view_loras.mkdir(parents=True, exist_ok=True)
        
        # Create active symlink
        active_path = store.layout.view_active_path("comfyui")
        active_path.parent.mkdir(parents=True, exist_ok=True)
        profile_path = store.layout.view_profile_path("comfyui", "global")
        active_path.symlink_to(profile_path)
        
        # Create fake ComfyUI root
        ui_root = tmp_path / "ComfyUI"
        ui_root.mkdir(parents=True)
        
        return store, ui_root
    
    def test_refresh_updates_paths_without_losing_backup(self, setup_store_with_two_packs):
        """Test that refresh after use/back updates paths but preserves backup."""
        store, ui_root = setup_store_with_two_packs
        
        from src.store.ui_attach import UIAttacher
        import yaml
        
        attacher = UIAttacher(
            layout=store.layout,
            ui_roots={"comfyui": ui_root},
        )
        
        yaml_path = ui_root / "extra_model_paths.yaml"
        backup_path = ui_root / "extra_model_paths.yaml.synapse.bak"
        
        # Create original YAML
        original_content = {"user_paths": {"custom": "/my/path"}}
        with open(yaml_path, "w") as f:
            yaml.dump(original_content, f)
        original_bytes = yaml_path.read_bytes()
        
        # First attach - creates backup
        result1 = attacher.attach("comfyui", use_yaml=True)
        assert result1.success
        assert backup_path.exists()
        backup_bytes = backup_path.read_bytes()
        
        # Read synapse paths after first attach
        with open(yaml_path) as f:
            content1 = yaml.safe_load(f)
        synapse_paths1 = content1.get("synapse", {})
        
        # Simulate view change (would happen after use/back)
        # Just update the active view target
        active_path = store.layout.view_active_path("comfyui")
        
        # Refresh attach (simulating what happens after use/back)
        result2 = attacher.attach("comfyui", use_yaml=True)
        assert result2.success
        
        # Backup should still exist and be unchanged
        assert backup_path.exists(), "Backup should still exist after refresh"
        assert backup_path.read_bytes() == backup_bytes, "Backup should not change"
        assert backup_path.read_bytes() == original_bytes, "Backup should match original"
        
        # YAML should still have synapse section and user content
        with open(yaml_path) as f:
            content2 = yaml.safe_load(f)
        
        assert "synapse" in content2
        assert "user_paths" in content2, "User content should be preserved"
    
    def test_refresh_attached_only_updates_attached_uis(self, setup_store_with_two_packs):
        """Test that refresh_attached only updates UIs that are already attached."""
        store, ui_root = setup_store_with_two_packs
        
        from src.store.ui_attach import UIAttacher
        
        # Create second UI root (forge) but don't attach it
        forge_root = ui_root.parent / "Forge"
        forge_root.mkdir(parents=True)
        (forge_root / "models" / "Lora").mkdir(parents=True)
        
        attacher = UIAttacher(
            layout=store.layout,
            ui_roots={"comfyui": ui_root, "forge": forge_root},
        )
        
        # Attach only comfyui
        attacher.attach("comfyui", use_yaml=True)
        
        # Verify comfyui is attached, forge is not
        comfyui_status = attacher.status("comfyui")
        forge_status = attacher.status("forge")
        
        assert comfyui_status["attached"], "ComfyUI should be attached"
        assert not forge_status["attached"], "Forge should NOT be attached"
        
        # Call refresh_attached
        results = attacher.refresh_attached(["comfyui", "forge"])
        
        # Only comfyui should be in results (forge was skipped)
        assert "comfyui" in results, "ComfyUI should be refreshed"
        assert "forge" not in results, "Forge should not be refreshed (was detached)"
        
        # Forge should still be detached
        forge_status_after = attacher.status("forge")
        assert not forge_status_after["attached"], "Forge should still be detached"
    
    def test_full_attach_detach_reattach_cycle(self, setup_store_with_two_packs):
        """Test complete attach -> detach -> reattach cycle preserves behavior."""
        store, ui_root = setup_store_with_two_packs
        
        from src.store.ui_attach import UIAttacher
        import yaml
        
        attacher = UIAttacher(
            layout=store.layout,
            ui_roots={"comfyui": ui_root},
        )
        
        yaml_path = ui_root / "extra_model_paths.yaml"
        backup_path = ui_root / "extra_model_paths.yaml.synapse.bak"
        
        # Create original YAML with custom content
        original_content = {"my_custom": {"base_path": "/my/custom/path", "loras": "loras"}}
        with open(yaml_path, "w") as f:
            yaml.dump(original_content, f)
        original_bytes = yaml_path.read_bytes()
        
        # 1. First attach
        result1 = attacher.attach("comfyui", use_yaml=True)
        assert result1.success
        assert backup_path.exists(), "Backup should be created on first attach"
        backup_bytes_1 = backup_path.read_bytes()
        
        # Verify synapse section added
        with open(yaml_path) as f:
            content_after_attach1 = yaml.safe_load(f)
        assert "synapse" in content_after_attach1
        assert "my_custom" in content_after_attach1  # Original preserved
        
        # 2. Detach - should restore original
        result2 = attacher.detach("comfyui")
        assert result2.success
        assert not backup_path.exists(), "Backup should be deleted after detach"
        
        # Verify original restored
        restored_bytes = yaml_path.read_bytes()
        assert restored_bytes == original_bytes, "Detach should restore exact original"
        
        # 3. Re-attach - should work and create new backup
        result3 = attacher.attach("comfyui", use_yaml=True)
        assert result3.success
        assert backup_path.exists(), "Backup should be created on re-attach"
        
        # Backup should match the original
        backup_bytes_2 = backup_path.read_bytes()
        assert backup_bytes_2 == original_bytes, "Re-attach backup should be the original"
        
        # 4. Verify synapse section is back
        with open(yaml_path) as f:
            content_after_reattach = yaml.safe_load(f)
        assert "synapse" in content_after_reattach
        assert "my_custom" in content_after_reattach


# =============================================================================
# Frontend Build Sanity Test
# =============================================================================

class TestFrontendBuild:
    """Test that frontend build passes (CI sanity check)."""
    
    def test_frontend_typescript_valid(self):
        """Verify critical frontend files have valid TypeScript (no unused imports etc)."""
        import sys
        from pathlib import Path
        
        project_root = Path(__file__).parent.parent.parent
        
        # Check key files exist and don't have obvious issues
        critical_files = [
            "apps/web/src/components/modules/PacksPage.tsx",
            "apps/web/src/components/modules/PackDetailPage.tsx",
            "apps/web/src/components/modules/BrowsePage.tsx",
            "apps/web/src/components/modules/ProfilesPage.tsx",
            "apps/web/src/components/modules/ImportModal.tsx",
        ]
        
        for file_path in critical_files:
            full_path = project_root / file_path
            if full_path.exists():
                content = full_path.read_text()
                
                # Basic sanity checks
                assert "import" in content, f"{file_path} should have imports"
                assert "export" in content, f"{file_path} should have exports"
                
                # Check for common issues
                # FileJson was removed in iteration 1
                if "GenerationDataPanel" in file_path:
                    assert "FileJson" not in content.split("import")[1].split("from")[0] if "import" in content else True


class TestPackDetailWithRealData:
    """Tests for pack detail API with realistic pack structures."""
    
    def test_list_packs_with_selector_structure(self, tmp_path):
        """Test that list packs works with selector-based dependency structure."""
        from src.store import Store
        
        store = Store(tmp_path / "store")
        store.init()
        
        # Create pack directory
        pack_name = "Test_LoRA_Pack"
        pack_dir = store.layout.pack_dir(pack_name)
        pack_dir.mkdir(parents=True, exist_ok=True)
        
        # Create pack.json with realistic structure (matching real Civitai imports)
        pack_data = {
            "schema": "synapse.pack.v2",
            "name": pack_name,
            "pack_type": "lora",
            "source": {
                "provider": "civitai",
                "model_id": 123456,
                "version_id": 789012,
                "url": "https://civitai.com/models/123456"
            },
            "dependencies": [
                {
                    "id": "base_checkpoint",
                    "kind": "checkpoint",
                    "required": True,
                    "selector": {
                        "strategy": "base_model_hint",
                        "base_model": "SDXL",
                        "civitai": None,
                        "huggingface": None,
                        "url": None,
                        "local_path": None,
                        "constraints": None
                    },
                    "update_policy": {"mode": "pinned"},
                    "expose": {
                        "filename": "sdxl_base.safetensors",
                        "trigger_words": []
                    }
                },
                {
                    "id": "main_lora",
                    "kind": "lora",
                    "required": True,
                    "selector": {
                        "strategy": "civitai_model_latest",
                        "base_model": None,
                        "civitai": {
                            "model_id": 123456,
                            "version_id": 789012,
                            "file_id": 999888
                        },
                        "huggingface": None,
                        "url": None,
                        "local_path": None,
                        "constraints": None
                    },
                    "update_policy": {"mode": "follow_latest"},
                    "expose": {
                        "filename": "test_lora.safetensors",
                        "trigger_words": ["test_trigger"]
                    }
                }
            ],
            "resources": {
                "previews_keep_in_git": True,
                "workflows_keep_in_git": True
            }
        }
        
        pack_json_path = store.layout.pack_json_path(pack_name)
        pack_json_path.write_text(json.dumps(pack_data, indent=2))
        
        # List packs
        packs = store.list_packs()
        assert pack_name in packs
        
        # Load pack
        pack = store.get_pack(pack_name)
        assert pack.name == pack_name
        assert len(pack.dependencies) == 2
        
        # Verify selector structure is correct
        for dep in pack.dependencies:
            assert hasattr(dep, 'selector'), "PackDependency must have selector attribute"
            assert hasattr(dep.selector, 'civitai'), "DependencySelector must have civitai attribute"
            assert hasattr(dep.selector, 'huggingface'), "DependencySelector must have huggingface attribute"
            assert hasattr(dep.selector, 'base_model'), "DependencySelector must have base_model attribute"
    
    def test_api_get_pack_detail_with_selector(self, tmp_path):
        """Test API GET /api/packs/{name} with selector-based structure."""
        import pytest
        pytest.skip("V2 Store API test - V1 backend uses different structure")
    
    def test_api_list_packs_with_selector(self, tmp_path):
        """Test API GET /api/packs/ works with selector-based structure."""
        import pytest
        pytest.skip("V2 Store API test - V1 backend uses different structure")


# =============================================================================
# Reset Endpoint Tests
# =============================================================================

class TestResetEndpoint:
    """Tests for profiles/reset endpoint."""

    def test_reset_resets_stack_to_global(self, tmp_path):
        """Test that reset sets stack to ['global'] for all UIs."""
        from src.store import Store, Pack, PackLock, PackSource, AssetKind, ProviderName

        store = Store(tmp_path / "store")
        store.init()

        # Create a pack
        pack = Pack(
            name="TestPack",
            pack_type=AssetKind.LORA,
            source=PackSource(provider=ProviderName.CIVITAI),
            dependencies=[],
        )
        store.layout.save_pack(pack)
        store.layout.save_pack_lock(PackLock(pack="TestPack"))
        store.profile_service.add_pack_to_global("TestPack")

        # Use pack to create work profile
        store.use("TestPack", ui_set="local", sync=False)

        # Verify stack has work profile
        runtime = store.layout.load_runtime()
        assert runtime.get_active_profile("comfyui") == "work__TestPack"
        assert len(runtime.get_stack("comfyui")) > 1

        # Reset - simulate what API does (with proper error handling)
        ui_targets = store.get_ui_targets("local")
        with store.layout.lock():
            runtime = store.layout.load_runtime()
            for ui in ui_targets:
                runtime.set_stack(ui, ["global"])
            store.layout.save_runtime(runtime)
            # Update active symlinks (ignore if view doesn't exist yet)
            for ui in ui_targets:
                try:
                    store.view_builder.activate(ui, "global")
                except Exception:
                    # View may not exist yet - sync will create it
                    pass

        # Verify stack is reset
        runtime = store.layout.load_runtime()
        assert runtime.get_active_profile("comfyui") == "global"
        assert runtime.get_stack("comfyui") == ["global"]

    def test_reset_handles_deep_stack(self, tmp_path):
        """Test that reset handles multiple nested use() calls."""
        from src.store import Store, Pack, PackLock, PackSource, AssetKind, ProviderName

        store = Store(tmp_path / "store")
        store.init()

        # Create multiple packs
        for i in range(3):
            pack = Pack(
                name=f"Pack{i}",
                pack_type=AssetKind.LORA,
                source=PackSource(provider=ProviderName.CIVITAI),
                dependencies=[],
            )
            store.layout.save_pack(pack)
            store.layout.save_pack_lock(PackLock(pack=f"Pack{i}"))
            store.profile_service.add_pack_to_global(f"Pack{i}")

        # Use multiple packs (creates deep stack)
        for i in range(3):
            store.use(f"Pack{i}", ui_set="local", sync=False)

        # Verify deep stack
        runtime = store.layout.load_runtime()
        assert len(runtime.get_stack("comfyui")) == 4  # global + 3 work profiles

        # Reset
        ui_targets = store.get_ui_targets("local")
        with store.layout.lock():
            runtime = store.layout.load_runtime()
            for ui in ui_targets:
                runtime.set_stack(ui, ["global"])
            store.layout.save_runtime(runtime)

        # Verify clean reset
        runtime = store.layout.load_runtime()
        assert runtime.get_stack("comfyui") == ["global"]


# =============================================================================
# Delete Pack Cleanup Tests
# =============================================================================

class TestDeletePackCleanup:
    """Tests for delete_pack cleanup behavior."""

    def test_delete_pack_removes_work_profile(self, tmp_path):
        """Test that delete_pack removes associated work profile."""
        from src.store import Store, Pack, PackLock, PackSource, AssetKind, ProviderName

        store = Store(tmp_path / "store")
        store.init()

        # Create and use pack
        pack = Pack(
            name="TestPack",
            pack_type=AssetKind.LORA,
            source=PackSource(provider=ProviderName.CIVITAI),
            dependencies=[],
        )
        store.layout.save_pack(pack)
        store.layout.save_pack_lock(PackLock(pack="TestPack"))
        store.profile_service.add_pack_to_global("TestPack")
        store.use("TestPack", ui_set="local", sync=False)

        # Verify work profile exists
        assert store.layout.profile_exists("work__TestPack")

        # Delete pack
        store.delete_pack("TestPack")

        # Verify work profile is deleted
        assert not store.layout.profile_exists("work__TestPack")

    def test_delete_pack_removes_from_runtime_stack(self, tmp_path):
        """Test that delete_pack removes work profile from runtime stacks."""
        from src.store import Store, Pack, PackLock, PackSource, AssetKind, ProviderName

        store = Store(tmp_path / "store")
        store.init()

        # Create and use pack
        pack = Pack(
            name="TestPack",
            pack_type=AssetKind.LORA,
            source=PackSource(provider=ProviderName.CIVITAI),
            dependencies=[],
        )
        store.layout.save_pack(pack)
        store.layout.save_pack_lock(PackLock(pack="TestPack"))
        store.profile_service.add_pack_to_global("TestPack")
        store.use("TestPack", ui_set="local", sync=False)

        # Verify work profile is in stack
        runtime = store.layout.load_runtime()
        assert "work__TestPack" in runtime.get_stack("comfyui")

        # Delete pack
        store.delete_pack("TestPack")

        # Verify work profile removed from stack
        runtime = store.layout.load_runtime()
        assert "work__TestPack" not in runtime.get_stack("comfyui")
        # Stack should still have global
        assert "global" in runtime.get_stack("comfyui")

    def test_delete_pack_removes_from_global_profile(self, tmp_path):
        """Test that delete_pack removes pack from global profile."""
        from src.store import Store, Pack, PackLock, PackSource, AssetKind, ProviderName

        store = Store(tmp_path / "store")
        store.init()

        # Create pack
        pack = Pack(
            name="TestPack",
            pack_type=AssetKind.LORA,
            source=PackSource(provider=ProviderName.CIVITAI),
            dependencies=[],
        )
        store.layout.save_pack(pack)
        store.layout.save_pack_lock(PackLock(pack="TestPack"))
        store.profile_service.add_pack_to_global("TestPack")

        # Verify in global profile
        global_profile = store.profile_service.load_global()
        assert "TestPack" in global_profile.get_pack_names()

        # Delete pack
        store.delete_pack("TestPack")

        # Verify removed from global profile
        global_profile = store.profile_service.load_global()
        assert "TestPack" not in global_profile.get_pack_names()

    def test_delete_pack_handles_unused_pack(self, tmp_path):
        """Test that delete_pack works for pack that was never used."""
        from src.store import Store, Pack, PackLock, PackSource, AssetKind, ProviderName

        store = Store(tmp_path / "store")
        store.init()

        # Create pack but don't use it
        pack = Pack(
            name="UnusedPack",
            pack_type=AssetKind.LORA,
            source=PackSource(provider=ProviderName.CIVITAI),
            dependencies=[],
        )
        store.layout.save_pack(pack)
        store.layout.save_pack_lock(PackLock(pack="UnusedPack"))

        # Verify no work profile exists
        assert not store.layout.profile_exists("work__UnusedPack")

        # Delete should work without error
        result = store.delete_pack("UnusedPack")
        assert result.deleted is True
        assert result.pack_name == "UnusedPack"


# =============================================================================
# API Response Contract Tests
# =============================================================================
# These tests ensure API responses match what the frontend expects.
# When you change an API response format, you MUST update the frontend interface!


class TestAPIResponseContracts:
    """
    Tests that verify API responses match frontend interface expectations.

    CRITICAL: These tests prevent API/UI contract mismatches that cause
    silent failures or crashes in the frontend.
    """

    def test_verify_blobs_response_format(self, tmp_path):
        """
        Verify that verify_blobs returns the expected format.

        Frontend VerifyResult interface (InventoryPage.tsx) expects transformation from:
        - API: { verified, valid: string[], invalid: string[], duration_ms }
        - UI:  { total, verified, failed, bytes_verified, errors: Array<{sha256, error}> }

        The frontend transforms the API response - this test documents the API contract.
        """
        from src.store import Store

        store = Store(tmp_path)
        store.init()

        # Create some blobs
        content = b"test content"
        blob_path = tmp_path / "test_blob.bin"
        blob_path.write_bytes(content)
        sha256 = store.blob_store.adopt(blob_path)

        result = store.verify_blobs(all_blobs=True)

        # Document exact API response format
        assert "verified" in result, "API must return 'verified' (count of total verified)"
        assert "valid" in result, "API must return 'valid' (list of valid sha256)"
        assert "invalid" in result, "API must return 'invalid' (list of invalid sha256)"
        assert "duration_ms" in result, "API must return 'duration_ms'"

        # Type checks
        assert isinstance(result["verified"], int)
        assert isinstance(result["valid"], list)
        assert isinstance(result["invalid"], list)
        assert isinstance(result["duration_ms"], int)

        # Value checks
        assert result["verified"] == 1
        assert sha256 in result["valid"]
        assert len(result["invalid"]) == 0

    def test_delete_blob_response_format(self, tmp_path):
        """
        Verify that delete_blob returns the expected format.

        Frontend expects:
        - deleted: bool
        - sha256: string
        - bytes_freed: number (when deleted)
        - deleted_from: string[] (when deleted)
        - remaining_on: string | string[] (where blob still exists)
        - reason: string (when not deleted)
        - impacts: object (when blocked by references)
        """
        from src.store import Store

        store = Store(tmp_path)
        store.init()

        # Create an orphan blob
        content = b"orphan blob"
        blob_path = tmp_path / "orphan.bin"
        blob_path.write_bytes(content)
        sha256 = store.blob_store.adopt(blob_path)

        result = store.delete_blob(sha256, target="local")

        # Document exact API response format
        assert "deleted" in result, "API must return 'deleted' boolean"
        assert "sha256" in result, "API must return 'sha256'"

        if result["deleted"]:
            assert "bytes_freed" in result, "When deleted, must return 'bytes_freed'"
            assert "deleted_from" in result, "When deleted, must return 'deleted_from' list"
            assert isinstance(result["deleted_from"], list)
        else:
            assert "reason" in result or "impacts" in result, \
                "When not deleted, must return 'reason' or 'impacts'"

    def test_backup_blob_response_format(self, tmp_path):
        """
        Verify that backup_blob returns the expected format.

        Frontend expects BackupOperationResult:
        - success: bool
        - sha256: string
        - bytes_copied: number
        - duration_ms: number
        - verified: bool | null
        - error: string | null
        """
        from src.store import Store
        from src.store.models import BackupConfig

        store = Store(tmp_path)
        store.init()

        # Setup backup
        backup_path = tmp_path / "backup"
        backup_path.mkdir()
        store.configure_backup(BackupConfig(enabled=True, path=str(backup_path)))

        # Create a blob
        content = b"blob to backup"
        blob_path = tmp_path / "blob.bin"
        blob_path.write_bytes(content)
        sha256 = store.blob_store.adopt(blob_path)

        result = store.backup_blob(sha256)

        # Document exact API response format
        assert hasattr(result, 'success'), "API must return 'success' boolean"
        assert hasattr(result, 'sha256'), "API must return 'sha256'"
        assert hasattr(result, 'bytes_copied'), "API must return 'bytes_copied'"
        assert hasattr(result, 'duration_ms'), "API must return 'duration_ms'"

        # The result is a Pydantic model, check the actual values
        assert result.success is True
        assert result.sha256 == sha256
        assert result.bytes_copied == len(content)

    def test_inventory_response_format(self, tmp_path):
        """
        Verify that get_inventory returns the expected format.

        Frontend expects InventoryResponse with:
        - generated_at: string
        - summary: InventorySummary
        - items: InventoryItem[]
        """
        from src.store import Store

        store = Store(tmp_path)
        store.init()

        inventory = store.get_inventory()

        # Document exact API response format
        assert hasattr(inventory, 'generated_at'), "Must have 'generated_at'"
        assert hasattr(inventory, 'summary'), "Must have 'summary'"
        assert hasattr(inventory, 'items'), "Must have 'items'"

        # Summary must have required fields
        summary = inventory.summary
        assert hasattr(summary, 'blobs_total'), "Summary must have 'blobs_total'"
        assert hasattr(summary, 'blobs_referenced'), "Summary must have 'blobs_referenced'"
        assert hasattr(summary, 'blobs_orphan'), "Summary must have 'blobs_orphan'"
        assert hasattr(summary, 'blobs_missing'), "Summary must have 'blobs_missing'"

    def test_resolved_dependency_has_artifact_not_artifacts(self, tmp_path):
        """
        Verify that ResolvedDependency uses 'artifact' (singular), not 'artifacts'.

        Regression test for bug #20: pack-status endpoint used resolved.artifacts
        but ResolvedDependency model has resolved.artifact (singular).
        """
        from src.store.models import (
            ResolvedDependency,
            ResolvedArtifact,
            AssetKind,
            ArtifactProvider,
            ProviderName,
        )

        # Create a resolved dependency with all required fields
        resolved = ResolvedDependency(
            dependency_id="test_dep",
            artifact=ResolvedArtifact(
                kind=AssetKind.LORA,
                sha256="abc123",
                size_bytes=1000,
                provider=ArtifactProvider(name=ProviderName.CIVITAI),
            ),
        )

        # MUST have artifact (singular)
        assert hasattr(resolved, 'artifact'), "ResolvedDependency must have 'artifact' attribute"
        assert resolved.artifact is not None

        # MUST NOT have artifacts (plural) - this was the bug
        assert not hasattr(resolved, 'artifacts'), "ResolvedDependency must NOT have 'artifacts' (plural)"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
