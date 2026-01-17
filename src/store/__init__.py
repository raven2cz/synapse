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
    CivitaiSelector,
    DependencySelector,
    DoctorReport,
    ExposeConfig,
    HuggingFaceSelector,
    MissingBlob,
    Pack,
    PackDependency,
    PackLock,
    PackResources,
    PackSource,
    Profile,
    ProfilePackEntry,
    ProviderName,
    ResolvedArtifact,
    ResolvedDependency,
    Runtime,
    SearchResult,
    SelectorConstraints,
    SelectorStrategy,
    ShadowedEntry,
    StatusReport,
    StoreConfig,
    UISets,
    UnresolvedDependency,
    UnresolvedReport,
    UpdatePolicy,
    UpdatePlan,
    UpdatePolicyMode,
    UpdateResult,
    UseResult,
)
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
    "DoctorReport",
    "SearchResult",
    "BuildReport",
    "APIResponse",
    
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
                  or ~/.synapse
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
    
    def delete_pack(self, pack_name: str) -> bool:
        """Delete a pack."""
        # Remove from global profile first
        try:
            self.profile_service.remove_pack_from_global(pack_name)
        except Exception:
            pass
        return self.pack_service.delete_pack(pack_name)
    
    def import_civitai(
        self,
        url: str,
        download_previews: bool = True,
        add_to_global: bool = True,
    ) -> Pack:
        """
        Import a pack from Civitai URL.
        
        Args:
            url: Civitai model URL
            download_previews: If True, download preview images
            add_to_global: If True, add pack to global profile
        
        Returns:
            Created Pack
        """
        pack = self.pack_service.import_from_civitai(url, download_previews)
        
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
