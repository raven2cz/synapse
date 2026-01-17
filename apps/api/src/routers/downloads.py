"""
Downloads Router - v2 Only

Handle asset downloads with progress tracking.
Uses Store v2 for all operations.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from pathlib import Path
import asyncio
import json
import uuid
from datetime import datetime

from src.store.api import get_store

router = APIRouter()


# In-memory download tracking
_downloads: Dict[str, dict] = {}


class DownloadInfo(BaseModel):
    """Download status information."""
    id: str
    pack_name: str
    status: str  # pending, downloading, completed, failed
    progress: float  # 0.0 - 1.0
    current_file: Optional[str] = None
    total_files: int = 0
    completed_files: int = 0
    error: Optional[str] = None
    started_at: str
    completed_at: Optional[str] = None


class DownloadStartRequest(BaseModel):
    """Request to start a download."""
    pack_name: str
    dependency_ids: Optional[List[str]] = None  # If None, download all unresolved


class DownloadStartResponse(BaseModel):
    """Response when starting a download."""
    download_id: str
    pack_name: str
    status: str
    message: str = ""


def _create_download_entry(pack_name: str) -> str:
    """Create a new download tracking entry."""
    download_id = str(uuid.uuid4())[:8]
    _downloads[download_id] = {
        "id": download_id,
        "pack_name": pack_name,
        "status": "pending",
        "progress": 0.0,
        "current_file": None,
        "total_files": 0,
        "completed_files": 0,
        "error": None,
        "started_at": datetime.now().isoformat(),
        "completed_at": None,
    }
    return download_id


def _update_download(download_id: str, **kwargs):
    """Update download entry."""
    if download_id in _downloads:
        _downloads[download_id].update(kwargs)


async def _run_download(download_id: str, pack_name: str, dependency_ids: Optional[List[str]]):
    """Background task to run download."""
    store = get_store()
    
    if not store.layout.is_initialized():
        _update_download(download_id, status="failed", error="Store not initialized")
        return
    
    try:
        _update_download(download_id, status="downloading")
        
        # Get pack and lock
        pack = store.layout.load_pack(pack_name)
        lock = store.layout.load_pack_lock(pack_name)
        
        # Determine what to download
        deps_to_download = []
        if dependency_ids:
            deps_to_download = [d for d in pack.dependencies if d.id in dependency_ids]
        elif lock:
            # Download unresolved or missing blobs
            for dep in pack.dependencies:
                resolved = lock.get_resolved(dep.id)
                if resolved is None:
                    deps_to_download.append(dep)
                elif resolved.artifact.sha256:
                    if not store.blob_store.blob_exists(resolved.artifact.sha256):
                        deps_to_download.append(dep)
        else:
            deps_to_download = list(pack.dependencies)
        
        total = len(deps_to_download)
        _update_download(download_id, total_files=total)
        
        if total == 0:
            _update_download(
                download_id,
                status="completed",
                progress=1.0,
                completed_at=datetime.now().isoformat(),
            )
            return
        
        # Download each dependency
        for i, dep in enumerate(deps_to_download):
            _update_download(
                download_id,
                current_file=dep.id,
                progress=i / total,
            )
            
            try:
                # Use store's install method for single dependency
                # This is a simplified version - full implementation would use
                # the resolver and downloader services
                await asyncio.sleep(0.1)  # Placeholder for actual download
                
            except Exception as e:
                _update_download(
                    download_id,
                    status="failed",
                    error=f"Failed to download {dep.id}: {e}",
                )
                return
            
            _update_download(download_id, completed_files=i + 1)
        
        _update_download(
            download_id,
            status="completed",
            progress=1.0,
            current_file=None,
            completed_at=datetime.now().isoformat(),
        )
        
    except Exception as e:
        _update_download(
            download_id,
            status="failed",
            error=str(e),
        )


@router.get("/", response_model=List[DownloadInfo])
async def list_downloads():
    """List all downloads."""
    return [DownloadInfo(**d) for d in _downloads.values()]


@router.get("/{download_id}", response_model=DownloadInfo)
async def get_download(download_id: str):
    """Get download status."""
    if download_id not in _downloads:
        raise HTTPException(status_code=404, detail=f"Download not found: {download_id}")
    
    return DownloadInfo(**_downloads[download_id])


@router.post("/start", response_model=DownloadStartResponse)
async def start_download(request: DownloadStartRequest, background_tasks: BackgroundTasks):
    """Start downloading a pack's assets."""
    store = get_store()
    
    if not store.layout.is_initialized():
        raise HTTPException(status_code=400, detail="Store not initialized")
    
    # Check pack exists
    if request.pack_name not in store.list_packs():
        raise HTTPException(status_code=404, detail=f"Pack not found: {request.pack_name}")
    
    # Create download entry
    download_id = _create_download_entry(request.pack_name)
    
    # Start background download
    background_tasks.add_task(
        _run_download,
        download_id,
        request.pack_name,
        request.dependency_ids,
    )
    
    return DownloadStartResponse(
        download_id=download_id,
        pack_name=request.pack_name,
        status="pending",
        message="Download started",
    )


@router.delete("/{download_id}")
async def cancel_download(download_id: str):
    """Cancel/remove a download."""
    if download_id not in _downloads:
        raise HTTPException(status_code=404, detail=f"Download not found: {download_id}")
    
    # Mark as cancelled if still running
    if _downloads[download_id]["status"] in ["pending", "downloading"]:
        _downloads[download_id]["status"] = "cancelled"
    
    # Remove from tracking
    del _downloads[download_id]
    
    return {"message": "Download removed", "download_id": download_id}


@router.get("/progress/{download_id}")
async def get_download_progress(download_id: str):
    """Get download progress (for polling)."""
    if download_id not in _downloads:
        raise HTTPException(status_code=404, detail=f"Download not found: {download_id}")
    
    d = _downloads[download_id]
    return {
        "id": d["id"],
        "status": d["status"],
        "progress": d["progress"],
        "current_file": d["current_file"],
        "completed_files": d["completed_files"],
        "total_files": d["total_files"],
    }
