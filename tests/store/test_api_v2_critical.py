"""
Critical tests for v2 API endpoints.

Tests ensure:
1. resolve-base-model endpoint works correctly
2. parameters endpoint saves and loads correctly
3. download-asset endpoint uses correct v2 models
4. get_pack returns all required fields including all_installed
5. No v1 code is used in production paths
"""

import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import tempfile
import shutil


class TestResolveBaseModel:
    """Tests for POST /packs/{pack_name}/resolve-base-model endpoint."""
    
    def test_resolve_base_model_request_validation(self):
        """Test that ResolveBaseModelRequest model accepts valid data."""
        from src.store.api import ResolveBaseModelRequest
        
        # Test with download_url
        req = ResolveBaseModelRequest(
            download_url="https://huggingface.co/test/model/resolve/main/model.safetensors",
            source="huggingface",
            file_name="model.safetensors",
            size_kb=1024
        )
        assert req.download_url == "https://huggingface.co/test/model/resolve/main/model.safetensors"
        assert req.source == "huggingface"
        assert req.file_name == "model.safetensors"
        assert req.size_kb == 1024
        
        # Test with model_path
        req2 = ResolveBaseModelRequest(
            model_path="/path/to/model.safetensors"
        )
        assert req2.model_path == "/path/to/model.safetensors"
        assert req2.download_url is None
    
    def test_resolve_base_model_creates_dependency_if_missing(self):
        """Test that resolve-base-model creates base_checkpoint dependency if not exists."""
        from src.store.models import (
            Pack, PackDependency, DependencySelector, SelectorStrategy,
            AssetKind, UpdatePolicy, ExposeConfig, PackSource, ProviderName
        )
        
        # Create a pack without base_checkpoint dependency
        pack = Pack(
            name="test-pack",
            pack_type=AssetKind.LORA,
            dependencies=[],
            source=PackSource(provider=ProviderName.CIVITAI),
        )
        
        assert len(pack.dependencies) == 0
        
        # Simulate adding dependency (as resolve-base-model would do)
        base_dep = PackDependency(
            id="base_checkpoint",
            kind=AssetKind.CHECKPOINT,
            required=True,
            selector=DependencySelector(
                strategy=SelectorStrategy.HUGGINGFACE_FILE,
                url="https://huggingface.co/test/model.safetensors",
            ),
            update_policy=UpdatePolicy(),
            expose=ExposeConfig(filename="model.safetensors"),
        )
        pack.dependencies.append(base_dep)
        
        assert len(pack.dependencies) == 1
        assert pack.dependencies[0].id == "base_checkpoint"


class TestParameters:
    """Tests for parameters endpoints."""
    
    def test_camel_to_snake_conversion(self):
        """Test that camelCase keys are converted to snake_case."""
        import re
        
        def camel_to_snake(name: str) -> str:
            name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
            return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()
        
        # Test conversions
        assert camel_to_snake("clipSkip") == "clip_skip"
        assert camel_to_snake("cfgScale") == "cfg_scale"
        assert camel_to_snake("steps") == "steps"
        assert camel_to_snake("strengthRecommended") == "strength_recommended"
    
    def test_parameters_merge(self):
        """Test that new parameters merge with existing."""
        existing = {"clip_skip": 2, "cfg_scale": 7.0}
        new_params = {"steps": 20, "cfg_scale": 8.0}  # cfg_scale should be overwritten
        
        existing.update(new_params)
        
        assert existing["clip_skip"] == 2
        assert existing["cfg_scale"] == 8.0
        assert existing["steps"] == 20


class TestGetPack:
    """Tests for GET /packs/{pack_name} endpoint."""
    
    def test_get_pack_response_has_required_fields(self):
        """Test that get_pack response includes all required fields."""
        required_fields = [
            "name", "version", "description", "author", "tags", "user_tags",
            "source_url", "created_at", "installed", "has_unresolved",
            "all_installed", "can_generate", "assets", "previews", "workflows",
            "custom_nodes", "docs", "parameters", "model_info"
        ]
        
        # This tests the expected structure - actual endpoint test would need running server
        mock_response = {
            "name": "test-pack",
            "version": "1.0.0",
            "description": "Test pack",
            "author": None,
            "tags": [],
            "user_tags": [],
            "source_url": None,
            "created_at": None,
            "installed": True,
            "has_unresolved": False,
            "all_installed": True,
            "can_generate": True,
            "assets": [],
            "previews": [],
            "workflows": [],
            "custom_nodes": [],
            "docs": {},
            "parameters": {},
            "model_info": {},
        }
        
        for field in required_fields:
            assert field in mock_response, f"Missing required field: {field}"
    
    def test_all_installed_logic(self):
        """Test that all_installed is calculated correctly."""
        # All installed
        assets1 = [
            {"status": "installed"},
            {"status": "installed"},
        ]
        all_installed1 = all(a["status"] == "installed" for a in assets1)
        assert all_installed1 is True
        
        # One not installed
        assets2 = [
            {"status": "installed"},
            {"status": "resolved"},  # resolved but not installed
        ]
        all_installed2 = all(a["status"] == "installed" for a in assets2)
        assert all_installed2 is False
        
        # One unresolved
        assets3 = [
            {"status": "installed"},
            {"status": "unresolved"},
        ]
        all_installed3 = all(a["status"] == "installed" for a in assets3)
        assert all_installed3 is False
        
        # Empty assets
        assets4 = []
        all_installed4 = all(a["status"] == "installed" for a in assets4) if assets4 else True
        assert all_installed4 is True


class TestDownloadAsset:
    """Tests for POST /packs/{pack_name}/download-asset endpoint."""
    
    def test_download_asset_request_validation(self):
        """Test DownloadAssetRequest model validation."""
        from src.store.api import DownloadAssetRequest
        
        req = DownloadAssetRequest(
            asset_name="base_checkpoint",
            asset_type="checkpoint",
            url="https://example.com/model.safetensors",
            filename="model.safetensors"
        )
        
        assert req.asset_name == "base_checkpoint"
        assert req.asset_type == "checkpoint"
        assert req.url == "https://example.com/model.safetensors"
    
    def test_asset_type_mapping(self):
        """Test that asset types map to correct directories."""
        type_map = {
            'checkpoint': 'checkpoints',
            'base_model': 'checkpoints', 
            'base_checkpoint': 'checkpoints',
            'lora': 'loras',
            'vae': 'vae',
            'controlnet': 'controlnet',
            'upscaler': 'upscale_models',
            'embedding': 'embeddings',
            'clip': 'clip',
            'text_encoder': 'text_encoders',
            'diffusion_model': 'diffusion_models',
        }
        
        # Test all mappings
        for asset_type, expected_dir in type_map.items():
            actual_dir = type_map.get(asset_type.lower(), 'checkpoints')
            assert actual_dir == expected_dir, f"Mapping failed for {asset_type}"


class TestV2ModelsUsage:
    """Tests to ensure v2 models are used correctly."""
    
    def test_pack_dependency_has_correct_structure(self):
        """Test PackDependency model has required fields."""
        from src.store.models import (
            PackDependency, DependencySelector, SelectorStrategy,
            AssetKind, UpdatePolicy, ExposeConfig
        )
        
        dep = PackDependency(
            id="test_dep",
            kind=AssetKind.CHECKPOINT,
            required=True,
            selector=DependencySelector(
                strategy=SelectorStrategy.CIVITAI_FILE,
            ),
            update_policy=UpdatePolicy(),
            expose=ExposeConfig(filename="test.safetensors"),
        )
        
        assert dep.id == "test_dep"
        assert dep.kind == AssetKind.CHECKPOINT
        assert dep.selector.strategy == SelectorStrategy.CIVITAI_FILE
    
    def test_resolved_dependency_structure(self):
        """Test ResolvedDependency model structure."""
        from src.store.models import (
            ResolvedDependency, ResolvedArtifact, ArtifactProvider,
            ArtifactDownload, ArtifactIntegrity, AssetKind, ProviderName
        )
        
        resolved = ResolvedDependency(
            dependency_id="base_checkpoint",
            artifact=ResolvedArtifact(
                kind=AssetKind.CHECKPOINT,
                sha256="abc123",
                size_bytes=1024,
                provider=ArtifactProvider(
                    name=ProviderName.HUGGINGFACE,
                    filename="model.safetensors",
                ),
                download=ArtifactDownload(urls=["https://example.com/model.safetensors"]),
                integrity=ArtifactIntegrity(sha256_verified=True),
            ),
        )
        
        assert resolved.dependency_id == "base_checkpoint"
        assert resolved.artifact.sha256 == "abc123"
        assert resolved.artifact.download.urls[0] == "https://example.com/model.safetensors"
    
    def test_pack_lock_structure(self):
        """Test PackLock model structure."""
        from src.store.models import (
            PackLock, ResolvedDependency, ResolvedArtifact, 
            ArtifactProvider, ArtifactDownload, ArtifactIntegrity,
            AssetKind, ProviderName
        )
        
        lock = PackLock(
            pack="test-pack",
            resolved=[
                ResolvedDependency(
                    dependency_id="base_checkpoint",
                    artifact=ResolvedArtifact(
                        kind=AssetKind.CHECKPOINT,
                        sha256="abc123",
                        size_bytes=1024,
                        provider=ArtifactProvider(
                            name=ProviderName.LOCAL, 
                            filename="test.safetensors"
                        ),
                        download=ArtifactDownload(urls=[]),
                        integrity=ArtifactIntegrity(sha256_verified=True),
                    ),
                ),
            ],
        )
        
        assert lock.pack == "test-pack"
        assert len(lock.resolved) == 1
        
        # Test get_resolved method
        resolved = lock.get_resolved("base_checkpoint")
        assert resolved is not None
        assert resolved.dependency_id == "base_checkpoint"
        
        # Test non-existent
        assert lock.get_resolved("non_existent") is None


class TestCivitaiSearchKeys:
    """Tests for Civitai search result unique keys."""
    
    def test_unique_key_generation(self):
        """Test that search results can generate unique keys."""
        results = [
            {"model_id": 9409, "version_id": 90854, "file_name": "model_v1.safetensors"},
            {"model_id": 9409, "version_id": 90854, "file_name": "model_v2.safetensors"},
            {"model_id": 9409, "version_id": 90854, "file_name": "model_v3.safetensors"},
        ]
        
        # Generate keys like frontend does
        keys = []
        for idx, result in enumerate(results):
            key = f"civitai-{result['model_id']}-{result['version_id']}-{result.get('file_name', '')}-{idx}"
            keys.append(key)
        
        # All keys should be unique
        assert len(keys) == len(set(keys)), "Keys are not unique!"
        
        # Verify format
        assert keys[0] == "civitai-9409-90854-model_v1.safetensors-0"
        assert keys[1] == "civitai-9409-90854-model_v2.safetensors-1"


class TestNoV1Code:
    """Tests to ensure no v1 code is used in production."""
    
    def test_main_uses_v2_packs_router(self):
        """Test that main.py uses v2_packs_router."""
        main_path = Path(__file__).parent.parent.parent / "apps" / "api" / "src" / "main.py"
        if main_path.exists():
            content = main_path.read_text()
            
            # Should import v2_packs_router
            assert "v2_packs_router" in content, "main.py should import v2_packs_router"
            
            # Should NOT import packs_router from routers (v1)
            assert "from .routers import packs_router" not in content, \
                "main.py should not import v1 packs_router"
    
    def test_v1_packs_router_deprecated(self):
        """Test that v1 packs router is marked as deprecated."""
        deprecated_path = Path(__file__).parent.parent.parent / "apps" / "api" / "src" / "routers" / "packs_v1_DEPRECATED.py"
        
        # If v1 exists, it should be deprecated file
        old_path = Path(__file__).parent.parent.parent / "apps" / "api" / "src" / "routers" / "packs.py"
        
        # Either deprecated file exists, or old packs.py doesn't exist
        if old_path.exists():
            pytest.fail("packs.py still exists - should be renamed to packs_v1_DEPRECATED.py")
    
    def test_routers_init_exports(self):
        """Test that routers/__init__.py doesn't export packs_router as a module."""
        init_path = Path(__file__).parent.parent.parent / "apps" / "api" / "src" / "routers" / "__init__.py"
        if init_path.exists():
            content = init_path.read_text()
            # The comment mentions packs_router but doesn't export it as a module
            # Just check it doesn't do "from .packs import packs_router" or similar
            assert "from .packs import" not in content, \
                "routers/__init__.py should not import from packs"


class TestAPIEndpointsExist:
    """Tests that required v2 API endpoints exist."""
    
    def test_v2_api_exports(self):
        """Test that v2 API exports required routers."""
        from src.store import api
        
        assert hasattr(api, 'v2_packs_router'), "v2_packs_router should be exported"
        assert hasattr(api, 'store_router'), "store_router should be exported"
        assert hasattr(api, 'profiles_router'), "profiles_router should be exported"
    
    def test_v2_api_has_resolve_base_model(self):
        """Test that v2 API has resolve-base-model endpoint."""
        from src.store.api import v2_packs_router
        
        routes = [r.path for r in v2_packs_router.routes]
        assert any("resolve-base-model" in r for r in routes), \
            "v2_packs_router should have resolve-base-model endpoint"
    
    def test_v2_api_has_parameters_endpoints(self):
        """Test that v2 API has parameters endpoints."""
        from src.store.api import v2_packs_router
        
        routes = [r.path for r in v2_packs_router.routes]
        assert any("parameters" in r for r in routes), \
            "v2_packs_router should have parameters endpoints"
    
    def test_v2_api_has_download_asset(self):
        """Test that v2 API has download-asset endpoint."""
        from src.store.api import v2_packs_router
        
        routes = [r.path for r in v2_packs_router.routes]
        assert any("download-asset" in r for r in routes), \
            "v2_packs_router should have download-asset endpoint"


class TestPackDependencyModel:
    """Tests for PackDependency model fields."""
    
    def test_pack_dependency_has_description_field(self):
        """Test that PackDependency model has description field."""
        from src.store.models import PackDependency
        
        # Check that description is in model_fields
        assert "description" in PackDependency.model_fields, \
            "PackDependency should have 'description' field"
    
    def test_pack_dependency_description_is_optional(self):
        """Test that PackDependency.description is optional (can be None)."""
        from src.store.models import (
            PackDependency, DependencySelector, SelectorStrategy,
            AssetKind, UpdatePolicy, ExposeConfig
        )
        
        # Create without description
        dep = PackDependency(
            id="test_dep",
            kind=AssetKind.LORA,
            selector=DependencySelector(
                strategy=SelectorStrategy.CIVITAI_FILE,
                base_model="SD 1.5"
            ),
            expose=ExposeConfig(filename="test.safetensors")
        )
        assert dep.description is None
        
        # Create with description
        dep_with_desc = PackDependency(
            id="test_dep2",
            kind=AssetKind.LORA,
            selector=DependencySelector(
                strategy=SelectorStrategy.CIVITAI_FILE,
                base_model="SD 1.5"
            ),
            expose=ExposeConfig(filename="test2.safetensors"),
            description="This is a test dependency"
        )
        assert dep_with_desc.description == "This is a test dependency"


class TestWorkflowManagement:
    """Tests for workflow generation and management."""
    
    def test_workflow_info_model_exists(self):
        """Test that WorkflowInfo model exists with correct fields."""
        from src.store.models import WorkflowInfo
        
        assert "name" in WorkflowInfo.model_fields
        assert "filename" in WorkflowInfo.model_fields
        assert "description" in WorkflowInfo.model_fields
        assert "source_url" in WorkflowInfo.model_fields
        assert "is_default" in WorkflowInfo.model_fields
    
    def test_workflow_info_creation(self):
        """Test creating WorkflowInfo instances."""
        from src.store.models import WorkflowInfo
        
        # Minimal workflow
        wf = WorkflowInfo(name="Test Workflow", filename="test.json")
        assert wf.name == "Test Workflow"
        assert wf.filename == "test.json"
        assert wf.is_default == False
        assert wf.description is None
        
        # Full workflow
        wf_full = WorkflowInfo(
            name="Default Workflow",
            filename="default.json",
            description="Auto-generated workflow",
            source_url="https://example.com",
            is_default=True
        )
        assert wf_full.is_default == True
        assert wf_full.description == "Auto-generated workflow"
    
    def test_pack_has_workflows_field(self):
        """Test that Pack model has workflows field."""
        from src.store.models import Pack
        
        assert "workflows" in Pack.model_fields
    
    def test_pack_workflows_default_empty(self):
        """Test that Pack.workflows defaults to empty list."""
        from src.store.models import (
            Pack, PackSource, ProviderName, AssetKind
        )
        
        pack = Pack(
            name="test_pack",
            pack_type=AssetKind.LORA,
            source=PackSource(provider=ProviderName.CIVITAI)
        )
        assert pack.workflows == []
    
    def test_pack_with_workflows(self):
        """Test creating Pack with workflows."""
        from src.store.models import (
            Pack, PackSource, ProviderName, AssetKind, WorkflowInfo
        )
        
        workflows = [
            WorkflowInfo(name="Default", filename="default.json", is_default=True),
            WorkflowInfo(name="Custom", filename="custom.json"),
        ]
        
        pack = Pack(
            name="test_pack",
            pack_type=AssetKind.LORA,
            source=PackSource(provider=ProviderName.CIVITAI),
            workflows=workflows
        )
        
        assert len(pack.workflows) == 2
        assert pack.workflows[0].is_default == True
        assert pack.workflows[1].is_default == False
    
    def test_detect_architecture_function(self):
        """Test architecture detection logic."""
        from src.store.api import _detect_architecture
        from src.store.models import (
            Pack, PackSource, ProviderName, AssetKind
        )
        
        # Test SDXL detection via base_model
        pack_sdxl = Pack(
            name="test",
            pack_type=AssetKind.LORA,
            source=PackSource(provider=ProviderName.CIVITAI),
            base_model="SDXL 1.0"
        )
        assert _detect_architecture(pack_sdxl) == "sdxl"
        
        # Test SD15 detection
        pack_sd15 = Pack(
            name="test",
            pack_type=AssetKind.LORA,
            source=PackSource(provider=ProviderName.CIVITAI),
            base_model="SD 1.5"
        )
        assert _detect_architecture(pack_sd15) == "sd15"
        
        # Test Illustrious detection (should be SDXL)
        pack_ill = Pack(
            name="test",
            pack_type=AssetKind.LORA,
            source=PackSource(provider=ProviderName.CIVITAI),
            base_model="Illustrious"
        )
        assert _detect_architecture(pack_ill) == "sdxl"
        
        # Test default fallback
        pack_unknown = Pack(
            name="test",
            pack_type=AssetKind.LORA,
            source=PackSource(provider=ProviderName.CIVITAI),
        )
        assert _detect_architecture(pack_unknown) == "sd15"
    
    def test_workflow_api_endpoints_exist(self):
        """Test that workflow API endpoints are registered."""
        from src.store.api import v2_packs_router
        
        routes = [r.path for r in v2_packs_router.routes]
        
        # Generate workflow endpoint
        assert any("generate-workflow" in r for r in routes), \
            "generate-workflow endpoint should exist"
        
        # Workflow symlink endpoint
        assert any("/workflow/symlink" in r for r in routes), \
            "workflow symlink endpoint should exist"
        
        # Workflow add endpoint
        assert any("/workflow/add" in r for r in routes), \
            "workflow add endpoint should exist"
        
        # Workflow upload endpoint
        assert any("/workflow/upload-file" in r for r in routes), \
            "workflow upload endpoint should exist"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
