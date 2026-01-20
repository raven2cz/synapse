"""
Pack Builder - Builds Synapse packs from various sources.

This module provides the core functionality for creating packs from:
- Civitai model URLs (with full video preview support)
- ComfyUI workflow JSON files  
- PNG images with embedded workflows

Enhanced Features (v2.6.0):
- Video preview downloading with proper extensions
- Configurable filters (images/videos/NSFW)
- Progress callbacks for large downloads
- Optimized video URLs for quality control
- Extended timeout support for video files

Author: Synapse Team
License: MIT
"""

import json
import logging
import requests
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class PreviewDownloadOptions:
    """
    Configuration options for preview media downloading.
    
    Provides fine-grained control over what types of preview content
    to download during pack import operations.
    
    Attributes:
        download_images: Whether to download image previews (.jpg, .png, etc.)
        download_videos: Whether to download video previews (.mp4)
        include_nsfw: Whether to include NSFW-flagged content
        max_previews: Maximum number of previews to download
        video_quality: Target video width for optimization (450, 720, 1080)
        image_timeout: Timeout in seconds for image downloads
        video_timeout: Timeout in seconds for video downloads (larger files)
    
    Example:
        >>> options = PreviewDownloadOptions(
        ...     download_videos=True,
        ...     include_nsfw=False,
        ...     video_quality=1080,
        ... )
    """
    download_images: bool = True
    download_videos: bool = True
    include_nsfw: bool = True
    max_previews: int = 20
    video_quality: int = 1080
    image_timeout: int = 60
    video_timeout: int = 120


@dataclass
class DownloadProgress:
    """
    Progress information for a single download operation.
    
    Used to track and report download progress through callbacks,
    enabling UI updates during long-running operations.
    
    Attributes:
        index: Current item index (0-based)
        total: Total number of items to download
        filename: Name of the file being downloaded
        url: Source URL
        media_type: Type of media ('image' or 'video')
        bytes_downloaded: Bytes downloaded so far
        total_bytes: Total bytes to download (if known)
        status: Current status ('downloading', 'completed', 'skipped', 'failed')
        error: Error message if status is 'failed'
    """
    index: int
    total: int
    filename: str
    url: str
    media_type: str
    bytes_downloaded: int = 0
    total_bytes: Optional[int] = None
    status: Literal['downloading', 'completed', 'skipped', 'failed'] = 'downloading'
    error: Optional[str] = None
    
    @property
    def percent_complete(self) -> Optional[float]:
        """
        Calculate completion percentage if total bytes is known.
        
        Returns:
            Percentage (0-100) or None if total unknown
        """
        if self.total_bytes and self.total_bytes > 0:
            return (self.bytes_downloaded / self.total_bytes) * 100
        return None
    
    @property
    def size_mb(self) -> Optional[float]:
        """
        Get file size in megabytes.
        
        Returns:
            Size in MB or None if unknown
        """
        if self.total_bytes:
            return self.total_bytes / (1024 * 1024)
        return None


# Type alias for progress callback
ProgressCallback = Callable[[DownloadProgress], None]


@dataclass
class PreviewImage:
    """
    Represents a downloaded preview image or video.
    
    Stores metadata about preview media including local path,
    dimensions, NSFW status, and generation metadata.
    
    Attributes:
        filename: Local filename (e.g., 'preview_1.mp4')
        url: Original source URL
        local_path: Relative path within pack (e.g., 'resources/previews/preview_1.mp4')
        nsfw: Whether this preview is NSFW
        width: Image/video width in pixels
        height: Image/video height in pixels
        media_type: Type of media ('image', 'video', 'unknown')
        duration: Video duration in seconds (videos only)
        has_audio: Whether video has audio (videos only)
        thumbnail_url: Static thumbnail URL for videos
        meta: Generation metadata (prompt, settings, etc.)
    """
    filename: str
    url: Optional[str] = None
    local_path: Optional[str] = None
    nsfw: bool = False
    width: Optional[int] = None
    height: Optional[int] = None
    media_type: Literal['image', 'video', 'unknown'] = 'image'
    duration: Optional[float] = None
    has_audio: Optional[bool] = None
    thumbnail_url: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


@dataclass
class PackMetadata:
    """Pack metadata information."""
    name: str
    version: str = "1.0.0"
    description: Optional[str] = None
    author: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    user_tags: List[str] = field(default_factory=list)
    created_at: Optional[str] = None
    source_url: Optional[str] = None


@dataclass
class Pack:
    """Complete pack definition."""
    metadata: PackMetadata
    dependencies: List[Any] = field(default_factory=list)
    custom_nodes: List[Any] = field(default_factory=list)
    workflows: List[Any] = field(default_factory=list)
    previews: List[PreviewImage] = field(default_factory=list)
    docs: Dict[str, str] = field(default_factory=dict)
    parameters: Optional[Any] = None
    model_info: Optional[Any] = None


@dataclass
class PackBuildResult:
    """Result of a pack build operation."""
    pack: Optional[Pack]
    success: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    pack_dir: Optional[Path] = None


# =============================================================================
# Pack Builder Class
# =============================================================================

class PackBuilder:
    """
    Builds Synapse packs from various sources.
    
    The PackBuilder handles importing models from Civitai, extracting
    workflows from images, and assembling complete pack structures
    with all necessary metadata and previews.
    
    Features:
        - Civitai model import with full video support
        - Configurable preview download options
        - Progress tracking for large downloads
        - Metadata extraction and merging
        - NSFW content filtering
    
    Example:
        >>> builder = PackBuilder(civitai_client, config)
        >>> result = builder.build_from_civitai_url(
        ...     url="https://civitai.com/models/123",
        ...     preview_options=PreviewDownloadOptions(
        ...         download_videos=True,
        ...         video_quality=1080,
        ...     ),
        ...     progress_callback=lambda p: print(f"Downloading: {p.filename}")
        ... )
    """
    
    def __init__(self, civitai_client, config=None):
        """
        Initialize PackBuilder.
        
        Args:
            civitai_client: Civitai API client instance
            config: Optional configuration object with paths
        """
        self.civitai = civitai_client
        self.config = config
    
    def _sanitize_name(self, name: str) -> str:
        """
        Sanitize a string for use as a pack/directory name.
        
        Removes or replaces characters that are problematic for
        file systems while preserving readability.
        
        Args:
            name: Original name string
            
        Returns:
            Sanitized name safe for file system use
        """
        # Replace problematic characters
        for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
            name = name.replace(char, '_')
        # Remove leading/trailing whitespace and dots
        name = name.strip(' .')
        # Limit length
        return name[:100] if len(name) > 100 else name
    
    def _determine_nsfw_status(self, img_data: Dict[str, Any]) -> bool:
        """
        Determine NSFW status from Civitai image data.
        
        Civitai uses multiple fields to indicate NSFW status:
        - nsfw: boolean flag
        - nsfwLevel: numeric level (1=Safe, 2=Soft, 3+=Explicit)
        
        Args:
            img_data: Raw image data from Civitai API
            
        Returns:
            True if content is NSFW, False otherwise
        """
        # Check explicit nsfw flag
        if img_data.get("nsfw", False):
            return True
        
        # Check nsfw level (2+ is considered NSFW)
        nsfw_level = img_data.get("nsfwLevel", 0)
        if isinstance(nsfw_level, (int, float)) and nsfw_level >= 2:
            return True
        
        return False
    
    def _extract_meta_safely(self, img_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Safely extract generation metadata from image data.
        
        Handles various API response formats where meta might be:
        - Directly in 'meta' key
        - In 'metadata' key
        - Nested as meta.meta (API quirk)
        
        Args:
            img_data: Raw image data from API
            
        Returns:
            Extracted metadata dict or None
        """
        meta = img_data.get("meta")
        
        # Try alternative key
        if not meta:
            meta = img_data.get("metadata")
        
        # Handle nested meta (API v1 quirk)
        if isinstance(meta, dict) and "meta" in meta and isinstance(meta["meta"], dict):
            meta = meta["meta"]
        
        # Validate it's a proper dict
        return meta if isinstance(meta, dict) else None
    
    def _download_preview_images(
        self,
        version,
        pack_dir: Path,
        max_previews: int,
        download: bool = True,
        detailed_version_images: Optional[List[Dict[str, Any]]] = None,
        # === NEW v2.6.0 Parameters ===
        download_images: bool = True,
        download_videos: bool = True,
        include_nsfw: bool = True,
        video_quality: int = 1080,
        image_timeout: int = 60,
        video_timeout: int = 120,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> List[PreviewImage]:
        """
        Download preview media (images and videos) to pack resources directory.
        
        This method handles downloading preview content from Civitai with full
        support for both images and videos. It includes configurable filtering
        by media type and NSFW status, optimized video URLs, and progress
        tracking for large downloads.
        
        Media Type Detection:
            Uses URL-based detection to identify videos vs images without
            making additional network requests. Civitai videos are properly
            detected even when served with misleading extensions (.jpeg).
        
        Video Handling:
            - Videos are always saved with .mp4 extension
            - Optimized URLs are used for quality control
            - Longer timeouts account for larger file sizes
            - Thumbnail URLs are extracted for preview display
        
        Metadata Merging:
            When detailed_version_images is provided, metadata is merged from
            the detailed source to include full generation parameters.
        
        Args:
            version: CivitaiModelVersion object with images list
            pack_dir: Target directory for the pack
            max_previews: Maximum number of previews to download
            download: Whether to actually download files (False for dry run)
            detailed_version_images: Detailed image data with full metadata
            download_images: Whether to download image files
            download_videos: Whether to download video files
            include_nsfw: Whether to include NSFW content
            video_quality: Target video width (450, 720, 1080)
            progress_callback: Optional callback for progress updates
            
        Returns:
            List of PreviewImage objects with metadata
            
        Example:
            >>> previews = builder._download_preview_images(
            ...     version=model_version,
            ...     pack_dir=Path("/packs/my-model"),
            ...     max_previews=20,
            ...     download_videos=True,
            ...     include_nsfw=False,
            ...     video_quality=1080,
            ...     progress_callback=lambda p: print(f"{p.percent_complete:.0f}%")
            ... )
        """
        # Import detection utilities (avoid circular imports)
        from ..utils.media_detection import (
            detect_media_type,
            get_video_thumbnail_url,
            get_optimized_video_url,
        )
        
        previews: List[PreviewImage] = []
        resources_dir = pack_dir / "resources" / "previews"
        
        if download:
            resources_dir.mkdir(parents=True, exist_ok=True)
        
        # Build lookup map for detailed images by URL (metadata merge)
        detailed_map: Dict[str, Dict[str, Any]] = {}
        if detailed_version_images:
            for img in detailed_version_images:
                url = img.get("url")
                if url:
                    detailed_map[url] = img
        
        # Get images from version (limit to max_previews)
        images = version.images[:max_previews] if version.images else []
        
        # Track downloaded URLs to avoid duplicates
        downloaded_urls: set = set()
        
        # Counter for actually processed items
        preview_number = 0
        total_to_process = len(images)
        
        for i, img_data in enumerate(images):
            url = img_data.get("url", "")
            if not url:
                continue
            
            # Skip duplicates
            if url in downloaded_urls:
                logger.debug(f"[PackBuilder] Skipping duplicate URL: {url[:80]}...")
                continue
            
            # MERGE: Get richer data if available
            detailed_img = detailed_map.get(url)
            source_img = detailed_img if detailed_img else img_data
            
            # Determine NSFW status
            is_nsfw = self._determine_nsfw_status(source_img)
            
            # === NSFW FILTER ===
            if is_nsfw and not include_nsfw:
                logger.debug(f"[PackBuilder] Skipping NSFW preview: {url[:80]}...")
                continue
            
            # Detect media type from URL
            media_info = detect_media_type(url, use_head_request=False)
            media_type = media_info.type.value  # 'image', 'video', 'unknown'
            
            # === MEDIA TYPE FILTER ===
            if media_type == 'video' and not download_videos:
                logger.debug(f"[PackBuilder] Skipping video (disabled): {url[:80]}...")
                continue
            
            if media_type == 'image' and not download_images:
                logger.debug(f"[PackBuilder] Skipping image (disabled): {url[:80]}...")
                continue
            
            # Increment preview number only for items we're keeping
            preview_number += 1
            
            # Generate filename with appropriate extension
            url_path = url.split("?")[0]
            original_ext = Path(url_path).suffix or ".png"
            
            # For videos: ALWAYS use .mp4 extension regardless of original
            if media_type == 'video':
                filename = f"preview_{preview_number}.mp4"
            else:
                filename = f"preview_{preview_number}{original_ext}"
            
            local_path = f"resources/previews/{filename}"
            
            # Extract metadata
            meta = self._extract_meta_safely(source_img)
            
            # Get video thumbnail URL
            thumbnail_url = None
            if media_type == 'video':
                thumbnail_url = get_video_thumbnail_url(url, width=450)
            
            # Create PreviewImage object
            preview = PreviewImage(
                filename=filename,
                url=url,
                local_path=local_path,
                nsfw=is_nsfw,
                width=source_img.get("width"),
                height=source_img.get("height"),
                media_type=media_type,
                thumbnail_url=thumbnail_url,
                meta=meta,
            )
            
            # === DOWNLOAD ===
            if download:
                # Determine download URL
                download_url = url
                timeout = image_timeout  # Use configured timeout
                
                if media_type == 'video':
                    # Use optimized video URL for quality control
                    download_url = get_optimized_video_url(url, width=video_quality)
                    timeout = video_timeout  # Use configured video timeout
                    logger.info(f"[PackBuilder] Downloading video: {filename} (quality: {video_quality}p)")
                
                dest_path = resources_dir / filename
                
                # Create progress object
                progress = DownloadProgress(
                    index=preview_number - 1,
                    total=total_to_process,
                    filename=filename,
                    url=url,
                    media_type=media_type,
                    status='downloading',
                )
                
                # Report progress start
                if progress_callback:
                    progress_callback(progress)
                
                try:
                    # Stream download for large files
                    response = requests.get(
                        download_url,
                        timeout=timeout,
                        stream=True,
                    )
                    response.raise_for_status()
                    
                    # Get content length if available
                    total_bytes = response.headers.get('content-length')
                    if total_bytes:
                        total_bytes = int(total_bytes)
                        progress.total_bytes = total_bytes
                    
                    # Write with progress tracking
                    bytes_downloaded = 0
                    with open(dest_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                bytes_downloaded += len(chunk)
                                
                                # Update progress periodically (every ~100KB)
                                progress.bytes_downloaded = bytes_downloaded
                                if progress_callback and total_bytes and bytes_downloaded % 102400 < 8192:
                                    progress_callback(progress)
                    
                    # Final progress update
                    progress.bytes_downloaded = bytes_downloaded
                    progress.status = 'completed'
                    if progress_callback:
                        progress_callback(progress)
                    
                    # Log video downloads with size
                    if media_type == 'video':
                        file_size = dest_path.stat().st_size
                        logger.info(
                            f"[PackBuilder] Video downloaded: {filename} "
                            f"({file_size / 1024 / 1024:.1f} MB)"
                        )
                    
                    # Mark URL as downloaded
                    downloaded_urls.add(url)
                    
                except requests.exceptions.Timeout:
                    error_msg = f"Timeout downloading {filename} (>{timeout}s)"
                    logger.warning(f"[PackBuilder] {error_msg}")
                    progress.status = 'failed'
                    progress.error = error_msg
                    if progress_callback:
                        progress_callback(progress)
                    # Don't add to previews list
                    preview_number -= 1
                    continue
                    
                except requests.exceptions.RequestException as e:
                    error_msg = f"Network error downloading {filename}: {str(e)}"
                    logger.warning(f"[PackBuilder] {error_msg}")
                    progress.status = 'failed'
                    progress.error = error_msg
                    if progress_callback:
                        progress_callback(progress)
                    preview_number -= 1
                    continue
                    
                except Exception as e:
                    error_msg = f"Failed to download {filename}: {str(e)}"
                    logger.error(f"[PackBuilder] {error_msg}")
                    progress.status = 'failed'
                    progress.error = error_msg
                    if progress_callback:
                        progress_callback(progress)
                    preview_number -= 1
                    continue
            else:
                # Not downloading, just mark as processed
                downloaded_urls.add(url)
            
            previews.append(preview)
        
        # Summary log
        video_count = sum(1 for p in previews if p.media_type == 'video')
        image_count = sum(1 for p in previews if p.media_type == 'image')
        logger.info(
            f"[PackBuilder] Downloaded {len(previews)} previews "
            f"({video_count} videos, {image_count} images)"
        )
        
        return previews
    
    def build_from_civitai_url(
        self,
        url: str,
        pack_name: Optional[str] = None,
        pack_dir: Optional[Path] = None,
        max_previews: int = 20,
        include_previews: bool = True,
        download_previews: bool = True,
        # === NEW v2.6.0 Parameters ===
        preview_options: Optional[PreviewDownloadOptions] = None,
        progress_callback: Optional[ProgressCallback] = None,
        # === NEW v2.6.0 Multi-version Parameters ===
        version_ids: Optional[List[int]] = None,
        thumbnail_url: Optional[str] = None,
        custom_description: Optional[str] = None,
    ) -> PackBuildResult:
        """
        Build a pack from a Civitai model URL.
        
        This is the main entry point for importing models from Civitai.
        It handles all aspects of pack creation including metadata extraction,
        dependency setup, and preview downloading.
        
        Supports multi-version import for creating comprehensive packs with
        multiple file variants.
        
        Args:
            url: Civitai model URL (can include version ID)
            pack_name: Optional custom pack name (auto-generated if not provided)
            pack_dir: Target directory (uses config default if not provided)
            max_previews: Maximum preview count (overridden by preview_options)
            include_previews: Whether to include preview metadata
            download_previews: Whether to download preview files
            preview_options: Detailed preview download configuration
            progress_callback: Optional callback for download progress
            version_ids: List of version IDs to include (None = URL version or latest)
            thumbnail_url: Custom thumbnail URL for the pack
            custom_description: Custom pack description
            
        Returns:
            PackBuildResult with pack data and status
            
        Example:
            >>> # Single version import
            >>> result = builder.build_from_civitai_url(
            ...     url="https://civitai.com/models/123",
            ... )
            
            >>> # Multi-version import
            >>> result = builder.build_from_civitai_url(
            ...     url="https://civitai.com/models/123",
            ...     version_ids=[456, 789],  # Import specific versions
            ...     preview_options=PreviewDownloadOptions(
            ...         download_videos=True,
            ...         include_nsfw=False,
            ...     ),
            ... )
        """
        errors: List[str] = []
        warnings: List[str] = []
        
        # Use default options if not provided
        if preview_options is None:
            preview_options = PreviewDownloadOptions(max_previews=max_previews)
        
        logger.info(f"[PackBuilder] Building from URL: {url}")
        
        try:
            # Parse URL to get model and version IDs
            model_id, version_id = self.civitai.parse_civitai_url(url)
            logger.info(f"[PackBuilder] Parsed model_id={model_id}, version_id={version_id}")
            
            # Fetch model data
            model_data = self.civitai.get_model(model_id)
            logger.info(f"[PackBuilder] Fetched model: {model_data.get('name', 'unknown')}")
            
            # Convert to model object
            model = self.civitai.create_model_from_response(model_data)
            
            # Determine which versions to import
            versions_to_import: List[Any] = []
            
            if version_ids:
                # Multi-version import: use specified version IDs
                for vid in version_ids:
                    version = next(
                        (v for v in model.model_versions if v.id == vid),
                        None
                    )
                    if version:
                        versions_to_import.append(version)
                    else:
                        warnings.append(f"Version ID {vid} not found in model")
                
                if not versions_to_import:
                    return PackBuildResult(
                        pack=None,
                        success=False,
                        errors=["None of the specified version IDs were found"],
                        warnings=warnings,
                    )
                
                logger.info(f"[PackBuilder] Multi-version import: {len(versions_to_import)} versions")
            
            elif version_id:
                # Single version from URL
                version = next(
                    (v for v in model.model_versions if v.id == version_id),
                    model.model_versions[0] if model.model_versions else None
                )
                if version:
                    versions_to_import = [version]
            
            else:
                # Default: first/latest version
                if model.model_versions:
                    versions_to_import = [model.model_versions[0]]
            
            if not versions_to_import:
                return PackBuildResult(
                    pack=None,
                    success=False,
                    errors=["No model version found"],
                    warnings=[],
                )
            
            # Use first version for primary metadata
            primary_version = versions_to_import[0]
            logger.info(f"[PackBuilder] Primary version: {primary_version.name} (ID: {primary_version.id})")
            if len(versions_to_import) > 1:
                logger.info(f"[PackBuilder] Additional versions: {[v.name for v in versions_to_import[1:]]}")
            
            # Fetch detailed version data for metadata enrichment (all versions)
            all_detailed_images: List[Dict[str, Any]] = []
            for ver in versions_to_import:
                try:
                    ver_detail = self.civitai.get_model_version(ver.id)
                    detailed_images = ver_detail.get("images", [])
                    all_detailed_images.extend(detailed_images)
                    logger.debug(f"[PackBuilder] Got {len(detailed_images)} images from version {ver.id}")
                except Exception as e:
                    logger.warning(f"[PackBuilder] Failed to fetch details for version {ver.id}: {e}")
            
            # Create pack name and directory
            name = pack_name or self._sanitize_name(model.name)
            
            if pack_dir is None and self.config:
                pack_dir = self.config.packs_path / name
            elif pack_dir is None:
                pack_dir = Path.home() / ".synapse" / "packs" / name
            
            pack_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"[PackBuilder] Pack directory: {pack_dir}")
            
            # Create pack metadata (use custom description if provided)
            description = custom_description or model.description
            
            # Build version string from all versions
            version_str = primary_version.name or "1.0.0"
            if len(versions_to_import) > 1:
                version_str = f"{version_str} (+{len(versions_to_import) - 1} more)"
            
            metadata = PackMetadata(
                name=name,
                version=version_str,
                description=description,
                author=model.creator.get("username") if model.creator else None,
                tags=model.tags,
                user_tags=[],
                created_at=datetime.now().isoformat(),
                source_url=url,
            )
            
            # Download previews from ALL versions with deduplication
            previews: List[PreviewImage] = []
            downloaded_urls: set = set()
            
            if include_previews:
                for ver in versions_to_import:
                    # Get detailed images for this version
                    # NOTE: ver.images are DICTS, not objects - use .get() not .url
                    ver_detailed = [
                        img for img in all_detailed_images 
                        if img.get("url") in [
                            i.get("url") if isinstance(i, dict) else getattr(i, 'url', None)
                            for i in getattr(ver, 'images', [])
                        ]
                    ] if all_detailed_images else None
                    
                    ver_previews = self._download_preview_images(
                        version=ver,
                        pack_dir=pack_dir,
                        max_previews=preview_options.max_previews - len(previews),  # Remaining quota
                        download=download_previews,
                        detailed_version_images=ver_detailed or all_detailed_images,
                        # Pass through new options
                        download_images=preview_options.download_images,
                        download_videos=preview_options.download_videos,
                        include_nsfw=preview_options.include_nsfw,
                        video_quality=preview_options.video_quality,
                        image_timeout=preview_options.image_timeout,
                        video_timeout=preview_options.video_timeout,
                        progress_callback=progress_callback,
                    )
                    
                    # Add only non-duplicate previews
                    for p in ver_previews:
                        if p.url not in downloaded_urls:
                            downloaded_urls.add(p.url)
                            previews.append(p)
                    
                    # Check if we've reached max previews
                    if len(previews) >= preview_options.max_previews:
                        break
                
                logger.info(f"[PackBuilder] Total previews: {len(previews)} from {len(versions_to_import)} versions")
            
            # Handle custom thumbnail
            if thumbnail_url:
                # Move custom thumbnail to first position or add it
                existing = next((p for p in previews if p.url == thumbnail_url), None)
                if existing:
                    previews.remove(existing)
                    previews.insert(0, existing)
                else:
                    # Download custom thumbnail
                    logger.info(f"[PackBuilder] Custom thumbnail: {thumbnail_url[:50]}...")
            
            # Build pack object
            pack = Pack(
                metadata=metadata,
                dependencies=[],  # Would be populated by dependency extraction
                custom_nodes=[],
                workflows=[],
                previews=previews,
                docs={},
            )
            
            return PackBuildResult(
                pack=pack,
                success=True,
                errors=errors,
                warnings=warnings,
                pack_dir=pack_dir,
            )
            
        except Exception as e:
            logger.error(f"[PackBuilder] Build failed: {e}")
            return PackBuildResult(
                pack=None,
                success=False,
                errors=[str(e)],
                warnings=warnings,
            )


# =============================================================================
# Factory Function
# =============================================================================

def create_pack_builder(civitai_client, config=None) -> PackBuilder:
    """
    Factory function to create a PackBuilder instance.
    
    Args:
        civitai_client: Configured Civitai API client
        config: Optional application configuration
        
    Returns:
        Configured PackBuilder instance
    """
    return PackBuilder(civitai_client, config)
