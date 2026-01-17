"""
Pack Builder

Creates Synapse packs from various sources:
- Use-case 1: From Civitai URL
- Use-case 2: From workflow JSON file
- Use-case 3: From local models folder scan
- Use-case 4: From PNG image metadata
"""

import json
import re
import os
import base64
import requests
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from dataclasses import dataclass

from .models import (
    Pack, PackMetadata, AssetDependency, CustomNodeDependency,
    PreviewImage, WorkflowInfo, AssetType, AssetSource,
    CivitaiSource, HuggingFaceSource, ASSET_TYPE_FOLDERS,
    GenerationParameters, ModelInfo, DependencyStatus, AssetHash
)
from ..clients.civitai_client import CivitaiClient, CivitaiModel, CivitaiModelVersion
from ..clients.huggingface_client import HuggingFaceClient
from ..workflows.scanner import WorkflowScanner, WorkflowScanResult
from ..workflows.resolver import DependencyResolver
from ..utils.media_detection import detect_media_type, get_video_thumbnail_url

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class PackBuildResult:
    """Result of building a pack."""
    pack: Optional[Pack]
    success: bool
    errors: List[str]
    warnings: List[str]
    pack_dir: Optional[Path] = None


class PackBuilder:
    """
    Builds Synapse packs from various sources.
    
    Supports all 4 use-cases:
    1. Civitai URL → Pack
    2. Workflow JSON → Pack
    3. Local folder scan → Pack
    4. PNG metadata → Pack
    """
    
    def __init__(
        self,
        config=None,
        civitai_client: Optional[CivitaiClient] = None,
        huggingface_client: Optional[HuggingFaceClient] = None,
        resolver: Optional[DependencyResolver] = None,
        scanner: Optional[WorkflowScanner] = None,
    ):
        self.config = config
        
        # Create clients with tokens from config if available
        if civitai_client:
            self.civitai = civitai_client
        else:
            api_token = None
            if config and hasattr(config, 'api') and hasattr(config.api, 'civitai_token'):
                api_token = config.api.civitai_token
            self.civitai = CivitaiClient(api_key=api_token)
        
        if huggingface_client:
            self.huggingface = huggingface_client
        else:
            hf_token = None
            if config and hasattr(config, 'api') and hasattr(config.api, 'huggingface_token'):
                hf_token = config.api.huggingface_token
            self.huggingface = HuggingFaceClient(token=hf_token)
        
        self.resolver = resolver or DependencyResolver()
        self.scanner = scanner or WorkflowScanner()
    
    # =========================================================================
    # USE-CASE 1: Build from Civitai URL
    # =========================================================================
    
    def build_from_civitai_url(
        self,
        url: str,
        pack_name: Optional[str] = None,
        pack_dir: Optional[Path] = None,
        include_previews: bool = True,
        max_previews: int = 50,
        download_previews: bool = True,
    ) -> PackBuildResult:
        """
        Build a pack from a Civitai model URL.
        
        Extracts:
        - Model metadata (name, description, tags)
        - Primary model file as dependency
        - Base model as dependency (unresolved)
        - Preview images with NSFW flags (downloaded to resources)
        - Generation parameters from example images
        - Model info table (trigger words, hash, etc.)
        """
        errors = []
        warnings = []
        
        print(f"[IMPORT DEBUG] === Starting import from: {url} ===")
        logger.info(f"[PackBuilder] Building from URL: {url}")
        
        try:
            # Parse URL
            model_id, version_id = self.civitai.parse_civitai_url(url)
            print(f"[IMPORT DEBUG] Parsed model_id={model_id}, version_id={version_id}")
            logger.info(f"[PackBuilder] Parsed model_id={model_id}, version_id={version_id}")
            
            # Fetch model data (as dict)
            model_data = self.civitai.get_model(model_id)
            print(f"[IMPORT DEBUG] Fetched model: {model_data.get('name', 'unknown')}")
            logger.info(f"[PackBuilder] Fetched model data: {model_data.get('name', 'unknown')}")
            
            # Convert to objects for easier handling
            model = CivitaiModel.from_api_response(model_data)
            print(f"[IMPORT DEBUG] CivitaiModel created: name={model.name}, type={model.type}")
            logger.info(f"[PackBuilder] Model: {model.name}, type: {model.type}")
            
            # Get specific version or latest
            if version_id:
                version = next(
                    (v for v in model.model_versions if v.id == version_id),
                    model.model_versions[0] if model.model_versions else None
                )
            else:
                version = model.model_versions[0] if model.model_versions else None
            
            if not version:
                logger.error("[PackBuilder] No model version found")
                return PackBuildResult(
                    pack=None,
                    success=False,
                    errors=["No model version found"],
                    warnings=[],
                )
            
            logger.info(f"[PackBuilder] Using version: {version.name} (ID: {version.id})")

            # ------------------------------------------------------------------
            # METADATA ENRICHMENT: Fetch detailed version data for images
            # ------------------------------------------------------------------
            detailed_version_images = []
            try:
                logger.info(f"[PackBuilder] Fetching detailed version metadata from: {version.id}")
                # The raw API response for version contains 'images' list with full 'meta' dicts
                ver_detail = self.civitai.get_model_version(version.id)
                detailed_version_images = ver_detail.get("images", [])
                logger.debug(f"[PackBuilder] Got {len(detailed_version_images)} detailed images")
            except Exception as e:
                logger.warning(f"[PackBuilder] Failed to fetch detailed version info: {e}")
                # Non-fatal, just continue with basic info
            
            # Create pack name and directory
            name = pack_name or self._sanitize_name(model.name)
            if pack_dir is None and self.config:
                pack_dir = self.config.packs_path / name
            elif pack_dir is None:
                pack_dir = Path.home() / ".synapse" / "packs" / name
            
            pack_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"[PackBuilder] Pack directory: {pack_dir}")
            
            # Create pack metadata
            metadata = PackMetadata(
                name=name,
                version=version.name or "1.0.0",
                description=model.description,
                author=model.creator.get("username") if model.creator else None,
                tags=model.tags,
                user_tags=[],  # User can add later
                created_at=datetime.now().isoformat(),
                source_url=url,
            )
            
            # Create main asset dependency
            main_dependency = self.civitai.create_asset_dependency(model, version)
            main_dependency.status = DependencyStatus.RESOLVED
            dependencies = [main_dependency]
            
            # Create base model dependency (unresolved - needs user to select)
            if version.base_model:
                base_model_dep = AssetDependency(
                    name=f"Base Model: {version.base_model}",
                    asset_type=AssetType.BASE_MODEL,
                    source=AssetSource.UNRESOLVED,
                    filename="",
                    required=True,
                    status=DependencyStatus.UNRESOLVED,
                    base_model_hint=version.base_model,
                    description=f"Required base model: {version.base_model}. Please select a specific checkpoint.",
                )
                dependencies.append(base_model_dep)
            
            # Extract generation parameters from example images
            parameters = self._extract_parameters_from_version(version, model_data)
            print(f"[IMPORT DEBUG] parameters after extraction: {parameters}")
            if parameters:
                print(f"[IMPORT DEBUG] parameters.to_dict(): {parameters.to_dict()}")
            
            # Extract model info table
            print(f"[IMPORT DEBUG] Extracting model_info...")
            print(f"[IMPORT DEBUG] model.type = {model.type}")
            try:
                model_info = self._extract_model_info(model, version, model_data)
                print(f"[IMPORT DEBUG] model_info created successfully")
            except AttributeError as e:
                print(f"[IMPORT DEBUG] ERROR in _extract_model_info: {e}")
                import traceback
                traceback.print_exc()
                raise
            
            # Get and download preview images
            previews = []
            if include_previews:
                previews = self._download_preview_images(
                    version, 
                    pack_dir, 
                    max_previews,
                    download_previews,
                    detailed_version_images=detailed_version_images
                )
            
            # Extract hints from description and trained words
            docs = {}
            if model.description:
                docs["source.md"] = model.description
            
            hints = {
                "trained_words": version.trained_words,
                "base_model": version.base_model,
                "nsfw": model.nsfw,
            }
            if parameters:
                hints["parameters"] = parameters.to_dict()
            docs["extracted_hints.json"] = json.dumps(hints, indent=2, ensure_ascii=False)
            
            # Build pack
            pack = Pack(
                metadata=metadata,
                dependencies=dependencies,
                custom_nodes=[],
                workflows=[],
                previews=previews,
                docs=docs,
                parameters=parameters,
                model_info=model_info,
            )
            
            return PackBuildResult(
                pack=pack,
                success=True,
                errors=errors,
                warnings=warnings,
                pack_dir=pack_dir,
            )
            
        except Exception as e:
            return PackBuildResult(
                pack=None,
                success=False,
                errors=[str(e)],
                warnings=warnings,
            )
    
    def _download_preview_images(
        self,
        version: CivitaiModelVersion,
        pack_dir: Path,
        max_previews: int,
        download: bool = True,
        detailed_version_images: List[Dict[str, Any]] = None,
    ) -> List[PreviewImage]:
        """
        Download preview media (images and videos) to pack resources directory.
        
        Detects media type from URL and handles both images and videos.
        """
        # Local imports to avoid circular dependency issues if any (though top-level is fine usually)
        from ..utils.media_detection import detect_media_type, get_video_thumbnail_url
        
        previews = []
        resources_dir = pack_dir / "resources" / "previews"
        
        if download:
            resources_dir.mkdir(parents=True, exist_ok=True)
        
        # Create lookup map for detailed images by URL
        detailed_map = {}
        if detailed_version_images:
            for img in detailed_version_images:
                url = img.get("url")
                if url:
                    detailed_map[url] = img
        
        # Get images from version (basic summary data)
        images = version.images[:max_previews] if version.images else []
        
        for i, img_data in enumerate(images):
            url = img_data.get("url", "")
            if not url:
                continue
                
            # MERGE: Check if we have richer data for this image
            detailed_img = detailed_map.get(url)
            source_img = detailed_img if detailed_img else img_data
            
            # Determine NSFW status
            nsfw = source_img.get("nsfw", False)
            nsfw_level = source_img.get("nsfwLevel", 0)
            if nsfw_level >= 2:
                nsfw = True
            
            # Detect media type from URL
            media_info = detect_media_type(url, use_head_request=False)
            media_type = media_info.type.value  # 'image', 'video', or 'unknown'
            
            # Generate filename with appropriate extension
            url_path = url.split("?")[0]
            original_ext = Path(url_path).suffix or ".png"
            
            # For videos, ensure we use video extension
            if media_type == 'video' and original_ext in ['.jpg', '.jpeg', '.png']:
                # Civitai sometimes serves videos as .jpeg - keep original but mark as video
                pass
            
            filename = f"preview_{i+1}{original_ext}"
            local_path = f"resources/previews/{filename}"
            
            # Extract metadata safely
            meta = source_img.get("meta")
            if not meta and "metadata" in source_img:
                meta = source_img.get("metadata")
                
            # Handle potential nested 'meta' key (API v1 quirk)
            if isinstance(meta, dict) and "meta" in meta and isinstance(meta["meta"], dict):
                meta = meta["meta"]
            
            # Get video thumbnail URL
            thumbnail_url = None
            if media_type == 'video':
                thumbnail_url = get_video_thumbnail_url(url)
            
            # Create PreviewImage with media type
            preview = PreviewImage(
                filename=filename,
                url=url,
                local_path=local_path,
                nsfw=nsfw,
                width=source_img.get("width"),
                height=source_img.get("height"),
                media_type=media_type,
                thumbnail_url=thumbnail_url,
                meta=meta if isinstance(meta, dict) else None,
            )
            
            # Download the media file
            if download:
                try:
                    dest_path = resources_dir / filename
                    response = requests.get(url, timeout=60, stream=True)  # Longer timeout for videos
                    if response.status_code == 200:
                        with open(dest_path, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                f.write(chunk)
                        
                        # Log video downloads
                        if media_type == 'video':
                            file_size = dest_path.stat().st_size
                            print(f"[PackBuilder] Downloaded video preview: {filename} ({file_size / 1024 / 1024:.1f} MB)")
                            
                except Exception as e:
                    print(f"Warning: Failed to download preview {url}: {e}")
            
            previews.append(preview)
        
        return previews
    
    def _extract_parameters_from_version(
        self,
        version: CivitaiModelVersion,
        model_data: Dict[str, Any],
    ) -> Optional[GenerationParameters]:
        """Extract generation parameters from version's example images."""
        print(f"[IMPORT DEBUG] _extract_parameters_from_version called")
        print(f"[IMPORT DEBUG] Looking for version.id = {version.id}")
        
        model_versions = model_data.get("modelVersions", [])
        print(f"[IMPORT DEBUG] Found {len(model_versions)} model versions in model_data")
        
        # Try to get meta from first image with generation data
        for ver_data in model_versions:
            ver_id = ver_data.get("id")
            print(f"[IMPORT DEBUG] Checking version id={ver_id} vs target={version.id}")
            
            if ver_id != version.id:
                continue
            
            print(f"[IMPORT DEBUG] Found matching version!")
            images = ver_data.get("images", [])
            print(f"[IMPORT DEBUG] Version has {len(images)} images")
            
            for idx, img in enumerate(images):
                print(f"[IMPORT DEBUG] Image {idx} keys: {list(img.keys())}")
                meta = img.get("meta", {})
                
                # Meta can also be under 'metadata' in some API responses
                if not meta:
                    meta = img.get("metadata", {})
                
                print(f"[IMPORT DEBUG] Image {idx} meta: {meta}")
                
                if meta:
                    print(f"[IMPORT DEBUG] Found meta in image {idx}: {list(meta.keys())}")
                    
                    # Parse width/height - can be in meta directly or in "Size" field
                    width = meta.get("width")
                    height = meta.get("height")
                    
                    # Try to parse from "Size" field like "512x768"
                    if not width or not height:
                        size_str = meta.get("Size", "")
                        if size_str and "x" in size_str:
                            try:
                                parts = size_str.split("x")
                                width = width or int(parts[0])
                                height = height or int(parts[1])
                            except (ValueError, IndexError):
                                pass
                    
                    # Ensure numeric types
                    try:
                        steps = int(meta.get("steps")) if meta.get("steps") is not None else None
                    except (ValueError, TypeError):
                        steps = None
                    
                    try:
                        cfg_scale = float(meta.get("cfgScale")) if meta.get("cfgScale") is not None else None
                    except (ValueError, TypeError):
                        cfg_scale = None
                    
                    try:
                        clip_skip = int(meta.get("clipSkip")) if meta.get("clipSkip") is not None else None
                    except (ValueError, TypeError):
                        clip_skip = None
                    
                    try:
                        seed = int(meta.get("seed")) if meta.get("seed") is not None else None
                    except (ValueError, TypeError):
                        seed = None
                    
                    params = GenerationParameters(
                        sampler=meta.get("sampler"),
                        scheduler=meta.get("scheduler"),
                        steps=steps,
                        cfg_scale=cfg_scale,
                        clip_skip=clip_skip,
                        denoise=meta.get("denoise") or meta.get("denoising"),
                        width=int(width) if width else None,
                        height=int(height) if height else None,
                        seed=seed,
                        hires_fix=bool(meta.get("hiresFix") or meta.get("Hires fix")),
                        hires_upscaler=meta.get("hiresUpscaler") or meta.get("Hires upscaler"),
                        hires_steps=meta.get("hiresSteps") or meta.get("Hires steps"),
                        hires_denoise=meta.get("hiresDenoising") or meta.get("Hires upscale"),
                    )
                    
                    params_dict = params.to_dict()
                    print(f"[IMPORT DEBUG] Extracted parameters: {params_dict}")
                    
                    if params_dict:  # Only return if we actually got some parameters
                        return params
                    else:
                        print(f"[IMPORT DEBUG] Parameters dict is empty, continuing to next image...")
        
        print(f"[IMPORT DEBUG] No parameters found in any image!")
        return None
    
    def _extract_model_info(
        self,
        model: CivitaiModel,
        version: CivitaiModelVersion,
        model_data: Dict[str, Any],
    ) -> ModelInfo:
        """Extract model info table from Civitai data."""
        # Get file hash
        hash_autov2 = None
        hash_sha256 = None
        
        for ver_data in model_data.get("modelVersions", []):
            if ver_data.get("id") != version.id:
                continue
            
            for file in ver_data.get("files", []):
                hashes = file.get("hashes", {})
                hash_autov2 = hashes.get("AutoV2")
                hash_sha256 = hashes.get("SHA256")
                break
        
        # Get stats
        stats = model_data.get("stats", {})
        
        # Get usage tips from first image meta
        usage_tips = None
        for ver_data in model_data.get("modelVersions", []):
            if ver_data.get("id") != version.id:
                continue
            for img in ver_data.get("images", []):
                meta = img.get("meta", {})
                if meta.get("clipSkip"):
                    usage_tips = f"CLIP Skip: {meta.get('clipSkip')}"
                if meta.get("cfgScale"):
                    usage_tips = (usage_tips + ", " if usage_tips else "") + f"CFG: {meta.get('cfgScale')}"
                break
        
        # Get recommended strength from version
        strength = None
        for ver_data in model_data.get("modelVersions", []):
            if ver_data.get("id") == version.id:
                strength = ver_data.get("baseModelStrength")
                break
        
        return ModelInfo(
            model_type=model.type,
            base_model=version.base_model,
            trigger_words=version.trained_words[:10] if version.trained_words else [],
            trained_words=version.trained_words,
            usage_tips=usage_tips,
            hash_autov2=hash_autov2,
            hash_sha256=hash_sha256,
            civitai_air=f"civitai: {model.id} @ {version.id}",
            download_count=stats.get("downloadCount"),
            rating=stats.get("rating"),
            published_at=version.published_at,
            strength_recommended=strength,
        )
    
    # =========================================================================
    # USE-CASE 2: Build from Workflow JSON
    # =========================================================================
    
    def build_from_workflow(
        self,
        workflow_path: Path,
        pack_name: Optional[str] = None,
        pack_dir: Optional[Path] = None,
    ) -> PackBuildResult:
        """
        Build a pack from a ComfyUI workflow JSON file.
        
        Scans the workflow to extract:
        - Model dependencies (checkpoints, LoRAs, VAEs, etc.)
        - Custom node requirements
        - Includes the workflow as upstream
        """
        errors = []
        warnings = []
        
        try:
            # Scan workflow
            scan_result = self.scanner.scan_file(workflow_path)
            
            if scan_result.errors:
                errors.extend(scan_result.errors)
            
            # Resolve dependencies
            asset_deps, node_deps = self.resolver.resolve_workflow_dependencies(scan_result)
            
            # Check for unresolved assets
            for dep in asset_deps:
                if dep.source == AssetSource.LOCAL:
                    warnings.append(
                        f"Asset '{dep.name}' source unknown - may need manual resolution"
                    )
            
            # Create pack name and directory
            name = pack_name or workflow_path.stem
            name = self._sanitize_name(name)
            
            if pack_dir is None and self.config:
                pack_dir = self.config.packs_path / name
            elif pack_dir is None:
                pack_dir = Path.home() / ".synapse" / "packs" / name
            
            pack_dir.mkdir(parents=True, exist_ok=True)
            
            # Create metadata
            metadata = PackMetadata(
                name=name,
                version="1.0.0",
                description=f"Pack created from workflow: {workflow_path.name}",
                created_at=datetime.now().isoformat(),
            )
            
            # Create workflow info
            workflow_info = WorkflowInfo(
                name=workflow_path.stem,
                filename=workflow_path.name,
                description="Original imported workflow",
            )
            
            # Build pack
            pack = Pack(
                metadata=metadata,
                dependencies=asset_deps,
                custom_nodes=node_deps,
                workflows=[workflow_info],
                previews=[],
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
            return PackBuildResult(
                pack=None,
                success=False,
                errors=[str(e)],
                warnings=warnings,
            )
    
    # =========================================================================
    # USE-CASE 3: Build from Local Folder Scan
    # =========================================================================
    
    def build_from_local_scan(
        self,
        comfyui_path: Path,
        pack_name: str = "local_models",
        pack_dir: Optional[Path] = None,
    ) -> PackBuildResult:
        """
        Build a pack from scanning local ComfyUI models folder.
        
        Creates a pack documenting existing local models.
        """
        errors = []
        warnings = []
        
        try:
            models_path = comfyui_path / "models"
            
            if not models_path.exists():
                return PackBuildResult(
                    pack=None,
                    success=False,
                    errors=[f"Models directory not found: {models_path}"],
                    warnings=[],
                )
            
            # Scan each model type folder
            dependencies = []
            
            for asset_type, folder_name in ASSET_TYPE_FOLDERS.items():
                folder_path = models_path / folder_name
                
                if not folder_path.exists():
                    continue
                
                # Scan for safetensors files
                for file_path in folder_path.rglob("*.safetensors"):
                    rel_path = file_path.relative_to(models_path)
                    
                    dep = AssetDependency(
                        name=file_path.stem,
                        asset_type=asset_type,
                        source=AssetSource.LOCAL,
                        filename=file_path.name,
                        local_path=str(rel_path),
                        file_size=file_path.stat().st_size,
                        status=DependencyStatus.INSTALLED,
                    )
                    dependencies.append(dep)
                
                # Also check for .ckpt and .pt files
                for ext in [".ckpt", ".pt", ".bin", ".gguf"]:
                    for file_path in folder_path.rglob(f"*{ext}"):
                        rel_path = file_path.relative_to(models_path)
                        
                        dep = AssetDependency(
                            name=file_path.stem,
                            asset_type=asset_type,
                            source=AssetSource.LOCAL,
                            filename=file_path.name,
                            local_path=str(rel_path),
                            file_size=file_path.stat().st_size,
                            status=DependencyStatus.INSTALLED,
                        )
                        dependencies.append(dep)
            
            if not dependencies:
                warnings.append("No model files found in scan")
            
            # Create pack directory
            if pack_dir is None and self.config:
                pack_dir = self.config.packs_path / pack_name
            elif pack_dir is None:
                pack_dir = Path.home() / ".synapse" / "packs" / pack_name
            
            pack_dir.mkdir(parents=True, exist_ok=True)
            
            # Create metadata
            metadata = PackMetadata(
                name=self._sanitize_name(pack_name),
                version="1.0.0",
                description=f"Pack created from local scan of {comfyui_path}",
                created_at=datetime.now().isoformat(),
            )
            
            # Build pack
            pack = Pack(
                metadata=metadata,
                dependencies=dependencies,
                custom_nodes=[],
                workflows=[],
                previews=[],
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
            return PackBuildResult(
                pack=None,
                success=False,
                errors=[str(e)],
                warnings=warnings,
            )
    
    # =========================================================================
    # USE-CASE 4: Build from PNG Metadata
    # =========================================================================
    
    def build_from_png_metadata(
        self,
        image_path: Path,
        pack_name: Optional[str] = None,
        pack_dir: Optional[Path] = None,
    ) -> PackBuildResult:
        """
        Build a pack from PNG image metadata (ComfyUI workflow embed).
        
        Extracts embedded workflow data from PNG and creates a pack
        with all dependencies.
        """
        errors = []
        warnings = []
        
        try:
            # Extract metadata from PNG
            workflow_data = self._extract_png_metadata(image_path)
            
            if not workflow_data:
                return PackBuildResult(
                    pack=None,
                    success=False,
                    errors=["No workflow metadata found in PNG"],
                    warnings=[],
                )
            
            # Parse workflow
            if isinstance(workflow_data, str):
                workflow_data = json.loads(workflow_data)
            
            # Scan workflow
            scan_result = self.scanner.scan_workflow(workflow_data)
            
            if scan_result.errors:
                errors.extend(scan_result.errors)
            
            # Resolve dependencies
            asset_deps, node_deps = self.resolver.resolve_workflow_dependencies(scan_result)
            
            # Create pack name and directory
            name = pack_name or image_path.stem
            name = self._sanitize_name(name)
            
            if pack_dir is None and self.config:
                pack_dir = self.config.packs_path / name
            elif pack_dir is None:
                pack_dir = Path.home() / ".synapse" / "packs" / name
            
            pack_dir.mkdir(parents=True, exist_ok=True)
            
            # Create metadata
            metadata = PackMetadata(
                name=name,
                version="1.0.0",
                description=f"Pack extracted from image: {image_path.name}",
                created_at=datetime.now().isoformat(),
            )
            
            # Copy the image as a preview
            resources_dir = pack_dir / "resources" / "previews"
            resources_dir.mkdir(parents=True, exist_ok=True)
            
            import shutil
            preview_path = resources_dir / image_path.name
            shutil.copy2(image_path, preview_path)
            
            previews = [PreviewImage(
                filename=image_path.name,
                local_path=f"resources/previews/{image_path.name}",
                nsfw=False,  # User can flag later
            )]
            
            # Build pack
            pack = Pack(
                metadata=metadata,
                dependencies=asset_deps,
                custom_nodes=node_deps,
                workflows=[],  # Workflow embedded in image
                previews=previews,
                docs={"extracted_workflow.json": json.dumps(workflow_data, indent=2)},
            )
            
            return PackBuildResult(
                pack=pack,
                success=True,
                errors=errors,
                warnings=warnings,
                pack_dir=pack_dir,
            )
            
        except Exception as e:
            return PackBuildResult(
                pack=None,
                success=False,
                errors=[str(e)],
                warnings=warnings,
            )
    
    def _extract_png_metadata(self, path: Path) -> Optional[Dict[str, Any]]:
        """
        Extract ComfyUI workflow metadata from PNG.
        
        ComfyUI stores workflow in PNG tEXt chunks with keys:
        - "workflow" - API format workflow
        - "prompt" - execution prompt
        """
        try:
            import struct
            import zlib
            
            with open(path, 'rb') as f:
                # Check PNG signature
                signature = f.read(8)
                if signature != b'\x89PNG\r\n\x1a\n':
                    return None
                
                # Read chunks
                while True:
                    try:
                        length_bytes = f.read(4)
                        if len(length_bytes) < 4:
                            break
                        
                        length = struct.unpack('>I', length_bytes)[0]
                        chunk_type = f.read(4)
                        chunk_data = f.read(length)
                        crc = f.read(4)
                        
                        # Check for tEXt chunk
                        if chunk_type == b'tEXt':
                            # Format: keyword\x00text
                            null_pos = chunk_data.find(b'\x00')
                            if null_pos > 0:
                                keyword = chunk_data[:null_pos].decode('latin-1')
                                text = chunk_data[null_pos + 1:].decode('utf-8')
                                
                                if keyword == 'workflow':
                                    return json.loads(text)
                                elif keyword == 'prompt':
                                    # Prompt contains node data
                                    return json.loads(text)
                        
                        # Check for iTXt chunk (compressed text)
                        elif chunk_type == b'iTXt':
                            # More complex format with compression
                            null_pos = chunk_data.find(b'\x00')
                            if null_pos > 0:
                                keyword = chunk_data[:null_pos].decode('latin-1')
                                if keyword in ('workflow', 'prompt'):
                                    # Skip compression flag and method
                                    rest = chunk_data[null_pos + 3:]
                                    # Find text after language tag
                                    null_pos2 = rest.find(b'\x00')
                                    if null_pos2 >= 0:
                                        text_data = rest[null_pos2 + 1:]
                                        try:
                                            text = text_data.decode('utf-8')
                                            return json.loads(text)
                                        except:
                                            pass
                        
                        # End of chunks
                        if chunk_type == b'IEND':
                            break
                    
                    except struct.error:
                        break
            
            return None
            
        except Exception:
            return None
    
    def _sanitize_name(self, name: str) -> str:
        """Sanitize a name for use as pack identifier."""
        # Remove special characters, keep alphanumeric and some safe chars
        sanitized = re.sub(r'[^\w\s\-_]', '', name)
        # Replace spaces with underscores
        sanitized = re.sub(r'\s+', '_', sanitized)
        # Limit length
        return sanitized[:64]


def create_pack_builder() -> PackBuilder:
    """Factory function to create a configured PackBuilder."""
    return PackBuilder()
