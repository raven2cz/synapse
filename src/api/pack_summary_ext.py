"""
Pack Summary API Extension - Adds thumbnail_type to pack listing.

This module extends the pack listing API to include information about
whether the thumbnail is an image or video.

Author: Synapse Team
License: MIT
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field


class PackSummaryExtended(BaseModel):
    """
    Extended pack summary for listing with thumbnail type info.
    
    This extends the base PackSummary with thumbnail_type field
    to support video thumbnail display in the UI.
    
    Attributes:
        name: Pack name
        version: Pack version string
        description: Pack description
        installed: Whether pack dependencies are installed
        assets_count: Number of assets/dependencies
        previews_count: Total preview count
        nsfw_previews_count: NSFW preview count  
        source_url: Civitai source URL
        created_at: Creation timestamp
        thumbnail: Thumbnail URL
        thumbnail_type: Type of thumbnail ('image' or 'video')
        tags: Model tags from source
        user_tags: User-defined tags
        has_unresolved: Whether pack has unresolved dependencies
        model_type: Model type (LORA, Checkpoint, etc.)
        base_model: Base model (SD 1.5, SDXL, etc.)
    """
    name: str
    version: str = "1.0.0"
    description: Optional[str] = None
    installed: bool = False
    assets_count: int = 0
    previews_count: int = 0
    nsfw_previews_count: int = 0
    source_url: Optional[str] = None
    created_at: Optional[str] = None
    thumbnail: Optional[str] = None
    thumbnail_type: Literal['image', 'video', 'unknown'] = Field(
        default='image',
        description="Type of thumbnail media for proper rendering"
    )
    tags: list[str] = Field(default_factory=list)
    user_tags: list[str] = Field(default_factory=list)
    has_unresolved: bool = False
    model_type: Optional[str] = None
    base_model: Optional[str] = None


def determine_thumbnail_type(thumbnail_url: Optional[str], previews: list = None) -> str:
    """
    Determine thumbnail type from URL or preview list.
    
    Checks the thumbnail URL extension or looks at the first preview
    to determine if the thumbnail is an image or video.
    
    Args:
        thumbnail_url: URL of the thumbnail
        previews: List of preview objects with media_type field
        
    Returns:
        'image', 'video', or 'unknown'
    """
    if not thumbnail_url:
        return 'image'
    
    # Check extension
    url_lower = thumbnail_url.lower()
    video_extensions = ['.mp4', '.webm', '.mov', '.avi']
    
    for ext in video_extensions:
        if ext in url_lower:
            return 'video'
    
    # Check for Civitai video patterns
    if 'transcode=true' in url_lower:
        return 'video'
    
    # If we have previews, check the first one
    if previews:
        first_preview = previews[0] if previews else None
        if first_preview:
            media_type = (
                first_preview.get('media_type') 
                if isinstance(first_preview, dict) 
                else getattr(first_preview, 'media_type', None)
            )
            if media_type == 'video':
                return 'video'
    
    return 'image'


def extend_pack_summary_response(pack_data: dict, previews: list = None) -> dict:
    """
    Extend pack summary dict with thumbnail_type.
    
    This helper can be used in the API to add thumbnail_type
    to existing pack listing responses.
    
    Args:
        pack_data: Pack summary dictionary
        previews: Optional list of preview objects
        
    Returns:
        Extended pack_data with thumbnail_type
    """
    thumbnail_url = pack_data.get('thumbnail')
    pack_data['thumbnail_type'] = determine_thumbnail_type(thumbnail_url, previews)
    return pack_data
