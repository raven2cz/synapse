"""
Synapse Store v2 - Main Entry Point

This module provides the main Store facade for interacting with the
Synapse storage system.

Usage:
    from src.store import Store
    
    store = Store()
    store.init()
    
    # Import from Civitai
    pack = store.import_civitai("https://civitai.com/models/12345")
    
    # Install and sync
    store.install(pack.name)
    store.sync("global", ["comfyui"])
    
    # Use a specific pack
    result = store.use("MyPack", ["comfyui"])
    
    # Go back
    store.back(["comfyui"])
"""

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .blob_store import BlobStore, BlobStoreError, DownloadError, HashMismatchError
from .layout import (
    PackNotFoundError,
    ProfileNotFoundError,
    StoreError,
    StoreLayout,
    StoreLockError,
    StoreNotInitializedError,
)
from .models import (
    APIResponse,
    ArtifactDownload,
    ArtifactIntegrity,
    ArtifactProvider,
    AssetKind,
    BackResult,
    BackupConfig,
    BackupDeleteResult,
    BackupOperationResult,
    BackupStatus,
    BlobLocation,
    BlobStatus,
    CivitaiSelector,
    CleanupResult,
    DeleteResult,
    DependencySelector,
    DoctorReport,
    ExposeConfig,
    HuggingFaceSelector,
    ImpactAnalysis,
    InventoryItem,
    InventoryResponse,
    InventorySummary,
    MissingBlob,
    Pack,
    PackDependency,
    PackLock,
    PackResources,
    PackSource,
    Profile,
    ProfilePackEntry,
    ProviderName,
    ResetResult,
    ResolvedArtifact,
    ResolvedDependency,
    Runtime,
    SearchResult,
    SelectorConstraints,
    SelectorStrategy,
    ShadowedEntry,
    StatusReport,
    StoreConfig,
    SyncItem,
    SyncResult,
    UISets,
    UnresolvedDependency,
    UnresolvedReport,
    UpdatePolicy,
    UpdatePlan,
    UpdatePolicyMode,
    UpdateResult,
    UseResult,
)
from .backup_service import BackupService, BackupError, BackupNotConnectedError, BackupNotEnabledError
from .inventory_service import InventoryService
from .pack_service import PackService
from .profile_service import ProfileService
from .update_service import UpdateService
from .view_builder import BuildReport, ViewBuilder, ViewBuildError


__all__ = [
    # Main facade
    "Store",
    
    # Layout
    "StoreLayout",
    
    # Services
    "BlobStore",
    "ViewBuilder",
    "PackService",
    "ProfileService",
    "UpdateService",
    "InventoryService",
    
    # Models
    "Pack",
    "PackLock",
    "Profile",
    "Runtime",
    "StoreConfig",
    "UISets",
    "AssetKind",
    "ProviderName",
    "SelectorStrategy",
    
    # Results
    "StatusReport",
    "UpdatePlan",
    "UpdateResult",
    "UseResult",
    "BackResult",
    "ResetResult",
    "DeleteResult",
    "DoctorReport",
    "SearchResult",
    "BuildReport",
    "APIResponse",

    # Inventory
    "BlobStatus",
    "BlobLocation",
    "InventoryItem",
    "InventoryResponse",
    "InventorySummary",
    "CleanupResult",
    "ImpactAnalysis",

    # Backup
    "BackupService",
    "BackupConfig",
    "BackupStatus",
    "BackupOperationResult",
    "BackupDeleteResult",
    "SyncItem",
    "SyncResult",
    "BackupError",
    "BackupNotEnabledError",
    "BackupNotConnectedError",

    # Errors
    "StoreError",
    "StoreLockError",
    "StoreNotInitializedError",
    "PackNotFoundError",
    "ProfileNotFoundError",
    "BlobStoreError",
    "DownloadError",
    "HashMismatchError",
    "ViewBuildError",
]


class Store:
    """
    Main facade for Synapse Store v2.
    
    Provides high-level operations for managing packs, profiles, and views.
    """
    
    def __init__(
        self,
        root: Optional[Path] = None,
        civitai_client: Optional[Any] = None,
        huggingface_client: Optional[Any] = None,
        civitai_api_key: Optional[str] = None,
    ):
        """
        Initialize the store.

        Args:
            root: Root directory for the store. Defaults to SYNAPSE_ROOT env var
                  or ~/.synapse/store
            civitai_client: Optional CivitaiClient instance
            huggingface_client: Optional HuggingFaceClient instance
            civitai_api_key: Optional Civitai API key for authenticated downloads
        """
        self.layout = StoreLayout(root)
        self.blob_store = BlobStore(self.layout, api_key=civitai_api_key)
        self.view_builder = ViewBuilder(self.layout, self.blob_store)
        self.pack_service = PackService(
            self.layout,
            self.blob_store,
            civitai_client,
            huggingface_client,
        )
        self.profile_service = ProfileService(
            self.layout,
            self.blob_store,
            self.view_builder,
        )
        self.update_service = UpdateService(
            self.layout,
            self.blob_store,
            self.view_builder,
            civitai_client,
        )
        # BackupService initialized with default config, updated when store loads
        self.backup_service = BackupService(
            self.layout,
            BackupConfig(),
        )
        # InventoryService with backup support
        self.inventory_service = InventoryService(
            self.layout,
            self.blob_store,
            self.backup_service,
        )
        # Set backup service on profile service for auto-restore
        self.profile_service.set_backup_service(self.backup_service)

    # =========================================================================
    # Initialization
    # =========================================================================
    
    def is_initialized(self) -> bool:
        """Check if store is initialized."""
        return self.layout.is_initialized()
    
    def init(self, force: bool = False) -> None:
        """
        Initialize the store.
        
        Args:
            force: If True, reinitialize even if already initialized.
        """
        self.layout.init_store(force)
    
    # =========================================================================
    # Config
    # =========================================================================
    
    def get_config(self) -> StoreConfig:
        """Get store configuration."""
        return self.layout.load_config()
    
    def save_config(self, config: StoreConfig) -> None:
        """Save store configuration."""
        self.layout.save_config(config)
    
    def get_ui_sets(self) -> UISets:
        """Get UI sets configuration."""
        return self.layout.load_ui_sets()
    
    def get_default_ui_set(self) -> str:
        """Get default UI set name from config."""
        config = self.get_config()
        return config.defaults.ui_set
    
    def get_ui_targets(self, ui_set: Optional[str] = None) -> List[str]:
        """
        Get UI targets for a UI set.
        
        Args:
            ui_set: Name of UI set. Uses default if None.
        
        Returns:
            List of UI names
        """
        if ui_set is None:
            ui_set = self.get_default_ui_set()
        
        ui_sets = self.get_ui_sets()
        return ui_sets.sets.get(ui_set, [])
    
    # =========================================================================
    # Pack Operations
    # =========================================================================
    
    def list_packs(self) -> List[str]:
        """List all pack names."""
        return self.pack_service.list_packs()
    
    def list_models(self, kind: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all installed models in the store.
        
        Args:
            kind: Optional filter by asset kind (e.g., 'checkpoint', 'lora')
            
        Returns:
            List of model details
        """
        models = []
        for pack_name in self.list_packs():
            try:
                pack = self.get_pack(pack_name)
                lock = self.get_pack_lock(pack_name)
                if not lock:
                    continue
                
                for dep in pack.dependencies:
                    # Filter by kind if specified
                    dep_kind = dep.kind.value if hasattr(dep.kind, 'value') else str(dep.kind)
                    if kind and kind.lower() != dep_kind.lower():
                        continue
                    
                    resolved = lock.get_resolved(dep.id)
                    if resolved and resolved.artifact.sha256:
                        if self.blob_store.blob_exists(resolved.artifact.sha256):
                            # Get preview image if available
                            preview_url = None
                            previews_dir = self.layout.pack_previews_path(pack_name)
                            if previews_dir.exists():
                                for ext in ['.png', '.jpg', '.jpeg', '.webp']:
                                    matches = list(previews_dir.glob(f'*{ext}'))
                                    if matches:
                                        preview_url = f"/previews/{pack_name}/resources/previews/{matches[0].name}"
                                        break
                            
                            models.append({
                                "id": f"{pack_name}:{dep.id}",
                                "name": resolved.artifact.provider.filename,
                                "kind": dep_kind,
                                "pack": pack_name,
                                "base_model": pack.base_model,
                                "image": preview_url,
                                "filename": resolved.artifact.provider.filename, # v1 compat
                                "size": resolved.artifact.size_bytes,
                            })
            except Exception:
                pass
        return models
    
    def search(self, query: str) -> SearchResult:
        """
        Search packs by name or metadata.
        
        Uses simple substring matching. In the future, could use SQLite FTS.
        
        Args:
            query: Search query string
        
        Returns:
            SearchResult with matching packs
        """
        from .models import SearchResult, SearchResultItem
        
        query_lower = query.lower().strip()
        items = []
        
        for pack_name in self.list_packs():
            try:
                pack = self.layout.load_pack(pack_name)
                
                # Check if query matches pack name
                if query_lower in pack_name.lower():
                    items.append(SearchResultItem(
                        pack_name=pack_name,
                        pack_type=pack.pack_type.value if hasattr(pack.pack_type, 'value') else str(pack.pack_type),
                        provider=pack.source.provider.value if pack.source else None,
                        source_model_id=pack.source.model_id if pack.source else None,
                        source_url=pack.source.url if pack.source else None,
                    ))
                    continue
                
                # Check dependencies
                for dep in pack.dependencies:
                    if query_lower in dep.id.lower():
                        items.append(SearchResultItem(
                            pack_name=pack_name,
                            pack_type=pack.pack_type.value if hasattr(pack.pack_type, 'value') else str(pack.pack_type),
                            provider=pack.source.provider.value if pack.source else None,
                            source_model_id=pack.source.model_id if pack.source else None,
                            source_url=pack.source.url if pack.source else None,
                        ))
                        break
                        
            except Exception:
                # Skip packs that can't be loaded
                continue
        
        return SearchResult(
            query=query,
            used_db=False,  # Simple scan, no DB
            items=items,
        )
    
    def get_pack(self, pack_name: str) -> Pack:
        """Get a pack by name."""
        return self.pack_service.load_pack(pack_name)
    
    def get_pack_lock(self, pack_name: str) -> Optional[PackLock]:
        """Get lock file for a pack."""
        return self.layout.load_pack_lock(pack_name)
    
    def delete_pack(self, pack_name: str) -> "DeleteResult":
        """Delete a pack and clean up associated resources.

        This includes:
        - Removing from global profile
        - Deleting work profile (work__<pack>)
        - Removing from runtime stacks if active
        - Deleting pack files

        Returns:
            DeleteResult with detailed status of the operation
        """
        from .models import DeleteResult

        work_profile_name = self.profile_service.get_work_profile_name(pack_name)
        warnings: List[str] = []
        removed_from_stacks = False
        removed_from_global = False
        removed_work_profile = False

        # 1. Remove from runtime stacks if work profile is active (with lock)
        try:
            with self.layout.lock():
                runtime = self.layout.load_runtime()
                modified = False
                for ui_name, ui_state in runtime.ui.items():
                    if work_profile_name in ui_state.stack:
                        # Remove work profile from stack
                        ui_state.stack = [p for p in ui_state.stack if p != work_profile_name]
                        # Ensure at least global remains
                        if not ui_state.stack:
                            ui_state.stack = ["global"]
                        modified = True
                if modified:
                    self.layout.save_runtime(runtime)
                    removed_from_stacks = True
        except Exception as e:
            warnings.append(f"Failed to clean runtime stacks: {e}")

        # 2. Remove from global profile
        try:
            self.profile_service.remove_pack_from_global(pack_name)
            removed_from_global = True
        except Exception as e:
            warnings.append(f"Failed to remove from global profile: {e}")

        # 3. Delete work profile
        try:
            if self.layout.profile_exists(work_profile_name):
                self.layout.delete_profile(work_profile_name)
                removed_work_profile = True
        except Exception as e:
            warnings.append(f"Failed to delete work profile: {e}")

        # 4. Delete pack files
        deleted = self.pack_service.delete_pack(pack_name)

        return DeleteResult(
            pack_name=pack_name,
            deleted=deleted,
            cleanup_warnings=warnings,
            removed_from_global=removed_from_global,
            removed_work_profile=removed_work_profile,
            removed_from_stacks=removed_from_stacks,
        )
    
    def import_civitai(
        self,
        url: str,
        download_previews: bool = True,
        add_to_global: bool = True,
        # Extended wizard options
        pack_name: Optional[str] = None,
        max_previews: int = 100,
        download_images: bool = True,
        download_videos: bool = True,
        include_nsfw: bool = True,
        video_quality: int = 1080,
        download_from_all_versions: bool = True,
        cover_url: Optional[str] = None,
        selected_version_ids: Optional[List[int]] = None,
        **kwargs,  # For future extensibility
    ) -> Pack:
        """
        Import a pack from Civitai URL.

        Args:
            url: Civitai model URL
            download_previews: If True, download preview images/videos
            add_to_global: If True, add pack to global profile
            pack_name: Optional custom pack name
            max_previews: Maximum number of previews to download
            download_images: Whether to download image previews
            download_videos: Whether to download video previews
            include_nsfw: Whether to include NSFW content
            video_quality: Target video width (450, 720, 1080)
            download_from_all_versions: If True, download previews from all versions
            cover_url: User-selected thumbnail URL for pack cover
            selected_version_ids: List of version IDs to import (creates one dependency per version)

        Returns:
            Created Pack
        """
        from .pack_service import PreviewDownloadConfig

        # Build download config from wizard options
        download_config = PreviewDownloadConfig(
            download_images=download_images,
            download_videos=download_videos,
            include_nsfw=include_nsfw,
            video_quality=video_quality,
            download_from_all_versions=download_from_all_versions,
        )

        pack = self.pack_service.import_from_civitai(
            url=url,
            download_previews=download_previews,
            max_previews=max_previews,
            pack_name=pack_name,
            download_config=download_config,
            cover_url=cover_url,
            selected_version_ids=selected_version_ids,
        )

        if add_to_global:
            self.profile_service.add_pack_to_global(pack.name)

        return pack
    
    def resolve(
        self,
        pack_name: str,
        progress_callback: Optional[Callable[[str, str], None]] = None,
    ) -> PackLock:
        """
        Resolve all dependencies for a pack.
        
        Args:
            pack_name: Pack to resolve
            progress_callback: Optional callback (dep_id, status)
        
        Returns:
            Updated PackLock
        """
        return self.pack_service.resolve_pack(pack_name, progress_callback)
    
    def install(
        self,
        pack_name: str,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> List[str]:
        """
        Install all blobs for a pack.
        
        Args:
            pack_name: Pack to install
            progress_callback: Optional callback (dep_id, downloaded, total)
        
        Returns:
            List of installed SHA256 hashes
        """
        return self.pack_service.install_pack(pack_name, progress_callback)
    
    # =========================================================================
    # Profile Operations
    # =========================================================================
    
    def list_profiles(self) -> List[str]:
        """List all profile names."""
        return self.layout.list_profiles()
    
    def get_profile(self, profile_name: str) -> Profile:
        """Get a profile by name."""
        return self.layout.load_profile(profile_name)
    
    def get_global_profile(self) -> Profile:
        """Get the global profile."""
        return self.profile_service.load_global()
    
    def sync(
        self,
        profile_name: str,
        ui_targets: Optional[List[str]] = None,
        ui_set: Optional[str] = None,
        install_missing: bool = True,
    ) -> Dict[str, BuildReport]:
        """
        Sync a profile: install missing blobs and build views.
        
        Args:
            profile_name: Profile to sync
            ui_targets: List of UI names. If None, uses ui_set.
            ui_set: Name of UI set to use. Uses default if None.
            install_missing: If True, download missing blobs
        
        Returns:
            Dict mapping ui -> BuildReport
        """
        if ui_targets is None:
            ui_targets = self.get_ui_targets(ui_set)
        
        return self.profile_service.sync_profile(
            profile_name,
            ui_targets,
            install_missing,
        )
    
    # =========================================================================
    # Use/Back Operations
    # =========================================================================
    
    def use(
        self,
        pack_name: str,
        ui_targets: Optional[List[str]] = None,
        ui_set: Optional[str] = None,
        sync: bool = True,
    ) -> UseResult:
        """
        Execute 'use' command for a pack.
        
        Args:
            pack_name: Pack to use
            ui_targets: List of UI names. If None, uses ui_set.
            ui_set: Name of UI set to use. Uses default if None.
            sync: If True, build views
        
        Returns:
            UseResult with details
        """
        if ui_targets is None:
            ui_targets = self.get_ui_targets(ui_set)
        
        result = self.profile_service.use(pack_name, ui_targets, sync=sync)
        
        # Refresh already-attached UIs (don't auto-attach detached ones)
        if sync and ui_targets:
            try:
                self.refresh_attached_uis(ui_targets=ui_targets)
            except Exception:
                # Don't fail use() if refresh fails
                pass
        
        return result
    
    def back(
        self,
        ui_targets: Optional[List[str]] = None,
        ui_set: Optional[str] = None,
        sync: bool = False,
    ) -> BackResult:
        """
        Execute 'back' command.
        
        Args:
            ui_targets: List of UI names. If None, uses ui_set.
            ui_set: Name of UI set to use. Uses default if None.
            sync: If True, rebuild views
        
        Returns:
            BackResult with details
        """
        if ui_targets is None:
            ui_targets = self.get_ui_targets(ui_set)
        
        result = self.profile_service.back(ui_targets, sync)
        
        # Refresh already-attached UIs (don't auto-attach detached ones)
        if sync and ui_targets:
            try:
                self.refresh_attached_uis(ui_targets=ui_targets)
            except Exception:
                # Don't fail back() if refresh fails
                pass
        
        return result

    def reset(
        self,
        ui_targets: Optional[List[str]] = None,
        ui_set: Optional[str] = None,
        sync: bool = False,
    ) -> "ResetResult":
        """
        Reset stack to global for all specified UIs.

        Pops all work profiles and returns to just ["global"].

        Args:
            ui_targets: List of UI names. If None, uses ui_set.
            ui_set: Name of UI set to use. Uses default if None.
            sync: If True, rebuild views

        Returns:
            ResetResult with details
        """
        from .models import ResetResult

        if ui_targets is None:
            ui_targets = self.get_ui_targets(ui_set)

        notes: List[str] = []
        from_profiles: dict[str, str] = {}

        with self.layout.lock():
            runtime = self.layout.load_runtime()

            for ui in ui_targets:
                # Remember what profile we were on
                from_profiles[ui] = runtime.get_active_profile(ui)

                # Reset stack to just global
                runtime.set_stack(ui, ["global"])

            # Save runtime
            self.layout.save_runtime(runtime)

            # Update active symlinks (ignore if view doesn't exist yet)
            for ui in ui_targets:
                try:
                    self.view_builder.activate(ui, "global")
                except Exception:
                    # View may not exist yet - sync will create it
                    notes.append(f"view_not_activated:{ui}")

        # Sync if requested (outside lock to avoid long hold)
        if sync:
            self.sync(ui_set=ui_set)

        # Check if we were already at global
        if all(p == "global" for p in from_profiles.values()):
            notes.append("already_at_global")

        return ResetResult(
            ui_targets=ui_targets,
            from_profiles=from_profiles,
            to_profile="global",
            synced=sync,
            notes=notes,
        )

    # =========================================================================
    # Update Operations
    # =========================================================================

    def check_updates(self, pack_name: str) -> UpdatePlan:
        """
        Check for updates on a pack.
        
        Args:
            pack_name: Pack to check
        
        Returns:
            UpdatePlan with changes
        """
        return self.update_service.plan_update(pack_name)
    
    def check_all_updates(self) -> Dict[str, UpdatePlan]:
        """
        Check for updates on all packs.
        
        Returns:
            Dict mapping pack_name -> UpdatePlan
        """
        return self.update_service.check_all_updates()
    
    def update(
        self,
        pack_name: str,
        dry_run: bool = False,
        choose: Optional[Dict[str, int]] = None,
        sync: bool = False,
        ui_targets: Optional[List[str]] = None,
        ui_set: Optional[str] = None,
    ) -> UpdateResult:
        """
        Update a pack to latest versions.
        
        Args:
            pack_name: Pack to update
            dry_run: If True, only plan without applying
            choose: Optional file selections for ambiguous updates
            sync: If True, download new blobs and rebuild views
            ui_targets: UI targets for sync
            ui_set: UI set name for sync
        
        Returns:
            UpdateResult with details
        """
        if sync and ui_targets is None:
            ui_targets = self.get_ui_targets(ui_set)
        
        return self.update_service.update_pack(
            pack_name,
            dry_run,
            choose,
            sync,
            ui_targets,
        )
    
    # =========================================================================
    # Status
    # =========================================================================
    
    def status(
        self,
        ui_targets: Optional[List[str]] = None,
        ui_set: Optional[str] = None,
    ) -> StatusReport:
        """
        Get current status.
        
        Args:
            ui_targets: List of UI names. If None, uses ui_set.
            ui_set: Name of UI set to use. Uses default if None.
        
        Returns:
            StatusReport with current state
        """
        if ui_targets is None:
            ui_targets = self.get_ui_targets(ui_set)
        
        runtime = self.layout.load_runtime()
        
        # Get active profiles
        active = {ui: runtime.get_active_profile(ui) for ui in ui_targets}
        
        # Determine which profile to report on (use first UI's active)
        if ui_targets:
            profile_name = active.get(ui_targets[0], "global")
        else:
            profile_name = "global"
        
        # Collect missing blobs and unresolved
        missing_blobs = []
        unresolved = []
        
        try:
            profile = self.layout.load_profile(profile_name)
            
            for pack_entry in profile.packs:
                try:
                    pack = self.layout.load_pack(pack_entry.name)
                    lock = self.layout.load_pack_lock(pack_entry.name)
                    
                    if lock:
                        # Check resolved
                        for resolved in lock.resolved:
                            sha256 = resolved.artifact.sha256
                            if sha256 and not self.blob_store.blob_exists(sha256):
                                dep = pack.get_dependency(resolved.dependency_id)
                                missing_blobs.append(MissingBlob(
                                    pack=pack_entry.name,
                                    dependency_id=resolved.dependency_id,
                                    kind=dep.kind if dep else AssetKind.UNKNOWN,
                                    sha256=sha256,
                                ))
                        
                        # Check unresolved
                        for unres in lock.unresolved:
                            unresolved.append(UnresolvedReport(
                                pack=pack_entry.name,
                                dependency_id=unres.dependency_id,
                                reason=unres.reason,
                                details=unres.details,
                            ))
                except Exception:
                    pass
        except Exception:
            pass
        
        # Get shadowed entries (would need to compute view plan for accurate info)
        shadowed: List[ShadowedEntry] = []
        
        return StatusReport(
            profile=profile_name,
            ui_targets=ui_targets,
            active=active,
            missing_blobs=missing_blobs,
            unresolved=unresolved,
            shadowed=shadowed,
        )
    
    # =========================================================================
    # Doctor
    # =========================================================================
    
    def doctor(
        self,
        rebuild_views: bool = True,
        rebuild_db: Optional[str] = None,
        verify_blobs: bool = False,
        ui_targets: Optional[List[str]] = None,
        ui_set: Optional[str] = None,
    ) -> DoctorReport:
        """
        Run diagnostics and repairs.
        
        Args:
            rebuild_views: If True, rebuild all views
            rebuild_db: "auto" or "force" to rebuild DB
            verify_blobs: If True, verify all blob hashes
            ui_targets: List of UI names
            ui_set: Name of UI set
        
        Returns:
            DoctorReport with actions taken
        """
        from .models import DoctorActions
        
        if ui_targets is None:
            ui_targets = self.get_ui_targets(ui_set)
        
        runtime = self.layout.load_runtime()
        profile_name = runtime.get_active_profile(ui_targets[0]) if ui_targets else "global"
        
        actions = DoctorActions()
        notes = []
        
        # Verify blobs if requested
        if verify_blobs:
            valid, invalid = self.blob_store.verify_all()
            actions.blobs_verified = True
            if invalid:
                notes.append(f"Found {len(invalid)} invalid blobs")
        
        # Rebuild views if requested
        if rebuild_views:
            try:
                profile = self.layout.load_profile(profile_name)
                
                # Load packs
                packs_data = {}
                for p in profile.packs:
                    try:
                        pack = self.layout.load_pack(p.name)
                        lock = self.layout.load_pack_lock(p.name)
                        packs_data[p.name] = (pack, lock)
                    except Exception:
                        pass
                
                # Build for each UI
                for ui in ui_targets:
                    self.view_builder.build(ui, profile, packs_data)
                    self.view_builder.activate(ui, profile_name)
                
                actions.views_rebuilt = True
            except Exception as e:
                notes.append(f"Failed to rebuild views: {e}")
        
        # DB rebuild (placeholder - SQLite not implemented yet)
        if rebuild_db:
            actions.db_rebuilt = rebuild_db
            notes.append("SQLite DB not implemented yet")
        
        # Get current status
        status = self.status(ui_targets)
        
        return DoctorReport(
            profile=profile_name,
            ui_targets=ui_targets,
            actions=actions,
            active=status.active,
            missing_blobs=status.missing_blobs,
            unresolved=status.unresolved,
            shadowed=status.shadowed,
            notes=notes,
        )
    
    # =========================================================================
    # UI Attach Operations
    # =========================================================================
    
    def _get_ui_attacher(self):
        """Get UIAttacher instance (lazy initialization)."""
        if not hasattr(self, '_ui_attacher'):
            from .ui_attach import UIAttacher
            
            # Get ui_roots from synapse config if available
            ui_roots = {}
            if hasattr(self, '_synapse_config') and self._synapse_config:
                cfg = self._synapse_config
                ui_roots = {
                    "comfyui": cfg.store.ui_roots.comfyui,
                    "forge": cfg.store.ui_roots.forge,
                    "a1111": cfg.store.ui_roots.a1111,
                    "sdnext": cfg.store.ui_roots.sdnext,
                }
            else:
                # Fallback to defaults
                from pathlib import Path
                home = Path.home()
                ui_roots = {
                    "comfyui": home / "ComfyUI",
                    "forge": home / "stable-diffusion-webui-forge",
                    "a1111": home / "stable-diffusion-webui",
                    "sdnext": home / "sdnext",
                }
            
            # Get store config for UIKindMap
            try:
                store_config = self.layout.load_config()
            except Exception:
                store_config = None
            
            self._ui_attacher = UIAttacher(self.layout, ui_roots, store_config)
        
        return self._ui_attacher
    
    def attach_uis(
        self,
        ui_targets: Optional[List[str]] = None,
        ui_set: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Attach UIs to their Synapse views.
        
        Creates symlinks so UIs can see Synapse-managed models.
        
        Args:
            ui_targets: List of UI names. If None, uses ui_set.
            ui_set: Name of UI set to use. Uses default if None.
        
        Returns:
            Dict mapping ui -> result dict
        """
        if ui_targets is None:
            ui_targets = self.get_ui_targets(ui_set)
        
        attacher = self._get_ui_attacher()
        results = attacher.attach_all(ui_targets)
        
        # Convert to dict for serialization
        return {
            ui: {
                "ui": r.ui,
                "success": r.success,
                "method": r.method,
                "created": r.created,
                "errors": r.errors,
            }
            for ui, r in results.items()
        }
    
    def detach_uis(
        self,
        ui_targets: Optional[List[str]] = None,
        ui_set: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Detach UIs from Synapse views.
        
        Removes symlinks.
        
        Args:
            ui_targets: List of UI names. If None, uses ui_set.
            ui_set: Name of UI set to use. Uses default if None.
        
        Returns:
            Dict mapping ui -> result dict
        """
        if ui_targets is None:
            ui_targets = self.get_ui_targets(ui_set)
        
        attacher = self._get_ui_attacher()
        results = {}
        for ui in ui_targets:
            r = attacher.detach(ui)
            results[ui] = {
                "ui": r.ui,
                "success": r.success,
                "method": r.method,
                "created": r.created,
                "errors": r.errors,
            }
        
        return results
    
    def refresh_attached_uis(
        self,
        ui_targets: Optional[List[str]] = None,
        ui_set: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Refresh attachment for UIs that are already attached.
        
        This updates paths to match current active view WITHOUT attaching
        UIs that are currently detached.
        
        Called automatically after use/back/sync to keep attached UIs in sync.
        
        Args:
            ui_targets: List of UI names. If None, uses ui_set.
            ui_set: Name of UI set to use. Uses default if None.
        
        Returns:
            Dict mapping ui -> result dict (only for UIs that were refreshed)
        """
        if ui_targets is None:
            ui_targets = self.get_ui_targets(ui_set)
        
        attacher = self._get_ui_attacher()
        results = attacher.refresh_attached(ui_targets)
        
        # Convert to dict for serialization
        return {
            ui: {
                "ui": r.ui,
                "success": r.success,
                "method": r.method,
                "created": r.created,
                "errors": r.errors,
            }
            for ui, r in results.items()
        }
    
    def get_attach_status(
        self,
        ui_targets: Optional[List[str]] = None,
        ui_set: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get attachment status for UIs.
        
        Args:
            ui_targets: List of UI names. If None, uses ui_set.
            ui_set: Name of UI set to use. Uses default if None.
        
        Returns:
            Dict mapping ui -> status dict
        """
        if ui_targets is None:
            ui_targets = self.get_ui_targets(ui_set)
        
        attacher = self._get_ui_attacher()
        return {ui: attacher.status(ui) for ui in ui_targets}
    
    # =========================================================================
    # Cleanup
    # =========================================================================
    
    def clean(
        self,
        tmp: bool = True,
        cache: bool = False,
        partial: bool = True,
    ) -> Dict[str, int]:
        """
        Clean temporary files.
        
        Args:
            tmp: Clean tmp directory
            cache: Clean cache directory
            partial: Clean partial downloads
        
        Returns:
            Dict with counts of cleaned items
        """
        result = {}
        
        if tmp:
            result["tmp"] = self.layout.clean_tmp()
        
        if cache:
            result["cache"] = self.layout.clean_cache()
        
        if partial:
            result["partial"] = self.blob_store.clean_partial()

        return result

    # =========================================================================
    # Inventory
    # =========================================================================

    def get_inventory(
        self,
        kind_filter: Optional[AssetKind] = None,
        status_filter: Optional["BlobStatus"] = None,
        include_verification: bool = False,
    ) -> "InventoryResponse":
        """
        Get blob inventory with optional filtering.

        Args:
            kind_filter: Filter by asset kind
            status_filter: Filter by blob status
            include_verification: If True, verify blob hashes (slow!)

        Returns:
            Complete inventory response with summary and items
        """
        return self.inventory_service.build_inventory(
            kind_filter=kind_filter,
            status_filter=status_filter,
            include_verification=include_verification,
        )

    def get_inventory_summary(self) -> "InventorySummary":
        """
        Get quick inventory summary (without item list).

        Returns:
            Summary statistics only
        """
        response = self.inventory_service.build_inventory()
        return response.summary

    def cleanup_orphans(self, dry_run: bool = True, max_items: int = 0) -> "CleanupResult":
        """
        Remove orphan blobs safely.

        NEVER removes referenced blobs.

        Args:
            dry_run: If True, only preview without deleting
            max_items: Maximum number of items to delete (0 = unlimited)

        Returns:
            Cleanup result with details
        """
        return self.inventory_service.cleanup_orphans(dry_run=dry_run, max_items=max_items)

    def get_blob_impacts(self, sha256: str) -> "ImpactAnalysis":
        """
        Analyze what would break if a blob is deleted.

        Args:
            sha256: SHA256 hash of blob to analyze

        Returns:
            Impact analysis
        """
        return self.inventory_service.get_impacts(sha256)

    def delete_blob(
        self,
        sha256: str,
        force: bool = False,
        target: str = "local",
    ) -> Dict:
        """
        Delete a blob with safety checks.

        Args:
            sha256: SHA256 hash of blob to delete
            force: If True, delete even if referenced
            target: Where to delete from: "local", "backup", or "both"

        Returns:
            Dict with deletion result
        """
        return self.inventory_service.delete_blob(sha256, force=force, target=target)

    def verify_blobs(
        self,
        sha256_list: Optional[List[str]] = None,
        all_blobs: bool = False,
    ) -> Dict:
        """
        Verify blob integrity.

        Args:
            sha256_list: Specific blobs to verify
            all_blobs: If True, verify all blobs

        Returns:
            Verification result
        """
        return self.inventory_service.verify_blobs(sha256_list=sha256_list, all_blobs=all_blobs)

    # =========================================================================
    # Backup Storage Operations
    # =========================================================================

    def get_backup_status(self) -> "BackupStatus":
        """
        Get backup storage status.

        Returns:
            BackupStatus with connection info and statistics
        """
        # Ensure backup service has current config
        if self.is_initialized():
            config = self.layout.load_config()
            self.backup_service.update_config(config.backup)
        return self.backup_service.get_status()

    def backup_blob(
        self,
        sha256: str,
        verify_after: bool = True,
    ) -> "BackupOperationResult":
        """
        Backup a blob from local to backup storage.

        Args:
            sha256: SHA256 hash of the blob
            verify_after: If True, verify the copy after backup

        Returns:
            BackupOperationResult with operation details
        """
        return self.backup_service.backup_blob(sha256, verify_after=verify_after)

    def restore_blob(
        self,
        sha256: str,
        verify_after: bool = True,
    ) -> "BackupOperationResult":
        """
        Restore a blob from backup to local storage.

        Args:
            sha256: SHA256 hash of the blob
            verify_after: If True, verify the copy after restore

        Returns:
            BackupOperationResult with operation details
        """
        return self.backup_service.restore_blob(sha256, verify_after=verify_after)

    def delete_from_backup(
        self,
        sha256: str,
        confirm: bool = False,
    ) -> "BackupDeleteResult":
        """
        Delete a blob from backup storage.

        Args:
            sha256: SHA256 hash of the blob
            confirm: Must be True to actually delete

        Returns:
            BackupDeleteResult with operation details
        """
        return self.backup_service.delete_from_backup(sha256, confirm=confirm)

    def sync_backup(
        self,
        direction: str = "to_backup",
        only_missing: bool = True,
        dry_run: bool = True,
    ) -> "SyncResult":
        """
        Sync blobs between local and backup storage.

        Args:
            direction: "to_backup" or "from_backup"
            only_missing: Only sync blobs missing from target
            dry_run: If True, only preview without syncing

        Returns:
            SyncResult with sync details
        """
        return self.backup_service.sync(
            direction=direction,
            only_missing=only_missing,
            dry_run=dry_run,
        )

    def configure_backup(self, config: "BackupConfig") -> None:
        """
        Update backup configuration.

        Args:
            config: New backup configuration
        """
        # Update the stored config
        if self.is_initialized():
            store_config = self.layout.load_config()
            store_config.backup = config
            self.layout.save_config(store_config)
        # Update the service
        self.backup_service.update_config(config)

    def is_backup_connected(self) -> bool:
        """Quick check if backup is connected."""
        return self.backup_service.is_connected()

    def blob_exists_on_backup(self, sha256: str) -> bool:
        """Check if blob exists on backup storage."""
        return self.backup_service.blob_exists_on_backup(sha256)

    # =========================================================================
    # Pack-Level Backup Operations (pull/push)
    # =========================================================================

    def pull_pack(
        self,
        pack_name: str,
        dry_run: bool = True,
    ) -> "SyncResult":
        """
        Pull (restore) all blobs for a pack from backup to local.

        This restores pack blobs without activating any profile.
        Use case: Need pack models locally but want to stay on global profile.

        Args:
            pack_name: Name of the pack to pull
            dry_run: If True, only preview without restoring

        Returns:
            SyncResult with restore details
        """
        # Load pack and lock
        pack = self.layout.load_pack(pack_name)
        lock = self.layout.load_pack_lock(pack_name)

        if not lock:
            return SyncResult(
                dry_run=dry_run,
                direction="from_backup",
                blobs_to_sync=0,
                bytes_to_sync=0,
                blobs_synced=0,
                bytes_synced=0,
                items=[],
                errors=[f"Pack {pack_name} has no lock file"],
            )

        # Collect blobs that need to be restored
        items_to_restore: List[SyncItem] = []
        errors: List[str] = []

        for resolved in lock.resolved:
            sha256 = resolved.artifact.sha256
            if not sha256:
                continue

            # Skip if already local
            if self.blob_store.blob_exists(sha256):
                continue

            # Check if on backup
            if not self.backup_service.is_connected():
                errors.append("Backup not connected")
                break

            if self.backup_service.blob_exists_on_backup(sha256):
                # Get display name and kind from dependency
                dep = pack.get_dependency(resolved.dependency_id)
                # Use expose.filename as primary, fallback to dep.id or dependency_id
                display_name = (
                    dep.expose.filename if dep and dep.expose else
                    dep.id if dep else
                    resolved.dependency_id
                )
                # P5: Include kind in SyncItem
                kind = dep.kind.value if dep and hasattr(dep.kind, 'value') else str(dep.kind) if dep else None

                items_to_restore.append(SyncItem(
                    sha256=sha256,
                    size_bytes=resolved.artifact.size_bytes or 0,
                    display_name=display_name,
                    kind=kind,
                ))
            else:
                # P4: Blob not on backup - report as error instead of silent download fallback
                dep = pack.get_dependency(resolved.dependency_id)
                dep_name = dep.id if dep else resolved.dependency_id
                errors.append(f"Blob {sha256[:12]} ({dep_name}) not found on backup")

        bytes_to_sync = sum(item.size_bytes for item in items_to_restore)
        blobs_synced = 0
        bytes_synced = 0

        # Execute restore if not dry run
        if not dry_run:
            for item in items_to_restore:
                try:
                    result = self.backup_service.restore_blob(item.sha256)
                    if result.success:
                        blobs_synced += 1
                        bytes_synced += item.size_bytes
                    else:
                        errors.append(f"Restore failed for {item.sha256[:12]}: {result.error}")
                except Exception as e:
                    errors.append(f"Restore error for {item.sha256[:12]}: {e}")

        return SyncResult(
            dry_run=dry_run,
            direction="from_backup",
            blobs_to_sync=len(items_to_restore),
            bytes_to_sync=bytes_to_sync,
            blobs_synced=blobs_synced,
            bytes_synced=bytes_synced,
            items=items_to_restore,
            errors=errors,
        )

    def push_pack(
        self,
        pack_name: str,
        dry_run: bool = True,
        cleanup: bool = False,
    ) -> "SyncResult":
        """
        Push (backup) all blobs for a pack from local to backup.

        Optionally removes local copies after successful backup.

        Args:
            pack_name: Name of the pack to push
            dry_run: If True, only preview without backing up
            cleanup: If True, delete local copies after backup (requires dry_run=False)

        Returns:
            SyncResult with backup details
        """
        # Load pack and lock
        pack = self.layout.load_pack(pack_name)
        lock = self.layout.load_pack_lock(pack_name)

        if not lock:
            return SyncResult(
                dry_run=dry_run,
                direction="to_backup",
                blobs_to_sync=0,
                bytes_to_sync=0,
                blobs_synced=0,
                bytes_synced=0,
                items=[],
                errors=[f"Pack {pack_name} has no lock file"],
            )

        # Collect blobs that need to be backed up
        items_to_backup: List[SyncItem] = []
        errors: List[str] = []

        if not self.backup_service.is_connected():
            return SyncResult(
                dry_run=dry_run,
                direction="to_backup",
                blobs_to_sync=0,
                bytes_to_sync=0,
                blobs_synced=0,
                bytes_synced=0,
                items=[],
                errors=["Backup not connected"],
            )

        for resolved in lock.resolved:
            sha256 = resolved.artifact.sha256
            if not sha256:
                continue

            # Skip if not local
            if not self.blob_store.blob_exists(sha256):
                continue

            # Skip if already on backup
            if self.backup_service.blob_exists_on_backup(sha256):
                continue

            # Get display name and kind from dependency
            dep = pack.get_dependency(resolved.dependency_id)
            # Use expose.filename as primary, fallback to dep.id
            display_name = (
                dep.expose.filename if dep and dep.expose else
                dep.id if dep else
                resolved.dependency_id
            )
            # P5: Include kind in SyncItem
            kind = dep.kind.value if dep and hasattr(dep.kind, 'value') else str(dep.kind) if dep else None

            items_to_backup.append(SyncItem(
                sha256=sha256,
                size_bytes=resolved.artifact.size_bytes or 0,
                display_name=display_name,
                kind=kind,
            ))

        bytes_to_sync = sum(item.size_bytes for item in items_to_backup)
        blobs_synced = 0
        bytes_synced = 0
        blobs_cleaned = 0

        # Execute backup if not dry run
        if not dry_run:
            for item in items_to_backup:
                try:
                    result = self.backup_service.backup_blob(item.sha256)
                    if result.success:
                        blobs_synced += 1
                        bytes_synced += item.size_bytes

                        # Cleanup local copy if requested
                        if cleanup:
                            try:
                                self.blob_store.remove_blob(item.sha256)
                                blobs_cleaned += 1
                            except Exception as e:
                                errors.append(f"Cleanup failed for {item.sha256[:12]}: {e}")
                    else:
                        errors.append(f"Backup failed for {item.sha256[:12]}: {result.error}")
                except Exception as e:
                    errors.append(f"Backup error for {item.sha256[:12]}: {e}")

            if cleanup and blobs_cleaned > 0:
                errors.append(f"note:cleaned_up_{blobs_cleaned}_local_copies")

        return SyncResult(
            dry_run=dry_run,
            direction="to_backup",
            blobs_to_sync=len(items_to_backup),
            bytes_to_sync=bytes_to_sync,
            blobs_synced=blobs_synced,
            bytes_synced=bytes_synced,
            items=items_to_backup,
            errors=errors,
        )
