"""
Synapse Store v2 - Pack Service

Manages packs: creation, resolution, installation.

Features:
- Import from Civitai URL with video support
- Resolve dependencies (create lock from pack.json)
- Install blobs from lock
- Full video preview support with progress tracking

Enhanced Features (v2.6.0):
- Full video preview support with proper extensions
- Configurable media type filters
- NSFW content filtering
- Progress tracking for large downloads
- Optimized video URLs

Author: Synapse Team
License: MIT
"""

from __future__ import annotations

import json
import logging
import re
import requests
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from pydantic import BaseModel

from .blob_store import BlobStore
from .layout import PackNotFoundError, StoreLayout
from .models import (
    ArtifactDownload,
    ArtifactIntegrity,
    ArtifactProvider,
    AssetKind,
    BlobManifest,
    BlobOrigin,
    CivitaiSelector,
    DependencySelector,
    ExposeConfig,
    Pack,
    PackCategory,
    PackDependency,
    PackLock,
    PackResources,
    PackSource,
    PreviewInfo,
    ProviderName,
    ResolvedArtifact,
    ResolvedDependency,
    SelectorStrategy,
    StoreConfig,
    UnresolvedDependency,
    UpdatePolicy,
    UpdatePolicyMode,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Pydantic Models for Video Support
# =============================================================================

class PreviewDownloadConfig(BaseModel):
    """
    Configuration for preview download operations.

    Provides fine-grained control over what types of preview content
    to download during pack import operations.

    Attributes:
        download_images: Whether to download image previews
        download_videos: Whether to download video previews
        include_nsfw: Whether to include NSFW content
        video_quality: Target video width for optimization
        download_from_all_versions: Whether to download from all versions or just selected
    """
    download_images: bool = True
    download_videos: bool = True
    include_nsfw: bool = True
    video_quality: int = 1080
    download_from_all_versions: bool = True


class DownloadProgressInfo(BaseModel):
    """
    Progress information for download operations.

    Used to track and report download progress through callbacks.

    Attributes:
        index: Current item index (0-based)
        total: Total number of items
        filename: Current filename
        media_type: Type of media being downloaded
        bytes_downloaded: Bytes downloaded so far
        total_bytes: Total bytes (if known)
        status: Current status
        error: Error message if failed
    """
    index: int
    total: int
    filename: str
    media_type: str
    bytes_downloaded: int = 0
    total_bytes: Optional[int] = None
    status: Literal['downloading', 'completed', 'skipped', 'failed'] = 'downloading'
    error: Optional[str] = None


# Type aliases for progress callbacks
ProgressCallback = Callable[[DownloadProgressInfo], None]
ResolveProgressCallback = Callable[[str, str], None]


# =============================================================================
# Pack Service Class
# =============================================================================

class PackService:
    """
    Service for managing packs.

    Provides methods for importing, managing, and resolving packs
    with full support for video previews and configurable options.

    Features:
        - Civitai model import with video support
        - Configurable preview downloads (images/videos/NSFW)
        - Progress tracking for large operations
        - Metadata enrichment and merging
        - Dependency resolution
        - Pack installation
    """

    # Mapping Civitai model types to AssetKind
    CIVITAI_TYPE_MAP = {
        "Checkpoint": AssetKind.CHECKPOINT,
        "LORA": AssetKind.LORA,
        "TextualInversion": AssetKind.EMBEDDING,
        "VAE": AssetKind.VAE,
        "ControlNet": AssetKind.CONTROLNET,
        "Upscaler": AssetKind.UPSCALER,
        "LoCon": AssetKind.LORA,
        "DoRA": AssetKind.LORA,
    }

    def __init__(
        self,
        layout: StoreLayout,
        blob_store: BlobStore,
        civitai_client: Optional[Any] = None,
        huggingface_client: Optional[Any] = None,
        resolvers: Optional[Dict[SelectorStrategy, Any]] = None,
        download_service: Optional[Any] = None,
    ):
        """
        Initialize pack service.

        Args:
            layout: Store layout manager
            blob_store: Blob store
            civitai_client: Optional CivitaiClient instance
            huggingface_client: Optional HuggingFaceClient instance
            resolvers: Optional resolver registry (strategy -> DependencyResolver).
                       If None, default resolvers are created lazily.
            download_service: Optional DownloadService for authenticated downloads
        """
        self.layout = layout
        self.blob_store = blob_store
        self._civitai = civitai_client
        self._huggingface = huggingface_client
        self._download_service = download_service
        self._resolvers: Dict[SelectorStrategy, Any] = resolvers or {}

    @property
    def civitai(self):
        """Lazy-load Civitai client."""
        if self._civitai is None:
            from ..clients.civitai_client import CivitaiClient
            self._civitai = CivitaiClient()
        return self._civitai

    @property
    def huggingface(self):
        """Lazy-load HuggingFace client."""
        if self._huggingface is None:
            from ..clients.huggingface_client import HuggingFaceClient
            self._huggingface = HuggingFaceClient()
        return self._huggingface

    # =========================================================================
    # Pack CRUD
    # =========================================================================

    def list_packs(self) -> List[str]:
        """List all pack names."""
        return self.layout.list_packs()

    def load_pack(self, pack_name: str) -> Pack:
        """Load a pack by name."""
        return self.layout.load_pack(pack_name)

    def save_pack(self, pack: Pack) -> None:
        """Save a pack."""
        self.layout.save_pack(pack)

    def delete_pack(self, pack_name: str) -> bool:
        """Delete a pack."""
        return self.layout.delete_pack(pack_name)

    def pack_exists(self, pack_name: str) -> bool:
        """Check if pack exists."""
        return self.layout.pack_exists(pack_name)

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _determine_nsfw_status(self, img_data: Dict[str, Any]) -> bool:
        """
        Determine NSFW status from Civitai image data.

        Handles multiple field formats used by Civitai API:
        - nsfw: boolean or string
        - nsfwLevel: numeric level (1=Safe, 2=Soft, 3+=Explicit)
        """
        nsfw_val = img_data.get("nsfw")
        if nsfw_val is True:
            return True
        if isinstance(nsfw_val, str) and nsfw_val.lower() not in ["none", "false", "safe"]:
            return True

        nsfw_level = img_data.get("nsfwLevel", 0)
        if isinstance(nsfw_level, (int, float)) and nsfw_level > 1:
            return True

        return False

    def _extract_meta_safely(self, img_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Safely extract generation metadata from image data.

        Handles various API response formats where meta might be:
        - Directly in 'meta' key
        - In 'metadata' key
        - Nested as meta.meta (API quirk)
        """
        meta = img_data.get("meta")

        if not meta:
            meta = img_data.get("metadata")

        if isinstance(meta, dict) and "meta" in meta and isinstance(meta["meta"], dict):
            meta = meta["meta"]

        return meta if isinstance(meta, dict) else None

    def _sanitize_pack_name(self, name: str) -> str:
        """Sanitize a name for use as pack name."""
        sanitized = re.sub(r'[/\\:*?"<>|]', '_', name)
        sanitized = re.sub(r'\s+', '_', sanitized)
        sanitized = re.sub(r'_+', '_', sanitized)
        sanitized = sanitized.strip('_')

        if len(sanitized) > 100:
            sanitized = sanitized[:100]

        return sanitized or "unnamed_pack"

    # =========================================================================
    # Import from Civitai
    # =========================================================================

    def parse_civitai_url(self, url: str) -> Tuple[int, Optional[int]]:
        """
        Parse Civitai URL to extract model ID and optional version ID.

        Supports:
        - https://civitai.com/models/12345
        - https://civitai.com/models/12345/model-name
        - https://civitai.com/models/12345?modelVersionId=67890
        """
        parsed = urlparse(url)

        path_match = re.match(r'/models/(\d+)', parsed.path)
        if not path_match:
            raise ValueError(f"Invalid Civitai URL: {url}")

        model_id = int(path_match.group(1))

        query_params = parse_qs(parsed.query)
        version_id = None
        if "modelVersionId" in query_params:
            version_id = int(query_params["modelVersionId"][0])

        return model_id, version_id

    def import_from_civitai(
        self,
        url: str,
        download_previews: bool = True,
        max_previews: int = 100,
        pack_name: Optional[str] = None,
        download_config: Optional[PreviewDownloadConfig] = None,
        progress_callback: Optional[ProgressCallback] = None,
        cover_url: Optional[str] = None,
        selected_version_ids: Optional[List[int]] = None,
    ) -> Pack:
        """
        Import a pack from Civitai URL.

        Creates pack.json with:
        - One dependency per selected version (multi-version support)
        - Base model as dependency (if detectable)
        - Preview images downloaded with full metadata
        - Model info extracted from Civitai

        Args:
            url: Civitai model URL
            download_previews: If True, download preview images
            max_previews: Max number of previews to download
            pack_name: Optional custom pack name
            download_config: Preview download configuration
            progress_callback: Optional progress callback
            cover_url: User-selected thumbnail URL
            selected_version_ids: List of version IDs to import (creates one dependency per version)

        Returns:
            Created Pack
        """
        from .models import ModelInfo

        if download_config is None:
            download_config = PreviewDownloadConfig()

        logger.info(f"[PackService] Importing from: {url}")

        model_id, version_id = self.parse_civitai_url(url)

        # Fetch model data
        model_data = self.civitai.get_model(model_id)

        # Get specific version or latest
        if version_id:
            version_data = self.civitai.get_model_version(version_id)
        else:
            versions = model_data.get("modelVersions", [])
            if not versions:
                raise ValueError(f"No versions found for model {model_id}")
            version_data = versions[0]
            version_id = version_data["id"]

        # Collect images for preview download
        # If download_from_all_versions is True, collect from ALL versions
        # Otherwise, only use images from the selected version
        detailed_version_images: List[Dict[str, Any]] = []
        all_versions = model_data.get("modelVersions", [])

        if download_config.download_from_all_versions:
            # Use images already present in model_data (no extra API calls needed).
            # get_model() returns modelVersions[].images with full metadata.
            seen_urls: set = set()
            for ver in all_versions:
                for img in ver.get("images", []):
                    img_url = img.get("url")
                    if img_url and img_url not in seen_urls:
                        seen_urls.add(img_url)
                        detailed_version_images.append(img)
            logger.info(f"[PackService] Collected {len(detailed_version_images)} unique previews from {len(all_versions)} versions")
        else:
            # Only use images from selected version (already fetched)
            detailed_version_images = version_data.get("images", [])
            logger.info(f"[PackService] Collected {len(detailed_version_images)} previews from version {version_id}")

        # Determine asset type
        civitai_type = model_data.get("type", "LORA")
        asset_kind = self.CIVITAI_TYPE_MAP.get(civitai_type, AssetKind.LORA)

        # Create pack name (sanitized)
        model_name = model_data.get("name", f"model_{model_id}")
        name = pack_name or self._sanitize_pack_name(model_name)

        # Determine which versions to import
        # If selected_version_ids provided, use those; otherwise use single version from URL
        versions_to_import: List[int] = []
        if selected_version_ids and len(selected_version_ids) > 0:
            versions_to_import = selected_version_ids
            logger.info(f"[PackService] Multi-version import: {len(versions_to_import)} versions selected")
        else:
            versions_to_import = [version_id]
            logger.info(f"[PackService] Single version import: {version_id}")

        dependencies: List[PackDependency] = []
        base_model = None
        autov2 = None
        sha256 = None
        first_version_data = None

        # Create one dependency for each selected version
        for idx, ver_id in enumerate(versions_to_import):
            try:
                # Fetch version data
                ver_data = self.civitai.get_model_version(ver_id)
                if first_version_data is None:
                    first_version_data = ver_data

                # Get files for this version
                files = ver_data.get("files", [])
                if not files:
                    logger.warning(f"[PackService] No files found for version {ver_id}, skipping")
                    continue

                # Find primary file (prefer safetensors)
                primary_file = None
                for f in files:
                    if f.get("primary"):
                        primary_file = f
                        break
                if primary_file is None:
                    for f in files:
                        if f.get("name", "").endswith(".safetensors"):
                            primary_file = f
                            break
                if primary_file is None:
                    primary_file = files[0]

                # Get hash info for first version (for model_info)
                if idx == 0:
                    hashes = primary_file.get("hashes", {})
                    sha256 = hashes.get("SHA256", "").lower() if hashes else None
                    autov2 = hashes.get("AutoV2") if hashes else None
                    base_model = ver_data.get("baseModel")

                # Create unique dependency ID
                # For single version: main_lora
                # For multi-version: version_{version_id}_lora (with version name if available)
                version_name = ver_data.get("name", str(ver_id))
                if len(versions_to_import) == 1:
                    dep_id = f"main_{asset_kind.value}"
                else:
                    # Sanitize version name for ID
                    safe_name = re.sub(r'[^a-zA-Z0-9]', '_', version_name)[:30]
                    dep_id = f"v{ver_id}_{safe_name}_{asset_kind.value}"

                dep = PackDependency(
                    id=dep_id,
                    kind=asset_kind,
                    required=True,
                    selector=DependencySelector(
                        strategy=SelectorStrategy.CIVITAI_MODEL_LATEST,
                        civitai=CivitaiSelector(
                            model_id=model_id,
                            version_id=ver_id,
                            file_id=primary_file.get("id"),
                        ),
                    ),
                    update_policy=UpdatePolicy(mode=UpdatePolicyMode.FOLLOW_LATEST),
                    expose=ExposeConfig(
                        filename=primary_file.get("name", f"{name}.safetensors"),
                        trigger_words=ver_data.get("trainedWords", []),
                    ),
                )
                dependencies.append(dep)
                logger.info(f"[PackService] Created dependency '{dep_id}' for version {ver_id} ({version_name})")

            except Exception as e:
                logger.error(f"[PackService] Failed to process version {ver_id}: {e}")
                continue

        if not dependencies:
            raise ValueError(f"No valid versions could be processed for model {model_id}")

        # Use first version data for pack metadata if we don't have version_data
        if first_version_data:
            version_data = first_version_data

        # Add base model dependency if detected
        if base_model:
            base_dep = self._create_base_model_dependency(base_model)
            if base_dep:
                dependencies.insert(0, base_dep)

        # Extract model info
        stats = model_data.get("stats", {})
        model_info = ModelInfo(
            model_type=civitai_type,
            base_model=base_model,
            trigger_words=version_data.get("trainedWords", []),
            trained_words=version_data.get("trainedWords", []),
            hash_autov2=autov2,
            hash_sha256=sha256,
            civitai_air=f"civitai: {model_id} @ {version_id}",
            download_count=stats.get("downloadCount"),
            rating=stats.get("rating"),
            published_at=version_data.get("publishedAt"),
        )

        # Create pack with all metadata
        pack = Pack(
            name=name,
            pack_type=asset_kind,
            pack_category=PackCategory.EXTERNAL,  # Imported from Civitai
            source=PackSource(
                provider=ProviderName.CIVITAI,
                model_id=model_id,
                version_id=version_id,
                url=url,
            ),
            dependencies=dependencies,
            pack_dependencies=[],  # No pack dependencies by default
            resources=PackResources(
                previews_keep_in_git=True,
                workflows_keep_in_git=True,
            ),
            cover_url=cover_url,  # User-selected thumbnail
            version=version_data.get("name"),
            description=model_data.get("description"),
            base_model=base_model,
            author=model_data.get("creator", {}).get("username"),
            tags=model_data.get("tags", []),
            trigger_words=version_data.get("trainedWords", []),
            model_info=model_info,
        )

        # Extract parameters from description using AI (with rule-based fallback)
        if pack.description:
            from src.ai import get_ai_service
            from .models import GenerationParameters

            logger.info(f"[parameter-extraction] Extracting from description (length: {len(pack.description)})")

            try:
                ai_service = get_ai_service()
                result = ai_service.extract_parameters(pack.description)

                if result.success and result.output:
                    param_keys = list(result.output.keys())
                    logger.info(
                        f"[parameter-extraction] Found {len(param_keys)} params via {result.provider_id}: {param_keys}"
                    )

                    # Convert to GenerationParameters model
                    pack.parameters = GenerationParameters(**result.output)
                    pack.parameters_source = result.provider_id  # Track extraction source
                    logger.info(f"[parameter-extraction] Parameters saved to pack (source: {result.provider_id})")
                else:
                    logger.info(f"[parameter-extraction] No parameters found in description")

            except Exception as e:
                logger.warning(f"[parameter-extraction] AI extraction failed, skipping: {e}")

        # Save pack
        self.layout.save_pack(pack)

        # Create initial lock for all dependencies
        lock = self._create_initial_lock_multi(pack)
        self.layout.save_pack_lock(lock)

        # Download previews and get metadata
        if download_previews:
            previews = self._download_previews(
                pack_name=name,
                version_data=version_data,
                max_count=max_previews,
                detailed_version_images=detailed_version_images,
                download_images=download_config.download_images,
                download_videos=download_config.download_videos,
                include_nsfw=download_config.include_nsfw,
                video_quality=download_config.video_quality,
                progress_callback=progress_callback,
            )
            if previews:
                pack.previews = previews
                self.layout.save_pack(pack)

        logger.info(f"[PackService] Import complete: {name}")
        return pack

    def _create_base_model_dependency(self, base_model: str) -> Optional[PackDependency]:
        """Create a base model dependency from Civitai baseModel string."""
        try:
            config = self.layout.load_config()
            alias = config.base_model_aliases.get(base_model)
            if alias:
                return PackDependency(
                    id="base_checkpoint",
                    kind=alias.kind,
                    required=False,
                    selector=DependencySelector(
                        strategy=SelectorStrategy.BASE_MODEL_HINT,
                        base_model=base_model,
                    ),
                    update_policy=UpdatePolicy(mode=UpdatePolicyMode.PINNED),
                    expose=ExposeConfig(filename=alias.default_expose_filename),
                )
        except Exception:
            pass

        return PackDependency(
            id="base_checkpoint",
            kind=AssetKind.CHECKPOINT,
            required=False,
            selector=DependencySelector(
                strategy=SelectorStrategy.BASE_MODEL_HINT,
                base_model=base_model,
            ),
            update_policy=UpdatePolicy(mode=UpdatePolicyMode.PINNED),
            expose=ExposeConfig(filename=f"{base_model}.safetensors"),
        )

    def _create_initial_lock_multi(self, pack: Pack) -> PackLock:
        """
        Create initial lock file from pack with multi-version support.

        Fetches version data for each Civitai dependency to get correct
        sha256, size, and download URL for each version.
        """
        resolved = []
        unresolved = []

        for dep in pack.dependencies:
            if dep.selector.strategy == SelectorStrategy.CIVITAI_MODEL_LATEST:
                try:
                    # Fetch version data for this specific dependency
                    civ = dep.selector.civitai
                    if not civ or not civ.version_id:
                        continue

                    version_data = self.civitai.get_model_version(civ.version_id)
                    files = version_data.get("files", [])

                    # Find the specific file or primary file
                    target_file = None
                    if civ.file_id:
                        for f in files:
                            if f.get("id") == civ.file_id:
                                target_file = f
                                break
                    if not target_file and files:
                        # Find primary or first safetensors
                        for f in files:
                            if f.get("primary"):
                                target_file = f
                                break
                        if not target_file:
                            for f in files:
                                if f.get("name", "").endswith(".safetensors"):
                                    target_file = f
                                    break
                        if not target_file:
                            target_file = files[0]

                    if not target_file:
                        unresolved.append(UnresolvedDependency(
                            dependency_id=dep.id,
                            reason="no_file_found",
                            details={"version_id": civ.version_id},
                        ))
                        continue

                    # Extract file info
                    hashes = target_file.get("hashes", {})
                    sha256 = hashes.get("SHA256", "").lower() if hashes else None
                    file_size = target_file.get("sizeKB", 0) * 1024 if target_file.get("sizeKB") else None

                    download_url = target_file.get("downloadUrl", "")
                    if not download_url:
                        download_url = f"https://civitai.com/api/download/models/{civ.version_id}"

                    resolved.append(ResolvedDependency(
                        dependency_id=dep.id,
                        artifact=ResolvedArtifact(
                            kind=dep.kind,
                            sha256=sha256,
                            size_bytes=file_size,
                            provider=ArtifactProvider(
                                name=ProviderName.CIVITAI,
                                model_id=civ.model_id,
                                version_id=civ.version_id,
                                file_id=target_file.get("id"),
                                filename=target_file.get("name"),
                            ),
                            download=ArtifactDownload(urls=[download_url]),
                            integrity=ArtifactIntegrity(sha256_verified=sha256 is not None),
                        ),
                    ))
                    logger.debug(f"[PackService] Resolved dependency '{dep.id}' for version {civ.version_id}")

                except Exception as e:
                    logger.error(f"[PackService] Failed to resolve {dep.id}: {e}")
                    unresolved.append(UnresolvedDependency(
                        dependency_id=dep.id,
                        reason="resolution_error",
                        details={"error": str(e)},
                    ))

            elif dep.selector.strategy == SelectorStrategy.BASE_MODEL_HINT:
                try:
                    config = self.layout.load_config()
                    alias = config.base_model_aliases.get(dep.selector.base_model)
                    if alias and alias.selector.civitai:
                        resolved.append(ResolvedDependency(
                            dependency_id=dep.id,
                            artifact=ResolvedArtifact(
                                kind=dep.kind,
                                sha256=None,
                                size_bytes=None,
                                provider=ArtifactProvider(
                                    name=ProviderName.CIVITAI,
                                    model_id=alias.selector.civitai.model_id,
                                    version_id=alias.selector.civitai.version_id,
                                    file_id=alias.selector.civitai.file_id,
                                ),
                                download=ArtifactDownload(urls=[]),
                                integrity=ArtifactIntegrity(sha256_verified=False),
                            ),
                        ))
                    else:
                        unresolved.append(UnresolvedDependency(
                            dependency_id=dep.id,
                            reason="unknown_base_model_alias",
                            details={"base_model": dep.selector.base_model},
                        ))
                except Exception:
                    unresolved.append(UnresolvedDependency(
                        dependency_id=dep.id,
                        reason="base_model_resolution_failed",
                        details={"base_model": dep.selector.base_model},
                    ))

        logger.info(f"[PackService] Lock created: {len(resolved)} resolved, {len(unresolved)} unresolved")

        return PackLock(
            pack=pack.name,
            resolved_at=datetime.now().isoformat(),
            resolved=resolved,
            unresolved=unresolved,
        )

    # =========================================================================
    # Preview Download with Video Support
    # =========================================================================

    def _download_previews(
        self,
        pack_name: str,
        version_data: Dict[str, Any],
        max_count: int = 100,
        detailed_version_images: Optional[List[Dict[str, Any]]] = None,
        download_images: bool = True,
        download_videos: bool = True,
        include_nsfw: bool = True,
        video_quality: int = 1080,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> List[PreviewInfo]:
        """
        Download preview media for a pack with full video support.

        Downloads are parallelized with ThreadPoolExecutor(max_workers=4) for
        significantly faster import of packs with many previews.

        This method handles downloading preview content from Civitai with
        support for both images and videos. It includes configurable filtering
        by media type and NSFW status, optimized video URLs, and progress
        tracking for large downloads.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from ..utils.media_detection import (
            detect_media_type,
            get_video_thumbnail_url,
            get_optimized_video_url,
        )

        # Use detailed_version_images if available (contains all versions),
        # otherwise fall back to version_data.images (single version)
        if detailed_version_images:
            images = detailed_version_images[:max_count]
        else:
            images = version_data.get("images", [])[:max_count]

        previews_dir = self.layout.pack_previews_path(pack_name)
        previews_dir.mkdir(parents=True, exist_ok=True)

        # Create lookup map for detailed images by URL (metadata merge)
        detailed_map: Dict[str, Dict[str, Any]] = {}
        if detailed_version_images:
            for img in detailed_version_images:
                url = img.get("url")
                if url:
                    detailed_map[url] = img

        # =====================================================================
        # Phase 1: Collect download tasks (serial, fast — no I/O)
        # =====================================================================
        download_tasks: List[Dict[str, Any]] = []
        downloaded_urls: set = set()
        preview_number = 0
        total_count = len(images)

        for i, img_data in enumerate(images):
            url = img_data.get("url")
            if not url:
                continue

            if url in downloaded_urls:
                logger.debug(f"[PackService] Skipping duplicate URL: {url[:60]}...")
                continue

            # MERGE: Get richer data if available
            detailed_img = detailed_map.get(url)
            source_img = detailed_img if detailed_img else img_data

            is_nsfw = self._determine_nsfw_status(source_img)

            if is_nsfw and not include_nsfw:
                logger.debug(f"[PackService] Skipping NSFW preview: {url[:60]}...")
                continue

            # Detect media type from URL
            media_info = detect_media_type(url, use_head_request=False)
            media_type = media_info.type.value

            if media_type == 'video' and not download_videos:
                logger.debug(f"[PackService] Skipping video (disabled): {url[:60]}...")
                continue

            if media_type == 'image' and not download_images:
                logger.debug(f"[PackService] Skipping image (disabled): {url[:60]}...")
                continue

            preview_number += 1

            # Generate filename with appropriate extension
            url_path = url.split("/")[-1].split("?")[0]
            original_filename = url_path if url_path else f"preview_{preview_number}.jpg"

            if media_type == 'video':
                base_name = Path(original_filename).stem
                filename = f"{base_name}.mp4"
            else:
                filename = original_filename

            dest = previews_dir / filename

            meta = self._extract_meta_safely(source_img)

            # Get video thumbnail URL
            thumbnail_url = None
            if media_type == 'video':
                thumbnail_url = get_video_thumbnail_url(url, width=450)

            # Save metadata to sidecar JSON
            try:
                if meta:
                    meta_file = dest.with_suffix(dest.suffix + '.json')
                    meta_file.write_text(json.dumps(meta, indent=2))
            except Exception as e:
                logger.debug(f"[PackService] Failed to write meta sidecar: {e}")

            # Compute download URL and timeout
            download_url = url
            timeout = 60
            if media_type == 'video':
                download_url = get_optimized_video_url(url, width=video_quality)
                timeout = 120

            download_tasks.append({
                "url": url,
                "download_url": download_url,
                "dest": dest,
                "filename": filename,
                "timeout": timeout,
                "media_type": media_type,
                "is_nsfw": is_nsfw,
                "source_img": source_img,
                "meta": meta,
                "thumbnail_url": thumbnail_url,
                "preview_number": preview_number,
            })

            downloaded_urls.add(url)

        # =====================================================================
        # Phase 2: Download in parallel (ThreadPoolExecutor)
        # =====================================================================
        preview_infos: List[PreviewInfo] = []
        # Map to preserve order: task index → PreviewInfo (or None on failure)
        results_map: Dict[int, Optional[PreviewInfo]] = {}

        def _download_single(task_idx: int, task: Dict[str, Any]) -> Optional[PreviewInfo]:
            """Download a single preview file. Thread-safe."""
            dest = task["dest"]
            filename = task["filename"]
            download_url = task["download_url"]
            timeout = task["timeout"]
            media_type = task["media_type"]

            if dest.exists():
                return PreviewInfo(
                    filename=filename,
                    url=task["url"],
                    nsfw=task["is_nsfw"],
                    width=task["source_img"].get("width"),
                    height=task["source_img"].get("height"),
                    meta=task["meta"],
                    media_type=media_type,
                    thumbnail_url=task["thumbnail_url"],
                )

            if media_type == 'video':
                logger.info(f"[PackService] Downloading video: {filename}")

            try:
                if self._download_service:
                    self._download_service.download_to_file(
                        download_url,
                        dest,
                        timeout=(15, timeout),
                        progress_callback=None,
                        resume=False,
                    )
                else:
                    # Fallback: direct download (no auth)
                    response = requests.get(
                        download_url,
                        timeout=timeout,
                        stream=True,
                    )
                    response.raise_for_status()

                    with open(dest, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)

                if media_type == 'video' and dest.exists():
                    file_size = dest.stat().st_size
                    logger.info(
                        f"[PackService] Video downloaded: {filename} "
                        f"({file_size / 1024 / 1024:.1f} MB)"
                    )

                return PreviewInfo(
                    filename=filename,
                    url=task["url"],
                    nsfw=task["is_nsfw"],
                    width=task["source_img"].get("width"),
                    height=task["source_img"].get("height"),
                    meta=task["meta"],
                    media_type=media_type,
                    thumbnail_url=task["thumbnail_url"],
                )

            except Exception as e:
                dest.unlink(missing_ok=True)
                logger.warning(f"[PackService] Download error for {filename}: {e}")
                return None

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {}
            for idx, task in enumerate(download_tasks):
                future = executor.submit(_download_single, idx, task)
                futures[future] = idx

            for future in as_completed(futures):
                idx = futures[future]
                try:
                    result = future.result()
                    results_map[idx] = result
                except Exception as e:
                    logger.warning(f"[PackService] Preview download future failed: {e}")
                    results_map[idx] = None

        # Collect results in original order
        for idx in range(len(download_tasks)):
            info = results_map.get(idx)
            if info is not None:
                preview_infos.append(info)
                task = download_tasks[idx]
                if progress_callback:
                    progress = DownloadProgressInfo(
                        index=idx,
                        total=total_count,
                        filename=task["filename"],
                        media_type=task["media_type"],
                        status='completed',
                    )
                    progress_callback(progress)

        video_count = sum(1 for p in preview_infos if p.media_type == 'video')
        image_count = sum(1 for p in preview_infos if p.media_type == 'image')
        logger.info(
            f"[PackService] Downloaded {len(preview_infos)} previews "
            f"({video_count} videos, {image_count} images)"
        )

        return preview_infos

    # =========================================================================
    # Resolution
    # =========================================================================

    def resolve_pack(
        self,
        pack_name: str,
        progress_callback: Optional[ResolveProgressCallback] = None,
    ) -> PackLock:
        """
        Resolve all dependencies in a pack, creating/updating lock file.

        Args:
            pack_name: Pack to resolve
            progress_callback: Optional callback for progress updates

        Returns:
            Updated PackLock
        """
        pack = self.layout.load_pack(pack_name)
        existing_lock = self.layout.load_pack_lock(pack_name)

        resolved = []
        unresolved = []

        for dep in pack.dependencies:
            if progress_callback:
                progress_callback(dep.id, "resolving")

            try:
                artifact = self._resolve_dependency(pack, dep, existing_lock)
                if artifact:
                    resolved.append(ResolvedDependency(
                        dependency_id=dep.id,
                        artifact=artifact,
                    ))
                    if progress_callback:
                        progress_callback(dep.id, "resolved")
                else:
                    unresolved.append(UnresolvedDependency(
                        dependency_id=dep.id,
                        reason="no_artifact_found",
                        details={},
                    ))
                    if progress_callback:
                        progress_callback(dep.id, "unresolved")
            except Exception as e:
                unresolved.append(UnresolvedDependency(
                    dependency_id=dep.id,
                    reason="resolution_error",
                    details={"error": str(e)},
                ))
                if progress_callback:
                    progress_callback(dep.id, f"error: {e}")

        lock = PackLock(
            pack=pack_name,
            resolved_at=datetime.now().isoformat(),
            resolved=resolved,
            unresolved=unresolved,
        )

        self.layout.save_pack_lock(lock)
        return lock

    def _ensure_resolvers(self) -> None:
        """Lazily initialize default resolvers if none were provided."""
        if self._resolvers:
            return

        from .dependency_resolver import (
            BaseModelHintResolver,
            CivitaiFileResolver,
            CivitaiLatestResolver,
            HuggingFaceResolver,
            LocalFileResolver,
            UrlResolver,
        )

        self._resolvers = {
            SelectorStrategy.CIVITAI_FILE: CivitaiFileResolver(self.civitai),
            SelectorStrategy.CIVITAI_MODEL_LATEST: CivitaiLatestResolver(self.civitai),
            SelectorStrategy.BASE_MODEL_HINT: BaseModelHintResolver(self.civitai, self.layout),
            SelectorStrategy.HUGGINGFACE_FILE: HuggingFaceResolver(),
            SelectorStrategy.URL_DOWNLOAD: UrlResolver(),
            SelectorStrategy.LOCAL_FILE: LocalFileResolver(),
        }

    def _resolve_dependency(
        self,
        pack: Pack,
        dep: PackDependency,
        existing_lock: Optional[PackLock],
    ) -> Optional[ResolvedArtifact]:
        """Resolve a single dependency via the resolver registry."""
        self._ensure_resolvers()

        resolver = self._resolvers.get(dep.selector.strategy)
        if resolver is None:
            logger.warning("No resolver for strategy %s", dep.selector.strategy)
            return None

        return resolver.resolve(dep)

    # =========================================================================
    # Installation
    # =========================================================================

    def install_pack(
        self,
        pack_name: str,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> List[str]:
        """
        Install all blobs for a pack from its lock file.

        Args:
            pack_name: Pack to install
            progress_callback: Optional callback (dep_id, downloaded, total)

        Returns:
            List of installed SHA256 hashes
        """
        lock = self.layout.load_pack_lock(pack_name)
        if not lock:
            raise PackNotFoundError(f"No lock file for pack: {pack_name}")

        # Load pack for expose filename lookup
        pack = self.layout.load_pack(pack_name)

        installed = []

        for resolved in lock.resolved:
            sha256 = resolved.artifact.sha256
            urls = resolved.artifact.download.urls

            if not urls:
                continue

            blob_already_existed = sha256 and self.blob_store.blob_exists(sha256)

            if blob_already_existed:
                installed.append(sha256)
                # Ensure manifest exists even for pre-existing blobs
                self._ensure_blob_manifest(sha256, resolved, pack)
                continue

            try:
                def make_callback(dep_id: str):
                    if progress_callback:
                        return lambda d, t: progress_callback(dep_id, d, t)
                    return None

                actual_sha = self.blob_store.download(
                    urls[0],
                    sha256,
                    progress_callback=make_callback(resolved.dependency_id),
                )
                installed.append(actual_sha)

                if not sha256:
                    resolved.artifact.sha256 = actual_sha
                    resolved.artifact.integrity.sha256_verified = True
                    self.layout.save_pack_lock(lock)

                # Create manifest for newly downloaded blob
                self._ensure_blob_manifest(actual_sha, resolved, pack)

            except Exception as e:
                logger.error(f"[PackService] Failed to install {resolved.dependency_id}: {e}")

        return installed

    def _ensure_blob_manifest(
        self,
        sha256: str,
        resolved: ResolvedDependency,
        pack: Optional[Pack],
    ) -> None:
        """
        Ensure a manifest exists for a blob (write-once, never overwrites).

        Called during blob installation to persist metadata for orphan recovery.
        """
        # Skip if manifest already exists
        if self.blob_store.manifest_exists(sha256):
            return

        # Get expose filename from pack dependency, fall back to provider filename
        expose_filename: Optional[str] = None
        if pack:
            dep = pack.get_dependency(resolved.dependency_id)
            if dep:
                expose_filename = dep.expose.filename

        # Fall back to provider filename or SHA256 prefix
        original_filename = (
            expose_filename
            or resolved.artifact.provider.filename
            or f"{sha256[:12]}.bin"
        )

        # Build origin from provider
        provider = resolved.artifact.provider
        origin = BlobOrigin(
            provider=provider.name,
            model_id=provider.model_id,
            version_id=provider.version_id,
            file_id=provider.file_id,
            filename=provider.filename,
            repo_id=provider.repo_id,
        )

        # Create manifest
        manifest = BlobManifest(
            original_filename=original_filename,
            kind=resolved.artifact.kind,
            origin=origin,
        )

        # Write manifest (write-once)
        self.blob_store.write_manifest(sha256, manifest)
