"""
Import API Router - Endpoints for pack import operations.

Provides endpoints for:
- /api/packs/import/preview - Preview import without executing
- /api/packs/import - Execute import with options

Author: Synapse Team
License: MIT
"""

import logging
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from .import_models import (
    ImportRequest,
    ImportPreviewRequest,
    ImportPreviewResponse,
    ImportResult,
    VersionPreviewInfo,
    format_file_size,
)

# Import media detection - handle different import contexts
try:
    from ..utils.media_detection import detect_media_type, MediaType
except ImportError:
    # Fallback for standalone testing
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from utils.media_detection import detect_media_type, MediaType

logger = logging.getLogger(__name__)

# Router for import endpoints
import_router = APIRouter(prefix="/import", tags=["import"])


# =============================================================================
# Helper Functions
# =============================================================================

def parse_civitai_url(url: str) -> Optional[int]:
    """
    Extract model ID from Civitai URL.
    
    Supports formats:
    - https://civitai.com/models/12345
    - https://civitai.com/models/12345/model-name
    - https://civitai.com/models/12345?version=67890
    
    Args:
        url: Civitai URL
        
    Returns:
        Model ID or None if URL is invalid
    """
    patterns = [
        r'civitai\.com/models/(\d+)',
        r'civitai\.com/api/.*models/(\d+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return int(match.group(1))
    
    return None


def count_previews_by_type(
    images: List[Dict[str, Any]],
    include_nsfw: bool = True,
) -> Dict[str, int]:
    """
    Count previews by type (image, video, nsfw).
    
    Args:
        images: List of image/video data from Civitai
        include_nsfw: Whether to count NSFW items
        
    Returns:
        Dict with image_count, video_count, nsfw_count
    """
    image_count = 0
    video_count = 0
    nsfw_count = 0
    
    for img in images:
        url = img.get("url", "")
        is_nsfw = img.get("nsfw", False) or img.get("nsfwLevel", 0) >= 2
        
        if is_nsfw:
            nsfw_count += 1
            if not include_nsfw:
                continue
        
        # Detect media type
        media_info = detect_media_type(url)
        
        if media_info.type == MediaType.VIDEO:
            video_count += 1
        else:
            image_count += 1
    
    return {
        "image_count": image_count,
        "video_count": video_count,
        "nsfw_count": nsfw_count,
    }


def collect_thumbnail_options(
    versions: List[Any],
    max_thumbnails: int = 20,
) -> List[Dict[str, Any]]:
    """
    Collect thumbnail options from all versions.
    
    Args:
        versions: List of version data
        max_thumbnails: Maximum thumbnails to return
        
    Returns:
        List of thumbnail option dicts with url, version_id, nsfw, type
    """
    options = []
    seen_urls = set()
    
    for version in versions:
        version_id = version.get("id") if isinstance(version, dict) else getattr(version, "id", None)
        images = version.get("images", []) if isinstance(version, dict) else getattr(version, "images", [])
        
        for img in images:
            url = img.get("url", "")
            if not url or url in seen_urls:
                continue
            
            seen_urls.add(url)
            
            is_nsfw = img.get("nsfw", False) or img.get("nsfwLevel", 0) >= 2
            media_info = detect_media_type(url)
            
            options.append({
                "url": url,
                "version_id": version_id,
                "nsfw": is_nsfw,
                "type": media_info.type.value,
                "width": img.get("width"),
                "height": img.get("height"),
            })
            
            if len(options) >= max_thumbnails:
                return options
    
    return options


# =============================================================================
# Preview Endpoint
# =============================================================================

@import_router.post("/preview", response_model=ImportPreviewResponse)
async def preview_import(
    request: ImportPreviewRequest,
    # store=Depends(require_initialized),  # Uncomment when integrating
):
    """
    Preview what will be imported without actually importing.
    
    Returns detailed information about the model, versions, file sizes,
    and preview counts to help the user make informed import decisions.
    
    Args:
        request: ImportPreviewRequest with URL and optional version IDs
        
    Returns:
        ImportPreviewResponse with model details and statistics
        
    Raises:
        HTTPException: If URL is invalid or model not found
    """
    logger.info(f"[Import Preview] URL: {request.url}")
    
    # Parse URL
    model_id = parse_civitai_url(request.url)
    if not model_id:
        raise HTTPException(
            status_code=400,
            detail="Invalid Civitai URL. Expected format: https://civitai.com/models/12345"
        )
    
    # TODO: Fetch model data from Civitai API
    # For now, return mock response structure
    # In real implementation:
    # civitai_client = get_civitai_client()
    # model = civitai_client.get_model(model_id)
    
    # Mock response for testing endpoint structure
    # This will be replaced with real Civitai API call
    logger.info(f"[Import Preview] Model ID: {model_id}")
    
    # Return structure that frontend expects
    return ImportPreviewResponse(
        model_id=model_id,
        model_name=f"Model {model_id}",  # Will be replaced with real data
        creator="Unknown",
        model_type="LORA",
        base_model="SDXL 1.0",
        versions=[],
        total_size_bytes=0,
        total_size_formatted="0 B",
        total_image_count=0,
        total_video_count=0,
        total_nsfw_count=0,
        thumbnail_options=[],
    )


# =============================================================================
# Import Endpoint
# =============================================================================

@import_router.post("", response_model=ImportResult)
async def import_pack(
    request: ImportRequest,
    # store=Depends(require_initialized),  # Uncomment when integrating
):
    """
    Import a pack from Civitai URL with configured options.
    
    Supports multi-version import, preview filtering, and custom
    pack naming.
    
    Args:
        request: ImportRequest with URL and import options
        
    Returns:
        ImportResult with success status and statistics
        
    Raises:
        HTTPException: If import fails
    """
    logger.info(f"[Import] Starting import from: {request.url}")
    logger.info(f"[Import] Options: versions={request.version_ids}, "
                f"images={request.download_images}, videos={request.download_videos}, "
                f"nsfw={request.include_nsfw}")
    
    # Parse URL
    model_id = parse_civitai_url(request.url)
    if not model_id:
        raise HTTPException(
            status_code=400,
            detail="Invalid Civitai URL"
        )
    
    # TODO: Implement actual import logic
    # This will call pack_builder with the new options
    # 
    # builder = PackBuilder(civitai_client, config)
    # result = builder.build_from_civitai_url(
    #     url=request.url,
    #     pack_name=request.pack_name,
    #     version_ids=request.version_ids,
    #     download_images=request.download_images,
    #     download_videos=request.download_videos,
    #     include_nsfw=request.include_nsfw,
    #     thumbnail_url=request.thumbnail_url,
    #     custom_description=request.pack_description,
    # )
    
    # Mock response for testing
    return ImportResult(
        success=True,
        pack_name=request.pack_name or f"pack-{model_id}",
        message=f"Import preview - actual import not yet implemented",
        previews_downloaded=0,
        videos_downloaded=0,
    )


# =============================================================================
# Integration Helper
# =============================================================================

def create_import_preview_response(
    model: Any,
    version_ids: Optional[List[int]] = None,
) -> ImportPreviewResponse:
    """
    Create ImportPreviewResponse from Civitai model data.
    
    This is a helper for when the endpoint is fully integrated
    with the Civitai client.
    
    Args:
        model: CivitaiModel object
        version_ids: Optional list of version IDs to include
        
    Returns:
        ImportPreviewResponse with all computed statistics
    """
    # Get versions to process
    all_versions = model.model_versions if hasattr(model, 'model_versions') else []
    
    if version_ids:
        versions = [v for v in all_versions if v.id in version_ids]
    else:
        versions = all_versions
    
    # Compute statistics
    version_infos = []
    total_size = 0
    total_images = 0
    total_videos = 0
    total_nsfw = 0
    
    for version in versions:
        # Count files
        files = version.files if hasattr(version, 'files') else []
        version_size = sum(f.get("sizeKB", 0) * 1024 for f in files if isinstance(f, dict))
        
        # Count previews
        images = version.images if hasattr(version, 'images') else []
        counts = count_previews_by_type(images)
        
        version_infos.append(VersionPreviewInfo(
            id=version.id,
            name=version.name if hasattr(version, 'name') else str(version.id),
            base_model=version.base_model if hasattr(version, 'base_model') else None,
            files=[{"name": f.get("name"), "sizeKB": f.get("sizeKB")} for f in files if isinstance(f, dict)],
            image_count=counts["image_count"],
            video_count=counts["video_count"],
            nsfw_count=counts["nsfw_count"],
            total_size_bytes=int(version_size),
        ))
        
        total_size += version_size
        total_images += counts["image_count"]
        total_videos += counts["video_count"]
        total_nsfw += counts["nsfw_count"]
    
    # Collect thumbnail options
    thumbnails = collect_thumbnail_options(versions)
    
    return ImportPreviewResponse(
        model_id=model.id,
        model_name=model.name if hasattr(model, 'name') else f"Model {model.id}",
        creator=model.creator.get("username") if hasattr(model, 'creator') and model.creator else None,
        model_type=model.type if hasattr(model, 'type') else None,
        base_model=versions[0].base_model if versions and hasattr(versions[0], 'base_model') else None,
        versions=version_infos,
        total_size_bytes=int(total_size),
        total_size_formatted=format_file_size(int(total_size)),
        total_image_count=total_images,
        total_video_count=total_videos,
        total_nsfw_count=total_nsfw,
        thumbnail_options=thumbnails,
    )
