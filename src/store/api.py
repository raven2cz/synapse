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
    AssetKind,
    BackResult,
    BlobStatus,
    CivitaiSelector,
    DoctorReport,
    GenerationParameters,
    HuggingFaceSelector,
    PackDependencyRef,
    SearchResult,
    SelectorStrategy,
    StatusReport,
    StoreConfig,
    UpdatePlan,
    UpdateResult,
    UseResult,
    WorkflowInfo,
)
from .layout import PackNotFoundError
from .backup_service import BackupNotEnabledError, BackupNotConnectedError


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


class UpdateOptionsRequest(BaseModel):
    """Update options for what to sync beyond blobs."""
    merge_previews: bool = False
    update_description: bool = False
    update_model_info: bool = False


class UpdateRequest(BaseModel):
    """Request for update command."""
    pack: str
    dry_run: bool = False
    sync: bool = True
    ui_set: Optional[str] = None
    choose: Optional[Dict[str, int]] = None
    options: Optional[UpdateOptionsRequest] = None


class BatchUpdateRequest(BaseModel):
    """Request for batch update command."""
    packs: List[str]
    sync: bool = True
    ui_set: Optional[str] = None
    choose: Optional[Dict[str, Dict[str, int]]] = None
    options: Optional[UpdateOptionsRequest] = None


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
    """Request for import command with wizard options."""
    url: str
    # Wizard options
    version_ids: Optional[List[int]] = Field(None, description="Specific versions to import")
    download_images: bool = Field(True, description="Download image previews")
    download_videos: bool = Field(True, description="Download video previews")
    include_nsfw: bool = Field(True, description="Include NSFW content")
    download_from_all_versions: bool = Field(True, description="Download previews from all versions, not just selected")
    thumbnail_url: Optional[str] = Field(None, description="Custom thumbnail URL")
    pack_name: Optional[str] = Field(None, description="Custom pack name")
    pack_description: Optional[str] = Field(None, description="Custom description")
    max_previews: int = Field(100, description="Max previews to download")
    video_quality: int = Field(1080, description="Video quality width")
    # Legacy fields for compatibility
    download_previews: bool = True
    add_to_global: bool = True


class ImportResponse(BaseModel):
    """Response for import command."""
    success: bool = True
    pack_name: str
    pack_type: str
    dependencies_count: int
    previews_downloaded: int = 0
    videos_downloaded: int = 0
    message: str = ""


class ImportPreviewRequest(BaseModel):
    """Request for import preview - fetches model info without importing."""
    url: str
    version_ids: Optional[List[int]] = None


class VersionPreviewInfo(BaseModel):
    """Preview info for a single version."""
    id: int
    name: str
    base_model: Optional[str] = None
    files: List[Dict[str, Any]] = []
    image_count: int = 0
    video_count: int = 0
    nsfw_count: int = 0
    total_size_bytes: int = 0


class ThumbnailOption(BaseModel):
    """Thumbnail option for selection."""
    url: str
    version_id: Optional[int] = None
    nsfw: bool = False
    type: str = "image"
    width: Optional[int] = None
    height: Optional[int] = None


class ImportPreviewResponse(BaseModel):
    """Response for import preview endpoint."""
    model_id: int
    model_name: str
    creator: Optional[str] = None
    model_type: Optional[str] = None
    base_model: Optional[str] = None
    versions: List[VersionPreviewInfo] = []
    total_size_bytes: int = 0
    total_size_formatted: str = "0 B"
    total_image_count: int = 0
    total_video_count: int = 0
    total_nsfw_count: int = 0
    thumbnail_options: List[ThumbnailOption] = []


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
# Inventory Endpoints
# =============================================================================


class CleanupRequest(BaseModel):
    """Request for cleanup operation."""
    dry_run: bool = True
    max_items: int = 0


class DeleteBlobRequest(BaseModel):
    """Request for blob deletion."""
    force: bool = False
    target: str = "local"  # "local", "backup", or "both"


class VerifyRequest(BaseModel):
    """Request for blob verification."""
    sha256: Optional[List[str]] = None
    all: bool = False


class BackupBlobRequest(BaseModel):
    """Request for backup blob operation."""
    verify_after: bool = True


class RestoreBlobRequest(BaseModel):
    """Request for restore blob operation."""
    verify_after: bool = True


class DeleteFromBackupRequest(BaseModel):
    """Request for deleting from backup."""
    confirm: bool = False


class SyncBackupRequest(BaseModel):
    """Request for backup sync operation."""
    direction: str = "to_backup"  # "to_backup" or "from_backup"
    only_missing: bool = True
    dry_run: bool = True


class ConfigureBackupRequest(BaseModel):
    """Request for configuring backup storage."""
    enabled: bool = False
    path: Optional[str] = None
    auto_backup_new: bool = False
    warn_before_delete_last_copy: bool = True


@store_router.get("/inventory", response_model=Dict[str, Any])
def get_inventory(
    kind: Optional[str] = Query(None, description="Filter by asset kind"),
    status: Optional[str] = Query(None, description="Filter by blob status"),
    include_verification: bool = Query(False, description="Verify blob hashes (slow!)"),
    sort_by: str = Query("size_desc", description="Sort by: size_desc, size_asc, name_asc, kind"),
    limit: int = Query(1000, description="Maximum items to return"),
    offset: int = Query(0, description="Pagination offset"),
    store=Depends(require_initialized),
):
    """
    Get blob inventory with filtering and pagination.

    Returns all blobs with their status (REFERENCED, ORPHAN, MISSING),
    usage information, and disk statistics.
    """
    from .models import AssetKind, BlobStatus

    logger.info(
        "[API] GET /inventory (kind=%s, status=%s, verify=%s, limit=%d)",
        kind,
        status,
        include_verification,
        limit,
    )

    kind_filter = None
    if kind and kind != "all":
        try:
            kind_filter = AssetKind(kind)
        except ValueError:
            logger.warning("[API] Invalid kind filter: %s", kind)
            raise HTTPException(400, f"Invalid kind: {kind}")

    status_filter = None
    if status and status != "all":
        try:
            status_filter = BlobStatus(status)
        except ValueError:
            logger.warning("[API] Invalid status filter: %s", status)
            raise HTTPException(400, f"Invalid status: {status}")

    try:
        inventory = store.get_inventory(
            kind_filter=kind_filter,
            status_filter=status_filter,
            include_verification=include_verification,
        )
    except Exception as e:
        logger.error("[API] Failed to get inventory: %s", e, exc_info=True)
        raise HTTPException(500, f"Failed to get inventory: {str(e)}")

    # Sort items
    if sort_by == "size_desc":
        inventory.items.sort(key=lambda x: x.size_bytes, reverse=True)
    elif sort_by == "size_asc":
        inventory.items.sort(key=lambda x: x.size_bytes)
    elif sort_by == "name_asc":
        inventory.items.sort(key=lambda x: x.display_name.lower())
    elif sort_by == "kind":
        inventory.items.sort(key=lambda x: x.kind.value)

    # Paginate
    total = len(inventory.items)
    inventory.items = inventory.items[offset:offset + limit]

    logger.debug("[API] Returning %d items (total=%d)", len(inventory.items), total)

    return {
        "generated_at": inventory.generated_at,
        "summary": inventory.summary.model_dump(),
        "items": [item.model_dump() for item in inventory.items],
        "pagination": {
            "total": total,
            "offset": offset,
            "limit": limit,
        },
    }


@store_router.get("/inventory/summary", response_model=Dict[str, Any])
def get_inventory_summary(store=Depends(require_initialized)):
    """
    Get quick inventory summary (no items).

    Returns statistics only, useful for dashboard widgets.
    """
    summary = store.get_inventory_summary()
    return summary.model_dump()


@store_router.get("/inventory/{sha256}/impact", response_model=Dict[str, Any])
def get_blob_impact(
    sha256: str,
    store=Depends(require_initialized),
):
    """
    Get impact analysis for a specific blob.

    Returns what would be affected if the blob was deleted.
    IMPORTANT: This route must be defined BEFORE /inventory/{sha256} to avoid path matching issues.
    """
    logger.info("[API] GET /inventory/%s/impact", sha256[:12] if len(sha256) >= 12 else sha256)
    try:
        impacts = store.get_blob_impacts(sha256)
        logger.debug("[API] Impact analysis: can_delete=%s, packs=%s", impacts.can_delete_safely, impacts.used_by_packs)
        return impacts.model_dump()
    except Exception as e:
        logger.error("[API] Failed to get impact analysis for %s: %s", sha256[:12], e, exc_info=True)
        raise HTTPException(500, f"Failed to get impact analysis: {str(e)}")


@store_router.get("/inventory/{sha256}", response_model=Dict[str, Any])
def get_blob_detail(
    sha256: str,
    store=Depends(require_initialized),
):
    """
    Get detailed info about a specific blob.

    Returns blob info plus impact analysis for deletion.
    """
    inventory = store.get_inventory()

    item = next((i for i in inventory.items if i.sha256 == sha256.lower()), None)
    if not item:
        raise HTTPException(404, f"Blob not found: {sha256}")

    impacts = store.get_blob_impacts(sha256)

    return {
        "item": item.model_dump(),
        "impacts": impacts.model_dump(),
    }


@store_router.post("/inventory/cleanup-orphans", response_model=Dict[str, Any])
def cleanup_orphans(
    request: CleanupRequest = Body(...),
    store=Depends(require_initialized),
):
    """
    Remove orphan blobs safely.

    NEVER removes referenced blobs. Use dry_run=true to preview.
    """
    logger.info(
        "[API] POST /inventory/cleanup-orphans (dry_run=%s, max_items=%d)",
        request.dry_run,
        request.max_items,
    )

    try:
        result = store.cleanup_orphans(
            dry_run=request.dry_run,
            max_items=request.max_items,
        )
        logger.info(
            "[API] Cleanup result: found=%d, deleted=%d, freed=%.2f MB",
            result.orphans_found,
            result.orphans_deleted,
            result.bytes_freed / 1024 / 1024 if result.bytes_freed else 0,
        )
        return result.model_dump()
    except Exception as e:
        logger.error("[API] Cleanup failed: %s", e, exc_info=True)
        raise HTTPException(500, f"Cleanup failed: {str(e)}")


@store_router.delete("/inventory/{sha256}", response_model=Dict[str, Any])
def delete_blob(
    sha256: str,
    force: bool = Query(False, description="Force delete even if referenced"),
    target: str = Query("local", description="Delete from: local, backup, both"),
    store=Depends(require_initialized),
):
    """
    Delete a specific blob with safety checks.

    Without force=true, only orphan blobs can be deleted.
    Returns 409 Conflict if blob is referenced and force=false.
    """
    logger.info(
        "[API] DELETE /inventory/%s (force=%s, target=%s)",
        sha256[:12] if len(sha256) >= 12 else sha256,
        force,
        target,
    )

    try:
        result = store.delete_blob(sha256, force=force, target=target)

        if not result.get("deleted"):
            if "impacts" in result:
                logger.info("[API] Delete blocked: blob is referenced")
                # Convert ImpactAnalysis pydantic model to dict for JSON serialization
                serializable_result = {**result, "impacts": result["impacts"].model_dump()}
                raise HTTPException(409, detail=serializable_result)
            else:
                reason = result.get("reason", "Unknown error")
                logger.warning("[API] Delete failed: %s", reason)
                raise HTTPException(400, detail=reason)

        logger.info("[API] Delete result: deleted=%s, from=%s", result.get("deleted"), result.get("deleted_from"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[API] Delete failed: %s", e, exc_info=True)
        raise HTTPException(500, f"Delete failed: {str(e)}")


@store_router.post("/inventory/verify", response_model=Dict[str, Any])
def verify_blobs(
    request: VerifyRequest = Body(...),
    store=Depends(require_initialized),
):
    """
    Verify blob integrity.

    Checks SHA256 hashes of blobs. Use all=true to verify all blobs.
    """
    logger.info(
        "[API] POST /inventory/verify (all=%s, specific=%d)",
        request.all,
        len(request.sha256 or []),
    )

    try:
        result = store.verify_blobs(
            sha256_list=request.sha256,
            all_blobs=request.all,
        )
        logger.info(
            "[API] Verify result: %d verified, %d invalid",
            result.get("verified", 0),
            len(result.get("invalid", [])),
        )
        return result
    except Exception as e:
        logger.error("[API] Verify failed: %s", e, exc_info=True)
        raise HTTPException(500, f"Verification failed: {str(e)}")


# =============================================================================
# Backup Storage Endpoints
# =============================================================================

@store_router.get("/backup/status", response_model=Dict[str, Any])
def get_backup_status(store=Depends(require_initialized)):
    """
    Get backup storage status.

    Returns connection status, blob count, and disk usage.
    """
    status = store.get_backup_status()
    return status.model_dump()


@store_router.post("/backup/blob/{sha256}", response_model=Dict[str, Any])
def backup_blob(
    sha256: str,
    request: BackupBlobRequest = Body(default_factory=BackupBlobRequest),
    store=Depends(require_initialized),
):
    """
    Backup a blob from local to backup storage.

    Copies the blob to the backup storage location.
    Returns 400 if backup not enabled, 503 if not connected,
    409 if already on backup, 507 if insufficient space.
    """
    result = store.backup_blob(sha256, verify_after=request.verify_after)
    if not result.success:
        error = result.error or "Unknown error"
        if "not enabled" in error.lower():
            raise HTTPException(status_code=400, detail=error)
        elif "not accessible" in error.lower() or "not connected" in error.lower():
            raise HTTPException(status_code=503, detail=error)
        elif "not found" in error.lower():
            raise HTTPException(status_code=404, detail=error)
        elif "not enough space" in error.lower():
            raise HTTPException(status_code=507, detail=error)
        else:
            raise HTTPException(status_code=500, detail=error)
    return result.model_dump()


@store_router.post("/backup/restore/{sha256}", response_model=Dict[str, Any])
def restore_blob(
    sha256: str,
    request: RestoreBlobRequest = Body(default_factory=RestoreBlobRequest),
    store=Depends(require_initialized),
):
    """
    Restore a blob from backup to local storage.

    Copies the blob from backup storage to local.
    Returns 400 if backup not enabled, 503 if not connected,
    404 if not found on backup, 507 if insufficient local space.
    """
    result = store.restore_blob(sha256, verify_after=request.verify_after)
    if not result.success:
        error = result.error or "Unknown error"
        if "not enabled" in error.lower():
            raise HTTPException(status_code=400, detail=error)
        elif "not accessible" in error.lower() or "not connected" in error.lower():
            raise HTTPException(status_code=503, detail=error)
        elif "not found" in error.lower():
            raise HTTPException(status_code=404, detail=error)
        elif "not enough space" in error.lower():
            raise HTTPException(status_code=507, detail=error)
        else:
            raise HTTPException(status_code=500, detail=error)
    return result.model_dump()


@store_router.delete("/backup/blob/{sha256}", response_model=Dict[str, Any])
def delete_from_backup(
    sha256: str,
    request: DeleteFromBackupRequest = Body(default_factory=DeleteFromBackupRequest),
    store=Depends(require_initialized),
):
    """
    Delete a blob from backup storage.

    Requires confirm=true in request body.
    The blob remains on local storage if it exists there.
    """
    result = store.delete_from_backup(sha256, confirm=request.confirm)
    if not result.success:
        error = result.error or "Unknown error"
        if "not confirmed" in error.lower():
            raise HTTPException(status_code=400, detail="Deletion not confirmed. Set confirm=true.")
        elif "not enabled" in error.lower():
            raise HTTPException(status_code=400, detail=error)
        elif "not accessible" in error.lower() or "not connected" in error.lower():
            raise HTTPException(status_code=503, detail=error)
        elif "not found" in error.lower():
            raise HTTPException(status_code=404, detail=error)
        else:
            raise HTTPException(status_code=500, detail=error)
    return result.model_dump()


@store_router.post("/backup/sync", response_model=Dict[str, Any])
def sync_backup(
    request: SyncBackupRequest = Body(...),
    store=Depends(require_initialized),
):
    """
    Sync blobs between local and backup storage.

    Direction can be "to_backup" or "from_backup".
    Use dry_run=true to preview without actually syncing.
    """
    result = store.sync_backup(
        direction=request.direction,
        only_missing=request.only_missing,
        dry_run=request.dry_run,
    )
    return result.model_dump()


@store_router.put("/backup/config", response_model=Dict[str, Any])
def configure_backup(
    request: ConfigureBackupRequest = Body(...),
    store=Depends(require_initialized),
):
    """
    Configure backup storage settings.

    Updates the backup configuration in the store config.
    """
    from .models import BackupConfig
    config = BackupConfig(
        enabled=request.enabled,
        path=request.path,
        auto_backup_new=request.auto_backup_new,
        warn_before_delete_last_copy=request.warn_before_delete_last_copy,
    )
    store.configure_backup(config)
    return {"success": True, "config": config.model_dump()}


@store_router.get("/backup/blob/{sha256}/warning", response_model=Dict[str, Any])
def get_delete_warning(
    sha256: str,
    target: str = Query("local", description="Target: local, backup, or both"),
    store=Depends(require_initialized),
):
    """
    Get a warning message if deleting this blob would be dangerous.

    Returns a warning message if this is the last copy of the blob,
    or null if deletion is safe.
    """
    warning = store.backup_service.get_delete_warning(sha256, target)
    return {
        "sha256": sha256,
        "target": target,
        "warning": warning,
        "is_last_copy": store.backup_service.is_last_copy(sha256),
    }


# -----------------------------------------------------------------------------
# Pack-Level Backup Operations (pull/push)
# -----------------------------------------------------------------------------


class PackPullRequest(BaseModel):
    """Request for pack pull operation."""
    dry_run: bool = True


class PackPushRequest(BaseModel):
    """Request for pack push operation."""
    dry_run: bool = True
    cleanup: bool = False


@store_router.post("/backup/pull-pack/{pack_name}", response_model=Dict[str, Any])
def backup_pull_pack(
    pack_name: str,
    request: PackPullRequest = Body(default=PackPullRequest()),
    store=Depends(require_initialized),
):
    """
    Pull (restore) all blobs for a pack from backup to local.

    Restores pack blobs without activating any profile.
    Use case: Need pack models locally but want to stay on global profile.

    Returns 400 if backup not enabled, 503 if not connected,
    404 if pack not found.
    """
    try:
        result = store.pull_pack(pack_name, dry_run=request.dry_run)
        return {
            "success": True,
            "pack": pack_name,
            "dry_run": result.dry_run,
            "direction": result.direction,
            "blobs_to_sync": result.blobs_to_sync,
            "bytes_to_sync": result.bytes_to_sync,
            "blobs_synced": result.blobs_synced,
            "bytes_synced": result.bytes_synced,
            "items": [
                {
                    "sha256": item.sha256,
                    "display_name": item.display_name,
                    "kind": item.kind,
                    "size_bytes": item.size_bytes,
                }
                for item in result.items
            ],
            "errors": result.errors,
        }
    except PackNotFoundError:
        raise HTTPException(status_code=404, detail=f"Pack not found: {pack_name}")
    except BackupNotEnabledError:
        raise HTTPException(status_code=400, detail="Backup not enabled")
    except BackupNotConnectedError:
        raise HTTPException(status_code=503, detail="Backup storage not connected")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@store_router.post("/backup/push-pack/{pack_name}", response_model=Dict[str, Any])
def backup_push_pack(
    pack_name: str,
    request: PackPushRequest = Body(default=PackPushRequest()),
    store=Depends(require_initialized),
):
    """
    Push (backup) all blobs for a pack from local to backup.

    Optionally removes local copies after successful backup.

    Returns 400 if backup not enabled, 503 if not connected,
    404 if pack not found.
    """
    try:
        result = store.push_pack(
            pack_name,
            dry_run=request.dry_run,
            cleanup=request.cleanup,
        )
        return {
            "success": True,
            "pack": pack_name,
            "dry_run": result.dry_run,
            "direction": result.direction,
            "blobs_to_sync": result.blobs_to_sync,
            "bytes_to_sync": result.bytes_to_sync,
            "blobs_synced": result.blobs_synced,
            "bytes_synced": result.bytes_synced,
            "cleanup": request.cleanup,
            "items": [
                {
                    "sha256": item.sha256,
                    "display_name": item.display_name,
                    "kind": item.kind,
                    "size_bytes": item.size_bytes,
                }
                for item in result.items
            ],
            "errors": result.errors,
        }
    except PackNotFoundError:
        raise HTTPException(status_code=404, detail=f"Pack not found: {pack_name}")
    except BackupNotEnabledError:
        raise HTTPException(status_code=400, detail="Backup not enabled")
    except BackupNotConnectedError:
        raise HTTPException(status_code=503, detail="Backup storage not connected")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@store_router.get("/backup/pack-status/{pack_name}", response_model=Dict[str, Any])
def get_pack_backup_status(
    pack_name: str,
    store=Depends(require_initialized),
):
    """
    Get backup status for all blobs in a pack.

    Returns location (local_only, backup_only, both, nowhere) for each blob.
    Useful for UI to determine which actions are available.
    """
    # Ensure backup config is loaded (same as /backup/status does)
    backup_status = store.get_backup_status()
    backup_enabled = backup_status.enabled
    backup_connected = backup_status.connected

    logger.info(f"[pack-status] Called for pack: {pack_name}, backup_enabled={backup_enabled}, backup_connected={backup_connected}")

    try:
        pack = store.layout.load_pack(pack_name)
        logger.info(f"[pack-status] Loaded pack with {len(pack.dependencies)} dependencies")
        lock = store.layout.load_pack_lock(pack_name)
        if not lock:
            return {
                "pack": pack_name,
                "backup_enabled": backup_enabled,
                "backup_connected": backup_connected,
                "blobs": [],
                "summary": {
                    "total": 0,
                    "local_only": 0,
                    "backup_only": 0,
                    "both": 0,
                    "nowhere": 0,
                    "total_bytes": 0,
                },
            }

        # Build blob status list
        blobs = []
        summary = {
            "total": 0,
            "local_only": 0,
            "backup_only": 0,
            "both": 0,
            "nowhere": 0,
            "total_bytes": 0,
        }

        for dep in pack.dependencies:
            resolved = lock.get_resolved(dep.id)
            if not resolved or not resolved.artifact:
                continue
            artifact = resolved.artifact
            if not artifact.sha256:
                continue
            sha256 = artifact.sha256
            on_local = store.blob_store.blob_exists(sha256)
            on_backup = store.backup_service.blob_exists_on_backup(sha256) if backup_connected else False

            if on_local and on_backup:
                location = "both"
                summary["both"] += 1
            elif on_local:
                location = "local_only"
                summary["local_only"] += 1
            elif on_backup:
                location = "backup_only"
                summary["backup_only"] += 1
            else:
                location = "nowhere"
                summary["nowhere"] += 1

            summary["total"] += 1
            size = artifact.size_bytes or 0
            summary["total_bytes"] += size

            blobs.append({
                "sha256": sha256,
                "display_name": artifact.provider.filename or dep.id,
                "kind": dep.kind.value if hasattr(dep.kind, "value") else str(dep.kind),
                "size_bytes": size,
                "location": location,
                "on_local": on_local,
                "on_backup": on_backup,
            })

        return {
            "pack": pack_name,
            "backup_enabled": backup_enabled,
            "backup_connected": backup_connected,
            "blobs": blobs,
            "summary": summary,
        }
    except PackNotFoundError:
        raise HTTPException(status_code=404, detail=f"Pack not found: {pack_name}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# State Sync Endpoints
# =============================================================================

class StateSyncRequest(BaseModel):
    """Request for state sync operation."""
    direction: str = "to_backup"  # "to_backup", "from_backup", "bidirectional"
    dry_run: bool = True


@store_router.get("/state/sync-status", response_model=Dict[str, Any])
def get_state_sync_status(store=Depends(require_initialized)):
    """
    Get the sync status of the state/ directory.

    Returns summary and list of files with their sync status.
    """
    try:
        result = store.backup_service.get_state_sync_status()
        return {
            "enabled": store.backup_service.config.enabled,
            "connected": store.backup_service.is_connected(),
            "dry_run": result.dry_run,
            "direction": result.direction,
            "summary": {
                "total_files": result.summary.total_files,
                "synced": result.summary.synced,
                "local_only": result.summary.local_only,
                "backup_only": result.summary.backup_only,
                "modified": result.summary.modified,
                "conflicts": result.summary.conflicts,
                "last_sync": result.summary.last_sync,
            },
            "items": [
                {
                    "relative_path": item.relative_path,
                    "status": item.status.value,
                    "local_mtime": item.local_mtime,
                    "backup_mtime": item.backup_mtime,
                    "local_size": item.local_size,
                    "backup_size": item.backup_size,
                }
                for item in result.items
            ],
            "errors": result.errors,
        }
    except BackupNotEnabledError:
        return {
            "enabled": False,
            "connected": False,
            "summary": {
                "total_files": 0,
                "synced": 0,
                "local_only": 0,
                "backup_only": 0,
                "modified": 0,
                "conflicts": 0,
                "last_sync": None,
            },
            "items": [],
            "errors": ["Backup not enabled"],
        }
    except BackupNotConnectedError:
        return {
            "enabled": True,
            "connected": False,
            "summary": {
                "total_files": 0,
                "synced": 0,
                "local_only": 0,
                "backup_only": 0,
                "modified": 0,
                "conflicts": 0,
                "last_sync": None,
            },
            "items": [],
            "errors": ["Backup storage not connected"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@store_router.post("/state/sync", response_model=Dict[str, Any])
def sync_state(
    request: StateSyncRequest = Body(...),
    store=Depends(require_initialized),
):
    """
    Sync the state/ directory with backup storage.

    Args:
        direction: "to_backup", "from_backup", or "bidirectional"
        dry_run: If true, just show what would be synced
    """
    try:
        result = store.backup_service.sync_state(
            direction=request.direction,
            dry_run=request.dry_run,
        )
        return {
            "dry_run": result.dry_run,
            "direction": result.direction,
            "summary": {
                "total_files": result.summary.total_files,
                "synced": result.summary.synced,
                "local_only": result.summary.local_only,
                "backup_only": result.summary.backup_only,
                "modified": result.summary.modified,
                "conflicts": result.summary.conflicts,
                "last_sync": result.summary.last_sync,
            },
            "synced_files": result.synced_files,
            "items": [
                {
                    "relative_path": item.relative_path,
                    "status": item.status.value,
                    "local_mtime": item.local_mtime,
                    "backup_mtime": item.backup_mtime,
                    "local_size": item.local_size,
                    "backup_size": item.backup_size,
                }
                for item in result.items
            ],
            "errors": result.errors,
        }
    except BackupNotEnabledError:
        raise HTTPException(status_code=400, detail="Backup not enabled")
    except BackupNotConnectedError:
        raise HTTPException(status_code=503, detail="Backup storage not connected")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
            
            # Get preview thumbnail with video support
            # Priority: 1. User-selected cover_url, 2. First preview in pack.previews, 3. First file on disk
            thumbnail = None
            thumbnail_type = "image"  # Default type
            previews_dir = store.layout.pack_previews_path(name)

            # 1. Check for user-selected cover_url
            if pack.cover_url:
                # Find the matching preview by URL and use its filename
                for preview in pack.previews:
                    if preview.url == pack.cover_url and preview.filename:
                        local_path = previews_dir / preview.filename
                        if local_path.exists():
                            thumbnail = f"/previews/{name}/resources/previews/{preview.filename}"
                            thumbnail_type = preview.media_type or ("video" if preview.filename.endswith(('.mp4', '.webm')) else "image")
                            break

            # 2. Fallback to first preview from pack.previews with existing local file
            if not thumbnail and pack.previews:
                for preview in pack.previews:
                    if preview.filename:
                        local_path = previews_dir / preview.filename
                        if local_path.exists():
                            thumbnail = f"/previews/{name}/resources/previews/{preview.filename}"
                            thumbnail_type = preview.media_type or ("video" if preview.filename.endswith(('.mp4', '.webm')) else "image")
                            break

            # 3. Final fallback: scan filesystem
            if not thumbnail and previews_dir.exists():
                # First look for images
                for ext in ['.png', '.jpg', '.jpeg', '.webp']:
                    for f in previews_dir.glob(f'*{ext}'):
                        thumbnail = f"/previews/{name}/resources/previews/{f.name}"
                        thumbnail_type = "image"
                        break
                    if thumbnail:
                        break

                # If no image found, look for videos
                if not thumbnail:
                    for ext in ['.mp4', '.webm']:
                        for f in previews_dir.glob(f'*{ext}'):
                            thumbnail = f"/previews/{name}/resources/previews/{f.name}"
                            thumbnail_type = "video"
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
                "thumbnail_type": thumbnail_type,  # NEW: video support
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
                "thumbnail_type": "image",  # Default for error case
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
                "required": dep.required,
                "is_base_model": dep.selector.strategy == SelectorStrategy.BASE_MODEL_HINT,
                "trigger_words": dep.expose.trigger_words if dep.expose else [],
                "update_policy": dep.update_policy.mode.value if dep.update_policy else "pinned",
                "strategy": dep.selector.strategy.value,
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
                preview_url = f"/previews/{pack_name}/resources/previews/{preview.filename}"

                # Determine media_type from filename extension or pack data
                media_type = getattr(preview, 'media_type', None)
                if not media_type:
                    ext = preview.filename.lower().split('.')[-1] if '.' in preview.filename else ''
                    media_type = 'video' if ext in ['mp4', 'webm', 'mov'] else 'image'

                preview_info = {
                    "filename": preview.filename,
                    "url": preview_url,
                    "nsfw": preview.nsfw,
                    "width": preview.width,
                    "height": preview.height,
                    "media_type": media_type,
                }

                # For videos, generate thumbnail URL (first frame)
                if media_type == 'video':
                    # Civitai URLs need special handling, local files can be served directly
                    # For local .mp4 files, frontend will use video element to show first frame
                    preview_info["thumbnail_url"] = getattr(preview, 'thumbnail_url', None) or preview_url

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
            image_exts = ['.png', '.jpg', '.jpeg', '.webp', '.gif']
            video_exts = ['.mp4', '.webm', '.mov']
            all_exts = image_exts + video_exts

            for f in sorted(previews_dir.iterdir()):
                if f.suffix.lower() in all_exts:
                    preview_url = f"/previews/{pack_name}/resources/previews/{f.name}"
                    media_type = 'video' if f.suffix.lower() in video_exts else 'image'

                    preview_info = {
                        "filename": f.name,
                        "url": preview_url,
                        "nsfw": "nsfw" in f.name.lower(),
                        "media_type": media_type,
                    }

                    # For videos, thumbnail_url is the same (frontend shows first frame)
                    if media_type == 'video':
                        preview_info["thumbnail_url"] = preview_url

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
        
        # Transform cover_url to match preview URL format (/previews/ instead of /packs/)
        cover_url = None
        if pack.cover_url:
            # Find matching preview and use its URL (which uses /previews/ format)
            for p in previews:
                if pack.cover_url and p["filename"] in pack.cover_url:
                    cover_url = p["url"]
                    break

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
            # Cover URL in same format as preview URLs (for frontend comparison)
            "cover_url": cover_url,
            # Raw data for debugging
            "pack": pack.model_dump(),
            "lock": lock.model_dump() if lock else None,
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@v2_packs_router.get("/import/preview", response_model=ImportPreviewResponse)
def import_preview(
    url: str = Query(..., description="Civitai model URL"),
    store=Depends(require_initialized),
):
    """
    Preview what will be imported without actually importing.

    Fetches model information from Civitai and returns version details,
    file sizes, and preview statistics for the Import Wizard.
    """
    import re
    from ..utils.media_detection import detect_media_type, MediaType

    # Parse model ID from URL
    model_id_match = re.search(r'civitai\.com/models/(\d+)', url)
    if not model_id_match:
        raise HTTPException(
            status_code=400,
            detail="Invalid Civitai URL. Expected: https://civitai.com/models/12345"
        )

    model_id = int(model_id_match.group(1))

    try:
        # Fetch model data from Civitai
        civitai = store.pack_service.civitai
        model_data = civitai.get_model(model_id)

        if not model_data:
            raise HTTPException(status_code=404, detail=f"Model not found: {model_id}")

        model_versions = model_data.get("modelVersions", [])

        versions = []
        total_size = 0
        total_images = 0
        total_videos = 0
        total_nsfw = 0
        all_thumbnails = []

        for version in model_versions:
            # Process files
            files = []
            version_size = 0
            for f in version.get("files", []):
                size_kb = f.get("sizeKB") or f.get("sizeKb") or 0
                version_size += size_kb * 1024
                files.append({
                    "id": f.get("id", 0),
                    "name": f.get("name", "unknown"),
                    "sizeKB": size_kb,
                    "type": f.get("type"),
                    "primary": f.get("primary", False),
                })

            # Count previews
            images = version.get("images", [])
            image_count = 0
            video_count = 0
            nsfw_count = 0

            for img in images:
                img_url = img.get("url", "")
                is_nsfw = img.get("nsfw", False) or (img.get("nsfwLevel", 1) >= 4)
                media_info = detect_media_type(img_url)
                is_video = media_info.type == MediaType.VIDEO

                if is_nsfw:
                    nsfw_count += 1
                if is_video:
                    video_count += 1
                else:
                    image_count += 1

                all_thumbnails.append(ThumbnailOption(
                    url=img_url,
                    version_id=version.get("id"),
                    nsfw=is_nsfw,
                    type="video" if is_video else "image",
                    width=img.get("width"),
                    height=img.get("height"),
                ))

            versions.append(VersionPreviewInfo(
                id=version.get("id", 0),
                name=version.get("name", "Unknown"),
                base_model=version.get("baseModel"),
                files=files,
                image_count=image_count,
                video_count=video_count,
                nsfw_count=nsfw_count,
                total_size_bytes=int(version_size),
            ))

            total_size += version_size
            total_images += image_count
            total_videos += video_count
            total_nsfw += nsfw_count

        # Get creator
        creator = model_data.get("creator", {})
        creator_name = creator.get("username") if isinstance(creator, dict) else None

        # Format size
        def format_size(size_bytes: int) -> str:
            if size_bytes < 1024:
                return f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                return f"{size_bytes / 1024:.1f} KB"
            elif size_bytes < 1024 * 1024 * 1024:
                return f"{size_bytes / (1024 * 1024):.1f} MB"
            else:
                return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

        return ImportPreviewResponse(
            model_id=model_id,
            model_name=model_data.get("name", "Unknown Model"),
            creator=creator_name,
            model_type=model_data.get("type"),
            base_model=versions[0].base_model if versions else None,
            versions=versions,
            total_size_bytes=int(total_size),
            total_size_formatted=format_size(int(total_size)),
            total_image_count=total_images,
            total_video_count=total_videos,
            total_nsfw_count=total_nsfw,
            thumbnail_options=all_thumbnails[:20],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[import-preview] Failed: {e}")
        # Check if it's a 404 from Civitai API
        if "404" in str(e) or "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=f"Model not found: {model_id}")
        raise HTTPException(status_code=500, detail=str(e))


@v2_packs_router.post("/import", response_model=ImportResponse)
def import_pack(
    request: ImportRequest,
    store=Depends(require_initialized),
):
    """
    Import a pack from Civitai URL with wizard options.

    Supports:
    - Version selection (version_ids)
    - Preview filtering (download_images, download_videos, include_nsfw)
    - Custom thumbnail (thumbnail_url)
    - Custom pack name and description
    """
    logger.info(f"[import] Starting import from: {request.url}")
    logger.info(f"[import] Options: images={request.download_images}, "
                f"videos={request.download_videos}, nsfw={request.include_nsfw}, "
                f"all_versions={request.download_from_all_versions}")

    try:
        pack = store.import_civitai(
            url=request.url,
            download_previews=request.download_previews,
            add_to_global=request.add_to_global,
            pack_name=request.pack_name,
            max_previews=request.max_previews,
            download_images=request.download_images,
            download_videos=request.download_videos,
            include_nsfw=request.include_nsfw,
            video_quality=request.video_quality,
            download_from_all_versions=request.download_from_all_versions,
            cover_url=request.thumbnail_url,  # User-selected thumbnail
            selected_version_ids=request.version_ids,  # Multi-version import support
        )

        # Count downloaded previews
        videos_count = sum(1 for p in pack.previews if getattr(p, 'media_type', 'image') == 'video')
        images_count = len(pack.previews) - videos_count

        return ImportResponse(
            success=True,
            pack_name=pack.name,
            pack_type=pack.pack_type.value,
            dependencies_count=len(pack.dependencies),
            previews_downloaded=images_count,
            videos_downloaded=videos_count,
            message=f"Successfully imported '{pack.name}' with {len(pack.previews)} previews",
        )
    except Exception as e:
        logger.exception(f"[import] Failed: {e}")
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
    """Delete a pack and clean up associated resources."""
    result = store.delete_pack(pack_name)
    if result.deleted:
        return {
            "deleted": pack_name,
            "cleanup": {
                "removed_from_global": result.removed_from_global,
                "removed_work_profile": result.removed_work_profile,
                "removed_from_stacks": result.removed_from_stacks,
            },
            "warnings": result.cleanup_warnings,
        }
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
                required=False,
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

    # Check if Civitai API key is configured for Civitai downloads
    if "civitai.com" in download_url and not store.blob_store.api_key:
        logger.warning(f"[download-asset] No Civitai API key configured! Download may fail.")

    # Determine filename
    filename = request.filename or resolved_filename or f"{request.asset_name}.safetensors"

    logger.info(f"[download-asset] Downloading {filename} from {download_url[:100]}...")
    if store.blob_store.api_key:
        logger.debug(f"[download-asset] Using Civitai API key: {store.blob_store.api_key[:8]}...")
    
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

            # Validate downloaded file is not HTML/error page
            blob_path = store.blob_store.blob_path(sha256)
            blob_size = blob_path.stat().st_size

            # Check if file is suspiciously small (likely error page)
            MIN_MODEL_SIZE = 100_000  # 100KB minimum for models
            if blob_size < MIN_MODEL_SIZE:
                # Read first bytes to check if HTML
                with open(blob_path, 'rb') as f:
                    header = f.read(100)
                if b'<!DOCTYPE' in header or b'<html' in header.lower():
                    # Delete the corrupt blob
                    store.blob_store.remove_blob(sha256)
                    raise RuntimeError(
                        f"Download failed: received HTML error page instead of model file. "
                        f"Size: {blob_size} bytes. This usually means Civitai returned an error. "
                        f"Try again later or check if the model is still available."
                    )
                else:
                    logger.warning(f"[download-asset] Downloaded file is small ({blob_size} bytes), but not HTML. Proceeding.")

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


@v2_packs_router.delete("/downloads/{download_id}")
def cancel_download(download_id: str):
    """Cancel a download."""
    if download_id in _active_downloads:
        _active_downloads[download_id]["status"] = "cancelled"
        del _active_downloads[download_id]
    return {"cancelled": download_id}
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
        
        # Delete blob if exists (but KEEP resolved info in lock.json for re-download!)
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

                # NOTE: We intentionally keep the resolved entry in lock.json!
                # It contains download URLs needed for re-downloading.
                # The UI should check blob existence to show download button.
        
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


@v2_packs_router.post("/{pack_name}/dependencies/{dep_id}/set-base-model", response_model=Dict[str, Any])
def set_dependency_as_base_model(
    pack_name: str,
    dep_id: str,
    store=Depends(require_initialized),
):
    """Mark a dependency as the base model for this pack.

    Changes the dependency's selector strategy to BASE_MODEL_HINT.
    If another dependency already has BASE_MODEL_HINT strategy, it is removed.
    Only one base model dependency is allowed per pack.
    """
    try:
        pack = store.get_pack(pack_name)

        # Find the target dependency
        target_dep = None
        for d in pack.dependencies:
            if d.id == dep_id:
                target_dep = d
                break

        if not target_dep:
            raise HTTPException(status_code=404, detail=f"Dependency not found: {dep_id}")

        # Remove any existing BASE_MODEL_HINT dependency (except the target)
        removed_old = None
        new_deps = []
        for d in pack.dependencies:
            if d.id != dep_id and d.selector.strategy == SelectorStrategy.BASE_MODEL_HINT:
                removed_old = d.id
                continue
            new_deps.append(d)
        pack.dependencies = new_deps

        # Update the target dependency to be the base model
        target_dep.selector.strategy = SelectorStrategy.BASE_MODEL_HINT
        if pack.base_model:
            target_dep.selector.base_model = pack.base_model

        store.layout.save_pack(pack)
        logger.info(f"[set-base-model] Set {dep_id} as base model for {pack_name}")

        return {
            "success": True,
            "dependency_id": dep_id,
            "removed_old_base_model": removed_old,
            "message": f"Set {dep_id} as base model",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[set-base-model] Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Pack Dependencies (pack-to-pack) CRUD
# =============================================================================


@v2_packs_router.get("/{pack_name}/pack-dependencies/status", response_model=List[Dict[str, Any]])
def get_pack_dependencies_status(
    pack_name: str,
    store=Depends(require_initialized),
):
    """Get status of all pack dependencies (batch resolve).

    Returns installation status for each pack dependency,
    replacing the N+1 per-pack query pattern.
    """
    try:
        pack = store.get_pack(pack_name)
        statuses = []
        for ref in pack.pack_dependencies:
            try:
                dep_pack = store.get_pack(ref.pack_name)
                # Aggregate trigger words from LoRA/embedding deps
                trigger_words = []
                for d in dep_pack.dependencies:
                    if d.expose and d.expose.trigger_words:
                        trigger_words.extend(d.expose.trigger_words)
                # Check resolution status
                dep_lock = store.layout.load_pack_lock(dep_pack.name)
                has_unresolved = bool(dep_lock and dep_lock.unresolved)
                # Check if all blobs exist locally
                all_installed = True
                if dep_lock:
                    for rd in dep_lock.resolved:
                        if rd.artifact.sha256 and not store.blob_store.blob_exists(rd.artifact.sha256):
                            all_installed = False
                            break
                else:
                    all_installed = False
                statuses.append({
                    "pack_name": ref.pack_name,
                    "required": ref.required,
                    "installed": True,
                    "version": dep_pack.version if hasattr(dep_pack, 'version') else None,
                    "pack_type": dep_pack.pack_type.value if hasattr(dep_pack.pack_type, 'value') else str(dep_pack.pack_type) if dep_pack.pack_type else None,
                    "description": (dep_pack.description or "")[:200] if dep_pack.description else None,
                    "asset_count": len(dep_pack.dependencies),
                    "trigger_words": trigger_words,
                    "base_model": dep_pack.base_model,
                    "has_unresolved": has_unresolved,
                    "all_installed": all_installed,
                })
            except Exception:
                statuses.append({
                    "pack_name": ref.pack_name,
                    "required": ref.required,
                    "installed": False,
                    "version": None,
                    "pack_type": None,
                    "description": None,
                    "asset_count": 0,
                    "trigger_words": [],
                    "base_model": None,
                    "has_unresolved": False,
                    "all_installed": False,
                })
        return statuses
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[pack-deps-status] Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


class AddPackDependencyRequest(BaseModel):
    pack_name: str
    required: bool = True


@v2_packs_router.post("/{pack_name}/pack-dependencies", response_model=Dict[str, Any])
def add_pack_dependency(
    pack_name: str,
    request: AddPackDependencyRequest = Body(...),
    store=Depends(require_initialized),
):
    """Add a pack dependency (pack-to-pack reference)."""
    try:
        pack = store.get_pack(pack_name)

        # Self-reference check
        if request.pack_name == pack_name:
            raise HTTPException(status_code=400, detail="Pack cannot depend on itself")

        # Duplicate check
        existing_names = {ref.pack_name for ref in pack.pack_dependencies}
        if request.pack_name in existing_names:
            raise HTTPException(
                status_code=409,
                detail=f"Pack dependency already exists: {request.pack_name}",
            )

        # Add the dependency
        new_ref = PackDependencyRef(
            pack_name=request.pack_name,
            required=request.required,
        )
        pack.pack_dependencies.append(new_ref)
        store.layout.save_pack(pack)

        logger.info(f"[pack-deps] Added {request.pack_name} to {pack_name}")
        return {
            "success": True,
            "pack_name": request.pack_name,
            "required": request.required,
            "message": f"Added pack dependency: {request.pack_name}",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[pack-deps] Error adding: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@v2_packs_router.delete("/{pack_name}/pack-dependencies/{dep_pack_name}", response_model=Dict[str, Any])
def remove_pack_dependency(
    pack_name: str,
    dep_pack_name: str,
    store=Depends(require_initialized),
):
    """Remove a pack dependency."""
    try:
        pack = store.get_pack(pack_name)

        # Check if it exists
        original_count = len(pack.pack_dependencies)
        pack.pack_dependencies = [
            ref for ref in pack.pack_dependencies if ref.pack_name != dep_pack_name
        ]

        if len(pack.pack_dependencies) == original_count:
            raise HTTPException(
                status_code=404,
                detail=f"Pack dependency not found: {dep_pack_name}",
            )

        store.layout.save_pack(pack)
        logger.info(f"[pack-deps] Removed {dep_pack_name} from {pack_name}")
        return {
            "success": True,
            "pack_name": dep_pack_name,
            "message": f"Removed pack dependency: {dep_pack_name}",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[pack-deps] Error removing: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@v2_packs_router.get("/{pack_name}/dependency-tree", response_model=Dict[str, Any])
def get_dependency_tree(
    pack_name: str,
    max_depth: int = 5,
    store=Depends(require_initialized),
):
    """Get recursive dependency tree for a pack.

    Builds a tree of pack dependencies with cycle detection.
    Each node includes installation status, asset count, and metadata.
    """
    try:
        pack = store.get_pack(pack_name)

        def build_node(name: str, depth: int, visited: set) -> dict:
            """Recursively build tree node with cycle detection."""
            if name in visited:
                return {
                    "pack_name": name,
                    "installed": False,
                    "version": None,
                    "pack_type": None,
                    "description": None,
                    "asset_count": 0,
                    "trigger_words": [],
                    "children": [],
                    "circular": True,
                    "depth": depth,
                }

            visited = visited | {name}  # New set per branch (not in-place)

            try:
                p = store.get_pack(name)
            except Exception:
                return {
                    "pack_name": name,
                    "installed": False,
                    "version": None,
                    "pack_type": None,
                    "description": None,
                    "asset_count": 0,
                    "trigger_words": [],
                    "children": [],
                    "circular": False,
                    "depth": depth,
                }

            # Aggregate trigger words
            trigger_words = []
            for d in p.dependencies:
                if d.expose and d.expose.trigger_words:
                    trigger_words.extend(d.expose.trigger_words)

            # Build children (if not at max depth)
            children = []
            if depth < max_depth and p.pack_dependencies:
                for ref in p.pack_dependencies:
                    children.append(build_node(ref.pack_name, depth + 1, visited))

            return {
                "pack_name": name,
                "installed": True,
                "version": p.version if hasattr(p, 'version') else None,
                "pack_type": p.pack_type.value if hasattr(p.pack_type, 'value') else str(p.pack_type) if p.pack_type else None,
                "description": (p.description or "")[:200] if p.description else None,
                "asset_count": len(p.dependencies),
                "trigger_words": trigger_words,
                "children": children,
                "circular": False,
                "depth": depth,
            }

        tree = build_node(pack_name, 0, set())
        return {"tree": tree, "max_depth": max_depth}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[dependency-tree] Error: {e}")
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
    """Request to update pack metadata.

    All fields are optional - only provided fields are updated.
    Supports partial updates for description, tags, cover_url, etc.
    """
    user_tags: Optional[List[str]] = None
    name: Optional[str] = None  # For rename
    description: Optional[str] = None  # HTML description
    cover_url: Optional[str] = None  # Cover image URL
    author: Optional[str] = None
    version: Optional[str] = None
    tags: Optional[List[str]] = None
    trigger_words: Optional[List[str]] = None
    base_model: Optional[str] = None


class CreatePackRequest(BaseModel):
    """Request to create a custom pack from scratch."""
    name: str = Field(..., description="Pack name (must be unique)")
    pack_type: str = Field("lora", description="Asset type: lora, checkpoint, vae, controlnet, etc.")
    description: Optional[str] = Field(None, description="Pack description (Markdown supported)")
    base_model: Optional[str] = Field(None, description="Base model (e.g., 'SD 1.5', 'SDXL 1.0')")
    version: str = Field("1.0.0", description="Pack version")
    author: Optional[str] = Field(None, description="Pack author")
    tags: Optional[List[str]] = Field(default_factory=list, description="Tags for categorization")
    user_tags: Optional[List[str]] = Field(default_factory=list, description="User-defined tags")
    trigger_words: Optional[List[str]] = Field(default_factory=list, description="Trigger words for generation")


@v2_packs_router.post("/create", response_model=Dict[str, Any])
def create_pack(
    request: CreatePackRequest,
    store=Depends(require_initialized),
):
    """
    Create a custom pack from scratch.

    Creates an empty pack with the specified metadata.
    The pack can then be populated with dependencies, previews, and workflows.

    Returns the created pack details.
    """
    from datetime import datetime
    from .models import Pack, PackSource, PackCategory, AssetKind, ProviderName

    try:
        # Check if pack already exists
        try:
            existing = store.get_pack(request.name)
            if existing:
                raise HTTPException(
                    status_code=400,
                    detail=f"Pack with name '{request.name}' already exists"
                )
        except PackNotFoundError:
            pass  # Good - pack doesn't exist

        # Parse pack_type to AssetKind
        try:
            pack_type = AssetKind(request.pack_type.lower())
        except ValueError:
            pack_type = AssetKind.UNKNOWN

        # Create the pack
        pack = Pack(
            name=request.name,
            pack_type=pack_type,
            pack_category=PackCategory.CUSTOM,  # Custom packs are fully editable
            source=PackSource(
                provider=ProviderName.LOCAL,
                url=None,
                model_id=None,
                version_id=None,
            ),
            version=request.version,
            description=request.description,
            base_model=request.base_model,
            author=request.author,
            tags=request.tags or [],
            user_tags=request.user_tags or [],
            trigger_words=request.trigger_words or [],
            created_at=datetime.now(),
        )

        # Save the pack
        store.layout.save_pack(pack)

        # Create pack directories
        pack_path = store.layout.pack_path(request.name)
        (pack_path / "resources" / "previews").mkdir(parents=True, exist_ok=True)
        (pack_path / "resources" / "workflows").mkdir(parents=True, exist_ok=True)

        logger.info(f"[create_pack] Created custom pack: {request.name}")

        return {
            "success": True,
            "name": pack.name,
            "pack_type": pack.pack_type.value,
            "pack_category": pack.pack_category.value,
            "created_at": pack.created_at.isoformat() if pack.created_at else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[create_pack] Error creating pack: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@v2_packs_router.patch("/{pack_name}", response_model=Dict[str, Any])
def update_pack(
    pack_name: str,
    request: UpdatePackRequest = Body(...),
    store=Depends(require_initialized),
):
    """
    Update pack metadata.

    Supports partial updates - only provided fields are updated.
    Handles: description, user_tags, tags, cover_url, author, version, etc.
    Also supports pack renaming via the 'name' field.
    """
    try:
        pack = store.get_pack(pack_name)
        updated_name = pack_name
        updated_fields = []

        # Update description (HTML content)
        if request.description is not None:
            pack.description = request.description
            updated_fields.append("description")

        # Update user_tags
        if request.user_tags is not None:
            pack.user_tags = request.user_tags
            updated_fields.append("user_tags")

        # Update tags
        if request.tags is not None:
            pack.tags = request.tags
            updated_fields.append("tags")

        # Update cover_url
        if request.cover_url is not None:
            pack.cover_url = request.cover_url
            updated_fields.append("cover_url")

        # Update author
        if request.author is not None:
            pack.author = request.author
            updated_fields.append("author")

        # Update version
        if request.version is not None:
            pack.version = request.version
            updated_fields.append("version")

        # Update trigger_words
        if request.trigger_words is not None:
            pack.trigger_words = request.trigger_words
            updated_fields.append("trigger_words")

        # Update base_model
        if request.base_model is not None:
            pack.base_model = request.base_model
            updated_fields.append("base_model")

        # Handle rename (must be last to avoid path issues)
        if request.name and request.name != pack_name:
            new_name = request.name
            # Check if new name exists
            try:
                store.get_pack(new_name)
                raise HTTPException(status_code=400, detail=f"Pack with name '{new_name}' already exists")
            except PackNotFoundError:
                pass  # Good - doesn't exist

            # Rename pack directory
            old_path = store.layout.pack_path(pack_name)
            new_path = old_path.parent / new_name
            if old_path.exists():
                import shutil
                shutil.move(str(old_path), str(new_path))

            pack.name = new_name
            updated_name = new_name
            updated_fields.append("name")

        store.layout.save_pack(pack)

        logger.info(f"[update_pack] Updated {pack_name}: {updated_fields}")

        return {
            "success": True,
            "name": pack.name,
            "updated_fields": updated_fields,
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


class ExtractParametersRequest(BaseModel):
    """Request for parameter extraction from various sources."""
    source: str = Field(..., description="Source type: 'image', 'aggregated', or 'description'")
    image_index: Optional[int] = Field(None, description="Image index for source='image'")


class ExtractParametersResponse(BaseModel):
    """Response with extracted parameters."""
    parameters: Dict[str, Any]
    source: str
    confidence: Optional[float] = None
    preview_count: Optional[int] = None


@v2_packs_router.post("/{pack_name}/parameters/extract", response_model=ExtractParametersResponse)
def extract_pack_parameters(
    pack_name: str,
    request: ExtractParametersRequest,
    store=Depends(require_initialized),
):
    """Extract generation parameters from pack previews or description.

    Sources:
    - 'image': Extract from specific preview image metadata (requires image_index)
    - 'aggregated': Aggregate from all preview images with metadata
    - 'description': Parse pack description for recommended parameters

    Returns extracted parameters with confidence score for aggregated results.
    """
    from ..utils.parameter_extractor import (
        extract_from_image_meta,
        aggregate_from_previews,
        extract_from_description,
    )

    try:
        pack = store.get_pack(pack_name)

        if request.source == 'image':
            # Extract from specific preview image
            if request.image_index is None:
                raise HTTPException(status_code=400, detail="image_index required for source='image'")

            if request.image_index < 0 or request.image_index >= len(pack.previews):
                raise HTTPException(status_code=400, detail=f"Invalid image_index: {request.image_index}")

            preview = pack.previews[request.image_index]
            if not preview.meta:
                return ExtractParametersResponse(
                    parameters={},
                    source='image',
                    confidence=0.0,
                )

            result = extract_from_image_meta(preview.meta)
            return ExtractParametersResponse(
                parameters=result.parameters,
                source='image',
                confidence=result.confidence,
            )

        elif request.source == 'aggregated':
            # Aggregate from all previews with metadata
            previews_with_meta = [
                {'meta': p.meta}
                for p in pack.previews
                if p.meta
            ]

            if not previews_with_meta:
                return ExtractParametersResponse(
                    parameters={},
                    source='aggregated',
                    confidence=0.0,
                    preview_count=0,
                )

            result = aggregate_from_previews(previews_with_meta)
            return ExtractParametersResponse(
                parameters=result.parameters,
                source='aggregated',
                confidence=result.confidence,
                preview_count=len(previews_with_meta),
            )

        elif request.source == 'description':
            # Extract from pack description using AI service
            if not pack.description:
                return ExtractParametersResponse(
                    parameters={},
                    source='description',
                    confidence=0.0,
                )

            from src.ai import AIService

            ai_service = AIService()
            ai_result = ai_service.extract_parameters(pack.description)

            if ai_result.success and ai_result.output:
                # Normalize AI output using GenerationParameters validator
                # This converts AI formats like {recommended: 7} to plain values
                try:
                    normalized = GenerationParameters(**ai_result.output)
                    # Get normalized dict, excluding None values and _extracted_by
                    params = {
                        k: v for k, v in normalized.model_dump(exclude_none=True).items()
                        if k != "_extracted_by"
                    }
                except Exception as e:
                    logger.warning(f"[extract-parameters] Normalization failed: {e}, using raw output")
                    params = {k: v for k, v in ai_result.output.items() if k != "_extracted_by"}

                return ExtractParametersResponse(
                    parameters=params,
                    source=f'description:{ai_result.provider_id}',  # Include provider info
                    confidence=1.0 if ai_result.provider_id != "rule_based" else 0.8,
                )
            else:
                return ExtractParametersResponse(
                    parameters={},
                    source='description',
                    confidence=0.0,
                )

        else:
            raise HTTPException(status_code=400, detail=f"Invalid source: {request.source}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[extract-parameters] Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Preview Endpoints
# =============================================================================


class PreviewOrderRequest(BaseModel):
    """Request to reorder previews."""
    order: List[str]  # List of filenames in new order


@v2_packs_router.patch("/{pack_name}/previews", response_model=Dict[str, Any])
def batch_update_previews(
    pack_name: str,
    files: List[UploadFile] = File(default=[]),
    order: Optional[str] = Form(None),  # JSON array of filenames
    cover_filename: Optional[str] = Form(None),
    deleted: Optional[str] = Form(None),  # JSON array of filenames to delete
    store=Depends(require_initialized),
):
    """
    Batch update previews in a single transaction.

    Handles upload, delete, reorder, and cover change atomically.
    This prevents race conditions from multiple parallel requests.

    Form fields:
    - files: New files to upload (multipart)
    - order: JSON array of filenames in desired order
    - cover_filename: Filename to set as cover
    - deleted: JSON array of filenames to delete
    """
    import json
    from .models import PreviewInfo

    try:
        pack = store.get_pack(pack_name)
        previews_dir = store.layout.pack_previews_path(pack_name)
        previews_dir.mkdir(parents=True, exist_ok=True)

        results = {
            "uploaded": [],
            "deleted": [],
            "reordered": False,
            "cover_changed": False,
        }

        # 1. Delete specified previews
        if deleted:
            deleted_list = json.loads(deleted)
            for filename in deleted_list:
                # Remove from pack.previews
                pack.previews = [p for p in pack.previews if p.filename != filename]
                # Delete file
                file_path = previews_dir / filename
                if file_path.exists():
                    file_path.unlink()
                results["deleted"].append(filename)
                logger.info(f"[batch_update_previews] Deleted: {filename}")

        # 2. Upload new files
        allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.mp4', '.webm'}
        for file in files:
            ext = Path(file.filename).suffix.lower()
            if ext not in allowed_extensions:
                logger.warning(f"[batch_update_previews] Skipping unsupported file: {file.filename}")
                continue

            media_type = 'video' if ext in {'.mp4', '.webm'} else 'image'
            dest_path = previews_dir / file.filename
            content = file.file.read()
            dest_path.write_bytes(content)

            preview = PreviewInfo(
                filename=file.filename,
                url=f"/packs/{pack_name}/resources/previews/{file.filename}",
                media_type=media_type,
                nsfw=False,
            )
            pack.previews.append(preview)
            results["uploaded"].append(file.filename)
            logger.info(f"[batch_update_previews] Uploaded: {file.filename}")

        # 3. Reorder previews
        if order:
            order_list = json.loads(order)
            preview_map = {p.filename: p for p in pack.previews}
            new_previews = []

            # Add in specified order
            for filename in order_list:
                if filename in preview_map:
                    new_previews.append(preview_map.pop(filename))

            # Append any remaining
            new_previews.extend(preview_map.values())
            pack.previews = new_previews
            results["reordered"] = True
            logger.info(f"[batch_update_previews] Reordered {len(new_previews)} previews")

        # 4. Set cover
        if cover_filename:
            for p in pack.previews:
                if p.filename == cover_filename:
                    pack.cover_url = p.url
                    results["cover_changed"] = True
                    logger.info(f"[batch_update_previews] Set cover: {cover_filename}")
                    break

        # Single atomic save
        store.layout.save_pack(pack)

        return {
            "success": True,
            "pack_name": pack_name,
            **results,
            "total_previews": len(pack.previews),
        }
    except Exception as e:
        logger.error(f"[batch_update_previews] Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@v2_packs_router.post("/{pack_name}/previews/upload", response_model=Dict[str, Any])
def upload_preview(
    pack_name: str,
    file: UploadFile = File(...),
    position: int = Form(-1),  # -1 = append at end
    nsfw: bool = Form(False),
    set_as_cover: bool = Form(False),
    store=Depends(require_initialized),
):
    """
    Upload a preview image or video to a pack.

    Supports jpg, png, gif, webp, mp4, webm.
    Position -1 appends at end, 0 inserts at beginning.
    """
    from .models import PreviewInfo

    try:
        pack = store.get_pack(pack_name)

        # Validate file type
        allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.mp4', '.webm'}
        ext = Path(file.filename).suffix.lower()
        if ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {ext}. Allowed: {', '.join(allowed_extensions)}"
            )

        # Determine media type
        media_type = 'video' if ext in {'.mp4', '.webm'} else 'image'

        # Save file to previews directory
        previews_dir = store.layout.pack_previews_path(pack_name)
        previews_dir.mkdir(parents=True, exist_ok=True)

        dest_path = previews_dir / file.filename
        content = file.file.read()
        dest_path.write_bytes(content)

        # Create preview info
        preview = PreviewInfo(
            filename=file.filename,
            url=f"/packs/{pack_name}/resources/previews/{file.filename}",
            media_type=media_type,
            nsfw=nsfw,
        )

        # Insert at position
        if position < 0 or position >= len(pack.previews):
            pack.previews.append(preview)
        else:
            pack.previews.insert(position, preview)

        # Set as cover if requested
        if set_as_cover:
            pack.cover_url = preview.url

        store.layout.save_pack(pack)

        logger.info(f"[upload_preview] Added {file.filename} to {pack_name}")

        return {
            "success": True,
            "filename": file.filename,
            "media_type": media_type,
            "position": position if position >= 0 else len(pack.previews) - 1,
            "is_cover": set_as_cover,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[upload_preview] Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@v2_packs_router.get("/{pack_name}/previews", response_model=List[Dict[str, Any]])
def list_pack_previews(
    pack_name: str,
    store=Depends(require_initialized),
):
    """List all previews for a pack with metadata."""
    try:
        pack = store.get_pack(pack_name)
        previews = []

        for i, preview in enumerate(pack.previews):
            is_cover = (
                pack.cover_url == preview.url if pack.cover_url
                else i == 0  # First preview is default cover
            )
            previews.append({
                "filename": preview.filename,
                "url": preview.url,
                "media_type": preview.media_type,
                "width": preview.width,
                "height": preview.height,
                "nsfw": preview.nsfw,
                "is_cover": is_cover,
                "meta": preview.meta,
                "duration": preview.duration,
                "has_audio": preview.has_audio,
                "thumbnail_url": preview.thumbnail_url,
            })

        return previews
    except Exception as e:
        logger.error(f"[list_previews] Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@v2_packs_router.patch("/{pack_name}/previews/order", response_model=Dict[str, Any])
def reorder_previews(
    pack_name: str,
    request: PreviewOrderRequest,
    store=Depends(require_initialized),
):
    """
    Reorder previews for a pack.

    The order list should contain filenames in the desired order.
    Filenames not in the list will be appended at the end.
    """
    try:
        pack = store.get_pack(pack_name)

        # Create a map of filename -> preview
        preview_map = {p.filename: p for p in pack.previews}

        # Build new order
        new_previews = []
        for filename in request.order:
            if filename in preview_map:
                new_previews.append(preview_map.pop(filename))

        # Append any remaining previews not in the order
        new_previews.extend(preview_map.values())

        pack.previews = new_previews
        store.layout.save_pack(pack)

        logger.info(f"[reorder_previews] Reordered {len(new_previews)} previews for {pack_name}")

        return {
            "success": True,
            "count": len(new_previews),
            "order": [p.filename for p in new_previews],
        }
    except Exception as e:
        logger.error(f"[reorder_previews] Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@v2_packs_router.patch("/{pack_name}/previews/{filename}/cover", response_model=Dict[str, Any])
def set_cover_preview(
    pack_name: str,
    filename: str,
    store=Depends(require_initialized),
):
    """Set a specific preview as the pack cover image."""
    try:
        pack = store.get_pack(pack_name)

        # Find the preview
        preview = None
        for p in pack.previews:
            if p.filename == filename:
                preview = p
                break

        if not preview:
            raise HTTPException(status_code=404, detail=f"Preview not found: {filename}")

        # Set cover_url to the preview's URL
        pack.cover_url = preview.url
        store.layout.save_pack(pack)

        logger.info(f"[set_cover] Set cover for {pack_name}: {filename}")

        return {
            "success": True,
            "cover_url": pack.cover_url,
            "filename": filename,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[set_cover] Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@v2_packs_router.delete("/{pack_name}/previews/{filename}", response_model=Dict[str, Any])
def delete_preview(
    pack_name: str,
    filename: str,
    store=Depends(require_initialized),
):
    """
    Delete a preview from a pack.

    Removes both the file and the entry from pack.json.
    If this was the cover, cover_url will be cleared.
    """
    try:
        pack = store.get_pack(pack_name)

        # Find and remove the preview from the list
        original_count = len(pack.previews)
        removed_preview = None
        for p in pack.previews:
            if p.filename == filename:
                removed_preview = p
                break

        if not removed_preview:
            raise HTTPException(status_code=404, detail=f"Preview not found: {filename}")

        pack.previews = [p for p in pack.previews if p.filename != filename]

        # Clear cover_url if this was the cover
        if pack.cover_url and removed_preview.url == pack.cover_url:
            pack.cover_url = None

        # Delete the file if it exists locally
        previews_dir = store.layout.pack_previews_path(pack_name)
        preview_file = previews_dir / filename
        if preview_file.exists():
            preview_file.unlink()
            logger.info(f"[delete_preview] Deleted file: {preview_file}")

        store.layout.save_pack(pack)

        logger.info(f"[delete_preview] Removed preview {filename} from {pack_name}")

        return {
            "success": True,
            "deleted": filename,
            "remaining_count": len(pack.previews),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[delete_preview] Error: {e}")
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
        result = store.reset(ui_set=request.ui_set, sync=request.sync)

        # Convert to legacy API format for backwards compatibility
        ui_results = {}
        for ui, from_profile in result.from_profiles.items():
            ui_results[ui] = {
                "reset": True,
                "profile": "global",
                "from_profile": from_profile,
            }

        return {
            "ok": True,
            "reset": True,
            "ui_results": ui_results,
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
        # Convert options if provided
        update_options = None
        if request.options:
            from .models import UpdateOptions
            update_options = UpdateOptions(
                merge_previews=request.options.merge_previews,
                update_description=request.options.update_description,
                update_model_info=request.options.update_model_info,
            )

        result = store.update(
            request.pack,
            dry_run=request.dry_run,
            choose=request.choose,
            sync=request.sync,
            ui_set=request.ui_set,
            options=update_options,
        )
        return result.model_dump()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@updates_router.post("/apply-batch", response_model=Dict[str, Any])
def apply_batch_update(
    request: BatchUpdateRequest,
    store=Depends(require_initialized),
):
    """Apply updates to multiple packs."""
    try:
        update_options = None
        if request.options:
            from .models import UpdateOptions
            update_options = UpdateOptions(
                merge_previews=request.options.merge_previews,
                update_description=request.options.update_description,
                update_model_info=request.options.update_model_info,
            )

        result = store.update_batch(
            request.packs,
            choose=request.choose,
            sync=request.sync,
            ui_set=request.ui_set,
            options=update_options,
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
# AI Services Router
# =============================================================================

ai_router = APIRouter(prefix="/ai", tags=["ai"])


class AIProviderStatusResponse(BaseModel):
    """Status of an AI provider."""
    provider_id: str
    available: bool
    running: bool
    version: Optional[str] = None
    models: List[str] = []
    error: Optional[str] = None


class AIDetectionResponse(BaseModel):
    """Response for provider detection."""
    providers: Dict[str, AIProviderStatusResponse]
    available_count: int
    running_count: int


class AIExtractionRequest(BaseModel):
    """Request for parameter extraction."""
    description: str
    use_cache: bool = True


class AIExtractionResponse(BaseModel):
    """Response for parameter extraction."""
    success: bool
    parameters: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    provider_id: Optional[str] = None
    model: Optional[str] = None
    cached: bool = False
    execution_time_ms: int = 0


class AICacheStatsResponse(BaseModel):
    """Response for cache stats."""
    cache_dir: str
    entry_count: int
    total_size_bytes: int
    total_size_mb: float
    ttl_days: int


class AISettingsResponse(BaseModel):
    """Response for AI settings."""
    enabled: bool
    providers: Dict[str, Any]
    task_priorities: Dict[str, Any]
    cli_timeout_seconds: int
    max_retries: int = 2
    retry_delay_seconds: int = 1
    cache_enabled: bool
    cache_ttl_days: int
    cache_directory: str = "~/.synapse/store/data/cache/ai"
    always_fallback_to_rule_based: bool
    show_provider_in_results: bool = True
    log_requests: bool = True
    log_level: str = "INFO"
    log_prompts: bool = False
    log_responses: bool = False


class AISettingsUpdateRequest(BaseModel):
    """Request for updating AI settings."""
    enabled: Optional[bool] = None
    providers: Optional[Dict[str, Any]] = None
    task_priorities: Optional[Dict[str, Any]] = None
    cli_timeout_seconds: Optional[int] = None
    max_retries: Optional[int] = None
    retry_delay_seconds: Optional[int] = None
    cache_enabled: Optional[bool] = None
    cache_ttl_days: Optional[int] = None
    always_fallback_to_rule_based: Optional[bool] = None
    show_provider_in_results: Optional[bool] = None
    log_requests: Optional[bool] = None
    log_level: Optional[str] = None
    log_prompts: Optional[bool] = None
    log_responses: Optional[bool] = None


@ai_router.get("/providers", response_model=AIDetectionResponse)
def detect_providers():
    """Detect available AI providers."""
    from src.ai import detect_ai_providers

    providers = detect_ai_providers()

    response_providers = {}
    for pid, status in providers.items():
        response_providers[pid] = AIProviderStatusResponse(
            provider_id=status.provider_id,
            available=status.available,
            running=status.running,
            version=status.version,
            models=status.models,
            error=status.error,
        )

    return AIDetectionResponse(
        providers=response_providers,
        available_count=sum(1 for s in providers.values() if s.available),
        running_count=sum(1 for s in providers.values() if s.running),
    )


@ai_router.post("/extract", response_model=AIExtractionResponse)
def extract_parameters(request: AIExtractionRequest):
    """Extract generation parameters from description using AI."""
    from src.ai import AIService, AIServicesSettings

    service = AIService(AIServicesSettings.load())
    result = service.extract_parameters(
        description=request.description,
        use_cache=request.use_cache,
    )

    return AIExtractionResponse(
        success=result.success,
        parameters=result.output if result.success else None,
        error=result.error,
        provider_id=result.provider_id,
        model=result.model,
        cached=result.cached,
        execution_time_ms=result.execution_time_ms,
    )


@ai_router.get("/cache/stats", response_model=AICacheStatsResponse)
def get_cache_stats():
    """Get AI cache statistics."""
    from src.ai import AIService, AIServicesSettings

    service = AIService(AIServicesSettings.load())
    stats = service.get_cache_stats()

    return AICacheStatsResponse(**stats)


@ai_router.delete("/cache")
def clear_cache():
    """Clear all AI cache entries."""
    from src.ai import AIService, AIServicesSettings

    service = AIService(AIServicesSettings.load())
    count = service.clear_cache()

    return {"cleared": count}


@ai_router.post("/cache/cleanup")
def cleanup_cache():
    """Remove expired AI cache entries."""
    from src.ai import AIService, AIServicesSettings

    service = AIService(AIServicesSettings.load())
    count = service.cleanup_cache()

    return {"cleaned": count}


@ai_router.get("/settings", response_model=AISettingsResponse)
def get_ai_settings():
    """Get current AI settings."""
    from src.ai import AIServicesSettings

    settings = AIServicesSettings.load()

    return AISettingsResponse(
        enabled=settings.enabled,
        providers={k: v.to_dict() for k, v in settings.providers.items()},
        task_priorities={k: v.to_dict() for k, v in settings.task_priorities.items()},
        cli_timeout_seconds=settings.cli_timeout_seconds,
        max_retries=settings.max_retries,
        retry_delay_seconds=settings.retry_delay_seconds,
        cache_enabled=settings.cache_enabled,
        cache_ttl_days=settings.cache_ttl_days,
        cache_directory=settings.cache_directory,
        always_fallback_to_rule_based=settings.always_fallback_to_rule_based,
        show_provider_in_results=settings.show_provider_in_results,
        log_requests=settings.log_requests,
        log_level=settings.log_level,
        log_prompts=settings.log_prompts,
        log_responses=settings.log_responses,
    )


@ai_router.patch("/settings", response_model=AISettingsResponse)
def update_ai_settings(request: AISettingsUpdateRequest):
    """
    Update AI settings and persist to disk.

    Settings are saved to: ~/.synapse/store/data/ai_settings.json
    """
    from src.ai import AIServicesSettings, ProviderConfig, TaskPriorityConfig

    # Load current settings from disk
    settings = AIServicesSettings.load()

    # Update only provided fields
    if request.enabled is not None:
        settings.enabled = request.enabled

    if request.providers is not None:
        for provider_id, provider_data in request.providers.items():
            # Ensure provider_id is set in the data
            provider_data["provider_id"] = provider_id
            settings.providers[provider_id] = ProviderConfig.from_dict(provider_data)

    if request.task_priorities is not None:
        for task_type, priority_data in request.task_priorities.items():
            # Ensure task_type is set in the data
            priority_data["task_type"] = task_type
            settings.task_priorities[task_type] = TaskPriorityConfig.from_dict(priority_data)

    if request.cli_timeout_seconds is not None:
        settings.cli_timeout_seconds = request.cli_timeout_seconds

    if request.max_retries is not None:
        settings.max_retries = request.max_retries

    if request.retry_delay_seconds is not None:
        settings.retry_delay_seconds = request.retry_delay_seconds

    if request.cache_enabled is not None:
        settings.cache_enabled = request.cache_enabled

    if request.cache_ttl_days is not None:
        settings.cache_ttl_days = request.cache_ttl_days

    if request.always_fallback_to_rule_based is not None:
        settings.always_fallback_to_rule_based = request.always_fallback_to_rule_based

    if request.show_provider_in_results is not None:
        settings.show_provider_in_results = request.show_provider_in_results

    if request.log_requests is not None:
        settings.log_requests = request.log_requests

    if request.log_level is not None:
        settings.log_level = request.log_level

    if request.log_prompts is not None:
        settings.log_prompts = request.log_prompts

    if request.log_responses is not None:
        settings.log_responses = request.log_responses

    # Save to disk
    if not settings.save():
        raise HTTPException(status_code=500, detail="Failed to save AI settings to disk")

    logger.info(f"[ai-settings] Updated and saved AI settings: enabled={settings.enabled}")

    return AISettingsResponse(
        enabled=settings.enabled,
        providers={k: v.to_dict() for k, v in settings.providers.items()},
        task_priorities={k: v.to_dict() for k, v in settings.task_priorities.items()},
        cli_timeout_seconds=settings.cli_timeout_seconds,
        max_retries=settings.max_retries,
        retry_delay_seconds=settings.retry_delay_seconds,
        cache_enabled=settings.cache_enabled,
        cache_ttl_days=settings.cache_ttl_days,
        cache_directory=settings.cache_directory,
        always_fallback_to_rule_based=settings.always_fallback_to_rule_based,
        show_provider_in_results=settings.show_provider_in_results,
        log_requests=settings.log_requests,
        log_level=settings.log_level,
        log_prompts=settings.log_prompts,
        log_responses=settings.log_responses,
    )


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
        ai_router,
    ]
