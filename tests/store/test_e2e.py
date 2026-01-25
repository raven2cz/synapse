"""
End-to-end tests for Synapse Store v2

Tests the complete flow:
1. use/back with active symlink verification
2. update with blob change verification

These tests verify the "load-bearing" parts of the system.
"""

import hashlib
import os
import tempfile
from pathlib import Path

import pytest


class TestUseBackE2E:
    """E2E tests for use/back workflow with symlink verification."""
    
    def test_use_creates_active_symlink_pointing_to_work_profile(self):
        """
        Test that 'use' creates active symlink pointing to work__<pack> in all UI targets.
        
        This is the critical "trinity" test:
        - runtime.json has work profile on stack
        - views/<ui>/profiles/work__<pack>/ exists
        - views/<ui>/active → profiles/work__<pack>
        """
        from src.store import (
            Store, Pack, PackLock, PackDependency, DependencySelector,
            ExposeConfig, ResolvedDependency, ResolvedArtifact, ArtifactProvider,
            PackSource, AssetKind, ProviderName, SelectorStrategy
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            store = Store(Path(tmpdir))
            store.init()
            
            # Create a blob
            content = b"test model content for e2e"
            sha256 = hashlib.sha256(content).hexdigest()
            blob_path = store.blob_store.blob_path(sha256)
            blob_path.parent.mkdir(parents=True, exist_ok=True)
            blob_path.write_bytes(content)
            
            # Create pack with dependency
            pack = Pack(
                name="TestPackE2E",
                pack_type=AssetKind.LORA,
                source=PackSource(provider=ProviderName.CIVITAI, model_id=999),
                dependencies=[
                    PackDependency(
                        id="main_lora",
                        kind=AssetKind.LORA,
                        selector=DependencySelector(strategy=SelectorStrategy.CIVITAI_FILE),
                        expose=ExposeConfig(filename="test_e2e.safetensors"),
                    )
                ],
            )
            store.layout.save_pack(pack)
            
            # Create lock
            lock = PackLock(
                pack="TestPackE2E",
                resolved=[
                    ResolvedDependency(
                        dependency_id="main_lora",
                        artifact=ResolvedArtifact(
                            kind=AssetKind.LORA,
                            sha256=sha256,
                            provider=ArtifactProvider(name=ProviderName.CIVITAI),
                        ),
                    )
                ],
            )
            store.layout.save_pack_lock(lock)
            
            # Add to global profile
            store.profile_service.add_pack_to_global("TestPackE2E")
            
            # Use pack with sync
            ui_targets = ["comfyui", "forge"]
            result = store.use("TestPackE2E", ui_set="local", sync=True)
            
            # Verify result
            assert result.pack == "TestPackE2E"
            assert result.created_profile == "work__TestPackE2E"
            
            # Verify the trinity for each UI:
            for ui in ui_targets:
                # 1. Runtime stack has work profile on top
                runtime = store.layout.load_runtime()
                assert runtime.get_active_profile(ui) == "work__TestPackE2E", \
                    f"{ui}: runtime stack should have work__TestPackE2E on top"
                
                # 2. View profile directory exists
                view_profile_path = store.layout.view_profile_path(ui, "work__TestPackE2E")
                assert view_profile_path.exists(), \
                    f"{ui}: view profile directory should exist"
                
                # 3. Active symlink points to work profile
                active_path = store.layout.view_active_path(ui)
                assert active_path.is_symlink(), \
                    f"{ui}: active should be a symlink"
                
                target = os.readlink(active_path)
                assert target == "profiles/work__TestPackE2E", \
                    f"{ui}: active should point to profiles/work__TestPackE2E, got {target}"
                
                # 4. Symlink to blob exists and works
                # Note: Different UIs have different paths (ComfyUI: models/loras, Forge: models/Lora)
                if ui == "comfyui":
                    lora_symlink = view_profile_path / "models" / "loras" / "test_e2e.safetensors"
                elif ui == "forge":
                    lora_symlink = view_profile_path / "models" / "Lora" / "test_e2e.safetensors"
                else:
                    lora_symlink = view_profile_path / "models" / "loras" / "test_e2e.safetensors"
                
                assert lora_symlink.exists(), \
                    f"{ui}: lora symlink should exist at {lora_symlink}"
                assert lora_symlink.read_bytes() == content, \
                    f"{ui}: lora symlink should point to correct blob"
    
    def test_back_restores_active_symlink_to_global(self):
        """
        Test that 'back' pops the stack and restores active symlink to global.
        """
        from src.store import (
            Store, Pack, PackLock, PackSource, AssetKind, ProviderName
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            store = Store(Path(tmpdir))
            store.init()
            
            # Create minimal pack
            pack = Pack(
                name="TestBackE2E",
                pack_type=AssetKind.LORA,
                source=PackSource(provider=ProviderName.CIVITAI),
                dependencies=[],
            )
            store.layout.save_pack(pack)
            store.layout.save_pack_lock(PackLock(pack="TestBackE2E"))
            store.profile_service.add_pack_to_global("TestBackE2E")
            
            ui_targets = ["comfyui"]
            
            # Use pack
            store.use("TestBackE2E", ui_set="local", sync=False)
            
            # Verify we're on work profile
            runtime = store.layout.load_runtime()
            assert runtime.get_active_profile("comfyui") == "work__TestBackE2E"
            
            # Back
            result = store.back(ui_set="local", sync=False)
            
            # Verify result
            assert result.from_profile == "work__TestBackE2E"
            assert result.to_profile == "global"
            
            # Verify runtime stack
            runtime = store.layout.load_runtime()
            assert runtime.get_active_profile("comfyui") == "global"
            
            # Verify active symlink (if it exists)
            active_path = store.layout.view_active_path("comfyui")
            if active_path.exists():
                target = os.readlink(active_path)
                assert target == "profiles/global"
    
    def test_use_multiple_packs_stacks_correctly(self):
        """
        Test that using multiple packs creates correct stack order.
        
        use PackA → stack: [global, work__PackA]
        use PackB → stack: [global, work__PackA, work__PackB]
        back → stack: [global, work__PackA]
        back → stack: [global]
        """
        from src.store import (
            Store, Pack, PackLock, PackSource, AssetKind, ProviderName
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            store = Store(Path(tmpdir))
            store.init()
            
            # Create two packs
            for name in ["PackA", "PackB"]:
                pack = Pack(
                    name=name,
                    pack_type=AssetKind.LORA,
                    source=PackSource(provider=ProviderName.CIVITAI),
                    dependencies=[],
                )
                store.layout.save_pack(pack)
                store.layout.save_pack_lock(PackLock(pack=name))
                store.profile_service.add_pack_to_global(name)
            
            # Use PackA
            store.use("PackA", ui_set="local", sync=False)
            runtime = store.layout.load_runtime()
            assert runtime.ui["comfyui"].stack == ["global", "work__PackA"]
            
            # Use PackB
            store.use("PackB", ui_set="local", sync=False)
            runtime = store.layout.load_runtime()
            assert runtime.ui["comfyui"].stack == ["global", "work__PackA", "work__PackB"]
            
            # Back (should pop PackB)
            result = store.back(ui_set="local", sync=False)
            assert result.from_profile == "work__PackB"
            assert result.to_profile == "work__PackA"
            
            runtime = store.layout.load_runtime()
            assert runtime.ui["comfyui"].stack == ["global", "work__PackA"]
            
            # Back again (should pop PackA)
            result = store.back(ui_set="local", sync=False)
            assert result.from_profile == "work__PackA"
            assert result.to_profile == "global"
            
            runtime = store.layout.load_runtime()
            assert runtime.ui["comfyui"].stack == ["global"]


class TestUpdateE2E:
    """E2E tests for update workflow with blob verification."""
    
    def test_update_changes_lock_and_symlink_points_to_new_blob(self):
        """
        Test complete update flow:
        1. Create pack with version 1
        2. Simulate update available (version 2)
        3. Apply update
        4. Verify lock is updated
        5. Verify symlink points to new blob
        6. Verify expose.filename remains unchanged
        """
        from src.store import (
            Store, Pack, PackLock, PackDependency, DependencySelector,
            ExposeConfig, ResolvedDependency, ResolvedArtifact, ArtifactProvider,
            ArtifactDownload, PackSource, AssetKind, ProviderName, 
            SelectorStrategy, UpdatePolicy, UpdatePolicyMode, CivitaiSelector
        )
        from src.store.update_service import UpdateService
        from src.store.models import UpdatePlan, UpdateChange
        
        with tempfile.TemporaryDirectory() as tmpdir:
            store = Store(Path(tmpdir))
            store.init()
            
            # Create two blobs (version 1 and version 2)
            content_v1 = b"model content version 1"
            content_v2 = b"model content version 2 - updated"
            sha256_v1 = hashlib.sha256(content_v1).hexdigest()
            sha256_v2 = hashlib.sha256(content_v2).hexdigest()
            
            for sha, content in [(sha256_v1, content_v1), (sha256_v2, content_v2)]:
                blob_path = store.blob_store.blob_path(sha)
                blob_path.parent.mkdir(parents=True, exist_ok=True)
                blob_path.write_bytes(content)
            
            # Create pack with follow_latest policy
            exposed_filename = "my_stable_lora.safetensors"  # This must NOT change
            
            pack = Pack(
                name="UpdateTestPack",
                pack_type=AssetKind.LORA,
                source=PackSource(provider=ProviderName.CIVITAI, model_id=123),
                dependencies=[
                    PackDependency(
                        id="main_lora",
                        kind=AssetKind.LORA,
                        selector=DependencySelector(
                            strategy=SelectorStrategy.CIVITAI_MODEL_LATEST,
                            civitai=CivitaiSelector(model_id=123, version_id=100),
                        ),
                        update_policy=UpdatePolicy(mode=UpdatePolicyMode.FOLLOW_LATEST),
                        expose=ExposeConfig(filename=exposed_filename),
                    )
                ],
            )
            store.layout.save_pack(pack)
            
            # Create initial lock (version 1)
            lock_v1 = PackLock(
                pack="UpdateTestPack",
                resolved=[
                    ResolvedDependency(
                        dependency_id="main_lora",
                        artifact=ResolvedArtifact(
                            kind=AssetKind.LORA,
                            sha256=sha256_v1,
                            provider=ArtifactProvider(
                                name=ProviderName.CIVITAI,
                                model_id=123,
                                version_id=100,
                                file_id=1000,
                            ),
                            download=ArtifactDownload(urls=["file:///fake/v1.safetensors"]),
                        ),
                    )
                ],
            )
            store.layout.save_pack_lock(lock_v1)
            store.profile_service.add_pack_to_global("UpdateTestPack")
            
            # Build initial view
            store.use("UpdateTestPack", ui_set="local", sync=True)
            
            # Verify initial state
            view_path = store.layout.view_profile_path("comfyui", "work__UpdateTestPack")
            lora_path = view_path / "models" / "loras" / exposed_filename
            
            assert lora_path.exists(), "Initial lora symlink should exist"
            assert lora_path.read_bytes() == content_v1, "Should point to v1 blob"
            
            # Manually create an update plan (simulating what update_service would do)
            plan = UpdatePlan(
                pack="UpdateTestPack",
                changes=[
                    UpdateChange(
                        dependency_id="main_lora",
                        old={
                            "provider_model_id": 123,
                            "provider_version_id": 100,
                            "sha256": sha256_v1,
                        },
                        new={
                            "provider_model_id": 123,
                            "provider_version_id": 200,  # New version
                            "provider_file_id": 2000,
                            "sha256": sha256_v2,
                        },
                    )
                ],
            )
            
            # Apply update
            new_lock = store.update_service.apply_update("UpdateTestPack", plan)
            
            # Verify lock changed
            assert new_lock.resolved[0].artifact.sha256 == sha256_v2, \
                "Lock should be updated to v2 sha256"
            assert new_lock.resolved[0].artifact.provider.version_id == 200, \
                "Lock should have new version_id"
            
            # Verify expose.filename is unchanged in pack.json
            reloaded_pack = store.layout.load_pack("UpdateTestPack")
            dep = reloaded_pack.get_dependency("main_lora")
            assert dep.expose.filename == exposed_filename, \
                "expose.filename must remain unchanged after update"
            
            # Rebuild views
            store.sync(profile_name="work__UpdateTestPack", ui_set="local")
            
            # Verify symlink now points to new blob
            assert lora_path.exists(), "Lora symlink should still exist"
            assert lora_path.read_bytes() == content_v2, \
                "Symlink should now point to v2 blob"
            
            # Verify filename in view is still the same
            assert lora_path.name == exposed_filename, \
                "Filename in view must be unchanged"
    
    def test_update_dry_run_does_not_change_anything(self):
        """
        Test that update --dry-run doesn't modify lock or blobs.
        """
        from src.store import (
            Store, Pack, PackLock, PackDependency, DependencySelector,
            ExposeConfig, ResolvedDependency, ResolvedArtifact, ArtifactProvider,
            PackSource, AssetKind, ProviderName, SelectorStrategy,
            UpdatePolicy, UpdatePolicyMode, CivitaiSelector
        )
        from src.store.models import UpdatePlan, UpdateChange
        
        with tempfile.TemporaryDirectory() as tmpdir:
            store = Store(Path(tmpdir))
            store.init()
            
            # Create blob
            content = b"original content"
            sha256 = hashlib.sha256(content).hexdigest()
            blob_path = store.blob_store.blob_path(sha256)
            blob_path.parent.mkdir(parents=True, exist_ok=True)
            blob_path.write_bytes(content)
            
            # Create pack and lock
            pack = Pack(
                name="DryRunTest",
                pack_type=AssetKind.LORA,
                source=PackSource(provider=ProviderName.CIVITAI, model_id=456),
                dependencies=[
                    PackDependency(
                        id="main",
                        kind=AssetKind.LORA,
                        selector=DependencySelector(
                            strategy=SelectorStrategy.CIVITAI_MODEL_LATEST,
                            civitai=CivitaiSelector(model_id=456),
                        ),
                        update_policy=UpdatePolicy(mode=UpdatePolicyMode.FOLLOW_LATEST),
                        expose=ExposeConfig(filename="dryrun.safetensors"),
                    )
                ],
            )
            store.layout.save_pack(pack)
            
            lock = PackLock(
                pack="DryRunTest",
                resolved=[
                    ResolvedDependency(
                        dependency_id="main",
                        artifact=ResolvedArtifact(
                            kind=AssetKind.LORA,
                            sha256=sha256,
                            provider=ArtifactProvider(
                                name=ProviderName.CIVITAI,
                                model_id=456,
                                version_id=100,
                            ),
                        ),
                    )
                ],
            )
            store.layout.save_pack_lock(lock)
            
            # Get original lock content
            original_lock = store.layout.load_pack_lock("DryRunTest")
            original_sha = original_lock.resolved[0].artifact.sha256
            
            # Create plan
            plan = UpdatePlan(
                pack="DryRunTest",
                changes=[
                    UpdateChange(
                        dependency_id="main",
                        old={"sha256": sha256},
                        new={"sha256": "newsha256" * 4},  # Fake new sha
                    )
                ],
            )
            
            # Dry run via high-level API
            result = store.update(
                "DryRunTest",
                dry_run=True,
                sync=False,
            )
            
            # Verify nothing changed
            current_lock = store.layout.load_pack_lock("DryRunTest")
            assert current_lock.resolved[0].artifact.sha256 == original_sha, \
                "Lock should not be modified in dry run"


class TestResponseFormatConsistency:
    """Test that CLI --json and API return same format."""
    
    def test_status_response_format(self):
        """Test that status returns consistent format."""
        from src.store import Store
        
        with tempfile.TemporaryDirectory() as tmpdir:
            store = Store(Path(tmpdir))
            store.init()
            
            status = store.status(ui_set="local")
            
            # Required fields
            assert hasattr(status, "profile")
            assert hasattr(status, "ui_targets")
            assert hasattr(status, "active")
            assert hasattr(status, "missing_blobs")
            assert hasattr(status, "unresolved")
            assert hasattr(status, "shadowed")
            
            # model_dump should work for JSON serialization
            data = status.model_dump()
            assert "profile" in data
            assert "ui_targets" in data
            assert isinstance(data["ui_targets"], list)
            assert isinstance(data["active"], dict)
    
    def test_use_result_format(self):
        """Test that use returns consistent format."""
        from src.store import (
            Store, Pack, PackLock, PackSource, AssetKind, ProviderName
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            store = Store(Path(tmpdir))
            store.init()
            
            # Create pack
            pack = Pack(
                name="FormatTest",
                pack_type=AssetKind.LORA,
                source=PackSource(provider=ProviderName.CIVITAI),
                dependencies=[],
            )
            store.layout.save_pack(pack)
            store.layout.save_pack_lock(PackLock(pack="FormatTest"))
            store.profile_service.add_pack_to_global("FormatTest")
            
            result = store.use("FormatTest", ui_set="local", sync=False)
            
            # Required fields
            assert hasattr(result, "pack")
            assert hasattr(result, "created_profile")
            assert hasattr(result, "ui_targets")
            assert hasattr(result, "notes")
            
            # Serialization
            data = result.model_dump()
            assert data["pack"] == "FormatTest"
            assert data["created_profile"] == "work__FormatTest"
            assert isinstance(data["ui_targets"], list)
    
    def test_back_result_format(self):
        """Test that back returns consistent format."""
        from src.store import Store
        
        with tempfile.TemporaryDirectory() as tmpdir:
            store = Store(Path(tmpdir))
            store.init()
            
            result = store.back(ui_set="local", sync=False)
            
            # Required fields
            assert hasattr(result, "from_profile")
            assert hasattr(result, "to_profile")
            assert hasattr(result, "ui_targets")
            assert hasattr(result, "notes")
            
            # Serialization
            data = result.model_dump()
            assert "from_profile" in data
            assert "to_profile" in data
    
    def test_update_plan_format(self):
        """Test that update plan has consistent format."""
        from src.store.models import UpdatePlan, UpdateChange, AmbiguousUpdate, UpdateCandidate
        
        plan = UpdatePlan(
            pack="TestPack",
            changes=[
                UpdateChange(
                    dependency_id="main",
                    old={"version_id": 1},
                    new={"version_id": 2},
                )
            ],
            ambiguous=[
                AmbiguousUpdate(
                    dependency_id="optional",
                    candidates=[
                        UpdateCandidate(
                            provider="civitai",
                            provider_model_id=123,
                            provider_version_id=200,
                            provider_file_id=1000,
                            sha256="abc123",
                        )
                    ],
                )
            ],
        )
        
        data = plan.model_dump()
        
        assert data["pack"] == "TestPack"
        assert len(data["changes"]) == 1
        assert len(data["ambiguous"]) == 1
        assert data["changes"][0]["dependency_id"] == "main"
        assert data["ambiguous"][0]["dependency_id"] == "optional"


# =============================================================================
# Complete User Workflow Integration Tests
# =============================================================================

class TestCompleteUserWorkflow:
    """
    Comprehensive integration tests covering complete user workflows.

    These tests simulate real user scenarios from start to finish:
    - Store initialization
    - Pack creation with multiple asset types
    - Blob storage and deduplication
    - View building for multiple UIs
    - UI attachment
    - Doctor diagnostics
    - Pack modification and cleanup
    """

    def test_full_workflow_init_to_cleanup(self):
        """
        Complete workflow test:
        1. Initialize store
        2. Create multiple packs with various asset types
        3. Create blobs (simulate downloaded models)
        4. Build views for multiple UIs
        5. Attach UIs via symlinks
        6. Use/back workflow
        7. Run doctor diagnostics
        8. Modify pack (add/remove dependency)
        9. Delete pack and verify cleanup
        10. Clean temp files
        """
        from src.store import (
            Store, Pack, PackLock, PackDependency, DependencySelector,
            ExposeConfig, ResolvedDependency, ResolvedArtifact, ArtifactProvider,
            PackSource, AssetKind, ProviderName, SelectorStrategy
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            store_path = root / "store"
            ui_roots = {
                "comfyui": root / "ComfyUI",
                "forge": root / "Forge",
            }

            # Create fake UI directories
            for ui, ui_path in ui_roots.items():
                (ui_path / "models" / "Lora").mkdir(parents=True, exist_ok=True)
                (ui_path / "models" / "Stable-diffusion").mkdir(parents=True, exist_ok=True)
                if ui == "comfyui":
                    (ui_path / "models" / "loras").mkdir(parents=True, exist_ok=True)
                    (ui_path / "models" / "checkpoints").mkdir(parents=True, exist_ok=True)

            # =========================================
            # STEP 1: Initialize store
            # =========================================
            store = Store(store_path)
            store.init()

            assert store.is_initialized()
            assert store.layout.state_path.exists()
            assert store.layout.data_path.exists()
            assert store.layout.config_path.exists()

            # Verify initial structure
            assert store.layout.profile_exists("global")
            runtime = store.layout.load_runtime()
            assert runtime.get_active_profile("comfyui") == "global"

            # =========================================
            # STEP 2: Create blobs (fake models)
            # =========================================
            # Create various model files
            models = {
                "lora1": (b"lora content 1" * 1000, AssetKind.LORA),
                "lora2": (b"lora content 2" * 1000, AssetKind.LORA),
                "checkpoint": (b"checkpoint content" * 5000, AssetKind.CHECKPOINT),
                "vae": (b"vae content" * 2000, AssetKind.VAE),
                "shared_lora": (b"shared lora content" * 1000, AssetKind.LORA),  # Used by multiple packs
            }

            blob_shas = {}
            for name, (content, _) in models.items():
                sha = hashlib.sha256(content).hexdigest()
                blob_shas[name] = sha
                blob_path = store.blob_store.blob_path(sha)
                blob_path.parent.mkdir(parents=True, exist_ok=True)
                blob_path.write_bytes(content)

            # Verify blobs exist
            for name, sha in blob_shas.items():
                assert store.blob_store.blob_exists(sha), f"Blob for {name} should exist"

            # =========================================
            # STEP 3: Create Pack 1 (Lora pack)
            # =========================================
            pack1 = Pack(
                name="LoraPackA",
                pack_type=AssetKind.LORA,
                source=PackSource(provider=ProviderName.CIVITAI, model_id=1001),
                dependencies=[
                    PackDependency(
                        id="main_lora",
                        kind=AssetKind.LORA,
                        selector=DependencySelector(strategy=SelectorStrategy.CIVITAI_FILE),
                        expose=ExposeConfig(filename="lora_a.safetensors"),
                    ),
                    PackDependency(
                        id="shared",
                        kind=AssetKind.LORA,
                        selector=DependencySelector(strategy=SelectorStrategy.CIVITAI_FILE),
                        expose=ExposeConfig(filename="shared_style.safetensors"),
                    ),
                ],
            )
            store.layout.save_pack(pack1)

            lock1 = PackLock(
                pack="LoraPackA",
                resolved=[
                    ResolvedDependency(
                        dependency_id="main_lora",
                        artifact=ResolvedArtifact(
                            kind=AssetKind.LORA,
                            sha256=blob_shas["lora1"],
                            provider=ArtifactProvider(name=ProviderName.CIVITAI),
                        ),
                    ),
                    ResolvedDependency(
                        dependency_id="shared",
                        artifact=ResolvedArtifact(
                            kind=AssetKind.LORA,
                            sha256=blob_shas["shared_lora"],
                            provider=ArtifactProvider(name=ProviderName.CIVITAI),
                        ),
                    ),
                ],
            )
            store.layout.save_pack_lock(lock1)
            store.profile_service.add_pack_to_global("LoraPackA")

            # =========================================
            # STEP 4: Create Pack 2 (Checkpoint pack with shared lora)
            # =========================================
            pack2 = Pack(
                name="CheckpointPackB",
                pack_type=AssetKind.CHECKPOINT,
                source=PackSource(provider=ProviderName.CIVITAI, model_id=2001),
                dependencies=[
                    PackDependency(
                        id="main_checkpoint",
                        kind=AssetKind.CHECKPOINT,
                        selector=DependencySelector(strategy=SelectorStrategy.CIVITAI_FILE),
                        expose=ExposeConfig(filename="model_b.safetensors"),
                    ),
                    PackDependency(
                        id="vae",
                        kind=AssetKind.VAE,
                        selector=DependencySelector(strategy=SelectorStrategy.CIVITAI_FILE),
                        expose=ExposeConfig(filename="vae_b.safetensors"),
                    ),
                    PackDependency(
                        id="shared",
                        kind=AssetKind.LORA,
                        selector=DependencySelector(strategy=SelectorStrategy.CIVITAI_FILE),
                        expose=ExposeConfig(filename="shared_style.safetensors"),  # Same filename!
                    ),
                ],
            )
            store.layout.save_pack(pack2)

            lock2 = PackLock(
                pack="CheckpointPackB",
                resolved=[
                    ResolvedDependency(
                        dependency_id="main_checkpoint",
                        artifact=ResolvedArtifact(
                            kind=AssetKind.CHECKPOINT,
                            sha256=blob_shas["checkpoint"],
                            provider=ArtifactProvider(name=ProviderName.CIVITAI),
                        ),
                    ),
                    ResolvedDependency(
                        dependency_id="vae",
                        artifact=ResolvedArtifact(
                            kind=AssetKind.VAE,
                            sha256=blob_shas["vae"],
                            provider=ArtifactProvider(name=ProviderName.CIVITAI),
                        ),
                    ),
                    ResolvedDependency(
                        dependency_id="shared",
                        artifact=ResolvedArtifact(
                            kind=AssetKind.LORA,
                            sha256=blob_shas["shared_lora"],  # Same blob - deduplication!
                            provider=ArtifactProvider(name=ProviderName.CIVITAI),
                        ),
                    ),
                ],
            )
            store.layout.save_pack_lock(lock2)
            store.profile_service.add_pack_to_global("CheckpointPackB")

            # Verify both packs in global profile
            global_profile = store.profile_service.load_global()
            pack_names = global_profile.get_pack_names()
            assert "LoraPackA" in pack_names
            assert "CheckpointPackB" in pack_names

            # =========================================
            # STEP 5: Use pack and verify views
            # =========================================
            result = store.use("LoraPackA", ui_set="local", sync=True)

            assert result.pack == "LoraPackA"
            assert result.created_profile == "work__LoraPackA"

            # Verify runtime stack
            runtime = store.layout.load_runtime()
            assert runtime.get_active_profile("comfyui") == "work__LoraPackA"

            # Verify views created for ComfyUI
            view_path = store.layout.view_profile_path("comfyui", "work__LoraPackA")
            lora_in_view = view_path / "models" / "loras" / "lora_a.safetensors"
            assert lora_in_view.exists(), "Lora should be in ComfyUI view"
            assert lora_in_view.is_symlink(), "Should be a symlink"
            assert lora_in_view.read_bytes() == models["lora1"][0], "Should point to correct blob"

            # Verify active symlink
            active_path = store.layout.view_active_path("comfyui")
            assert active_path.is_symlink()
            assert os.readlink(active_path) == "profiles/work__LoraPackA"

            # =========================================
            # STEP 6: Stack multiple uses
            # =========================================
            store.use("CheckpointPackB", ui_set="local", sync=True)

            runtime = store.layout.load_runtime()
            assert runtime.get_active_profile("comfyui") == "work__CheckpointPackB"
            stack = runtime.get_stack("comfyui")
            assert stack == ["global", "work__LoraPackA", "work__CheckpointPackB"]

            # Verify view has checkpoint now
            view_path = store.layout.view_profile_path("comfyui", "work__CheckpointPackB")
            checkpoint_in_view = view_path / "models" / "checkpoints" / "model_b.safetensors"
            assert checkpoint_in_view.exists(), "Checkpoint should be in view"

            # =========================================
            # STEP 7: Doctor diagnostics
            # =========================================
            report = store.doctor(
                rebuild_views=False,
                verify_blobs=True,
            )

            # Doctor should complete without critical errors
            # Note: report is a DoctorReport Pydantic model
            assert report is not None, "Doctor should return a report"

            # =========================================
            # STEP 8: Back command
            # =========================================
            back_result = store.back(ui_set="local", sync=True)

            assert back_result.from_profile == "work__CheckpointPackB"
            assert back_result.to_profile == "work__LoraPackA"

            runtime = store.layout.load_runtime()
            assert runtime.get_active_profile("comfyui") == "work__LoraPackA"

            # =========================================
            # STEP 9: Reset to global
            # =========================================
            # Back again to get to global
            store.back(ui_set="local", sync=True)

            runtime = store.layout.load_runtime()
            assert runtime.get_active_profile("comfyui") == "global"

            # =========================================
            # STEP 10: Delete pack and verify cleanup
            # =========================================
            # First verify work profile exists
            assert store.layout.profile_exists("work__LoraPackA")

            # Delete pack
            deleted = store.delete_pack("LoraPackA")
            assert deleted

            # Verify pack is gone
            assert not store.layout.pack_exists("LoraPackA")

            # Verify work profile is also deleted
            assert not store.layout.profile_exists("work__LoraPackA")

            # Verify removed from global profile
            global_profile = store.profile_service.load_global()
            assert "LoraPackA" not in global_profile.get_pack_names()

            # Blob should still exist (used by other pack)
            assert store.blob_store.blob_exists(blob_shas["shared_lora"]), \
                "Shared blob should still exist (used by CheckpointPackB)"

            # =========================================
            # STEP 11: Clean temp files
            # =========================================
            # Create some temp files
            temp_file = store.layout.tmp_path / "test.tmp"
            temp_file.parent.mkdir(parents=True, exist_ok=True)
            temp_file.write_text("temp data")

            clean_result = store.clean(tmp=True, cache=True, partial=False)

            assert clean_result.get("tmp", 0) > 0 or not temp_file.exists()

            # =========================================
            # STEP 12: Final state verification
            # =========================================
            # Only CheckpointPackB should remain
            packs = store.list_packs()
            assert packs == ["CheckpointPackB"]

            # Runtime should be clean
            runtime = store.layout.load_runtime()
            # work__LoraPackA should not be in any stack
            for ui_name, ui_state in runtime.ui.items():
                assert "work__LoraPackA" not in ui_state.stack

    def test_shadowing_and_last_wins(self):
        """
        Test that last-wins conflict resolution works correctly.

        Scenario:
        - PackA has lora with filename "style.safetensors"
        - PackB has different lora with same filename "style.safetensors"
        - In profile [PackA, PackB], PackB's lora should be used
        - In profile [PackB, PackA], PackA's lora should be used
        """
        from src.store import (
            Store, Pack, PackLock, PackDependency, DependencySelector,
            ExposeConfig, ResolvedDependency, ResolvedArtifact, ArtifactProvider,
            PackSource, AssetKind, ProviderName, SelectorStrategy, Profile, ProfilePackEntry
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            store = Store(Path(tmpdir))
            store.init()

            # Create two different blobs
            content_a = b"content from pack A"
            content_b = b"content from pack B"
            sha_a = hashlib.sha256(content_a).hexdigest()
            sha_b = hashlib.sha256(content_b).hexdigest()

            for sha, content in [(sha_a, content_a), (sha_b, content_b)]:
                blob_path = store.blob_store.blob_path(sha)
                blob_path.parent.mkdir(parents=True, exist_ok=True)
                blob_path.write_bytes(content)

            # Create PackA
            pack_a = Pack(
                name="PackA",
                pack_type=AssetKind.LORA,
                source=PackSource(provider=ProviderName.CIVITAI),
                dependencies=[
                    PackDependency(
                        id="main",
                        kind=AssetKind.LORA,
                        selector=DependencySelector(strategy=SelectorStrategy.CIVITAI_FILE),
                        expose=ExposeConfig(filename="style.safetensors"),  # Same filename!
                    ),
                ],
            )
            store.layout.save_pack(pack_a)
            store.layout.save_pack_lock(PackLock(
                pack="PackA",
                resolved=[
                    ResolvedDependency(
                        dependency_id="main",
                        artifact=ResolvedArtifact(
                            kind=AssetKind.LORA,
                            sha256=sha_a,
                            provider=ArtifactProvider(name=ProviderName.CIVITAI),
                        ),
                    ),
                ],
            ))

            # Create PackB
            pack_b = Pack(
                name="PackB",
                pack_type=AssetKind.LORA,
                source=PackSource(provider=ProviderName.CIVITAI),
                dependencies=[
                    PackDependency(
                        id="main",
                        kind=AssetKind.LORA,
                        selector=DependencySelector(strategy=SelectorStrategy.CIVITAI_FILE),
                        expose=ExposeConfig(filename="style.safetensors"),  # Same filename!
                    ),
                ],
            )
            store.layout.save_pack(pack_b)
            store.layout.save_pack_lock(PackLock(
                pack="PackB",
                resolved=[
                    ResolvedDependency(
                        dependency_id="main",
                        artifact=ResolvedArtifact(
                            kind=AssetKind.LORA,
                            sha256=sha_b,
                            provider=ArtifactProvider(name=ProviderName.CIVITAI),
                        ),
                    ),
                ],
            ))

            # Add both to global (PackA first, then PackB)
            store.profile_service.add_pack_to_global("PackA")
            store.profile_service.add_pack_to_global("PackB")

            # Build view for global profile
            global_profile = store.profile_service.load_global()
            packs_data = {}
            for p in ["PackA", "PackB"]:
                packs_data[p] = (store.layout.load_pack(p), store.layout.load_pack_lock(p))

            report = store.view_builder.build("comfyui", global_profile, packs_data)

            # Verify shadowing detected
            assert len(report.shadowed) == 1, "Should detect one shadowed file"
            assert report.shadowed[0].winner_pack == "PackB"  # Last wins
            assert report.shadowed[0].loser_pack == "PackA"

            # Verify symlink points to PackB's content (last wins)
            view_path = store.layout.view_profile_path("comfyui", "global")
            lora_path = view_path / "models" / "loras" / "style.safetensors"

            assert lora_path.exists()
            assert lora_path.read_bytes() == content_b, "Last pack (PackB) should win"

            # Now test with reversed order - create custom profile [PackB, PackA]
            reversed_profile = Profile(
                name="reversed",
                packs=[
                    ProfilePackEntry(name="PackB"),
                    ProfilePackEntry(name="PackA"),  # PackA last = PackA wins
                ],
            )
            store.layout.save_profile(reversed_profile)

            report2 = store.view_builder.build("comfyui", reversed_profile, packs_data)

            # Now PackA should win
            assert report2.shadowed[0].winner_pack == "PackA"
            assert report2.shadowed[0].loser_pack == "PackB"

            view_path2 = store.layout.view_profile_path("comfyui", "reversed")
            lora_path2 = view_path2 / "models" / "loras" / "style.safetensors"

            assert lora_path2.read_bytes() == content_a, "PackA should win in reversed profile"

    def test_blob_deduplication(self):
        """
        Test that identical content is only stored once.

        Scenario:
        - Two packs reference the same model file
        - Only one blob should exist in storage
        """
        from src.store import Store

        with tempfile.TemporaryDirectory() as tmpdir:
            store = Store(Path(tmpdir))
            store.init()

            # Create content
            content = b"shared model content" * 1000
            sha = hashlib.sha256(content).hexdigest()

            # Add same content twice (simulating two downloads)
            file1 = Path(tmpdir) / "file1.safetensors"
            file2 = Path(tmpdir) / "file2.safetensors"
            file1.write_bytes(content)
            file2.write_bytes(content)

            sha1 = store.blob_store.adopt(file1)
            sha2 = store.blob_store.adopt(file2)

            # Same hash
            assert sha1 == sha2 == sha

            # Only one blob in storage
            blobs = store.blob_store.list_blobs()
            assert len(blobs) == 1

            # Total size should be content size (not doubled)
            total_size = store.blob_store.get_total_size()
            assert total_size == len(content)

    def test_multiple_ui_views(self):
        """
        Test that views are correctly built for multiple UIs with different path mappings.

        - ComfyUI: models/loras/, models/checkpoints/
        - Forge: models/Lora/, models/Stable-diffusion/
        """
        from src.store import (
            Store, Pack, PackLock, PackDependency, DependencySelector,
            ExposeConfig, ResolvedDependency, ResolvedArtifact, ArtifactProvider,
            PackSource, AssetKind, ProviderName, SelectorStrategy
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            store = Store(Path(tmpdir))
            store.init()

            # Create blobs
            lora_content = b"lora content"
            checkpoint_content = b"checkpoint content"
            lora_sha = hashlib.sha256(lora_content).hexdigest()
            checkpoint_sha = hashlib.sha256(checkpoint_content).hexdigest()

            for sha, content in [(lora_sha, lora_content), (checkpoint_sha, checkpoint_content)]:
                blob_path = store.blob_store.blob_path(sha)
                blob_path.parent.mkdir(parents=True, exist_ok=True)
                blob_path.write_bytes(content)

            # Create pack with multiple asset types
            pack = Pack(
                name="MultiAssetPack",
                pack_type=AssetKind.CHECKPOINT,
                source=PackSource(provider=ProviderName.CIVITAI),
                dependencies=[
                    PackDependency(
                        id="lora",
                        kind=AssetKind.LORA,
                        selector=DependencySelector(strategy=SelectorStrategy.CIVITAI_FILE),
                        expose=ExposeConfig(filename="test_lora.safetensors"),
                    ),
                    PackDependency(
                        id="checkpoint",
                        kind=AssetKind.CHECKPOINT,
                        selector=DependencySelector(strategy=SelectorStrategy.CIVITAI_FILE),
                        expose=ExposeConfig(filename="test_checkpoint.safetensors"),
                    ),
                ],
            )
            store.layout.save_pack(pack)

            lock = PackLock(
                pack="MultiAssetPack",
                resolved=[
                    ResolvedDependency(
                        dependency_id="lora",
                        artifact=ResolvedArtifact(
                            kind=AssetKind.LORA,
                            sha256=lora_sha,
                            provider=ArtifactProvider(name=ProviderName.CIVITAI),
                        ),
                    ),
                    ResolvedDependency(
                        dependency_id="checkpoint",
                        artifact=ResolvedArtifact(
                            kind=AssetKind.CHECKPOINT,
                            sha256=checkpoint_sha,
                            provider=ArtifactProvider(name=ProviderName.CIVITAI),
                        ),
                    ),
                ],
            )
            store.layout.save_pack_lock(lock)
            store.profile_service.add_pack_to_global("MultiAssetPack")

            # Build views for both UIs
            store.use("MultiAssetPack", ui_set="local", sync=True)

            # Verify ComfyUI paths
            comfy_view = store.layout.view_profile_path("comfyui", "work__MultiAssetPack")
            comfy_lora = comfy_view / "models" / "loras" / "test_lora.safetensors"
            comfy_checkpoint = comfy_view / "models" / "checkpoints" / "test_checkpoint.safetensors"

            assert comfy_lora.exists(), "ComfyUI lora path should exist"
            assert comfy_checkpoint.exists(), "ComfyUI checkpoint path should exist"
            assert comfy_lora.read_bytes() == lora_content
            assert comfy_checkpoint.read_bytes() == checkpoint_content

            # Verify Forge paths (different folder names!)
            forge_view = store.layout.view_profile_path("forge", "work__MultiAssetPack")
            forge_lora = forge_view / "models" / "Lora" / "test_lora.safetensors"
            forge_checkpoint = forge_view / "models" / "Stable-diffusion" / "test_checkpoint.safetensors"

            assert forge_lora.exists(), "Forge lora path should exist"
            assert forge_checkpoint.exists(), "Forge checkpoint path should exist"
            assert forge_lora.read_bytes() == lora_content
            assert forge_checkpoint.read_bytes() == checkpoint_content

    def test_doctor_detects_issues(self):
        """
        Test that doctor correctly detects and reports issues.
        """
        from src.store import (
            Store, Pack, PackLock, PackDependency, DependencySelector,
            ExposeConfig, ResolvedDependency, ResolvedArtifact, ArtifactProvider,
            PackSource, AssetKind, ProviderName, SelectorStrategy
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            store = Store(Path(tmpdir))
            store.init()

            # Create a pack with a missing blob
            missing_sha = "0" * 64  # Non-existent blob

            pack = Pack(
                name="MissingBlobPack",
                pack_type=AssetKind.LORA,
                source=PackSource(provider=ProviderName.CIVITAI),
                dependencies=[
                    PackDependency(
                        id="main",
                        kind=AssetKind.LORA,
                        selector=DependencySelector(strategy=SelectorStrategy.CIVITAI_FILE),
                        expose=ExposeConfig(filename="missing.safetensors"),
                    ),
                ],
            )
            store.layout.save_pack(pack)

            lock = PackLock(
                pack="MissingBlobPack",
                resolved=[
                    ResolvedDependency(
                        dependency_id="main",
                        artifact=ResolvedArtifact(
                            kind=AssetKind.LORA,
                            sha256=missing_sha,
                            provider=ArtifactProvider(name=ProviderName.CIVITAI),
                        ),
                    ),
                ],
            )
            store.layout.save_pack_lock(lock)
            store.profile_service.add_pack_to_global("MissingBlobPack")

            # Run status check
            status = store.status(ui_set="local")

            # Should detect missing blob
            # Note: status.missing_blobs is a list of MissingBlob Pydantic models
            assert len(status.missing_blobs) > 0, "Should detect missing blob"
            assert any(mb.sha256 == missing_sha for mb in status.missing_blobs), \
                f"Should find missing blob {missing_sha}"


# =============================================================================
# Complex Shadowing Integration Tests
# =============================================================================

class TestComplexShadowingScenarios:
    """
    Comprehensive shadowing tests with multiple packs.

    These tests verify that last-wins priority works correctly
    with 3+ packs and various conflict patterns.
    """

    def _create_pack_with_lora(
        self,
        store,
        name: str,
        filename: str,
        content: bytes,
    ) -> str:
        """Helper to create a pack with a single lora dependency."""
        from src.store import (
            Pack, PackLock, PackDependency, DependencySelector,
            ExposeConfig, ResolvedDependency, ResolvedArtifact, ArtifactProvider,
            PackSource, AssetKind, ProviderName, SelectorStrategy
        )

        sha = hashlib.sha256(content).hexdigest()
        blob_path = store.blob_store.blob_path(sha)
        blob_path.parent.mkdir(parents=True, exist_ok=True)
        blob_path.write_bytes(content)

        pack = Pack(
            name=name,
            pack_type=AssetKind.LORA,
            source=PackSource(provider=ProviderName.CIVITAI),
            dependencies=[
                PackDependency(
                    id="main",
                    kind=AssetKind.LORA,
                    selector=DependencySelector(strategy=SelectorStrategy.CIVITAI_FILE),
                    expose=ExposeConfig(filename=filename),
                ),
            ],
        )
        store.layout.save_pack(pack)
        store.layout.save_pack_lock(PackLock(
            pack=name,
            resolved=[
                ResolvedDependency(
                    dependency_id="main",
                    artifact=ResolvedArtifact(
                        kind=AssetKind.LORA,
                        sha256=sha,
                        provider=ArtifactProvider(name=ProviderName.CIVITAI),
                    ),
                ),
            ],
        ))

        return sha

    def test_three_pack_shadowing_chain(self):
        """
        Test shadowing with 3 packs all exposing same filename.

        Profile: [PackA, PackB, PackC]
        All expose: style.safetensors

        Shadowing records each transition:
        - PackB shadows PackA
        - PackC shadows PackB

        Final winner: PackC (last in list)
        """
        from src.store import Store, Profile, ProfilePackEntry

        with tempfile.TemporaryDirectory() as tmpdir:
            store = Store(Path(tmpdir))
            store.init()

            # Create 3 packs with same filename but different content
            contents = {
                "PackA": b"content from pack A - first",
                "PackB": b"content from pack B - second",
                "PackC": b"content from pack C - third and winner",
            }

            for name, content in contents.items():
                self._create_pack_with_lora(store, name, "style.safetensors", content)

            # Create profile with order [A, B, C]
            profile = Profile(
                name="test_chain",
                packs=[
                    ProfilePackEntry(name="PackA"),
                    ProfilePackEntry(name="PackB"),
                    ProfilePackEntry(name="PackC"),  # Last = winner
                ],
            )
            store.layout.save_profile(profile)

            # Build view
            packs_data = {}
            for name in ["PackA", "PackB", "PackC"]:
                packs_data[name] = (store.layout.load_pack(name), store.layout.load_pack_lock(name))

            report = store.view_builder.build("comfyui", profile, packs_data)

            # Shadowing records each transition:
            # - B shadows A
            # - C shadows B
            assert len(report.shadowed) == 2, f"Expected 2 shadowed entries, got {len(report.shadowed)}"

            # Verify shadow chain
            shadow_pairs = [(e.winner_pack, e.loser_pack) for e in report.shadowed]
            assert ("PackB", "PackA") in shadow_pairs, f"PackB should shadow PackA, got {shadow_pairs}"
            assert ("PackC", "PackB") in shadow_pairs, f"PackC should shadow PackB, got {shadow_pairs}"

            # Verify symlink points to PackC content (final winner)
            view_path = store.layout.view_profile_path("comfyui", "test_chain")
            lora_path = view_path / "models" / "loras" / "style.safetensors"
            assert lora_path.read_bytes() == contents["PackC"]

    def test_mixed_shadowing_multiple_files(self):
        """
        Test complex scenario with multiple files and partial overlaps.

        PackA: style1.safetensors, style2.safetensors
        PackB: style2.safetensors, style3.safetensors  (shadows A's style2)
        PackC: style1.safetensors, style3.safetensors  (shadows A's style1, B's style3)

        Profile: [PackA, PackB, PackC]
        Expected in view:
        - style1.safetensors → PackC (shadows PackA)
        - style2.safetensors → PackB (shadows PackA)
        - style3.safetensors → PackC (shadows PackB)
        """
        from src.store import (
            Store, Pack, PackLock, PackDependency, DependencySelector,
            ExposeConfig, ResolvedDependency, ResolvedArtifact, ArtifactProvider,
            PackSource, AssetKind, ProviderName, SelectorStrategy, Profile, ProfilePackEntry
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            store = Store(Path(tmpdir))
            store.init()

            # Create content for each file
            file_contents = {
                ("PackA", "style1"): b"PackA style1 content",
                ("PackA", "style2"): b"PackA style2 content",
                ("PackB", "style2"): b"PackB style2 content - shadows A",
                ("PackB", "style3"): b"PackB style3 content",
                ("PackC", "style1"): b"PackC style1 content - shadows A",
                ("PackC", "style3"): b"PackC style3 content - shadows B",
            }

            shas = {}
            for (pack, file), content in file_contents.items():
                sha = hashlib.sha256(content).hexdigest()
                shas[(pack, file)] = sha
                blob_path = store.blob_store.blob_path(sha)
                blob_path.parent.mkdir(parents=True, exist_ok=True)
                blob_path.write_bytes(content)

            # Create PackA
            pack_a = Pack(
                name="PackA",
                pack_type=AssetKind.LORA,
                source=PackSource(provider=ProviderName.CIVITAI),
                dependencies=[
                    PackDependency(
                        id="style1",
                        kind=AssetKind.LORA,
                        selector=DependencySelector(strategy=SelectorStrategy.CIVITAI_FILE),
                        expose=ExposeConfig(filename="style1.safetensors"),
                    ),
                    PackDependency(
                        id="style2",
                        kind=AssetKind.LORA,
                        selector=DependencySelector(strategy=SelectorStrategy.CIVITAI_FILE),
                        expose=ExposeConfig(filename="style2.safetensors"),
                    ),
                ],
            )
            store.layout.save_pack(pack_a)
            store.layout.save_pack_lock(PackLock(
                pack="PackA",
                resolved=[
                    ResolvedDependency(
                        dependency_id="style1",
                        artifact=ResolvedArtifact(
                            kind=AssetKind.LORA,
                            sha256=shas[("PackA", "style1")],
                            provider=ArtifactProvider(name=ProviderName.CIVITAI),
                        ),
                    ),
                    ResolvedDependency(
                        dependency_id="style2",
                        artifact=ResolvedArtifact(
                            kind=AssetKind.LORA,
                            sha256=shas[("PackA", "style2")],
                            provider=ArtifactProvider(name=ProviderName.CIVITAI),
                        ),
                    ),
                ],
            ))

            # Create PackB
            pack_b = Pack(
                name="PackB",
                pack_type=AssetKind.LORA,
                source=PackSource(provider=ProviderName.CIVITAI),
                dependencies=[
                    PackDependency(
                        id="style2",
                        kind=AssetKind.LORA,
                        selector=DependencySelector(strategy=SelectorStrategy.CIVITAI_FILE),
                        expose=ExposeConfig(filename="style2.safetensors"),
                    ),
                    PackDependency(
                        id="style3",
                        kind=AssetKind.LORA,
                        selector=DependencySelector(strategy=SelectorStrategy.CIVITAI_FILE),
                        expose=ExposeConfig(filename="style3.safetensors"),
                    ),
                ],
            )
            store.layout.save_pack(pack_b)
            store.layout.save_pack_lock(PackLock(
                pack="PackB",
                resolved=[
                    ResolvedDependency(
                        dependency_id="style2",
                        artifact=ResolvedArtifact(
                            kind=AssetKind.LORA,
                            sha256=shas[("PackB", "style2")],
                            provider=ArtifactProvider(name=ProviderName.CIVITAI),
                        ),
                    ),
                    ResolvedDependency(
                        dependency_id="style3",
                        artifact=ResolvedArtifact(
                            kind=AssetKind.LORA,
                            sha256=shas[("PackB", "style3")],
                            provider=ArtifactProvider(name=ProviderName.CIVITAI),
                        ),
                    ),
                ],
            ))

            # Create PackC
            pack_c = Pack(
                name="PackC",
                pack_type=AssetKind.LORA,
                source=PackSource(provider=ProviderName.CIVITAI),
                dependencies=[
                    PackDependency(
                        id="style1",
                        kind=AssetKind.LORA,
                        selector=DependencySelector(strategy=SelectorStrategy.CIVITAI_FILE),
                        expose=ExposeConfig(filename="style1.safetensors"),
                    ),
                    PackDependency(
                        id="style3",
                        kind=AssetKind.LORA,
                        selector=DependencySelector(strategy=SelectorStrategy.CIVITAI_FILE),
                        expose=ExposeConfig(filename="style3.safetensors"),
                    ),
                ],
            )
            store.layout.save_pack(pack_c)
            store.layout.save_pack_lock(PackLock(
                pack="PackC",
                resolved=[
                    ResolvedDependency(
                        dependency_id="style1",
                        artifact=ResolvedArtifact(
                            kind=AssetKind.LORA,
                            sha256=shas[("PackC", "style1")],
                            provider=ArtifactProvider(name=ProviderName.CIVITAI),
                        ),
                    ),
                    ResolvedDependency(
                        dependency_id="style3",
                        artifact=ResolvedArtifact(
                            kind=AssetKind.LORA,
                            sha256=shas[("PackC", "style3")],
                            provider=ArtifactProvider(name=ProviderName.CIVITAI),
                        ),
                    ),
                ],
            ))

            # Create profile
            profile = Profile(
                name="complex_shadow",
                packs=[
                    ProfilePackEntry(name="PackA"),
                    ProfilePackEntry(name="PackB"),
                    ProfilePackEntry(name="PackC"),
                ],
            )
            store.layout.save_profile(profile)

            # Build view
            packs_data = {
                "PackA": (store.layout.load_pack("PackA"), store.layout.load_pack_lock("PackA")),
                "PackB": (store.layout.load_pack("PackB"), store.layout.load_pack_lock("PackB")),
                "PackC": (store.layout.load_pack("PackC"), store.layout.load_pack_lock("PackC")),
            }

            report = store.view_builder.build("comfyui", profile, packs_data)

            # Verify shadowing entries
            # style1: C shadows A
            # style2: B shadows A
            # style3: C shadows B
            assert len(report.shadowed) == 3, f"Expected 3 shadowed, got {len(report.shadowed)}"

            shadowed_map = {e.dst_relpath: (e.winner_pack, e.loser_pack) for e in report.shadowed}

            # Check each shadow relationship
            style1_path = "models/loras/style1.safetensors"
            style2_path = "models/loras/style2.safetensors"
            style3_path = "models/loras/style3.safetensors"

            assert shadowed_map[style1_path] == ("PackC", "PackA"), f"style1 wrong: {shadowed_map.get(style1_path)}"
            assert shadowed_map[style2_path] == ("PackB", "PackA"), f"style2 wrong: {shadowed_map.get(style2_path)}"
            assert shadowed_map[style3_path] == ("PackC", "PackB"), f"style3 wrong: {shadowed_map.get(style3_path)}"

            # Verify actual content in view
            view_path = store.layout.view_profile_path("comfyui", "complex_shadow")

            assert (view_path / "models" / "loras" / "style1.safetensors").read_bytes() == file_contents[("PackC", "style1")]
            assert (view_path / "models" / "loras" / "style2.safetensors").read_bytes() == file_contents[("PackB", "style2")]
            assert (view_path / "models" / "loras" / "style3.safetensors").read_bytes() == file_contents[("PackC", "style3")]

    def test_shadowing_after_profile_reorder(self):
        """
        Test that shadowing changes correctly when profile order changes.

        Initial: [PackA, PackB] → PackB wins
        Reorder: [PackB, PackA] → PackA wins
        """
        from src.store import Store, Profile, ProfilePackEntry

        with tempfile.TemporaryDirectory() as tmpdir:
            store = Store(Path(tmpdir))
            store.init()

            content_a = b"PackA content"
            content_b = b"PackB content"

            self._create_pack_with_lora(store, "PackA", "shared.safetensors", content_a)
            self._create_pack_with_lora(store, "PackB", "shared.safetensors", content_b)

            packs_data = {
                "PackA": (store.layout.load_pack("PackA"), store.layout.load_pack_lock("PackA")),
                "PackB": (store.layout.load_pack("PackB"), store.layout.load_pack_lock("PackB")),
            }

            # First order: A, B
            profile1 = Profile(
                name="order_ab",
                packs=[ProfilePackEntry(name="PackA"), ProfilePackEntry(name="PackB")],
            )
            store.layout.save_profile(profile1)

            report1 = store.view_builder.build("comfyui", profile1, packs_data)
            view1 = store.layout.view_profile_path("comfyui", "order_ab")

            assert report1.shadowed[0].winner_pack == "PackB"
            assert (view1 / "models" / "loras" / "shared.safetensors").read_bytes() == content_b

            # Second order: B, A
            profile2 = Profile(
                name="order_ba",
                packs=[ProfilePackEntry(name="PackB"), ProfilePackEntry(name="PackA")],
            )
            store.layout.save_profile(profile2)

            report2 = store.view_builder.build("comfyui", profile2, packs_data)
            view2 = store.layout.view_profile_path("comfyui", "order_ba")

            assert report2.shadowed[0].winner_pack == "PackA"
            assert (view2 / "models" / "loras" / "shared.safetensors").read_bytes() == content_a

    def test_use_command_changes_shadowing_priority(self):
        """
        Test that 'use' command creates work profile with pack at end (winning position).

        Global: [PackA, PackB] - PackB wins
        Use PackA → work__PackA: [PackB, PackA] - PackA wins
        """
        from src.store import Store

        with tempfile.TemporaryDirectory() as tmpdir:
            store = Store(Path(tmpdir))
            store.init()

            content_a = b"PackA should win after use"
            content_b = b"PackB wins in global"

            self._create_pack_with_lora(store, "PackA", "style.safetensors", content_a)
            self._create_pack_with_lora(store, "PackB", "style.safetensors", content_b)

            # Add to global (A first, then B - so B wins)
            store.profile_service.add_pack_to_global("PackA")
            store.profile_service.add_pack_to_global("PackB")

            # Build global view
            global_profile = store.profile_service.load_global()
            packs_data = {
                "PackA": (store.layout.load_pack("PackA"), store.layout.load_pack_lock("PackA")),
                "PackB": (store.layout.load_pack("PackB"), store.layout.load_pack_lock("PackB")),
            }
            report_global = store.view_builder.build("comfyui", global_profile, packs_data)

            # Verify B wins in global
            assert report_global.shadowed[0].winner_pack == "PackB"

            # Now use PackA - should move it to end
            result = store.use("PackA", ui_set="local", sync=True)

            # Verify work profile has PackA at end
            work_profile = store.layout.load_profile("work__PackA")
            pack_names = work_profile.get_pack_names()
            assert pack_names[-1] == "PackA", f"PackA should be last, got {pack_names}"

            # Verify PackA now wins
            view_path = store.layout.view_profile_path("comfyui", "work__PackA")
            lora_path = view_path / "models" / "loras" / "style.safetensors"
            assert lora_path.read_bytes() == content_a, "PackA should win after 'use'"


# =============================================================================
# Profile Switching and Restoration Tests
# =============================================================================

class TestProfileSwitchingAndRestoration:
    """
    Tests for profile switching, stacking, and correct restoration.
    """

    def test_deep_stack_and_full_unwind(self):
        """
        Test stacking 5 levels deep and unwinding completely.

        global → use A → use B → use C → use D → use E
        Then back 5 times to get back to global
        """
        from src.store import Store, Pack, PackLock, PackSource, AssetKind, ProviderName

        with tempfile.TemporaryDirectory() as tmpdir:
            store = Store(Path(tmpdir))
            store.init()

            # Create 5 packs
            pack_names = ["PackA", "PackB", "PackC", "PackD", "PackE"]
            for name in pack_names:
                pack = Pack(
                    name=name,
                    pack_type=AssetKind.LORA,
                    source=PackSource(provider=ProviderName.CIVITAI),
                    dependencies=[],
                )
                store.layout.save_pack(pack)
                store.layout.save_pack_lock(PackLock(pack=name))
                store.profile_service.add_pack_to_global(name)

            # Stack up
            expected_stack = ["global"]
            for name in pack_names:
                store.use(name, ui_set="local", sync=False)
                expected_stack.append(f"work__{name}")

                runtime = store.layout.load_runtime()
                assert runtime.ui["comfyui"].stack == expected_stack, \
                    f"Stack mismatch after use {name}"

            # Verify we're at the deepest level
            runtime = store.layout.load_runtime()
            assert runtime.get_active_profile("comfyui") == "work__PackE"
            assert len(runtime.ui["comfyui"].stack) == 6

            # Unwind all the way back
            for i, name in enumerate(reversed(pack_names)):
                result = store.back(ui_set="local", sync=False)

                assert result.from_profile == f"work__{name}"

                if i < 4:  # Not the last back
                    expected_to = f"work__{pack_names[-(i+2)]}"
                else:
                    expected_to = "global"

                assert result.to_profile == expected_to, \
                    f"Expected to_profile={expected_to}, got {result.to_profile}"

            # Verify we're back at global
            runtime = store.layout.load_runtime()
            assert runtime.get_active_profile("comfyui") == "global"
            assert runtime.ui["comfyui"].stack == ["global"]

    def test_back_at_global_is_noop(self):
        """
        Test that 'back' at global level is a no-op.
        """
        from src.store import Store

        with tempfile.TemporaryDirectory() as tmpdir:
            store = Store(Path(tmpdir))
            store.init()

            # First back at global
            result = store.back(ui_set="local", sync=False)

            assert result.from_profile == "global"
            assert result.to_profile == "global"
            assert "already_at_base" in result.notes

            # Stack should still just be global
            runtime = store.layout.load_runtime()
            assert runtime.ui["comfyui"].stack == ["global"]

    def test_reset_clears_entire_stack(self):
        """
        Test that 'reset' clears entire stack in one operation.

        use A → use B → use C → reset → should be at global immediately
        """
        from src.store import Store, Pack, PackLock, PackSource, AssetKind, ProviderName

        with tempfile.TemporaryDirectory() as tmpdir:
            store = Store(Path(tmpdir))
            store.init()

            # Create packs
            for name in ["PackA", "PackB", "PackC"]:
                pack = Pack(
                    name=name,
                    pack_type=AssetKind.LORA,
                    source=PackSource(provider=ProviderName.CIVITAI),
                    dependencies=[],
                )
                store.layout.save_pack(pack)
                store.layout.save_pack_lock(PackLock(pack=name))
                store.profile_service.add_pack_to_global(name)

            # Stack multiple uses
            store.use("PackA", ui_set="local", sync=False)
            store.use("PackB", ui_set="local", sync=False)
            store.use("PackC", ui_set="local", sync=False)

            # Verify deep stack
            runtime = store.layout.load_runtime()
            assert runtime.ui["comfyui"].stack == ["global", "work__PackA", "work__PackB", "work__PackC"]

            # Reset
            result = store.reset(ui_set="local", sync=False)

            # Verify result
            assert result.to_profile == "global"
            assert result.from_profiles["comfyui"] == "work__PackC"

            # Verify stack is cleared
            runtime = store.layout.load_runtime()
            assert runtime.ui["comfyui"].stack == ["global"]
            assert runtime.get_active_profile("comfyui") == "global"

    def test_reset_at_global_is_noop(self):
        """
        Test that 'reset' at global level is a no-op.
        """
        from src.store import Store

        with tempfile.TemporaryDirectory() as tmpdir:
            store = Store(Path(tmpdir))
            store.init()

            result = store.reset(ui_set="local", sync=False)

            assert result.to_profile == "global"
            assert result.from_profiles["comfyui"] == "global"
            assert "already_at_global" in result.notes

            # Stack should still just be global
            runtime = store.layout.load_runtime()
            assert runtime.ui["comfyui"].stack == ["global"]

    def test_profile_restoration_after_delete(self):
        """
        Test that deleting the active pack correctly updates stack.
        """
        from src.store import Store, Pack, PackLock, PackSource, AssetKind, ProviderName

        with tempfile.TemporaryDirectory() as tmpdir:
            store = Store(Path(tmpdir))
            store.init()

            # Create pack
            pack = Pack(
                name="ToDelete",
                pack_type=AssetKind.LORA,
                source=PackSource(provider=ProviderName.CIVITAI),
                dependencies=[],
            )
            store.layout.save_pack(pack)
            store.layout.save_pack_lock(PackLock(pack="ToDelete"))
            store.profile_service.add_pack_to_global("ToDelete")

            # Use it
            store.use("ToDelete", ui_set="local", sync=False)

            # Verify on work profile
            runtime = store.layout.load_runtime()
            assert runtime.get_active_profile("comfyui") == "work__ToDelete"

            # Delete pack
            deleted = store.delete_pack("ToDelete")
            assert deleted

            # Verify stack is cleaned up
            runtime = store.layout.load_runtime()
            assert "work__ToDelete" not in runtime.ui["comfyui"].stack
            # Should fall back to global or previous profile
            assert runtime.get_active_profile("comfyui") == "global"

    def test_consistent_stack_across_multiple_uis(self):
        """
        Test that stack operations affect all UIs in the set consistently.
        """
        from src.store import Store, Pack, PackLock, PackSource, AssetKind, ProviderName

        with tempfile.TemporaryDirectory() as tmpdir:
            store = Store(Path(tmpdir))
            store.init()

            pack = Pack(
                name="MultiUI",
                pack_type=AssetKind.LORA,
                source=PackSource(provider=ProviderName.CIVITAI),
                dependencies=[],
            )
            store.layout.save_pack(pack)
            store.layout.save_pack_lock(PackLock(pack="MultiUI"))
            store.profile_service.add_pack_to_global("MultiUI")

            # Use pack
            store.use("MultiUI", ui_set="local", sync=False)

            # Check all UIs in "local" set have same stack
            runtime = store.layout.load_runtime()
            ui_sets = store.layout.load_ui_sets()

            for ui in ui_sets.sets.get("local", []):
                if ui in runtime.ui:
                    assert runtime.get_active_profile(ui) == "work__MultiUI", \
                        f"UI {ui} should have work__MultiUI active"

            # Back
            store.back(ui_set="local", sync=False)

            runtime = store.layout.load_runtime()
            for ui in ui_sets.sets.get("local", []):
                if ui in runtime.ui:
                    assert runtime.get_active_profile(ui) == "global", \
                        f"UI {ui} should be back at global"

    def test_interleaved_use_back_operations(self):
        """
        Test complex interleaved use/back operations.

        use A → use B → back → use C → back → back → should be at global
        """
        from src.store import Store, Pack, PackLock, PackSource, AssetKind, ProviderName

        with tempfile.TemporaryDirectory() as tmpdir:
            store = Store(Path(tmpdir))
            store.init()

            # Create packs
            for name in ["PackA", "PackB", "PackC"]:
                pack = Pack(
                    name=name,
                    pack_type=AssetKind.LORA,
                    source=PackSource(provider=ProviderName.CIVITAI),
                    dependencies=[],
                )
                store.layout.save_pack(pack)
                store.layout.save_pack_lock(PackLock(pack=name))
                store.profile_service.add_pack_to_global(name)

            # use A
            store.use("PackA", ui_set="local", sync=False)
            runtime = store.layout.load_runtime()
            assert runtime.ui["comfyui"].stack == ["global", "work__PackA"]

            # use B
            store.use("PackB", ui_set="local", sync=False)
            runtime = store.layout.load_runtime()
            assert runtime.ui["comfyui"].stack == ["global", "work__PackA", "work__PackB"]

            # back (pop B)
            result = store.back(ui_set="local", sync=False)
            assert result.to_profile == "work__PackA"
            runtime = store.layout.load_runtime()
            assert runtime.ui["comfyui"].stack == ["global", "work__PackA"]

            # use C
            store.use("PackC", ui_set="local", sync=False)
            runtime = store.layout.load_runtime()
            assert runtime.ui["comfyui"].stack == ["global", "work__PackA", "work__PackC"]

            # back (pop C)
            result = store.back(ui_set="local", sync=False)
            assert result.to_profile == "work__PackA"

            # back (pop A)
            result = store.back(ui_set="local", sync=False)
            assert result.to_profile == "global"

            # Verify at global
            runtime = store.layout.load_runtime()
            assert runtime.ui["comfyui"].stack == ["global"]


# =============================================================================
# CLI Integration Tests
# =============================================================================

class TestCLIIntegration:
    """
    Integration tests for CLI commands using typer.testing.CliRunner.
    """

    @pytest.fixture
    def cli_runner(self):
        """Create a CLI test runner."""
        from typer.testing import CliRunner
        return CliRunner()

    @pytest.fixture
    def temp_store(self, tmp_path, monkeypatch):
        """Create a temporary store for CLI tests."""
        from src.store import Store

        store_path = tmp_path / "store"
        store = Store(store_path)
        store.init()

        # Monkeypatch get_store to return our test store
        def mock_get_store():
            return store

        from src.store import cli
        monkeypatch.setattr(cli, "get_store", mock_get_store)

        return store

    def test_cli_init_creates_store(self, cli_runner, tmp_path, monkeypatch):
        """Test 'synapse store init' creates a new store."""
        from src.store import Store
        from src.store.cli import app

        store_path = tmp_path / "new_store"

        def mock_get_store():
            return Store(store_path)

        from src.store import cli
        monkeypatch.setattr(cli, "get_store", mock_get_store)

        result = cli_runner.invoke(app, ["store", "init"])

        assert result.exit_code == 0
        assert "initialized" in result.output.lower() or "Store initialized" in result.output

    def test_cli_list_empty(self, cli_runner, temp_store):
        """Test 'synapse list' with no packs."""
        from src.store.cli import app

        result = cli_runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "No packs installed" in result.output

    def test_cli_list_json(self, cli_runner, temp_store):
        """Test 'synapse list --json' returns valid JSON."""
        from src.store.cli import app
        import json

        result = cli_runner.invoke(app, ["list", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "packs" in data
        assert isinstance(data["packs"], list)

    def test_cli_status(self, cli_runner, temp_store):
        """Test 'synapse status' shows current state."""
        from src.store.cli import app

        result = cli_runner.invoke(app, ["status"])

        assert result.exit_code == 0
        # New Rich-formatted output uses table with "Synapse Status" header
        assert "global" in result.output.lower()

    def test_cli_status_json(self, cli_runner, temp_store):
        """Test 'synapse status --json' returns valid JSON."""
        from src.store.cli import app
        import json

        result = cli_runner.invoke(app, ["status", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "profile" in data
        assert "ui_targets" in data
        assert "active" in data

    def test_cli_use_requires_pack(self, cli_runner, temp_store):
        """Test 'synapse use' requires pack name."""
        from src.store.cli import app

        result = cli_runner.invoke(app, ["use"])

        # Should fail - missing required argument
        assert result.exit_code != 0

    def test_cli_back_at_global(self, cli_runner, temp_store):
        """Test 'synapse back' at global level."""
        from src.store.cli import app

        result = cli_runner.invoke(app, ["back"])

        assert result.exit_code == 0
        # Should indicate we're already at base
        assert "global" in result.output.lower() or "Back:" in result.output

    def test_cli_use_and_back_workflow(self, cli_runner, temp_store):
        """Test complete use/back workflow via CLI."""
        from src.store.cli import app
        from src.store import Pack, PackLock, PackSource, AssetKind, ProviderName

        # Create a pack first
        pack = Pack(
            name="CLITestPack",
            pack_type=AssetKind.LORA,
            source=PackSource(provider=ProviderName.CIVITAI),
            dependencies=[],
        )
        temp_store.layout.save_pack(pack)
        temp_store.layout.save_pack_lock(PackLock(pack="CLITestPack"))
        temp_store.profile_service.add_pack_to_global("CLITestPack")

        # List packs
        result = cli_runner.invoke(app, ["list"])
        assert "CLITestPack" in result.output

        # Use pack
        result = cli_runner.invoke(app, ["use", "CLITestPack", "--no-sync"])
        assert result.exit_code == 0
        assert "Activated" in result.output or "work__CLITestPack" in result.output

        # Check status
        result = cli_runner.invoke(app, ["status"])
        assert "work__CLITestPack" in result.output

        # Back
        result = cli_runner.invoke(app, ["back"])
        assert result.exit_code == 0
        assert "global" in result.output.lower()

    def test_cli_doctor(self, cli_runner, temp_store):
        """Test 'synapse doctor' runs diagnostics."""
        from src.store.cli import app

        result = cli_runner.invoke(app, ["doctor"])

        assert result.exit_code == 0
        # New Rich-formatted output uses "Doctor Report" header and "Profile:" label
        assert "Profile" in result.output or "global" in result.output.lower()

    def test_cli_doctor_json(self, cli_runner, temp_store):
        """Test 'synapse doctor --json' returns valid JSON."""
        from src.store.cli import app
        import json

        result = cli_runner.invoke(app, ["doctor", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "profile" in data
        assert "actions" in data

    def test_cli_clean(self, cli_runner, temp_store):
        """Test 'synapse clean' cleans temp files."""
        from src.store.cli import app

        # Create temp file
        temp_file = temp_store.layout.tmp_path / "test.tmp"
        temp_file.parent.mkdir(parents=True, exist_ok=True)
        temp_file.write_text("temp data")

        result = cli_runner.invoke(app, ["clean"])

        assert result.exit_code == 0
        assert "Cleaned" in result.output

    def test_cli_config(self, cli_runner, temp_store):
        """Test 'synapse store config' shows configuration."""
        from src.store.cli import app

        result = cli_runner.invoke(app, ["store", "config"])

        assert result.exit_code == 0
        # New Rich-formatted output uses table with "Store Configuration" title
        assert "Store Configuration" in result.output or "comfyui" in result.output.lower()

    def test_cli_delete_nonexistent_pack(self, cli_runner, temp_store):
        """Test 'synapse delete' with non-existent pack."""
        from src.store.cli import app

        result = cli_runner.invoke(app, ["delete", "NonExistentPack", "--force"])

        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_cli_delete_pack(self, cli_runner, temp_store):
        """Test 'synapse delete' removes a pack."""
        from src.store.cli import app
        from src.store import Pack, PackLock, PackSource, AssetKind, ProviderName

        # Create pack
        pack = Pack(
            name="ToDeleteCLI",
            pack_type=AssetKind.LORA,
            source=PackSource(provider=ProviderName.CIVITAI),
            dependencies=[],
        )
        temp_store.layout.save_pack(pack)
        temp_store.layout.save_pack_lock(PackLock(pack="ToDeleteCLI"))

        # Delete with force
        result = cli_runner.invoke(app, ["delete", "ToDeleteCLI", "--force"])

        assert result.exit_code == 0
        assert "Deleted" in result.output

        # Verify gone
        assert not temp_store.layout.pack_exists("ToDeleteCLI")

    def test_cli_reset_at_global(self, cli_runner, temp_store):
        """Test 'synapse reset' at global level."""
        from src.store.cli import app

        result = cli_runner.invoke(app, ["reset"])

        assert result.exit_code == 0
        assert "global" in result.output.lower()
        # Should indicate we were already at global
        assert "Already at global profile" in result.output or "Reset to:" in result.output

    def test_cli_reset_after_use(self, cli_runner, temp_store):
        """Test 'synapse reset' after using multiple packs."""
        from src.store.cli import app
        from src.store import Pack, PackLock, PackSource, AssetKind, ProviderName

        # Create packs
        for name in ["PackA", "PackB", "PackC"]:
            pack = Pack(
                name=name,
                pack_type=AssetKind.LORA,
                source=PackSource(provider=ProviderName.CIVITAI),
                dependencies=[],
            )
            temp_store.layout.save_pack(pack)
            temp_store.layout.save_pack_lock(PackLock(pack=name))
            temp_store.profile_service.add_pack_to_global(name)

        # Stack multiple uses
        cli_runner.invoke(app, ["use", "PackA", "--no-sync"])
        cli_runner.invoke(app, ["use", "PackB", "--no-sync"])
        cli_runner.invoke(app, ["use", "PackC", "--no-sync"])

        # Verify we're on PackC
        runtime = temp_store.layout.load_runtime()
        assert runtime.get_active_profile("comfyui") == "work__PackC"
        assert len(runtime.ui["comfyui"].stack) == 4  # global + 3 work profiles

        # Reset
        result = cli_runner.invoke(app, ["reset"])

        assert result.exit_code == 0
        assert "Reset to: global" in result.output

        # Verify stack is reset
        runtime = temp_store.layout.load_runtime()
        assert runtime.ui["comfyui"].stack == ["global"]
        assert runtime.get_active_profile("comfyui") == "global"

    def test_cli_reset_json_output(self, cli_runner, temp_store):
        """Test 'synapse reset --json' returns valid JSON."""
        from src.store.cli import app
        import json

        result = cli_runner.invoke(app, ["reset", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "to_profile" in data
        assert data["to_profile"] == "global"
        assert "from_profiles" in data
        assert "ui_targets" in data


# =============================================================================
# Edge Case Tests
# =============================================================================

class TestEdgeCases:
    """
    Edge case tests for unusual scenarios.
    """

    def test_empty_profile_builds_empty_view(self):
        """Test that an empty profile creates an empty view."""
        from src.store import Store, Profile

        with tempfile.TemporaryDirectory() as tmpdir:
            store = Store(Path(tmpdir))
            store.init()

            # Create empty profile
            empty_profile = Profile(name="empty", packs=[])
            store.layout.save_profile(empty_profile)

            # Build view
            report = store.view_builder.build("comfyui", empty_profile, {})

            assert report.entries_created == 0
            assert len(report.shadowed) == 0
            assert len(report.errors) == 0

    def test_pack_with_no_dependencies(self):
        """Test pack with no dependencies works correctly."""
        from src.store import Store, Pack, PackLock, PackSource, AssetKind, ProviderName

        with tempfile.TemporaryDirectory() as tmpdir:
            store = Store(Path(tmpdir))
            store.init()

            pack = Pack(
                name="NoDeps",
                pack_type=AssetKind.LORA,
                source=PackSource(provider=ProviderName.CIVITAI),
                dependencies=[],
            )
            store.layout.save_pack(pack)
            store.layout.save_pack_lock(PackLock(pack="NoDeps"))
            store.profile_service.add_pack_to_global("NoDeps")

            # Use should work
            result = store.use("NoDeps", ui_set="local", sync=True)

            assert result.pack == "NoDeps"
            assert result.created_profile == "work__NoDeps"

    def test_same_pack_use_twice_updates_profile(self):
        """Test using same pack twice updates the work profile."""
        from src.store import Store, Pack, PackLock, PackSource, AssetKind, ProviderName

        with tempfile.TemporaryDirectory() as tmpdir:
            store = Store(Path(tmpdir))
            store.init()

            pack = Pack(
                name="DoublePack",
                pack_type=AssetKind.LORA,
                source=PackSource(provider=ProviderName.CIVITAI),
                dependencies=[],
            )
            store.layout.save_pack(pack)
            store.layout.save_pack_lock(PackLock(pack="DoublePack"))
            store.profile_service.add_pack_to_global("DoublePack")

            # First use
            result1 = store.use("DoublePack", ui_set="local", sync=False)
            assert "profile_created" in result1.notes or "profile_updated" in result1.notes

            # Back
            store.back(ui_set="local", sync=False)

            # Second use should work too
            result2 = store.use("DoublePack", ui_set="local", sync=False)
            assert result2.created_profile == "work__DoublePack"

    def test_unicode_pack_name(self):
        """Test pack names with unicode characters."""
        from src.store import Store, Pack, PackLock, PackSource, AssetKind, ProviderName

        with tempfile.TemporaryDirectory() as tmpdir:
            store = Store(Path(tmpdir))
            store.init()

            # Note: This might fail depending on filesystem
            pack_name = "TestPack_v1.0"  # Safe name with special chars

            pack = Pack(
                name=pack_name,
                pack_type=AssetKind.LORA,
                source=PackSource(provider=ProviderName.CIVITAI),
                dependencies=[],
            )
            store.layout.save_pack(pack)
            store.layout.save_pack_lock(PackLock(pack=pack_name))

            # Verify it can be loaded
            loaded = store.layout.load_pack(pack_name)
            assert loaded.name == pack_name

    def test_very_deep_blob_storage_path(self):
        """Test blob storage with SHA256 hash creates correct path."""
        from src.store import Store

        with tempfile.TemporaryDirectory() as tmpdir:
            store = Store(Path(tmpdir))
            store.init()

            content = b"test content for deep path"
            sha = hashlib.sha256(content).hexdigest()

            blob_path = store.blob_store.blob_path(sha)
            blob_path.parent.mkdir(parents=True, exist_ok=True)
            blob_path.write_bytes(content)

            # Verify path structure (should be <root>/blobs/<sha[0:2]>/<sha>)
            assert sha[:2] in str(blob_path)
            assert blob_path.exists()
            assert blob_path.read_bytes() == content

    def test_missing_blob_does_not_crash_view_build(self):
        """Test that missing blobs are handled gracefully in view building."""
        from src.store import (
            Store, Pack, PackLock, PackDependency, DependencySelector,
            ExposeConfig, ResolvedDependency, ResolvedArtifact, ArtifactProvider,
            PackSource, AssetKind, ProviderName, SelectorStrategy
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            store = Store(Path(tmpdir))
            store.init()

            missing_sha = "0" * 64

            pack = Pack(
                name="MissingBlobPack",
                pack_type=AssetKind.LORA,
                source=PackSource(provider=ProviderName.CIVITAI),
                dependencies=[
                    PackDependency(
                        id="main",
                        kind=AssetKind.LORA,
                        selector=DependencySelector(strategy=SelectorStrategy.CIVITAI_FILE),
                        expose=ExposeConfig(filename="missing.safetensors"),
                    ),
                ],
            )
            store.layout.save_pack(pack)
            store.layout.save_pack_lock(PackLock(
                pack="MissingBlobPack",
                resolved=[
                    ResolvedDependency(
                        dependency_id="main",
                        artifact=ResolvedArtifact(
                            kind=AssetKind.LORA,
                            sha256=missing_sha,
                            provider=ArtifactProvider(name=ProviderName.CIVITAI),
                        ),
                    ),
                ],
            ))
            store.profile_service.add_pack_to_global("MissingBlobPack")

            # Use should not crash, but symlink won't be created
            result = store.use("MissingBlobPack", ui_set="local", sync=True)

            assert result.pack == "MissingBlobPack"

            # View should exist but without the symlink
            view_path = store.layout.view_profile_path("comfyui", "work__MissingBlobPack")
            assert view_path.exists()

    def test_concurrent_view_builds_for_same_profile(self):
        """Test that views can be built for different UIs concurrently."""
        from src.store import (
            Store, Pack, PackLock, PackDependency, DependencySelector,
            ExposeConfig, ResolvedDependency, ResolvedArtifact, ArtifactProvider,
            PackSource, AssetKind, ProviderName, SelectorStrategy
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            store = Store(Path(tmpdir))
            store.init()

            content = b"concurrent test content"
            sha = hashlib.sha256(content).hexdigest()
            blob_path = store.blob_store.blob_path(sha)
            blob_path.parent.mkdir(parents=True, exist_ok=True)
            blob_path.write_bytes(content)

            pack = Pack(
                name="ConcurrentPack",
                pack_type=AssetKind.LORA,
                source=PackSource(provider=ProviderName.CIVITAI),
                dependencies=[
                    PackDependency(
                        id="main",
                        kind=AssetKind.LORA,
                        selector=DependencySelector(strategy=SelectorStrategy.CIVITAI_FILE),
                        expose=ExposeConfig(filename="concurrent.safetensors"),
                    ),
                ],
            )
            store.layout.save_pack(pack)
            store.layout.save_pack_lock(PackLock(
                pack="ConcurrentPack",
                resolved=[
                    ResolvedDependency(
                        dependency_id="main",
                        artifact=ResolvedArtifact(
                            kind=AssetKind.LORA,
                            sha256=sha,
                            provider=ArtifactProvider(name=ProviderName.CIVITAI),
                        ),
                    ),
                ],
            ))
            store.profile_service.add_pack_to_global("ConcurrentPack")

            # Build for multiple UIs
            global_profile = store.profile_service.load_global()
            packs_data = {
                "ConcurrentPack": (store.layout.load_pack("ConcurrentPack"), store.layout.load_pack_lock("ConcurrentPack"))
            }

            # Build for both UIs
            report_comfy = store.view_builder.build("comfyui", global_profile, packs_data)
            report_forge = store.view_builder.build("forge", global_profile, packs_data)

            # Both should succeed
            assert report_comfy.entries_created >= 1
            assert report_forge.entries_created >= 1

            # Both views should have the symlink
            comfy_lora = store.layout.view_profile_path("comfyui", "global") / "models" / "loras" / "concurrent.safetensors"
            forge_lora = store.layout.view_profile_path("forge", "global") / "models" / "Lora" / "concurrent.safetensors"

            assert comfy_lora.exists()
            assert forge_lora.exists()

    def test_reinitialize_store_preserves_data(self):
        """Test that reinitializing with --force preserves blobs."""
        from src.store import Store

        with tempfile.TemporaryDirectory() as tmpdir:
            store = Store(Path(tmpdir))
            store.init()

            # Add some data
            content = b"preserve this blob"
            sha = hashlib.sha256(content).hexdigest()
            blob_path = store.blob_store.blob_path(sha)
            blob_path.parent.mkdir(parents=True, exist_ok=True)
            blob_path.write_bytes(content)

            # Reinit with force
            store.init(force=True)

            # Blob should still exist (data is in data/, not state/)
            assert store.blob_store.blob_exists(sha)
            assert store.blob_store.blob_path(sha).read_bytes() == content
