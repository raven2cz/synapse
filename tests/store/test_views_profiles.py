"""
Tests for Synapse Store v2 - View Builder and Profile Service

Tests:
- View building and symlinks
- Profile management
- Use/back workflow
"""

import hashlib
import os
import tempfile
from pathlib import Path

import pytest


class TestViewBuilder:
    """Tests for ViewBuilder class."""
    
    def test_compute_plan_empty_profile(self):
        """Test computing plan for empty profile."""
        from src.store import (
            StoreLayout, BlobStore, ViewBuilder, 
            Profile, AssetKind
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            layout = StoreLayout(Path(tmpdir))
            layout.init_store()
            blob_store = BlobStore(layout)
            builder = ViewBuilder(layout, blob_store)
            
            profile = Profile(name="test")
            
            plan = builder.compute_plan("comfyui", profile, {})
            
            assert plan.ui == "comfyui"
            assert plan.profile == "test"
            assert len(plan.entries) == 0
            assert len(plan.shadowed) == 0
    
    def test_compute_plan_with_pack(self):
        """Test computing plan with a pack."""
        from src.store import (
            StoreLayout, BlobStore, ViewBuilder,
            Profile, ProfilePackEntry, Pack, PackLock, PackSource,
            PackDependency, DependencySelector, ExposeConfig,
            ResolvedDependency, ResolvedArtifact, ArtifactProvider,
            AssetKind, ProviderName, SelectorStrategy
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            layout = StoreLayout(Path(tmpdir))
            layout.init_store()
            blob_store = BlobStore(layout)
            builder = ViewBuilder(layout, blob_store)
            
            # Create test blob
            content = b"test model content"
            sha256 = hashlib.sha256(content).hexdigest()
            blob_path = blob_store.blob_path(sha256)
            blob_path.parent.mkdir(parents=True, exist_ok=True)
            blob_path.write_bytes(content)
            
            # Create pack
            pack = Pack(
                name="TestPack",
                pack_type=AssetKind.LORA,
                source=PackSource(provider=ProviderName.CIVITAI, model_id=123),
                dependencies=[
                    PackDependency(
                        id="main_lora",
                        kind=AssetKind.LORA,
                        selector=DependencySelector(strategy=SelectorStrategy.CIVITAI_FILE),
                        expose=ExposeConfig(filename="test_lora.safetensors"),
                    )
                ],
            )
            
            # Create lock
            lock = PackLock(
                pack="TestPack",
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
            
            # Create profile
            profile = Profile(
                name="test",
                packs=[ProfilePackEntry(name="TestPack")],
            )
            
            # Compute plan
            plan = builder.compute_plan(
                "comfyui",
                profile,
                {"TestPack": (pack, lock)},
            )
            
            assert len(plan.entries) == 1
            entry = plan.entries[0]
            assert entry.pack_name == "TestPack"
            assert entry.expose_filename == "test_lora.safetensors"
            assert entry.sha256 == sha256
            assert "loras" in entry.dst_relpath
    
    def test_last_wins_conflict_resolution(self):
        """Test that later packs shadow earlier ones."""
        from src.store import (
            StoreLayout, BlobStore, ViewBuilder,
            Profile, ProfilePackEntry, Pack, PackLock, PackSource,
            PackDependency, DependencySelector, ExposeConfig,
            ResolvedDependency, ResolvedArtifact, ArtifactProvider,
            AssetKind, ProviderName, SelectorStrategy
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            layout = StoreLayout(Path(tmpdir))
            layout.init_store()
            blob_store = BlobStore(layout)
            builder = ViewBuilder(layout, blob_store)
            
            # Create blobs
            content1 = b"pack1 content"
            content2 = b"pack2 content"
            sha1 = hashlib.sha256(content1).hexdigest()
            sha2 = hashlib.sha256(content2).hexdigest()
            
            for sha, content in [(sha1, content1), (sha2, content2)]:
                path = blob_store.blob_path(sha)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            
            # Same filename in both packs
            filename = "shared_lora.safetensors"
            
            packs_data = {}
            for i, sha in enumerate([sha1, sha2], 1):
                pack = Pack(
                    name=f"Pack{i}",
                    pack_type=AssetKind.LORA,
                    source=PackSource(provider=ProviderName.CIVITAI),
                    dependencies=[
                        PackDependency(
                            id="main",
                            kind=AssetKind.LORA,
                            selector=DependencySelector(strategy=SelectorStrategy.CIVITAI_FILE),
                            expose=ExposeConfig(filename=filename),
                        )
                    ],
                )
                lock = PackLock(
                    pack=f"Pack{i}",
                    resolved=[
                        ResolvedDependency(
                            dependency_id="main",
                            artifact=ResolvedArtifact(
                                kind=AssetKind.LORA,
                                sha256=sha,
                                provider=ArtifactProvider(name=ProviderName.CIVITAI),
                            ),
                        )
                    ],
                )
                packs_data[f"Pack{i}"] = (pack, lock)
            
            # Profile with Pack1 first, Pack2 last
            profile = Profile(
                name="test",
                packs=[
                    ProfilePackEntry(name="Pack1"),
                    ProfilePackEntry(name="Pack2"),
                ],
            )
            
            plan = builder.compute_plan("comfyui", profile, packs_data)
            
            # Should have one entry (Pack2 wins)
            assert len(plan.entries) == 1
            assert plan.entries[0].pack_name == "Pack2"
            assert plan.entries[0].sha256 == sha2
            
            # Should have one shadowed entry
            assert len(plan.shadowed) == 1
            assert plan.shadowed[0].winner_pack == "Pack2"
            assert plan.shadowed[0].loser_pack == "Pack1"
    
    def test_build_creates_symlinks(self):
        """Test that build creates working symlinks."""
        from src.store import (
            StoreLayout, BlobStore, ViewBuilder,
            Profile, ProfilePackEntry, Pack, PackLock, PackSource,
            PackDependency, DependencySelector, ExposeConfig,
            ResolvedDependency, ResolvedArtifact, ArtifactProvider,
            AssetKind, ProviderName, SelectorStrategy
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            layout = StoreLayout(Path(tmpdir))
            layout.init_store()
            blob_store = BlobStore(layout)
            builder = ViewBuilder(layout, blob_store)
            
            # Create blob
            content = b"lora content"
            sha256 = hashlib.sha256(content).hexdigest()
            blob_path = blob_store.blob_path(sha256)
            blob_path.parent.mkdir(parents=True, exist_ok=True)
            blob_path.write_bytes(content)
            
            # Create pack and lock
            pack = Pack(
                name="TestPack",
                pack_type=AssetKind.LORA,
                source=PackSource(provider=ProviderName.CIVITAI),
                dependencies=[
                    PackDependency(
                        id="main",
                        kind=AssetKind.LORA,
                        selector=DependencySelector(strategy=SelectorStrategy.CIVITAI_FILE),
                        expose=ExposeConfig(filename="my_lora.safetensors"),
                    )
                ],
            )
            lock = PackLock(
                pack="TestPack",
                resolved=[
                    ResolvedDependency(
                        dependency_id="main",
                        artifact=ResolvedArtifact(
                            kind=AssetKind.LORA,
                            sha256=sha256,
                            provider=ArtifactProvider(name=ProviderName.CIVITAI),
                        ),
                    )
                ],
            )
            
            profile = Profile(
                name="test",
                packs=[ProfilePackEntry(name="TestPack")],
            )
            
            # Build
            report = builder.build("comfyui", profile, {"TestPack": (pack, lock)})
            
            assert report.entries_created == 1
            assert len(report.errors) == 0
            
            # Check symlink exists
            expected_link = layout.view_profile_path("comfyui", "test") / "models" / "loras" / "my_lora.safetensors"
            assert expected_link.exists()
            assert expected_link.is_symlink()
            
            # Check symlink points to blob
            assert expected_link.resolve() == blob_path.resolve()
            
            # Check content is accessible
            assert expected_link.read_bytes() == content
    
    def test_activate_profile(self):
        """Test activating a profile."""
        from src.store import (
            StoreLayout, BlobStore, ViewBuilder, Profile
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            layout = StoreLayout(Path(tmpdir))
            layout.init_store()
            blob_store = BlobStore(layout)
            builder = ViewBuilder(layout, blob_store)
            
            # Create empty profile view
            profile = Profile(name="test")
            builder.build("comfyui", profile, {})
            
            # Activate
            builder.activate("comfyui", "test")
            
            # Check active symlink
            active_path = layout.view_active_path("comfyui")
            assert active_path.is_symlink()
            
            target = os.readlink(active_path)
            assert target == "profiles/test"
    
    def test_get_active_profile(self):
        """Test getting active profile."""
        from src.store import (
            StoreLayout, BlobStore, ViewBuilder, Profile
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            layout = StoreLayout(Path(tmpdir))
            layout.init_store()
            blob_store = BlobStore(layout)
            builder = ViewBuilder(layout, blob_store)
            
            # No active initially
            assert builder.get_active_profile("comfyui") is None
            
            # Build and activate
            profile = Profile(name="myprofile")
            builder.build("comfyui", profile, {})
            builder.activate("comfyui", "myprofile")
            
            assert builder.get_active_profile("comfyui") == "myprofile"


class TestProfileService:
    """Tests for ProfileService class."""
    
    def test_load_global(self):
        """Test loading global profile."""
        from src.store import Store
        
        with tempfile.TemporaryDirectory() as tmpdir:
            store = Store(Path(tmpdir))
            store.init()
            
            profile = store.profile_service.load_global()
            assert profile.name == "global"
    
    def test_add_pack_to_global(self):
        """Test adding pack to global profile."""
        from src.store import (
            Store, Pack, PackSource, AssetKind, ProviderName
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            store = Store(Path(tmpdir))
            store.init()
            
            # Create pack
            pack = Pack(
                name="TestPack",
                pack_type=AssetKind.LORA,
                source=PackSource(provider=ProviderName.CIVITAI),
            )
            store.layout.save_pack(pack)
            
            # Add to global
            store.profile_service.add_pack_to_global("TestPack")
            
            # Verify
            global_profile = store.profile_service.load_global()
            pack_names = [p.name for p in global_profile.packs]
            assert "TestPack" in pack_names
    
    def test_work_profile_name(self):
        """Test work profile naming."""
        from src.store import Store
        
        with tempfile.TemporaryDirectory() as tmpdir:
            store = Store(Path(tmpdir))
            
            name = store.profile_service.get_work_profile_name("MyPack")
            assert name == "work__MyPack"
            
            assert store.profile_service.is_work_profile("work__MyPack")
            assert not store.profile_service.is_work_profile("global")
            assert not store.profile_service.is_work_profile("MyPack")
    
    def test_ensure_work_profile_creates(self):
        """Test work profile creation."""
        from src.store import (
            Store, Pack, PackSource, AssetKind, ProviderName
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            store = Store(Path(tmpdir))
            store.init()
            
            # Create pack and add to global
            pack = Pack(
                name="TestPack",
                pack_type=AssetKind.LORA,
                source=PackSource(provider=ProviderName.CIVITAI),
            )
            store.layout.save_pack(pack)
            store.profile_service.add_pack_to_global("TestPack")
            
            # Create work profile
            work, created = store.profile_service.ensure_work_profile("TestPack")
            
            assert created
            assert work.name == "work__TestPack"
            
            # Pack should be at end
            pack_names = work.get_pack_names()
            assert pack_names[-1] == "TestPack"
    
    def test_use_command(self):
        """Test 'use' command workflow."""
        from src.store import (
            Store, Pack, PackSource, PackLock, 
            AssetKind, ProviderName
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            store = Store(Path(tmpdir))
            store.init()
            
            # Create pack
            pack = Pack(
                name="TestPack",
                pack_type=AssetKind.LORA,
                source=PackSource(provider=ProviderName.CIVITAI),
            )
            store.layout.save_pack(pack)
            store.layout.save_pack_lock(PackLock(pack="TestPack"))
            store.profile_service.add_pack_to_global("TestPack")
            
            # Use pack
            result = store.profile_service.use(
                "TestPack",
                ui_targets=["comfyui"],
                sync=False,
            )
            
            assert result.pack == "TestPack"
            assert result.created_profile == "work__TestPack"
            assert "comfyui" in result.ui_targets
            
            # Check runtime stack updated
            runtime = store.layout.load_runtime()
            assert runtime.get_active_profile("comfyui") == "work__TestPack"
    
    def test_back_command(self):
        """Test 'back' command workflow."""
        from src.store import (
            Store, Pack, PackSource, PackLock,
            AssetKind, ProviderName
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            store = Store(Path(tmpdir))
            store.init()
            
            # Create pack
            pack = Pack(
                name="TestPack",
                pack_type=AssetKind.LORA,
                source=PackSource(provider=ProviderName.CIVITAI),
            )
            store.layout.save_pack(pack)
            store.layout.save_pack_lock(PackLock(pack="TestPack"))
            store.profile_service.add_pack_to_global("TestPack")
            
            # Use then back
            store.profile_service.use("TestPack", ["comfyui"], sync=False)
            result = store.profile_service.back(["comfyui"], sync=False)
            
            assert result.from_profile == "work__TestPack"
            assert result.to_profile == "global"
            
            # Check runtime stack updated
            runtime = store.layout.load_runtime()
            assert runtime.get_active_profile("comfyui") == "global"
    
    def test_back_at_base_does_nothing(self):
        """Test that back at base profile does nothing."""
        from src.store import Store
        
        with tempfile.TemporaryDirectory() as tmpdir:
            store = Store(Path(tmpdir))
            store.init()
            
            result = store.profile_service.back(["comfyui"], sync=False)
            
            # Already at global
            assert result.from_profile == "global"
            assert result.to_profile == "global"
            assert "already_at_base" in result.notes


class TestStoreHighLevelAPI:
    """Tests for Store high-level API."""
    
    def test_status_empty(self):
        """Test status on empty store."""
        from src.store import Store
        
        with tempfile.TemporaryDirectory() as tmpdir:
            store = Store(Path(tmpdir))
            store.init()
            
            status = store.status()
            
            assert status.profile == "global"
            assert len(status.missing_blobs) == 0
            assert len(status.unresolved) == 0
    
    def test_clean_operations(self):
        """Test clean operations."""
        from src.store import Store
        
        with tempfile.TemporaryDirectory() as tmpdir:
            store = Store(Path(tmpdir))
            store.init()
            
            # Create some temp files
            tmp_file = store.layout.tmp_path / "test.tmp"
            tmp_file.write_text("temp")
            
            result = store.clean(tmp=True, cache=False, partial=False)
            
            assert result["tmp"] > 0
            assert not tmp_file.exists()
