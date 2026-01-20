"""
Import API Models - Extended request/response models for pack import.

This module defines the Pydantic models used by the import API endpoints,
including support for multi-version import, video download options, and
preview filtering.

Author: Synapse Team
License: MIT
"""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


# =============================================================================
# Import Request Models
# =============================================================================

class ImportRequest(BaseModel):
    """
    Request model for pack import from Civitai URL.
    
    Supports multi-version import with configurable preview options.
    
    Attributes:
        url: Civitai model URL (required)
        version_ids: List of version IDs to import (None = first version only)
        download_images: Whether to download image previews
        download_videos: Whether to download video previews
        include_nsfw: Whether to include NSFW content
        thumbnail_url: Custom thumbnail URL for the pack
        pack_name: Custom pack name (default: model name)
        pack_description: Custom pack description
        download_previews: Deprecated - use download_images/download_videos
        add_to_global: Whether to add pack to global profile
    
    Example:
        >>> request = ImportRequest(
        ...     url="https://civitai.com/models/12345",
        ...     version_ids=[67890, 67891],
        ...     download_videos=True,
        ...     include_nsfw=False,
        ... )
    """
    # Required
    url: str = Field(..., description="Civitai model URL")
    
    # Version selection
    version_ids: Optional[List[int]] = Field(
        default=None,
        description="Version IDs to import. None = first version only."
    )
    
    # Preview options
    download_images: bool = Field(
        default=True,
        description="Download image preview files"
    )
    download_videos: bool = Field(
        default=True,
        description="Download video preview files"
    )
    include_nsfw: bool = Field(
        default=True,
        description="Include NSFW-flagged previews"
    )
    
    # Pack customization
    thumbnail_url: Optional[str] = Field(
        default=None,
        description="Custom thumbnail URL for the pack"
    )
    pack_name: Optional[str] = Field(
        default=None,
        description="Custom pack name (default: model name from Civitai)"
    )
    pack_description: Optional[str] = Field(
        default=None,
        description="Custom pack description"
    )
    
    # Legacy/compatibility options
    download_previews: bool = Field(
        default=True,
        description="DEPRECATED: Use download_images and download_videos instead"
    )
    add_to_global: bool = Field(
        default=True,
        description="Add imported pack to global profile"
    )


class ImportPreviewRequest(BaseModel):
    """
    Request model for previewing import without executing.
    
    Used by the Import Wizard to show what will be imported
    before the user confirms.
    
    Attributes:
        url: Civitai model URL
        version_ids: Version IDs to preview (None = all versions)
    """
    url: str = Field(..., description="Civitai model URL")
    version_ids: Optional[List[int]] = Field(
        default=None,
        description="Version IDs to preview. None = all versions."
    )


# =============================================================================
# Import Response Models
# =============================================================================

class VersionPreviewInfo(BaseModel):
    """
    Preview information for a single model version.
    
    Attributes:
        id: Version ID
        name: Version name
        base_model: Base model (e.g., "SDXL 1.0")
        files: List of downloadable files with sizes
        image_count: Number of image previews
        video_count: Number of video previews
        nsfw_count: Number of NSFW previews
    """
    id: int
    name: str
    base_model: Optional[str] = None
    files: List[Dict[str, Any]] = Field(default_factory=list)
    image_count: int = 0
    video_count: int = 0
    nsfw_count: int = 0
    total_size_bytes: int = 0


class ImportPreviewResponse(BaseModel):
    """
    Response model for import preview endpoint.
    
    Provides detailed information about what will be imported,
    allowing the user to make informed decisions in the Import Wizard.
    
    Attributes:
        model_id: Civitai model ID
        model_name: Model name
        creator: Creator username
        model_type: Model type (LORA, Checkpoint, etc.)
        base_model: Primary base model
        versions: List of version previews
        total_size_bytes: Total size of all selected versions
        total_size_formatted: Human-readable total size
        total_image_count: Total image preview count
        total_video_count: Total video preview count
        total_nsfw_count: Total NSFW preview count
        thumbnail_options: List of preview URLs for thumbnail selection
    """
    model_id: int
    model_name: str
    creator: Optional[str] = None
    model_type: Optional[str] = None
    base_model: Optional[str] = None
    
    versions: List[VersionPreviewInfo] = Field(default_factory=list)
    
    total_size_bytes: int = 0
    total_size_formatted: str = "0 B"
    total_image_count: int = 0
    total_video_count: int = 0
    total_nsfw_count: int = 0
    
    thumbnail_options: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Available previews for thumbnail selection"
    )


class ImportResult(BaseModel):
    """
    Result of a pack import operation.
    
    Attributes:
        success: Whether import succeeded
        pack_name: Name of imported pack (if successful)
        errors: List of error messages
        warnings: List of warning messages
        message: Summary message
        previews_downloaded: Number of previews downloaded
        videos_downloaded: Number of videos downloaded
    """
    success: bool
    pack_name: Optional[str] = None
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    message: str = ""
    previews_downloaded: int = 0
    videos_downloaded: int = 0


# =============================================================================
# Utility Functions
# =============================================================================

def format_file_size(size_bytes: int) -> str:
    """
    Format byte size to human-readable string.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        Formatted string like "1.5 GB" or "256 MB"
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
