"""
Packs Router

Full CRUD operations for Synapse packs including:
- List, get, create, update, delete packs
- User tags management
- Preview image serving from resources
- Default workflow generation
- Download tracking with SSE progress
"""

import logging
import asyncio
from datetime import datetime
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks, Body
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path
import json
import shutil
import time

from src.core.models import (
    Pack, AssetType, AssetSource, ASSET_TYPE_FOLDERS,
    DependencyStatus, GenerationParameters, WorkflowInfo
)
from src.core.registry import PackRegistry
from src.core.pack_builder import PackBuilder
from src.core.validator import PackValidator
from src.workflows.generator import WorkflowGenerator
from config.settings import get_config

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Asset Validation Utilities
# ============================================================================

def validate_asset_file(
    asset_type: AssetType,
    filename: str,
    local_path: Optional[str],
    config
) -> Tuple[bool, Optional[str]]:
    """
    Validate if an asset file exists on disk.
    
    Returns:
        Tuple of (exists: bool, actual_path: str or None)
    """
    # First check local_path if provided
    if local_path:
        path = Path(local_path)
        if path.exists():
            return True, str(path)
    
    # Check standard ComfyUI location
    folder = ASSET_TYPE_FOLDERS.get(asset_type, "")
    if folder and filename:
        standard_path = config.comfyui.base_path / "models" / folder / filename
        if standard_path.exists():
            return True, str(standard_path)
    
    return False, None


def validate_pack_assets(pack: Pack, config) -> List[Dict[str, Any]]:
    """
    Validate all assets in a pack against disk.
    
    Returns list of validation results for each asset.
    """
    results = []
    for dep in pack.dependencies:
        exists, actual_path = validate_asset_file(
            dep.asset_type,
            dep.filename,
            dep.local_path,
            config
        )
        
        # Determine expected status based on validation
        if exists:
            expected_status = DependencyStatus.RESOLVED
        elif dep.url:
            expected_status = DependencyStatus.PENDING
        else:
            expected_status = DependencyStatus.UNRESOLVED
        
        results.append({
            "name": dep.name,
            "asset_type": dep.asset_type.value,
            "filename": dep.filename,
            "exists": exists,
            "actual_path": actual_path,
            "local_path_in_pack": dep.local_path,
            "current_status": dep.status.value,
            "expected_status": expected_status.value,
            "status_correct": dep.status == expected_status,
            "has_url": bool(dep.url),
        })
    
    return results


# ============================================================================
# Global Download Tracking
# ============================================================================

# In-memory tracking of active downloads
_active_downloads: Dict[str, dict] = {}


class DownloadProgress(BaseModel):
    """Download progress info."""
    download_id: str
    pack_name: str
    asset_name: str
    filename: str
    status: str  # pending, downloading, completed, failed
    progress: float  # 0-100
    downloaded_bytes: int
    total_bytes: int
    speed_bps: float
    eta_seconds: Optional[float] = None
    error: Optional[str] = None
    started_at: str
    completed_at: Optional[str] = None
    target_path: Optional[str] = None


def _update_download_progress(
    download_id: str,
    status: str = None,
    downloaded_bytes: int = None,
    total_bytes: int = None,
    error: str = None,
):
    """Update download progress in global tracker."""
    if download_id not in _active_downloads:
        return
    
    d = _active_downloads[download_id]
    
    if status:
        d["status"] = status
    if downloaded_bytes is not None:
        d["downloaded_bytes"] = downloaded_bytes
    if total_bytes is not None:
        d["total_bytes"] = total_bytes
    if error:
        d["error"] = error
        d["status"] = "failed"
    
    # Calculate progress and speed
    if d["total_bytes"] > 0:
        d["progress"] = (d["downloaded_bytes"] / d["total_bytes"]) * 100
    
    elapsed = time.time() - d["_start_time"]
    if elapsed > 0 and d["downloaded_bytes"] > 0:
        d["speed_bps"] = d["downloaded_bytes"] / elapsed
        remaining_bytes = d["total_bytes"] - d["downloaded_bytes"]
        if d["speed_bps"] > 0:
            d["eta_seconds"] = remaining_bytes / d["speed_bps"]
    
    if status == "completed":
        d["completed_at"] = datetime.now().isoformat()
        d["progress"] = 100.0


# ============================================================================
# Response Models
# ============================================================================

class AssetInfo(BaseModel):
    """Asset information."""
    name: str
    asset_type: str
    source: str
    size: Optional[int] = None
    installed: bool = False
    status: str = "unresolved"
    base_model_hint: Optional[str] = None
    url: Optional[str] = None
    filename: Optional[str] = None
    local_path: Optional[str] = None
    version_name: Optional[str] = None  # Civitai version name


class PreviewInfo(BaseModel):
    """Preview image information."""
    filename: str
    url: Optional[str] = None
    nsfw: bool = False
    width: Optional[int] = None
    height: Optional[int] = None
    meta: Optional[Dict[str, Any]] = None


class WorkflowInfoResponse(BaseModel):
    """Workflow information."""
    name: str
    filename: str
    description: Optional[str] = None
    is_default: bool = False
    local_path: Optional[str] = None
    has_symlink: bool = False
    symlink_valid: bool = False
    symlink_path: Optional[str] = None


class CustomNodeInfo(BaseModel):
    """Custom node dependency."""
    name: str
    git_url: Optional[str] = None
    installed: bool = False


class ParametersInfo(BaseModel):
    """Generation parameters."""
    sampler: Optional[str] = None
    scheduler: Optional[str] = None
    steps: Optional[int] = None
    cfg_scale: Optional[float] = None
    clip_skip: Optional[int] = None
    denoise: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None


class ModelInfoResponse(BaseModel):
    """Model info table."""
    model_type: Optional[str] = None
    base_model: Optional[str] = None
    trigger_words: List[str] = []
    usage_tips: Optional[str] = None
    hash_autov2: Optional[str] = None
    civitai_air: Optional[str] = None
    download_count: Optional[int] = None
    rating: Optional[float] = None
    published_at: Optional[str] = None
    strength_recommended: Optional[float] = None


class PackSummary(BaseModel):
    """Pack summary for list view."""
    name: str
    version: str
    description: Optional[str] = None
    installed: bool
    assets_count: int
    previews_count: int
    nsfw_previews_count: int
    source_url: Optional[str] = None
    created_at: Optional[str] = None
    thumbnail: Optional[str] = None
    tags: List[str] = []
    user_tags: List[str] = []
    has_unresolved: bool = False
    model_type: Optional[str] = None  # LORA, Checkpoint, etc.
    base_model: Optional[str] = None  # SD 1.5, SDXL, etc.


class PackDetail(BaseModel):
    """Full pack details."""
    name: str
    version: str
    description: Optional[str] = None
    author: Optional[str] = None
    tags: List[str] = []
    user_tags: List[str] = []
    source_url: Optional[str] = None
    created_at: Optional[str] = None
    installed: bool
    has_unresolved: bool
    assets: List[AssetInfo]
    previews: List[PreviewInfo]
    workflows: List[WorkflowInfoResponse]
    custom_nodes: List[CustomNodeInfo]
    docs: Dict[str, str] = {}
    parameters: Optional[ParametersInfo] = None
    model_info: Optional[ModelInfoResponse] = None


class ImportFromUrlRequest(BaseModel):
    """Request to import from Civitai URL."""
    url: str
    pack_name: Optional[str] = None


class ImportResult(BaseModel):
    """Import result."""
    success: bool
    pack_name: Optional[str] = None
    errors: List[str] = []
    warnings: List[str] = []
    message: str = ""


class ValidationIssue(BaseModel):
    """Validation issue."""
    level: str
    message: str
    asset_name: Optional[str] = None
    suggestion: Optional[str] = None


class ValidationResult(BaseModel):
    """Validation result."""
    valid: bool
    pack_name: str
    issues: List[ValidationIssue]


class UpdatePackRequest(BaseModel):
    """Request to update pack."""
    user_tags: Optional[List[str]] = None
    name: Optional[str] = None  # For rename


class ResolveDependencyRequest(BaseModel):
    """Request to resolve a dependency."""
    dependency_name: str
    source: str  # civitai, huggingface, local
    civitai_model_id: Optional[int] = None
    civitai_version_id: Optional[int] = None
    huggingface_repo: Optional[str] = None
    huggingface_filename: Optional[str] = None
    local_path: Optional[str] = None


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/", response_model=List[PackSummary])
async def list_packs(
    installed_only: bool = False,
    user_tag: Optional[str] = None,
    tag: Optional[str] = None,
):
    """List all registered packs with optional filtering."""
    logger.info("[list_packs] Starting pack listing...")
    print("[list_packs] Starting pack listing...")
    
    config = get_config()
    registry = PackRegistry(config)
    
    # Rescan to catch any new packs
    registry.scan_packs_directory()
    
    entries = registry.list_packs(installed_only=installed_only)
    logger.info(f"[list_packs] Found {len(entries)} pack entries")
    print(f"[list_packs] Found {len(entries)} pack entries")
    
    result = []
    
    for entry in entries:
        logger.debug(f"[list_packs] Processing entry: {entry.name}")
        print(f"[list_packs] Processing entry: {entry.name}")
        
        pack = registry.get_pack(entry.name)
        if not pack:
            logger.warning(f"[list_packs] Could not load pack: {entry.name}")
            print(f"[list_packs] WARNING: Could not load pack: {entry.name}")
            continue
        
        # Filter by user_tag
        if user_tag and user_tag not in pack.metadata.user_tags:
            continue
        
        # Filter by tag
        if tag and tag not in pack.metadata.tags:
            continue
        
        # Count NSFW previews
        nsfw_count = sum(1 for p in pack.previews if p.nsfw)
        
        # Check for unresolved dependencies
        has_unresolved = any(
            dep.status == DependencyStatus.UNRESOLVED 
            for dep in pack.dependencies
        )
        
        # Get first preview as thumbnail (prefer non-NSFW)
        thumbnail = None
        for preview in pack.previews:
            if not preview.nsfw and preview.local_path:
                thumbnail = f"/api/packs/{entry.name}/preview/{preview.filename}"
                break
        # Fallback to any preview
        if not thumbnail and pack.previews:
            preview = pack.previews[0]
            if preview.local_path:
                thumbnail = f"/api/packs/{entry.name}/preview/{preview.filename}"
            elif preview.url:
                thumbnail = preview.url  # Use original URL as fallback
        
        logger.debug(f"[list_packs] Pack {entry.name}: {len(pack.previews)} previews, thumbnail={thumbnail}")
        print(f"[list_packs] Pack {entry.name}: {len(pack.previews)} previews, thumbnail={thumbnail}")
        
        # Get model info
        model_type = None
        base_model_name = None
        if pack.model_info:
            model_type = pack.model_info.model_type
            base_model_name = pack.model_info.base_model
        
        result.append(PackSummary(
            name=pack.metadata.name,
            version=pack.metadata.version,
            description=pack.metadata.description[:200] if pack.metadata.description else None,
            installed=entry.installed,
            assets_count=len(pack.dependencies),
            previews_count=len(pack.previews),
            nsfw_previews_count=nsfw_count,
            source_url=pack.metadata.source_url,
            created_at=pack.metadata.created_at,
            thumbnail=thumbnail,
            tags=pack.metadata.tags[:5],  # Limit for list view
            user_tags=pack.metadata.user_tags,
            has_unresolved=has_unresolved,
            model_type=model_type,
            base_model=base_model_name,
        ))
    
    return result


@router.get("/tags")
async def get_all_tags():
    """Get all unique tags and user_tags across all packs."""
    config = get_config()
    registry = PackRegistry(config)
    
    tags = set()
    user_tags = set()
    
    for entry in registry.list_packs():
        pack = registry.get_pack(entry.name)
        if pack:
            tags.update(pack.metadata.tags)
            user_tags.update(pack.metadata.user_tags)
    
    return {
        "tags": sorted(list(tags)),
        "user_tags": sorted(list(user_tags)),
    }


@router.get("/{pack_name}", response_model=PackDetail)
async def get_pack(pack_name: str):
    """Get pack details."""
    logger.info(f"[get_pack] Fetching pack: {pack_name}")
    print(f"[get_pack] Fetching pack: {pack_name}")
    
    config = get_config()
    registry = PackRegistry(config)
    
    pack = registry.get_pack(pack_name)
    if not pack:
        logger.error(f"[get_pack] Pack not found: {pack_name}")
        print(f"[get_pack] ERROR: Pack not found: {pack_name}")
        raise HTTPException(status_code=404, detail=f"Pack not found: {pack_name}")
    
    logger.info(f"[get_pack] Pack loaded: {pack.metadata.name}")
    print(f"[get_pack] Pack loaded: {pack.metadata.name}")
    print(f"[get_pack] Previews count: {len(pack.previews)}")
    
    entry = registry.registry.entries.get(pack_name)
    
    # Build asset info using validation function
    assets = []
    for dep in pack.dependencies:
        # Use centralized validation
        exists, actual_path = validate_asset_file(
            dep.asset_type,
            dep.filename,
            dep.local_path,
            config
        )
        
        # CRITICAL: installed = file actually exists on disk, regardless of status in pack.json
        installed = exists
        local_path = actual_path
        
        # Debug logging
        print(f"[get_pack] Asset '{dep.name}': filename={dep.filename}, "
              f"local_path_in_pack={dep.local_path}, status={dep.status.value}, "
              f"EXISTS={exists}, actual_path={actual_path}")
        
        # Get version name from civitai info
        version_name = None
        if dep.civitai and dep.civitai.version_name:
            version_name = dep.civitai.version_name
        
        assets.append(AssetInfo(
            name=dep.name,
            asset_type=dep.asset_type.value,
            source=dep.source.value,
            size=dep.file_size,
            installed=installed,
            status=dep.status.value,
            base_model_hint=dep.base_model_hint,
            url=dep.url,
            filename=dep.filename,
            local_path=local_path,
            version_name=version_name,
            description=dep.description,
        ))
    
    # Build preview info - use local resources
    previews = []
    logger.info(f"[get_pack] Building previews for {len(pack.previews)} items")
    print(f"[get_pack] Building previews for {len(pack.previews)} items")
    
    for i, preview in enumerate(pack.previews):
        url = None
        if preview.local_path:
            url = f"/api/packs/{pack_name}/preview/{preview.filename}"
            logger.debug(f"[get_pack] Preview {i}: local_path={preview.local_path}, url={url}")
            print(f"[get_pack] Preview {i}: local_path={preview.local_path}, url={url}")
        elif preview.url:
            url = preview.url  # Fallback to original URL
            logger.debug(f"[get_pack] Preview {i}: using original url={url}")
            print(f"[get_pack] Preview {i}: using original url={url}")
        else:
            logger.warning(f"[get_pack] Preview {i}: NO URL! filename={preview.filename}")
            print(f"[get_pack] Preview {i}: NO URL! filename={preview.filename}")
        
        previews.append(PreviewInfo(
            filename=preview.filename,
            url=url,
            nsfw=preview.nsfw,
            width=preview.width,
            height=preview.height,
            meta=preview.meta,
        ))
    
    # Build workflow info
    workflows = []
    comfyui_workflows_dir = config.comfyui.base_path / "user" / "default" / "workflows"
    
    for wf in pack.workflows:
        # Workflow file path
        workflow_path = entry.pack_path / "workflows" / wf.filename if entry else None
        local_path = str(workflow_path) if workflow_path and workflow_path.exists() else None
        
        # Check symlink status
        symlink_name = f"synapse_{pack_name}_{wf.filename}"
        symlink_path = comfyui_workflows_dir / symlink_name
        has_symlink = symlink_path.is_symlink()
        symlink_valid = has_symlink and symlink_path.exists()
        
        workflows.append(WorkflowInfoResponse(
            name=wf.name,
            filename=wf.filename,
            description=wf.description,
            is_default=wf.is_default,
            local_path=local_path,
            has_symlink=has_symlink,
            symlink_valid=symlink_valid,
            symlink_path=str(symlink_path) if has_symlink else None,
        ))
    
    # Build custom node info
    custom_nodes = []
    for node in pack.custom_nodes:
        installed = False
        if node.name:
            node_path = config.comfyui.base_path / "custom_nodes" / node.name
            installed = node_path.exists()
        
        custom_nodes.append(CustomNodeInfo(
            name=node.name,
            git_url=node.git_url,
            installed=installed,
        ))
    
    # Build parameters info
    parameters = None
    if pack.parameters:
        parameters = ParametersInfo(
            sampler=pack.parameters.sampler,
            scheduler=pack.parameters.scheduler,
            steps=pack.parameters.steps,
            cfg_scale=pack.parameters.cfg_scale,
            clip_skip=pack.parameters.clip_skip,
            denoise=pack.parameters.denoise,
            width=pack.parameters.width,
            height=pack.parameters.height,
        )
    
    # Build model info
    model_info = None
    if pack.model_info:
        model_info = ModelInfoResponse(
            model_type=pack.model_info.model_type,
            base_model=pack.model_info.base_model,
            trigger_words=pack.model_info.trigger_words,
            usage_tips=pack.model_info.usage_tips,
            hash_autov2=pack.model_info.hash_autov2,
            civitai_air=pack.model_info.civitai_air,
            download_count=pack.model_info.download_count,
            rating=pack.model_info.rating,
            published_at=pack.model_info.published_at,
            strength_recommended=pack.model_info.strength_recommended,
        )
    
    # Check for unresolved
    has_unresolved = any(
        dep.status == DependencyStatus.UNRESOLVED 
        for dep in pack.dependencies
    )
    
    return PackDetail(
        name=pack.metadata.name,
        version=pack.metadata.version,
        description=pack.metadata.description,
        author=pack.metadata.author,
        tags=pack.metadata.tags,
        user_tags=pack.metadata.user_tags,
        source_url=pack.metadata.source_url,
        created_at=pack.metadata.created_at,
        installed=entry.installed if entry else False,
        has_unresolved=has_unresolved,
        assets=assets,
        previews=previews,
        workflows=workflows,
        custom_nodes=custom_nodes,
        docs=pack.docs,
        parameters=parameters,
        model_info=model_info,
    )


@router.get("/{pack_name}/preview/{filename}")
async def get_preview_image(pack_name: str, filename: str):
    """Serve preview image from pack resources."""
    logger.info(f"[get_preview_image] Requested: pack={pack_name}, file={filename}")
    print(f"[get_preview_image] Requested: pack={pack_name}, file={filename}")
    
    config = get_config()
    registry = PackRegistry(config)
    
    entry = registry.registry.entries.get(pack_name)
    if not entry:
        logger.error(f"[get_preview_image] Pack not found: {pack_name}")
        print(f"[get_preview_image] Pack not found: {pack_name}")
        raise HTTPException(status_code=404, detail=f"Pack not found: {pack_name}")
    
    # Look in resources/previews
    preview_path = entry.pack_path / "resources" / "previews" / filename
    logger.debug(f"[get_preview_image] Trying path: {preview_path}")
    print(f"[get_preview_image] Trying path: {preview_path}")
    
    if not preview_path.exists():
        # Try old location
        preview_path = entry.pack_path / "previews" / filename
        logger.debug(f"[get_preview_image] Trying fallback path: {preview_path}")
        print(f"[get_preview_image] Trying fallback path: {preview_path}")
    
    if not preview_path.exists():
        logger.error(f"[get_preview_image] Preview file not found: {preview_path}")
        print(f"[get_preview_image] Preview file not found: {preview_path}")
        raise HTTPException(status_code=404, detail=f"Preview not found: {filename}")
    
    logger.info(f"[get_preview_image] Serving: {preview_path}")
    print(f"[get_preview_image] Serving: {preview_path}")
    return FileResponse(preview_path)


@router.post("/import/url", response_model=ImportResult)
async def import_from_url(request: ImportFromUrlRequest):
    """Import a pack from Civitai URL."""
    print(f"[IMPORT API] === Starting import from URL: {request.url} ===")
    logger.info(f"[IMPORT] Starting import from URL: {request.url}")
    
    try:
        config = get_config()
        builder = PackBuilder(config)
        registry = PackRegistry(config)
        
        print(f"[IMPORT API] Building pack from Civitai...")
        logger.info(f"[IMPORT] Building pack from Civitai...")
        
        # Build pack (downloads previews to resources)
        result = builder.build_from_civitai_url(
            request.url, 
            request.pack_name,
            download_previews=True,
        )
        
        if not result.success:
            print(f"[IMPORT API] Build failed: {result.errors}")
            logger.error(f"[IMPORT] Build failed: {result.errors}")
            return ImportResult(
                success=False,
                errors=result.errors,
                warnings=result.warnings,
                message="Import failed: " + "; ".join(result.errors),
            )
        
        # Register pack
        pack = result.pack
        pack_dir = result.pack_dir or registry.get_pack_directory(pack.metadata.name)
        
        print(f"[IMPORT API] Registering pack: {pack.metadata.name} at {pack_dir}")
        logger.info(f"[IMPORT] Registering pack: {pack.metadata.name} at {pack_dir}")
        registry.register_pack(pack, pack_dir)
        
        print(f"[IMPORT API] Successfully imported: {pack.metadata.name}")
        logger.info(f"[IMPORT] Successfully imported: {pack.metadata.name}")
        
        return ImportResult(
            success=True,
            pack_name=pack.metadata.name,
            errors=result.errors,
            warnings=result.warnings,
            message=f"Successfully imported '{pack.metadata.name}'",
        )
    
    except Exception as e:
        import traceback
        print(f"[IMPORT API] EXCEPTION: {e}")
        print(f"[IMPORT API] Traceback:\n{traceback.format_exc()}")
        logger.exception(f"[IMPORT] Exception during import: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import/workflow", response_model=ImportResult)
async def import_from_workflow(
    file: UploadFile = File(...),
    pack_name: Optional[str] = Form(None),
):
    """Import a pack from workflow JSON file."""
    config = get_config()
    builder = PackBuilder(config)
    registry = PackRegistry(config)
    
    # Save uploaded file temporarily
    temp_path = Path("/tmp") / file.filename
    with open(temp_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    try:
        result = builder.build_from_workflow(temp_path, pack_name)
        
        if not result.success:
            return ImportResult(
                success=False,
                errors=result.errors,
                warnings=result.warnings,
            )
        
        # Register pack
        pack = result.pack
        pack_dir = result.pack_dir or registry.get_pack_directory(pack.metadata.name)
        registry.register_pack(pack, pack_dir)
        
        # Copy workflow to pack
        workflows_dir = pack_dir / "workflows"
        workflows_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(temp_path, workflows_dir / file.filename)
        
        return ImportResult(
            success=True,
            pack_name=pack.metadata.name,
            errors=result.errors,
            warnings=result.warnings,
            message=f"Successfully imported '{pack.metadata.name}'",
        )
    
    finally:
        temp_path.unlink(missing_ok=True)


@router.patch("/{pack_name}", response_model=PackDetail)
async def update_pack(pack_name: str, request: UpdatePackRequest):
    """Update pack metadata (user_tags, rename)."""
    config = get_config()
    registry = PackRegistry(config)
    
    entry = registry.registry.entries.get(pack_name)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Pack not found: {pack_name}")
    
    pack = registry.get_pack(pack_name)
    if not pack:
        raise HTTPException(status_code=404, detail=f"Pack not found: {pack_name}")
    
    # Update user_tags
    if request.user_tags is not None:
        pack.metadata.user_tags = request.user_tags
    
    # Handle rename
    if request.name and request.name != pack_name:
        new_name = request.name
        
        # Check if new name exists
        if registry.registry.entries.get(new_name):
            raise HTTPException(status_code=400, detail=f"Pack with name '{new_name}' already exists")
        
        # Rename directory
        old_dir = entry.pack_path
        new_dir = old_dir.parent / new_name
        
        if old_dir.exists():
            old_dir.rename(new_dir)
        
        # Update pack metadata
        pack.metadata.name = new_name
        
        # Update registry
        del registry.registry.entries[pack_name]
        entry.name = new_name
        entry.pack_path = new_dir
        registry.registry.entries[new_name] = entry
    
    # Save pack
    pack_path = entry.pack_path / "pack.json"
    pack.save(pack_path)
    registry.save_registry()
    
    # Return updated pack
    return await get_pack(pack.metadata.name)


@router.delete("/{pack_name}")
async def delete_pack(pack_name: str, delete_files: bool = True):
    """Delete a pack from registry and optionally delete files."""
    config = get_config()
    registry = PackRegistry(config)
    
    if not registry.registry.entries.get(pack_name):
        raise HTTPException(status_code=404, detail=f"Pack not found: {pack_name}")
    
    success = registry.unregister_pack(pack_name, delete_files=delete_files)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete pack")
    
    return {
        "success": True,
        "message": f"Pack '{pack_name}' deleted",
        "files_deleted": delete_files
    }


@router.post("/{pack_name}/generate-workflow")
async def generate_default_workflow(pack_name: str):
    """Generate a default workflow for the pack."""
    config = get_config()
    registry = PackRegistry(config)
    
    entry = registry.registry.entries.get(pack_name)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Pack not found: {pack_name}")
    
    pack = registry.get_pack(pack_name)
    if not pack:
        raise HTTPException(status_code=404, detail=f"Pack not found: {pack_name}")
    
    # Generate workflow
    generator = WorkflowGenerator()
    
    workflows_dir = entry.pack_path / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    
    workflow_filename = f"default_{pack_name}.json"
    workflow_path = workflows_dir / workflow_filename
    
    workflow_data = generator.generate_default_workflow(pack, workflow_path)
    
    # Add workflow to pack
    workflow_info = WorkflowInfo(
        name=f"Default - {pack.metadata.name}",
        filename=workflow_filename,
        description="Auto-generated default workflow based on pack parameters",
        is_default=True,
    )
    
    # Remove existing default workflows
    pack.workflows = [w for w in pack.workflows if not w.is_default]
    pack.workflows.append(workflow_info)
    
    # Save pack
    pack.save(entry.pack_path / "pack.json")
    
    return {
        "success": True,
        "message": "Default workflow generated",
        "workflow_filename": workflow_filename,
    }


@router.get("/{pack_name}/workflow/{filename}")
async def get_workflow(pack_name: str, filename: str):
    """Get workflow JSON file."""
    config = get_config()
    registry = PackRegistry(config)
    
    entry = registry.registry.entries.get(pack_name)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Pack not found: {pack_name}")
    
    workflow_path = entry.pack_path / "workflows" / filename
    
    if not workflow_path.exists():
        raise HTTPException(status_code=404, detail=f"Workflow not found: {filename}")
    
    with open(workflow_path, 'r', encoding='utf-8') as f:
        return json.load(f)


@router.delete("/{pack_name}/workflow/{filename}")
async def delete_workflow(pack_name: str, filename: str):
    """Delete a workflow from the pack."""
    config = get_config()
    registry = PackRegistry(config)
    
    entry = registry.registry.entries.get(pack_name)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Pack not found: {pack_name}")
    
    pack = registry.get_pack(pack_name)
    if not pack:
        raise HTTPException(status_code=404, detail=f"Pack not found: {pack_name}")
    
    workflow_path = entry.pack_path / "workflows" / filename
    
    # Delete the actual file
    if workflow_path.exists():
        workflow_path.unlink()
    
    # Remove symlink from ComfyUI if exists
    comfyui_workflows = config.comfyui.base_path / "user" / "default" / "workflows"
    symlink_path = comfyui_workflows / filename
    if symlink_path.is_symlink():
        symlink_path.unlink()
    
    # Remove from pack.workflows
    pack.workflows = [w for w in pack.workflows if w.filename != filename]
    pack.save(entry.pack_path / "pack.json")
    
    return {
        "success": True,
        "message": f"Deleted workflow: {filename}",
    }


class WorkflowSymlinkRequest(BaseModel):
    """Request to create symlink for workflow."""
    filename: str


@router.post("/{pack_name}/workflow/symlink")
async def create_workflow_symlink(pack_name: str, request: WorkflowSymlinkRequest):
    """Create symlink for workflow in ComfyUI user workflows directory."""
    config = get_config()
    registry = PackRegistry(config)
    
    entry = registry.registry.entries.get(pack_name)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Pack not found: {pack_name}")
    
    workflow_path = entry.pack_path / "workflows" / request.filename
    
    if not workflow_path.exists():
        raise HTTPException(status_code=404, detail=f"Workflow not found: {request.filename}")
    
    # ComfyUI user workflows directory
    comfyui_workflows = config.comfyui.base_path / "user" / "default" / "workflows"
    comfyui_workflows.mkdir(parents=True, exist_ok=True)
    
    # Create symlink with pack name prefix for uniqueness
    symlink_name = f"synapse_{pack_name}_{request.filename}"
    symlink_path = comfyui_workflows / symlink_name
    
    # Remove existing symlink if exists
    if symlink_path.is_symlink() or symlink_path.exists():
        symlink_path.unlink()
    
    # Create symlink
    symlink_path.symlink_to(workflow_path.resolve())
    
    return {
        "success": True,
        "message": f"Symlink created: {symlink_name}",
        "symlink_path": str(symlink_path),
        "target_path": str(workflow_path),
    }


@router.delete("/{pack_name}/workflow/{filename}/symlink")
async def remove_workflow_symlink(pack_name: str, filename: str):
    """Remove symlink for workflow from ComfyUI."""
    config = get_config()
    
    comfyui_workflows = config.comfyui.base_path / "user" / "default" / "workflows"
    symlink_name = f"synapse_{pack_name}_{filename}"
    symlink_path = comfyui_workflows / symlink_name
    
    if symlink_path.is_symlink():
        symlink_path.unlink()
        return {
            "success": True,
            "message": f"Symlink removed: {symlink_name}",
        }
    
    return {
        "success": False,
        "message": f"Symlink not found: {symlink_name}",
    }


@router.get("/{pack_name}/workflow/{filename}/status")
async def get_workflow_status(pack_name: str, filename: str):
    """Get workflow status including symlink info."""
    config = get_config()
    registry = PackRegistry(config)
    
    entry = registry.registry.entries.get(pack_name)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Pack not found: {pack_name}")
    
    workflow_path = entry.pack_path / "workflows" / filename
    
    # Check symlink
    comfyui_workflows = config.comfyui.base_path / "user" / "default" / "workflows"
    symlink_name = f"synapse_{pack_name}_{filename}"
    symlink_path = comfyui_workflows / symlink_name
    
    has_symlink = symlink_path.is_symlink()
    symlink_valid = has_symlink and symlink_path.exists()
    
    return {
        "filename": filename,
        "exists": workflow_path.exists(),
        "path": str(workflow_path),
        "has_symlink": has_symlink,
        "symlink_valid": symlink_valid,
        "symlink_path": str(symlink_path) if has_symlink else None,
        "symlink_name": symlink_name,
    }


class WorkflowUploadRequest(BaseModel):
    """Request to upload custom workflow."""
    name: str
    description: Optional[str] = None
    workflow_json: Dict[str, Any]


@router.post("/{pack_name}/workflow/upload")
async def upload_custom_workflow(pack_name: str, request: WorkflowUploadRequest):
    """Upload a custom workflow to the pack."""
    config = get_config()
    registry = PackRegistry(config)
    
    entry = registry.registry.entries.get(pack_name)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Pack not found: {pack_name}")
    
    pack = registry.get_pack(pack_name)
    if not pack:
        raise HTTPException(status_code=404, detail=f"Pack not found: {pack_name}")
    
    # Create workflows directory
    workflows_dir = entry.pack_path / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate filename from name
    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in request.name)
    filename = f"{safe_name}.json"
    workflow_path = workflows_dir / filename
    
    # Ensure unique filename
    counter = 1
    while workflow_path.exists():
        filename = f"{safe_name}_{counter}.json"
        workflow_path = workflows_dir / filename
        counter += 1
    
    # Save workflow
    with open(workflow_path, 'w', encoding='utf-8') as f:
        json.dump(request.workflow_json, f, indent=2)
    
    # Add to pack.workflows
    workflow_info = WorkflowInfo(
        name=request.name,
        filename=filename,
        description=request.description,
        is_default=False,
    )
    pack.workflows.append(workflow_info)
    pack.save(entry.pack_path / "pack.json")
    
    return {
        "success": True,
        "message": f"Workflow uploaded: {filename}",
        "filename": filename,
    }


@router.post("/{pack_name}/workflow/upload-file")
async def upload_workflow_file(
    pack_name: str,
    file: UploadFile = File(...),
    name: str = Form(...),
    description: str = Form(None),
):
    """Upload a workflow JSON file to the pack."""
    config = get_config()
    registry = PackRegistry(config)
    
    entry = registry.registry.entries.get(pack_name)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Pack not found: {pack_name}")
    
    pack = registry.get_pack(pack_name)
    if not pack:
        raise HTTPException(status_code=404, detail=f"Pack not found: {pack_name}")
    
    # Validate file is JSON
    if not file.filename.endswith('.json'):
        raise HTTPException(status_code=400, detail="File must be a JSON file")
    
    # Read and parse JSON
    content = await file.read()
    try:
        workflow_json = json.loads(content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file")
    
    # Create workflows directory
    workflows_dir = entry.pack_path / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    
    # Use original filename or generate from name
    filename = file.filename or f"{name}.json"
    workflow_path = workflows_dir / filename
    
    # Ensure unique filename
    counter = 1
    base_name = filename.rsplit('.', 1)[0]
    while workflow_path.exists():
        filename = f"{base_name}_{counter}.json"
        workflow_path = workflows_dir / filename
        counter += 1
    
    # Save workflow
    with open(workflow_path, 'w', encoding='utf-8') as f:
        json.dump(workflow_json, f, indent=2)
    
    # Add to pack.workflows
    workflow_info = WorkflowInfo(
        name=name,
        filename=filename,
        description=description,
        is_default=False,
    )
    pack.workflows.append(workflow_info)
    pack.save(entry.pack_path / "pack.json")
    
    return {
        "success": True,
        "message": f"Workflow uploaded: {filename}",
        "filename": filename,
    }


@router.post("/{pack_name}/resolve-dependency")
async def resolve_dependency(pack_name: str, request: ResolveDependencyRequest):
    """Resolve an unresolved dependency by specifying its source."""
    config = get_config()
    registry = PackRegistry(config)
    
    entry = registry.registry.entries.get(pack_name)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Pack not found: {pack_name}")
    
    pack = registry.get_pack(pack_name)
    if not pack:
        raise HTTPException(status_code=404, detail=f"Pack not found: {pack_name}")
    
    # Find the dependency
    dep = None
    dep_index = -1
    for i, d in enumerate(pack.dependencies):
        if d.name == request.dependency_name:
            dep = d
            dep_index = i
            break
    
    if not dep:
        raise HTTPException(status_code=404, detail=f"Dependency not found: {request.dependency_name}")
    
    # Update dependency based on source
    from src.core.models import CivitaiSource, HuggingFaceSource
    from src.clients.civitai_client import CivitaiClient
    
    if request.source == "civitai" and request.civitai_model_id and request.civitai_version_id:
        client = CivitaiClient(api_key=config.api.civitai_token)
        
        # Fetch version info
        version_data = client.get_model_version(request.civitai_version_id)
        if not version_data:
            raise HTTPException(status_code=404, detail="Civitai version not found")
        
        files = version_data.get("files", [])
        primary_file = files[0] if files else {}
        hashes = primary_file.get("hashes", {})
        
        dep.source = AssetSource.CIVITAI
        dep.civitai = CivitaiSource(
            model_id=request.civitai_model_id,
            model_version_id=request.civitai_version_id,
            model_name=version_data.get("model", {}).get("name"),
            version_name=version_data.get("name"),
        )
        dep.filename = primary_file.get("name", "")
        dep.file_size = int(primary_file.get("sizeKB", 0) * 1024) if primary_file.get("sizeKB") else None
        if hashes:
            from src.core.models import AssetHash
            dep.hash = AssetHash(
                sha256=hashes.get("SHA256"),
                civitai_autov2=hashes.get("AutoV2"),
            )
        dep.status = DependencyStatus.RESOLVED
        
    elif request.source == "huggingface" and request.huggingface_repo and request.huggingface_filename:
        dep.source = AssetSource.HUGGINGFACE
        dep.huggingface = HuggingFaceSource(
            repo_id=request.huggingface_repo,
            filename=request.huggingface_filename,
        )
        dep.filename = request.huggingface_filename
        dep.status = DependencyStatus.RESOLVED
        
    elif request.source == "local" and request.local_path:
        dep.source = AssetSource.LOCAL
        dep.local_path = request.local_path
        dep.filename = Path(request.local_path).name
        dep.status = DependencyStatus.INSTALLED
        
    else:
        raise HTTPException(status_code=400, detail="Invalid resolution parameters")
    
    # Update pack
    pack.dependencies[dep_index] = dep
    pack.save(entry.pack_path / "pack.json")
    
    return {
        "success": True,
        "message": f"Dependency '{request.dependency_name}' resolved",
        "status": dep.status.value,
    }


@router.post("/{pack_name}/validate", response_model=ValidationResult)
async def validate_pack(pack_name: str, verify_hashes: bool = False):
    """Validate pack integrity."""
    config = get_config()
    registry = PackRegistry(config)
    
    pack = registry.get_pack(pack_name)
    if not pack:
        raise HTTPException(status_code=404, detail=f"Pack not found: {pack_name}")
    
    entry = registry.registry.entries.get(pack_name)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Pack not in registry: {pack_name}")
    
    validator = PackValidator(config)
    result = validator.validate_pack(pack, entry.pack_path, check_hashes=verify_hashes)
    
    issues = [
        ValidationIssue(
            level=issue.level.value,
            message=issue.message,
            asset_name=issue.asset_name,
            suggestion=issue.suggestion,
        )
        for issue in result.issues
    ]
    
    return ValidationResult(
        valid=result.valid,
        pack_name=result.pack_name,
        issues=issues,
    )


class ResolveBaseModelRequest(BaseModel):
    """Request to resolve base model."""
    model_path: Optional[str] = None
    download_url: Optional[str] = None
    source: Optional[str] = None
    file_name: Optional[str] = None
    size_kb: Optional[int] = None


class AssetValidationResult(BaseModel):
    """Result of asset validation."""
    name: str
    asset_type: str
    filename: Optional[str]
    exists: bool
    actual_path: Optional[str]
    local_path_in_pack: Optional[str]
    current_status: str
    expected_status: str
    status_correct: bool
    has_url: bool


class PackValidationResponse(BaseModel):
    """Response for pack validation."""
    pack_name: str
    all_valid: bool
    assets: List[AssetValidationResult]
    repaired: int = 0


@router.post("/{pack_name}/validate-assets")
async def validate_pack_assets_endpoint(pack_name: str, auto_repair: bool = True):
    """
    Validate all asset files in a pack against disk.
    
    This checks if files actually exist and optionally repairs status mismatches.
    
    Args:
        pack_name: Name of the pack
        auto_repair: If True, automatically fix status mismatches and save pack
    
    Returns:
        Validation results for each asset with optional repair status
    """
    logger.info(f"[validate-assets] Pack: {pack_name}, auto_repair={auto_repair}")
    print(f"[validate-assets] Pack: {pack_name}, auto_repair={auto_repair}")
    
    config = get_config()
    registry = PackRegistry(config)
    
    pack = registry.get_pack(pack_name)
    if not pack:
        raise HTTPException(status_code=404, detail=f"Pack not found: {pack_name}")
    
    entry = registry.registry.entries.get(pack_name)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Pack not in registry: {pack_name}")
    
    # Validate all assets
    validation_results = validate_pack_assets(pack, config)
    
    all_valid = all(r["status_correct"] for r in validation_results)
    repaired = 0
    
    # Auto-repair if requested
    if auto_repair and not all_valid:
        print(f"[validate-assets] Auto-repairing status mismatches...")
        for i, dep in enumerate(pack.dependencies):
            result = validation_results[i]
            if not result["status_correct"]:
                old_status = dep.status.value
                new_status = result["expected_status"]
                
                # Update status
                dep.status = DependencyStatus[new_status.upper()]
                
                # Update local_path based on validation
                if result["exists"]:
                    dep.local_path = result["actual_path"]
                else:
                    dep.local_path = None
                
                print(f"[validate-assets] Repaired {dep.name}: {old_status} -> {new_status}")
                repaired += 1
        
        # Save pack
        pack.save(entry.pack_path / "pack.json")
        print(f"[validate-assets] Saved pack with {repaired} repairs")
        
        # Re-validate after repair
        validation_results = validate_pack_assets(pack, config)
        all_valid = all(r["status_correct"] for r in validation_results)
    
    return PackValidationResponse(
        pack_name=pack_name,
        all_valid=all_valid,
        assets=[AssetValidationResult(**r) for r in validation_results],
        repaired=repaired,
    )


class ImportModelRequest(BaseModel):
    """Request to import a local model file."""
    model_type: str = "checkpoint"  # checkpoint, lora, vae
    model_name: str = ""  # Optional display name
    base_model: str = ""  # e.g., SDXL, Illustrious, Pony


class ImportModelResponse(BaseModel):
    """Response from model import."""
    success: bool
    model_path: str
    model_name: str
    model_type: str
    file_size: int


@router.post("/import-model", response_model=ImportModelResponse)
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
    print(f"[import-model] Importing: {file.filename}, type={model_type}, name={model_name}")
    
    config = get_config()
    
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
    
    print(f"[import-model] Target path: {target_path}")
    
    # Copy file
    try:
        file_size = 0
        with open(target_path, 'wb') as f:
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                f.write(chunk)
                file_size += len(chunk)
        
        print(f"[import-model] Saved {file_size / 1024 / 1024:.1f} MB to {target_path}")
        
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


@router.post("/{pack_name}/resolve-base-model")
async def resolve_base_model(pack_name: str, request: ResolveBaseModelRequest):
    """Resolve base model for a pack.
    
    Can either:
    1. Link to existing local model (model_path)
    2. Save download info from Civitai/HuggingFace (download_url + source)
    
    This updates the pack's base_model field AND updates the corresponding
    BASE_MODEL dependency to RESOLVED or PENDING status.
    """
    logger.info(f"[resolve-base-model] Pack: {pack_name}, Request: {request}")
    print(f"[resolve-base-model] Pack: {pack_name}")
    print(f"[resolve-base-model] model_path={request.model_path}, download_url={request.download_url}")
    print(f"[resolve-base-model] source={request.source}, file_name={request.file_name}")
    
    config = get_config()
    registry = PackRegistry(config)
    
    pack = registry.get_pack(pack_name)
    if not pack:
        logger.error(f"[resolve-base-model] Pack not found: {pack_name}")
        raise HTTPException(status_code=404, detail=f"Pack not found: {pack_name}")
    
    entry = registry.registry.entries.get(pack_name)
    if not entry:
        logger.error(f"[resolve-base-model] Pack not in registry: {pack_name}")
        raise HTTPException(status_code=404, detail=f"Pack not in registry: {pack_name}")
    
    from src.core.models import AssetDependency, AssetSource, AssetType
    
    # Find existing base_model dependency - search by multiple criteria
    # Priority: 1. BASE_MODEL type, 2. Name "base_model", 3. Name containing "base" with UNRESOLVED
    base_model_dep = None
    base_model_dep_idx = None
    
    print(f"[resolve-base-model] Searching for base_model dependency in {len(pack.dependencies)} dependencies")
    for idx, dep in enumerate(pack.dependencies):
        print(f"[resolve-base-model]   [{idx}] name={dep.name}, type={dep.asset_type}, status={dep.status}")
    
    # First pass: exact BASE_MODEL type
    for idx, dep in enumerate(pack.dependencies):
        if dep.asset_type == AssetType.BASE_MODEL:
            base_model_dep = dep
            base_model_dep_idx = idx
            print(f"[resolve-base-model] Found by BASE_MODEL type at [{idx}]: {dep.name}")
            break
    
    # Second pass: name is exactly "base_model"
    if not base_model_dep:
        for idx, dep in enumerate(pack.dependencies):
            if dep.name.lower() == "base_model":
                base_model_dep = dep
                base_model_dep_idx = idx
                print(f"[resolve-base-model] Found by name 'base_model' at [{idx}]: {dep.name}")
                break
    
    # Third pass: name contains "base" AND is UNRESOLVED (likely the one we need to resolve)
    if not base_model_dep:
        for idx, dep in enumerate(pack.dependencies):
            if "base" in dep.name.lower() and dep.status == DependencyStatus.UNRESOLVED:
                base_model_dep = dep
                base_model_dep_idx = idx
                print(f"[resolve-base-model] Found UNRESOLVED with 'base' in name at [{idx}]: {dep.name}")
                break
    
    if not base_model_dep:
        print(f"[resolve-base-model] No base_model dependency found, will create new one")
    
    if request.model_path:
        # Using existing local model
        model_name = Path(request.model_path).name
        model_name_clean = model_name.replace('.safetensors', '').replace('.ckpt', '')
        
        print(f"[resolve-base-model] Setting LOCAL base model: {model_name_clean}")
        
        # Update pack's base model reference
        pack.base_model = model_name_clean
        
        # Update or create base_model dependency
        if base_model_dep:
            base_model_dep.status = DependencyStatus.RESOLVED
            base_model_dep.filename = model_name
            base_model_dep.local_path = str(config.comfyui.base_path / "models" / "checkpoints" / model_name)
            base_model_dep.source = AssetSource.LOCAL
            base_model_dep.asset_type = AssetType.BASE_MODEL  # Ensure correct type
            print(f"[resolve-base-model] Updated dependency '{base_model_dep.name}' -> RESOLVED")
        else:
            new_dep = AssetDependency(
                name="base_model",
                asset_type=AssetType.BASE_MODEL,
                source=AssetSource.LOCAL,
                filename=model_name,
                local_path=str(config.comfyui.base_path / "models" / "checkpoints" / model_name),
                status=DependencyStatus.RESOLVED,
            )
            pack.dependencies.append(new_dep)
            print(f"[resolve-base-model] Created new dependency: base_model -> RESOLVED")
        
        pack.save(entry.pack_path / "pack.json")
        print(f"[resolve-base-model] SUCCESS: Saved pack, base_model={model_name_clean}")
        
        return {
            "success": True,
            "message": f"Base model set to: {model_name_clean}",
            "base_model": model_name_clean,
        }
    
    elif request.download_url:
        # Save download info for later download
        file_name = request.file_name or "model.safetensors"
        model_name_clean = file_name.replace('.safetensors', '').replace('.ckpt', '')
        
        # Determine source
        source = AssetSource.CIVITAI if request.source == 'civitai' else AssetSource.HUGGINGFACE
        
        print(f"[resolve-base-model] Setting REMOTE base model: {model_name_clean} from {source.value}")
        print(f"[resolve-base-model] Download URL: {request.download_url}")
        
        # Update pack's base model reference
        pack.base_model = model_name_clean
        
        # Update or create base_model dependency
        if base_model_dep:
            base_model_dep.url = request.download_url
            base_model_dep.filename = file_name
            base_model_dep.file_size = request.size_kb * 1024 if request.size_kb else None
            base_model_dep.status = DependencyStatus.PENDING
            base_model_dep.source = source
            base_model_dep.asset_type = AssetType.BASE_MODEL  # Ensure correct type
            # CRITICAL: Clear local_path since this is a NEW model that needs download
            base_model_dep.local_path = None
            print(f"[resolve-base-model] Updated dependency '{base_model_dep.name}' -> PENDING, cleared local_path")
        else:
            new_dep = AssetDependency(
                name="base_model",
                asset_type=AssetType.BASE_MODEL,
                source=source,
                url=request.download_url,
                filename=file_name,
                file_size=request.size_kb * 1024 if request.size_kb else None,
                status=DependencyStatus.PENDING,
                local_path=None,  # Explicitly None - needs download
            )
            pack.dependencies.append(new_dep)
            print(f"[resolve-base-model] Created new dependency: base_model -> PENDING")
        
        pack.save(entry.pack_path / "pack.json")
        print(f"[resolve-base-model] SUCCESS: Saved pack, base_model={model_name_clean}, status=PENDING")
        
        # Verify the saved state
        saved_pack = Pack.load(entry.pack_path / "pack.json")
        for dep in saved_pack.dependencies:
            if dep.asset_type == AssetType.BASE_MODEL:
                print(f"[resolve-base-model] VERIFY: filename={dep.filename}, local_path={dep.local_path}, status={dep.status.value}")
                # Also verify file doesn't exist
                exists, actual_path = validate_asset_file(dep.asset_type, dep.filename, dep.local_path, config)
                print(f"[resolve-base-model] VERIFY: file_exists={exists}, actual_path={actual_path}")
        
        return {
            "success": True,
            "message": f"Base model saved: {model_name_clean}. Ready for download.",
            "base_model": model_name_clean,
            "download_url": request.download_url,
            "needs_download": True,
        }
    
    else:
        raise HTTPException(status_code=400, detail="Either model_path or download_url is required")


class DownloadAssetRequest(BaseModel):
    """Request to download a single asset."""
    asset_name: str
    asset_type: str
    url: Optional[str] = None
    filename: Optional[str] = None


@router.post("/{pack_name}/download-asset")
async def download_asset(pack_name: str, request: DownloadAssetRequest, background_tasks: BackgroundTasks):
    """Start download of a single asset with progress tracking."""
    import uuid
    import requests
    
    logger.info(f"[download-asset] Pack: {pack_name}, Asset: {request.asset_name}")
    print(f"[download-asset] Pack: {pack_name}, Asset: {request.asset_name}, URL: {request.url}")
    
    config = get_config()
    registry = PackRegistry(config)
    
    pack = registry.get_pack(pack_name)
    if not pack:
        raise HTTPException(status_code=404, detail=f"Pack not found: {pack_name}")
    
    entry = registry.registry.entries.get(pack_name)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Pack not in registry: {pack_name}")
    
    # Find the asset
    asset = None
    for dep in pack.dependencies:
        if dep.name == request.asset_name:
            asset = dep
            break
    
    if not asset:
        raise HTTPException(status_code=404, detail=f"Asset not found: {request.asset_name}")
    
    # Use URL from request or from asset
    download_url = request.url or asset.url
    if not download_url:
        raise HTTPException(status_code=400, detail="No download URL available for this asset")
    
    # Determine target path
    asset_type_map = {
        'checkpoint': 'checkpoints',
        'base_model': 'checkpoints',
        'lora': 'loras',
        'vae': 'vae',
        'controlnet': 'controlnet',
        'upscaler': 'upscale_models',
        'clip': 'clip',
        'text_encoder': 'text_encoders',
        'diffusion_model': 'diffusion_models',
        'embedding': 'embeddings',
    }
    
    model_dir = asset_type_map.get(request.asset_type.lower(), 'checkpoints')
    target_dir = config.comfyui.base_path / "models" / model_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    
    filename = request.filename or asset.filename or f"{request.asset_name}.safetensors"
    target_path = target_dir / filename
    
    print(f"[download-asset] Target: {target_path}")
    print(f"[download-asset] URL: {download_url}")
    
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
        "speed_bps": 0.0,
        "eta_seconds": None,
        "error": None,
        "started_at": datetime.now().isoformat(),
        "completed_at": None,
        "target_path": str(target_path),
        "_start_time": time.time(),
    }
    
    # Start download in background
    def do_download():
        try:
            print(f"[download-asset] Starting download: {filename}")
            _update_download_progress(download_id, status="downloading")
            
            # Prepare headers
            headers = {"User-Agent": "Synapse/1.0"}
            if config.api.civitai_token and 'civitai' in download_url.lower():
                headers['Authorization'] = f'Bearer {config.api.civitai_token}'
            if config.api.huggingface_token and 'huggingface' in download_url.lower():
                headers['Authorization'] = f'Bearer {config.api.huggingface_token}'
            
            # Check for existing partial file for resume
            resume_from = 0
            temp_path = Path(str(target_path) + ".part")
            if temp_path.exists():
                resume_from = temp_path.stat().st_size
                headers['Range'] = f'bytes={resume_from}-'
                print(f"[download-asset] Resuming from {resume_from} bytes")
            
            response = requests.get(download_url, headers=headers, stream=True, timeout=600, allow_redirects=True)
            
            # Handle resume response
            if response.status_code == 206:  # Partial content
                total_size = resume_from + int(response.headers.get('content-length', 0))
            elif response.status_code == 200:
                total_size = int(response.headers.get('content-length', 0))
                resume_from = 0  # Server doesn't support resume, start fresh
                if temp_path.exists():
                    temp_path.unlink()
            else:
                response.raise_for_status()
                total_size = 0
            
            _update_download_progress(download_id, total_bytes=total_size, downloaded_bytes=resume_from)
            print(f"[download-asset] Total size: {total_size / 1024 / 1024:.1f} MB")
            
            downloaded = resume_from
            last_log_time = time.time()
            
            # Write to temp file first
            mode = 'ab' if resume_from > 0 else 'wb'
            with open(temp_path, mode) as f:
                for chunk in response.iter_content(chunk_size=65536):  # 64KB chunks
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Update progress periodically (not every chunk)
                        current_time = time.time()
                        if current_time - last_log_time >= 0.5:  # Update every 0.5 seconds
                            _update_download_progress(download_id, downloaded_bytes=downloaded)
                            
                            if total_size > 0:
                                progress = (downloaded / total_size) * 100
                                if int(progress) % 10 == 0:  # Log every 10%
                                    d = _active_downloads.get(download_id, {})
                                    speed_mb = d.get("speed_bps", 0) / 1024 / 1024
                                    eta = d.get("eta_seconds", 0)
                                    print(f"[download-asset] {filename}: {progress:.1f}% @ {speed_mb:.1f} MB/s, ETA: {eta:.0f}s")
                            
                            last_log_time = current_time
            
            # Move temp file to final location
            temp_path.rename(target_path)
            
            print(f"[download-asset] Completed: {filename}")
            _update_download_progress(download_id, status="completed", downloaded_bytes=downloaded)
            
            # Update asset status in pack
            for dep in pack.dependencies:
                if dep.name == request.asset_name:
                    dep.status = DependencyStatus.RESOLVED
                    dep.local_path = str(target_path)
                    break
            
            pack.save(entry.pack_path / "pack.json")
            print(f"[download-asset] Updated pack status for {request.asset_name}")
            
        except Exception as e:
            error_msg = str(e)
            print(f"[download-asset] FAILED: {filename} - {error_msg}")
            logger.error(f"[download-asset] Failed to download {filename}: {error_msg}")
            _update_download_progress(download_id, error=error_msg)
    
    # Run in thread pool
    import concurrent.futures
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    executor.submit(do_download)
    
    return {
        "success": True,
        "message": f"Download started for {request.asset_name}",
        "download_id": download_id,
        "target_path": str(target_path),
    }


@router.get("/downloads/active", response_model=List[DownloadProgress])
async def get_active_downloads():
    """Get list of all active downloads with progress."""
    return [
        DownloadProgress(
            download_id=d["download_id"],
            pack_name=d["pack_name"],
            asset_name=d["asset_name"],
            filename=d["filename"],
            status=d["status"],
            progress=d["progress"],
            downloaded_bytes=d["downloaded_bytes"],
            total_bytes=d["total_bytes"],
            speed_bps=d["speed_bps"],
            eta_seconds=d.get("eta_seconds"),
            error=d.get("error"),
            started_at=d["started_at"],
            completed_at=d.get("completed_at"),
            target_path=d.get("target_path"),
        )
        for d in _active_downloads.values()
    ]


@router.get("/downloads/{download_id}/progress")
async def stream_download_progress(download_id: str):
    """Stream download progress via SSE."""
    if download_id not in _active_downloads:
        raise HTTPException(status_code=404, detail=f"Download not found: {download_id}")
    
    async def generate():
        """Generate SSE events."""
        while True:
            if download_id not in _active_downloads:
                yield f"data: {json.dumps({'status': 'not_found'})}\n\n"
                break
            
            d = _active_downloads[download_id]
            data = json.dumps({
                "download_id": d["download_id"],
                "status": d["status"],
                "progress": d["progress"],
                "downloaded_bytes": d["downloaded_bytes"],
                "total_bytes": d["total_bytes"],
                "speed_bps": d["speed_bps"],
                "eta_seconds": d.get("eta_seconds"),
                "error": d.get("error"),
            })
            
            yield f"data: {data}\n\n"
            
            # Stop streaming if completed or failed
            if d["status"] in ("completed", "failed"):
                break
            
            await asyncio.sleep(0.5)
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.delete("/downloads/{download_id}")
async def cancel_download(download_id: str):
    """Cancel and remove a download from tracking."""
    if download_id in _active_downloads:
        _active_downloads[download_id]["status"] = "cancelled"
        del _active_downloads[download_id]
    return {"message": "Download cancelled", "download_id": download_id}


@router.delete("/downloads/completed")
async def clear_completed_downloads():
    """Clear completed/failed downloads from tracking."""
    to_remove = [
        did for did, d in _active_downloads.items()
        if d["status"] in ("completed", "failed", "cancelled")
    ]
    for did in to_remove:
        del _active_downloads[did]
    return {"message": f"Cleared {len(to_remove)} downloads"}


@router.post("/{pack_name}/download-all")
async def download_all_assets(pack_name: str, background_tasks: BackgroundTasks):
    """Start download of all pending assets with progress tracking."""
    import uuid
    import concurrent.futures
    
    logger.info(f"[download-all] Pack: {pack_name}")
    print(f"[download-all] Pack: {pack_name}")
    
    config = get_config()
    registry = PackRegistry(config)
    
    pack = registry.get_pack(pack_name)
    if not pack:
        raise HTTPException(status_code=404, detail=f"Pack not found: {pack_name}")
    
    entry = registry.registry.entries.get(pack_name)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Pack not in registry: {pack_name}")
    
    # Asset type to directory mapping
    asset_type_map = {
        'checkpoint': 'checkpoints',
        'base_model': 'checkpoints',
        'lora': 'loras',
        'vae': 'vae',
        'controlnet': 'controlnet',
        'upscaler': 'upscale_models',
        'clip': 'clip',
        'text_encoder': 'text_encoders',
        'diffusion_model': 'diffusion_models',
        'embedding': 'embeddings',
    }
    
    # Collect pending downloads
    pending_downloads = []
    for dep in pack.dependencies:
        # Get status as string for comparison
        status_str = dep.status.value if hasattr(dep.status, 'value') else str(dep.status)
        has_local = bool(dep.local_path)
        print(f"[download-all] Checking {dep.name}: status={status_str}, local_path={has_local}, url={dep.url}")
        
        # Download if: has URL AND not already downloaded (no local_path)
        if not dep.url:
            print(f"[download-all] Skipping {dep.name}: no URL")
            continue
        if has_local:
            print(f"[download-all] Skipping {dep.name}: already downloaded at {dep.local_path}")
            continue
        
        # Get asset type as string
        asset_type_str = dep.asset_type.value if hasattr(dep.asset_type, 'value') else str(dep.asset_type)
        model_dir = asset_type_map.get(asset_type_str.lower(), 'checkpoints')
        target_dir = config.comfyui.base_path / "models" / model_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        
        filename = dep.filename or f"{dep.name}.safetensors"
        target_path = target_dir / filename
        
        # Create download tracking entry
        download_id = str(uuid.uuid4())[:8]
        _active_downloads[download_id] = {
            "download_id": download_id,
            "pack_name": pack_name,
            "asset_name": dep.name,
            "filename": filename,
            "status": "pending",
            "progress": 0.0,
            "downloaded_bytes": 0,
            "total_bytes": 0,
            "speed_bps": 0.0,
            "eta_seconds": None,
            "error": None,
            "started_at": datetime.now().isoformat(),
            "completed_at": None,
            "target_path": str(target_path),
            "_start_time": time.time(),
        }
        
        pending_downloads.append({
            "name": dep.name,
            "url": dep.url,
            "target_path": str(target_path),
            "filename": filename,
            "download_id": download_id,
        })
        print(f"[download-all] Queued: {dep.name} -> {target_path} (id={download_id})")
    
    if not pending_downloads:
        return {
            "success": True,
            "message": "No pending downloads",
            "downloads": [],
        }
    
    # Download function for a single item
    def _download_single(item: dict):
        import requests
        
        download_id = item["download_id"]
        filename = item["filename"]
        target_path = Path(item["target_path"])
        
        try:
            print(f"[download-all] Starting: {filename}")
            _update_download_progress(download_id, status="downloading")
            
            # Prepare headers
            headers = {"User-Agent": "Synapse/1.0"}
            if config.api.civitai_token and 'civitai' in item['url'].lower():
                headers['Authorization'] = f'Bearer {config.api.civitai_token}'
            if config.api.huggingface_token and 'huggingface' in item['url'].lower():
                headers['Authorization'] = f'Bearer {config.api.huggingface_token}'
            
            # Check for existing partial file for resume
            resume_from = 0
            temp_path = Path(str(target_path) + ".part")
            if temp_path.exists():
                resume_from = temp_path.stat().st_size
                headers['Range'] = f'bytes={resume_from}-'
                print(f"[download-all] Resuming {filename} from {resume_from} bytes")
            
            # Reset start time for accurate speed calculation
            _active_downloads[download_id]["_start_time"] = time.time()
            
            response = requests.get(item['url'], headers=headers, stream=True, timeout=600, allow_redirects=True)
            
            # Handle resume response
            if response.status_code == 206:  # Partial content
                total_size = resume_from + int(response.headers.get('content-length', 0))
            elif response.status_code == 200:
                total_size = int(response.headers.get('content-length', 0))
                resume_from = 0  # Server doesn't support resume
                if temp_path.exists():
                    temp_path.unlink()
            else:
                response.raise_for_status()
                total_size = 0
            
            _update_download_progress(download_id, total_bytes=total_size, downloaded_bytes=resume_from)
            print(f"[download-all] {filename}: Total size: {total_size / 1024 / 1024:.1f} MB")
            
            downloaded = resume_from
            last_log_time = time.time()
            
            # Write to temp file first
            mode = 'ab' if resume_from > 0 else 'wb'
            with open(temp_path, mode) as f:
                for chunk in response.iter_content(chunk_size=65536):  # 64KB chunks
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Update progress periodically
                        current_time = time.time()
                        if current_time - last_log_time >= 0.5:
                            _update_download_progress(download_id, downloaded_bytes=downloaded)
                            
                            if total_size > 0:
                                progress = (downloaded / total_size) * 100
                                d = _active_downloads.get(download_id, {})
                                speed_mb = d.get("speed_bps", 0) / 1024 / 1024
                                eta = d.get("eta_seconds", 0) or 0
                                if int(progress) % 5 == 0:  # Log every 5%
                                    print(f"[download-all] {filename}: {progress:.1f}% @ {speed_mb:.1f} MB/s, ETA: {eta:.0f}s")
                            
                            last_log_time = current_time
            
            # Move temp file to final location
            temp_path.rename(target_path)
            
            print(f"[download-all] Completed: {filename}")
            _update_download_progress(download_id, status="completed", downloaded_bytes=downloaded)
            
            # Update asset status in pack
            for dep in pack.dependencies:
                if dep.name == item['name']:
                    dep.status = DependencyStatus.RESOLVED
                    dep.local_path = str(target_path)
                    break
            
            return True
            
        except Exception as e:
            error_msg = str(e)
            print(f"[download-all] FAILED: {filename} - {error_msg}")
            logger.error(f"[download-all] Failed: {filename}: {error_msg}")
            _update_download_progress(download_id, error=error_msg)
            return False
    
    # Start downloads in background thread pool
    def do_all_downloads():
        for item in pending_downloads:
            _download_single(item)
        
        # Save pack after all downloads
        pack.save(entry.pack_path / "pack.json")
        print(f"[download-all] Saved pack status")
    
    # Run in thread pool
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    executor.submit(do_all_downloads)
    
    return {
        "success": True,
        "message": f"Started {len(pending_downloads)} downloads",
        "downloads": [{"name": d["name"], "download_id": d["download_id"]} for d in pending_downloads],
    }


@router.post("/{pack_name}/repair-urls")
async def repair_pack_urls(pack_name: str):
    """Repair pack by fetching missing download URLs from Civitai."""
    logger.info(f"[repair-urls] Pack: {pack_name}")
    print(f"[repair-urls] Repairing URLs for pack: {pack_name}")
    
    config = get_config()
    registry = PackRegistry(config)
    
    pack = registry.get_pack(pack_name)
    if not pack:
        raise HTTPException(status_code=404, detail=f"Pack not found: {pack_name}")
    
    entry = registry.registry.entries.get(pack_name)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Pack not in registry: {pack_name}")
    
    from src.clients.civitai_client import CivitaiClient
    civitai = CivitaiClient(api_token=config.api.civitai_token)
    
    repaired = []
    
    for dep in pack.dependencies:
        # Skip if already has URL
        if dep.url:
            print(f"[repair-urls] {dep.name}: already has URL")
            continue
        
        # Try to get URL from Civitai source
        if dep.civitai and dep.civitai.model_version_id:
            try:
                # Construct download URL from version ID
                download_url = f"https://civitai.com/api/download/models/{dep.civitai.model_version_id}"
                dep.url = download_url
                repaired.append(dep.name)
                print(f"[repair-urls] {dep.name}: set URL from version ID -> {download_url}")
            except Exception as e:
                print(f"[repair-urls] {dep.name}: failed to set URL: {e}")
        else:
            print(f"[repair-urls] {dep.name}: no civitai source info")
    
    # Save pack
    if repaired:
        pack.save(entry.pack_path / "pack.json")
        print(f"[repair-urls] Saved pack with {len(repaired)} repaired URLs")
    
    return {
        "success": True,
        "message": f"Repaired {len(repaired)} URLs",
        "repaired": repaired,
    }


@router.patch("/{pack_name}/parameters")
async def update_pack_parameters(pack_name: str, request: Dict[str, Any] = Body(...)):
    """
    Update pack generation parameters dynamically.
    
    Accepts any key-value pairs. Known parameters:
    - strength: LoRA strength (stored in model_info.strength_recommended)
    - cfgScale / cfg_scale: CFG scale
    - steps: Number of steps
    - sampler: Sampler name
    - clipSkip / clip_skip: CLIP skip value
    - width, height: Image dimensions
    - denoise: Denoise strength
    """
    logger.info(f"[parameters] Pack: {pack_name}")
    print(f"[parameters] Pack: {pack_name}, request: {request}")
    
    config = get_config()
    registry = PackRegistry(config)
    
    pack = registry.get_pack(pack_name)
    if not pack:
        raise HTTPException(status_code=404, detail=f"Pack not found: {pack_name}")
    
    entry = registry.registry.entries.get(pack_name)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Pack not in registry: {pack_name}")
    
    from src.core.models import GenerationParameters, ModelInfo
    
    # Ensure model_info exists
    if pack.model_info is None:
        pack.model_info = ModelInfo()
    
    # Ensure parameters exists
    if pack.parameters is None:
        pack.parameters = GenerationParameters()
    
    # Process each parameter
    for key, value in request.items():
        if value is None or value == '':
            continue
            
        # Handle strength (goes to model_info)
        if key in ('strength', 'strength_recommended'):
            pack.model_info.strength_recommended = float(value)
            print(f"[parameters] Updated strength_recommended: {value}")
        
        # Handle cfgScale / cfg_scale
        elif key in ('cfgScale', 'cfg_scale'):
            pack.parameters.cfg_scale = float(value)
            print(f"[parameters] Updated cfg_scale: {value}")
        
        # Handle steps
        elif key == 'steps':
            pack.parameters.steps = int(value)
            print(f"[parameters] Updated steps: {value}")
        
        # Handle sampler
        elif key == 'sampler':
            pack.parameters.sampler = str(value)
            print(f"[parameters] Updated sampler: {value}")
        
        # Handle clipSkip / clip_skip
        elif key in ('clipSkip', 'clip_skip'):
            pack.parameters.clip_skip = int(value)
            print(f"[parameters] Updated clip_skip: {value}")
        
        # Handle width
        elif key == 'width':
            pack.parameters.width = int(value)
            print(f"[parameters] Updated width: {value}")
        
        # Handle height
        elif key == 'height':
            pack.parameters.height = int(value)
            print(f"[parameters] Updated height: {value}")
        
        # Handle denoise
        elif key == 'denoise':
            pack.parameters.denoise = float(value)
            print(f"[parameters] Updated denoise: {value}")
        
        # Handle seed
        elif key == 'seed':
            pack.parameters.seed = int(value)
            print(f"[parameters] Updated seed: {value}")
        
        # Handle scheduler
        elif key == 'scheduler':
            pack.parameters.scheduler = str(value)
            print(f"[parameters] Updated scheduler: {value}")
        
        else:
            print(f"[parameters] Unknown parameter: {key}={value}")
    
    # Save
    pack.save(entry.pack_path / "pack.json")
    print(f"[parameters] Saved pack")
    
    return {
        "success": True,
        "message": "Parameters updated",
    }
