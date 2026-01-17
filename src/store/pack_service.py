"""
Synapse Store v2 - Pack Service

Manages packs: creation, resolution, installation.

Features:
- Import from Civitai URL
- Resolve dependencies (create lock from pack.json)
- Install blobs from lock
"""

from __future__ import annotations

import re
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from .blob_store import BlobStore
from .layout import PackNotFoundError, StoreLayout
from .models import (
    ArtifactDownload,
    ArtifactIntegrity,
    ArtifactProvider,
    AssetKind,
    CivitaiSelector,
    DependencySelector,
    ExposeConfig,
    Pack,
    PackDependency,
    PackLock,
    PackResources,
    PackSource,
    ProviderName,
    ResolvedArtifact,
    ResolvedDependency,
    SelectorStrategy,
    StoreConfig,
    UnresolvedDependency,
    UpdatePolicy,
    UpdatePolicyMode,
)


# Progress callback type: (dependency_id, status_message)
ResolveProgressCallback = Callable[[str, str], None]


class PackService:
    """
    Service for managing packs.
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
    ):
        """
        Initialize pack service.
        
        Args:
            layout: Store layout manager
            blob_store: Blob store
            civitai_client: Optional CivitaiClient instance
            huggingface_client: Optional HuggingFaceClient instance
        """
        self.layout = layout
        self.blob_store = blob_store
        self._civitai = civitai_client
        self._huggingface = huggingface_client
    
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
        
        # Extract model ID from path
        path_match = re.match(r'/models/(\d+)', parsed.path)
        if not path_match:
            raise ValueError(f"Invalid Civitai URL: {url}")
        
        model_id = int(path_match.group(1))
        
        # Check for version ID in query params
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
    ) -> Pack:
        """
        Import a pack from Civitai URL.
        
        Creates pack.json with:
        - Main asset as primary dependency
        - Base model as dependency (if detectable)
        - Preview images downloaded with full metadata
        - Model info extracted from Civitai
        
        Args:
            url: Civitai model URL
            download_previews: If True, download preview images
            max_previews: Max number of previews to download
        
        Returns:
            Created Pack
        """
        from .models import ModelInfo
        
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
        
        # CRITICAL: Always fetch detailed version data for images with meta
        # The summary version_data may have limited image info
        detailed_version_images = []
        try:
            detailed_version = self.civitai.get_model_version(version_id)
            detailed_version_images = detailed_version.get("images", [])
        except Exception:
            # Non-fatal, continue with basic info
            pass
        
        # Determine asset type
        civitai_type = model_data.get("type", "LORA")
        asset_kind = self.CIVITAI_TYPE_MAP.get(civitai_type, AssetKind.LORA)
        
        # Get files
        files = version_data.get("files", [])
        if not files:
            raise ValueError(f"No files found for version {version_id}")
        
        # Find primary file (prefer safetensors)
        primary_file = None
        for f in files:
            if f.get("primary"):
                primary_file = f
                break
        if primary_file is None:
            # Try to find safetensors
            for f in files:
                if f.get("name", "").endswith(".safetensors"):
                    primary_file = f
                    break
        if primary_file is None:
            primary_file = files[0]
        
        # Create pack name (sanitized)
        model_name = model_data.get("name", f"model_{model_id}")
        pack_name = self._sanitize_pack_name(model_name)
        
        # Get hash and size
        hashes = primary_file.get("hashes", {})
        sha256 = hashes.get("SHA256", "").lower() if hashes else None
        autov2 = hashes.get("AutoV2") if hashes else None
        file_size = primary_file.get("sizeKB", 0) * 1024 if primary_file.get("sizeKB") else None
        
        # Get download URL
        download_url = primary_file.get("downloadUrl", "")
        if not download_url:
            download_url = f"https://civitai.com/api/download/models/{version_id}"
        
        # Get base model
        base_model = version_data.get("baseModel")
        
        # Create main dependency
        main_dep = PackDependency(
            id=f"main_{asset_kind.value}",
            kind=asset_kind,
            required=True,
            selector=DependencySelector(
                strategy=SelectorStrategy.CIVITAI_MODEL_LATEST,
                civitai=CivitaiSelector(
                    model_id=model_id,
                    version_id=version_id,
                    file_id=primary_file.get("id"),
                ),
            ),
            update_policy=UpdatePolicy(mode=UpdatePolicyMode.FOLLOW_LATEST),
            expose=ExposeConfig(
                filename=primary_file.get("name", f"{pack_name}.safetensors"),
                trigger_words=version_data.get("trainedWords", []),
            ),
        )
        
        dependencies = [main_dep]
        
        # Add base model dependency if detected
        if base_model:
            base_dep = self._create_base_model_dependency(base_model)
            if base_dep:
                dependencies.insert(0, base_dep)
        
        # Extract model info (v1 feature)
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
            name=pack_name,
            pack_type=asset_kind,
            source=PackSource(
                provider=ProviderName.CIVITAI,
                model_id=model_id,
                version_id=version_id,
                url=url,
            ),
            dependencies=dependencies,
            resources=PackResources(
                previews_keep_in_git=True,
                workflows_keep_in_git=True,
            ),
            # Metadata fields
            version=version_data.get("name"),
            description=model_data.get("description"),
            base_model=base_model,
            author=model_data.get("creator", {}).get("username"),
            tags=model_data.get("tags", []),
            trigger_words=version_data.get("trainedWords", []),
            model_info=model_info,
        )
        
        # Save pack
        self.layout.save_pack(pack)
        
        # Create initial lock
        lock = self._create_initial_lock(pack, version_data, primary_file, download_url, sha256, file_size)
        self.layout.save_pack_lock(lock)
        
        # Download previews and get metadata (pass detailed images for merge)
        if download_previews:
            previews = self._download_previews(
                pack_name, 
                version_data, 
                max_previews,
                detailed_version_images=detailed_version_images
            )
            if previews:
                pack.previews = previews
                # Save pack again with previews
                self.layout.save_pack(pack)
        
        return pack
    
    def _sanitize_pack_name(self, name: str) -> str:
        """Sanitize a name for use as pack name."""
        # Replace problematic characters
        sanitized = re.sub(r'[/\\:*?"<>|]', '_', name)
        sanitized = re.sub(r'\s+', '_', sanitized)
        sanitized = re.sub(r'_+', '_', sanitized)
        sanitized = sanitized.strip('_')
        
        # Limit length
        if len(sanitized) > 100:
            sanitized = sanitized[:100]
        
        return sanitized or "unnamed_pack"
    
    def _create_base_model_dependency(self, base_model: str) -> Optional[PackDependency]:
        """Create a base model dependency from Civitai baseModel string."""
        # Try to load config for base model aliases
        try:
            config = self.layout.load_config()
            alias = config.base_model_aliases.get(base_model)
            if alias:
                return PackDependency(
                    id="base_checkpoint",
                    kind=alias.kind,
                    required=True,
                    selector=DependencySelector(
                        strategy=SelectorStrategy.BASE_MODEL_HINT,
                        base_model=base_model,
                    ),
                    update_policy=UpdatePolicy(mode=UpdatePolicyMode.PINNED),
                    expose=ExposeConfig(filename=alias.default_expose_filename),
                )
        except Exception:
            pass
        
        # Create unresolved base model hint
        return PackDependency(
            id="base_checkpoint",
            kind=AssetKind.CHECKPOINT,
            required=False,  # Not required since we can't resolve it
            selector=DependencySelector(
                strategy=SelectorStrategy.BASE_MODEL_HINT,
                base_model=base_model,
            ),
            update_policy=UpdatePolicy(mode=UpdatePolicyMode.PINNED),
            expose=ExposeConfig(filename=f"{base_model}.safetensors"),
        )
    
    def _create_initial_lock(
        self,
        pack: Pack,
        version_data: Dict[str, Any],
        primary_file: Dict[str, Any],
        download_url: str,
        sha256: Optional[str],
        file_size: Optional[int],
    ) -> PackLock:
        """Create initial lock file from import data."""
        resolved = []
        unresolved = []
        
        for dep in pack.dependencies:
            if dep.selector.strategy == SelectorStrategy.CIVITAI_MODEL_LATEST:
                # Main dependency - resolved from import
                resolved.append(ResolvedDependency(
                    dependency_id=dep.id,
                    artifact=ResolvedArtifact(
                        kind=dep.kind,
                        sha256=sha256,
                        size_bytes=file_size,
                        provider=ArtifactProvider(
                            name=ProviderName.CIVITAI,
                            model_id=dep.selector.civitai.model_id if dep.selector.civitai else None,
                            version_id=dep.selector.civitai.version_id if dep.selector.civitai else None,
                            file_id=dep.selector.civitai.file_id if dep.selector.civitai else None,
                        ),
                        download=ArtifactDownload(urls=[download_url]),
                        integrity=ArtifactIntegrity(sha256_verified=sha256 is not None),
                    ),
                ))
            elif dep.selector.strategy == SelectorStrategy.BASE_MODEL_HINT:
                # Base model - may be unresolved
                try:
                    config = self.layout.load_config()
                    alias = config.base_model_aliases.get(dep.selector.base_model)
                    if alias and alias.selector.civitai:
                        resolved.append(ResolvedDependency(
                            dependency_id=dep.id,
                            artifact=ResolvedArtifact(
                                kind=dep.kind,
                                sha256=None,  # Unknown until downloaded
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
        
        return PackLock(
            pack=pack.name,
            resolved_at=datetime.now().isoformat(),
            resolved=resolved,
            unresolved=unresolved,
        )
    
    def _download_previews(
        self,
        pack_name: str,
        version_data: Dict[str, Any],
        max_count: int = 100,
        detailed_version_images: List[Dict[str, Any]] = None,
    ) -> List[Any]: # Returns List[PreviewInfo] but Any to avoid circular import issues if type not available at runtime
        """
        Download preview images for a pack and return metadata.
        
        Uses a merge algorithm to combine basic image data with detailed metadata:
        1. Creates a lookup map from detailed_version_images by URL
        2. For each basic image, tries to find richer data in the lookup map
        3. Extracts meta from the richer source when available
        
        Returns:
            List of PreviewInfo objects with full metadata
        """
        from .models import PreviewInfo
        
        images = version_data.get("images", [])[:max_count]
        previews_dir = self.layout.pack_previews_path(pack_name)
        previews_dir.mkdir(parents=True, exist_ok=True)
        
        preview_infos = []
        
        # Create lookup map for detailed images by URL (v1 merge algorithm)
        detailed_map = {}
        if detailed_version_images:
            for img in detailed_version_images:
                url = img.get("url")
                if url:
                    detailed_map[url] = img
        
        for i, img_data in enumerate(images):
            url = img_data.get("url")
            if not url:
                continue
            
            # MERGE: Check if we have richer data for this image
            # The summary 'img_data' has limited info. 'detailed_img' has full meta if available.
            detailed_img = detailed_map.get(url)
            source_img = detailed_img if detailed_img else img_data
            
            # Extract filename from URL
            filename = url.split("/")[-1].split("?")[0]
            if not filename:
                filename = f"preview_{i}.jpg"
            
            dest = previews_dir / filename
            
            # Extract metadata safely (v1 algorithm)
            meta = source_img.get("meta")
            if not meta and "metadata" in source_img:
                meta = source_img.get("metadata")
            
            # Handle potential nested 'meta' key (API quirk)
            if isinstance(meta, dict) and "meta" in meta and isinstance(meta["meta"], dict):
                meta = meta["meta"]

            # Save metadata to sidecar JSON (Legacy/Compatibility)
            try:
                if meta:
                    meta_file = dest.with_suffix(dest.suffix + '.json')
                    meta_file.write_text(json.dumps(meta, indent=2))
            except Exception:
                pass
            
            # Idempotency check: Don't re-download if exists
            if not dest.exists():
                try:
                    self.civitai.download_preview_image(
                        type("Preview", (), {"url": url, "filename": filename})(),
                        dest
                    )
                except Exception:
                    pass
            
            # Extract NSFW status (handle boolean, string, or level)
            # Civitai nsfwLevel: 1=None/Safe, 2=Soft, 3+=Explicit
            nsfw_val = source_img.get("nsfw")
            nsfw_level = source_img.get("nsfwLevel")
            is_nsfw = False
            
            if nsfw_val is True:
                is_nsfw = True
            elif isinstance(nsfw_val, str) and nsfw_val.lower() not in ["none", "false", "safe"]:
                is_nsfw = True
            elif isinstance(nsfw_level, (int, float)) and nsfw_level > 1:
                is_nsfw = True  # Level 2+ is NSFW (Soft or Explicit)
                
            # Create PreviewInfo for Pack manifest
            preview_infos.append(PreviewInfo(
                filename=filename,
                url=url,
                nsfw=is_nsfw,
                width=source_img.get("width"),
                height=source_img.get("height"),
                meta=meta if isinstance(meta, dict) else None,  # Ensure it's a dict or None
            ))
        
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
    
    def _resolve_dependency(
        self,
        pack: Pack,
        dep: PackDependency,
        existing_lock: Optional[PackLock],
    ) -> Optional[ResolvedArtifact]:
        """Resolve a single dependency."""
        strategy = dep.selector.strategy
        
        if strategy == SelectorStrategy.CIVITAI_FILE:
            return self._resolve_civitai_file(dep)
        elif strategy == SelectorStrategy.CIVITAI_MODEL_LATEST:
            return self._resolve_civitai_latest(dep)
        elif strategy == SelectorStrategy.BASE_MODEL_HINT:
            return self._resolve_base_model_hint(dep)
        elif strategy == SelectorStrategy.HUGGINGFACE_FILE:
            return self._resolve_huggingface_file(dep)
        elif strategy == SelectorStrategy.URL_DOWNLOAD:
            return self._resolve_url(dep)
        elif strategy == SelectorStrategy.LOCAL_FILE:
            return self._resolve_local_file(dep)
        else:
            return None
    
    def _resolve_civitai_file(self, dep: PackDependency) -> Optional[ResolvedArtifact]:
        """Resolve a pinned Civitai file."""
        if not dep.selector.civitai:
            return None
        
        civ = dep.selector.civitai
        if not civ.version_id:
            return None
        
        # Get version data
        version_data = self.civitai.get_model_version(civ.version_id)
        files = version_data.get("files", [])
        
        # Find specific file or first
        target_file = None
        if civ.file_id:
            for f in files:
                if f.get("id") == civ.file_id:
                    target_file = f
                    break
        if not target_file and files:
            target_file = files[0]
        
        if not target_file:
            return None
        
        hashes = target_file.get("hashes", {})
        sha256 = hashes.get("SHA256", "").lower() if hashes else None
        
        download_url = target_file.get("downloadUrl", "")
        if not download_url:
            download_url = f"https://civitai.com/api/download/models/{civ.version_id}"
        
        return ResolvedArtifact(
            kind=dep.kind,
            sha256=sha256,
            size_bytes=target_file.get("sizeKB", 0) * 1024 if target_file.get("sizeKB") else None,
            provider=ArtifactProvider(
                name=ProviderName.CIVITAI,
                model_id=civ.model_id,
                version_id=civ.version_id,
                file_id=target_file.get("id"),
            ),
            download=ArtifactDownload(urls=[download_url]),
            integrity=ArtifactIntegrity(sha256_verified=sha256 is not None),
        )
    
    def _resolve_civitai_latest(self, dep: PackDependency) -> Optional[ResolvedArtifact]:
        """Resolve latest version of a Civitai model."""
        if not dep.selector.civitai:
            return None
        
        civ = dep.selector.civitai
        
        # Get model data
        model_data = self.civitai.get_model(civ.model_id)
        versions = model_data.get("modelVersions", [])
        if not versions:
            return None
        
        # Get latest version
        latest = versions[0]
        files = latest.get("files", [])
        if not files:
            return None
        
        # Find best file based on constraints
        target_file = self._select_file(files, dep.selector.constraints)
        if not target_file:
            return None
        
        hashes = target_file.get("hashes", {})
        sha256 = hashes.get("SHA256", "").lower() if hashes else None
        
        download_url = target_file.get("downloadUrl", "")
        if not download_url:
            download_url = f"https://civitai.com/api/download/models/{latest['id']}"
        
        return ResolvedArtifact(
            kind=dep.kind,
            sha256=sha256,
            size_bytes=target_file.get("sizeKB", 0) * 1024 if target_file.get("sizeKB") else None,
            provider=ArtifactProvider(
                name=ProviderName.CIVITAI,
                model_id=civ.model_id,
                version_id=latest["id"],
                file_id=target_file.get("id"),
            ),
            download=ArtifactDownload(urls=[download_url]),
            integrity=ArtifactIntegrity(sha256_verified=sha256 is not None),
        )
    
    def _select_file(
        self,
        files: List[Dict[str, Any]],
        constraints: Optional[Any],
    ) -> Optional[Dict[str, Any]]:
        """Select best file from list based on constraints."""
        if not files:
            return None
        
        candidates = files.copy()
        
        if constraints:
            # Filter by primary file
            if constraints.primary_file_only:
                primary = [f for f in candidates if f.get("primary")]
                if primary:
                    candidates = primary
            
            # Filter by extension
            if constraints.file_ext:
                ext_filtered = [
                    f for f in candidates
                    if any(f.get("name", "").endswith(ext) for ext in constraints.file_ext)
                ]
                if ext_filtered:
                    candidates = ext_filtered
        
        # Return first remaining candidate
        return candidates[0] if candidates else None
    
    def _resolve_base_model_hint(self, dep: PackDependency) -> Optional[ResolvedArtifact]:
        """Resolve a base model hint using config aliases."""
        if not dep.selector.base_model:
            return None
        
        try:
            config = self.layout.load_config()
            alias = config.base_model_aliases.get(dep.selector.base_model)
            if not alias or not alias.selector.civitai:
                return None
            
            # Resolve via Civitai
            civ = alias.selector.civitai
            if civ.version_id:
                version_data = self.civitai.get_model_version(civ.version_id)
                files = version_data.get("files", [])
                
                target_file = None
                if civ.file_id:
                    for f in files:
                        if f.get("id") == civ.file_id:
                            target_file = f
                            break
                if not target_file and files:
                    target_file = files[0]
                
                if target_file:
                    hashes = target_file.get("hashes", {})
                    sha256 = hashes.get("SHA256", "").lower() if hashes else None
                    
                    download_url = target_file.get("downloadUrl", "")
                    if not download_url:
                        download_url = f"https://civitai.com/api/download/models/{civ.version_id}"
                    
                    return ResolvedArtifact(
                        kind=dep.kind,
                        sha256=sha256,
                        size_bytes=target_file.get("sizeKB", 0) * 1024 if target_file.get("sizeKB") else None,
                        provider=ArtifactProvider(
                            name=ProviderName.CIVITAI,
                            model_id=civ.model_id,
                            version_id=civ.version_id,
                            file_id=target_file.get("id"),
                        ),
                        download=ArtifactDownload(urls=[download_url]),
                        integrity=ArtifactIntegrity(sha256_verified=sha256 is not None),
                    )
        except Exception:
            pass
        
        return None
    
    def _resolve_huggingface_file(self, dep: PackDependency) -> Optional[ResolvedArtifact]:
        """Resolve a HuggingFace file."""
        if not dep.selector.huggingface:
            return None
        
        hf = dep.selector.huggingface
        
        # Build download URL
        url = f"https://huggingface.co/{hf.repo_id}/resolve/{hf.revision or 'main'}"
        if hf.subfolder:
            url += f"/{hf.subfolder}"
        url += f"/{hf.filename}"
        
        return ResolvedArtifact(
            kind=dep.kind,
            sha256=None,  # HF doesn't provide SHA256 easily
            size_bytes=None,
            provider=ArtifactProvider(
                name=ProviderName.HUGGINGFACE,
                repo_id=hf.repo_id,
                filename=hf.filename,
                revision=hf.revision,
            ),
            download=ArtifactDownload(urls=[url]),
            integrity=ArtifactIntegrity(sha256_verified=False),
        )
    
    def _resolve_url(self, dep: PackDependency) -> Optional[ResolvedArtifact]:
        """Resolve a direct URL download."""
        if not dep.selector.url:
            return None
        
        return ResolvedArtifact(
            kind=dep.kind,
            sha256=None,
            size_bytes=None,
            provider=ArtifactProvider(name=ProviderName.URL),
            download=ArtifactDownload(urls=[dep.selector.url]),
            integrity=ArtifactIntegrity(sha256_verified=False),
        )
    
    def _resolve_local_file(self, dep: PackDependency) -> Optional[ResolvedArtifact]:
        """Resolve a local file."""
        if not dep.selector.local_path:
            return None
        
        path = Path(dep.selector.local_path)
        if not path.exists():
            return None
        
        # Compute SHA256
        from .blob_store import compute_sha256
        sha256 = compute_sha256(path)
        
        return ResolvedArtifact(
            kind=dep.kind,
            sha256=sha256,
            size_bytes=path.stat().st_size,
            provider=ArtifactProvider(name=ProviderName.LOCAL),
            download=ArtifactDownload(urls=[path.as_uri()]),
            integrity=ArtifactIntegrity(sha256_verified=True),
        )
    
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
        
        installed = []
        
        for resolved in lock.resolved:
            sha256 = resolved.artifact.sha256
            urls = resolved.artifact.download.urls
            
            if not urls:
                continue
            
            # Skip if already downloaded
            if sha256 and self.blob_store.blob_exists(sha256):
                installed.append(sha256)
                continue
            
            # Download
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
                
                # Update lock with actual SHA if it was unknown
                if not sha256:
                    resolved.artifact.sha256 = actual_sha
                    resolved.artifact.integrity.sha256_verified = True
                    self.layout.save_pack_lock(lock)
                    
            except Exception:
                pass  # Log error, continue
        
        return installed
