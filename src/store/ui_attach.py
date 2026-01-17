"""
Synapse Store v2 - UI Attach

Attaches the active view to UI installations.

Two strategies available:
1. SYMLINK (default for A1111/Forge/SD.Next):
   Creates "synapse" subdirectory symlink in UI's model folders.
   Example: Forge/models/Lora/synapse -> <store>/views/forge/active/models/Lora
   
2. EXTRA_MODEL_PATHS (preferred for ComfyUI):
   Generates extra_model_paths.yaml configuration that points directly
   to the view folders. This avoids subfolder issues with workflow paths.
   Example: extra_model_paths.yaml with "synapse: {loras: /path/to/view/models/loras}"

The extra_model_paths method is preferred for ComfyUI because it makes
models appear at root level (not in synapse/ subfolder), which is 
critical for Civitai generation data compatibility.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

from .models import UIConfig, UIKindMap, AssetKind, StoreConfig

logger = logging.getLogger(__name__)


@dataclass
class AttachResult:
    """Result of attaching UI to store views."""
    ui: str
    success: bool
    method: str  # "symlink", "extra_model_paths", "skipped", "detach"
    created: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    config_path: Optional[str] = None  # For extra_model_paths method


class UIAttacher:
    """
    Attaches Synapse store views to UI installations.
    
    For ComfyUI: Generates extra_model_paths.yaml (recommended)
    For A1111/Forge/SD.Next: Creates symlinks in model directories
    """
    
    def __init__(
        self,
        layout,  # StoreLayout
        ui_roots: Dict[str, Path],
        config: Optional[StoreConfig] = None,
    ):
        """
        Initialize UI attacher.
        
        Args:
            layout: Store layout instance
            ui_roots: Dict mapping ui_name -> installation path
            config: Store configuration (for UIKindMap). If None, uses defaults.
        """
        self.layout = layout
        self.ui_roots = {k: Path(v).expanduser() for k, v in ui_roots.items()}
        self._config = config
    
    def _get_kind_map(self, ui_name: str) -> UIKindMap:
        """Get UIKindMap for a UI (from config or defaults)."""
        if self._config and self._config.ui.kind_map:
            kind_map = self._config.ui.kind_map.get(ui_name)
            if kind_map:
                return kind_map
        
        # Fall back to defaults
        defaults = UIConfig.get_default_kind_maps()
        return defaults.get(ui_name, UIKindMap())
    
    def get_active_view_path(self, ui_name: str) -> Optional[Path]:
        """Get path to active view for a UI (resolved if symlink)."""
        active_path = self.layout.view_active_path(ui_name)
        if active_path.exists():
            # Resolve symlink to get actual path
            return active_path.resolve() if active_path.is_symlink() else active_path
        return None
    
    # =========================================================================
    # ComfyUI: extra_model_paths.yaml method (PREFERRED)
    # =========================================================================
    
    def generate_extra_model_paths_yaml(self, ui_name: str = "comfyui") -> Dict[str, Any]:
        """
        Generate extra_model_paths.yaml content for ComfyUI.
        
        This is the PREFERRED method for ComfyUI because it makes models
        appear at root level (not in subfolder), which is critical for
        Civitai generation data compatibility.
        
        Returns:
            Dict ready to be written as YAML
        """
        ui_name = ui_name.lower()
        active_view = self.get_active_view_path(ui_name)
        
        if active_view is None:
            return {}
        
        kind_map = self._get_kind_map(ui_name)
        
        # Build paths dict
        # ComfyUI extra_model_paths format:
        # synapse:
        #     base_path: /path/to/view
        #     checkpoints: models/checkpoints
        #     loras: models/loras
        #     ...
        
        paths = {}
        
        for kind in AssetKind:
            kind_path = kind_map.get_path(kind)
            if not kind_path:
                continue
            
            view_kind_path = active_view / kind_path
            if view_kind_path.exists():
                # Map kind to ComfyUI folder name
                comfy_name = self._kind_to_comfyui_name(kind)
                if comfy_name:
                    paths[comfy_name] = str(view_kind_path)
        
        if not paths:
            return {}
        
        return {
            "synapse": paths
        }
    
    def _kind_to_comfyui_name(self, kind: AssetKind) -> Optional[str]:
        """Map AssetKind to ComfyUI extra_model_paths key name."""
        mapping = {
            AssetKind.CHECKPOINT: "checkpoints",
            AssetKind.LORA: "loras",
            AssetKind.VAE: "vae",
            AssetKind.EMBEDDING: "embeddings",
            AssetKind.CONTROLNET: "controlnet",
            AssetKind.UPSCALER: "upscale_models",
            AssetKind.CLIP: "clip",
            AssetKind.TEXT_ENCODER: "text_encoders",
            AssetKind.DIFFUSION_MODEL: "diffusion_models",
            AssetKind.UNET: "unet",
        }
        return mapping.get(kind)
    
    def attach_comfyui_yaml(self, output_path: Optional[Path] = None) -> AttachResult:
        """
        Attach ComfyUI by patching extra_model_paths.yaml directly.
        
        This patches ComfyUI's extra_model_paths.yaml in place:
        1. Creates backup (once): extra_model_paths.yaml.synapse.bak
        2. Adds/updates 'synapse:' section with paths to active view
        3. Preserves all other content in the file
        
        Args:
            output_path: Path to extra_model_paths.yaml. If None, uses comfyui_root/extra_model_paths.yaml
        
        Returns:
            AttachResult with config_path set
        """
        result = AttachResult(ui="comfyui", success=True, method="extra_model_paths")
        
        # Get ComfyUI root
        comfyui_root = self.ui_roots.get("comfyui")
        if comfyui_root is None:
            result.success = False
            result.errors.append("No ComfyUI root configured")
            return result
        
        if not comfyui_root.exists():
            result.success = False
            result.errors.append(f"ComfyUI root does not exist: {comfyui_root}")
            return result
        
        # Target file path
        if output_path is None:
            output_path = comfyui_root / "extra_model_paths.yaml"
        
        backup_path = output_path.parent / f"{output_path.name}.synapse.bak"
        
        # Generate synapse section content
        synapse_content = self.generate_extra_model_paths_yaml("comfyui")
        
        if not synapse_content:
            result.success = False
            result.errors.append("No active view or no models to attach")
            return result
        
        try:
            # Load existing content or start fresh
            existing_content = {}
            if output_path.exists():
                # Create backup ONLY if it doesn't exist yet (preserve original)
                if not backup_path.exists():
                    import shutil
                    shutil.copy2(output_path, backup_path)
                    result.created.append(f"Backup: {backup_path}")
                    logger.info(f"[comfyui] Created backup: {backup_path}")
                
                # Load existing YAML
                with open(output_path, "r") as f:
                    content = f.read()
                    if content.strip():
                        existing_content = yaml.safe_load(content) or {}
            
            # Merge: update synapse section, preserve everything else
            existing_content["synapse"] = synapse_content["synapse"]
            
            # Write back
            with open(output_path, "w") as f:
                yaml.dump(existing_content, f, default_flow_style=False, sort_keys=False)
            
            result.config_path = str(output_path)
            result.created.append(f"Updated: {output_path}")
            logger.info(f"[comfyui] Patched extra_model_paths.yaml with synapse section")
            
        except Exception as e:
            result.success = False
            result.errors.append(f"Failed to patch YAML: {e}")
            logger.error(f"[comfyui] Failed to patch: {e}")
        
        return result
    
    def detach_comfyui_yaml(self) -> AttachResult:
        """
        Detach ComfyUI by restoring original extra_model_paths.yaml from backup.
        
        Returns:
            AttachResult
        """
        result = AttachResult(ui="comfyui", success=True, method="detach")
        
        comfyui_root = self.ui_roots.get("comfyui")
        if comfyui_root is None:
            return result  # Nothing to detach
        
        yaml_path = comfyui_root / "extra_model_paths.yaml"
        backup_path = yaml_path.parent / f"{yaml_path.name}.synapse.bak"
        
        try:
            if backup_path.exists():
                # Restore from backup (byte-identical)
                import shutil
                shutil.copy2(backup_path, yaml_path)
                backup_path.unlink()
                result.created.append(f"Restored: {yaml_path}")
                logger.info(f"[comfyui] Restored original extra_model_paths.yaml from backup")
            elif yaml_path.exists():
                # No backup but file exists - just remove synapse section
                with open(yaml_path, "r") as f:
                    content = yaml.safe_load(f) or {}
                
                if "synapse" in content:
                    del content["synapse"]
                    
                    with open(yaml_path, "w") as f:
                        if content:
                            yaml.dump(content, f, default_flow_style=False, sort_keys=False)
                        # If empty, just leave empty file
                    
                    result.created.append(f"Removed synapse section from: {yaml_path}")
                    logger.info(f"[comfyui] Removed synapse section (no backup found)")
        except Exception as e:
            result.errors.append(f"Failed to restore: {e}")
            logger.error(f"[comfyui] Detach failed: {e}")
        
        return result
    
    # =========================================================================
    # Symlink method (for A1111/Forge/SD.Next)
    # =========================================================================
    
    def attach(self, ui_name: str, use_yaml: bool = False) -> AttachResult:
        """
        Attach a UI to its Synapse view.
        
        For ComfyUI with use_yaml=True: Uses extra_model_paths.yaml method
        For others: Creates per-kind symlinks: UI/<kind_path>/synapse -> view/active/<kind_path>
        
        Args:
            ui_name: Name of UI (comfyui, forge, a1111, sdnext)
            use_yaml: For ComfyUI, use extra_model_paths.yaml instead of symlinks
        
        Returns:
            AttachResult with status and created symlinks
        """
        ui_name = ui_name.lower()
        
        # For ComfyUI with yaml option
        if ui_name == "comfyui" and use_yaml:
            return self.attach_comfyui_yaml()
        
        result = AttachResult(ui=ui_name, success=True, method="symlink")
        
        # Get UI root
        ui_root = self.ui_roots.get(ui_name)
        if ui_root is None:
            result.success = False
            result.method = "skipped"
            result.errors.append(f"No root configured for {ui_name}")
            return result
        
        if not ui_root.exists():
            result.success = False
            result.method = "skipped"
            result.errors.append(f"UI root does not exist: {ui_root}")
            return result
        
        # Get active view path
        active_view = self.get_active_view_path(ui_name)
        if active_view is None:
            result.success = False
            result.method = "skipped"
            result.errors.append(f"No active view for {ui_name}")
            return result
        
        # Get kind map for this UI
        kind_map = self._get_kind_map(ui_name)
        
        # Create symlinks for each asset kind
        for kind in AssetKind:
            kind_path = kind_map.get_path(kind)
            if not kind_path:
                continue
            
            # Source in view: views/<ui>/active/<kind_path>
            view_kind_path = active_view / kind_path
            
            # Skip if this kind doesn't exist in the view
            if not view_kind_path.exists():
                continue
            
            # Target directory in UI: <ui_root>/<kind_path>
            ui_kind_dir = ui_root / kind_path
            
            # Ensure parent directory exists
            ui_kind_dir.mkdir(parents=True, exist_ok=True)
            
            # Synapse symlink location: <ui_root>/<kind_path>/synapse
            synapse_link = ui_kind_dir / "synapse"
            
            try:
                # Remove existing symlink if present
                if synapse_link.is_symlink():
                    synapse_link.unlink()
                elif synapse_link.exists():
                    # Real directory - don't overwrite
                    result.errors.append(
                        f"Cannot create symlink - real directory exists: {synapse_link}"
                    )
                    continue
                
                # Create symlink
                synapse_link.symlink_to(view_kind_path)
                result.created.append(str(synapse_link))
                logger.info(f"[{ui_name}] Created: {synapse_link} -> {view_kind_path}")
                
            except OSError as e:
                result.errors.append(f"Failed to create {synapse_link}: {e}")
                result.success = False
        
        if not result.created and not result.errors:
            result.errors.append("No kinds found in active view to attach")
            result.success = False
        
        return result
    
    def attach_all(
        self,
        ui_targets: Optional[List[str]] = None,
        comfyui_use_yaml: bool = True,  # Default to YAML for ComfyUI
    ) -> Dict[str, AttachResult]:
        """
        Attach all configured UIs to their views.
        
        Args:
            ui_targets: List of UIs to attach. If None, attach all configured.
            comfyui_use_yaml: Use extra_model_paths.yaml for ComfyUI (recommended)
        
        Returns:
            Dict mapping ui_name -> AttachResult
        """
        if ui_targets is None:
            ui_targets = list(self.ui_roots.keys())
        
        results = {}
        for ui in ui_targets:
            use_yaml = comfyui_use_yaml and ui.lower() == "comfyui"
            results[ui] = self.attach(ui, use_yaml=use_yaml)
        
        return results
    
    def detach(self, ui_name: str) -> AttachResult:
        """
        Detach a UI from Synapse.
        
        For ComfyUI: Restores original extra_model_paths.yaml AND removes symlinks
        For others: Removes synapse symlinks
        
        Args:
            ui_name: Name of UI to detach
        
        Returns:
            AttachResult with status
        """
        ui_name = ui_name.lower()
        result = AttachResult(ui=ui_name, success=True, method="detach")
        
        ui_root = self.ui_roots.get(ui_name)
        if ui_root is None:
            return result  # Nothing to detach
        
        if not ui_root.exists():
            return result  # Nothing to detach
        
        # For ComfyUI, also restore YAML
        if ui_name == "comfyui":
            yaml_result = self.detach_comfyui_yaml()
            result.created.extend(yaml_result.created)
            result.errors.extend(yaml_result.errors)
        
        # Always remove symlinks (for both ComfyUI and others)
        kind_map = self._get_kind_map(ui_name)
        
        for kind in AssetKind:
            kind_path = kind_map.get_path(kind)
            if not kind_path:
                continue
            
            synapse_link = ui_root / kind_path / "synapse"
            
            if synapse_link.is_symlink():
                try:
                    synapse_link.unlink()
                    result.created.append(f"Removed: {synapse_link}")
                    logger.info(f"[{ui_name}] Removed: {synapse_link}")
                except OSError as e:
                    result.errors.append(f"Failed to remove {synapse_link}: {e}")
        
        return result
    
    def status(self, ui_name: str) -> Dict[str, Any]:
        """
        Get attachment status for a UI.
        
        Returns dict with:
        - attached: bool (synapse section in yaml OR symlinks exist)
        - method: "symlink" | "extra_model_paths" | "none"
        - symlinks: list of existing synapse symlinks
        - yaml_config: path to YAML config if exists
        - view_exists: bool
        - has_backup: bool (for ComfyUI - whether backup exists)
        """
        ui_name = ui_name.lower()
        
        status_info = {
            "ui": ui_name,
            "attached": False,
            "method": "none",
            "symlinks": [],
            "yaml_config": None,
            "view_exists": False,
            "has_backup": False,
            "error": None,
        }
        
        ui_root = self.ui_roots.get(ui_name)
        if ui_root is None:
            status_info["error"] = f"No root configured for {ui_name}"
            return status_info
        
        if not ui_root.exists():
            status_info["error"] = f"UI root does not exist: {ui_root}"
            return status_info
        
        # Check view exists
        active_view = self.get_active_view_path(ui_name)
        status_info["view_exists"] = active_view is not None and active_view.exists()
        
        # Check YAML config (for ComfyUI) - check in ComfyUI root, not store root
        if ui_name == "comfyui":
            yaml_path = ui_root / "extra_model_paths.yaml"
            backup_path = yaml_path.parent / f"{yaml_path.name}.synapse.bak"
            
            status_info["has_backup"] = backup_path.exists()
            
            if yaml_path.exists():
                try:
                    with open(yaml_path, "r") as f:
                        content = yaml.safe_load(f) or {}
                    
                    # Check if synapse section exists
                    if "synapse" in content:
                        status_info["yaml_config"] = str(yaml_path)
                        status_info["attached"] = True
                        status_info["method"] = "extra_model_paths"
                except Exception:
                    pass  # Ignore parse errors
        
        # Get kind map for this UI
        kind_map = self._get_kind_map(ui_name)
        
        # Check each possible symlink
        for kind in AssetKind:
            kind_path = kind_map.get_path(kind)
            if not kind_path:
                continue
            
            synapse_link = ui_root / kind_path / "synapse"
            
            if synapse_link.is_symlink():
                target = str(synapse_link.resolve()) if synapse_link.exists() else "broken"
                status_info["symlinks"].append({
                    "kind": kind.value,
                    "path": str(synapse_link),
                    "target": target,
                })
        
        if status_info["symlinks"]:
            status_info["attached"] = True
            if status_info["method"] == "none":
                status_info["method"] = "symlink"
        
        return status_info
    
    def refresh_attached(self, ui_targets: Optional[List[str]] = None) -> Dict[str, AttachResult]:
        """
        Refresh attachment for UIs that are already attached.
        
        This is called after use/back/sync to update paths to match new active view.
        Only updates UIs that are currently attached - does NOT attach detached UIs.
        
        Args:
            ui_targets: List of UIs to check. If None, checks all configured.
        
        Returns:
            Dict mapping ui_name -> AttachResult (only for UIs that were refreshed)
        """
        if ui_targets is None:
            ui_targets = list(self.ui_roots.keys())
        
        results = {}
        
        for ui_name in ui_targets:
            ui_name = ui_name.lower()
            current_status = self.status(ui_name)
            
            # Only refresh if already attached
            if not current_status.get("attached"):
                logger.debug(f"[{ui_name}] Not attached, skipping refresh")
                continue
            
            # Re-attach to update paths
            if ui_name == "comfyui":
                results[ui_name] = self.attach_comfyui_yaml()
            else:
                results[ui_name] = self.attach(ui_name)
            
            logger.info(f"[{ui_name}] Refreshed attachment for active view")
        
        return results
    
    def refresh_all_attached(self) -> Dict[str, AttachResult]:
        """
        Refresh all attached UIs to match current active views.
        
        Convenience method that calls refresh_attached for all configured UIs.
        
        Returns:
            Dict mapping ui_name -> AttachResult (only for UIs that were refreshed)
        """
        return self.refresh_attached()

