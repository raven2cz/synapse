"""
Synapse Store v2 - View Builder

Builds and manages view directories for different UIs.

Views are symlink trees that point into the blob store:
- data/views/<ui>/profiles/<profile>/<kind_path>/<filename> -> blob

Features:
- Multi-UI support (ComfyUI, Forge, A1111, SD.Next)
- Profile-based views
- Atomic builds (build to staging, then replace)
- Active profile symlinks
- Last-wins conflict resolution
- Shadowed file tracking
"""

from __future__ import annotations

import os
import platform
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .blob_store import BlobStore
from .layout import StoreLayout, StoreError
from .models import (
    AssetKind,
    ConflictMode,
    Pack,
    PackLock,
    Profile,
    ShadowedEntry,
    StoreConfig,
    UIKindMap,
)


class ViewBuildError(StoreError):
    """Error during view building."""
    pass


class SymlinkError(ViewBuildError):
    """Error creating symlink."""
    pass


@dataclass
class ViewEntry:
    """A single entry in a view plan."""
    pack_name: str
    dependency_id: str
    kind: AssetKind
    expose_filename: str
    sha256: str
    dst_relpath: str  # Relative path within the view


@dataclass
class ViewPlan:
    """Plan for building a view."""
    ui: str
    profile: str
    entries: List[ViewEntry] = field(default_factory=list)
    shadowed: List[ShadowedEntry] = field(default_factory=list)
    missing_blobs: List[Tuple[str, str, str]] = field(default_factory=list)  # (pack, dep_id, sha256)
    
    def add_entry(
        self,
        pack_name: str,
        dependency_id: str,
        kind: AssetKind,
        expose_filename: str,
        sha256: str,
        kind_map: UIKindMap,
    ) -> Optional[ShadowedEntry]:
        """
        Add an entry to the plan.
        
        Returns ShadowedEntry if this entry shadows an existing one.
        """
        kind_path = kind_map.get_path(kind)
        if not kind_path:
            kind_path = f"models/{kind.value}"
        
        dst_relpath = f"{kind_path}/{expose_filename}"
        
        # Check for existing entry with same destination
        for i, existing in enumerate(self.entries):
            if existing.dst_relpath == dst_relpath:
                # Shadow the existing entry
                shadowed = ShadowedEntry(
                    ui=self.ui,
                    dst_relpath=dst_relpath,
                    winner_pack=pack_name,
                    loser_pack=existing.pack_name,
                )
                self.shadowed.append(shadowed)
                
                # Replace with new entry
                self.entries[i] = ViewEntry(
                    pack_name=pack_name,
                    dependency_id=dependency_id,
                    kind=kind,
                    expose_filename=expose_filename,
                    sha256=sha256,
                    dst_relpath=dst_relpath,
                )
                return shadowed
        
        # No conflict, add new entry
        self.entries.append(ViewEntry(
            pack_name=pack_name,
            dependency_id=dependency_id,
            kind=kind,
            expose_filename=expose_filename,
            sha256=sha256,
            dst_relpath=dst_relpath,
        ))
        return None


@dataclass
class BuildReport:
    """Report from a view build operation."""
    ui: str
    profile: str
    entries_created: int
    shadowed: List[ShadowedEntry] = field(default_factory=list)
    missing_blobs: List[Tuple[str, str, str]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


def create_symlink(source: Path, target: Path) -> None:
    """
    Create a symlink, handling platform differences.
    
    On Windows, attempts symlink first, then hardlink, then copy.
    On Linux/Mac, uses symlink.
    
    Args:
        source: The symlink to create
        target: What the symlink should point to
    """
    source.parent.mkdir(parents=True, exist_ok=True)
    
    # Remove existing if present
    if source.exists() or source.is_symlink():
        source.unlink()
    
    if platform.system() == "Windows":
        # Try symlink first (requires Developer Mode or admin)
        try:
            source.symlink_to(target)
            return
        except OSError:
            pass
        
        # Try hardlink (works without admin, but same filesystem only)
        try:
            os.link(target, source)
            return
        except OSError:
            pass
        
        # Fall back to copy (worst case)
        shutil.copy2(target, source)
    else:
        # Linux/Mac - symlinks work normally
        source.symlink_to(target)


class ViewBuilder:
    """
    Builds and manages view directories.
    
    Views are symlink trees for each UI that point into the blob store.
    """
    
    def __init__(
        self,
        layout: StoreLayout,
        blob_store: BlobStore,
        config: Optional[StoreConfig] = None,
    ):
        """
        Initialize view builder.
        
        Args:
            layout: Store layout manager
            blob_store: Blob store for resolving paths
            config: Store configuration (loaded from layout if not provided)
        """
        self.layout = layout
        self.blob_store = blob_store
        self._config = config
    
    @property
    def config(self) -> StoreConfig:
        """Get store configuration, loading if necessary."""
        if self._config is None:
            self._config = self.layout.load_config()
        return self._config
    
    # =========================================================================
    # Plan Building
    # =========================================================================
    
    def compute_plan(
        self,
        ui: str,
        profile: Profile,
        packs: Dict[str, Tuple[Pack, Optional[PackLock]]],
    ) -> ViewPlan:
        """
        Compute a view plan for a UI and profile.
        
        Args:
            ui: UI name (e.g., "comfyui")
            profile: Profile to build
            packs: Dict mapping pack_name -> (pack, lock)
        
        Returns:
            ViewPlan with entries and shadowed info
        """
        plan = ViewPlan(ui=ui, profile=profile.name)
        
        # Get kind map for this UI
        kind_map = self.config.ui.kind_map.get(ui)
        if not kind_map:
            kind_map = UIKindMap()  # Use defaults
        
        # Process packs in order (last wins)
        for pack_entry in profile.packs:
            pack_name = pack_entry.name
            if pack_name not in packs:
                continue
            
            pack, lock = packs[pack_name]
            if lock is None:
                continue
            
            # Process each resolved dependency
            for resolved in lock.resolved:
                # Find the dependency definition in pack
                dep = pack.get_dependency(resolved.dependency_id)
                if dep is None:
                    continue
                
                sha256 = resolved.artifact.sha256
                if not sha256:
                    continue
                
                # Check if blob exists
                if not self.blob_store.blob_exists(sha256):
                    plan.missing_blobs.append((pack_name, dep.id, sha256))
                    continue
                
                # Add to plan (handles shadowing)
                plan.add_entry(
                    pack_name=pack_name,
                    dependency_id=dep.id,
                    kind=dep.kind,
                    expose_filename=dep.expose.filename,
                    sha256=sha256,
                    kind_map=kind_map,
                )
        
        return plan
    
    # =========================================================================
    # View Building
    # =========================================================================
    
    def build(
        self,
        ui: str,
        profile: Profile,
        packs: Dict[str, Tuple[Pack, Optional[PackLock]]],
    ) -> BuildReport:
        """
        Build view for a UI and profile.
        
        Uses atomic build: creates in staging directory, then replaces.
        
        Args:
            ui: UI name
            profile: Profile to build
            packs: Dict mapping pack_name -> (pack, lock)
        
        Returns:
            BuildReport with results
        """
        # Compute plan
        plan = self.compute_plan(ui, profile, packs)
        
        report = BuildReport(
            ui=ui,
            profile=profile.name,
            entries_created=0,
            shadowed=plan.shadowed,
            missing_blobs=plan.missing_blobs,
        )
        
        # Build in staging directory
        staging_dir = self.layout.tmp_path / "views" / ui / f"{profile.name}.new"
        final_dir = self.layout.view_profile_path(ui, profile.name)
        
        # Clean staging
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
        staging_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Create symlinks
            for entry in plan.entries:
                blob_path = self.blob_store.blob_path(entry.sha256)
                link_path = staging_dir / entry.dst_relpath
                
                try:
                    create_symlink(link_path, blob_path)
                    report.entries_created += 1
                except Exception as e:
                    report.errors.append(f"Failed to create link {entry.dst_relpath}: {e}")
            
            # Atomic replace
            if final_dir.exists():
                # Move old to backup, then replace
                backup_dir = final_dir.with_suffix(".old")
                if backup_dir.exists():
                    shutil.rmtree(backup_dir)
                final_dir.rename(backup_dir)
                staging_dir.rename(final_dir)
                shutil.rmtree(backup_dir)
            else:
                final_dir.parent.mkdir(parents=True, exist_ok=True)
                staging_dir.rename(final_dir)
            
        except Exception as e:
            report.errors.append(f"Failed to finalize build: {e}")
            # Clean up staging
            if staging_dir.exists():
                shutil.rmtree(staging_dir)
        
        return report
    
    def build_for_ui_set(
        self,
        ui_set_name: str,
        profile: Profile,
        packs: Dict[str, Tuple[Pack, Optional[PackLock]]],
    ) -> Dict[str, BuildReport]:
        """
        Build views for all UIs in a set.
        
        Returns:
            Dict mapping ui_name -> BuildReport
        """
        ui_sets = self.layout.load_ui_sets()
        ui_names = ui_sets.sets.get(ui_set_name, [])
        
        reports = {}
        for ui in ui_names:
            reports[ui] = self.build(ui, profile, packs)
        
        return reports
    
    # =========================================================================
    # Activation
    # =========================================================================
    
    def activate(self, ui: str, profile_name: str) -> None:
        """
        Activate a profile for a UI by updating the 'active' symlink.
        
        Args:
            ui: UI name
            profile_name: Profile to activate
        """
        active_path = self.layout.view_active_path(ui)
        profile_path = self.layout.view_profile_path(ui, profile_name)
        
        # Ensure profile view exists
        if not profile_path.exists():
            raise ViewBuildError(f"Profile view not found: {ui}/{profile_name}")
        
        # Create active symlink pointing to profile
        # Use relative path for portability
        active_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Atomic update: create .new, then replace
        active_new = active_path.with_suffix(".new")
        try:
            # Remove if exists
            if active_new.exists() or active_new.is_symlink():
                active_new.unlink()
            
            # Create relative symlink
            rel_target = Path("profiles") / profile_name
            active_new.symlink_to(rel_target)
            
            # Atomic replace
            active_new.replace(active_path)
        except Exception as e:
            active_new.unlink(missing_ok=True)
            raise ViewBuildError(f"Failed to activate profile: {e}") from e
    
    def activate_for_ui_set(self, ui_set_name: str, profile_name: str) -> List[str]:
        """
        Activate a profile for all UIs in a set.
        
        Returns:
            List of UI names that were activated
        """
        ui_sets = self.layout.load_ui_sets()
        ui_names = ui_sets.sets.get(ui_set_name, [])
        
        activated = []
        for ui in ui_names:
            try:
                self.activate(ui, profile_name)
                activated.append(ui)
            except ViewBuildError:
                pass  # Profile may not be built for this UI yet
        
        return activated
    
    def get_active_profile(self, ui: str) -> Optional[str]:
        """
        Get the currently active profile for a UI.
        
        Returns:
            Profile name, or None if no active profile
        """
        active_path = self.layout.view_active_path(ui)
        if not active_path.is_symlink():
            return None
        
        # Read the symlink target
        target = os.readlink(active_path)
        # Extract profile name from "profiles/<name>"
        parts = Path(target).parts
        if len(parts) >= 2 and parts[0] == "profiles":
            return parts[1]
        return None
    
    # =========================================================================
    # Cleanup
    # =========================================================================
    
    def remove_profile_view(self, ui: str, profile_name: str) -> bool:
        """
        Remove a profile view.
        
        Returns:
            True if removed, False if didn't exist
        """
        profile_path = self.layout.view_profile_path(ui, profile_name)
        if profile_path.exists():
            shutil.rmtree(profile_path)
            return True
        return False
    
    def clean_orphaned_views(self, ui: str) -> List[str]:
        """
        Remove views for profiles that no longer exist.
        
        Returns:
            List of removed profile names
        """
        profiles_path = self.layout.view_profiles_path(ui)
        if not profiles_path.exists():
            return []
        
        existing_profiles = set(self.layout.list_profiles())
        removed = []
        
        for profile_dir in profiles_path.iterdir():
            if profile_dir.is_dir() and profile_dir.name not in existing_profiles:
                shutil.rmtree(profile_dir)
                removed.append(profile_dir.name)
        
        return removed
    
    # =========================================================================
    # Status
    # =========================================================================
    
    def list_view_profiles(self, ui: str) -> List[str]:
        """List all built profile views for a UI."""
        profiles_path = self.layout.view_profiles_path(ui)
        if not profiles_path.exists():
            return []
        return [d.name for d in profiles_path.iterdir() if d.is_dir()]
    
    def get_view_entries(self, ui: str, profile_name: str) -> List[ViewEntry]:
        """
        Get all entries in a view.
        
        Note: This reads the filesystem, not a plan.
        """
        profile_path = self.layout.view_profile_path(ui, profile_name)
        if not profile_path.exists():
            return []
        
        entries = []
        for root, dirs, files in os.walk(profile_path):
            for name in files:
                link_path = Path(root) / name
                if link_path.is_symlink():
                    target = link_path.resolve()
                    # Extract sha256 from blob path
                    sha256 = target.name if target.parent.parent.name == "sha256" else ""
                    rel_path = link_path.relative_to(profile_path)
                    entries.append(ViewEntry(
                        pack_name="",  # Unknown from filesystem
                        dependency_id="",  # Unknown from filesystem
                        kind=AssetKind.UNKNOWN,
                        expose_filename=name,
                        sha256=sha256,
                        dst_relpath=str(rel_path),
                    ))
        
        return entries
