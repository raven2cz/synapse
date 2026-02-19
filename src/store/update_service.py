"""
Synapse Store v2 - Update Service

Manages updates for packs with civitai_model_latest strategy.

Features:
- Check for new versions
- Create update plans
- Handle ambiguous file selection
- Apply updates atomically
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .blob_store import BlobStore
from .layout import StoreLayout
from .models import (
    AmbiguousUpdate,
    ArtifactDownload,
    ArtifactIntegrity,
    ArtifactProvider,
    Pack,
    PackLock,
    ProviderName,
    ResolvedArtifact,
    ResolvedDependency,
    SelectorStrategy,
    UpdateCandidate,
    UpdateChange,
    UpdatePlan,
    UpdatePolicyMode,
    UpdateResult,
)
from .view_builder import ViewBuilder


class UpdateError(Exception):
    """Base exception for update errors."""
    pass


class AmbiguousSelectionError(UpdateError):
    """Error when update requires explicit file selection."""
    
    def __init__(self, pack: str, ambiguous: List[AmbiguousUpdate]):
        self.pack = pack
        self.ambiguous = ambiguous
        super().__init__(f"Update for {pack} requires file selection")


class UpdateService:
    """
    Service for managing pack updates.
    """
    
    def __init__(
        self,
        layout: StoreLayout,
        blob_store: BlobStore,
        view_builder: ViewBuilder,
        civitai_client: Optional[Any] = None,
    ):
        """
        Initialize update service.
        
        Args:
            layout: Store layout manager
            blob_store: Blob store
            view_builder: View builder
            civitai_client: Optional CivitaiClient instance
        """
        self.layout = layout
        self.blob_store = blob_store
        self.view_builder = view_builder
        self._civitai = civitai_client
    
    @property
    def civitai(self):
        """Lazy-load Civitai client."""
        if self._civitai is None:
            from ..clients.civitai_client import CivitaiClient
            self._civitai = CivitaiClient()
        return self._civitai
    
    # =========================================================================
    # Update Planning
    # =========================================================================
    
    def is_updatable(self, pack: Pack) -> bool:
        """
        Check if a pack has any updatable dependencies.
        
        A pack is updatable if it has at least one dependency with:
        - selector.strategy = civitai_model_latest
        - update_policy.mode = follow_latest
        """
        for dep in pack.dependencies:
            if (dep.selector.strategy == SelectorStrategy.CIVITAI_MODEL_LATEST and
                dep.update_policy.mode == UpdatePolicyMode.FOLLOW_LATEST):
                return True
        return False
    
    def plan_update(self, pack_name: str) -> UpdatePlan:
        """
        Create an update plan for a pack.
        
        Checks each updatable dependency for new versions.
        
        Args:
            pack_name: Pack to check for updates
        
        Returns:
            UpdatePlan with changes and ambiguous selections
        """
        pack = self.layout.load_pack(pack_name)
        lock = self.layout.load_pack_lock(pack_name)
        
        if not lock:
            return UpdatePlan(
                pack=pack_name,
                already_up_to_date=False,
                changes=[],
                ambiguous=[],
                impacted_packs=self._find_reverse_dependencies(pack_name),
            )
        
        changes = []
        ambiguous = []
        
        for dep in pack.dependencies:
            # Skip non-updatable dependencies
            if dep.update_policy.mode != UpdatePolicyMode.FOLLOW_LATEST:
                continue
            if dep.selector.strategy != SelectorStrategy.CIVITAI_MODEL_LATEST:
                continue
            
            # Get current lock entry
            current = lock.get_resolved(dep.id)
            if not current:
                continue
            
            # Check for updates
            try:
                update_info = self._check_dependency_update(dep, current)
                if update_info:
                    if update_info["ambiguous"]:
                        ambiguous.append(AmbiguousUpdate(
                            dependency_id=dep.id,
                            candidates=update_info["candidates"],
                        ))
                    elif update_info["has_update"]:
                        changes.append(UpdateChange(
                            dependency_id=dep.id,
                            old={
                                "provider": "civitai",
                                "provider_model_id": current.artifact.provider.model_id,
                                "provider_version_id": current.artifact.provider.version_id,
                                "provider_file_id": current.artifact.provider.file_id,
                                "sha256": current.artifact.sha256,
                            },
                            new={
                                "provider": "civitai",
                                "provider_model_id": update_info["model_id"],
                                "provider_version_id": update_info["version_id"],
                                "provider_file_id": update_info["file_id"],
                                "sha256": update_info["sha256"],
                            },
                        ))
            except Exception:
                pass  # Log error, continue
        
        already_up_to_date = len(changes) == 0 and len(ambiguous) == 0

        # Scan for reverse dependencies (which packs depend on this one)
        impacted_packs = self._find_reverse_dependencies(pack_name)

        return UpdatePlan(
            pack=pack_name,
            already_up_to_date=already_up_to_date,
            changes=changes,
            ambiguous=ambiguous,
            impacted_packs=impacted_packs,
        )
    
    def _find_reverse_dependencies(self, pack_name: str) -> List[str]:
        """
        Find all packs that depend on the given pack via pack_dependencies.

        Returns:
            List of pack names that have pack_name in their pack_dependencies.
        """
        reverse_deps = []
        for other_name in self.layout.list_packs():
            if other_name == pack_name:
                continue
            try:
                other_pack = self.layout.load_pack(other_name)
                dep_names = [ref.pack_name for ref in other_pack.pack_dependencies]
                if pack_name in dep_names:
                    reverse_deps.append(other_name)
            except Exception:
                continue
        return sorted(reverse_deps)

    def _check_dependency_update(
        self,
        dep: Any,
        current: ResolvedDependency,
    ) -> Optional[Dict[str, Any]]:
        """
        Check if a dependency has an update available.
        
        Returns:
            Dict with update info or None if no update
        """
        if not dep.selector.civitai:
            return None
        
        model_id = dep.selector.civitai.model_id
        
        # Get latest version from Civitai
        model_data = self.civitai.get_model(model_id)
        versions = model_data.get("modelVersions", [])
        if not versions:
            return None
        
        latest = versions[0]
        latest_version_id = latest["id"]
        
        # Check if we're already on latest version
        current_version_id = current.artifact.provider.version_id
        if current_version_id == latest_version_id:
            return {"has_update": False}
        
        # Find suitable files in latest version
        files = latest.get("files", [])
        candidates = self._filter_files(files, dep.selector.constraints)
        
        if not candidates:
            return None
        
        if len(candidates) > 1:
            # Ambiguous selection needed
            return {
                "ambiguous": True,
                "candidates": [
                    UpdateCandidate(
                        provider="civitai",
                        provider_model_id=model_id,
                        provider_version_id=latest_version_id,
                        provider_file_id=f.get("id"),
                        sha256=f.get("hashes", {}).get("SHA256", "").lower() if f.get("hashes") else None,
                    )
                    for f in candidates
                ],
            }
        
        # Single candidate - update available
        target = candidates[0]
        hashes = target.get("hashes", {})
        sha256 = hashes.get("SHA256", "").lower() if hashes else None
        
        return {
            "has_update": True,
            "ambiguous": False,
            "model_id": model_id,
            "version_id": latest_version_id,
            "file_id": target.get("id"),
            "sha256": sha256,
            "download_url": target.get("downloadUrl") or f"https://civitai.com/api/download/models/{latest_version_id}",
            "size_bytes": target.get("sizeKB", 0) * 1024 if target.get("sizeKB") else None,
        }
    
    def _filter_files(
        self,
        files: List[Dict[str, Any]],
        constraints: Optional[Any],
    ) -> List[Dict[str, Any]]:
        """Filter files based on constraints."""
        if not files:
            return []
        
        candidates = files.copy()
        
        if constraints:
            # Filter by primary file
            if constraints.primary_file_only:
                primary = [f for f in candidates if f.get("primary")]
                if primary:
                    candidates = primary
            
            # Filter by extension
            if constraints.file_ext:
                ext_filtered = [
                    f for f in candidates
                    if any(f.get("name", "").endswith(ext) for ext in constraints.file_ext)
                ]
                if ext_filtered:
                    candidates = ext_filtered
        
        return candidates
    
    # =========================================================================
    # Update Application
    # =========================================================================
    
    def apply_update(
        self,
        pack_name: str,
        plan: UpdatePlan,
        choose: Optional[Dict[str, int]] = None,
    ) -> PackLock:
        """
        Apply an update plan to a pack.
        
        Args:
            pack_name: Pack to update
            plan: Update plan from plan_update()
            choose: Optional dict mapping dep_id -> file_id for ambiguous selections
        
        Returns:
            Updated PackLock
        
        Raises:
            AmbiguousSelectionError: If plan has ambiguous entries without choose
        """
        # Check for unresolved ambiguous
        if plan.ambiguous:
            unresolved = []
            for amb in plan.ambiguous:
                if choose is None or amb.dependency_id not in choose:
                    unresolved.append(amb)
            
            if unresolved:
                raise AmbiguousSelectionError(pack_name, unresolved)
        
        # Load current lock
        lock = self.layout.load_pack_lock(pack_name)
        if not lock:
            raise UpdateError(f"No lock file for pack: {pack_name}")
        
        # Apply changes
        for change in plan.changes:
            dep_id = change.dependency_id
            new_data = change.new
            
            # Find and update resolved entry
            for i, resolved in enumerate(lock.resolved):
                if resolved.dependency_id == dep_id:
                    download_url = f"https://civitai.com/api/download/models/{new_data['provider_version_id']}"
                    
                    lock.resolved[i] = ResolvedDependency(
                        dependency_id=dep_id,
                        artifact=ResolvedArtifact(
                            kind=resolved.artifact.kind,
                            sha256=new_data.get("sha256"),
                            size_bytes=resolved.artifact.size_bytes,  # Will be updated on download
                            provider=ArtifactProvider(
                                name=ProviderName.CIVITAI,
                                model_id=new_data.get("provider_model_id"),
                                version_id=new_data.get("provider_version_id"),
                                file_id=new_data.get("provider_file_id"),
                            ),
                            download=ArtifactDownload(urls=[download_url]),
                            integrity=ArtifactIntegrity(sha256_verified=new_data.get("sha256") is not None),
                        ),
                    )
                    break
        
        # Apply ambiguous selections
        if choose:
            pack = self.layout.load_pack(pack_name)
            for amb in plan.ambiguous:
                if amb.dependency_id in choose:
                    file_id = choose[amb.dependency_id]
                    
                    # Find the selected candidate
                    selected = None
                    for cand in amb.candidates:
                        if cand.provider_file_id == file_id:
                            selected = cand
                            break
                    
                    if selected:
                        # Find and update resolved entry
                        dep = pack.get_dependency(amb.dependency_id)
                        for i, resolved in enumerate(lock.resolved):
                            if resolved.dependency_id == amb.dependency_id:
                                download_url = f"https://civitai.com/api/download/models/{selected.provider_version_id}"
                                
                                lock.resolved[i] = ResolvedDependency(
                                    dependency_id=amb.dependency_id,
                                    artifact=ResolvedArtifact(
                                        kind=dep.kind if dep else resolved.artifact.kind,
                                        sha256=selected.sha256,
                                        size_bytes=None,
                                        provider=ArtifactProvider(
                                            name=ProviderName.CIVITAI,
                                            model_id=selected.provider_model_id,
                                            version_id=selected.provider_version_id,
                                            file_id=selected.provider_file_id,
                                        ),
                                        download=ArtifactDownload(urls=[download_url]),
                                        integrity=ArtifactIntegrity(sha256_verified=selected.sha256 is not None),
                                    ),
                                )
                                break
        
        # Update timestamp
        lock.resolved_at = datetime.now().isoformat()
        
        # Save updated lock
        self.layout.save_pack_lock(lock)
        
        return lock
    
    # =========================================================================
    # High-Level Update Command
    # =========================================================================
    
    def update_pack(
        self,
        pack_name: str,
        dry_run: bool = False,
        choose: Optional[Dict[str, int]] = None,
        sync: bool = False,
        ui_targets: Optional[List[str]] = None,
    ) -> UpdateResult:
        """
        High-level update command.
        
        Args:
            pack_name: Pack to update
            dry_run: If True, only plan without applying
            choose: Optional file selections for ambiguous updates
            sync: If True, download new blobs and rebuild views
            ui_targets: UI targets for sync (required if sync=True)
        
        Returns:
            UpdateResult with details
        """
        # Create plan
        plan = self.plan_update(pack_name)
        
        if plan.already_up_to_date:
            return UpdateResult(
                pack=pack_name,
                applied=False,
                lock_updated=False,
                synced=False,
                ui_targets=[],
                already_up_to_date=True,
            )
        
        if dry_run:
            # Return plan as result
            return UpdateResult(
                pack=pack_name,
                applied=False,
                lock_updated=False,
                synced=False,
                ui_targets=[],
                already_up_to_date=False,
            )
        
        # Apply update
        lock = self.apply_update(pack_name, plan, choose)
        
        result = UpdateResult(
            pack=pack_name,
            applied=True,
            lock_updated=True,
            synced=False,
            ui_targets=ui_targets or [],
        )
        
        # Sync if requested
        if sync and ui_targets:
            result.synced = self._sync_after_update(pack_name, lock, ui_targets)
        
        return result
    
    def _sync_after_update(
        self,
        pack_name: str,
        lock: PackLock,
        ui_targets: List[str],
    ) -> bool:
        """Download new blobs and rebuild views after update."""
        try:
            # Download new blobs
            for resolved in lock.resolved:
                sha256 = resolved.artifact.sha256
                urls = resolved.artifact.download.urls
                
                if sha256 and not self.blob_store.blob_exists(sha256) and urls:
                    try:
                        self.blob_store.download(urls[0], sha256)
                    except Exception:
                        pass
            
            # Rebuild views for each UI
            # Need to determine which profile to rebuild
            runtime = self.layout.load_runtime()
            
            for ui in ui_targets:
                active_profile = runtime.get_active_profile(ui)
                if active_profile:
                    try:
                        profile = self.layout.load_profile(active_profile)
                        # Load packs for profile
                        packs_data = {}
                        for p in profile.packs:
                            try:
                                pack = self.layout.load_pack(p.name)
                                pack_lock = self.layout.load_pack_lock(p.name)
                                packs_data[p.name] = (pack, pack_lock)
                            except Exception:
                                continue
                        
                        self.view_builder.build(ui, profile, packs_data)
                        self.view_builder.activate(ui, active_profile)
                    except Exception:
                        pass
            
            return True
        except Exception:
            return False
    
    # =========================================================================
    # Batch Operations
    # =========================================================================
    
    def check_all_updates(self) -> Dict[str, UpdatePlan]:
        """
        Check for updates on all packs.
        
        Returns:
            Dict mapping pack_name -> UpdatePlan
        """
        plans = {}
        
        for pack_name in self.layout.list_packs():
            try:
                pack = self.layout.load_pack(pack_name)
                if self.is_updatable(pack):
                    plans[pack_name] = self.plan_update(pack_name)
            except Exception:
                pass
        
        return plans
    
    def get_updatable_packs(self) -> List[str]:
        """
        Get list of packs that have updates available.
        
        Returns:
            List of pack names with available updates
        """
        updatable = []
        
        plans = self.check_all_updates()
        for pack_name, plan in plans.items():
            if not plan.already_up_to_date:
                updatable.append(pack_name)
        
        return updatable
