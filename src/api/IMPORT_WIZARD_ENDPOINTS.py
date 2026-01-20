"""
Import Wizard API Endpoints Patch

Add these endpoints to src/store/api.py to support the Import Wizard feature.

INSTALLATION:
1. Add the new Pydantic models below to the existing models section
2. Add the endpoints to v2_packs_router
3. Register import_router if separate

Alternatively, paste these directly into src/store/api.py
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Query, Depends
import logging
import re

logger = logging.getLogger(__name__)

# Create router for standalone use - normally these would be added to v2_packs_router
v2_packs_router = APIRouter(tags=["import-wizard"])


# Stub dependency for standalone testing - actual implementation is in src.store.api
def require_initialized():
    """Placeholder dependency - should be imported from src.store.api in production."""
    return None


# =============================================================================
# NEW MODELS - Add to existing models section in api.py
# =============================================================================

class WizardVersionFile(BaseModel):
    """File info for wizard display."""
    id: int = 0
    name: str
    sizeKB: Optional[float] = None
    type: Optional[str] = None
    primary: bool = False


class WizardVersionInfo(BaseModel):
    """Version info for wizard display."""
    id: int
    name: str
    base_model: Optional[str] = None
    download_count: Optional[int] = None
    created_at: Optional[str] = None
    files: List[WizardVersionFile] = []
    image_count: int = 0
    video_count: int = 0
    nsfw_count: int = 0
    total_size_bytes: int = 0


class WizardThumbnailOption(BaseModel):
    """Thumbnail option for wizard selection."""
    url: str
    version_id: Optional[int] = None
    nsfw: bool = False
    type: str = "image"  # "image" or "video"
    width: Optional[int] = None
    height: Optional[int] = None


class ImportPreviewResponse(BaseModel):
    """Response for import preview endpoint."""
    model_id: int
    model_name: str
    creator: Optional[str] = None
    model_type: Optional[str] = None
    base_model: Optional[str] = None
    versions: List[WizardVersionInfo] = []
    total_size_bytes: int = 0
    total_size_formatted: str = "0 B"
    total_image_count: int = 0
    total_video_count: int = 0
    total_nsfw_count: int = 0
    thumbnail_options: List[WizardThumbnailOption] = []


class WizardImportRequest(BaseModel):
    """Extended import request with wizard options."""
    url: str = Field(..., description="Civitai model URL")
    version_ids: Optional[List[int]] = Field(None, description="Specific versions to import")
    download_images: bool = Field(True, description="Download image previews")
    download_videos: bool = Field(True, description="Download video previews")
    include_nsfw: bool = Field(True, description="Include NSFW content")
    thumbnail_url: Optional[str] = Field(None, description="Custom thumbnail URL")
    pack_name: Optional[str] = Field(None, description="Custom pack name")
    # Legacy fields for compatibility
    download_previews: bool = True
    add_to_global: bool = True


class WizardImportResponse(BaseModel):
    """Response for wizard import endpoint."""
    success: bool
    pack_name: Optional[str] = None
    message: str = ""
    errors: List[str] = []
    warnings: List[str] = []
    previews_downloaded: int = 0
    videos_downloaded: int = 0


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def parse_civitai_url(url: str) -> Optional[int]:
    """Extract model ID from Civitai URL."""
    patterns = [
        r'civitai\.com/models/(\d+)',
        r'civitai\.com/api/.*models/(\d+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return int(match.group(1))
    return None


def format_file_size(size_bytes: int) -> str:
    """Format bytes to human readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def detect_video_url(url: str) -> bool:
    """Check if URL points to video content."""
    url_lower = url.lower()
    if any(ext in url_lower for ext in ['.mp4', '.webm', '.mov']):
        return True
    if 'transcode=true' in url_lower and 'anim=false' not in url_lower:
        return True
    return False


# =============================================================================
# ENDPOINTS - Add to v2_packs_router in api.py
# =============================================================================

# Add this endpoint to v2_packs_router:

@v2_packs_router.get("/import/preview", response_model=ImportPreviewResponse)
def import_preview(url: str = Query(..., description="Civitai model URL")):
    """
    Fetch model information for Import Wizard display.
    
    Returns detailed version info, file sizes, and preview thumbnails
    to allow user to select import options.
    """
    from config.settings import get_config
    from src.clients.civitai_client import CivitaiClient
    
    logger.info(f"[ImportWizard] Preview request for: {url}")
    
    # Parse URL
    model_id = parse_civitai_url(url)
    if not model_id:
        raise HTTPException(
            status_code=400,
            detail="Invalid Civitai URL. Expected: https://civitai.com/models/12345"
        )
    
    try:
        # Fetch from Civitai
        config = get_config()
        client = CivitaiClient(api_token=config.api.civitai_token)
        model_data = client.get_model(model_id)
        
        if not model_data:
            raise HTTPException(status_code=404, detail=f"Model not found: {model_id}")
        
        # Build response
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
                files.append(WizardVersionFile(
                    id=f.get("id", 0),
                    name=f.get("name", "unknown"),
                    sizeKB=size_kb,
                    type=f.get("type"),
                    primary=f.get("primary", False),
                ))
            
            # Count previews
            images = version.get("images", [])
            image_count = 0
            video_count = 0
            nsfw_count = 0
            
            for img in images:
                img_url = img.get("url", "")
                is_nsfw = img.get("nsfw", False) or (img.get("nsfwLevel", 1) >= 4)
                is_video = detect_video_url(img_url)
                
                if is_nsfw:
                    nsfw_count += 1
                if is_video:
                    video_count += 1
                else:
                    image_count += 1
                
                # Add to thumbnails
                all_thumbnails.append(WizardThumbnailOption(
                    url=img_url,
                    version_id=version.get("id"),
                    nsfw=is_nsfw,
                    type="video" if is_video else "image",
                    width=img.get("width"),
                    height=img.get("height"),
                ))
            
            versions.append(WizardVersionInfo(
                id=version.get("id", 0),
                name=version.get("name", "Unknown"),
                base_model=version.get("baseModel"),
                download_count=version.get("stats", {}).get("downloadCount"),
                created_at=version.get("createdAt"),
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
        
        return ImportPreviewResponse(
            model_id=model_id,
            model_name=model_data.get("name", "Unknown Model"),
            creator=creator_name,
            model_type=model_data.get("type"),
            base_model=versions[0].base_model if versions else None,
            versions=versions,
            total_size_bytes=int(total_size),
            total_size_formatted=format_file_size(int(total_size)),
            total_image_count=total_images,
            total_video_count=total_videos,
            total_nsfw_count=total_nsfw,
            thumbnail_options=all_thumbnails[:20],  # Limit to 20
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[ImportWizard] Preview failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Replace existing import endpoint with this extended version:

@v2_packs_router.post("/import", response_model=WizardImportResponse)
def import_pack_with_wizard(
    request: WizardImportRequest,
    store=Depends(require_initialized),
):
    """
    Import pack with wizard options.
    
    Supports:
    - Multi-version selection (version_ids)
    - Preview filtering (download_images, download_videos, include_nsfw)
    - Custom thumbnail (thumbnail_url)
    """
    logger.info(f"[ImportWizard] Import: {request.url}")
    logger.info(f"[ImportWizard] Options: versions={request.version_ids}, "
                f"images={request.download_images}, videos={request.download_videos}, "
                f"nsfw={request.include_nsfw}")
    
    try:
        # Use store's import_civitai with extended options
        # Note: store.import_civitai needs to accept these params
        pack = store.import_civitai(
            request.url,
            download_previews=request.download_images or request.download_videos,
            add_to_global=request.add_to_global,
            # Extended options - may need pack_service update
            version_ids=request.version_ids,
            download_images=request.download_images,
            download_videos=request.download_videos,
            include_nsfw=request.include_nsfw,
            thumbnail_url=request.thumbnail_url,
        )
        
        return WizardImportResponse(
            success=True,
            pack_name=pack.name,
            message=f"Successfully imported '{pack.name}'",
        )
        
    except TypeError as e:
        # If store.import_civitai doesn't support new params, use basic import
        if "unexpected keyword argument" in str(e):
            logger.warning("[ImportWizard] Store doesn't support wizard params, using basic import")
            pack = store.import_civitai(
                request.url,
                download_previews=True,
                add_to_global=request.add_to_global,
            )
            return WizardImportResponse(
                success=True,
                pack_name=pack.name,
                message=f"Successfully imported '{pack.name}' (with default options)",
                warnings=["Wizard options not yet supported by backend"],
            )
        raise
        
    except Exception as e:
        logger.exception(f"[ImportWizard] Import failed: {e}")
        return WizardImportResponse(
            success=False,
            message=f"Import failed: {str(e)}",
            errors=[str(e)],
        )


# =============================================================================
# INSTALLATION INSTRUCTIONS
# =============================================================================
"""
To add these endpoints to your api.py:

1. Add the Pydantic models (WizardVersionFile, WizardVersionInfo, etc.) 
   to the models section at the top of api.py

2. Add the helper functions (parse_civitai_url, format_file_size, detect_video_url)
   near other helper functions

3. Add the endpoints to v2_packs_router:
   - GET /import/preview - for wizard preview
   - POST /import - replace existing or add as alternative

4. Make sure these imports exist:
   from fastapi import Query
   import re

5. Test:
   curl "http://localhost:8000/api/packs/import/preview?url=https://civitai.com/models/12345"
"""
