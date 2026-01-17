"""
Synapse Store v2 - Profile Service

Manages profiles and the use/back workflow.

Profiles:
- global: Default profile with all packs
- work__<Pack>: Work profile for focused pack work

Workflow:
- use <pack>: Create work__<pack> profile, push to stack, activate
- back: Pop stack, activate previous profile
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .blob_store import BlobStore
from .layout import StoreLayout, ProfileNotFoundError
from .models import (
    BackResult,
    Pack,
    PackLock,
    Profile,
    ProfilePackEntry,
    Runtime,
    ShadowedEntry,
    StoreConfig,
    UISets,
    UseResult,
)
from .view_builder import BuildReport, ViewBuilder


class ProfileService:
    """
    Service for managing profiles and use/back workflow.
    """
    
    WORK_PREFIX = "work__"
    
    def __init__(
        self,
        layout: StoreLayout,
        blob_store: BlobStore,
        view_builder: ViewBuilder,
    ):
        """
        Initialize profile service.
        
        Args:
            layout: Store layout manager
            blob_store: Blob store
            view_builder: View builder
        """
        self.layout = layout
        self.blob_store = blob_store
        self.view_builder = view_builder
    
    # =========================================================================
    # Profile Loading
    # =========================================================================
    
    def load_profile(self, profile_name: str) -> Profile:
        """Load a profile by name."""
        return self.layout.load_profile(profile_name)
    
    def load_global(self) -> Profile:
        """Load the global profile."""
        return self.load_profile("global")
    
    def get_work_profile_name(self, pack_name: str) -> str:
        """Get the work profile name for a pack."""
        return f"{self.WORK_PREFIX}{pack_name}"
    
    def is_work_profile(self, profile_name: str) -> bool:
        """Check if a profile is a work profile."""
        return profile_name.startswith(self.WORK_PREFIX)
    
    def get_pack_from_work_profile(self, profile_name: str) -> Optional[str]:
        """Extract pack name from work profile name."""
        if self.is_work_profile(profile_name):
            return profile_name[len(self.WORK_PREFIX):]
        return None
    
    # =========================================================================
    # Work Profile Management
    # =========================================================================
    
    def ensure_work_profile(
        self,
        pack_name: str,
        base_profile_name: str = "global",
    ) -> Tuple[Profile, bool]:
        """
        Ensure a work profile exists for a pack.
        
        Creates work__<pack> profile based on base profile, with pack moved to end.
        
        Args:
            pack_name: Pack to create work profile for
            base_profile_name: Base profile to copy from (default: global)
        
        Returns:
            Tuple of (profile, created) where created is True if newly created
        """
        work_name = self.get_work_profile_name(pack_name)
        
        # Check if work profile already exists
        if self.layout.profile_exists(work_name):
            return self.layout.load_profile(work_name), False
        
        # Load base profile
        base = self.layout.load_profile(base_profile_name)
        
        # Create work profile with pack at end
        work = Profile(
            name=work_name,
            conflicts=base.conflicts,
            packs=[],
        )
        
        # Copy packs, excluding the target pack
        for p in base.packs:
            if p.name != pack_name:
                work.packs.append(ProfilePackEntry(name=p.name))
        
        # Add target pack at end (last wins)
        work.packs.append(ProfilePackEntry(name=pack_name))
        
        # Save work profile
        self.layout.save_profile(work)
        
        return work, True
    
    def update_work_profile(
        self,
        pack_name: str,
        base_profile_name: str = "global",
    ) -> Profile:
        """
        Update or create a work profile to reflect current base profile.
        
        Always regenerates from base to ensure consistency.
        """
        work_name = self.get_work_profile_name(pack_name)
        base = self.layout.load_profile(base_profile_name)
        
        work = Profile(
            name=work_name,
            conflicts=base.conflicts,
            packs=[],
        )
        
        # Copy packs, excluding the target pack
        for p in base.packs:
            if p.name != pack_name:
                work.packs.append(ProfilePackEntry(name=p.name))
        
        # Add target pack at end
        work.packs.append(ProfilePackEntry(name=pack_name))
        
        self.layout.save_profile(work)
        return work
    
    # =========================================================================
    # Use Command
    # =========================================================================
    
    def use(
        self,
        pack_name: str,
        ui_targets: List[str],
        base_profile: str = "global",
        sync: bool = True,
    ) -> UseResult:
        """
        Execute 'use' command for a pack.
        
        1. Ensure pack exists
        2. Create/update work profile
        3. Build views for target UIs
        4. Activate work profile
        5. Push to runtime stack
        
        Args:
            pack_name: Pack to use
            ui_targets: List of UI names to target
            base_profile: Base profile for work profile
            sync: If True, build views
        
        Returns:
            UseResult with details
        """
        # Verify pack exists
        if not self.layout.pack_exists(pack_name):
            raise ProfileNotFoundError(f"Pack not found: {pack_name}")
        
        # Create/update work profile
        work_profile, created = self.ensure_work_profile(pack_name, base_profile)
        if not created:
            # Update to reflect any changes in base
            work_profile = self.update_work_profile(pack_name, base_profile)
        
        result = UseResult(
            pack=pack_name,
            created_profile=work_profile.name,
            ui_targets=ui_targets,
            activated_profile=work_profile.name,
            synced=sync,
            shadowed=[],
            notes=[],
        )
        
        if created:
            result.notes.append("profile_created")
        else:
            result.notes.append("profile_updated")
        
        # Load packs data for building
        if sync:
            packs_data = self._load_packs_for_profile(work_profile)
            
            # Build and activate for each UI
            for ui in ui_targets:
                report = self.view_builder.build(ui, work_profile, packs_data)
                result.shadowed.extend(report.shadowed)
                
                # Activate
                self.view_builder.activate(ui, work_profile.name)
        
        # Update runtime stack
        runtime = self.layout.load_runtime()
        for ui in ui_targets:
            runtime.push_profile(ui, work_profile.name)
        self.layout.save_runtime(runtime)
        
        return result
    
    def use_from_ui_set(
        self,
        pack_name: str,
        ui_set_name: str,
        base_profile: str = "global",
        sync: bool = True,
    ) -> UseResult:
        """
        Execute 'use' command using a UI set.
        """
        ui_sets = self.layout.load_ui_sets()
        ui_targets = ui_sets.sets.get(ui_set_name, [])
        return self.use(pack_name, ui_targets, base_profile, sync)
    
    # =========================================================================
    # Back Command
    # =========================================================================
    
    def back(
        self,
        ui_targets: List[str],
        sync: bool = False,
    ) -> BackResult:
        """
        Execute 'back' command.
        
        1. Pop current profile from stack
        2. Activate previous profile
        
        Args:
            ui_targets: List of UI names to target
            sync: If True, rebuild views
        
        Returns:
            BackResult with details
        """
        runtime = self.layout.load_runtime()
        
        # Determine from/to profiles (use first UI as reference)
        if not ui_targets:
            return BackResult(
                ui_targets=[],
                from_profile="",
                to_profile="",
                synced=False,
                notes=["no_ui_targets"],
            )
        
        first_ui = ui_targets[0]
        from_profile = runtime.get_active_profile(first_ui)
        
        # Pop from all target UIs
        for ui in ui_targets:
            runtime.pop_profile(ui)
        
        to_profile = runtime.get_active_profile(first_ui)
        
        result = BackResult(
            ui_targets=ui_targets,
            from_profile=from_profile,
            to_profile=to_profile,
            synced=sync,
            notes=[],
        )
        
        # Check if already at base
        if from_profile == to_profile:
            result.notes.append("already_at_base")
        
        # Rebuild and activate if syncing
        if sync and to_profile:
            try:
                profile = self.layout.load_profile(to_profile)
                packs_data = self._load_packs_for_profile(profile)
                
                for ui in ui_targets:
                    self.view_builder.build(ui, profile, packs_data)
                    self.view_builder.activate(ui, to_profile)
            except ProfileNotFoundError:
                result.notes.append("profile_not_found")
        else:
            # Just activate without rebuilding
            for ui in ui_targets:
                try:
                    self.view_builder.activate(ui, to_profile)
                except Exception:
                    pass  # View may not exist
        
        # Save runtime
        self.layout.save_runtime(runtime)
        
        return result
    
    def back_from_ui_set(
        self,
        ui_set_name: str,
        sync: bool = False,
    ) -> BackResult:
        """
        Execute 'back' command using a UI set.
        """
        ui_sets = self.layout.load_ui_sets()
        ui_targets = ui_sets.sets.get(ui_set_name, [])
        return self.back(ui_targets, sync)
    
    # =========================================================================
    # Sync Operations
    # =========================================================================
    
    def sync_profile(
        self,
        profile_name: str,
        ui_targets: List[str],
        install_missing: bool = True,
    ) -> Dict[str, BuildReport]:
        """
        Sync a profile: install missing blobs and build views.
        
        Args:
            profile_name: Profile to sync
            ui_targets: List of UI names
            install_missing: If True, download missing blobs
        
        Returns:
            Dict mapping ui -> BuildReport
        """
        profile = self.layout.load_profile(profile_name)
        packs_data = self._load_packs_for_profile(profile)
        
        # Install missing blobs if requested
        if install_missing:
            self._install_missing_blobs(packs_data)
        
        # Build views for each UI
        reports = {}
        for ui in ui_targets:
            reports[ui] = self.view_builder.build(ui, profile, packs_data)
            self.view_builder.activate(ui, profile_name)
        
        return reports
    
    def sync_profile_from_ui_set(
        self,
        profile_name: str,
        ui_set_name: str,
        install_missing: bool = True,
    ) -> Dict[str, BuildReport]:
        """
        Sync a profile using a UI set.
        """
        ui_sets = self.layout.load_ui_sets()
        ui_targets = ui_sets.sets.get(ui_set_name, [])
        return self.sync_profile(profile_name, ui_targets, install_missing)
    
    # =========================================================================
    # Global Profile Management
    # =========================================================================
    
    def add_pack_to_global(self, pack_name: str) -> Profile:
        """
        Add a pack to the global profile.
        
        Returns:
            Updated global profile
        """
        global_profile = self.load_global()
        global_profile.add_pack(pack_name)
        self.layout.save_profile(global_profile)
        return global_profile
    
    def remove_pack_from_global(self, pack_name: str) -> Profile:
        """
        Remove a pack from the global profile.
        
        Returns:
            Updated global profile
        """
        global_profile = self.load_global()
        global_profile.remove_pack(pack_name)
        self.layout.save_profile(global_profile)
        return global_profile
    
    # =========================================================================
    # Status
    # =========================================================================
    
    def get_active_profiles(self, ui_names: List[str]) -> Dict[str, str]:
        """
        Get active profile for each UI.
        
        Returns:
            Dict mapping ui_name -> profile_name
        """
        runtime = self.layout.load_runtime()
        return {ui: runtime.get_active_profile(ui) for ui in ui_names}
    
    def get_runtime_stacks(self, ui_names: List[str]) -> Dict[str, List[str]]:
        """
        Get runtime stacks for each UI.
        
        Returns:
            Dict mapping ui_name -> stack (list of profile names)
        """
        runtime = self.layout.load_runtime()
        return {
            ui: runtime.ui.get(ui, Runtime.create_default([ui]).ui[ui]).stack
            for ui in ui_names
        }
    
    # =========================================================================
    # Helpers
    # =========================================================================
    
    def _load_packs_for_profile(
        self,
        profile: Profile,
    ) -> Dict[str, Tuple[Pack, Optional[PackLock]]]:
        """
        Load all packs referenced by a profile.
        
        Returns:
            Dict mapping pack_name -> (pack, lock)
        """
        packs_data = {}
        for pack_entry in profile.packs:
            try:
                pack = self.layout.load_pack(pack_entry.name)
                lock = self.layout.load_pack_lock(pack_entry.name)
                packs_data[pack_entry.name] = (pack, lock)
            except Exception:
                continue
        return packs_data
    
    def _install_missing_blobs(
        self,
        packs_data: Dict[str, Tuple[Pack, Optional[PackLock]]],
    ) -> List[str]:
        """
        Install missing blobs for packs.
        
        Returns:
            List of installed blob SHA256 hashes
        """
        installed = []
        
        for pack_name, (pack, lock) in packs_data.items():
            if lock is None:
                continue
            
            for resolved in lock.resolved:
                sha256 = resolved.artifact.sha256
                if not sha256:
                    continue
                
                if self.blob_store.blob_exists(sha256):
                    continue
                
                # Download from first available URL
                urls = resolved.artifact.download.urls
                if urls:
                    try:
                        self.blob_store.download(urls[0], sha256)
                        installed.append(sha256)
                    except Exception:
                        pass  # Log error, continue
        
        return installed
