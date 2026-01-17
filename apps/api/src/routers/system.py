"""
System Router - v2 Only

Health checks, diagnostics, and system status using Store v2.
No v1 dependencies (no PackRegistry, no v1 SynapseDoctor).
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from pathlib import Path

from config.settings import get_config
from src.store.api import get_store, reset_store

router = APIRouter()

# Centralized version - update this for releases
VERSION = "2.0.8"


class StatusResponse(BaseModel):
    """System status response."""
    status: str
    version: str
    store_initialized: bool
    store_root: str
    comfyui_path: str
    comfyui_found: bool
    packs_count: int
    profiles_count: int
    nsfw_blur_enabled: bool


class DiagnosticIssue(BaseModel):
    """Single diagnostic issue."""
    level: str
    message: str
    suggestion: Optional[str] = None


class DiagnosticsResponse(BaseModel):
    """Full diagnostics response."""
    store_initialized: bool
    store_root: str
    comfyui_found: bool
    comfyui_path: str
    packs_count: int
    profiles_count: int
    blobs_count: int
    missing_blobs: int
    unresolved_deps: int
    ui_attach_status: Dict[str, Any]
    issues: List[DiagnosticIssue]


class SettingsResponse(BaseModel):
    """Current settings."""
    comfyui_path: str
    synapse_data_path: str
    nsfw_blur_enabled: bool
    civitai_token_set: bool
    huggingface_token_set: bool
    # Store v2 settings
    store_root: str
    store_ui_roots: Dict[str, str]
    store_default_ui_set: str
    store_ui_sets: Dict[str, List[str]]


class SettingsUpdate(BaseModel):
    """Settings update request."""
    comfyui_path: Optional[str] = None
    nsfw_blur_enabled: Optional[bool] = None
    civitai_token: Optional[str] = None
    huggingface_token: Optional[str] = None
    # Store v2 settings
    store_root: Optional[str] = None
    store_ui_roots: Optional[Dict[str, str]] = None
    store_default_ui_set: Optional[str] = None
    store_ui_sets: Optional[Dict[str, List[str]]] = None


@router.get("/status", response_model=StatusResponse)
async def get_status():
    """Get system status using v2 Store."""
    config = get_config()
    
    # Check ComfyUI
    comfyui_path = Path(config.comfyui.base_path).expanduser()
    comfyui_found = comfyui_path.exists()
    
    # Check store
    store = get_store()
    store_initialized = store.layout.is_initialized() if store else False
    
    # Count packs and profiles from v2 store
    packs_count = 0
    profiles_count = 0
    if store_initialized:
        try:
            packs_count = len(store.list_packs())
            profiles_count = len(store.layout.list_profiles())
        except Exception:
            pass
    
    return StatusResponse(
        status="running",
        version=VERSION,
        store_initialized=store_initialized,
        store_root=str(config.store.root),
        comfyui_path=str(config.comfyui.base_path),
        comfyui_found=comfyui_found,
        packs_count=packs_count,
        profiles_count=profiles_count,
        nsfw_blur_enabled=config.ui.nsfw_blur_enabled,
    )


@router.get("/diagnostics", response_model=DiagnosticsResponse)
async def get_diagnostics():
    """Run system diagnostics using v2 Store."""
    config = get_config()
    store = get_store()
    
    issues: List[DiagnosticIssue] = []
    
    # Check ComfyUI
    comfyui_path = Path(config.comfyui.base_path).expanduser()
    comfyui_found = comfyui_path.exists()
    if not comfyui_found:
        issues.append(DiagnosticIssue(
            level="warning",
            message=f"ComfyUI not found at {comfyui_path}",
            suggestion="Update ComfyUI path in settings",
        ))
    
    # Check store
    store_initialized = store.layout.is_initialized() if store else False
    if not store_initialized:
        issues.append(DiagnosticIssue(
            level="error",
            message="Store not initialized",
            suggestion="Run 'synapse init' or click Init Store in Settings",
        ))
    
    packs_count = 0
    profiles_count = 0
    blobs_count = 0
    missing_blobs = 0
    unresolved_deps = 0
    ui_attach_status = {}
    
    if store_initialized:
        try:
            packs_count = len(store.list_packs())
            profiles_count = len(store.layout.list_profiles())
            
            # Count blobs
            blobs_dir = store.layout.blobs_path
            if blobs_dir.exists():
                blobs_count = sum(1 for _ in blobs_dir.rglob("*") if _.is_file())
            
            # Check status for missing/unresolved
            status = store.status()
            missing_blobs = len(status.missing_blobs)
            unresolved_deps = len(status.unresolved)
            
            if missing_blobs > 0:
                issues.append(DiagnosticIssue(
                    level="warning",
                    message=f"{missing_blobs} missing blob(s)",
                    suggestion="Run 'synapse doctor' to fix",
                ))
            
            if unresolved_deps > 0:
                issues.append(DiagnosticIssue(
                    level="warning",
                    message=f"{unresolved_deps} unresolved dependency(s)",
                    suggestion="Run 'synapse resolve' on affected packs",
                ))
            
            # Get attach status
            ui_attach_status = store.get_attach_status()
            
        except Exception as e:
            issues.append(DiagnosticIssue(
                level="error",
                message=f"Error reading store: {e}",
            ))
    
    return DiagnosticsResponse(
        store_initialized=store_initialized,
        store_root=str(config.store.root),
        comfyui_found=comfyui_found,
        comfyui_path=str(comfyui_path),
        packs_count=packs_count,
        profiles_count=profiles_count,
        blobs_count=blobs_count,
        missing_blobs=missing_blobs,
        unresolved_deps=unresolved_deps,
        ui_attach_status=ui_attach_status,
        issues=issues,
    )


@router.get("/settings", response_model=SettingsResponse)
async def get_settings():
    """Get current settings."""
    config = get_config()
    
    return SettingsResponse(
        comfyui_path=str(config.comfyui.base_path),
        synapse_data_path=str(config.data_path),
        nsfw_blur_enabled=config.ui.nsfw_blur_enabled,
        civitai_token_set=bool(config.api.civitai_token),
        huggingface_token_set=bool(config.api.huggingface_token),
        store_root=str(config.store.root),
        store_ui_roots=config.store.ui_roots.to_dict(),
        store_default_ui_set=config.store.default_ui_set,
        store_ui_sets=config.store.ui_sets,
    )


@router.patch("/settings", response_model=SettingsResponse)
async def update_settings(update: SettingsUpdate):
    """Update settings."""
    from config.settings import UIRoots
    
    config = get_config()
    
    if update.comfyui_path is not None:
        config.comfyui.base_path = Path(update.comfyui_path).expanduser()
    
    if update.nsfw_blur_enabled is not None:
        config.ui.nsfw_blur_enabled = update.nsfw_blur_enabled
    
    if update.civitai_token is not None:
        config.api.civitai_token = update.civitai_token
    
    if update.huggingface_token is not None:
        config.api.huggingface_token = update.huggingface_token
    
    # Store v2 settings
    store_changed = False
    
    if update.store_root is not None:
        config.store.root = Path(update.store_root).expanduser()
        store_changed = True
    
    if update.store_ui_roots is not None:
        config.store.ui_roots = UIRoots.from_dict(update.store_ui_roots)
        store_changed = True
    
    if update.store_default_ui_set is not None:
        config.store.default_ui_set = update.store_default_ui_set
    
    if update.store_ui_sets is not None:
        config.store.ui_sets = update.store_ui_sets
    
    config.save()
    
    # Reset store singleton if store settings changed
    if store_changed:
        reset_store()
    
    return await get_settings()


@router.post("/rescan")
async def rescan_models():
    """Trigger a rescan/rebuild of store views."""
    store = get_store()
    
    if not store.layout.is_initialized():
        return {"message": "Store not initialized", "packs_found": 0}
    
    # Rebuild views via doctor
    report = store.doctor()
    
    return {
        "message": "Rescan completed",
        "packs_found": len(store.list_packs()),
        "views_rebuilt": report.actions.views_rebuilt,
    }
