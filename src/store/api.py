"""
Synapse Store API Routers

FastAPI routers for Store operations.
All endpoints return the same JSON format as CLI --json output.

Usage:
    from fastapi import FastAPI
    from src.store.api import create_store_routers
    
    app = FastAPI()
    routers = create_store_routers()
    for router in routers:
        app.include_router(router, prefix="/api")
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Body, File, UploadFile, Form, BackgroundTasks
from pydantic import BaseModel, Field

# Setup logger
logger = logging.getLogger(__name__)

from .models import (
    APIResponse,
    BackResult,
    DoctorReport,
    SearchResult,
    StatusReport,
    StoreConfig,
    UpdatePlan,
    UpdateResult,
    UseResult,
    CivitaiSelector,
    HuggingFaceSelector,
    AssetKind,
    GenerationParameters,
    WorkflowInfo,
)


# =============================================================================
# Request/Response Models
# =============================================================================

class InitRequest(BaseModel):
    """Request for store initialization."""
    force: bool = False


class InitResponse(BaseModel):
    """Response for store initialization."""
    initialized: bool
    root: str


class UseRequest(BaseModel):
    """Request for use command."""
    pack: str
    ui_set: Optional[str] = None
    sync: bool = True


class BackRequest(BaseModel):
    """Request for back command."""
    ui_set: Optional[str] = None
    sync: bool = False


class UpdateRequest(BaseModel):
    """Request for update command."""
    pack: str
    dry_run: bool = False
    sync: bool = True
    ui_set: Optional[str] = None
    choose: Optional[Dict[str, int]] = None


class DoctorRequest(BaseModel):
    """Request for doctor command."""
    rebuild_views: bool = False
    rebuild_db: Optional[str] = None
    verify_blobs: bool = False
    ui_set: Optional[str] = None


class ResetRequest(BaseModel):
    """Request for reset to global."""
    ui_set: Optional[str] = None
    sync: bool = True


class RuntimeStackEntry(BaseModel):
    """Single entry in runtime stack visualization."""
    profile: str
    is_active: bool = False


class UIRuntimeStatus(BaseModel):
    """Runtime status for a single UI."""
    ui: str
    active_profile: str
    stack: List[str]
    stack_depth: int


class ProfilesStatusResponse(BaseModel):
    """Complete profiles status for UI."""
    ui_statuses: List[UIRuntimeStatus]
    shadowed: List[Dict[str, Any]]
    shadowed_count: int
    updates_available: int = 0


class UpdateCheckResponse(BaseModel):
    """Response for update check."""
    pack: str
    has_updates: bool
    changes_count: int
    ambiguous_count: int
    plan: Optional[Dict[str, Any]] = None


class BulkUpdateCheckResponse(BaseModel):
    """Response for bulk update check."""
    packs_checked: int
    packs_with_updates: int
    total_changes: int
    plans: Dict[str, Dict[str, Any]]


class ImportRequest(BaseModel):
    """Request for import command."""
    url: str
    download_previews: bool = True
    add_to_global: bool = True


class ImportResponse(BaseModel):
    """Response for import command."""
    pack_name: str
    pack_type: str
    dependencies_count: int


class InstallResponse(BaseModel):
    """Response for install command."""
    pack: str
    blobs_installed: int
    hashes: List[str]


class SyncRequest(BaseModel):
    """Request for sync command."""
    profile: Optional[str] = None
    ui_set: Optional[str] = None
    install_missing: bool = True


class SyncResponse(BaseModel):
    """Response for sync command."""
    reports: Dict[str, Dict[str, Any]]


class CleanRequest(BaseModel):
    """Request for clean command."""
    tmp: bool = True
    cache: bool = False
    partial: bool = True


class CleanResponse(BaseModel):
    """Response for clean command."""
    cleaned: Dict[str, int]


# =============================================================================
# Store Instance Management
# =============================================================================

_store_instance = None


def get_store():
    """
    Get or create Store singleton.
    
    Reads configuration from config/settings.py to ensure Store uses
    the same settings as the rest of the application and UI.
    """
    global _store_instance
    if _store_instance is None:
        from . import Store
        from config.settings import get_config
        
        # Load application config
        cfg = get_config()
        
        # Get Civitai API key from config
        civitai_api_key = None
        if hasattr(cfg, 'api') and hasattr(cfg.api, 'civitai_token'):
            civitai_api_key = cfg.api.civitai_token
        
        # Create Store with configured root and API keys
        _store_instance = Store(
            root=cfg.store.root,
            civitai_api_key=civitai_api_key,
        )
        
        # Store config reference for later use (e.g., ui_roots, ui_sets)
        _store_instance._synapse_config = cfg
        
    return _store_instance


def reset_store():
    """Reset Store singleton (useful for config changes)."""
    global _store_instance
    _store_instance = None


def require_initialized():
    """Dependency that requires store to be initialized."""
    store = get_store()
    if not store.is_initialized():
        raise HTTPException(
            status_code=400,
            detail="Store not initialized. Call POST /api/store/init first."
        )
    return store


# =============================================================================
# Store Router
# =============================================================================

store_router = APIRouter(tags=["store"])


@store_router.get("/models", response_model=Dict[str, Any])
def list_store_models(
    kind: Optional[str] = Query(None),
    store=Depends(require_initialized),
):
    """List available models in store inventory."""
    models = store.list_models(kind=kind)
    return {"models": models}


@store_router.post("/init", response_model=InitResponse)
def init_store(request: InitRequest):
    """Initialize the store."""
    store = get_store()
    store.init(force=request.force)
    return InitResponse(
        initialized=True,
        root=str(store.layout.root),
    )


@store_router.get("/config", response_model=Dict[str, Any])
def get_config(store=Depends(require_initialized)):
    """Get store configuration."""
    config = store.get_config()
    return config.model_dump()


@store_router.get("/status", response_model=Dict[str, Any])
def get_status(
    ui_set: Optional[str] = Query(None),
    store=Depends(require_initialized),
):
    """Get current store status."""
    status = store.status(ui_set=ui_set)
    return status.model_dump()


@store_router.post("/doctor", response_model=Dict[str, Any])
def run_doctor(
    request: DoctorRequest,
    store=Depends(require_initialized),
):
    """Run diagnostics and repairs."""
    report = store.doctor(
        rebuild_views=request.rebuild_views,
        rebuild_db=request.rebuild_db,
        verify_blobs=request.verify_blobs,
        ui_set=request.ui_set,
    )
    return report.model_dump()


@store_router.post("/clean", response_model=CleanResponse)
def clean_store(
    request: CleanRequest,
    store=Depends(require_initialized),
):
    """Clean temporary files."""
    result = store.clean(
        tmp=request.tmp,
        cache=request.cache,
        partial=request.partial,
    )
    return CleanResponse(cleaned=result)


class AttachRequest(BaseModel):
    """Request for UI attach operation."""
    ui_set: Optional[str] = None


@store_router.post("/attach", response_model=Dict[str, Any])
def attach_uis(
    request: AttachRequest,
    store=Depends(require_initialized),
):
    """
    Attach UIs to Synapse views.
    
    Creates symlinks so UIs can see Synapse-managed models.
    """
    return store.attach_uis(ui_set=request.ui_set)


@store_router.post("/detach", response_model=Dict[str, Any])
def detach_uis(
    request: AttachRequest,
    store=Depends(require_initialized),
):
    """
    Detach UIs from Synapse views.
    
    Removes symlinks.
    """
    return store.detach_uis(ui_set=request.ui_set)


@store_router.get("/attach-status", response_model=Dict[str, Any])
def get_attach_status(
    ui_set: Optional[str] = Query(None),
    store=Depends(require_initialized),
):
    """Get UI attachment status."""
    return store.get_attach_status(ui_set=ui_set)


# =============================================================================
# Packs Router
# =============================================================================

v2_packs_router = APIRouter(tags=["packs"])


@v2_packs_router.get("/", response_model=Dict[str, Any])
def list_packs(
    show_nsfw: bool = Query(True, description="Include NSFW hidden packs"),
    store=Depends(require_initialized)
):
    """List all packs with UI-friendly details.
    
    NSFW handling:
    - nsfw-pack tag: Pack previews are blurred in UI
    - nsfw-pack-hide tag: Pack is completely hidden when show_nsfw=False
    """
    pack_names = store.list_packs()
    packs_list = []
    
    for name in pack_names:
        try:
            pack = store.get_pack(name)
            lock = store.get_pack_lock(name)
            
            # Check NSFW flags
            is_nsfw = pack.is_nsfw if hasattr(pack, 'is_nsfw') else "nsfw-pack" in (pack.user_tags or [])
            is_nsfw_hidden = pack.is_nsfw_hidden if hasattr(pack, 'is_nsfw_hidden') else "nsfw-pack-hide" in (pack.user_tags or [])
            
            # Filter out hidden packs when NSFW mode is off
            if not show_nsfw and is_nsfw_hidden:
                continue
            
            # Get preview thumbnail
            thumbnail = None
            previews_dir = store.layout.pack_previews_path(name)
            if previews_dir.exists():
                for ext in ['.png', '.jpg', '.jpeg', '.webp']:
                    for f in previews_dir.glob(f'*{ext}'):
                        thumbnail = f"/previews/{name}/resources/previews/{f.name}"
                        break
                    if thumbnail:
                        break
            
            # Check for unresolved dependencies
            has_unresolved = False
            if lock:
                for dep in pack.dependencies:
                    if lock.get_resolved(dep.id) is None:
                        has_unresolved = True
                        break
            else:
                has_unresolved = len(pack.dependencies) > 0
            
            packs_list.append({
                "name": pack.name,
                "version": pack.version or "1.0.0",
                "description": pack.description or "",
                "pack_type": pack.pack_type.value if hasattr(pack.pack_type, 'value') else str(pack.pack_type),
                "base_model": pack.base_model,
                "dependencies_count": len(pack.dependencies),
                "has_unresolved": has_unresolved,
                "thumbnail": thumbnail,
                "source_url": pack.source.url if pack.source else None,
                "tags": pack.tags or [],
                "user_tags": pack.user_tags or [],
                "is_nsfw": is_nsfw,
                "is_nsfw_hidden": is_nsfw_hidden,
                "created_at": pack.created_at.isoformat() if pack.created_at else None,
            })
        except Exception as e:
            # Include pack even if there's an error
            packs_list.append({
                "name": name,
                "version": "1.0.0",
                "description": f"Error loading: {e}",
                "pack_type": "unknown",
                "dependencies_count": 0,
                "has_unresolved": True,
                "thumbnail": None,
                "is_nsfw": False,
                "is_nsfw_hidden": False,
            })
    
    return {"packs": packs_list}


@v2_packs_router.get("/{pack_name}", response_model=Dict[str, Any])
def get_pack(pack_name: str, store=Depends(require_initialized)):
    """Get pack details in UI-friendly format."""
    try:
        pack = store.get_pack(pack_name)
        lock = store.get_pack_lock(pack_name)
        
        # Build assets list from dependencies
        assets = []
        for dep in pack.dependencies:
            resolved = lock.get_resolved(dep.id) if lock else None
            
            # Determine source from selector
            source = "local"
            source_info = {}
            if dep.selector.civitai:
                source = "civitai"
                source_info = {
                    "model_id": dep.selector.civitai.model_id,
                    "version_id": dep.selector.civitai.version_id,
                    "model_name": getattr(dep.selector.civitai, 'model_name', None),
                    "version_name": getattr(dep.selector.civitai, 'version_name', None),
                    "creator": getattr(dep.selector.civitai, 'creator', None),
                }
            elif dep.selector.huggingface:
                source = "huggingface"
                source_info = {
                    "repo_id": dep.selector.huggingface.repo_id,
                    "filename": dep.selector.huggingface.filename,
                }
            elif dep.selector.url:
                source = "url"
            
            asset_info = {
                "name": dep.id,
                "asset_type": dep.kind.value if hasattr(dep.kind, 'value') else str(dep.kind),
                "source": source,
                "source_info": source_info,
                "installed": False,
                "status": "unresolved",
                "base_model_hint": dep.selector.base_model,
                "filename": dep.expose.filename if dep.expose else None,
                "description": dep.description or None,
                "version_name": None,
            }
            
            # Get URL from selector first (always available)
            if dep.selector.url:
                asset_info["url"] = dep.selector.url
            
            if resolved:
                asset_info["status"] = "resolved"
                asset_info["filename"] = resolved.artifact.provider.filename
                asset_info["size"] = resolved.artifact.size_bytes
                asset_info["sha256"] = resolved.artifact.sha256
                
                # Add provider info
                asset_info["provider_name"] = resolved.artifact.provider.name.value if hasattr(resolved.artifact.provider.name, 'value') else str(resolved.artifact.provider.name)
                
                # Add version info if available
                if hasattr(resolved.artifact.provider, 'version_name'):
                    asset_info["version_name"] = resolved.artifact.provider.version_name
                
                # Override URL from resolved artifact if available
                if resolved.artifact.download.urls:
                    asset_info["url"] = resolved.artifact.download.urls[0]
                
                # Check if blob exists
                if resolved.artifact.sha256:
                    if store.blob_store.blob_exists(resolved.artifact.sha256):
                        asset_info["installed"] = True
                        asset_info["status"] = "installed"
                        asset_info["local_path"] = str(store.blob_store.blob_path(resolved.artifact.sha256))
            
            assets.append(asset_info)
        
        # Build previews list from pack manifest (canonical source)
        # This preserves correct nsfw flags and metadata from Civitai API
        previews = []
        previews_dir = store.layout.pack_previews_path(pack_name)
        
        if pack.previews:
            # Use pack.previews as canonical source (has correct nsfw and meta)
            for preview in pack.previews:
                preview_info = {
                    "filename": preview.filename,
                    "url": f"/previews/{pack_name}/resources/previews/{preview.filename}",
                    "nsfw": preview.nsfw,
                    "width": preview.width,
                    "height": preview.height,
                }
                
                # Use meta from pack manifest first
                if preview.meta:
                    preview_info["meta"] = preview.meta
                else:
                    # Fallback: try to load from sidecar JSON
                    if previews_dir.exists():
                        meta_file = previews_dir / (preview.filename + '.json')
                        if meta_file.exists():
                            try:
                                import json
                                preview_info["meta"] = json.loads(meta_file.read_text())
                            except:
                                pass
                
                previews.append(preview_info)
        elif previews_dir.exists():
            # Fallback for packs without manifest previews (legacy)
            for f in sorted(previews_dir.iterdir()):
                if f.suffix.lower() in ['.png', '.jpg', '.jpeg', '.webp', '.gif']:
                    preview_info = {
                        "filename": f.name,
                        "url": f"/previews/{pack_name}/resources/previews/{f.name}",
                        "nsfw": "nsfw" in f.name.lower(),
                    }
                    
                    # Try to load meta from sidecar
                    meta_file = f.with_suffix(f.suffix + '.json')
                    if meta_file.exists():
                        try:
                            import json
                            preview_info["meta"] = json.loads(meta_file.read_text())
                        except:
                            pass
                    
                    previews.append(preview_info)
        
        # Build workflows list - use pack.json as primary source, enrich with filesystem info
        workflows = []
        workflows_dir = store.layout.pack_workflows_path(pack_name)
        
        # First, collect all workflow files on disk
        workflow_files = {}
        if workflows_dir.exists():
            for f in sorted(workflows_dir.glob("*.json")):
                workflow_files[f.name] = f
        
        # Process workflows from pack.json
        for wf in pack.workflows:
            workflow_info = {
                "name": wf.name,
                "filename": wf.filename,
                "description": wf.description,
                "source_url": wf.source_url,
                "is_default": wf.is_default,
                "local_path": None,
                "file_exists": False,
                "has_symlink": False,
                "symlink_valid": False,
                "symlink_path": None,
            }
            
            # Check if file exists
            if wf.filename in workflow_files:
                f = workflow_files[wf.filename]
                workflow_info["local_path"] = str(f)
                workflow_info["file_exists"] = True
                
                # Check for symlink in ComfyUI workflows
                from config.settings import get_config
                config = get_config()
                comfyui_workflows = config.paths.comfyui / "user" / "default" / "workflows"
                
                # Check both symlink formats
                for symlink_name in [f.name, f"[{pack_name}] {f.name}"]:
                    symlink_path = comfyui_workflows / symlink_name
                    if symlink_path.exists() or symlink_path.is_symlink():
                        workflow_info["has_symlink"] = True
                        workflow_info["symlink_path"] = str(symlink_path)
                        workflow_info["symlink_valid"] = symlink_path.exists() and symlink_path.resolve() == f.resolve()
                        break
                
                # Remove from dict so we don't process it again
                del workflow_files[wf.filename]
            
            workflows.append(workflow_info)
        
        # Add any workflow files not in pack.json (orphaned files)
        for filename, f in workflow_files.items():
            workflow_info = {
                "name": f.stem,
                "filename": filename,
                "description": None,
                "source_url": None,
                "is_default": "default" in f.stem.lower(),
                "local_path": str(f),
                "file_exists": True,
                "has_symlink": False,
                "symlink_valid": False,
                "symlink_path": None,
                "orphaned": True,  # Not in pack.json
            }
            
            # Check for symlink
            from config.settings import get_config
            config = get_config()
            comfyui_workflows = config.paths.comfyui / "user" / "default" / "workflows"
            
            for symlink_name in [f.name, f"[{pack_name}] {f.name}"]:
                symlink_path = comfyui_workflows / symlink_name
                if symlink_path.exists() or symlink_path.is_symlink():
                    workflow_info["has_symlink"] = True
                    workflow_info["symlink_path"] = str(symlink_path)
                    workflow_info["symlink_valid"] = symlink_path.exists() and symlink_path.resolve() == f.resolve()
                    break
            
            workflows.append(workflow_info)
        
        # Check for unresolved and not installed assets
        has_unresolved = any(a["status"] == "unresolved" for a in assets)
        all_installed = all(a["status"] == "installed" for a in assets) if assets else True
        can_generate = all_installed and len(workflows) == 0  # Can generate if all installed but no workflows yet
        
        # Load parameters from pack.json (not external file)
        parameters = {}
        if pack.parameters:
            parameters = pack.parameters.model_dump(exclude_none=True)
        
        # Get model info from source
        model_info = {}
        if pack.source:
            model_info = {
                "model_type": pack.pack_type.value if hasattr(pack.pack_type, 'value') else str(pack.pack_type),
                "base_model": pack.base_model,
                "trigger_words": pack.trigger_words or [],
                "source_url": pack.source.url,
            }
        
        return {
            "name": pack.name,
            "version": pack.version or "1.0.0",
            "description": pack.description or "",
            "author": pack.author,
            "tags": pack.tags or [],
            "user_tags": pack.user_tags or [],
            "source_url": pack.source.url if pack.source else None,
            "created_at": pack.created_at.isoformat() if pack.created_at else None,
            "installed": all_installed,
            "has_unresolved": has_unresolved,
            "all_installed": all_installed,
            "can_generate": can_generate,
            "assets": assets,
            "previews": previews,
            "workflows": workflows,
            "custom_nodes": [],
            "docs": {},
            "parameters": parameters,
            "model_info": model_info,
            # Raw data for debugging
            "pack": pack.model_dump(),
            "lock": lock.model_dump() if lock else None,
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@v2_packs_router.post("/import", response_model=ImportResponse)
def import_pack(
    request: ImportRequest,
    store=Depends(require_initialized),
):
    """Import a pack from Civitai URL."""
    try:
        pack = store.import_civitai(
            request.url,
            download_previews=request.download_previews,
            add_to_global=request.add_to_global,
        )
        return ImportResponse(
            pack_name=pack.name,
            pack_type=pack.pack_type.value,
            dependencies_count=len(pack.dependencies),
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@v2_packs_router.post("/{pack_name}/resolve", response_model=Dict[str, Any])
def resolve_pack(pack_name: str, store=Depends(require_initialized)):
    """Resolve dependencies for a pack."""
    try:
        lock = store.resolve(pack_name)
        return lock.model_dump()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@v2_packs_router.post("/{pack_name}/install", response_model=InstallResponse)
def install_pack(pack_name: str, store=Depends(require_initialized)):
    """Install blobs for a pack."""
    try:
        hashes = store.install(pack_name)
        return InstallResponse(
            pack=pack_name,
            blobs_installed=len(hashes),
            hashes=hashes,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@v2_packs_router.delete("/{pack_name}")
def delete_pack(pack_name: str, store=Depends(require_initialized)):
    """Delete a pack."""
    if store.delete_pack(pack_name):
        return {"deleted": pack_name}
    raise HTTPException(status_code=404, detail=f"Pack not found: {pack_name}")


# =============================================================================
# Local Model Import
# =============================================================================

class ImportModelResponse(BaseModel):
    """Response from model import."""
    success: bool
    model_path: str
    model_name: str
    model_type: str
    file_size: int


@v2_packs_router.post("/import-model", response_model=ImportModelResponse)
async def import_model(
    file: UploadFile = File(...),
    model_type: str = Form("checkpoint"),
    model_name: str = Form(""),
    base_model: str = Form(""),
):
    """Import a local model file into ComfyUI models directory.
    
    This copies the uploaded file to the appropriate ComfyUI models folder
    and returns the path for use with resolve-base-model.
    """
    from config.settings import get_config
    config = get_config()
    
    logger.info(f"[import-model] Importing: {file.filename}, type={model_type}, name={model_name}")
    
    # Map model type to directory
    type_to_dir = {
        'checkpoint': 'checkpoints',
        'base_model': 'checkpoints',
        'lora': 'loras',
        'vae': 'vae',
        'embedding': 'embeddings',
        'controlnet': 'controlnet',
        'upscaler': 'upscale_models',
        'clip': 'clip',
        'text_encoder': 'text_encoders',
        'diffusion_model': 'diffusion_models',
    }
    
    model_dir = type_to_dir.get(model_type.lower(), 'checkpoints')
    target_dir = config.comfyui.base_path / "models" / model_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # Use original filename
    filename = file.filename or "imported_model.safetensors"
    target_path = target_dir / filename
    
    # Handle duplicate names
    counter = 1
    original_stem = Path(filename).stem
    original_suffix = Path(filename).suffix
    while target_path.exists():
        filename = f"{original_stem}_{counter}{original_suffix}"
        target_path = target_dir / filename
        counter += 1
    
    logger.info(f"[import-model] Target path: {target_path}")
    
    # Copy file
    try:
        file_size = 0
        with open(target_path, 'wb') as f:
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                f.write(chunk)
                file_size += len(chunk)
        
        logger.info(f"[import-model] Saved {file_size / 1024 / 1024:.1f} MB to {target_path}")
        
        # Determine display name
        display_name = model_name if model_name else Path(filename).stem
        
        return ImportModelResponse(
            success=True,
            model_path=str(target_path),
            model_name=display_name,
            model_type=model_type,
            file_size=file_size,
        )
        
    except Exception as e:
        logger.error(f"[import-model] Failed: {e}")
        # Clean up partial file
        if target_path.exists():
            target_path.unlink()
        raise HTTPException(status_code=500, detail=f"Failed to import model: {e}")


# =============================================================================
# Legacy v1 Compatibility Endpoints
# =============================================================================

class ResolveBaseModelRequest(BaseModel):
    """Request to resolve base model for a pack."""
    model_path: Optional[str] = None  # Local model path
    download_url: Optional[str] = None  # Remote download URL
    source: Optional[str] = None  # "civitai" or "huggingface"
    file_name: Optional[str] = None
    size_kb: Optional[int] = None


@v2_packs_router.post("/{pack_name}/resolve-base-model", response_model=Dict[str, Any])
def resolve_base_model(
    pack_name: str, 
    request: ResolveBaseModelRequest,
    store=Depends(require_initialized)
):
    """Resolve base model dependency for a pack.
    
    Updates both pack.json and pack.lock.json with the model info.
    Can either:
    1. Link to existing local model (model_path)
    2. Save download info from Civitai/HuggingFace (download_url + source)
    """
    try:
        logger.info(f"[resolve-base-model] Pack: {pack_name}, Request: {request}")
        
        pack = store.get_pack(pack_name)
        if not pack:
            raise HTTPException(status_code=404, detail=f"Pack not found: {pack_name}")
        
        # Find base_checkpoint dependency
        base_dep = None
        base_dep_idx = -1
        for idx, dep in enumerate(pack.dependencies):
            if dep.id == "base_checkpoint" or "base" in dep.id.lower():
                base_dep = dep
                base_dep_idx = idx
                break
        
        # Determine file name
        file_name = request.file_name or "model.safetensors"
        model_name_clean = file_name.replace('.safetensors', '').replace('.ckpt', '').replace('.pt', '')
        
        if not base_dep:
            # Create base_checkpoint dependency if it doesn't exist
            from .models import (
                PackDependency, AssetKind, DependencySelector, SelectorStrategy,
                UpdatePolicy, ExposeConfig
            )
            
            # Determine selector strategy
            if request.model_path:
                strategy = SelectorStrategy.LOCAL_FILE
            elif request.source == "civitai":
                strategy = SelectorStrategy.CIVITAI_FILE
            elif request.source == "huggingface":
                strategy = SelectorStrategy.HUGGINGFACE_FILE
            else:
                strategy = SelectorStrategy.URL_DOWNLOAD
            
            base_dep = PackDependency(
                id="base_checkpoint",
                kind=AssetKind.CHECKPOINT,
                required=True,
                selector=DependencySelector(
                    strategy=strategy,
                    civitai=CivitaiSelector(model_id=0, version_id=0) if request.source == "civitai" else None,
                    huggingface=HuggingFaceSelector(repo_id="", filename=file_name) if request.source == "huggingface" else None,
                    url=request.download_url,
                    local_path=request.model_path,
                ),
                update_policy=UpdatePolicy(),
                expose=ExposeConfig(filename=file_name),
            )
            pack.dependencies.append(base_dep)
            base_dep_idx = len(pack.dependencies) - 1
        
        # Update pack base_model field  
        pack.base_model = model_name_clean
        
        # Update or create lock file
        lock = store.get_pack_lock(pack_name)
        if not lock:
            from .models import PackLock
            lock = PackLock(pack=pack_name, resolved=[])
        
        # Build resolved artifact using correct v2 models
        from .models import (
            ResolvedDependency, ResolvedArtifact, ArtifactProvider, 
            ArtifactDownload, ArtifactIntegrity, AssetKind, ProviderName
        )
        
        if request.model_path:
            # Local model - create resolved with local path
            from pathlib import Path
            local_path = Path(request.model_path)
            
            # Compute SHA256 if file exists
            sha256 = None
            size_bytes = 0
            if local_path.exists():
                from .blob_store import compute_sha256
                sha256 = compute_sha256(local_path)
                size_bytes = local_path.stat().st_size
            
            resolved = ResolvedDependency(
                dependency_id=base_dep.id,
                artifact=ResolvedArtifact(
                    kind=AssetKind.CHECKPOINT,
                    sha256=sha256,
                    size_bytes=size_bytes,
                    provider=ArtifactProvider(
                        name=ProviderName.LOCAL,
                        filename=local_path.name,
                    ),
                    download=ArtifactDownload(urls=[f"file://{local_path}"]),
                    integrity=ArtifactIntegrity(sha256_verified=sha256 is not None),
                ),
            )
            
            status = "installed" if sha256 else "resolved"
            
        elif request.download_url:
            # Remote model - create resolved with download URL
            size_bytes = (request.size_kb or 0) * 1024
            
            # Determine provider
            if request.source == "civitai":
                provider_name = ProviderName.CIVITAI
            elif request.source == "huggingface":
                provider_name = ProviderName.HUGGINGFACE
            else:
                provider_name = ProviderName.LOCAL
            
            resolved = ResolvedDependency(
                dependency_id=base_dep.id,
                artifact=ResolvedArtifact(
                    kind=AssetKind.CHECKPOINT,
                    sha256=None,  # Unknown until downloaded
                    size_bytes=size_bytes,
                    provider=ArtifactProvider(
                        name=provider_name,
                        filename=file_name,
                    ),
                    download=ArtifactDownload(urls=[request.download_url]),
                    integrity=ArtifactIntegrity(sha256_verified=False),
                ),
            )
            
            # Update selector based on source
            from .models import DependencySelector, SelectorStrategy
            
            if request.source == "civitai":
                # Parse model_id and version_id from URL if possible
                import re
                match = re.search(r'models/(\d+)', request.download_url)
                model_id = int(match.group(1)) if match else 0
                match = re.search(r'modelVersionId=(\d+)', request.download_url)
                version_id = int(match.group(1)) if match else 0
                
                base_dep.selector.strategy = SelectorStrategy.CIVITAI_FILE
                base_dep.selector.civitai = CivitaiSelector(
                    model_id=model_id,
                    version_id=version_id,
                )
                base_dep.selector.url = request.download_url
                
                # Also update provider with IDs
                resolved.artifact.provider.model_id = model_id
                resolved.artifact.provider.version_id = version_id
                
            elif request.source == "huggingface":
                # Parse repo_id from URL
                import re
                match = re.search(r'huggingface\.co/([^/]+/[^/]+)', request.download_url)
                repo_id = match.group(1) if match else ""
                
                base_dep.selector.strategy = SelectorStrategy.HUGGINGFACE_FILE
                base_dep.selector.huggingface = HuggingFaceSelector(
                    repo_id=repo_id,
                    filename=file_name,
                )
                base_dep.selector.url = request.download_url
                
                # Also update provider
                resolved.artifact.provider.repo_id = repo_id
            else:
                # Generic URL download
                base_dep.selector.strategy = SelectorStrategy.URL_DOWNLOAD
                base_dep.selector.url = request.download_url
            
            status = "pending"
        else:
            raise HTTPException(status_code=400, detail="Either model_path or download_url required")
        
        # Update or add resolved dependency in lock
        found = False
        for i, r in enumerate(lock.resolved):
            if r.dependency_id == base_dep.id:
                lock.resolved[i] = resolved
                found = True
                break
        if not found:
            lock.resolved.append(resolved)
        
        # Save updated pack
        store.layout.save_pack(pack)
        
        # Save updated lock
        store.layout.save_pack_lock(lock)
        
        logger.info(f"[resolve-base-model] Success: {model_name_clean}, status={status}")
        
        return {
            "success": True,
            "message": f"Base model set to: {model_name_clean}",
            "base_model": model_name_clean,
            "status": status,
            "download_url": request.download_url,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[resolve-base-model] Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Download Endpoints (v2 implementation)
# =============================================================================

# In-memory download tracking
_active_downloads: Dict[str, dict] = {}


class DownloadAssetRequest(BaseModel):
    """Request to download a specific asset."""
    asset_name: str
    asset_type: str = "checkpoint"
    url: Optional[str] = None
    filename: Optional[str] = None


class DownloadProgress(BaseModel):
    """Download progress info."""
    download_id: str
    pack_name: str
    asset_name: str
    filename: str
    status: str  # pending, downloading, completed, failed
    progress: float  # 0-100
    downloaded_bytes: int = 0
    total_bytes: int = 0
    speed_mbps: float = 0
    eta_seconds: int = 0
    error: Optional[str] = None


@v2_packs_router.post("/{pack_name}/download-asset", response_model=Dict[str, Any])
async def download_asset(
    pack_name: str,
    request: DownloadAssetRequest,
    background_tasks: BackgroundTasks,
    store=Depends(require_initialized),
):
    """Start download of a single asset with progress tracking.
    
    Uses v2 blob store for content-addressable storage.
    """
    import uuid
    import requests
    import threading
    
    logger.info(f"[download-asset] Pack: {pack_name}, Asset: {request.asset_name}, URL: {request.url}")
    
    pack = store.get_pack(pack_name)
    if not pack:
        raise HTTPException(status_code=404, detail=f"Pack not found: {pack_name}")
    
    # Find the dependency (use .id not .dependency_id)
    dep = None
    for d in pack.dependencies:
        if d.id == request.asset_name:
            dep = d
            break
    
    if not dep:
        raise HTTPException(status_code=404, detail=f"Dependency not found: {request.asset_name}")
    
    # Get download URL - first from request, then from lock file
    download_url = request.url
    resolved_filename = None
    
    if not download_url:
        # Try to get URL from resolved artifact in lock
        lock = store.get_pack_lock(pack_name)
        if lock:
            resolved = lock.get_resolved(request.asset_name)
            if resolved and resolved.artifact.download.urls:
                download_url = resolved.artifact.download.urls[0]
                resolved_filename = resolved.artifact.provider.filename
    
    if not download_url:
        raise HTTPException(status_code=400, detail="No download URL available for this asset")
    
    # Determine filename
    filename = request.filename or resolved_filename or f"{request.asset_name}.safetensors"
    
    logger.info(f"[download-asset] Downloading {filename} from {download_url[:100]}...")
    
    # Create download tracking entry
    download_id = str(uuid.uuid4())[:8]
    _active_downloads[download_id] = {
        "download_id": download_id,
        "pack_name": pack_name,
        "asset_name": request.asset_name,
        "filename": filename,
        "status": "pending",
        "progress": 0.0,
        "downloaded_bytes": 0,
        "total_bytes": 0,
        "speed_bps": 0,
        "speed_mbps": 0,
        "eta_seconds": 0,
        "error": None,
    }
    
    def do_download():
        """Background download task."""
        import time
        
        entry = _active_downloads[download_id]
        entry["status"] = "downloading"
        start_time = time.time()
        last_update_time = start_time
        last_downloaded = 0
        
        try:
            # Use blob store for download
            def progress_callback(downloaded: int, total: int):
                nonlocal last_update_time, last_downloaded
                
                current_time = time.time()
                elapsed = current_time - start_time
                time_delta = current_time - last_update_time
                
                entry["downloaded_bytes"] = downloaded
                entry["total_bytes"] = total
                if total > 0:
                    entry["progress"] = (downloaded / total) * 100
                
                # Calculate speed (bytes per second)
                if time_delta > 0.5:  # Update speed every 0.5 seconds
                    bytes_delta = downloaded - last_downloaded
                    speed_bps = bytes_delta / time_delta if time_delta > 0 else 0
                    entry["speed_bps"] = speed_bps
                    entry["speed_mbps"] = speed_bps / (1024 * 1024)  # MB/s
                    
                    # Calculate ETA
                    remaining_bytes = total - downloaded
                    if speed_bps > 0:
                        entry["eta_seconds"] = int(remaining_bytes / speed_bps)
                    else:
                        entry["eta_seconds"] = 0
                    
                    last_update_time = current_time
                    last_downloaded = downloaded
            
            # Download via blob store
            sha256 = store.blob_store.download(
                download_url,
                expected_sha256=None,
                progress_callback=progress_callback,
            )
            
            # Create symlink to ComfyUI models folder
            # Map asset type to directory
            type_map = {
                'checkpoint': 'checkpoints',
                'base_model': 'checkpoints', 
                'base_checkpoint': 'checkpoints',
                'lora': 'loras',
                'vae': 'vae',
                'controlnet': 'controlnet',
                'upscaler': 'upscale_models',
                'embedding': 'embeddings',
                'clip': 'clip',
                'text_encoder': 'text_encoders',
                'diffusion_model': 'diffusion_models',
            }
            asset_type = request.asset_type.lower()
            model_dir = type_map.get(asset_type, 'checkpoints')
            
            # Get ComfyUI path from config
            from config.settings import get_config
            config = get_config()
            target_dir = config.comfyui.base_path / "models" / model_dir
            target_dir.mkdir(parents=True, exist_ok=True)
            target_path = target_dir / filename
            
            # Create symlink from blob to ComfyUI
            blob_path = store.blob_store.blob_path(sha256)
            if target_path.exists() or target_path.is_symlink():
                target_path.unlink()  # Remove existing
            target_path.symlink_to(blob_path)
            
            # Update lock file with SHA256
            lock = store.get_pack_lock(pack_name)
            if lock:
                resolved = lock.get_resolved(request.asset_name)
                if resolved:
                    resolved.artifact.sha256 = sha256
                    resolved.artifact.integrity.sha256_verified = True
                    store.layout.save_pack_lock(lock)
            
            entry["status"] = "completed"
            entry["progress"] = 100.0
            entry["sha256"] = sha256
            logger.info(f"[download-asset] Completed: {filename}, SHA256: {sha256[:16]}...")
            
        except Exception as e:
            entry["status"] = "failed"
            entry["error"] = str(e)
            logger.error(f"[download-asset] Failed: {e}")
            import traceback
            traceback.print_exc()
    
    # Start download in background thread
    thread = threading.Thread(target=do_download, daemon=True)
    thread.start()
    
    return {
        "download_id": download_id,
        "pack_name": pack_name,
        "asset_name": request.asset_name,
        "status": "started",
    }


@v2_packs_router.get("/downloads/active", response_model=List[Dict[str, Any]])
def get_active_downloads():
    """Get list of active downloads for UI."""
    return list(_active_downloads.values())


@v2_packs_router.get("/downloads/{download_id}/progress", response_model=Dict[str, Any])
def get_download_progress(download_id: str):
    """Get progress of a specific download."""
    if download_id not in _active_downloads:
        raise HTTPException(status_code=404, detail=f"Download not found: {download_id}")
    return _active_downloads[download_id]


@v2_packs_router.delete("/downloads/{download_id}")
def cancel_download(download_id: str):
    """Cancel a download."""
    if download_id in _active_downloads:
        _active_downloads[download_id]["status"] = "cancelled"
        del _active_downloads[download_id]
    return {"cancelled": download_id}


@v2_packs_router.delete("/downloads/completed")
def clear_completed_downloads():
    """Clear completed/failed downloads from tracking."""
    to_remove = [
        k for k, v in _active_downloads.items()
        if v.get("status") in ["completed", "failed", "cancelled"]
    ]
    for k in to_remove:
        del _active_downloads[k]
    return {"cleared": len(to_remove)}


@v2_packs_router.post("/{pack_name}/download-all", response_model=Dict[str, Any])
def download_all_assets(
    pack_name: str,
    background_tasks: BackgroundTasks,
    store=Depends(require_initialized),
):
    """Download all pending assets for a pack using v2 install mechanism."""
    try:
        # Use v2 install which downloads all blobs
        installed = store.install(pack_name)
        
        return {
            "success": True,
            "pack_name": pack_name,
            "blobs_installed": len(installed),
            "message": f"Installed {len(installed)} blob(s)",
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class DeleteResourceRequest(BaseModel):
    """Request to delete resource (blob) for a dependency."""
    dependency_id: str
    delete_dependency: bool = False  # If true, also remove from pack.json


@v2_packs_router.delete("/{pack_name}/dependencies/{dep_id}/resource", response_model=Dict[str, Any])
def delete_dependency_resource(
    pack_name: str,
    dep_id: str,
    delete_dependency: bool = Query(False, description="Also remove dependency from pack.json"),
    store=Depends(require_initialized),
):
    """Delete downloaded resource (blob) for a dependency.
    
    By default, only deletes the blob file but keeps the dependency in pack.json.
    If delete_dependency=true, also removes the dependency from pack.json (DANGEROUS).
    """
    try:
        pack = store.get_pack(pack_name)
        lock = store.get_pack_lock(pack_name)
        
        # Find the dependency
        dep = None
        for d in pack.dependencies:
            if d.id == dep_id:
                dep = d
                break
        
        if not dep:
            raise HTTPException(status_code=404, detail=f"Dependency not found: {dep_id}")
        
        deleted_blob = False
        deleted_dependency = False
        blob_path = None
        
        # Delete blob if exists
        if lock:
            resolved = lock.get_resolved(dep_id)
            if resolved and resolved.artifact.sha256:
                sha256 = resolved.artifact.sha256
                if store.blob_store.blob_exists(sha256):
                    blob_path = str(store.blob_store.blob_path(sha256))
                    # Delete the blob
                    import os
                    os.unlink(blob_path)
                    deleted_blob = True
                    logger.info(f"[delete-resource] Deleted blob: {blob_path}")
                
                # Clear from lock
                if resolved:
                    lock.resolved = [r for r in lock.resolved if r.dependency_id != dep_id]
                    store.layout.save_pack_lock(lock)
        
        # Delete dependency from pack.json if requested
        if delete_dependency:
            pack.dependencies = [d for d in pack.dependencies if d.id != dep_id]
            store.layout.save_pack(pack)
            deleted_dependency = True
            logger.info(f"[delete-resource] Deleted dependency from pack.json: {dep_id}")
        
        return {
            "success": True,
            "dependency_id": dep_id,
            "deleted_blob": deleted_blob,
            "deleted_dependency": deleted_dependency,
            "blob_path": blob_path,
            "message": f"Resource deleted" + (", dependency removed from pack" if deleted_dependency else ""),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[delete-resource] Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@v2_packs_router.post("/{pack_name}/repair-urls", response_model=Dict[str, Any])
def repair_pack_urls(
    pack_name: str,
    store=Depends(require_initialized)
):
    """Repair missing URLs for pack assets (v1 compatibility).
    
    Re-fetches download URLs from Civitai for assets missing URLs.
    """
    try:
        pack = store.get_pack(pack_name)
        if not pack:
            raise HTTPException(status_code=404, detail=f"Pack not found: {pack_name}")
        
        repaired = 0
        
        # For each dependency with civitai selector, try to get fresh URL
        for dep in pack.dependencies:
            if dep.selector.civitai:
                civ = dep.selector.civitai
                if civ.version_id:
                    try:
                        # Re-resolve to get fresh URL
                        store.resolve_pack(pack_name)
                        repaired += 1
                    except:
                        pass
        
        return {
            "success": True,
            "pack_name": pack_name,
            "repaired": repaired,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Pack Metadata Endpoints
# =============================================================================
# NOTE: Download tracking (downloads/active, downloads/completed) is handled
# by v1 packs router in apps/api/src/routers/packs.py with proper async support


class UpdatePackRequest(BaseModel):
    """Request to update pack metadata."""
    user_tags: Optional[List[str]] = None
    name: Optional[str] = None  # For rename


@v2_packs_router.patch("/{pack_name}", response_model=Dict[str, Any])
def update_pack(
    pack_name: str,
    request: UpdatePackRequest = Body(...),
    store=Depends(require_initialized),
):
    """Update pack metadata (user tags, rename, etc.)."""
    try:
        pack = store.get_pack(pack_name)
        updated_name = pack_name
        
        # Update user_tags
        if request.user_tags is not None:
            pack.user_tags = request.user_tags
        
        # Handle rename
        if request.name and request.name != pack_name:
            new_name = request.name
            # Check if new name exists
            try:
                store.get_pack(new_name)
                raise HTTPException(status_code=400, detail=f"Pack with name '{new_name}' already exists")
            except:
                pass
            
            # Rename pack directory
            old_path = store.layout.pack_path(pack_name)
            new_path = old_path.parent / new_name
            if old_path.exists():
                import shutil
                shutil.move(str(old_path), str(new_path))
            
            pack.name = new_name
            updated_name = new_name
        
        store.layout.save_pack(pack)
        
        return {
            "success": True,
            "updated": updated_name,
            "user_tags": pack.user_tags,
            "name": pack.name
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[update_pack] Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# Note: repair-urls removed in v2.0.5 - use reimport from Civitai instead


@v2_packs_router.get("/{pack_name}/parameters", response_model=Dict[str, Any])
def get_pack_parameters(
    pack_name: str,
    store=Depends(require_initialized),
):
    """Get recommended generation parameters for pack.
    
    Parameters are stored in pack.json under 'parameters' field.
    """
    try:
        pack = store.get_pack(pack_name)
        
        # Get parameters from pack.json
        if pack.parameters:
            return pack.parameters.model_dump(exclude_none=True)
        
        # Return defaults based on pack type
        defaults = {
            "sampler": "euler",
            "scheduler": "normal",
            "steps": 20,
            "cfg_scale": 7.0,
            "width": 512,
            "height": 768,
        }
        
        # Adjust defaults based on pack type
        if pack.pack_type == AssetKind.CHECKPOINT:
            defaults["width"] = 1024
            defaults["height"] = 1024
        elif pack.pack_type == AssetKind.LORA:
            defaults["steps"] = 25
            
        return defaults
    except Exception as e:
        logger.error(f"[get_pack_parameters] Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@v2_packs_router.patch("/{pack_name}/parameters", response_model=Dict[str, Any])
def update_pack_parameters(
    pack_name: str,
    parameters: Dict[str, Any] = Body(...),
    store=Depends(require_initialized),
):
    """Update recommended generation parameters.
    
    Parameters are stored in pack.json under 'parameters' field.
    Converts camelCase keys to snake_case for consistency.
    """
    try:
        pack = store.get_pack(pack_name)
        
        # Convert camelCase to snake_case for consistency
        import re
        def camel_to_snake(name: str) -> str:
            name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
            return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()
        
        converted = {camel_to_snake(k): v for k, v in parameters.items()}
        
        # Get existing parameters or create new
        existing = {}
        if pack.parameters:
            existing = pack.parameters.model_dump(exclude_none=True)
        
        # Merge new parameters into existing
        existing.update(converted)
        
        # Update pack
        from .models import GenerationParameters
        pack.parameters = GenerationParameters(**existing)
        
        # Save pack
        store.layout.save_pack(pack)
        
        logger.info(f"[update-parameters] Pack: {pack_name}, Parameters: {existing}")
        
        return {"updated": True, "parameters": existing}
    except Exception as e:
        logger.error(f"[update-parameters] Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Workflow Endpoints
# =============================================================================

@v2_packs_router.get("/{pack_name}/workflows", response_model=List[Dict[str, Any]])
def list_pack_workflows(
    pack_name: str,
    store=Depends(require_initialized),
):
    """List workflows for a pack."""
    try:
        workflows_dir = store.layout.pack_workflows_path(pack_name)
        
        workflows = []
        if workflows_dir.exists():
            for f in sorted(workflows_dir.glob("*.json")):
                workflows.append({
                    "name": f.stem,
                    "filename": f.name,
                    "local_path": str(f),
                    "is_default": f.stem == "default",
                })
        
        return workflows
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@v2_packs_router.post("/{pack_name}/generate-workflow", response_model=Dict[str, Any])
def generate_pack_workflow(
    pack_name: str,
    store=Depends(require_initialized),
):
    """Generate a default workflow for pack based on pack type and parameters."""
    import json
    
    try:
        # Load pack
        pack_dir = store.layout.pack_path(pack_name)
        pack_json = pack_dir / "pack.json"
        
        if not pack_json.exists():
            raise HTTPException(status_code=404, detail=f"Pack not found: {pack_name}")
        
        from .models import Pack
        pack = Pack.model_validate_json(pack_json.read_text())
        
        # Detect architecture from base_model
        architecture = _detect_architecture(pack)
        
        # Get checkpoint and lora dependencies
        checkpoint_dep = None
        lora_deps = []
        
        for dep in pack.dependencies:
            if dep.kind == AssetKind.CHECKPOINT:
                checkpoint_dep = dep
            elif dep.kind == AssetKind.LORA:
                lora_deps.append(dep)
        
        # Build workflow
        workflow = _build_v2_workflow(
            pack=pack,
            architecture=architecture,
            checkpoint_dep=checkpoint_dep,
            lora_deps=lora_deps,
        )
        
        # Save workflow file
        workflows_dir = store.layout.pack_workflows_path(pack_name)
        workflows_dir.mkdir(parents=True, exist_ok=True)
        
        safe_name = pack_name.replace("[", "_").replace("]", "_").replace(" ", "_")
        workflow_filename = f"default_{safe_name}.json"
        workflow_path = workflows_dir / workflow_filename
        
        with open(workflow_path, "w", encoding="utf-8") as f:
            json.dump(workflow, f, indent=2)
        
        # Add workflow info to pack.json
        workflow_info = WorkflowInfo(
            name=f"Default - {pack.name}",
            filename=workflow_filename,
            description="Auto-generated default workflow based on pack parameters",
            is_default=True,
        )
        
        # Remove existing default workflows
        pack.workflows = [w for w in pack.workflows if not w.is_default]
        pack.workflows.append(workflow_info)
        
        # Save pack.json
        with open(pack_json, "w", encoding="utf-8") as f:
            f.write(pack.model_dump_json(indent=2, by_alias=True, exclude_none=True))
        
        logger.info(f"[generate-workflow] Generated: {workflow_filename} for {pack_name}")
        
        return {
            "generated": True,
            "message": "Default workflow generated successfully",
            "workflow_filename": workflow_filename,
            "pack_name": pack_name,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[generate-workflow] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _detect_architecture(pack) -> str:
    """Detect architecture from pack's base model."""
    BASE_MODEL_ARCHITECTURE = {
        "SD 1.5": "sd15",
        "SD 1.4": "sd15",
        "SD 2.0": "sd20",
        "SD 2.1": "sd21",
        "SDXL 1.0": "sdxl",
        "SDXL": "sdxl",
        "SDXL Turbo": "sdxl",
        "SDXL Lightning": "sdxl",
        "Pony": "sdxl",
        "Illustrious": "sdxl",
        "NoobAI": "sdxl",
        "Flux.1 D": "flux",
        "Flux.1 S": "flux",
        "Flux": "flux",
        "AuraFlow": "auraflow",
    }
    
    # Check pack.base_model first
    if pack.base_model:
        for key, arch in BASE_MODEL_ARCHITECTURE.items():
            if key.lower() in pack.base_model.lower():
                return arch
    
    # Check model_info.base_model
    if pack.model_info and pack.model_info.base_model:
        for key, arch in BASE_MODEL_ARCHITECTURE.items():
            if key.lower() in pack.model_info.base_model.lower():
                return arch
    
    # Check dependency selectors for base_model
    for dep in pack.dependencies:
        if dep.selector and dep.selector.base_model:
            for key, arch in BASE_MODEL_ARCHITECTURE.items():
                if key.lower() in dep.selector.base_model.lower():
                    return arch
    
    return "sd15"


def _build_v2_workflow(pack, architecture: str, checkpoint_dep, lora_deps) -> Dict[str, Any]:
    """Build ComfyUI workflow for v2 pack."""
    # Sampler mapping
    SAMPLER_MAPPING = {
        "Euler": "euler",
        "Euler a": "euler_ancestral",
        "DPM++ 2M": "dpmpp_2m",
        "DPM++ 2M Karras": "dpmpp_2m",
        "DPM++ 2M SDE": "dpmpp_2m_sde",
        "DPM++ 2M SDE Karras": "dpmpp_2m_sde",
        "DPM++ 3M SDE": "dpmpp_3m_sde",
        "DPM++ 3M SDE Karras": "dpmpp_3m_sde",
        "DDIM": "ddim",
    }
    
    SCHEDULER_MAPPING = {
        "Euler": "normal",
        "Euler a": "normal",
        "DPM++ 2M": "normal",
        "DPM++ 2M Karras": "karras",
        "DPM++ 2M SDE": "normal",
        "DPM++ 2M SDE Karras": "karras",
        "DPM++ 3M SDE": "normal",
        "DPM++ 3M SDE Karras": "karras",
        "DDIM": "ddim_uniform",
    }
    
    # Get parameters
    params = pack.parameters or GenerationParameters()
    
    # Dimensions based on architecture
    if architecture == "sdxl":
        default_width, default_height = 1024, 1024
    elif architecture == "flux":
        default_width, default_height = 1024, 1024
    else:
        default_width, default_height = 512, 512
    
    width = params.width or default_width
    height = params.height or default_height
    sampler = SAMPLER_MAPPING.get(params.sampler, "euler") if params.sampler else "euler"
    scheduler = SCHEDULER_MAPPING.get(params.sampler, "normal") if params.sampler else "normal"
    steps = params.steps or 20
    cfg = params.cfg_scale or 7.0
    seed = params.seed if params.seed and params.seed >= 0 else 0
    
    # Get checkpoint filename
    ckpt_filename = "model.safetensors"
    if checkpoint_dep and checkpoint_dep.expose and checkpoint_dep.expose.filename:
        ckpt_filename = checkpoint_dep.expose.filename
    
    # Build trigger words
    trigger_words = ""
    if pack.trigger_words:
        trigger_words = ", ".join(pack.trigger_words) + ", "
    elif pack.model_info and pack.model_info.trigger_words:
        trigger_words = ", ".join(pack.model_info.trigger_words) + ", "
    
    # Build prompts
    positive_prompt = f"{trigger_words}masterpiece, best quality, "
    negative_prompt = "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, jpeg artifacts, signature, watermark, blurry"
    
    # Node ID counter
    node_id = 1
    link_id = 1
    nodes = []
    links = []
    
    # 1. CheckpointLoaderSimple
    ckpt_node_id = node_id
    nodes.append({
        "id": ckpt_node_id,
        "type": "CheckpointLoaderSimple",
        "pos": [50, 100],
        "size": [315, 98],
        "flags": {},
        "order": 0,
        "mode": 0,
        "outputs": [
            {"name": "MODEL", "type": "MODEL", "links": [], "slot_index": 0},
            {"name": "CLIP", "type": "CLIP", "links": [], "slot_index": 1},
            {"name": "VAE", "type": "VAE", "links": [], "slot_index": 2}
        ],
        "properties": {"Node name for S&R": "CheckpointLoaderSimple"},
        "widgets_values": [ckpt_filename]
    })
    node_id += 1
    
    current_model_node = ckpt_node_id
    current_model_slot = 0
    current_clip_node = ckpt_node_id
    current_clip_slot = 1
    vae_node = ckpt_node_id
    vae_slot = 2
    
    # 2. LoRA Loaders
    for i, lora in enumerate(lora_deps):
        lora_filename = "lora.safetensors"
        if lora.expose and lora.expose.filename:
            lora_filename = lora.expose.filename
        
        strength = 1.0
        if pack.model_info and pack.model_info.strength_recommended:
            strength = pack.model_info.strength_recommended
        
        lora_node_id = node_id
        nodes.append({
            "id": lora_node_id,
            "type": "LoraLoader",
            "pos": [400, 100 + i * 200],
            "size": [315, 126],
            "flags": {},
            "order": i + 1,
            "mode": 0,
            "inputs": [
                {"name": "model", "type": "MODEL", "link": None},
                {"name": "clip", "type": "CLIP", "link": None}
            ],
            "outputs": [
                {"name": "MODEL", "type": "MODEL", "links": [], "slot_index": 0},
                {"name": "CLIP", "type": "CLIP", "links": [], "slot_index": 1}
            ],
            "properties": {"Node name for S&R": "LoraLoader"},
            "widgets_values": [lora_filename, strength, strength]
        })
        
        # Connect MODEL
        links.append([link_id, current_model_node, current_model_slot, lora_node_id, 0, "MODEL"])
        nodes[current_model_node - 1]["outputs"][current_model_slot]["links"].append(link_id)
        nodes[-1]["inputs"][0]["link"] = link_id
        link_id += 1
        
        # Connect CLIP
        links.append([link_id, current_clip_node, current_clip_slot, lora_node_id, 1, "CLIP"])
        nodes[current_clip_node - 1]["outputs"][current_clip_slot]["links"].append(link_id)
        nodes[-1]["inputs"][1]["link"] = link_id
        link_id += 1
        
        current_model_node = lora_node_id
        current_model_slot = 0
        current_clip_node = lora_node_id
        current_clip_slot = 1
        
        node_id += 1
    
    # 3. CLIP Skip (only if needed)
    clip_skip = params.clip_skip
    if clip_skip and clip_skip > 1:
        clip_skip_node_id = node_id
        nodes.append({
            "id": clip_skip_node_id,
            "type": "CLIPSetLastLayer",
            "pos": [600, 200],
            "size": [315, 58],
            "flags": {},
            "order": len(lora_deps) + 1,
            "mode": 0,
            "inputs": [
                {"name": "clip", "type": "CLIP", "link": None}
            ],
            "outputs": [
                {"name": "CLIP", "type": "CLIP", "links": [], "slot_index": 0}
            ],
            "properties": {"Node name for S&R": "CLIPSetLastLayer"},
            "widgets_values": [-clip_skip]
        })
        
        # Connect CLIP
        links.append([link_id, current_clip_node, current_clip_slot, clip_skip_node_id, 0, "CLIP"])
        nodes[current_clip_node - 1]["outputs"][current_clip_slot]["links"].append(link_id)
        nodes[-1]["inputs"][0]["link"] = link_id
        link_id += 1
        
        current_clip_node = clip_skip_node_id
        current_clip_slot = 0
        node_id += 1
    
    base_order = len(lora_deps) + (2 if clip_skip and clip_skip > 1 else 1)
    
    # 4. CLIP Text Encode (Positive)
    pos_node_id = node_id
    nodes.append({
        "id": pos_node_id,
        "type": "CLIPTextEncode",
        "pos": [700, 100],
        "size": [425, 180],
        "flags": {},
        "order": base_order,
        "mode": 0,
        "inputs": [
            {"name": "clip", "type": "CLIP", "link": None}
        ],
        "outputs": [
            {"name": "CONDITIONING", "type": "CONDITIONING", "links": [], "slot_index": 0}
        ],
        "properties": {"Node name for S&R": "CLIPTextEncode"},
        "widgets_values": [positive_prompt],
        "title": "Positive Prompt"
    })
    
    links.append([link_id, current_clip_node, current_clip_slot, pos_node_id, 0, "CLIP"])
    nodes[current_clip_node - 1]["outputs"][current_clip_slot]["links"].append(link_id)
    nodes[-1]["inputs"][0]["link"] = link_id
    link_id += 1
    node_id += 1
    
    # 5. CLIP Text Encode (Negative)
    neg_node_id = node_id
    nodes.append({
        "id": neg_node_id,
        "type": "CLIPTextEncode",
        "pos": [700, 300],
        "size": [425, 180],
        "flags": {},
        "order": base_order + 1,
        "mode": 0,
        "inputs": [
            {"name": "clip", "type": "CLIP", "link": None}
        ],
        "outputs": [
            {"name": "CONDITIONING", "type": "CONDITIONING", "links": [], "slot_index": 0}
        ],
        "properties": {"Node name for S&R": "CLIPTextEncode"},
        "widgets_values": [negative_prompt],
        "title": "Negative Prompt"
    })
    
    # Connect CLIP from same source as positive
    links.append([link_id, current_clip_node, current_clip_slot, neg_node_id, 0, "CLIP"])
    nodes[current_clip_node - 1]["outputs"][current_clip_slot]["links"].append(link_id)
    nodes[-1]["inputs"][0]["link"] = link_id
    link_id += 1
    node_id += 1
    
    # 6. EmptyLatentImage
    latent_node_id = node_id
    nodes.append({
        "id": latent_node_id,
        "type": "EmptyLatentImage",
        "pos": [700, 500],
        "size": [315, 106],
        "flags": {},
        "order": base_order + 2,
        "mode": 0,
        "outputs": [
            {"name": "LATENT", "type": "LATENT", "links": [], "slot_index": 0}
        ],
        "properties": {"Node name for S&R": "EmptyLatentImage"},
        "widgets_values": [width, height, 1]
    })
    node_id += 1
    
    # 7. KSampler
    sampler_node_id = node_id
    nodes.append({
        "id": sampler_node_id,
        "type": "KSampler",
        "pos": [1200, 200],
        "size": [315, 262],
        "flags": {},
        "order": base_order + 3,
        "mode": 0,
        "inputs": [
            {"name": "model", "type": "MODEL", "link": None},
            {"name": "positive", "type": "CONDITIONING", "link": None},
            {"name": "negative", "type": "CONDITIONING", "link": None},
            {"name": "latent_image", "type": "LATENT", "link": None}
        ],
        "outputs": [
            {"name": "LATENT", "type": "LATENT", "links": [], "slot_index": 0}
        ],
        "properties": {"Node name for S&R": "KSampler"},
        "widgets_values": [seed, "randomize", steps, cfg, sampler, scheduler, 1.0]
    })
    
    # Connect model
    links.append([link_id, current_model_node, current_model_slot, sampler_node_id, 0, "MODEL"])
    nodes[current_model_node - 1]["outputs"][current_model_slot]["links"].append(link_id)
    nodes[-1]["inputs"][0]["link"] = link_id
    link_id += 1
    
    # Connect positive conditioning
    links.append([link_id, pos_node_id, 0, sampler_node_id, 1, "CONDITIONING"])
    nodes[pos_node_id - 1]["outputs"][0]["links"].append(link_id)
    nodes[-1]["inputs"][1]["link"] = link_id
    link_id += 1
    
    # Connect negative conditioning
    links.append([link_id, neg_node_id, 0, sampler_node_id, 2, "CONDITIONING"])
    nodes[neg_node_id - 1]["outputs"][0]["links"].append(link_id)
    nodes[-1]["inputs"][2]["link"] = link_id
    link_id += 1
    
    # Connect latent
    links.append([link_id, latent_node_id, 0, sampler_node_id, 3, "LATENT"])
    nodes[latent_node_id - 1]["outputs"][0]["links"].append(link_id)
    nodes[-1]["inputs"][3]["link"] = link_id
    link_id += 1
    node_id += 1
    
    # 8. VAEDecode
    vae_decode_node_id = node_id
    nodes.append({
        "id": vae_decode_node_id,
        "type": "VAEDecode",
        "pos": [1550, 200],
        "size": [210, 46],
        "flags": {},
        "order": base_order + 4,
        "mode": 0,
        "inputs": [
            {"name": "samples", "type": "LATENT", "link": None},
            {"name": "vae", "type": "VAE", "link": None}
        ],
        "outputs": [
            {"name": "IMAGE", "type": "IMAGE", "links": [], "slot_index": 0}
        ],
        "properties": {"Node name for S&R": "VAEDecode"}
    })
    
    # Connect samples from KSampler
    links.append([link_id, sampler_node_id, 0, vae_decode_node_id, 0, "LATENT"])
    nodes[sampler_node_id - 1]["outputs"][0]["links"].append(link_id)
    nodes[-1]["inputs"][0]["link"] = link_id
    link_id += 1
    
    # Connect VAE
    links.append([link_id, vae_node, vae_slot, vae_decode_node_id, 1, "VAE"])
    nodes[vae_node - 1]["outputs"][vae_slot]["links"].append(link_id)
    nodes[-1]["inputs"][1]["link"] = link_id
    link_id += 1
    node_id += 1
    
    # 9. SaveImage
    save_node_id = node_id
    nodes.append({
        "id": save_node_id,
        "type": "SaveImage",
        "pos": [1800, 200],
        "size": [315, 270],
        "flags": {},
        "order": base_order + 5,
        "mode": 0,
        "inputs": [
            {"name": "images", "type": "IMAGE", "link": None}
        ],
        "properties": {"Node name for S&R": "SaveImage"},
        "widgets_values": ["ComfyUI"]
    })
    
    # Connect IMAGE
    links.append([link_id, vae_decode_node_id, 0, save_node_id, 0, "IMAGE"])
    nodes[vae_decode_node_id - 1]["outputs"][0]["links"].append(link_id)
    nodes[-1]["inputs"][0]["link"] = link_id
    
    # Build final workflow
    return {
        "last_node_id": save_node_id,
        "last_link_id": link_id,
        "nodes": nodes,
        "links": links,
        "groups": [],
        "config": {},
        "extra": {
            "ds": {"scale": 1.0, "offset": [0, 0]},
            "synapse": {
                "pack_name": pack.name,
                "generated": True,
                "architecture": architecture,
            }
        },
        "version": 0.4
    }


@v2_packs_router.post("/{pack_name}/workflow/symlink", response_model=Dict[str, Any])
def create_workflow_symlink(
    pack_name: str,
    store=Depends(require_initialized),
):
    """Create symlinks for all pack workflows to ComfyUI."""
    try:
        from config.settings import get_config
        import json
        
        config = get_config()
        
        # Load pack
        pack_dir = store.layout.pack_path(pack_name)
        pack_json = pack_dir / "pack.json"
        
        if not pack_json.exists():
            raise HTTPException(status_code=404, detail=f"Pack not found: {pack_name}")
        
        from .models import Pack
        pack = Pack.model_validate_json(pack_json.read_text())
        
        # ComfyUI workflows folder
        comfyui_workflows = config.comfyui.base_path / "user" / "default" / "workflows"
        comfyui_workflows.mkdir(parents=True, exist_ok=True)
        
        workflows_dir = store.layout.pack_workflows_path(pack_name)
        created = []
        
        for wf in pack.workflows:
            source = workflows_dir / wf.filename
            if not source.exists():
                continue
            
            # Create symlink with pack prefix to avoid conflicts
            symlink_name = f"[{pack_name}] {wf.filename}"
            symlink_path = comfyui_workflows / symlink_name
            
            # Remove existing symlink
            if symlink_path.exists() or symlink_path.is_symlink():
                symlink_path.unlink()
            
            # Create new symlink
            symlink_path.symlink_to(source)
            created.append(symlink_name)
        
        logger.info(f"[workflow-symlink] Created {len(created)} symlinks for {pack_name}")
        
        return {
            "created": True,
            "pack_name": pack_name,
            "symlinks": created,
            "target_dir": str(comfyui_workflows),
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[workflow-symlink] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@v2_packs_router.post("/{pack_name}/workflow/{filename}/symlink", response_model=Dict[str, Any])
def create_specific_workflow_symlink(
    pack_name: str,
    filename: str,
    store=Depends(require_initialized),
):
    """Create symlink for specific workflow."""
    try:
        from config.settings import get_config
        
        config = get_config()
        
        workflows_dir = store.layout.pack_workflows_path(pack_name)
        source = workflows_dir / filename
        
        if not source.exists():
            raise HTTPException(status_code=404, detail=f"Workflow not found: {filename}")
        
        # ComfyUI workflows folder
        comfyui_workflows = config.comfyui.base_path / "user" / "default" / "workflows"
        comfyui_workflows.mkdir(parents=True, exist_ok=True)
        
        # Create symlink with pack prefix
        symlink_name = f"[{pack_name}] {filename}"
        symlink_path = comfyui_workflows / symlink_name
        
        # Remove existing symlink
        if symlink_path.exists() or symlink_path.is_symlink():
            symlink_path.unlink()
        
        # Create new symlink
        symlink_path.symlink_to(source)
        
        logger.info(f"[workflow-symlink] Created symlink: {symlink_name}")
        
        return {
            "created": True,
            "symlink": symlink_name,
            "source": str(source),
            "target": str(symlink_path),
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[workflow-symlink] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@v2_packs_router.get("/{pack_name}/workflow/{filename}", response_model=Dict[str, Any])
def get_workflow_content(
    pack_name: str,
    filename: str,
    store=Depends(require_initialized),
):
    """Get workflow JSON content."""
    try:
        workflows_dir = store.layout.pack_workflows_path(pack_name)
        workflow_file = workflows_dir / filename
        
        if not workflow_file.exists():
            raise HTTPException(status_code=404, detail=f"Workflow not found: {filename}")
        
        import json
        content = json.loads(workflow_file.read_text())
        
        return {
            "filename": filename,
            "content": content,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@v2_packs_router.delete("/{pack_name}/workflow/{filename}", response_model=Dict[str, Any])
def delete_workflow(
    pack_name: str,
    filename: str,
    store=Depends(require_initialized),
):
    """Delete a workflow file from pack and remove from pack.json."""
    try:
        import json
        
        workflows_dir = store.layout.pack_workflows_path(pack_name)
        workflow_file = workflows_dir / filename
        
        if not workflow_file.exists():
            raise HTTPException(status_code=404, detail=f"Workflow not found: {filename}")
        
        # Delete the workflow file
        workflow_file.unlink()
        
        # Also delete symlink if exists (in ComfyUI workflows folder)
        from config.settings import get_config
        config = get_config()
        comfyui_workflows = config.comfyui.base_path / "user" / "default" / "workflows"
        
        # Try both formats for symlink
        symlink_path1 = comfyui_workflows / filename
        symlink_path2 = comfyui_workflows / f"[{pack_name}] {filename}"
        
        for symlink_path in [symlink_path1, symlink_path2]:
            if symlink_path.is_symlink():
                symlink_path.unlink()
        
        # Remove from pack.json
        pack_dir = store.layout.pack_path(pack_name)
        pack_json = pack_dir / "pack.json"
        
        if pack_json.exists():
            from .models import Pack
            pack = Pack.model_validate_json(pack_json.read_text())
            pack.workflows = [w for w in pack.workflows if w.filename != filename]
            
            with open(pack_json, "w", encoding="utf-8") as f:
                f.write(pack.model_dump_json(indent=2, by_alias=True, exclude_none=True))
        
        logger.info(f"[delete-workflow] Deleted: {filename} from {pack_name}")
        
        return {
            "deleted": filename,
            "pack_name": pack_name,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class AddWorkflowRequest(BaseModel):
    """Request to add workflow info to pack.json."""
    name: str
    filename: str
    description: Optional[str] = None
    source_url: Optional[str] = None
    is_default: bool = False


@v2_packs_router.post("/{pack_name}/workflow/add", response_model=Dict[str, Any])
def add_workflow_to_pack(
    pack_name: str,
    request: AddWorkflowRequest,
    store=Depends(require_initialized),
):
    """Add workflow info to pack.json (workflow file must exist)."""
    try:
        # Check if workflow file exists
        workflows_dir = store.layout.pack_workflows_path(pack_name)
        workflow_file = workflows_dir / request.filename
        
        if not workflow_file.exists():
            raise HTTPException(
                status_code=404, 
                detail=f"Workflow file not found: {request.filename}. Upload the file first."
            )
        
        # Load pack
        pack_dir = store.layout.pack_path(pack_name)
        pack_json = pack_dir / "pack.json"
        
        if not pack_json.exists():
            raise HTTPException(status_code=404, detail=f"Pack not found: {pack_name}")
        
        from .models import Pack
        pack = Pack.model_validate_json(pack_json.read_text())
        
        # Remove existing workflow with same filename if exists
        pack.workflows = [w for w in pack.workflows if w.filename != request.filename]
        
        # Add new workflow info
        workflow_info = WorkflowInfo(
            name=request.name,
            filename=request.filename,
            description=request.description,
            source_url=request.source_url,
            is_default=request.is_default,
        )
        
        # If is_default, remove other defaults
        if request.is_default:
            pack.workflows = [w for w in pack.workflows if not w.is_default]
        
        pack.workflows.append(workflow_info)
        
        # Save pack.json
        with open(pack_json, "w", encoding="utf-8") as f:
            f.write(pack.model_dump_json(indent=2, by_alias=True, exclude_none=True))
        
        logger.info(f"[add-workflow] Added: {request.filename} to {pack_name}")
        
        return {
            "added": True,
            "workflow": workflow_info.model_dump(),
            "pack_name": pack_name,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class RenameWorkflowRequest(BaseModel):
    """Request to rename a workflow."""
    new_name: Optional[str] = None  # Display name in pack.json
    new_filename: Optional[str] = None  # Actual file name


@v2_packs_router.patch("/{pack_name}/workflow/{filename}", response_model=Dict[str, Any])
def rename_workflow(
    pack_name: str,
    filename: str,
    request: RenameWorkflowRequest,
    store=Depends(require_initialized),
):
    """Rename a workflow (display name and/or filename)."""
    try:
        import shutil
        
        workflows_dir = store.layout.pack_workflows_path(pack_name)
        workflow_file = workflows_dir / filename
        
        if not workflow_file.exists():
            raise HTTPException(status_code=404, detail=f"Workflow not found: {filename}")
        
        # Load pack
        pack_dir = store.layout.pack_path(pack_name)
        pack_json = pack_dir / "pack.json"
        
        if not pack_json.exists():
            raise HTTPException(status_code=404, detail=f"Pack not found: {pack_name}")
        
        from .models import Pack
        pack = Pack.model_validate_json(pack_json.read_text())
        
        # Find workflow in pack.workflows
        workflow_idx = None
        for i, w in enumerate(pack.workflows):
            if w.filename == filename:
                workflow_idx = i
                break
        
        old_filename = filename
        new_filename = request.new_filename or filename
        
        # Rename file if new_filename provided
        if request.new_filename and request.new_filename != filename:
            # Ensure it ends with .json
            if not new_filename.endswith(".json"):
                new_filename += ".json"
            
            new_path = workflows_dir / new_filename
            if new_path.exists():
                raise HTTPException(status_code=400, detail=f"Workflow already exists: {new_filename}")
            
            workflow_file.rename(new_path)
            
            # Update symlink if exists
            from config.settings import get_config
            config = get_config()
            comfyui_workflows = config.comfyui.base_path / "user" / "default" / "workflows"
            
            old_symlink = comfyui_workflows / f"[{pack_name}] {old_filename}"
            if old_symlink.is_symlink():
                old_symlink.unlink()
                new_symlink = comfyui_workflows / f"[{pack_name}] {new_filename}"
                new_symlink.symlink_to(new_path)
        
        # Update pack.workflows
        if workflow_idx is not None:
            if request.new_name:
                pack.workflows[workflow_idx].name = request.new_name
            if request.new_filename:
                pack.workflows[workflow_idx].filename = new_filename
        
        # Save pack.json
        with open(pack_json, "w", encoding="utf-8") as f:
            f.write(pack.model_dump_json(indent=2, by_alias=True, exclude_none=True))
        
        logger.info(f"[rename-workflow] Renamed: {filename} -> {new_filename} in {pack_name}")
        
        return {
            "renamed": True,
            "old_filename": old_filename,
            "new_filename": new_filename,
            "new_name": request.new_name,
            "pack_name": pack_name,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@v2_packs_router.post("/{pack_name}/workflow/upload-file", response_model=Dict[str, Any])
def upload_workflow_file(
    pack_name: str,
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    is_default: bool = Form(False),
    store=Depends(require_initialized),
):
    """Upload a workflow file to pack and optionally add to pack.json."""
    try:
        import json
        
        workflows_dir = store.layout.pack_workflows_path(pack_name)
        workflows_dir.mkdir(parents=True, exist_ok=True)
        
        # Save file
        dest_path = workflows_dir / file.filename
        content = file.file.read()
        
        # Validate JSON
        try:
            json.loads(content)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON file")
        
        dest_path.write_bytes(content)
        
        # Add to pack.json if name provided
        if name:
            pack_dir = store.layout.pack_path(pack_name)
            pack_json = pack_dir / "pack.json"
            
            if pack_json.exists():
                from .models import Pack
                pack = Pack.model_validate_json(pack_json.read_text())
                
                # Remove existing with same filename
                pack.workflows = [w for w in pack.workflows if w.filename != file.filename]
                
                # Remove other defaults if this is default
                if is_default:
                    pack.workflows = [w for w in pack.workflows if not w.is_default]
                
                # Add new workflow info
                workflow_info = WorkflowInfo(
                    name=name,
                    filename=file.filename,
                    description=description,
                    is_default=is_default,
                )
                pack.workflows.append(workflow_info)
                
                # Save pack.json
                with open(pack_json, "w", encoding="utf-8") as f:
                    f.write(pack.model_dump_json(indent=2, by_alias=True, exclude_none=True))
        
        return {
            "uploaded": True,
            "filename": file.filename,
            "path": str(dest_path),
            "added_to_pack": name is not None,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Profiles Router
# =============================================================================

profiles_router = APIRouter(tags=["profiles"])


@profiles_router.get("/", response_model=Dict[str, Any])
def list_profiles(store=Depends(require_initialized)):
    """List all profiles."""
    profiles = store.list_profiles()
    return {"profiles": profiles}


@profiles_router.get("/status", response_model=ProfilesStatusResponse)
def get_profiles_status(
    ui_set: Optional[str] = Query(None),
    store=Depends(require_initialized),
):
    """
    Get complete profiles status for UI display.
    
    Returns per-UI runtime status, stack visualization, and shadowed files.
    """
    try:
        ui_targets = store.get_ui_targets(ui_set)
        
        # Load runtime directly for stack info
        runtime = store.layout.load_runtime()
        
        # Build per-UI status list
        ui_statuses = []
        for ui in ui_targets:
            stack = runtime.get_stack(ui)
            active = runtime.get_active_profile(ui)
            ui_statuses.append(UIRuntimeStatus(
                ui=ui,
                active_profile=active,
                stack=stack,
                stack_depth=len(stack),
            ))
        
        # Get status for shadowed info
        status = store.status(ui_set=ui_set)
        
        # Convert shadowed entries to dicts
        all_shadowed = []
        for entry in status.shadowed:
            all_shadowed.append({
                "ui": entry.ui if hasattr(entry, 'ui') else ui_targets[0] if ui_targets else "unknown",
                "dst_relpath": entry.dst_relpath,
                "winner_pack": entry.winner_pack,
                "loser_pack": entry.loser_pack,
            })
        
        # Count available updates (from cached check or 0)
        updates_count = getattr(store, "_cached_updates_count", 0)
        
        return ProfilesStatusResponse(
            ui_statuses=ui_statuses,
            shadowed=all_shadowed,
            shadowed_count=len(all_shadowed),
            updates_available=updates_count,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@profiles_router.post("/use", response_model=Dict[str, Any])
def use_pack(
    request: UseRequest,
    store=Depends(require_initialized),
):
    """Activate a work profile for a pack."""
    try:
        result = store.use(
            request.pack,
            ui_set=request.ui_set,
            sync=request.sync,
        )
        return result.model_dump()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@profiles_router.post("/back", response_model=Dict[str, Any])
def back_profile(
    request: BackRequest,
    store=Depends(require_initialized),
):
    """Go back to previous profile."""
    try:
        result = store.back(
            ui_set=request.ui_set,
            sync=request.sync,
        )
        return result.model_dump()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@profiles_router.post("/sync", response_model=SyncResponse)
def sync_profile(
    request: SyncRequest,
    store=Depends(require_initialized),
):
    """Sync a profile: install missing blobs and rebuild views."""
    try:
        reports = store.sync(
            profile_name=request.profile,
            ui_set=request.ui_set,
            install_missing=request.install_missing,
        )
        return SyncResponse(
            reports={ui: {
                "entries_created": r.entries_created,
                "shadowed_count": len(r.shadowed),
                "missing_count": len(r.missing_blobs),
                "errors": r.errors,
            } for ui, r in reports.items()}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@profiles_router.post("/reset", response_model=Dict[str, Any])
def reset_to_global(
    request: ResetRequest,
    store=Depends(require_initialized),
):
    """
    Reset stack to global for all UIs in ui_set.
    
    This pops all work profiles and returns to just ["global"].
    Operation is atomic under store lock.
    """
    try:
        results = {}
        ui_targets = store.get_ui_targets(request.ui_set)
        
        # Atomic operation under lock
        with store.layout.lock():
            runtime = store.layout.load_runtime()
            
            for ui in ui_targets:
                # Reset stack to just global
                runtime.set_stack(ui, ["global"])
                results[ui] = {
                    "reset": True,
                    "profile": "global",
                }
            
            # Save runtime
            store.layout.save_runtime(runtime)
            
            # Update active symlinks
            for ui in ui_targets:
                store.view_builder.activate_profile("global", ui)
        
        # Sync once at the end if requested (outside lock to avoid long hold)
        if request.sync:
            store.sync(ui_set=request.ui_set)
        
        return {
            "ok": True,
            "reset": True,
            "ui_results": results,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# NOTE: This wildcard route MUST be last in the profiles router
# to avoid shadowing specific routes like /status, /use, /back, etc.
@profiles_router.get("/{profile_name}", response_model=Dict[str, Any])
def get_profile(profile_name: str, store=Depends(require_initialized)):
    """Get profile details."""
    try:
        profile = store.load_profile(profile_name)
        return profile.model_dump()
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


# =============================================================================
# Updates Router
# =============================================================================

updates_router = APIRouter(tags=["updates"])


@updates_router.get("/plan", response_model=Dict[str, Any])
def get_update_plan(
    pack: Optional[str] = Query(None),
    store=Depends(require_initialized),
):
    """Get update plan for a pack (or all packs if pack is None)."""
    try:
        if pack is None:
            # Get all packs
            plans = store.check_all_updates()
            return {
                name: plan.model_dump()
                for name, plan in plans.items()
            }
        else:
            # Get single pack
            plan = store.check_updates(pack)
            return {pack: plan.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@updates_router.get("/check/{pack_name}", response_model=UpdateCheckResponse)
def check_pack_updates(
    pack_name: str,
    store=Depends(require_initialized),
):
    """Check if a specific pack has updates available."""
    try:
        plan = store.check_updates(pack_name)
        plan_dict = plan.model_dump()
        changes_count = len(plan_dict.get("changes", []))
        ambiguous_count = len(plan_dict.get("ambiguous", []))
        
        return UpdateCheckResponse(
            pack=pack_name,
            has_updates=changes_count > 0 or ambiguous_count > 0,
            changes_count=changes_count,
            ambiguous_count=ambiguous_count,
            plan=plan_dict,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@updates_router.get("/check-all", response_model=BulkUpdateCheckResponse)
def check_all_updates(store=Depends(require_initialized)):
    """Check all packs for available updates."""
    try:
        plans = store.check_all_updates()
        
        packs_with_updates = 0
        total_changes = 0
        plans_dict = {}
        
        for name, plan in plans.items():
            plan_dict = plan.model_dump()
            changes = len(plan_dict.get("changes", []))
            ambiguous = len(plan_dict.get("ambiguous", []))
            
            if changes > 0 or ambiguous > 0:
                packs_with_updates += 1
                total_changes += changes + ambiguous
                plans_dict[name] = plan_dict
        
        # Cache the count for profiles status endpoint
        store._cached_updates_count = packs_with_updates
        
        return BulkUpdateCheckResponse(
            packs_checked=len(plans),
            packs_with_updates=packs_with_updates,
            total_changes=total_changes,
            plans=plans_dict,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@updates_router.post("/apply", response_model=Dict[str, Any])
def apply_update(
    request: UpdateRequest,
    store=Depends(require_initialized),
):
    """Apply update to a pack."""
    try:
        result = store.update(
            request.pack,
            dry_run=request.dry_run,
            choose=request.choose,
            sync=request.sync,
            ui_set=request.ui_set,
        )
        return result.model_dump()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Search Router
# =============================================================================

search_router = APIRouter(tags=["search"])


@search_router.get("/", response_model=Dict[str, Any])
def search_packs(
    q: str = Query(..., description="Search query"),
    store=Depends(require_initialized),
):
    """Search packs by name or metadata."""
    result = store.search(q)
    return result.model_dump()


# =============================================================================
# Router Factory
# =============================================================================

def create_store_routers() -> List[APIRouter]:
    """
    Create all store routers.
    
    Returns:
        List of APIRouter instances to be included in FastAPI app
    """
    return [
        store_router,
        v2_packs_router,
        profiles_router,
        updates_router,
        search_router,
    ]
