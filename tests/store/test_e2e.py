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
